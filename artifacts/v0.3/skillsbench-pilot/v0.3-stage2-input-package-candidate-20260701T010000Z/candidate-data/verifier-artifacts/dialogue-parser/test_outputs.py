from __future__ import annotations

import glob
import json
import os
import re
import traceback
from collections import deque
from pathlib import Path
from typing import Any, Callable

LOG_DIR = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))


class VerifierFailure(AssertionError):
    pass


def find_file(name: str, candidates: list[str], patterns: list[str]) -> Path:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return Path(matches[0])
    raise VerifierFailure(f"{name} not found in expected locations")


def load_dialogue() -> dict[str, Any]:
    path = find_file("dialogue.json", ["/app/dialogue.json", "dialogue.json", "/root/dialogue.json"], ["/app/**/dialogue.json", "/root/**/dialogue.json", "./**/dialogue.json"])
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise VerifierFailure("dialogue.json must contain an object")
    return data


def load_dot() -> str:
    path = find_file("dialogue.dot", ["/app/dialogue.dot", "dialogue.dot", "/root/dialogue.dot"], ["/app/**/dialogue.dot", "/root/**/dialogue.dot", "./**/dialogue.dot"])
    return path.read_text(encoding="utf-8")


def load_script() -> str:
    path = find_file("script.txt", ["/app/script.txt", "script.txt", "/root/script.txt"], ["/app/**/script.txt", "/root/**/script.txt", "./**/script.txt"])
    return path.read_text(encoding="utf-8")


def node_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in data["nodes"]}


def edge_map(data: dict[str, Any]) -> dict[str, list[str]]:
    edges: dict[str, list[str]] = {}
    for edge in data["edges"]:
        edges.setdefault(edge["from"], []).append(edge["to"])
    return edges


def assert_system_basics(data: dict[str, Any], dot: str) -> None:
    if "nodes" not in data or "edges" not in data:
        raise VerifierFailure("dialogue.json missing nodes or edges")
    if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
        raise VerifierFailure("nodes and edges must be lists")
    for node in data["nodes"]:
        if not isinstance(node.get("id"), str) or not isinstance(node.get("text"), str):
            raise VerifierFailure(f"Invalid node schema: {node}")
        if not isinstance(node.get("speaker"), str) or node.get("type") not in {"line", "choice"}:
            raise VerifierFailure(f"Invalid node speaker/type: {node}")
    for edge in data["edges"]:
        if not isinstance(edge.get("from"), str) or not isinstance(edge.get("to"), str) or not isinstance(edge.get("text"), str):
            raise VerifierFailure(f"Invalid edge schema: {edge}")
    if len(data["nodes"]) < 100 or len(data["edges"]) < 200:
        raise VerifierFailure(f"Expected 100+ nodes and 200+ edges, got {len(data['nodes'])}/{len(data['edges'])}")
    if "digraph" not in dot or "{" not in dot or "}" not in dot or "->" not in dot:
        raise VerifierFailure("dialogue.dot missing required DOT syntax")
    if "shape=diamond" not in dot and 'shape="diamond"' not in dot:
        raise VerifierFailure("Choice nodes should be visualized as diamonds")
    if "Start" not in dot:
        raise VerifierFailure("Visualization missing Start node")


def assert_narrative_content(nodes: dict[str, dict[str, Any]]) -> None:
    speakers = {n["speaker"] for n in nodes.values() if n.get("speaker")}
    for speaker in ["Narrator", "Barkeep", "Merchant", "Kira"]:
        if speaker not in speakers:
            raise VerifierFailure(f"Missing required speaker {speaker!r}")
    for node_id in ["Start", "TavernChoice", "StrangerApproach", "CrimsonQuestStart", "KiraMeet"]:
        if node_id not in nodes:
            raise VerifierFailure(f"Missing required node {node_id!r}")


def assert_graph_logic(data: dict[str, Any], nodes: dict[str, dict[str, Any]], edges_by_source: dict[str, list[str]]) -> None:
    for edge in data["edges"]:
        if edge["from"] not in nodes:
            raise VerifierFailure(f"Edge source {edge['from']!r} missing")
        if edge["to"] != "End" and edge["to"] not in nodes:
            raise VerifierFailure(f"Edge target {edge['to']!r} missing")
    reachable = set()
    queue: deque[str] = deque(["Start"])
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        for target in edges_by_source.get(current, []):
            if target != "End":
                queue.append(target)
    unreachable = set(nodes) - reachable
    if unreachable:
        raise VerifierFailure(f"Unreachable nodes found: {sorted(unreachable)[:3]}")
    if len([e for e in data["edges"] if e["from"] == "TavernChoice"]) < 4:
        raise VerifierFailure("TavernChoice needs 4+ options")
    if len([e for e in data["edges"] if e["to"] == "End"]) < 2:
        raise VerifierFailure("Expected 2+ endings")


