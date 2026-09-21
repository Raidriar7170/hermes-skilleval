from hermes_skilleval.intervention.local_source_index import build_index, materialize


def test_full_metadata_late_symbols_docs_and_returns(tmp_path):
    p = tmp_path / "lib" / "demo"
    p.mkdir(parents=True)
    (p / "a.py").write_text(
        "\n".join(f"def f{i}(x):\n    return x + {i}\n" for i in range(60))
    )
    (p / "z.py").write_text(
        'from demo.a import f59\nclass Documentation:\n    DOCUMENTATION = """Lists preserve all values unless empty."""\ndef run(x):\n    return f59(x)\ndef dynamic(obj):\n    return obj.f59()\n'
    )
    index = build_index(tmp_path, repository="test", revision="a" * 40)
    assert index["coverage"]["nodes"] > 60
    late = next(n for n in index["nodes"] if n["symbol"] == "lib.demo.a.f59")
    assert (
        "return x + 59"
        in materialize(
            index, late, count_tokens=len, max_tokens=2000
        ).serialized_payload
    )
    doc = next(
        n for n in index["nodes"] if n["symbol"].endswith("Documentation.DOCUMENTATION")
    )
    assert doc["role"] == "documented_contract"
    run = next(n for n in index["nodes"] if n["symbol"] == "lib.demo.z.run")
    assert any(
        e["source"] == run["node_id"]
        and e["target"] == late["node_id"]
        and e["kind"] == "direct_call"
        for e in index["edges"]
    )
    dynamic = next(n for n in index["nodes"] if n["symbol"].endswith(".dynamic"))
    assert not any(
        e["source"] == dynamic["node_id"] and e["kind"] == "direct_call"
        for e in index["edges"]
    )


def test_oversize_metadata_retained_and_no_symlink_escape(tmp_path):
    (tmp_path / "long.py").write_text(
        "def long(x):\n"
        + "".join(f"    x += {i}\n" for i in range(1000))
        + "    return x\n"
    )
    (tmp_path / "outside.py").symlink_to("/etc/passwd")
    index = build_index(tmp_path, repository="test", revision="b" * 40)
    assert len(index["nodes"]) > 0
    assert (
        materialize(index, index["nodes"][0], count_tokens=len, max_tokens=100) is None
    )
    assert index["excluded"]["outside.py"] == "symlink"


def test_branch_view_keeps_enclosing_guards_and_context(tmp_path):
    (tmp_path / "example.py").write_text(
        'def normalize(value):\n    if value is None:\n        return None\n    separator = "_"\n    if isinstance(value, list):\n        return separator.join(value)\n    return value\n'
    )
    index = build_index(tmp_path, repository="r", revision="c" * 40)
    branch = next(n for n in index["nodes"] if n["symbol"].endswith(".branch_5"))
    view = materialize(index, branch, count_tokens=len, max_tokens=2000)
    assert "if value is None:" in view.statement
    assert 'separator = "_"' in view.statement
    assert view.source_spans[0].line_start == 1
    assert ":example.py:1-6" in view.serialized_payload


def test_conditional_definition_metadata_not_lost(tmp_path):
    (tmp_path / "example.py").write_text(
        "if ENABLED:\n    def feature(x):\n        return x\n"
    )
    index = build_index(tmp_path, repository="r", revision="d" * 40)
    node = next(n for n in index["nodes"] if n["symbol"] == "example.feature")
    assert node["conditions"]


