#!/usr/bin/env python3
"""
run_benchmarks.py -- pin apec-col-design to its sources.  Must print ALL PASS.

    python3 ~/.claude/skills/apec-col-design/tests/run_benchmarks.py

Textbook: W&M 7th Ex 11-1 (P-M points), 11-5 (biaxial state), 11-7 (biaxial check +
Bresler), 19-2 (SMF column), 19-3 (SMF joint).  Vault: Concrete/05 joint (and its gamma
finding).  Code: NSCP 2015 203.3.1 / 203.4.1 combination factors.  Statics: the no-tension
footing pressure.  Guards: zero steel, Pu > phiPn,max, pure axial.  Physics: the biaxial
penalty grows with axial load (vault OpenSees/column_models/pmm.py).  Smoke: circular
spiral column, gravity column, the example project to zip.
"""

import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import combos as cmb                                                    # noqa: E402
from design_column import design_one                                    # noqa: E402
from footing import pressure_field, design_footing                     # noqa: E402
from joint import check_joint                                           # noqa: E402
from pm import Column                                                   # noqa: E402
from section import build_section, bar_area                             # noqa: E402

IN, KSI, KIP, KFT, KIN = 25.4, 6.894757, 4.448222, 1.355818, 0.1129848
RESULTS = []


def check(name, got, want, tol, absolute=False):
    if want == 0 or absolute:
        ok = abs(got - want) <= tol
        dev = ("abs", got - want)
    else:
        dev = (got - want) / abs(want)
        ok = abs(dev) <= tol
    RESULTS.append((ok, name, got, want, dev))
    return ok


def flag(name, cond, detail=""):
    RESULTS.append((bool(cond), name, detail, "", 0.0))


def load(name):
    return json.load(open(os.path.join(HERE, "benchmarks", name)))


# ------------------------------------------------------------------------------ runners
def wm_11_1():
    b = load("wm_11_1_interaction.json")
    s = b["section_in"]
    rows = []
    for d_in, a in s["layers"]:
        y = (s["h"] / 2 - d_in) * IN
        rows += [[x * IN, y, 25.4, a / 4 * IN * IN] for x in (-6, -2, 2, 6)]
    sec = build_section({"shape": "rect", "b": s["b"] * IN, "h": s["h"] * IN, "cover": 38}, {"custom": rows})
    col = Column(sec, b["fc_ksi"] * KSI, b["fy_ksi"] * KSI, b["Es_ksi"] * KSI, beta1_override=b["beta1"])
    e, t = b["expected"], b["tolerance"]
    check("11-1 Po", col.Po / 1e3 / KIP, e["Po_kips"], t["force"])
    check("11-1 phiPn,max", col.phiPn_max / 1e3 / KIP, e["phiPn_max_kips"], t["force"])
    check("11-1 Pnt", col.Pnt / 1e3 / KIP, e["Pnt_kips"], t["force"])
    th = math.pi / 2
    dt = col._g(th)[5]
    for p in e["points"]:
        eps = p["eps_t"] if "eps_t" in p else -p["Z"] * col.eps_ty
        c = 0.003 * dt / (0.003 + eps)
        P, Mx, My, et = col.state(th, c)
        lab = f"Z={p['Z']}" if "Z" in p else "eps_t=0.005"
        if abs(p["Pn_kips"]) < 60:
            check(f"11-1 {lab} Pn", P / 1e3 / KIP, p["Pn_kips"], t["small_P_abs_kips"], absolute=True)
        else:
            check(f"11-1 {lab} Pn", P / 1e3 / KIP, p["Pn_kips"], t["force"])
        check(f"11-1 {lab} Mn", Mx / 1e6 / KFT, p["Mn_kipft"], t["moment"])
        check(f"11-1 {lab} phi", col.phi(th, P, et)[0], p["phi"], t["phi"], absolute=True)


