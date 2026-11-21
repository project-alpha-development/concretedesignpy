# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""Calc report for the masonry calculators: one display equation per check, numbers substituted."""

from concretedesignpy.clause import clause


@clause("NSCP2015-701")
def build_report(result):
    """{'title', 'lines': [{'label', 'tex', 'status', 'clause'}], 'basis', 'notes', 'status'} from a calculator result."""
    lines = []
    for c in result["checks"]:
        if c.get("ok") is None:
            status = "NOT CHECKED — " + c.get("reason", "")
        else:
            status = ("OK" if c["ok"] else "NG") + (f" (ratio {c['ratio']:.3f})" if c.get("ratio") is not None else "")
        lines.append({"label": c["label"], "tex": c.get("tex") or "", "status": status, "clause": c["clause"]})
    overall = "OK" if result["ok"] else "NOT OK"
    if not result["complete"]:
        overall += " — incomplete (" + ", ".join(result["not_checked"]) + " not checked)"
    return {"title": result["calculator"].replace("_", " ").title() + " — NSCP 2015 Ch.7 (draft vault notes)",
            "lines": lines, "basis": result["basis"], "notes": result.get("notes", []), "status": overall}
