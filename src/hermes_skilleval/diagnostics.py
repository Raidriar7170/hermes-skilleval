from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = "diagnostic.v1"
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)

STOPWORDS = {
    "about",
    "against",
    "already",
    "and",
    "are",
    "can",
    "for",
    "from",
    "has",
    "into",
    "its",
    "local",
    "not",
    "only",
    "should",
    "that",
    "the",
    "then",
    "this",
    "use",
    "used",
    "when",
    "with",
}
GENERIC_TERMS = {
    "agent",
    "general",
    "help",
    "skill",
    "task",
    "tasks",
    "tool",
    "tools",
}
NEGATIVE_BOUNDARY_MARKERS = (
    ("do", "not", "use"),
    ("avoid",),
    ("not", "for"),
    ("unless",),
)


def scan_diagnostic_source(source: Path | str) -> dict[str, Any]:
    root = Path(source)
    if root.is_dir():
        skill_files = sorted(root.rglob("SKILL.md"))
        if skill_files:
            records = [_markdown_skill_record(path, root) for path in skill_files]
            return _scan_artifact(root, records)
        raise ValueError(f"unsupported skill source shape: {root} (directory without SKILL.md)")

    if root.is_file():
        if root.name.lower().endswith(".json"):
            try:
                payload = json.loads(root.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"unsupported skill source shape: {root} (invalid JSON)") from exc
            tools = _mcp_tools(payload)
            if tools is not None:
                return _scan_artifact(root, [_mcp_tool_record(tool, root) for tool in tools])
        raise ValueError(f"unsupported skill source shape: {root}")

    raise ValueError(f"unsupported skill source shape: {root}")


def write_scan_artifact(source: Path | str, output_path: Path | str) -> dict[str, Any]:
    artifact = scan_diagnostic_source(source)
    _write_json(output_path, artifact)
    return artifact


def lint_diagnostic_index(index_path: Path | str) -> dict[str, Any]:
    artifact = _read_json(index_path)
    skills = _skills_from_scan(artifact, index_path)
    findings: list[dict[str, Any]] = []
    for skill in skills:
        findings.extend(_lint_skill(skill))

    return {
        "artifact_type": "diagnostic_lint",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "index_path": str(index_path),
        "summary": {
            "skill_count": len(skills),
            "finding_count": len(findings),
            "findings_by_code": dict(sorted(Counter(f["code"] for f in findings).items())),
            "findings_by_severity": dict(
                sorted(Counter(f["severity"] for f in findings).items())
            ),
        },
        "findings": findings,
    }


def write_lint_artifact(index_path: Path | str, output_path: Path | str) -> dict[str, Any]:
    artifact = lint_diagnostic_index(index_path)
    _write_json(output_path, artifact)
    return artifact


def inspect_diagnostic_index(index_path: Path | str) -> dict[str, Any]:
    artifact = _read_json(index_path)
    skills = _skills_from_scan(artifact, index_path)
    clusters = _conflict_clusters(skills)
    return {
        "artifact_type": "diagnostic_inspect",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "index_path": str(index_path),
        "summary": {
            "skill_count": len(skills),
            "cluster_count": len(clusters),
        },
        "tone": "review-worthy risk signals only",
        "clusters": clusters,
    }


def write_inspect_artifact(index_path: Path | str, output_path: Path | str) -> dict[str, Any]:
    artifact = inspect_diagnostic_index(index_path)
    _write_json(output_path, artifact)
    return artifact


def route_diagnostic_query(
    query: str,
    index_path: Path | str,
    *,
    top_k: int = 5,
    inspect_path: Path | str | None = None,
) -> dict[str, Any]:
    if top_k <= 0:
        raise ValueError("--top-k must be positive")

    artifact = _read_json(index_path)
    skills = _skills_from_scan(artifact, index_path)
    if not skills:
        raise ValueError("diagnostic skill index is empty")

    clusters = _clusters_by_skill(inspect_path) if inspect_path else {}
    scored = [_route_candidate(query, skill, clusters.get(skill["id"], [])) for skill in skills]
    scored.sort(key=lambda item: (-item["score"], item["skill_id"]))
    candidates = scored[:top_k]
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank
    return {
        "artifact_type": "diagnostic_route",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "index_path": str(index_path),
        "inspect_path": str(inspect_path) if inspect_path else None,
        "query": query,
        "top_k": top_k,
        "summary": {
            "candidate_count": len(candidates),
            "risk_flag_count": sum(len(candidate["risk_flags"]) for candidate in candidates),
        },
        "candidates": candidates,
    }


