"""Single-use pure-functional policies and real-forward delay controllers."""

from dataclasses import dataclass
import math
from pathlib import Path

from .functional_features import prior_predict
from .study import read
from .value import load_models

METHODS = ("N0-v2", "S1-v2", "P1-v2", "H-task-fixedC-v2", "H-myopic-v2", "H-full-v2")


@dataclass
class FunctionalController:
    method: str
    remaining_interventions: int = 1
    fixed_skill: str | None = None

    def decide(
        self,
        stage,
        candidates,
        gains=None,
        wait=None,
        has_future=True,
        dynamic_top=None,
    ):
        if self.method not in (*METHODS, "DEFER_SAME-v2", "WAIT_THEN_FULL-v2"):
            raise ValueError("unknown functional method")
        if self.remaining_interventions == 0 or self.method == "N0-v2":
            return {"action": "CONTINUE", "reason": "NATIVE_CONTINUATION"}
        chosen = None
        if self.method == "DEFER_SAME-v2":
            # execute(from_checkpoint=...) starts with a neutral continuation.
            # This callback only occurs at this branch's NEXT natural opportunity.
            if self.fixed_skill is None:
                return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
            chosen = self.fixed_skill
        elif self.method == "S1-v2":
            if not candidates:
                return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
            if stage == "E0":
                chosen = candidates[0]
        else:
            if (
                not candidates
                or gains is None
                or set(gains) != set(candidates)
                or any(not math.isfinite(v) for v in gains.values())
            ):
                return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
            if self.method in ("H-myopic-v2", "P1-v2") or not has_future:
                wait = 0.0
            if wait is None or not math.isfinite(wait):
                return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
            # Candidate order is the predeclared stable tie rule for every head.
            best = max(candidates, key=lambda k: gains[k])
            sensitive = bool(has_future and 0 < gains[best] <= max(0.0, wait))
            if gains[best] > max(0.0, wait):
                chosen = best
            else:
                return {
                    "action": "WAIT" if has_future else "NO_INTERVENTION",
                    "reason": "FUNCTIONAL_WAIT" if has_future else "FUNCTIONAL_NOOP",
                    "gains": gains,
                    "waiting_value": wait,
                    "wait_sensitive": sensitive,
                }
        if chosen is None:
            return {"action": "WAIT", "reason": "FIXED_SCHEDULE"}
        self.remaining_interventions -= 1
        return {
            "action": "INJECT",
            "skill_id": chosen,
            "reason": "FUNCTIONAL_POLICY_DECISION",
            "gains": gains,
            "waiting_value": wait,
            "wait_sensitive": False,
        }


class FunctionalPredictor:
    def __init__(self, models, method, encoder, retriever):
        self.method, self.encoder, self.retriever = method, encoder, retriever
        self.gain_calls = self.wait_calls = 0
        if method == "P1-v2":
            report = read(Path(models) / "training.json")
            self.prior = (
                report.get("methods", {}).get("full", {}).get("cheap_baselines")
                or report.get("cheap_baselines", {})
            )["skill_stage_prior"]
            self.use_wait = False
            return
        name = "task-only" if method == "H-task-fixedC-v2" else "full"
        self.gain, self.wait, self.metadata = load_models(Path(models) / name)
        if (
            self.metadata.get("research_target") != "FUNCTIONAL_REPAIR_GAIN"
            or self.metadata.get("cost_in_labels") is not False
            or self.metadata.get("policy_in_labels") is not False
        ):
            raise ValueError("METHOD_UNAVAILABLE: incompatible functional model")
        self.use_wait = method != "H-myopic-v2"

    def __call__(self, state, candidates):
        if self.method == "P1-v2":
            return {
                k: prior_predict(self.prior, k, state.stage) for k in candidates
            }, 0.0
        import torch

        x = self.encoder.features(state, no_state=self.metadata["no_state"])[None]
        self.gain_calls += 1
        with torch.no_grad():
            gains = {
                k: float(
                    self.gain(x, self.encoder.encode(self.retriever.skills[k])[None])[0]
                )
                for k in candidates
            }
            waiting = 0.0
            if self.use_wait and state.stage != "E2":
                self.wait_calls += 1
                waiting = float(self.wait(x)[0, 0])
        return gains, waiting