def wm_11_5():
    b = load("wm_11_5_biaxial.json")
    s = b["section_in"]
    sec = build_section({"shape": "rect", "b": s["b"] * IN, "h": s["h"] * IN, "cover": 38},
                        {"custom": [[x * IN, y * IN, 25.4, s["bar_area_in2"] * IN * IN] for x, y in s["bars_xy_in"]]})
    col = Column(sec, b["fc_ksi"] * KSI, b["fy_ksi"] * KSI, b["Es_ksi"] * KSI)
    na = b["neutral_axis"]
    th = math.radians(na["angle_from_x_deg"] + 90.0)          # normal toward the compression side
    nx, ny = math.cos(th), math.sin(th)
    smax = abs(nx) * s["b"] / 2 * IN + abs(ny) * s["h"] / 2 * IN
    c = smax - ny * na["through_y_in"] * IN
    P, Mx, My, et = col.state(th, c)
    e, tol = b["expected"], b["tolerance"]["rel"]
    check("11-5 c_incl", c / IN, e["c_incl_in"], tol)
    check("11-5 Pn", P / 1e3 / KIP, e["Pn_kips"], tol)
    check("11-5 Mnx", Mx / 1e6 / KIN, e["Mnx_kipin"], tol)
    check("11-5 Mny", My / 1e6 / KIN, e["Mny_kipin"], tol)
    check("11-5 eps_t", -et, e["eps_t"], 0.02)
    check("11-5 phi", col.phi(th, P, et)[0], e["phi"], 1e-9, absolute=True)


def wm_11_7():
    b = load("wm_11_7_bresler.json")
    s = b["section_in"]
    sec = build_section({"shape": "rect", "b": s["b"] * IN, "h": s["h"] * IN, "cover": 38},
                        {"custom": [[x * IN, y * IN, 25.4, s["bar_area_in2"] * IN * IN] for x, y in s["bars_xy_in"]]})
    col = Column(sec, b["fc_ksi"] * KSI, b["fy_ksi"] * KSI, b["Es_ksi"] * KSI)
    d = b["demand"]
    r = col.check(d["Pu_kips"] * KIP * 1e3, d["Mux_kipft"] * KFT * 1e6, d["Muy_kipft"] * KFT * 1e6)
    flag("11-7 exact P-M-M check adequate", r["DC_M"] <= 1.0 and r["DC_PMM"] <= 1.0,
         f"DC_M {r['DC_M']:.3f}, DC_PMM {r['DC_PMM']:.3f}")
    br = col.bresler(d["Pu_kips"] * KIP * 1e3, d["Mux_kipft"] * KFT * 1e6, d["Muy_kipft"] * KFT * 1e6)
    e, t = b["expected"], b["tolerance"]
    check("11-7 Bresler phiPn", br["phiPn"] / 1e3 / KIP, e["bresler_phiPn_kips"], t["bresler"])
    check("11-7 phiPn at e/h 0.330 (chart)", br["phiPny"] / 1e3 / KIP, e["phiPn_e0330_kips"], t["chart"])
    check("11-7 phiPn at e/h 0.165 (chart)", br["phiPnx"] / 1e3 / KIP, e["phiPn_e0165_kips"], t["chart"])
    check("11-7 phiPno", br["phiPno"] / 1e3 / KIP, e["phiPno_kips"], t["phiPno"])


