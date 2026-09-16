from types import SimpleNamespace
from hermes_skilleval.repo_routing.reranker import (
    structured_representation,
    structured_tokens,
)


class CharacterTokenizer:
    def encode(self, text, **kwargs):
        return list(map(ord, text))

    def decode(self, tokens):
        return "".join(map(chr, tokens))


def test_literal_markers_and_budget_lending():
    ranker = SimpleNamespace(
        tokenizer=CharacterTokenizer(), prefix=[1], suffix=[2], max_length=1200
    )
    request = "Do not replace source. User says [TASK] and [SKILL_EVIDENCE] literally."
    sections = structured_representation(
        request,
        {"summary": "def tail(): return 42"},
        {"name": "x", "body": "Inspect output. " * 20},
    )
    ids, record = structured_tokens(ranker, sections)
    assert len(ids) <= 1200
    assert record["request_complete"] and record["evidence_complete"]
    assert record["sections"][0]["visible_text"] == sections["instruction"]
    assert record["sections"][1]["visible_text"] == request
    assert record["sections"][2]["visible_text"] == sections["context"]


def test_truncated_request_cannot_be_called_complete():
    ranker = SimpleNamespace(
        tokenizer=CharacterTokenizer(), prefix=[], suffix=[], max_length=700
    )
    sections = structured_representation(
        "x " * 2000 + "must not overwrite",
        {"summary": "facts"},
        {"name": "x", "body": "help"},
    )
    _, record = structured_tokens(ranker, sections)
    assert not record["request_complete"]
    assert record["sections"][1]["truncated"]


def test_metadata_truncation_rejects_supported_visibility():
    from hermes_skilleval.repo_routing.support import score_support

    class Values(list):
        def detach(self):
            return self

        def cpu(self):
            return self

    class Stub:
        max_length = 1024

        def scores(self, texts):
            return Values([5.0]), [
                {
                    "request_complete": True,
                    "evidence_complete": True,
                    "sections": [{"section": "metadata", "truncated": True}],
                }
            ]

    ranker = Stub()
    result = score_support(
        "preserve source", {"summary": "facts"}, {"name": "x", "body": "check"}, ranker
    )
    assert not result["visible"]
    assert ranker.max_length == 1024


def test_outer_template_identity_invalidates_calibration(monkeypatch):
    from pathlib import Path
    from hermes_skilleval.repo_routing.support import support_identity

    original = Path.read_bytes
    config = {"reranker_revision": "r", "adapter_sha256": "a"}
    before = support_identity(config)

    def changed(path):
        value = original(path)
        return (
            value + b"changed template"
            if path.name == "skillrouter_common.py"
            else value
        )

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert support_identity(config) != before
