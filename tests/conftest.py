import ast
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "reference_v5.2.1"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def extract_scheduler_functions(*names):
    source = (REFERENCE / "Mothbox" / "Scheduler.py").read_text()
    tree = ast.parse(source)
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in names for t in node.targets
        ):
            keep.append(node)
    module = ast.Module(body=keep, type_ignores=[])
    namespace = {}
    exec("import csv, os, datetime", namespace)
    exec(compile(module, "Scheduler_extract", "exec"), namespace)
    return namespace


@pytest.fixture
def sim_paths(tmp_path):
    from webui.config import Paths

    paths = Paths.under(tmp_path)
    shutil.copytree(REFERENCE / "mothbox_custom", paths.custom_root)
    shutil.copytree(REFERENCE / "Mothbox", paths.mothbox_root)
    return paths