def wm_19_2():
    b = load("wm_19_2_smf_column.json")
    g = b["input_in"]
    cases = {k: {kk: (vv * KIP if kk in ("P", "Vx", "Vy") else vv * KFT) for kk, vv in v.items()}
             for k, v in b["cases_kips_kipft"].items()}
    bm = b["beams"]
    inp = {"id": "WM19-2", "frame": "SMF",
           "section": {"shape": "rect", "b": g["b"] * IN, "h": g["h"] * IN, "cover": g["cover"] * IN,
                       "dbt": g["hoop_db"] * IN, "edge": g["edge"] * IN},
           "materials": {"fc": b["fc_ksi"] * KSI, "fy": b["fy_ksi"] * KSI, "fyt": b["fyt_ksi"] * KSI,
                         "Es": b["Es_ksi"] * KSI},
           "geometry": {"lu": g["lu"] * IN, "second_order": True},
           "loads": {"f1": 0.5, "rho": 1.0, "I": 1.0},
           "cases": cases,
           "bars": {"db": g["bar_db"] * IN, "nx": g["nx"], "ny": g["ny"]},
           "hoops": {"db": g["hoop_db"] * IN, "legs_x": 4, "legs_y": 4, "s_lo": 150, "s_mid": 150},
           "joints": {e: {"Mx": {"Mnb": [bm["Mnb_kipft"] * KFT] * 2, "Mpr_b": bm["Mpr_b_kipft"] * KFT, "DF": bm["DF"]},
                          "column_other": {"P": [836 * KIP, 1000 * KIP]}} for e in ("top", "bottom")},
           "design": {"vc_zero_in_lo": "always"}}
    r = design_one(inp)
    e, t = b["expected"], b["tolerance"]
    Ps = sorted([round(d["P"] / KIP, 1) for d in r["demands"]])
    flag("19-2 NSCP combos reproduce W&M Table 19-5 axial loads",
         Ps == sorted(e["combo_P_kips"]), f"{Ps}")
    sm = r["smf"]
    bc = (g["b"] - 2 * g["cover"]) * IN
    check("19-2 lo", sm["lo"] / IN, e["lo_in"], t["exact"])
    check("19-2 hx", sm["lateral_support"]["hx"] / IN, e["hx_in"], t["exact"])
    check("19-2 nl", sm["lateral_support"]["nl"], e["nl"], 0, absolute=True)
    check("19-2 kn", sm["confinement"]["kn"], e["kn"], 1e-9, absolute=True)
    check("19-2 Ash/s (a)", sm["confinement"]["a"] * bc / IN, e["Ash_s_a"], t["ash"])
    check("19-2 Ash/s (b)", sm["confinement"]["b"] * bc / IN, e["Ash_s_b"], t["ash"])
    check("19-2 Ash/s (c)", sm["confinement"]["c"] * bc / IN, e["Ash_s_c"], t["ash"])
    sh = sm["shear"]["y"]
    check("19-2 Mpr (Fig. 19-27 chart)", sh["Mpr"] / KFT, e["Mpr_kipft"], t["chart"])
    check("19-2 Ve from column Mpr", sh["Ve_col"] / KIP, e["Ve_col_kips"], t["chart"])
    check("19-2 Ve (beam-limited)", sh["Ve"] / KIP, e["Ve_kips"], t["exact"])
    check("19-2 d", sh["d"] / IN, e["d_in"], t["exact"])
    check("19-2 Av/s phi 0.75, Vc = 0", sh["Ve"] / 0.75 * 1e3 / (b["fyt_ksi"] * KSI * sh["d"]) / IN,
          e["Av_s_phi075_Vc0"], t["exact"])
    check("19-2 Vc outside lo (SI 0.17 vs 2 sqrt psi)", sh["Vc_mid"] / KIP, e["Vc_outside_kips"], t["vc_si"])
    flag("19-2 verdict OK at s = 150 mm", r["verdict"] in ("OK", "OK with warnings"),
         "; ".join(f"{c['id']}" for c in r["checks"] if c["status"] == "FAIL"))


