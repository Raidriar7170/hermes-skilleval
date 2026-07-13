from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.routers.base import SkillRouter


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class EmbeddingModel(Protocol):
    cache_key: str

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
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except (ImportError, ModuleNotFoundError) as exc:
            raise EmbeddingDependencyError(
                "sentence-transformers backend requires optional dependency; "
                'install with: python -m pip install -e ".[embedding]"'
            ) from exc

        self.model_name = model_name
        self.cache_key = f"sentence-transformers:{model_name}"
        self.model = SentenceTransformer(model_name)

    def encode_batch(self, texts: Iterable[str]) -> list[list[float]]:
        embeddings = self.model.encode(list(texts), normalize_embeddings=True)
        return [_to_float_list(vector) for vector in embeddings]


class EmbeddingRouter(SkillRouter):
    name = "embedding"

    def __init__(
        self,
        model: EmbeddingModel | None = None,
        cache_path: Path | str | None = None,
    ) -> None:
        self.model = model or HashingEmbeddingModel()
        self.cache = EmbeddingCache(cache_path) if cache_path is not None else None

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be positive")
        if not skills:
            raise ValueError("skill index is empty")

        started = time.perf_counter()
        query = self.model.encode_batch([router_query_text(task.prompt)])[0]
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
        for skill in skills:
            key = _skill_cache_key(self.model.cache_key, skill)
            cached = self.cache.get(key) if self.cache else None
            if cached is None:
                missing.append((skill, key))
            else:
                vectors[skill.id] = cached

        if missing:
            encoded = self.model.encode_batch(_skill_text(skill) for skill, _ in missing)
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
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(length))


def _to_float_list(vector) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(item) for item in vector]


def _skill_cache_key(model_key: str, skill: Skill) -> str:
    digest = hashlib.sha256(_skill_text(skill).encode("utf-8")).hexdigest()
    return f"{model_key}:{skill.id}:{digest}"
