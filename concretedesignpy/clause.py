"""@clause: tag a calculator with the vault clause notes it implements.

    @clause("NSCP2015-422.5.5.1", "NSCP2015-422.5.6")
    def compute_concrete_shear_strength(...): ...

Metadata only: the function is returned unchanged, with the note ids in ``__clauses__``.
The Mind vault's ``qaqc_solver.py concretedesignpy`` compares the tags with the vault manifest
(``03_Modelling/Solvers/manifests/concretedesignpy.json``). No dependencies.
"""


def clause(*notes):
    """Record vault clause-note ids (e.g. "NSCP2015-422.5.5.1") on the function as ``__clauses__``."""
    if not notes or not all(isinstance(n, str) and n for n in notes):
        raise TypeError("@clause needs one or more clause-note ids, e.g. @clause('NSCP2015-422.5.5.1')")

    def tag(fn):
        fn.__clauses__ = notes
        return fn
    return tag