def wm_19_3():
    b = load("wm_19_3_joint.json")
    g = b["input_in"]
    d_eq = lambda a_in2: math.sqrt(4 * a_in2 * IN * IN / math.pi)
    j = {"id": "WM19-3", "fc": b["fc_ksi"] * KSI, "fy": b["fy_ksi"] * KSI,
         "column": {"b": g["column_b"] * IN, "h": g["column_h"] * IN},
         "beam_left": {"b": g["beam_b"] * IN, "h": g["beam_h"] * IN, "top": [1, d_eq(b["As_in2"]["left_top"])],
                       "bot": [1, d_eq(b["As_in2"]["right_bot"])], "Mpr_neg": 531 * KFT, "Mpr_pos": 286 * KFT},
         "beam_right": {"b": g["beam_b"] * IN, "h": g["beam_h"] * IN, "top": [1, d_eq(b["As_in2"]["left_top"])],
                        "bot": [1, d_eq(b["As_in2"]["right_bot"])], "Mpr_neg": 531 * KFT, "Mpr_pos": 286 * KFT},
         "transverse_left_b": g["beam_b"] * IN, "transverse_right_b": g["beam_b"] * IN,
         "Vcol": b["Vcol_kips"] * KIP, "bars_continuous": False}
    r = check_joint(j)
    e, t = b["expected"], b["tolerance"]
    check("19-3 Vj", r["Vj"] / KIP, e["Vj_kips"], t["Vj"])
    check("19-3 phiVn (SI coefficient)", r["phiVn"] / KIP, e["phiVn_kips"], t["phiVn"])
    check("19-3 gamma", r["gamma"], e["gamma"], 0, absolute=True)


def vault_c05():
    b = load("vault_c05_joint.json")
    i = b["input"]
    base = {"id": "C05", "fc": i["fc"], "fy": i["fy"], "column": dict(i["column"]),
            "beam_left": dict(i["beam"]), "beam_right": dict(i["beam"]),
            "transverse_left_b": i["beam"]["b"], "transverse_right_b": i["beam"]["b"],
            "H_above": i["H"], "H_below": i["H"]}
    e, tol = b["expected"], b["tolerance"]["rel"]
    r17 = check_joint({**json.loads(json.dumps(base)), "confined_faces": 4})
    check("C05 T = 1.25 fy As", r17["T_top"][0], e["T_kN"], tol)
    check("C05 Vj (Mpr with A's)", r17["Vj"], e["Vj_kN"], tol)
    check("C05 phiVn at gamma 1.7", r17["phiVn"], e["phiVn_gamma17_kN"], tol)
    r = check_joint(json.loads(json.dumps(base)))
    flag("C05 FINDING: 400 < 0.75 x 600 -> faces not confined (418.8.4.2)", r["category"] == e["category_without_override"],
         f"category {r['category']}, gamma {r['gamma']}")
    check("C05 FINDING: phiVn at gamma 1.0", r["phiVn"], e["phiVn_gamma10_kN"], tol)
    flag("C05 FINDING: the worked joint fails at gamma 1.0", r["verdict"] == "FAIL", f"Vj {r['Vj']:.0f} vs {r['phiVn']:.0f}")


def nscp_combos():
    b = load("nscp_combos.json")
    ct = cmb.classify(b["cases"])
    U = cmb.strength_combos(ct, b["f1"], b["rho"], b["Ca"], b["I"])
    Uo = cmb.strength_combos(ct, b["f1"], b["rho"], b["Ca"], b["I"], orthogonal=True)
    S = cmb.service_combos(ct)
    e = b["expected"]
    check("combos: strength count", len(U), e["n_strength"], 0, absolute=True)
    check("combos: strength count, 100/30", len(Uo), e["n_strength_orthogonal"], 0, absolute=True)
    check("combos: service count", len(S), e["n_service"], 0, absolute=True)
    for row in e["rows"]:
        pool = U if int(row["eq"].split("-")[1]) <= 7 else S
        want = {k: v for k, v in row.items() if k != "eq"}
        hit = [c for c in pool if c["eq"] == row["eq"] and all(
            abs(c["factors"].get(k, 0.0) - v) < 1e-4 for k, v in want.items()) and
            all(k in want or k == "SDL" for k in c["factors"])]
        flag(f"combos: {row['eq']} {want}", bool(hit))
    flag("combos: SDL carries the D factor", all(abs(c["factors"].get("SDL", 0) - c["factors"].get("D", 0)) < 1e-9 for c in U))