def test_shadowing_and_nested_scope_do_not_fabricate_calls(tmp_path):
    (tmp_path / "target.py").write_text("def f():\n    return 1\n")
    (tmp_path / "caller.py").write_text(
        "from target import f\ndef shadow(f):\n    return f()\ndef outer():\n    def inner():\n        return f()\n    return inner\ndef direct():\n    return f()\n"
    )
    index = build_index(tmp_path, repository="r", revision="e" * 40)
    nodes = {n["symbol"]: n for n in index["nodes"]}
    calls = [e for e in index["edges"] if e["kind"] == "direct_call"]
    assert not any(e["source"] == nodes["caller.shadow"]["node_id"] for e in calls)
    assert not any(e["source"] == nodes["caller.outer"]["node_id"] for e in calls)
    assert any(
        e["source"] == nodes["caller.direct"]["node_id"]
        and e["target"] == nodes["target.f"]["node_id"]
        for e in calls
    )
    assert (
        materialize(
            index, nodes["caller.outer.inner"], count_tokens=len, max_tokens=3000
        )
        is None
    )


def test_indirect_closure_retained_but_not_bare_pack(tmp_path):
    (tmp_path / "example.py").write_text(
        "def factory(prefix):\n    try:\n        def inner(x):\n            return prefix + x\n        return inner\n    except Exception:\n        return None\n"
    )
    index = build_index(tmp_path, repository="r", revision="f" * 40)
    inner = next(n for n in index["nodes"] if n["symbol"] == "example.factory.inner")
    assert inner["parent"]
    assert materialize(index, inner, count_tokens=len, max_tokens=3000) is None


def test_exception_and_pattern_capture_shadow_import(tmp_path):
    (tmp_path / "target.py").write_text("def f():\n    return 1\n")
    (tmp_path / "caller.py").write_text(
        'from target import f\ndef exception():\n    try:\n        pass\n    except Exception as f:\n        return f()\ndef capture(value):\n    match value:\n        case {"value": f}:\n            return f()\n'
    )
    index = build_index(tmp_path, repository="r", revision="f" * 40)
    assert not any(e["kind"] == "direct_call" for e in index["edges"])


def test_complete_conditional_view_does_not_claim_if_guard_for_else(tmp_path):
    (tmp_path / "example.py").write_text(
        "def combine(a, b, merge=False):\n    if merge:\n        return merge_dicts(a, b)\n    else:\n        return a | b\n"
    )
    index = build_index(tmp_path, repository="r", revision="a" * 40)
    node = next(n for n in index["nodes"] if n["kind"] == "branch")
    view = materialize(index, node, count_tokens=len, max_tokens=3000)
    assert view.preconditions == ()
    assert "if merge:" in view.statement and "else:" in view.statement
    assert "return a | b" in view.statement


def test_content_based_scope_includes_languages_and_extensionless_sources(tmp_path):
    sources = {
        "module.psm1": "function Invoke-Demo { Write-Output 'hello' }\n",
        "Module.cs": "class Module { public void Run() {} }\n",
        "env-setup": "#!/bin/sh\nexport DEMO=yes\n",
        "empty": "",
        "test/integration/aliases": "posix\nshippable/posix/group1\n",
    }
    for name, text in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for name, data in {
        "nul": b"abc\x00def",
        "control.cs": b"abc\x01def",
        "nonutf": b"\xff",
    }.items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "legal.cs").write_text("class Vendored {}")
    (tmp_path / "generated.psm1").write_text("# generated file\nWrite-Output hello")
    (tmp_path / "copied.cs").write_text("// vendored copy\nclass Copy {}")
    (tmp_path / "outside.cs").symlink_to(tmp_path / "Module.cs")
    index = build_index(tmp_path, repository="r", revision="a" * 40)
    assert set(index["files"]) == set(sources)
    assert set(index["parsing"].values()) == {"text"}
    assert index["edges"] == []
    assert all(not node["calls"] and not node["imports"] for node in index["nodes"])
    assert all(
        node["role"] == "existing_behavior"
        for node in index["nodes"]
        if not node["path"].startswith("test/")
    )
    assert index["excluded"] == {
        "nul": "binary",
        "control.cs": "binary",
        "nonutf": "non_utf8",
        "vendor/legal.cs": "excluded_scope",
        "generated.psm1": "declared_generated",
        "copied.cs": "declared_third_party_source",
        "outside.cs": "symlink",
    }
