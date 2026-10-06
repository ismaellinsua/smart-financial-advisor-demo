"""Rules that keep the code easy to change: core/ never touches the interface, and modules only use each other's
public names (a leading underscore means «only inside this module»)."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
CODE = [p for p in APP.rglob("*.py") if "tests" not in p.parts] + list((ROOT / "ops").rglob("*.py"))


def test_core_never_imports_the_interface():
    for path in (APP / "core").glob("*.py"):
        text = path.read_text()
        assert not re.search(r"^\s*(import|from) (streamlit|ui)\b", text, re.M), path.name


def test_no_module_imports_another_ones_private_names():
    offenders = []
    for path in CODE:
        for line in path.read_text().splitlines():
            m = re.match(r"\s*from [\w.]+ import (.+)", line)
            if m and any(name.strip().split(" as ")[0].startswith("_") for name in m.group(1).strip("()").split(",")
                         if name.strip()):
                offenders.append(f"{path.relative_to(ROOT)}: {line.strip()}")
    assert not offenders, offenders


def test_the_lockfile_matches_the_direct_requirements():
    """requirements.txt says what the app needs; requirements.lock pins it and everything below it, with hashes.
    The container installs the lock, so the two must agree (regenerate the lock as its header explains)."""
    direct = dict(re.findall(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;]+)", (ROOT / "requirements.txt").read_text(), re.M))
    lock = (ROOT / "requirements.lock").read_text()
    pinned = {name.lower().replace("_", "-"): version
              for name, version in re.findall(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", lock, re.M)}
    for name, version in direct.items():
        assert pinned.get(name.lower().replace("_", "-")) == version, f"{name}=={version} is not what the lock pins"
    assert "--hash=sha256:" in lock
