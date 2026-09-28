#!/usr/bin/env python3
"""
footing.py -- isolated spread footing under one column, sized and designed for the NSCP
2015 load combinations generated from the column-base load cases.

    SERVICE  (NSCP 203.4.1 basic set, + the 0.6D rows 203-14/-15 for stability)
             -> base area, gross bearing, kern / partial contact, overturning, sliding
    STRENGTH (NSCP 203.3.1, E = rho Eh + Ev)
             -> two-way (punching) shear with moment transfer, one-way shear, flexure,
                minimum steel, bar spacing, bearing on the footing concrete

Engine: vendor/dp_foundation.py -- the vault's Design Procedures (MIDAS + Python) calculator
(self-test: 86 guards), vendored unchanged; see vendor/VENDORED_FROM.txt.  This wrapper adds
the load combinations, the no-tension pressure field, the integration of the factored
pressure over the critical sections, moment transfer in punching, and the sizing loops.

Basis (printed pages; NSCP folios from the vault notes, OCR -- see dp_foundation)
* base area from UNFACTORED loads, ASD combinations ... NSCP 413.3.1.1, 4-84; 203.4, 2-11
* kern e <= B/6 ....................................... W&M 7th Eq. (15-5), printed 831
* no-tension (partial contact) pressure plane ......... statics (not vault-cited)
* critical sections: moment at the column face, one-way at d, two-way at d/2
                                                        ACI 318-25M 13.2.7.1-.2, p. 210-211
* two-way vc = least of 0.33, 0.17(1 + 2/beta), 0.083(2 + alpha_s d/bo) x lam sqrt(f'c)
                                                        NSCP Table 422.6.5.2, 4-148 (no lam_s)
* moment transfer by eccentric shear gamma_v = 1 - gamma_f, gamma_f = 1/(1 + (2/3)sqrt(b1/b2))
                                                        ACI 318-25M 8.4.2.2.2, 8.4.4.2.2-.3,
                                                        R8.4.4.2.3, p. 116-119
* one-way Vc = 0.17 lam sqrt(f'c) b d ................. NSCP 422.5.5.1, 4-145 (read 2026-09-28)
* flexure phi 0.90, As,min (NSCP two-tier 0.0020 / 0.0018x420/fy >= 0.0014)
                                                        via dp_foundation.min_flexural_steel
* short-direction band gamma_s = 2/(beta + 1) ......... ACI 318-25M 13.3.3.3, p. 212
* bar spacing: least of 3h, 450 (ACI 7.7.2.3 / 8.7.2.2) and Table 24.3.2 (fs = 2/3 fy)
* depth above bottom bars >= 150 mm ................... ACI 318-25M 13.3.1.2, p. 211
* cover 75 mm cast against ground ..................... Table 420.6.1.3.1, 4-136
* bearing on the footing, phi 0.65, sqrt(A2/A1) <= 2 .. 22.8.3, p. 468
FS for overturning and sliding, the soil and concrete unit weights and q_allow are
PROJECT / OFFICE inputs (not vault-cited); NSCP 304.1(e) delegates FS to the geotechnical
report.  Settlement is not checked (no code limit exists -- vault note 03).
Units: kN, kN.m, kPa, m for plan, mm for sections.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combos as cmb                                                    # noqa: E402
from section import bar_area                                           # noqa: E402
from vendor import dp_foundation as dpf                                 # noqa: E402

VERSION = "apec-col-design/footing 0.1.0"
PHI_V, PHI_F = 0.75, 0.90

DEFAULTS = {
    "materials": {"fc": 20.684, "fy": 413.686, "lam": 1.0},
    "soil": {"q_allow": 150.0, "gamma_soil": 18.0, "Df": 1.5, "mu": 0.35, "cohesive_kPa": None,
             "silts_or_clays": False, "FS_overturning": 1.5, "FS_sliding": 1.5, "passive_kN": 0.0},
    "footing": {"cover": 75.0, "gamma_c": 24.0, "ratio": 1.0, "increment": 0.05, "t_increment": 50.0,
                "t_min": 300.0, "bar_sizes": [16, 20, 25], "s_increment": 25.0, "s_min": 100.0,
                "column_case": "interior", "pedestal_h": 0.0},
    "loads": {"f1": 0.5, "rho": 1.0, "I": 1.0, "orthogonal": False},
}


# ============================================================================ pressure
def pressure_field(P, Mx, My, Bx, By, n=40):
    """Soil pressure (kPa) on a rigid Bx x By base (m) under P (kN, down +) and base
    moments Mx (about x: varies with y), My (about y: varies with x), kN.m.
    Full contact -> linear; otherwise the no-tension plane q = max(0, a + b x + c y) is
    solved by Newton on the three equilibrium equations (statics, not vault-cited).
    Returns dict with the cell grid for integration."""
    A = Bx * By
    dx, dy = Bx / n, By / n
    xs = [-Bx / 2 + dx * (i + 0.5) for i in range(n)]
    ys = [-By / 2 + dy * (j + 0.5) for j in range(n)]
    dA = dx * dy
    if P <= 0:
        return {"ok": False, "reason": "net uplift / no compression on the soil", "q_max": math.inf}
    Ix, Iy = Bx * By ** 3 / 12.0, By * Bx ** 3 / 12.0
    a, b, c = P / A, My / Iy, Mx / Ix
    ex, ey = abs(My) / P, abs(Mx) / P
    in_kern = ex / Bx + ey / By <= 1.0 / 6.0 + 1e-12
    if ex >= Bx / 2 or ey >= By / 2 or ex / Bx + ey / By >= 0.5:
        return {"ok": False, "reason": "resultant outside the middle of the base -- overturning",
                "q_max": math.inf, "in_kern": False, "ex": ex, "ey": ey}
    if not in_kern:
        for _ in range(80):
            F0 = F1 = F2 = 0.0
            J = [[0.0] * 3 for _ in range(3)]
            for x in xs:
                for y in ys:
                    q = a + b * x + c * y
                    if q > 0:
                        v = (1.0, x, y)
                        F0 += q * dA
                        F1 += q * x * dA
                        F2 += q * y * dA
                        for r in range(3):
                            for s in range(3):
                                J[r][s] += v[r] * v[s] * dA
            R = [F0 - P, F1 - My, F2 - Mx]
            if max(abs(R[0]) / P, abs(R[1]) / (abs(My) + P * Bx * 1e-3), abs(R[2]) / (abs(Mx) + P * By * 1e-3)) < 1e-7:
                break
            d = _solve3(J, [-r for r in R])
            if d is None:
                break
            a, b, c = a + d[0], b + d[1], c + d[2]
    corners = [a + b * sx * Bx / 2 + c * sy * By / 2 for sx in (-1, 1) for sy in (-1, 1)]
    q_max = max(corners)
    q_min = min(corners)
    contact = sum(1 for x in xs for y in ys if a + b * x + c * y > 0) / (n * n)
    return {"ok": True, "a": a, "b": b, "c": c, "q_max": q_max, "q_min": max(q_min, 0.0) if not in_kern else q_min,
            "in_kern": in_kern, "contact_ratio": contact, "ex": ex, "ey": ey, "xs": xs, "ys": ys, "dA": dA}


def _solve3(J, r):
    import copy
    m = copy.deepcopy(J)
    v = list(r)
    for i in range(3):
        p = max(range(i, 3), key=lambda k: abs(m[k][i]))
        if abs(m[p][i]) < 1e-15:
            return None
        m[i], m[p] = m[p], m[i]
        v[i], v[p] = v[p], v[i]
        for k in range(i + 1, 3):
            f = m[k][i] / m[i][i]
            for j in range(i, 3):
                m[k][j] -= f * m[i][j]
            v[k] -= f * v[i]
    x = [0.0] * 3
    for i in (2, 1, 0):
        x[i] = (v[i] - sum(m[i][j] * x[j] for j in range(i + 1, 3))) / m[i][i]
    return x


def _q(pf, x, y):
    return max(0.0, pf["a"] + pf["b"] * x + pf["c"] * y)


def _integrate(pf, pred, arm=None):
    """Sum of q dA (kN) and, with arm(x, y), of q * arm dA (kN.m) over cells where pred."""
    F = M = 0.0
    for x in pf["xs"]:
        for y in pf["ys"]:
            if pred(x, y):
                q = _q(pf, x, y) * pf["dA"]
                F += q
                if arm:
                    M += q * arm(x, y)
    return F, M


# ============================================================================ design
def _combine(cases, ctype, combos, extra_D):
    out = []
    for c in combos:
        f = cmb.apply(c, cases)
        kD = max([k for case, k in c["factors"].items() if ctype.get(case) == "D"] or [0.0])
        out.append({"id": c["id"], "eq": c["eq"], "name": c["name"], "use": c.get("use", "strength"),
                    "one_third": c.get("one_third", False), "kD": kD,
                    "P": f.get("P", 0.0), "Mx": f.get("Mx", 0.0), "My": f.get("My", 0.0),
                    "Vx": f.get("Vx", 0.0), "Vy": f.get("Vy", 0.0),
                    "P_D": sum(k * cases[case].get("P", 0.0) for case, k in c["factors"].items()
                               if ctype.get(case) == "D")})
    return out


def design_footing(inp):
    cfg = _merge(DEFAULTS, inp)
    mat, soil, ft, col = cfg["materials"], cfg["soil"], cfg["footing"], cfg["column"]
    fc, fy, lam = mat["fc"], mat["fy"], mat.get("lam", 1.0)
    bxc, byc = col["b"], col["h"]                 # column plan (mm): b along x, h along y
    cases = cfg["cases"]
    ctype = cmb.classify(list(cases), cfg.get("case_types"))
    ld = cmb.settings(cfg.get("loads"))
    SU = cmb.strength_combos(ctype, ld["f1"], ld["rho"], ld["Ca"], ld["I"], ld["orthogonal"], ld["omega0"])
    SS = cmb.service_combos(ctype, ld["orthogonal"], ld["alternate_asd"], ld["stability_rows"])
    serv = _combine(cases, ctype, SS, 0.0)
    fact = _combine(cases, ctype, SU, 0.0)
    warns, checks = [], []
    ped = ft.get("pedestal_h", 0.0)

    def add(cid, clause, page, ok, value, limit, note=""):
        checks.append({"id": cid, "clause": clause, "page": page,
                       "status": ok if isinstance(ok, str) else ("OK" if ok else "FAIL"),
                       "value": value, "limit": limit, "note": note})

    def weights(Bx, By, t):
        wf = ft["gamma_c"] * Bx * By * t / 1000.0
        ws = soil["gamma_soil"] * max(Bx * By - bxc * byc / 1e6, 0.0) * max(soil["Df"] - t / 1000.0, 0.0)
        return wf, ws

    def base_forces(s, Bx, By, t):
        wf, ws = weights(Bx, By, t)
        arm = t / 1000.0 + ped
        P = s["P"] + s["kD"] * (wf + ws)
        return P, abs(s["Mx"]) + abs(s["Vy"]) * arm, abs(s["My"]) + abs(s["Vx"]) * arm

    def bearing_ok(Bx, By, t):
        worst = None
        for s in serv:
            if s["use"] != "bearing":
                continue
            P, Mx, My = base_forces(s, Bx, By, t)
            pf = pressure_field(P, Mx, My, Bx, By, 24)
            qa = soil["q_allow"] * (4.0 / 3.0 if s["one_third"] else 1.0)
            r = pf["q_max"] / qa if pf.get("ok") else math.inf
            if worst is None or r > worst[0]:
                worst = (r, s, pf, qa, P)
        return worst

    # ---------------- plan size
    t = float(ft.get("t") or max(ft["t_min"], 300.0))
    if ft.get("B") and ft.get("L"):
        Bx, By = float(ft["B"]), float(ft["L"])
    else:
        ratio = ft["ratio"]
        Bx = max(bxc, byc) / 1000.0 + 0.3
        while True:
            By = Bx * ratio
            w = bearing_ok(Bx, By, t)
            if w and w[0] <= 1.0 + 1e-9:
                break
            Bx = round(Bx + ft["increment"], 4)
            if Bx > 12.0:
                warns.append("footing size exceeded 12 m in the search -- check q_allow and the loads")
                break
    # ---------------- thickness and bars
    cover = ft["cover"]
    best = None
    t_try = float(ft.get("t") or ft["t_min"])
    for _ in range(40):
        res = _strength(fact, Bx, By, t_try, cfg, bxc, byc, fc, fy, lam, ped)
        if res["shear_ok"] or ft.get("t"):
            best = res
            break
        t_try += ft["t_increment"]
    if best is None:
        best = res
        warns.append("thickness search stopped at the 40th step -- shear still governs")
    t = best["t"]
    # the plan size was chosen at the first t; re-check bearing at the final t
    if not (ft.get("B") and ft.get("L")):
        while True:
            w = bearing_ok(Bx, By, t)
            if w and w[0] <= 1.0 + 1e-9:
                break
            Bx = round(Bx + ft["increment"], 4)
            By = Bx * ft["ratio"]
            best = _strength(fact, Bx, By, t, cfg, bxc, byc, fc, fy, lam, ped)
            if Bx > 12.0:
                break
    # ---------------- final checks
    w = bearing_ok(Bx, By, t)
    r, s, pf, qa, P = w
    add("bearing_service", "413.3.1.1 + 203.4.1 (ASD, no increase) | R13.2.6.1", "4-84, 2-11 | 208",
        r <= 1.0 + 1e-9, round(pf["q_max"], 1), f"<= q_allow {qa:.0f} kPa",
        f"{s['id']} {s['name']}; {'in kern' if pf.get('in_kern') else 'PARTIAL CONTACT ' + format(pf.get('contact_ratio', 0), '.0%') + ' of the base'}")
    partial = [x for x in serv if x["use"] == "bearing" and not pressure_field(*base_forces(x, Bx, By, t), Bx, By, 16).get("in_kern", True)]
    if partial:
        add("kern_service", "W&M 7th Eq. (15-5) (kern)", "831", "WARN", len(partial), "0 combos outside the kern",
            "part of the base lifts off under " + ", ".join(p["id"] for p in partial[:6])
            + " -- q_max is from the no-tension solution (statics, not vault-cited)")
    fs_o, fs_s = soil["FS_overturning"], soil["FS_sliding"]
    worst_o, worst_s = None, None
    for s2 in serv:
        P2, Mx2, My2 = base_forces(s2, Bx, By, t)
        for dirn, M, dim in (("x", My2, Bx), ("y", Mx2, By)):
            if M <= 0:
                continue
            o = dpf.check_overturning(M_driving=M, N_resisting=max(P2, 0.0), dimension=dim, FS=fs_o, direction=dirn)
            if worst_o is None or o["FS_computed"] < worst_o[0]["FS_computed"]:
                worst_o = (o, s2)
        H = math.hypot(s2["Vx"], s2["Vy"])
        if H > 0:
            wf, ws = weights(Bx, By, t)
            dead = max(s2["P_D"] + s2["kD"] * (wf + ws), 0.0)
            sl = dpf.check_sliding(H=H, N=max(P2, 0.0), area=Bx * By, dead_load=dead, FS=fs_s,
                                   mu=None if soil.get("cohesive_kPa") else soil["mu"],
                                   cohesive_resistance_kPa=soil.get("cohesive_kPa"),
                                   silts_or_clays=soil["silts_or_clays"], passive_kN=soil["passive_kN"])
            if worst_s is None or sl["FS_computed"] < worst_s[0]["FS_computed"]:
                worst_s = (sl, s2)
        if P2 <= 0:
            add(f"uplift_{s2['id']}", "statics (not vault-cited)", "-", False, round(P2, 1), "> 0 kN",
                f"net uplift under {s2['name']} -- anchor or enlarge")
    if worst_o:
        o, s2 = worst_o
        add("overturning", "statics; FS office practice (not vault-cited; NSCP 304.1(e))", "3-12",
            o["passed"], round(o["FS_computed"], 2), f">= {fs_o}", f"{s2['id']} {s2['name']} ({o['direction']})")
    if worst_s:
        sl, s2 = worst_s
        add("sliding", "Table 304-1 + footnote ceiling (1/2 dead load); FS (not vault-cited)", "3-13",
            sl["passed"], round(sl["FS_computed"], 2), f">= {fs_s}", f"{s2['id']} {s2['name']}")
    checks += best["checks"]
    wf, ws = weights(Bx, By, t)
    sched = {"plan": f"{Bx:.2f} m (x) x {By:.2f} m (y) x {t:.0f} mm thick, base at Df = {soil['Df']:.2f} m",
             "bars_x": best["bars_x_txt"], "bars_y": best["bars_y_txt"],
             "cover": f"{cover:.0f} mm (cast against ground, Table 420.6.1.3.1)",
             "self_weight": f"footing {wf:.1f} kN + soil above {ws:.1f} kN (included as D in the service set)"}
    return {"id": cfg.get("id"), "tool": VERSION, "member": "footing",
            "verdict": "FAIL" if any(c["status"] == "FAIL" for c in checks) else
            ("OK with warnings" if any(c["status"] == "WARN" for c in checks) else "OK"),
            "schedule": sched, "Bx": Bx, "By": By, "t": t, "soil": soil, "materials": mat, "column": col,
            "loads": ld, "combinations_service": SS, "combinations_strength": SU,
            "service": [{k: v for k, v in x.items()} for x in serv], "strength": best["detail"],
            "checks": checks, "warnings": sorted(set(warns + best["warnings"])),
            "not_checked": ["settlement (no code limit -- vault Design Procedures/03)",
                            "dowel / column bar development into the footing (Ch. 25)",
                            "combined, strap, mat or pile foundations", "soil bearing capacity itself "
                            "(q_allow is a geotechnical input)", "tie beams / grade beams"]}


def _strength(fact, Bx, By, t, cfg, bxc, byc, fc, fy, lam, ped):
    ft = cfg["footing"]
    cover = ft["cover"]
    checks, warns = [], []

    def add(cid, clause, page, ok, value, limit, note=""):
        checks.append({"id": cid, "clause": clause, "page": page,
                       "status": ok if isinstance(ok, str) else ("OK" if ok else "FAIL"),
                       "value": value, "limit": limit, "note": note})

    db = float(ft.get("db") or ft["bar_sizes"][0])
    dx = t - cover - db / 2.0          # x-direction bars (bottom layer)
    dy = t - cover - 1.5 * db          # y-direction bars on top of them
    d = 0.5 * (dx + dy)
    cx, cy = bxc / 2000.0, byc / 2000.0
    worst = {"punch": (0, None), "ow_x": (0, None), "ow_y": (0, None), "M_x": (0, None), "M_y": (0, None)}
    two_way = dpf.vc_two_way(fc=fc, bo=2 * (bxc + d) + 2 * (byc + d), dx=dx, dy=dy,
                             beta=max(bxc, byc) / min(bxc, byc), column_case=ft["column_case"],
                             rigid_and_continuously_soil_supported=True, lam=lam)
    vc2 = two_way["v_c_NSCP2015_MPa"]
    b1, b2 = bxc + d, byc + d
    bo = 2 * (b1 + b2)
    detail = []
    for u in fact:
        arm = t / 1000.0 + ped
        Pu = u["P"]                                   # net: self weight and fill cancel
        Mxu = abs(u["Mx"]) + abs(u["Vy"]) * arm
        Myu = abs(u["My"]) + abs(u["Vx"]) * arm
        if Pu <= 0:
            detail.append({"id": u["id"], "note": "net uplift -- no downward soil pressure"})
            continue
        pf = pressure_field(Pu, Mxu, Myu, Bx, By, 40)
        if not pf.get("ok"):
            add(f"factored_resultant_{u['id']}", "statics", "-", False, "outside base", "within base", pf.get("reason", ""))
            continue
        # punching at d/2 with moment transfer (gamma_v); interior-column Jc (R8.4.4.2.3)
        inside = lambda x, y: abs(x) <= b1 / 2000.0 and abs(y) <= b2 / 2000.0
        F_in, _ = _integrate(pf, inside)
        Vu2 = Pu - F_in
        gf1 = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b1 / b2))
        gf2 = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b2 / b1))
        Jc1 = d * b1 ** 3 / 6.0 + b1 * d ** 3 / 6.0 + d * b2 * b1 ** 2 / 2.0
        Jc2 = d * b2 ** 3 / 6.0 + b2 * d ** 3 / 6.0 + d * b1 * b2 ** 2 / 2.0
        vu = Vu2 * 1e3 / (bo * d) + (1 - gf1) * Myu * 1e6 * (b1 / 2.0) / Jc1 + (1 - gf2) * Mxu * 1e6 * (b2 / 2.0) / Jc2
        r = vu / (PHI_V * vc2)
        if r > worst["punch"][0]:
            worst["punch"] = (r, {"id": u["id"], "Vu": Vu2, "vu": vu, "phi_vc": PHI_V * vc2})
        # one-way at d from each face, both sides, both directions
        for key, sel, width in (("ow_x", lambda x, y: x >= cx + dx / 1000.0, By),
                                ("ow_x", lambda x, y: x <= -cx - dx / 1000.0, By),
                                ("ow_y", lambda x, y: y >= cy + dy / 1000.0, Bx),
                                ("ow_y", lambda x, y: y <= -cy - dy / 1000.0, Bx)):
            dd = dx if key == "ow_x" else dy
            V, _ = _integrate(pf, sel)
            vc1 = dpf.vc_one_way(fc=fc, bw=width * 1000.0, d=dd, rigid_and_continuously_soil_supported=True,
                                 lam=lam)["V_c_NSCP2015_N"] / 1e3
            rr = V / (PHI_V * vc1)
            if rr > worst[key][0]:
                worst[key] = (rr, {"id": u["id"], "Vu": V, "phi_Vc": PHI_V * vc1})
        # moments at the column faces
        for key, sel, armf in (("M_x", lambda x, y: x >= cx, lambda x, y: x - cx),
                               ("M_x", lambda x, y: x <= -cx, lambda x, y: -cx - x),
                               ("M_y", lambda x, y: y >= cy, lambda x, y: y - cy),
                               ("M_y", lambda x, y: y <= -cy, lambda x, y: -cy - y)):
            _, M = _integrate(pf, sel, armf)
            if M > worst[key][0]:
                worst[key] = (M, {"id": u["id"], "Mu": M})
        detail.append({"id": u["id"], "Pu": Pu, "Mxu": Mxu, "Myu": Myu, "q_max": pf["q_max"],
                       "contact": pf["contact_ratio"], "punch_ratio": r})
    shear_ok = all(worst[k][0] <= 1.0 + 1e-9 for k in ("punch", "ow_x", "ow_y"))
    p = worst["punch"][1] or {}
    add("punching", "NSCP Table 422.6.5.2 + ACI 318-25M 8.4.4.2 (gamma_v Msc)", "4-148 | 116-119",
        worst["punch"][0] <= 1.0 + 1e-9, round(p.get("vu", 0.0), 3), f"<= phi vc {p.get('phi_vc', 0.0):.3f} MPa",
        f"{p.get('id')}: Vu {p.get('Vu', 0):.0f} kN, bo {bo:.0f} mm, d {d:.0f} mm, "
        f"row {two_way['governing_row_NSCP']}, alpha_s {two_way['alpha_s']}")
    for key, lab in (("ow_x", "x"), ("ow_y", "y")):
        o = worst[key][1] or {}
        add(f"one_way_shear_{lab}", "NSCP 422.5.5.1 (0.17 lam sqrt f'c b d)", "4-145",
            worst[key][0] <= 1.0 + 1e-9, round(o.get("Vu", 0.0), 1), f"<= phi Vc {o.get('phi_Vc', 0.0):.1f} kN",
            str(o.get("id", "")))
    add("depth_above_bars", "ACI 318-25M 13.3.1.2", "211", dy - db / 2.0 >= 150.0 - 1e-9,
        round(dy - db / 2.0, 0), ">= 150 mm")
    # flexure: As per direction over the full width, then bars
    bars = {}
    fy_ = fy
    for key, width, dd, lab in (("M_x", By, dx, "x"), ("M_y", Bx, dy, "y")):
        Mu = worst[key][0]
        b_mm = width * 1000.0
        Rn = Mu * 1e6 / (PHI_F * b_mm * dd * dd)
        disc = 1.0 - 2.0 * Rn / (0.85 * fc)
        As_req = 0.85 * fc / fy_ * (1.0 - math.sqrt(disc)) * b_mm * dd if disc > 0 else math.inf
        mn = dpf.min_flexural_steel(footing_type="two_way_isolated", fc=fc, fy=fy_, Ag_mm2=b_mm * t)
        As_min = mn["As_min_NSCP2015_mm2"]
        As = max(As_req, As_min)
        smax_crack = dpf.max_bar_spacing(2.0 / 3.0 * fy_, cover)["s_max_mm"]
        smax = min(3.0 * t, 450.0, smax_crack)
        choice = None
        for dbi in ft["bar_sizes"]:
            ab = bar_area(dbi)
            n = max(math.ceil(As / ab - 1e-9), 2)
            s = (b_mm - 2 * cover - dbi) / (n - 1)
            if s > smax:
                n = math.ceil((b_mm - 2 * cover - dbi) / smax) + 1
                s = (b_mm - 2 * cover - dbi) / (n - 1)
            s_r = math.floor(s / ft["s_increment"]) * ft["s_increment"]
            if s_r >= ft["s_min"]:
                n = math.ceil((b_mm - 2 * cover - dbi) / s_r) + 1
                choice = (dbi, n, s_r, n * ab)
                break
        if choice is None:
            dbi = ft["bar_sizes"][-1]
            choice = (dbi, math.ceil(As / bar_area(dbi)), ft["s_min"], math.ceil(As / bar_area(dbi)) * bar_area(dbi))
            warns.append(f"{lab}-bars: spacing below s_min -- use a larger bar or a thicker footing")
        dbi, n, s_r, As_prov = choice
        a = As_prov * fy_ / (0.85 * fc * b_mm)
        phiMn = PHI_F * As_prov * fy_ * (dd - a / 2.0) / 1e6
        add(f"flexure_{lab}", "NSCP 422.2 / ACI 13.2.7.1 (moment at the column face)", "438 | 210",
            phiMn >= Mu - 1e-6, round(phiMn, 1), f">= Mu {Mu:.1f} kN.m",
            f"{worst[key][1]['id'] if worst[key][1] else '-'}; As req {As_req:.0f}, As,min {As_min:.0f} mm2 "
            f"({mn.get('nscp_branch', 'NSCP two-tier')})")
        add(f"bar_spacing_{lab}", "3h / 450 mm; Table 24.3.2 crack control", "503", s_r <= smax + 1e-9,
            s_r, f"<= {smax:.0f} mm")
        bars[lab] = {"db": dbi, "n": n, "s": s_r, "As": As_prov, "As_req": As_req, "As_min": As_min,
                     "Mu": Mu, "phiMn": phiMn, "d": dd}
    beta = max(Bx, By) / min(Bx, By)
    band = None
    if beta > 1.0 + 1e-9:
        band = dpf.band_reinforcement(bars["y" if By < Bx else "x"]["As"], min(Bx, By), max(Bx, By))
        warns.append(f"rectangular footing: {band['gamma_s']:.3f} of the short-direction steel in a central band "
                     f"{min(Bx, By):.2f} m wide (13.3.3.3)")
    Pu_max = max(u["P"] for u in fact)
    A1 = bxc * byc
    A2 = min(Bx * 1000.0, By * 1000.0) ** 2
    brg = dpf.bearing_strength_concrete(fc=fc, A1_mm2=A1, supporting_surface_wider_all_sides=True, A2_mm2=A2)
    add("bearing_on_footing", "22.8.3 (phi 0.65, sqrt(A2/A1) <= 2)", "468", brg["phi_B_n_N"] / 1e3 >= Pu_max - 1e-6,
        round(brg["phi_B_n_N"] / 1e3, 1), f">= Pu {Pu_max:.1f} kN")
    return {"t": t, "d": d, "shear_ok": shear_ok, "checks": checks, "warnings": warns,
            "bars_x_txt": f"{bars['x']['n']}-D{bars['x']['db']:g} @ {bars['x']['s']:g} mm, bars parallel to x (bottom layer)",
            "bars_y_txt": f"{bars['y']['n']}-D{bars['y']['db']:g} @ {bars['y']['s']:g} mm, bars parallel to y"
                          + (f" (band: {band['gamma_s']:.2f} of As within the central {min(Bx, By):.2f} m)" if band else ""),
            "detail": {"per_combo": detail, "bars": bars, "punch": worst["punch"][1], "two_way_vc_MPa": vc2,
                       "bo": bo, "d": d, "band": {k: band[k] for k in ("beta", "gamma_s")} if band else None}}


def _merge(base, over):
    import copy
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


TEMPLATE = {
    "id": "F-C1", "column": {"b": 500, "h": 500},
    "materials": {"fc": 20.684, "fy": 413.686},
    "soil": {"q_allow": 150, "gamma_soil": 18, "Df": 1.5, "mu": 0.35, "FS_overturning": 1.5, "FS_sliding": 1.5},
    "footing": {"ratio": 1.0},
    "loads": {"f1": 0.5, "rho": 1.0, "Ca": 0.523, "I": 1.0},
    "cases": {"D": {"P": 820, "Mx": 8, "My": -6, "Vx": 5, "Vy": 7},
              "L": {"P": 260, "Mx": 3, "My": -2, "Vx": 2, "Vy": 3},
              "EX": {"P": 95, "Mx": -15, "My": -215, "Vx": 118, "Vy": 8},
              "EY": {"P": 140, "Mx": -230, "My": -12, "Vx": 7, "Vy": 128}},
}


def main(argv):
    if "--template" in argv:
        print(json.dumps(TEMPLATE, indent=2)); return 0
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__); return 2
    res = design_footing(json.load(open(args[0])))
    print(json.dumps(res, indent=2, default=str))
    return 1 if res["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