def write_route_artifact(
    query: str,
    index_path: Path | str,
    output_path: Path | str,
    *,
    top_k: int = 5,
    inspect_path: Path | str | None = None,
) -> dict[str, Any]:
    artifact = route_diagnostic_query(
        query,
        index_path,
        top_k=top_k,
        inspect_path=inspect_path,
    )
    _write_json(output_path, artifact)
    return artifact


def _scan_artifact(source: Path, skills: list[dict[str, Any]]) -> dict[str, Any]:
    source_types = Counter(skill["source"]["type"] for skill in skills)
    warning_count = sum(len(skill["parser_warnings"]) for skill in skills)
    return {
        "artifact_type": "diagnostic_scan",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "source": {
            "path": str(source),
            "kind": "directory" if source.is_dir() else "file",
        },
        "summary": {
            "skill_count": len(skills),
            "source_types": dict(sorted(source_types.items())),
            "warning_count": warning_count,
        },
        "skills": skills,
    }


def _markdown_skill_record(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    metadata, body, warnings = _split_skill_frontmatter(text, path)
    skill_id = path.parent.name
    name = _metadata_text(metadata.get("name")) or _fallback_name(body, skill_id)
    description = _metadata_text(metadata.get("description"))
    category = _category_for(path, root)
    cues = _routing_cues(
        skill_id=skill_id,
        name=name,
        category=category,
        description=description,
        body=body,
        input_schema_terms=[],
    )
    return {
        "id": skill_id,
        "name": name,
        "category": category,
        "description": description,
        "body": body.strip(),
        "trigger_terms": cues["trigger_terms"],
        "token_count_estimate": len(WORD_RE.findall(text)),
        "source": {
            "type": "markdown_skill",
            "source_path": str(root),
            "file_path": str(path),
            "relative_path": _relative_path(path, root),
        },
        "routing_cues": cues,
        "parser_warnings": warnings,
    }


def _split_skill_frontmatter(
    text: str,
    path: Path,
) -> tuple[dict[str, Any], str, list[str]]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, ["missing frontmatter; used fallback metadata"]
    raw_meta, body = match.groups()
    try:
        metadata = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed skill frontmatter: {path}: {exc}") from exc
    if not isinstance(metadata, dict):
        return {}, body, ["frontmatter is not an object; used fallback metadata"]
    return metadata, body, []


def _mcp_tools(payload: Any) -> list[dict[str, Any]] | None:
    if not isinstance(payload, dict):
        return None
    tools = payload.get("tools")
    if isinstance(tools, list):
        return [tool for tool in tools if isinstance(tool, dict)]
    server = payload.get("server")
    if isinstance(server, dict) and isinstance(server.get("tools"), list):
        return [tool for tool in server["tools"] if isinstance(tool, dict)]
    return None


def _mcp_tool_record(tool: dict[str, Any], source: Path) -> dict[str, Any]:
    raw_name = _metadata_text(tool.get("name")) or "unnamed_tool"
    description = _metadata_text(tool.get("description"))
    warnings = []
    if not description:
        warnings.append("missing description")
    input_schema = tool.get("inputSchema", tool.get("input_schema"))
    input_terms, input_summary, schema_warnings = _input_schema_terms(input_schema)
    warnings.extend(schema_warnings)
    cues = _routing_cues(
        skill_id=raw_name,
        name=raw_name.replace("_", " ").replace("-", " "),
        category="mcp-tool",
        description=description,
        body=input_summary,
        input_schema_terms=input_terms,
    )
    return {
        "id": raw_name,
        "name": raw_name,
        "category": "mcp-tool",
        "description": description,
        "body": input_summary,
        "trigger_terms": cues["trigger_terms"],
        "token_count_estimate": len(WORD_RE.findall(f"{raw_name} {description} {input_summary}")),
        "source": {
            "type": "mcp_tool_schema",
            "source_path": str(source),
            "file_path": str(source),
            "relative_path": source.name,
        },
        "routing_cues": cues,
        "parser_warnings": warnings,
    }


def _input_schema_terms(input_schema: Any) -> tuple[list[str], str, list[str]]:
    if input_schema is None:
        return [], "", ["missing inputSchema"]
    if not isinstance(input_schema, dict):
        return [], "", ["inputSchema is not an object"]
    properties = input_schema.get("properties", {})
    if not isinstance(properties, dict):
        return [], "", ["inputSchema.properties is not an object"]
    terms = []
    summary_parts = []
    for name, spec in sorted(properties.items()):
        if not isinstance(spec, dict):
            terms.append(str(name))
            summary_parts.append(str(name))
            continue
        field_type = _metadata_text(spec.get("type")) or "unknown"
        descriptor = f"{name}:{field_type}"
        terms.append(descriptor)
        description = _metadata_text(spec.get("description"))
        summary_parts.append(
            f"{descriptor} {description}".strip()
        )
    return terms, "; ".join(summary_parts), []


def _routing_cues(
    *,
    skill_id: str,
    name: str,
    category: str | None,
    description: str,
    body: str,
    input_schema_terms: list[str],
) -> dict[str, list[str]]:
    negative = _negative_boundary_terms(f"{description}\n{body}")
    return {
        "name_terms": _terms(name),
        "description_terms": _terms(description),
        "category_terms": _terms(category or ""),
        "trigger_terms": _terms(f"{skill_id} {name} {description}"),
        "boundary_terms": _boundary_terms(f"{description}\n{body}"),
        "negative_boundary_terms": negative,
        "input_schema_terms": input_schema_terms,
    }


def _lint_skill(skill: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    description = skill.get("description", "").strip()
    distinctive = _distinctive_terms(
        " ".join(
            [
                skill.get("id", ""),
                skill.get("name", ""),
                description,
                " ".join(skill.get("routing_cues", {}).get("trigger_terms", [])),
            ]
        )
    )
    all_terms = set(_terms(f"{description} {skill.get('body', '')}"))
    if not description:
        findings.append(
            _finding(
                skill,
                "missing_description",
                "warning",
                "Description is missing, so routing evidence depends on weaker fallback cues.",
                [],
            )
        )
    if len(distinctive) < 3:
        findings.append(
            _finding(
                skill,
                "weak_activation_cues",
                "warning",
                "Activation cues look too thin for reliable routing.",
                distinctive,
            )
        )
    if not skill.get("routing_cues", {}).get("negative_boundary_terms"):
        findings.append(
            _finding(
                skill,
                "missing_negative_boundaries",
                "warning",
                "Skill does not state clear do-not-use or avoid boundaries.",
                [],
            )
        )
    generic_hits = sorted((all_terms & GENERIC_TERMS) - {"agent", "skill", "tool", "tools"})
    if generic_hits and len(distinctive) < 3:
        findings.append(
            _finding(
                skill,
                "generic_terms",
                "warning",
                "Routing cues rely on broad terms that can attract unrelated tasks.",
                generic_hits,
            )
        )
    return findings


def _finding(
    skill: dict[str, Any],
    code: str,
    severity: str,
    message: str,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "skill_id": skill["id"],
        "skill_name": skill["name"],
        "severity": severity,
        "code": code,
        "message": message,
        "evidence": evidence,
        "source_path": skill.get("source", {}).get("file_path"),
    }


def _conflict_clusters(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coappearances = _route_coappearances(skills)
    clusters = []
    cluster_index = 1
    for left_index, left in enumerate(skills):
        for right in skills[left_index + 1 :]:
            signals = _conflict_signals(left, right, coappearances)
            if len(signals) < 3:
                continue
            evidence_terms = sorted(
                {
                    term
                    for signal in signals
                    for term in signal.get("evidence_terms", [])
                }
            )
            clusters.append(
                {
                    "cluster_id": f"risk-cluster-{cluster_index:03d}",
                    "risk_level": "review",
                    "summary": (
                        "Review-worthy routing risk: shared cues may make these "
                        "skills hard to route apart without clearer boundaries."
                    ),
                    "involved_skills": [left["id"], right["id"]],
                    "signals": signals,
                    "evidence_terms": evidence_terms,
                }
            )
            cluster_index += 1
    return clusters


def _conflict_signals(
    left: dict[str, Any],
    right: dict[str, Any],
    coappearances: Counter[tuple[str, str]],
) -> list[dict[str, Any]]:
    signals = []
    overlap = sorted(_skill_terms(left) & _skill_terms(right))
    trigger_overlap = sorted(
        _distinctive_set(left.get("routing_cues", {}).get("trigger_terms", []))
        & _distinctive_set(right.get("routing_cues", {}).get("trigger_terms", []))
    )
    same_category = left.get("category") and left.get("category") == right.get("category")
    if len(overlap) >= 2 or (same_category and overlap):
        signals.append(
            {
                "type": "token_overlap",
                "detail": "Skills share routing terms that may attract similar queries.",
                "evidence_terms": overlap[:8],
            }
        )
    if trigger_overlap:
        signals.append(
            {
                "type": "trigger_term_overlap",
                "detail": "Extracted trigger terms overlap.",
                "evidence_terms": trigger_overlap[:8],
            }
        )
    if same_category:
        signals.append(
            {
                "type": "category_proximity",
                "detail": "Skills sit in the same category.",
                "evidence_terms": [left["category"]],
            }
        )
    if (
        not left.get("routing_cues", {}).get("negative_boundary_terms")
        or not right.get("routing_cues", {}).get("negative_boundary_terms")
    ):
        signals.append(
            {
                "type": "missing_boundaries",
                "detail": "At least one skill lacks explicit negative boundaries.",
                "evidence_terms": [],
            }
        )
    pair = _pair_key(left["id"], right["id"])
    if coappearances[pair] > 0:
        signals.append(
            {
                "type": "route_coappearance",
                "detail": "Skills co-appear in local diagnostic route probes.",
                "evidence_terms": overlap[:5],
            }
        )
    return signals


def _route_coappearances(skills: list[dict[str, Any]]) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for skill in skills:
        query = f"{skill['name']} {skill.get('description', '')}"
        ranked = sorted(
            skills,
            key=lambda item: (-_route_score(query, item)[0], item["id"]),
        )[:3]
        ids = [item["id"] for item in ranked if _route_score(query, item)[0] > 0]
        for left_index, left in enumerate(ids):
            for right in ids[left_index + 1 :]:
                counts[_pair_key(left, right)] += 1
    return counts


def _route_candidate(
    query: str,
    skill: dict[str, Any],
    clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    score, matched_terms, source_fields = _route_score(query, skill)
    risk_flags = []
    for cluster in clusters:
        risk_flags.append(
            {
                "code": "conflict_cluster",
                "message": "Candidate appears in a review-worthy conflict risk cluster.",
                "cluster_id": cluster["cluster_id"],
            }
        )
    if not skill.get("routing_cues", {}).get("negative_boundary_terms"):
        risk_flags.append(
            {
                "code": "weak_boundary",
                "message": "Candidate lacks explicit do-not-use or avoid boundaries.",
            }
        )
    return {
        "rank": 0,
        "skill_id": skill["id"],
        "skill_name": skill["name"],
        "score": round(score, 6),
        "evidence": {
            "matched_terms": matched_terms,
            "source_fields": source_fields,
            "category": skill.get("category"),
        },
        "risk_flags": risk_flags,
    }


def _route_score(query: str, skill: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    query_terms = _route_term_set(query)
    if not query_terms:
        return 0.0, [], []
    fields = {
        "id": skill.get("id", ""),
        "name": skill.get("name", ""),
        "category": skill.get("category", "") or "",
        "description": skill.get("description", ""),
        "body": skill.get("body", ""),
        "trigger_terms": " ".join(skill.get("routing_cues", {}).get("trigger_terms", [])),
        "input_schema": " ".join(skill.get("routing_cues", {}).get("input_schema_terms", [])),
    }
    matched_by_field = {
        field: sorted(query_terms & _route_term_set(value))
        for field, value in fields.items()
        if query_terms & _route_term_set(value)
    }
    matched_terms = sorted({term for terms in matched_by_field.values() for term in terms})
    skill_terms = Counter(
        term for value in fields.values() for term in _route_term_set(value)
    )
    score = sum(1.0 + math.log1p(skill_terms[term]) for term in matched_terms)
    if skill.get("category") and _normalize_term(skill["category"]) in query_terms:
        score += 0.5
    return score, matched_terms, sorted(matched_by_field)


def _clusters_by_skill(inspect_path: Path | str) -> dict[str, list[dict[str, Any]]]:
    artifact = _read_json(inspect_path)
    clusters: dict[str, list[dict[str, Any]]] = {}
    for cluster in artifact.get("clusters", []):
        for skill_id in cluster.get("involved_skills", []):
            clusters.setdefault(skill_id, []).append(cluster)
    return clusters


def _skills_from_scan(artifact: dict[str, Any], path: Path | str) -> list[dict[str, Any]]:
    if artifact.get("artifact_type") != "diagnostic_scan":
        raise ValueError(f"diagnostic index must be a diagnostic_scan artifact: {path}")
    skills = artifact.get("skills")
    if not isinstance(skills, list):
        raise ValueError(f"diagnostic index skills must be a list: {path}")
    return [skill for skill in skills if isinstance(skill, dict)]


def _skill_terms(skill: dict[str, Any]) -> set[str]:
    return set(
        _distinctive_terms(
            " ".join(
                [
                    skill.get("id", ""),
                    skill.get("name", ""),
                    skill.get("category", "") or "",
                    skill.get("description", ""),
                    " ".join(skill.get("routing_cues", {}).get("trigger_terms", [])),
                    " ".join(skill.get("routing_cues", {}).get("input_schema_terms", [])),
                ]
            )
        )
    )


def _distinctive_terms(text: str) -> list[str]:
    return sorted(term for term in set(_terms(text)) if term not in STOPWORDS | GENERIC_TERMS)


def _distinctive_set(terms: list[str]) -> set[str]:
    return {term for term in terms if term not in STOPWORDS | GENERIC_TERMS}


def _route_term_set(text: str) -> set[str]:
    return {term for term in _terms(text) if term not in STOPWORDS}


def _terms(text: str) -> list[str]:
    terms = []
    seen = set()
    for raw in WORD_RE.findall(text.lower().replace("_", " ")):
        term = _normalize_term(raw)
        if len(term) < 3 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _normalize_term(value: str) -> str:
    term = value.lower().strip("-_")
    for suffix in ("ing", "ers", "ies", "es", "s"):
        if len(term) > len(suffix) + 3 and term.endswith(suffix):
            if suffix == "ies":
                return term[: -len(suffix)] + "y"
            return term[: -len(suffix)]
    return term


def _boundary_terms(text: str) -> list[str]:
    lowered_terms = _terms(text)
    markers = []
    if "use" in lowered_terms or "when" in lowered_terms:
        markers.append("use-when")
    markers.extend(_negative_boundary_terms(text))
    return sorted(dict.fromkeys(markers))


def _negative_boundary_terms(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    if re.search(r"\bavoid\b", lowered):
        found.append("avoid")
    if re.search(r"\bdo\s+not\s+use\b", lowered):
        found.append("do not use")
    if re.search(r"\bnot\s+for\b", lowered):
        found.append("not for")
    if re.search(r"\bunless\b", lowered):
        found.append("unless")
    return found


def _fallback_name(body: str, skill_id: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return skill_id.replace("-", " ").title()


def _metadata_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _category_for(path: Path, root: Path) -> str | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) >= 3 else None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _read_json(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"diagnostic artifact must be an object: {path}")
    return payload


def _write_json(path: Path | str, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
