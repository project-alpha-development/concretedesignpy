#!/usr/bin/env python3
"""
beam.py -- bridge to the rc-design skill (NSCP 2015 RC beams) with the SAME load
combinations as the columns.

The beam's UNFACTORED load cases at stations I / M / J are combined with NSCP 2015
Section 203.3.1 (combos.py), enveloped per station (Mu_neg, Mu_pos, Vu, Tu, Nu), and handed to
rc-design's design_beam.py, which is run as a SUBPROCESS -- the two skills both ship a
shear.py, so they must not share an interpreter.  rc-design's SMF Ve uses
wu = (1.2 + ev) wD + fL wL; this bridge passes ev = 0.5 Ca I and fL = f1 so the capacity
shear carries the same Ev and live-load factor as the combinations.

Beam sign convention for the cases: M > 0 sagging (bottom in tension), M < 0 hogging.
"""

import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combos as cmb                                                    # noqa: E402

STATIONS = ("I", "M", "J")


def rc_design_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.expanduser("~/.claude/skills/rc-design/scripts/design_beam.py"),
              os.path.normpath(os.path.join(here, "..", "..", "rc-design", "scripts", "design_beam.py"))):
        if os.path.exists(p):
            return p
    return None


def envelope(cases, ctype, combos):
    """Per-station envelope of the strength combinations + the combination that set it."""
    env = {s: {"Mu_neg": 0.0, "Mu_pos": 0.0, "Vu": 0.0, "Tu": 0.0, "Nu": 0.0,
               "gov": {}} for s in STATIONS}
    rows = []
    for c in combos:
        for s in STATIONS:
            f = {"M": 0.0, "V": 0.0, "T": 0.0, "N": 0.0}
            for case, k in c["factors"].items():
                st = (cases[case] or {}).get(s) or {}
                for key in f:
                    f[key] += k * float(st.get(key, 0.0))
            rows.append({"combo": c["id"], "eq": c["eq"], "station": s, **f})
            e = env[s]
            for key, val in (("Mu_neg", max(0.0, -f["M"])), ("Mu_pos", max(0.0, f["M"])),
                             ("Vu", abs(f["V"])), ("Tu", abs(f["T"]))):
                if val > e[key]:
                    e[key] = val
                    e["gov"][key] = c["id"]
    return env, rows


def design_beam(inp, keep_dir=None):
    ld = cmb.settings(inp.get("loads"))
    cases = inp["cases"]
    ctype = cmb.classify(list(cases), inp.get("case_types"))
    combos = cmb.strength_combos(ctype, ld["f1"], ld["rho"], ld["Ca"], ld["I"], ld["orthogonal"], ld["omega0"])
    env, rows = envelope(cases, ctype, combos)
    rc_in = {k: v for k, v in inp.items() if k not in ("cases", "case_types", "loads")}
    rc_in["demand"] = {s: {k: round(env[s][k], 3) for k in ("Mu_neg", "Mu_pos", "Vu", "Tu", "Nu")} for s in STATIONS}
    g = dict(rc_in.get("gravity") or {})
    g.setdefault("ev", round(0.5 * ld["Ca"] * ld["I"], 5))
    g.setdefault("fL", ld["f1"])
    rc_in["gravity"] = g
    path = rc_design_path()
    out = {"id": inp.get("id"), "member": "beam", "combinations": combos, "envelope": env,
           "station_forces": rows, "rc_design_input": rc_in, "loads": ld}
    if not path:
        out.update({"verdict": "NOT RUN", "error": "rc-design skill not found (~/.claude/skills/rc-design)"})
        return out
    d = keep_dir or tempfile.mkdtemp(prefix="apec_beam_")
    fin, fout = os.path.join(d, f"{inp.get('id', 'beam')}_rc_in.json"), os.path.join(d, f"{inp.get('id', 'beam')}_rc_out.json")
    json.dump(rc_in, open(fin, "w"), indent=2)
    p = subprocess.run([sys.executable, path, fin, "--out", fout, "--summary"], capture_output=True, text=True)
    out["rc_design_summary"] = p.stderr.strip()
    if not os.path.exists(fout):
        out.update({"verdict": "ERROR", "error": (p.stderr or p.stdout)[-2000:]})
        return out
    res = json.load(open(fout))
    out.update({"verdict": res.get("verdict"), "rc_design": res, "schedule": res.get("schedule"),
                "checks": res.get("checks", []), "warnings": res.get("warnings", []),
                "not_checked": res.get("not_checked", [])})
    return out


def end_strengths(beam_res, end):
    """Mn / Mpr (kN.m) at end 'I' or 'J' of a designed beam, for joints and strong column."""
    rc = beam_res.get("rc_design") or {}
    fl = (rc.get("flexure") or {}).get(end) or {}
    se = rc.get("seismic") or {}
    return {"Mn_neg": (fl.get("top") or {}).get("Mn"), "Mn_pos": (fl.get("bot") or {}).get("Mn"),
            "Mpr_neg": se.get(f"Mpr_neg_{end}"), "Mpr_pos": se.get(f"Mpr_pos_{end}"),
            "Ve": se.get("Ve")}


def end_bars(beam_res, end):
    """(top [n, db], bot [n, db]) at end 'I' / 'J' from the rc-design schedule."""
    sch = (beam_res.get("rc_design") or {}).get("schedule") or {}
    st = sch.get(end) or {}

    def parse(txt):
        if not txt or "-D" not in txt:
            return None
        n, db = txt.split("-D")
        return [int(n), float(db)]
    return parse(st.get("top")), parse(st.get("bot"))


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    print(json.dumps(design_beam(data), indent=2, default=str))
