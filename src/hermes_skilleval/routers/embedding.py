from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.routers.base import SkillRouter


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class EmbeddingModel(Protocol):
    @property
    def cache_key(self) -> str: ...

    def encode_batch(self, texts: Iterable[str]) -> list[list[float]]:
        raise NotImplementedError


class HashingEmbeddingModel:
    """Small deterministic embedding model for offline routing experiments."""

    def __init__(self, dimensions: int = 512) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions
        self.cache_key = f"hashing:{dimensions}"

    def encode(self, text: str) -> dict[int, float]:
        vector: dict[int, float] = {}
        for feature in _features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] = vector.get(bucket, 0.0) + sign
        return _normalize(vector)

    def encode_batch(self, texts: Iterable[str]) -> list[list[float]]:
        return [_dense(self.encode(text), self.dimensions) for text in texts]


class EmbeddingDependencyError(RuntimeError):
    """Raised when an optional embedding backend dependency is unavailable."""


class SentenceTransformerEmbeddingModel:
    def __init__(
        self,
        model_name: str,
        *,
        revision: str | None = None,
        device: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except (ImportError, ModuleNotFoundError) as exc:
            raise EmbeddingDependencyError(
                "sentence-transformers backend requires optional dependency; "
                'install with: python -m pip install -e ".[embedding]"'
            ) from exc

        self.model_name = model_name
        options: dict[str, Any] = {}
        if revision is not None:
            options["revision"] = revision
        if device is not None:
            options["device"] = device
        if local_files_only:
            options["local_files_only"] = True
        self.model = SentenceTransformer(model_name, **options)
        self.max_seq_length = getattr(self.model, "max_seq_length", None)
        self.revision = revision
        self._loaded_identity = self._identity()
        self._loaded_metadata = self._metadata()

    @property
    def cache_key(self) -> str:
        if self._metadata() != self._loaded_metadata:
            raise ValueError("checkpoint changed after loading; reload the model")
        return f"sentence-transformers:{self.model_name}:{self._loaded_identity}:normalized-v1:maxlen={self.max_seq_length}"

    def _metadata(self) -> list[tuple[str, int, int]]:
        root = Path(self.model_name)
        return (
            [
                (str(p), p.stat().st_size, p.stat().st_mtime_ns)
                for p in sorted(root.rglob("*"))
                if p.is_file()
            ]
            if root.is_dir()
            else []
        )

    def _identity(self) -> str:
        # A path is not a model identity: replacing weights must invalidate the index.
        root = Path(self.model_name)
        digest = hashlib.sha256()
        if root.is_dir():
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                digest.update(path.relative_to(root).as_posix().encode())
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
            identity = digest.hexdigest()
        else:
            identity = self.revision or "unresolved-revision"
        return identity

    def encode_batch(self, texts: Iterable[str]) -> list[list[float]]:
        texts = list(texts)
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        vectors = [_to_float_list(vector) for vector in embeddings]
        if len(vectors) != len(texts):
            raise ValueError("embedding batch size mismatch")
        for vector in vectors:
            _validate_vector(vector)
        return vectors


class EmbeddingRouter(SkillRouter):
    name = "embedding"

    def __init__(
        self,
        model: EmbeddingModel | None = None,
        cache_path: Path | str | None = None,
    ) -> None:
        self.model = model or HashingEmbeddingModel()
        self.cache = EmbeddingCache(cache_path) if cache_path is not None else None

    def route(
        self, task: BenchmarkTask, skills: list[Skill], top_k: int
    ) -> RouteResult:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be positive")
        if not skills:
            raise ValueError("skill index is empty")

        started = time.perf_counter()
        queries = self.model.encode_batch([router_query_text(task.prompt)])
        if len(queries) != 1:
            raise ValueError("query embedding batch size mismatch")
        query = queries[0]
        skill_vectors = self._skill_vectors(skills)
        scores = {skill.id: _cosine(query, skill_vectors[skill.id]) for skill in skills}
        ranked = sorted(skills, key=lambda skill: (-scores[skill.id], skill.id))
        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=[skill.id for skill in ranked[:top_k]],
            scores=scores,
            latency_ms=latency_ms,
        )

    def _skill_vectors(self, skills: list[Skill]) -> dict[str, list[float]]:
        vectors: dict[str, list[float]] = {}
        missing: list[tuple[Skill, str]] = []
        model_key = self.model.cache_key
        for skill in skills:
            key = _skill_cache_key(model_key, skill)
            cached = self.cache.get(key) if self.cache else None
            if cached is None:
                missing.append((skill, key))
            else:
                vectors[skill.id] = cached

        if missing:
            encoded = self.model.encode_batch(
                _skill_text(skill) for skill, _ in missing
            )
            for (skill, key), vector in zip(missing, encoded, strict=True):
                vectors[skill.id] = vector
                if self.cache:
                    self.cache.set(key, vector)
            if self.cache:
                self.cache.save()

        return vectors


class EmbeddingCache:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.data = self._load()

    def get(self, key: str) -> list[float] | None:
        value = self.data.get(key)
        if not isinstance(value, list):
            return None
        return [float(item) for item in value]

    def set(self, key: str, vector: list[float]) -> None:
        self.data[key] = [float(item) for item in vector]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, sort_keys=True), encoding="utf-8")

    def _load(self) -> dict[str, list[float]]:
        if not self.path.exists():
            return {}
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"embedding cache must contain an object: {self.path}")
        return loaded


def _skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.id.replace("-", " "),
            skill.name,
            skill.category or "",
            skill.description,
            " ".join(skill.trigger_terms),
            skill.body,
        ]
    )


def _features(text: str) -> Iterable[str]:
    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    for token in tokens:
        if len(token) >= 3:
            yield f"tok:{token}"
    for left, right in zip(tokens, tokens[1:], strict=False):
        if len(left) >= 3 and len(right) >= 3:
            yield f"bi:{left}:{right}"


def _normalize(vector: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0.0:
        return {}
    return {index: value / norm for index, value in vector.items()}


def _dense(vector: dict[int, float], dimensions: int) -> list[float]:
    dense = [0.0] * dimensions
    for index, value in vector.items():
        dense[index] = value
    return dense


def _cosine(left: list[float], right: list[float]) -> float:
    _validate_vector(left)
    _validate_vector(right)
    if len(left) != len(right):
        raise ValueError("embedding dimensions mismatch")
    return sum(a * b for a, b in zip(left, right, strict=True))


def _validate_vector(vector: list[float]) -> None:
    if not vector or not all(math.isfinite(value) for value in vector):
        raise ValueError("embedding must be nonempty and finite")


def _to_float_list(vector) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(item) for item in vector]


def _skill_cache_key(model_key: str, skill: Skill) -> str:
    digest = hashlib.sha256(_skill_text(skill).encode("utf-8")).hexdigest()
    return f"{model_key}:skill-text-v1:{skill.id}:{digest}"
