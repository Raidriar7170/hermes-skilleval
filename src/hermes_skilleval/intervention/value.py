"""Frozen real text representation, paired utility regression and cross-fitted wait.

Heavy dependencies are imported only when this experimental path is selected.
Task identities group training folds; they are never input features.
"""

from __future__ import annotations

import json
from pathlib import Path


class Encoder:
    def __init__(self, path, max_length=256):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(path), local_files_only=True).eval()
        self.max_length = max_length
        self.cache = {}
        torch.set_num_threads(2)
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)

    def encode(self, text):
        if text not in self.cache:
            torch = self.torch
            tokens = self.tokenizer(
                text, return_tensors="pt", truncation=True, max_length=self.max_length
            )
            with torch.no_grad():
                states = self.model(**tokens).last_hidden_state
                mask = tokens["attention_mask"].unsqueeze(-1)
                vector = (states * mask).sum(1) / mask.sum(1).clamp(min=1)
                vector = torch.nn.functional.normalize(vector, dim=1)[0]
            self.cache[text] = vector
        return self.cache[text]

    def features(self, state, *, no_state=False):
        import torch

        request = self.encode(state.request + "\n" + state.repo_facts)
        # Encode errors and source separately so JSON bookkeeping cannot crowd them out.
        observation = (
            (
                self.encode(state.failure_text or "PUBLIC_TEST_MISSING")
                + self.encode(state.source_snippets or "SOURCE_MISSING")
                + self.encode(state.diff_summary or "DIFF_EMPTY")
            )
            / 3
            if not no_state
            else torch.zeros_like(request)
        )
        numeric = state.numeric()
        if no_state:
            numeric[4:] = [0.0] * (len(numeric) - 4)
        return torch.cat((request, observation, torch.tensor(numeric)))


class Retriever:
    def __init__(self, encoder, skills, full_bodies=None):
        self.encoder, self.skills = encoder, skills
        self.full_bodies = full_bodies or skills
        self.vectors = {k: encoder.encode(v) for k, v in self.full_bodies.items()}

    def rank(self, text):
        query = self.encoder.encode(text)
        return sorted(self.skills, key=lambda k: (-float(query @ self.vectors[k]), k))

    def dynamic_rank(self, state):
        # Encode each field independently: a long request cannot truncate away
        # the actual observed failure/source and collapse this into static retrieval.
        query = (
            self.encoder.encode(state.request)
            + self.encoder.encode(state.failure_text or "PUBLIC_TEST_MISSING")
            + self.encoder.encode(state.source_snippets or "SOURCE_MISSING")
        ) / 3
        return sorted(self.skills, key=lambda k: (-float(query @ self.vectors[k]), k))

    def dynamic_top(self, state):
        return self.dynamic_rank(state)[0]

    def candidates(self, state):
        static = self.rank(state.request + "\n" + state.repo_facts)[0]
        return [static] + [k for k in self.dynamic_rank(state) if k != static][:1]


