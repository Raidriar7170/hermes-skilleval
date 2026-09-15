"""Public-text evidence heuristics, independent of task IDs and evaluator labels.

A lexical match is evidence of a mention, not a sufficiency or success claim.
Only the same document prefix as the shared reranker is inspected by default.
"""

from __future__ import annotations
import re

REVISION = "public-clause-lexical-v1"
STOP = set(
    "a an the this that these those it its is are be been being to of for from by with as at on in into and or but then also use using used please must should can could will would may need needs want output input file files task data each all any other only same given provide provided create make return write read implement ensure include including following".split()
)
ACTIONS = re.compile(
    r"\b(convert\w*|validat\w*|pars\w*|extract\w*|aggregat\w*|join\w*|merg\w*|deduplicat\w*|sort\w*|filter\w*|normaliz\w*|normalis\w*|calculat\w*|comput\w*|analy[sz]\w*|test\w*|debug\w*|fix\w*|render\w*|export\w*|import\w*|compar\w*|detect\w*|generat\w*|build\w*|schedul\w*|optim\w*|transform\w*|check\w*|summari[sz]\w*|clean\w*|load\w*|save\w*|report\w*)\b",
    re.I,
)


def terms(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9+#.-]*", text.lower())
    result = set()
    for word in words:
        word = word.strip(".-")
        if len(word) < 3 or word in STOP:
            continue
        for ending in ("ation", "ing", "ed", "es", "s"):
            if word.endswith(ending) and len(word) > len(ending) + 3:
                word = word[: -len(ending)]
                break
        result.add(word)
    return result


def requirements(prompt: str) -> list[dict]:
    if not isinstance(prompt, str):
        raise TypeError("public prompt must be a string, not task metadata")
    found = []
    # Source offsets preserve exact provenance. No task-specific vocabulary.
    for match in re.finditer(r"[^\n;.!?]+(?:[;.!?\n]|$)", prompt):
        span = match.group().strip()
        if not ACTIONS.search(span) or len(terms(span)) < 2:
            continue
        found.append(
            {
                "text": span,
                "start": match.start(),
                "end": match.end(),
                "origin": "EXPLICIT_PUBLIC_SPAN",
                "terms": sorted(terms(span)),
            }
        )
    return found[:24]


def features(
    prompt: str,
    skills: list[dict],
    *,
    body_max: int = 2000,
    desc_max: int = 500,
    enabled: bool = True,
) -> dict:
    reqs = requirements(prompt) if enabled else []
    supports = {}
    for skill in skills:
        fields = [
            ("description", (skill.get("description") or "")[:desc_max]),
            ("body", (skill.get("body") or "")[:body_max]),
        ]
        evidence = []
        for req in reqs:
            best = None
            for field, text in fields:
                for match in re.finditer(r"[^\n.!?]+(?:[.!?]|$)", text):
                    snippet = match.group().strip()
                    overlap = set(req["terms"]) & terms(snippet)
                    # Two meaningful shared terms plus operation language on both sides.
                    if len(overlap) < 2 or not ACTIONS.search(snippet):
                        continue
                    # Negated support is unknown; do not infer a hard conflict.
                    if re.search(
                        r"\b(not|never|cannot|unsupported|without)\b", snippet, re.I
                    ):
                        continue
                    score = len(overlap) / len(req["terms"])
                    row = {
                        "support": score,
                        "status": "SUPPORTED_MENTION",
                        "field": field,
                        "start": match.start(),
                        "end": match.end(),
                        "snippet": snippet,
                        "matched_terms": sorted(overlap),
                    }
                    if best is None or score > best["support"]:
                        best = row
            evidence.append(best or {"support": 0.0, "status": "UNKNOWN"})
        supports[skill["id"]] = evidence
    return {
        "revision": REVISION,
        "requirements": reqs,
        "supports": supports,
        "input_scope": {"body_max": body_max, "desc_max": desc_max},
        "extra_model_usage": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
        "semantic_sufficiency": "NOT_ESTABLISHED",
    }


def relation(
    left: dict, right: dict, left_evidence: list, right_evidence: list
) -> dict:
    """Never classify versions as substitutes solely from their name or similarity."""
    same_resources = left.get("resource_sha256") is not None and left.get(
        "resource_sha256"
    ) == right.get("resource_sha256")
    same_text = left.get("body") == right.get("body") and left.get(
        "description"
    ) == right.get("description")
    if same_text and same_resources:
        return {
            "kind": "OPERATION_SUBSTITUTE",
            "reason": "Identical full body, description and non-SKILL resources",
            "sources": [left.get("path"), right.get("path")],
        }
    common = [
        i
        for i, (a, b) in enumerate(zip(left_evidence, right_evidence))
        if a["support"] > 0 and b["support"] > 0
    ]
    return {
        "kind": "PARTIAL_OVERLAP" if common else "UNKNOWN",
        "requirements": common,
        "reason": "Shared supported public spans; does not establish interchangeability"
        if common
        else "Insufficient evidence",
    }
