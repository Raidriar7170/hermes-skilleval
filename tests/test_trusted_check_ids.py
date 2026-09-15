"""Collection IDs must agree with actual pytest JUnit for functions and classes."""

import subprocess
import sys
import xml.etree.ElementTree as ET

from hermes_skilleval._maintenance.test_ids import case_id


def test_case_ids_match_real_pytest_junit(tmp_path):
    file = tmp_path / "test_cases.py"
    file.write_text("""import pytest
import unittest

@pytest.mark.parametrize("value", ["a::b", "plain"])
def test_function(value):
    assert value

class TestUnit(unittest.TestCase):
    def test_method(self):
        self.assertTrue(True)
""")
    xml = tmp_path / "result.xml"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(file),
            "--junitxml=" + str(xml),
            "--rootdir=" + str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout
    actual = sorted(
        c.attrib["classname"] + "::" + c.attrib["name"]
        for c in ET.parse(xml).iter("testcase")
    )
    expected = sorted(
        case_id(n)
        for n in [
            "test_cases.py::test_function[a::b]",
            "test_cases.py::test_function[plain]",
            "test_cases.py::TestUnit::test_method",
        ]
    )
    assert actual == expected


def test_qualification_binding_covers_case_id_helper(tmp_path, monkeypatch):
    from hermes_skilleval._maintenance import finalize

    package = tmp_path / "package"
    runtime = package / "_maintenance"
    runtime.mkdir(parents=True)
    for name in ("finalize.py", "check.py", "test_ids.py", "trusted_harness.py"):
        (runtime / name).write_text("initial")
    for name in ("repository_profile.py", "repository_maintenance.py"):
        (package / name).write_text("initial")
    task = tmp_path / "task"
    (task / "trusted").mkdir(parents=True)
    (task / "task.json").write_text("{}")
    monkeypatch.setattr(finalize, "__file__", str(runtime / "finalize.py"))
    monkeypatch.setattr(finalize, "identity", lambda image: "unit-image")
    before = finalize.binding(task)
    (runtime / "test_ids.py").write_text("changed helper")
    after = finalize.binding(task)
    assert (
        before["verifier_source"]["test_ids.py"]
        != after["verifier_source"]["test_ids.py"]
    )