def make_gain(state_dim, skill_dim, width=64):
    import torch

    class Gain(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.state = torch.nn.Sequential(
                torch.nn.Linear(state_dim, width), torch.nn.Tanh()
            )
            self.skill = torch.nn.Sequential(
                torch.nn.Linear(skill_dim, width), torch.nn.Tanh()
            )
            self.head = torch.nn.Sequential(
                torch.nn.Linear(width * 4, width),
                torch.nn.Tanh(),
                torch.nn.Linear(width, 1),
            )

        def forward(self, state, skill):
            zs, zk = self.state(state), self.skill(skill)
            return self.head(torch.cat((zs, zk, zs * zk, zs - zk), dim=-1)).squeeze(-1)

    return Gain()


def make_wait(state_dim, width=64):
    import torch

    return torch.nn.Sequential(
        torch.nn.Linear(state_dim, width),
        torch.nn.Tanh(),
        torch.nn.Linear(width, width),
        torch.nn.Tanh(),
        torch.nn.Linear(width, 1),
    )


def weights(rows):
    """Each task gets equal mass; states and shared native tail are not independent."""
    from collections import Counter
    import torch

    tasks = {r["task_id"] for r in rows}
    states = {t: {r["state_id"] for r in rows if r["task_id"] == t} for t in tasks}
    count = Counter((r["task_id"], r["state_id"]) for r in rows)
    return torch.tensor(
        [
            1
            / (
                len(tasks)
                * len(states[r["task_id"]])
                * count[r["task_id"], r["state_id"]]
            )
            for r in rows
        ]
    )


def fit_gain(rows, *, epochs=160, lr=0.002, seed=7170):
    import torch

    torch.manual_seed(seed)
    x = torch.stack([r["x"] for r in rows])
    k = torch.stack([r["k"] for r in rows])
    y = torch.tensor([r["delta"] for r in rows], dtype=torch.float32)
    w = weights(rows)
    model = make_gain(x.shape[1], k.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.001)
    before = torch.cat([p.detach().flatten() for p in model.parameters()]).clone()
    pairs = [
        (i, j)
        for i, a in enumerate(rows)
        for j, b in enumerate(rows[:i])
        if a["state_id"] == b["state_id"]
        and a["task_id"] == b["task_id"]
        and abs(a["delta"] - b["delta"]) > 1e-8
    ]
    curve = []
    for epoch in range(epochs):
        optimizer.zero_grad()
        pred = model(x, k)
        regression = (
            torch.nn.functional.huber_loss(pred, y, delta=0.1, reduction="none") * w
        ).sum()
        ranking = pred.sum() * 0
        if pairs:
            terms = [
                torch.nn.functional.softplus(
                    -torch.sign(y[i] - y[j]) * (pred[i] - pred[j])
                )
                * (w[i] + w[j])
                / 2
                for i, j in pairs
            ]
            ranking = torch.stack(terms).sum()
        loss = regression + 0.01 * ranking
        loss.backward()
        optimizer.step()
        curve.append(
            {
                "epoch": epoch,
                "loss": float(loss.detach()),
                "regression": float(regression.detach()),
            }
        )
    after = torch.cat([p.detach().flatten() for p in model.parameters()])
    return model.eval(), {
        "curve": curve,
        "parameter_l2_change": float((after - before).norm()),
        "rows": len(rows),
        "tasks": len({r["task_id"] for r in rows}),
        "nonzero_ranking_pairs": len(pairs),
    }


def fit_wait(rows, *, epochs=160, seed=7170):
    import torch

    torch.manual_seed(seed)
    x = torch.stack([r["x"] for r in rows])
    y = torch.tensor([r["target"] for r in rows], dtype=torch.float32)
    w = weights(rows)
    model = make_wait(x.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.001)
    before = torch.cat([p.detach().flatten() for p in model.parameters()]).clone()
    curve = []
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss = (
            torch.nn.functional.mse_loss(model(x).squeeze(-1), y, reduction="none") * w
        ).sum()
        loss.backward()
        optimizer.step()
        curve.append(float(loss.detach()))
    after = torch.cat([p.detach().flatten() for p in model.parameters()])
    return model.eval(), {
        "loss": curve,
        "parameter_l2_change": float((after - before).norm()),
    }


def cross_fitted_wait_targets(rows, chains, *, epochs=160):
    """Nested leave-task-out backward fitting; target models never see target task.

    Each chain holds naturally observed states with x and candidate skill vectors.
    E0/E1 get a predicted value of the next actual state offline. Terminal wait is
    structurally zero. No maximum over realized future branch outcomes is used.
    """
    import torch

    tasks = sorted(chains)
    if len(tasks) < 3:
        raise ValueError("need >=3 independent training tasks for nested wait fitting")
    gain_cache = {}

    def gain_without(excluded):
        key = tuple(sorted(excluded))
        if key not in gain_cache:
            fit = [r for r in rows if r["task_id"] not in excluded]
            if not fit:
                raise ValueError("no cross-fit training tasks")
            gain_cache[key] = fit_gain(fit, epochs=epochs)[0]
        return gain_cache[key]

    def value(gain, wait, state):
        with torch.no_grad():
            gains = [
                float(gain(state["x"][None], k[None])[0]) for k in state["candidates"]
            ]
            waiting = (
                max(0.0, float(wait(state["x"][None])[0, 0]))
                if wait is not None
                else 0.0
            )
        return max([0.0, waiting, *gains])

    result = []
    provenance = []
    for held in tasks:
        outside = [t for t in tasks if t != held]
        # Fit the E1 wait model using other tasks, with gain predictions that also
        # exclude the task receiving its target. Entire held task stays excluded.
        intermediate = []
        for t in outside:
            chain = chains[t]
            gain = gain_without({held, t})
            for i, state in enumerate(chain):
                if state["stage"] != "E1":
                    continue
                if i + 1 < len(chain):
                    target = value(gain, None, chain[i + 1])
                elif state.get("terminal_confirmed", False):
                    target = 0.0
                else:
                    continue
                intermediate.append({**state, "task_id": t, "target": target})
        wait = fit_wait(intermediate, epochs=epochs)[0] if intermediate else None
        gain = gain_without({held})
        chain = chains[held]
        unknown = []
        for i, state in enumerate(chain):
            if i == len(chain) - 1:
                if not state.get("terminal_confirmed", state["stage"] == "E2"):
                    unknown.append(
                        {
                            "state_id": state["state_id"],
                            "reason": "UNCONFIRMED_NATIVE_TERMINATION",
                        }
                    )
                    continue
                target = 0.0
            elif (
                chain[i + 1]["stage"] == "E1"
                and wait is None
                and not (
                    i + 1 == len(chain) - 1
                    and chain[i + 1].get("terminal_confirmed", False)
                )
            ):
                unknown.append(
                    {
                        "state_id": state["state_id"],
                        "reason": "NO_OUT_OF_TASK_DOWNSTREAM_WAIT_TARGETS",
                    }
                )
                continue
            else:
                next_is_known_terminal = i + 1 == len(chain) - 1 and chain[i + 1].get(
                    "terminal_confirmed", False
                )
                target = value(
                    gain,
                    wait
                    if chain[i + 1]["stage"] == "E1" and not next_is_known_terminal
                    else None,
                    chain[i + 1],
                )
            result.append({**state, "task_id": held, "target": target})
        provenance.append(
            {
                "target_task": held,
                "unknown_wait_targets": unknown,
                "gain_training_tasks": sorted(
                    {r["task_id"] for r in rows if r["task_id"] != held}
                ),
                "wait_training_tasks": sorted({r["task_id"] for r in intermediate}),
            }
        )
    return result, provenance


def save_models(output, gain, wait, metadata):
    import torch

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    torch.save(
        {"gain": gain.state_dict(), "wait": wait.state_dict()}, output / "weights.pt"
    )
    (output / "model.json").write_text(json.dumps(metadata, indent=2) + "\n")


def load_models(output):
    import torch

    output = Path(output)
    meta = json.loads((output / "model.json").read_text())
    data = torch.load(output / "weights.pt", weights_only=True, map_location="cpu")
    gain = make_gain(meta["state_dim"], meta["skill_dim"])
    wait = make_wait(meta["state_dim"])
    gain.load_state_dict(data["gain"])
    wait.load_state_dict(data["wait"])
    return gain.eval(), wait.eval(), meta
