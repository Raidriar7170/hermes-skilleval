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
