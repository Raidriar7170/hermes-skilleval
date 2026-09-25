"""Bounded, presampling public-contract check repairs in fresh private copies."""

import json
from pathlib import Path
import shutil
import sys

from hermes_skilleval.intervention.session import inventory
from hermes_skilleval.intervention.relation_store import atomic_json

assets, output = map(Path, sys.argv[1:])
roster = json.loads((output / "task_roster.json").read_text())
for entry in roster["finite_queue"][1:6]:
    tid = entry["instance_id"]
    task = output / "tasks" / tid
    original = assets / "hermes-repair-knowledge-private/tasks" / tid
    if not task.exists():
        shutil.copytree(original, task, symlinks=True)
    overlay = output / "overlays" / tid
    if (overlay / "contract-amendment.json").exists():
        continue
    candidates = [
        assets / p / tid
        for p in (
            "hermes-evidence-linked-private/test-overlays",
            "hermes-repair-knowledge-private/test-overlays-v2",
        )
    ]
    source = next(p for p in candidates if (p / "manifest.json").exists())
    (overlay / "files").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "files", overlay / "files")
    manifest = json.loads((source / "manifest.json").read_text())
    selectors = json.loads((task / "evaluation/selectors.json").read_text())
    mechanism = entry["mechanism"]
    changes = []
    if mechanism == "python-identifier-validation":
        filename = "test/units/utils/test_isidentifier.py"
        extra = """\n@pytest.mark.parametrize("value, expected", [(None, False), (123, False), ([], False), (b"alpha", False), ("_foo", True), ("__bar__", True), ("open", True), ("print", True)])
def test_public_identifier_contract_python3(value, expected):
    assert isidentifier(value) is expected
"""
        selectors["target"].append(
            filename + "::test_public_identifier_contract_python3"
        )
        changes.append(
            "Public non-string rejection and strict Python 3 boolean/name contract"
        )
    elif mechanism == "filter-attribute-forwarding":
        filename = "test/units/plugins/filter/test_mathstuff.py"
        extra = """\n@pytest.mark.parametrize("filter_name, expected", [("min", 1), ("max", 3)])
def test_public_filter_fallback_without_enhanced_jinja(monkeypatch, filter_name, expected):
    import importlib.util
    import jinja2.filters
    monkeypatch.delattr(jinja2.filters, "do_min", raising=False)
    monkeypatch.delattr(jinja2.filters, "do_max", raising=False)
    spec = importlib.util.spec_from_file_location("_trusted_mathstuff_without_enhanced_filters", ms.__file__)
    fallback_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fallback_module)
    operation = getattr(fallback_module, filter_name)
    assert operation(env, [3, 1, 2]) == expected
    with pytest.raises(AnsibleFilterError) as caught:
        operation(env, [{"key": 1}], attribute="key")
    assert str(caught.value) == ("Ansible's {0} filter does not support any keyword arguments. "
        "You need Jinja2 2.10 or later that provides their version of the filter.").format(filter_name)
"""
        selectors["target"].append(
            filename + "::test_public_filter_fallback_without_enhanced_jinja"
        )
        changes.append("Public fallback without enhanced Jinja filters")
    elif mechanism == "invalid-host-field-errors":
        filename = "test/units/playbook/test_play.py"
        path = overlay / "files" / filename
        text = path.read_text()
        start = text.index("def test_play_empty_hosts(value):")
        end = text.index("\n\n", start)
        # The replacement preserves the existing parametrization and membership.
        text = (
            text[:start]
            + """def test_play_empty_hosts(value):
    ambiguous = isinstance(value, (dict, set)) or value is False or type(value) is int
    message = (r"(?:Hosts list cannot be empty|Hosts list must be a sequence or string)"
               if ambiguous else r"Hosts list cannot be empty")
    with pytest.raises(AnsibleParserError, match=message):
        Play.load({"hosts": value})"""
            + text[end:]
        )
        path.write_text(text)
        extra = """\n@pytest.mark.parametrize("hosts", [[], ["one", None], ["one", {"two": None}]])
def test_rejected_hosts_preserve_input(hosts):
    import copy
    play_data = {"hosts": hosts}
    before = copy.deepcopy(play_data)
    original_hosts = play_data["hosts"]
    with pytest.raises(AnsibleParserError):
        Play.load(play_data)
    assert play_data == before
    assert play_data["hosts"] is original_hosts
    assert "name" not in play_data
"""
        selectors["target"].append(filename + "::test_rejected_hosts_preserve_input")
        changes.append(
            "Allow publicly unresolved empty/type category overlap; assert state after rejection"
        )
    else:
        filename, extra = None, ""
    if filename:
        path = overlay / "files" / filename
        path.write_text(path.read_text() + extra)
    manifest.update(
        files=inventory(overlay / "files"), status="PRESAMPLING_PUBLIC_CONTRACT_CHECKS"
    )
    manifest["modes"] = {
        name: (overlay / "files" / name).stat().st_mode & 0o777
        for name in manifest["files"]
    }
    atomic_json(overlay / "manifest.json", manifest)
    atomic_json(task / "evaluation/selectors.json", selectors)
    atomic_json(
        overlay / "contract-amendment.json",
        {"changes": changes, "reference_implementation_used": False, "agent_calls": 0},
    )
    print(mechanism, changes, flush=True)
