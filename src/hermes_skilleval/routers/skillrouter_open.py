"""Opt-in public SkillRouter inference; no fallback and no default-route change.

Formatting/pooling is from SkillRouter 2f0c69fe (MIT, vendor/SkillRouter-LICENSE).
Weights remain separately licensed public assets. Local Qwen3 needs no remote code.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from hermes_skilleval.vendor import skillrouter_common as ref


@dataclass(frozen=True)
class OpenProfile:
    device: str = "cpu"
    dtype: str = "float32"
    encoder_max_length: int = 4096
    reranker_max_length: int = 4096
    batch_size: int = 1
    retrieval_top_k: int = 20
    desc_max: int = 500
    encoder_body_max: int = 8000
    reranker_body_max: int = 2000
    query_chars: int = 2000
    attention: str = "sdpa"

    def __post_init__(self):
        if self.device not in ("cpu", "mps", "cuda") or self.dtype not in (
            "float32",
            "float16",
            "bfloat16",
        ):
            raise ValueError("unsupported device/dtype")
        for field in (
            "encoder_max_length",
            "reranker_max_length",
            "batch_size",
            "retrieval_top_k",
            "desc_max",
            "encoder_body_max",
            "reranker_body_max",
            "query_chars",
        ):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")


def asset_identity(path: Path, revision: str) -> dict:
    if not path.is_dir() or not revision:
        raise ValueError("local model and explicit revision required")
    files = sorted(
        p
        for p in path.iterdir()
        if p.is_file() and p.suffix in (".json", ".txt", ".safetensors")
    )
    if not any(p.suffix == ".safetensors" for p in files):
        raise ValueError("real model weights missing")
    hashes = {}
    for file in files:
        with file.open("rb") as stream:
            hashes[file.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"revision": revision, "files": hashes}


def token_record(tokenizer, text: str, max_length: int) -> dict:
    full = tokenizer(text, add_special_tokens=True, return_offsets_mapping=True)
    actual = tokenizer(
        text, truncation=True, max_length=max_length, return_offsets_mapping=True
    )
    offsets = [v for v in actual["offset_mapping"] if v[1] > v[0]]
    return {
        "formatted_chars": len(text),
        "tokens_before": len(full["input_ids"]),
        "actual_tokens": len(actual["input_ids"]),
        "input_ids": actual["input_ids"],
        "visible_char_spans": offsets,
        "truncation_side": tokenizer.truncation_side,
        "special_tokens": sum(a == b for a, b in actual["offset_mapping"]),
    }


class SkillRouterOpen:
    def __init__(
        self,
        encoder_path: Path,
        reranker_path: Path,
        *,
        encoder_revision: str,
        reranker_revision: str,
        profile: OpenProfile | None = None,
    ):
        import torch
        from transformers import AutoTokenizer

        self.profile = profile or OpenProfile()
        self.paths = {"encoder": Path(encoder_path), "reranker": Path(reranker_path)}
        self.identity = {
            "encoder": asset_identity(self.paths["encoder"], encoder_revision),
            "reranker": asset_identity(self.paths["reranker"], reranker_revision),
            "profile": asdict(self.profile),
            "implementation": "skillrouter-open-v1",
        }
        self.dtype = getattr(torch, self.profile.dtype)
        self.asset_metadata = self._metadata()
        self.tokenizers = {
            k: AutoTokenizer.from_pretrained(
                str(v),
                local_files_only=True,
                trust_remote_code=False,
                padding_side="left",
            )
            for k, v in self.paths.items()
        }
        for tok in self.tokenizers.values():
            if tok.pad_token is None:
                tok.pad_token = tok.eos_token
        self.model = None
        self.kind = None
        self.load_seconds: dict[str, float] = {}

    def _metadata(self):
        return [
            (kind, p.name, p.stat().st_size, p.stat().st_mtime_ns)
            for kind, root in self.paths.items()
            for p in sorted(root.iterdir())
            if p.is_file() and p.suffix in (".json", ".txt", ".safetensors")
        ]

    def _check_assets(self):
        if self._metadata() != self.asset_metadata:
            raise ValueError("model assets changed; reload and rebuild the index")

    def _load(self, kind):
        self._check_assets()
        import gc
        import torch
        from transformers import AutoModel, AutoModelForCausalLM

        if self.kind == kind:
            return self.model
        self.model = None
        gc.collect()
        if self.profile.device == "mps":
            torch.mps.empty_cache()
        started = time.perf_counter()
        cls = AutoModel if kind == "encoder" else AutoModelForCausalLM
        self.model = (
            cls.from_pretrained(
                str(self.paths[kind]),
                local_files_only=True,
                trust_remote_code=False,
                dtype=self.dtype,
                attn_implementation=self.profile.attention,
            )
            .to(self.profile.device)
            .eval()
        )
        self.kind = kind
        self.load_seconds[kind] = time.perf_counter() - started
        return self.model

    def encode(self, texts):
        import torch

        if not texts:
            raise ValueError("empty encoding batch")
        vectors = ref.encode_texts(
            self._load("encoder"),
            self.tokenizers["encoder"],
            texts,
            self.profile.encoder_max_length,
            self.profile.batch_size,
            torch.device(self.profile.device),
        ).float()
        if vectors.ndim != 2 or not torch.isfinite(vectors).all():
            raise ValueError("invalid encoder vectors")
        return vectors

    def index(
        self,
        skills: list[dict],
        cache: Path | None = None,
        *,
        registry_id: str | None = None,
    ):
        self._check_assets()
        import torch

        ids = [s["id"] for s in skills]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("pool must be nonempty with unique IDs")
        self.skills = skills
        self.texts = [
            ref.format_skill(s, self.profile.desc_max, self.profile.encoder_body_max)
            for s in skills
        ]
        cache_identity = [self.identity, ids, self.texts]
        if registry_id is not None:
            cache_identity.append({"registry_id": registry_id})
        key = hashlib.sha256(
            json.dumps(cache_identity, sort_keys=True).encode()
        ).hexdigest()
        start = time.perf_counter()
        if cache is not None and cache.exists():
            saved = json.loads(cache.read_text())
            if saved["key"] == key:
                vectors = torch.tensor(saved["vectors"], dtype=torch.float32)
                dimension = json.loads(
                    (self.paths["encoder"] / "config.json").read_text()
                )["hidden_size"]
                if (
                    vectors.shape != (len(ids), dimension)
                    or not torch.isfinite(vectors).all()
                ):
                    raise ValueError("cache dimension or finite-value mismatch")
                self.vectors = vectors
            else:
                self.vectors = self.encode(self.texts)
        else:
            self.vectors = self.encode(self.texts)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"key": key, "vectors": self.vectors.tolist()}))
        self.index_seconds = time.perf_counter() - start
        self.index_key = key
        self.input_records = [
            {
                "skill_id": s["id"],
                "raw_body_chars": len(s.get("body") or ""),
                **token_record(
                    self.tokenizers["encoder"], t, self.profile.encoder_max_length
                ),
            }
            for s, t in zip(skills, self.texts)
        ]

    def rerank(self, prompt, candidates):
        import torch

        tok = self.tokenizers["reranker"]
        prefix, suffix = ref.get_reranker_template_tokens(tok)
        if self.profile.reranker_max_length <= len(prefix) + len(suffix):
            raise ValueError("reranker special-token budget exhausted")
        texts = [
            ref.format_rerank_prompt(
                s["name"],
                s.get("description") or "",
                s.get("body") or "",
                prompt,
                desc_max=self.profile.desc_max,
                body_max=self.profile.reranker_body_max,
            )
            for s in candidates
        ]
        batches = [
            ref.tokenize_reranker_text(
                t, tok, prefix, suffix, self.profile.reranker_max_length
            )
            for t in texts
        ]
        model = self._load("reranker")
        scores = []
        for i in range(0, len(batches), self.profile.batch_size):
            batch = batches[i : i + self.profile.batch_size]
            length = max(map(len, batch))
            ids = torch.tensor(
                [[tok.pad_token_id] * (length - len(b)) + b for b in batch],
                device=self.profile.device,
            )
            mask = torch.tensor(
                [[0] * (length - len(b)) + [1] * len(b) for b in batch],
                device=self.profile.device,
            )
            with torch.no_grad():
                logits = model(input_ids=ids, attention_mask=mask).logits[:, -1, :]
                values = (
                    (
                        logits[:, tok.convert_tokens_to_ids("yes")]
                        - logits[:, tok.convert_tokens_to_ids("no")]
                    )
                    .float()
                    .cpu()
                )
            if not torch.isfinite(values).all():
                raise ValueError("nonfinite reranker score")
            scores.extend(values.tolist())
        records = []
        for s, t, b in zip(candidates, texts, batches):
            r = token_record(
                tok, t, self.profile.reranker_max_length - len(prefix) - len(suffix)
            )
            r.update(
                skill_id=s["id"],
                raw_body_chars=len(s.get("body") or ""),
                input_ids=b,
                actual_tokens=len(b),
                template_tokens=len(prefix) + len(suffix),
            )
            records.append(r)
        return scores, records

    def recommend(self, prompt: str, top_k: int = 2):
        from hermes_skilleval.router_query import router_query_text

        prompt = router_query_text(prompt)
        self._check_assets()
        import torch

        if top_k < 0:
            raise ValueError("negative K")
        start = time.perf_counter()
        query = ref.format_query(prompt, self.profile.query_chars)
        vector = self.encode([query])
        sims = (vector @ self.vectors.T)[0]
        _, idx = torch.topk(sims, min(self.profile.retrieval_top_k, len(self.skills)))
        indices = idx.tolist()
        retrieval_seconds = time.perf_counter() - start
        candidates = [self.skills[i] for i in indices]
        start = time.perf_counter()
        scores, inputs = self.rerank(prompt, candidates)
        rerank_seconds = time.perf_counter() - start
        ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
        return {
            "actual_router": "skillrouter-open",
            "model_identity": self.identity,
            "index_key": self.index_key,
            "skill_ids": [s["id"] for s, _ in ranked[:top_k]],
            "candidate_budget": top_k,
            "fallback": False,
            "scores": {s["id"]: v for s, v in ranked},
            "retrieval": [
                {"id": self.skills[i]["id"], "score": float(sims[i])} for i in indices
            ],
            "reranked_ids": [s["id"] for s, _ in ranked],
            "reranker_inputs": inputs,
            "query_input": token_record(
                self.tokenizers["encoder"], query, self.profile.encoder_max_length
            ),
            "timing": {
                "index_seconds": self.index_seconds,
                "retrieval_seconds": retrieval_seconds,
                "rerank_seconds": rerank_seconds,
                "latest_load_seconds": dict(self.load_seconds),
            },
        }
