"""The masonry subpackage must stay movable: it may import only the vault packages (nscp2015, asce41_17),
concretedesignpy.clause and itself — never concretedesignpy.calculators (or any other RC module)."""
import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "concretedesignpy" / "masonry"
ALLOWED_INTERNAL = ("concretedesignpy.clause", "concretedesignpy.masonry")


def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom):
            yield ("." * node.level) + (node.module or "")


def test_masonry_has_files():
    names = {p.name for p in PKG.glob("*.py")}
    assert {"__init__.py", "wall_oop.py", "wall_inplane.py", "partition.py", "fence.py", "report.py"} <= names


def test_no_import_from_calculators_or_other_rc_modules():
    bad = []
    for f in PKG.glob("*.py"):
        for mod in _imports(f):
            if mod.startswith("."):
                bad.append((f.name, mod, "relative import — use the absolute concretedesignpy.masonry path"))
            elif mod.startswith("concretedesignpy") and not mod.startswith(ALLOWED_INTERNAL):
                bad.append((f.name, mod))
    assert not bad, bad


def test_every_public_calculator_is_clause_tagged():
    import concretedesignpy.masonry as m
    for name in m.__all__:
        fn = getattr(m, name)
        assert getattr(fn, "__clauses__", None), name