def assert_content_integrity(nodes: dict[str, dict[str, Any]], data: dict[str, Any], script: str) -> None:
    for node_id, fragment in [
        ("StrangerMoreInfo", "Back so soon? Afraid?"),
        ("MerchantShame", "I light a candle for each of them"),
        ("KiraWarning", "She's never failed a contract"),
    ]:
        if node_id not in nodes or fragment not in nodes[node_id].get("text", ""):
            raise VerifierFailure(f"Node {node_id!r} missing expected text fragment")
    if not any(edge["from"] == "RecruitOptions" and "The stranger seems capable" in edge.get("text", "") for edge in data["edges"]):
        raise VerifierFailure("RecruitOptions edge with expected text missing")
    for node_id in ["HitNegotiate", "CrimsonCompromise"]:
        if node_id not in nodes:
            raise VerifierFailure(f"Specific node {node_id!r} from input script missing")
    matches = re.findall(r"^([A-Za-z]+):\s+([^\[\n]+?)\s+->\s+([A-Za-z]+)$", script, re.MULTILINE)
    for i, (speaker, text, _target) in enumerate(matches):
        if i % 10 != 0:
            continue
        if not any(n.get("speaker") == speaker and text.strip() in n.get("text", "") for n in nodes.values()):
            raise VerifierFailure(f"Sampled script line not found in graph: {speaker}: {text}")
    first_header = next((line for line in script.splitlines() if line.strip().startswith("[")), None)
    if not first_header:
        raise VerifierFailure("Script has no node headers")
    match = re.match(r"^\[(.*?)\]", first_header.strip())
    if not match or match.group(1) != "Start" or "Start" not in nodes:
        raise VerifierFailure("Script first node must be Start and output graph must include it")


def assert_structural_edges(nodes: dict[str, dict[str, Any]], edges_by_source: dict[str, list[str]]) -> None:
    for source, target in [
        ("Start", "TavernEntry"),
        ("TavernEntry", "TavernChoice"),
        ("TavernChoice", "StrangerApproach"),
        ("TavernChoice", "MerchantApproach"),
        ("StrangerGreet", "CrimsonQuestStart"),
        ("CrimsonQuestStart", "CrimsonWarning"),
    ]:
        if source not in nodes or target not in nodes:
            raise VerifierFailure(f"Structural edge endpoint missing: {source}->{target}")
        if target not in edges_by_source.get(source, []):
            raise VerifierFailure(f"Expected connection {source}->{target} missing")


def write_results(results: list[dict[str, Any]]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r["status"] == "passed")
    total = len(results)
    ctrf = {
        "results": {
            "tool": {"name": "stdlib-dialogue-parser-verifier"},
            "summary": {"tests": total, "passed": passed, "failed": total - passed},
            "tests": results,
        }
    }
    (LOG_DIR / "ctrf.json").write_text(json.dumps(ctrf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (LOG_DIR / "reward.txt").write_text("1\n" if passed == total else "0\n", encoding="utf-8")


def run_test(name: str, fn: Callable[[], None], results: list[dict[str, Any]]) -> None:
    try:
        fn()
    except Exception as exc:
        results.append({"name": name, "status": "failed", "message": str(exc), "trace": traceback.format_exc()})
    else:
        results.append({"name": name, "status": "passed"})


def main() -> None:
    data = load_dialogue()
    dot = load_dot()
    script = load_script()
    nodes = node_map(data)
    edges_by_source = edge_map(data)
    results: list[dict[str, Any]] = []
    run_test("system_basics", lambda: assert_system_basics(data, dot), results)
    run_test("narrative_content", lambda: assert_narrative_content(nodes), results)
    run_test("graph_logic", lambda: assert_graph_logic(data, nodes, edges_by_source), results)
    run_test("content_integrity", lambda: assert_content_integrity(nodes, data, script), results)
    run_test("structural_edges", lambda: assert_structural_edges(nodes, edges_by_source), results)
    write_results(results)


if __name__ == "__main__":
    main()