def footing_pressure():
    b = load("footing_no_tension.json")
    P, B, L = b["P_kN"], b["B_m"], b["L_m"]
    for e in b["e_m"]:
        pf = pressure_field(P, 0.0, P * e, B, L, 80)
        exact = P / (B * L) * (1 + 6 * e / B) if e <= B / 6 else 2 * P / (3 * L * (B / 2 - e))
        check(f"footing q_max e = {e} m", pf["q_max"], exact, b["tolerance"]["rel"])


def guards():
    sec0 = build_section({"shape": "rect", "b": 400, "h": 400, "cover": 40}, None)
    col0 = Column(sec0, 28, 420)
    r = col0.check(100e3, 50e6, 0.0)
    flag("guard: zero steel never scores a finite D/C", r["DC_M"] == math.inf or r["DC_M"] > 1.0,
         f"DC_M {r['DC_M']}")
    sec = build_section({"shape": "rect", "b": 400, "h": 400, "cover": 40}, {"db": 20, "nx": 3, "ny": 3})
    col = Column(sec, 28, 420)
    r = col.check(col.phiPn_max * 1.01, 1e6, 0.0)
    flag("guard: Pu > phiPn,max -> D/C = inf", r["DC_M"] == math.inf and r["DC_PMM"] == math.inf)
    r = col.check(0.5 * col.phiPn_max, 0.0, 0.0)
    check("guard: pure axial DC_PMM = Pu / phiPn,max", r["DC_PMM"], 0.5, 1e-9, absolute=True)
    # design run with zero steel requested in check mode must FAIL the verdict
    inp = {"id": "G0", "frame": "gravity", "section": {"shape": "rect", "b": 400, "h": 400, "cover": 40},
           "cases": {"D": {"P": 400, "Mx_top": 40}, "L": {"P": 100}},
           "bars": {"custom": [[0, 0, 1, 1e-6]]}, "hoops": {"db": 10, "s": 150}}
    flag("guard: near-zero steel column verdict FAIL", design_one(inp)["verdict"] == "FAIL")


def physics():
    sec = build_section({"shape": "rect", "b": 450, "h": 450, "cover": 40}, {"db": 20, "nx": 3, "ny": 3})
    col = Column(sec, 41.4, 517.5)
    ratios = []
    for n in (0.05, 0.20, 0.40):                     # NOMINAL, as in vault OpenSees/column_models/pmm.py
        P = n * col.Ag * col.fc
        uni = col.moment_at("x", P)["M"]
        c45 = col.c_for_Pn(math.pi / 4, P)           # square + symmetric bars: NA at 45 deg -> M at 45 deg
        _, mx, my, _ = col.state(math.pi / 4, c45)
        ratios.append(math.hypot(mx, my) / uni)
    # The vault's fibre-section result (pmm.py) keeps falling to n = 0.40; with the ACI rectangular
    # stress block the ratio falls from low axial load and then flattens (0.88 at both 0.20 and 0.40).
    # Pinned: the penalty at moderate/high axial load exceeds the low-axial one.
    flag("physics: biaxial penalty larger above n = 0.05 (vault pmm.py, Whitney-block form)",
         ratios[0] > max(ratios[1], ratios[2]) + 0.03, " / ".join(f"{x:.3f}" for x in ratios))
    # symmetry: the radial and load-contour ratios agree on the surface
    P = 0.3 * col.Ag * col.fc
    cap = col.capacity(P, math.radians(30))
    mx, my = cap["phiMx"], cap["phiMy"]
    r = col.check(P, mx, my)
    check("physics: DC_M = 1 on the surface", r["DC_M"], 1.0, 1e-4, absolute=True)
    check("physics: DC_PMM = 1 on the surface", r["DC_PMM"], 1.0, 2e-3, absolute=True)
    # circular section: segment formula = polygon integral and Po closed form
    csec = build_section({"shape": "circle", "D": 600, "cover": 40, "hoop": "spiral"}, {"db": 20, "n": 8})
    ccol = Column(csec, 28, 420)
    check("circle: Po = 0.85 f'c (Ag - Ast) + fy Ast",
          ccol.Po, 0.85 * 28 * (math.pi * 300 ** 2 - 8 * bar_area(20)) + 420 * 8 * bar_area(20), 1e-9)
    a0 = ccol.capacity(0.3 * ccol.Ag * 28, 0.0)["phiMn"]
    a1 = ccol.capacity(0.3 * ccol.Ag * 28, math.radians(22.5))["phiMn"]
    check("circle: capacity nearly direction-independent (8 bars)", a1, a0, 0.03)


