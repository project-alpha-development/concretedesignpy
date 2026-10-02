#!/usr/bin/env python3
"""Run every case in tests/benchmarks/ against the rc-design scripts.

    python3 ~/.claude/skills/rc-design/tests/run_benchmarks.py

Exit 0 only if every pinned value is inside its tolerance. A case of an unknown
"kind"/name is reported as SKIPPED, never as passed.
"""

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from flexure import face_layers, section_capacity                 # noqa: E402
from seismic import mpr                                           # noqa: E402
from shear import shear_demand, vc_nscp                           # noqa: E402
from serviceability import crack_control                          # noqa: E402
from torsion import torsion_design                                # noqa: E402

IN, KSI, KIP, KIPFT = 25.4, 6.894757, 4.44822, 1.35582


def apec_rcbeam(c):
    s, m = c["section"], c["materials"]
    (nt, dbt), (nb, dbb) = c["bars"]["top"], c["bars"]["bot"]
    t = face_layers(nb, dbb, s["b"], s["h"], s["cover"], s["dbs"])
    comp = face_layers(nt, dbt, s["b"], s["h"], s["cover"], s["dbs"])
    cap = section_capacity(s["b"], s["h"], m["fc"], m["fy"], t, comp)
    mp, _ = mpr(s["b"], s["h"], s["cover"], s["dbs"], m["fc"], m["fy"], nb, dbb, nt, dbt)
    mn_, _ = mpr(s["b"], s["h"], s["cover"], s["dbs"], m["fc"], m["fy"], nt, dbt, nb, dbb)
    return {"d_mm": cap["d"], "phiMn_pos_kNm": cap["phiMn"], "Mpr_pos_kNm": mp,
            "Vpr_kN_centreline": (mp + mn_) / c["span"]["L"]}


def wm41(c):
    r = section_capacity(c["b"], c["h"], c["fc"], c["fy"], c["tension"], c["compression"])
    return {"a_mm": r["a"], "c_mm": r["c"], "eps_t": r["eps_t"], "Mn_kNm": r["Mn"], "phi": r["phi"]}


def wm44(c):
    t = [(y * IN, a * IN * IN) for y, a in c["tension_in"]]
    cp = [(y * IN, a * IN * IN) for y, a in c["compression_in"]]
    r = section_capacity(c["b_in"] * IN, c["h_in"] * IN, c["fc_ksi"] * KSI, c["fy_ksi"] * KSI, t, cp)
    return {"Mn_kipft": r["Mn"] / KIPFT, "c_in": r["c"] / IN}


def wm61(c):
    vc, _ = vc_nscp(c["fc"], c["bw"], c["d"], c["h"])
    sd = shear_demand(c["Vu_over_phi_kN"] * 0.75, c["fc"], c["fyt"], c["bw"], c["d"], c["h"])
    return {"Vc_kN": vc, "s_mm_13M": c["Av_13M"] / sd["Av_s_req"], "Vs_limit_kN": sd["Vs_limit_22_5_1_2"]}


def wm72(c):
    r = torsion_design(c["Tu_kipft"] * KIPFT, c["Vu_kip"] * KIP, c["b_in"] * IN, c["h_in"] * IN,
                       c["d_in"] * IN, c["cover_in"] * IN, c["dbs_in"] * IN,
                       c["fc_ksi"] * KSI, c["fy_ksi"] * KSI, c["fy_ksi"] * KSI)
    return {"phiTth_kNm": r["phiTth"], "At_s_mm2_per_mm": r["At_s"], "Al_mm2": r["Al_design"],
            "Aoh_mm2": r["Aoh"], "ph_mm": r["ph"]}


def dp05(c):
    r = crack_control(1000, 600, c["cc"], 0.0, 5, 20, c["fy"])
    return {"s_max_mm": r["s_max"]}


RUNNERS = {"apec_rcbeam_id25": apec_rcbeam, "wm_4_1m_flexure": wm41, "wm_4_4_doubly": wm44,
           "wm_6_1m_shear": wm61, "wm_7_2_torsion": wm72, "dp05_crack_spacing": dp05}


def guards():
    """No-silent-acceptance guards (vault Software/12 D1/D2): zero steel must FAIL."""
    import copy
    import design_beam as D
    t = copy.deepcopy(D.TEMPLATE)
    t["provided"] = {s: {"top": [0, 25], "bot": [0, 25]} for s in ("I", "M", "J")}
    t["provided"]["stirrups"] = {"hinge": [2, 12, 100], "mid": [2, 12, 150]}
    r1 = D.design_one(t)
    g = copy.deepcopy(D.TEMPLATE)
    g["demand"]["I"]["Mu_neg"] = 5000.0            # impossible demand in design mode
    r2 = D.design_one(g)
    return [("zero bars in check mode -> FAIL", r1["verdict"] == "FAIL"),
            ("impossible Mu in design mode -> FAIL", r2["verdict"] == "FAIL")] + bw_guards()


def bw_guards():
    """NSCP 418.6.2.1(b), folio 4-113: bw >= the SMALLER of 0.3h and 250 mm."""
    import copy
    import design_beam as D

    def smf_bw(b, h):
        t = copy.deepcopy(D.TEMPLATE)
        t["section"].update({"b": b, "h": h, "dbs": 10})
        t["demand"] = {s: {"Mu_neg": 40, "Mu_pos": 20, "Vu": 30, "Tu": 0, "Nu": 0} for s in ("I", "M", "J")}
        t["gravity"].update({"wD": 8.0, "wL": 3.0})
        t["service"].update({"wD": 8.0, "wL": 3.0})
        t["bars"] = {"db_top": 16, "db_bot": 16, "n_legs": 2}
        hit = [c["status"] for c in D.design_one(t)["checks"] if c["id"] == "smf_bw"]
        return hit[0] if len(hit) == 1 else "MISSING"

    return [("SMF 200 x 500 smf_bw (limit 0.3h = 150) -> OK", smf_bw(200, 500) == "OK"),
            ("SMF 100 x 500 smf_bw (limit 0.3h = 150) -> FAIL", smf_bw(100, 500) == "FAIL"),
            ("SMF 250 x 1000 smf_bw (limit 250) -> OK", smf_bw(250, 1000) == "OK"),
            ("SMF 240 x 1000 smf_bw (limit 250) -> FAIL", smf_bw(240, 1000) == "FAIL")]


def main():
    bad = skipped = 0
    print("-- guards")
    for label, ok in guards():
        bad += not ok
        print(f"   {'PASS' if ok else 'FAIL'}  {label}")
    for path in sorted(glob.glob(os.path.join(HERE, "benchmarks", "*.json"))):
        key = os.path.splitext(os.path.basename(path))[0]
        case = json.load(open(path))
        fn = RUNNERS.get(key)
        if fn is None:
            print(f"SKIPPED  {key}: no runner"); skipped += 1; continue
        got = fn(case)
        print(f"-- {case['name']}")
        for k, (exp, tol) in case["expected"].items():
            dev = got[k] / exp - 1.0
            ok = abs(dev) <= tol
            bad += not ok
            print(f"   {'PASS' if ok else 'FAIL'}  {k:<22} got {got[k]:>12.4f}  exp {exp:>12.4f}  "
                  f"dev {dev * 100:+.2f} %  (tol {tol * 100:.1f} %)")
    print(f"\n{'ALL PASS' if not bad else f'{bad} FAILED'}" + (f", {skipped} skipped" if skipped else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
