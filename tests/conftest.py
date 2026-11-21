"""Make the Mind vault clause functions (package apec-provisions) importable for the masonry tests.
Preferred: pip install -e ~/Desktop/Mind/03_Modelling/Python. Fallback: APEC_PROVISIONS or the default vault path."""
import os
import sys

try:
    import nscp2015  # noqa: F401
except ImportError:
    _p = os.environ.get("APEC_PROVISIONS", os.path.expanduser("~/Desktop/Mind/03_Modelling/Python"))
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
