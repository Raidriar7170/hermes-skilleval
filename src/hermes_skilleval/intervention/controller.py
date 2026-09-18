"""Single-use stopping decision; missing models are never native model choices."""

from dataclasses import dataclass
import math

METHODS = ("N0", "S1", "R1", "H-myopic", "H-no-state", "H-full")


@dataclass
class Controller:
    method: str
    margin: float = 0.0
    remaining_interventions: int = 1

    def decide(
        self,
        stage,
        candidates,
        gains=None,
        wait=None,
        has_future=True,
        dynamic_top=None,
    ):
        if self.method not in METHODS:
            raise ValueError("unknown method")
        if self.remaining_interventions == 0 or self.method == "N0":
            return {"action": "CONTINUE", "reason": "NATIVE_CONTINUATION"}
        if not candidates:
            return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
        chosen = None
        if self.method == "S1" and stage == "E0":
            chosen = candidates[0]
        elif self.method == "R1" and stage in ("E1", "E2"):
            chosen = dynamic_top if dynamic_top in candidates else candidates[0]
        elif self.method.startswith("H-"):
            if (
                gains is None
                or set(gains) != set(candidates)
                or any(not math.isfinite(v) for v in gains.values())
            ):
                return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
            if self.method == "H-myopic" or not has_future:
                wait = 0.0
            if wait is None or not math.isfinite(wait):
                return {"action": "UNAVAILABLE", "reason": "METHOD_UNAVAILABLE"}
            best = min(candidates, key=lambda k: (-gains[k], k))
            if gains[best] > max(0.0, wait) + self.margin:
                chosen = best
            else:
                return {
                    "action": "WAIT" if has_future else "NO_INTERVENTION",
                    "reason": "WAIT_MODEL_DECISION"
                    if has_future
                    else "NOOP_MODEL_DECISION",
                    "gains": gains,
                    "waiting_value": wait,
                }
        if chosen is None:
            return {"action": "WAIT", "reason": "FIXED_SCHEDULE"}
        self.remaining_interventions -= 1
        return {
            "action": "INJECT",
            "skill_id": chosen,
            "reason": "POLICY_DECISION",
            "gains": gains,
            "waiting_value": wait,
        }
