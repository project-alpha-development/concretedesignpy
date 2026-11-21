# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""Masonry (CHB) API routes — /api/masonry/<partition|fence|wall-oop|wall-inplane>.

The engine imports the Mind vault package apec-provisions. It is imported per request so the rest of the
app still boots where that package is not installed (e.g. a deploy without the vault); those requests
get a 503 that says why.
"""

import math

from flask import Blueprint, jsonify, request

masonry_bp = Blueprint("masonry", __name__)

_CALCS = {"partition": "partition", "fence": "fence", "wall-oop": "wall_out_of_plane", "wall-inplane": "wall_in_plane"}


def _clean(x):
    """JSON-safe: non-finite floats -> None."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


@masonry_bp.route("/<calc>", methods=["POST"])
def run(calc):
    if calc not in _CALCS:
        return jsonify({"status": "error", "message": f"unknown masonry calculator '{calc}'"}), 404
    try:
        from concretedesignpy import masonry
    except ImportError as e:
        return jsonify({"status": "error", "message": "masonry needs the Mind vault package apec-provisions "
                        f"(pip install -e ~/Desktop/Mind/03_Modelling/Python): {e}"}), 503
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "JSON object body required"}), 400
    try:
        result = getattr(masonry, _CALCS[calc])(data)
        result["report"] = masonry.build_report(result)
        return jsonify({"status": "success", "result": _clean(result)})
    except NotImplementedError as e:
        return jsonify({"status": "error", "message": str(e)}), 422
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as e:
        return jsonify({"status": "error", "message": f"{type(e).__name__}: {e}"}), 400
