"""Local component timing diagnostic, separate from Agent utility comparisons."""

import argparse
import cProfile
import json
from pathlib import Path
import pstats
import time
import hashlib

from hermes_skilleval.repo_routing.policy import route, read_config

p = argparse.ArgumentParser(description=__doc__)
for name in ("repo", "request", "registry", "config", "output"):
    p.add_argument("--" + name, type=Path, required=True)
p.add_argument("--policy", choices=("auto", "repo-aware"), required=True)
a = p.parse_args()
config = read_config(a.config)
registry = json.loads(a.registry.read_text())
request = a.request.read_text()
started_at = time.time()
phases = []
for phase in ("cold_process", "warm_process_model_reloaded"):
    profiler = cProfile.Profile()
    profiler.enable()
    result = route(a.repo, request, {"network": "disabled"}, registry, a.policy, config)
    profiler.disable()
    stats = pstats.Stats(profiler)
    functions = []
    for (filename, line, name), (
        primitive,
        calls,
        own,
        cumulative,
        callers,
    ) in stats.stats.items():
        normalized = filename.replace("\\", "/")
        if "/hermes_skilleval/" not in normalized:
            continue
        source = normalized.split("/hermes_skilleval/", 1)[1]
        if source.startswith(
            ("repo_routing/", "routers/skillrouter_open", "vendor/skillrouter_common")
        ):
            functions.append(
                {
                    "source": source,
                    "line": line,
                    "function": name,
                    "calls": calls,
                    "own_seconds": own,
                    "inclusive_seconds": cumulative,
                }
            )
    phases.append(
        {
            "phase": phase,
            "action": result["action"],
            "decision_reason": result["decision"].get("fallback_reason"),
            "calls": result["calls"],
            "route_timing": result["timing"],
            "r_version": result["r_version"],
            "context_cache_hit": result["context"]["cost"]["cache_hit"],
            "functions": sorted(
                functions, key=lambda x: (x["source"], x["line"], x["function"])
            ),
        }
    )
with a.output.open("x") as stream:
    json.dump(
        {
            "started_at": started_at,
            "finished_at": time.time(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "evidence_scope": "ENGINEERING_COMPONENT_PROFILE_NOT_MAIN_COMPARISON",
            "profiler": "cProfile",
            "policy": a.policy,
            "limitations": "Inclusive function timings overlap and must not be summed. Profiling adds overhead. Warm process reloads models; no persistent model service or physical cold-disk claim. No Agent was run.",
            "phases": phases,
        },
        stream,
        indent=2,
    )