def smoke():
    inp = {"id": "S-circle", "frame": "SMF", "section": {"shape": "circle", "D": 600, "cover": 40, "hoop": "spiral"},
           "geometry": {"lu": 3000}, "loads": {"Ca": 0.44, "I": 1.0},
           "cases": {"D": {"P": 900, "Mx_top": 20, "Mx_bot": -10}, "L": {"P": 250},
                     "EX": {"P": 60, "My_top": 180, "My_bot": -220, "Vx": 130}}}
    r = design_one(inp)
    flag("smoke: circular spiral SMF column designs", r["verdict"] in ("OK", "OK with warnings"),
         f"{r['schedule'].get('longitudinal')} | {r['schedule'].get('hoops_lo')} | " +
         "; ".join(c["id"] for c in r["checks"] if c["status"] == "FAIL"))
    inp = {"id": "S-grav", "frame": "gravity", "section": {"shape": "rect", "b": 300, "h": 300, "cover": 40},
           "cases": {"D": {"P": 500, "Mx_top": 10, "Vx": 5}, "L": {"P": 150, "Mx_top": 4}}}
    r = design_one(inp)
    flag("smoke: gravity column designs", r["verdict"] in ("OK", "OK with warnings"), r["schedule"].get("longitudinal"))
    ft = design_footing({"id": "S-F", "column": {"b": 400, "h": 400},
                         "cases": {"D": {"P": 600}, "L": {"P": 200}, "EX": {"P": 40, "My": -120, "Vx": 60}},
                         "loads": {"Ca": 0.44}})
    flag("smoke: footing designs", ft["verdict"] in ("OK", "OK with warnings"), ft["schedule"]["plan"])
    import project
    proj = json.load(open(os.path.join(HERE, "..", "examples", "project_two_storey.json")))
    out = tempfile.mkdtemp(prefix="apec_col_bench_")
    res = project.run(proj, out)
    bad = [i for v in res["verdicts"].values() for i, s in v.items() if s not in ("OK", "OK with warnings")]
    flag("smoke: example project -> zip, all members pass", os.path.exists(res["zip"] or "") and not bad,
         f"{os.path.basename(res['zip'] or '')} {bad}")


def main():
    for fn in (wm_11_1, wm_11_5, wm_11_7, wm_19_2, wm_19_3, vault_c05, nscp_combos, footing_pressure,
               guards, physics, smoke):
        try:
            fn()
        except Exception as exc:                                   # a crash is a failure, not a skip
            import traceback
            RESULTS.append((False, f"{fn.__name__} CRASHED", repr(exc), traceback.format_exc()[-400:], 0.0))
    n_bad = 0
    for ok, name, got, want, dev in RESULTS:
        if not ok:
            n_bad += 1
        if isinstance(got, float):
            d = f"abs {dev[1]:+.4g}" if isinstance(dev, tuple) else f"dev {dev:+.2%}"
            print(f"{'PASS' if ok else 'FAIL'}  {name:<58} got {got:12.4f}  want {want!s:>10}  {d}")
        else:
            print(f"{'PASS' if ok else 'FAIL'}  {name:<58} {got} {want}")
    print(f"\n{len(RESULTS) - n_bad}/{len(RESULTS)} checks passed")
    print("ALL PASS" if n_bad == 0 else f"{n_bad} FAILED")
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
