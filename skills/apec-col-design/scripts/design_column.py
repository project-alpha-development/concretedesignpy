#!/usr/bin/env python3
"""
design_column.py -- design or check an RC column for P-M (uniaxial), P-M-M (biaxial) and,
for special moment frames, NSCP 2015 Section 418.7 (strong column, confinement, shear).
The demands are the NSCP 2015 Section 203.3.1 combinations generated from the member's
UNFACTORED load cases (combos.py); a pre-factored list is accepted only as an addition.

    python3 design_column.py input.json [--out result.json] [--summary]
                                        [--report calc.md] [--plots DIR]
    python3 design_column.py --template        # example input (SMF column, load cases)
    python3 design_column.py --defaults        # APEC defaults in force

Design mode (no "bars" / "hoops" block): bars and hoops are SELECTED.
Check mode ("bars" and "hoops" given): nothing is resized.
Zero capacity is never reported as zero utilisation.  Any FAIL makes the verdict FAIL.
Units: kN, kN.m, mm, MPa.  Moments: +Mx compresses the +y face (depth h), +My the +x face
(width b) -- W&M 7th Fig. 11-35.  Shear Vx acts along x (pairs with My), Vy along y (Mx).
"""

import copy
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import combos as cmb                                                    # noqa: E402
import shear as shr                                                     # noqa: E402
import smf                                                              # noqa: E402
from pm import Column, INF                                              # noqa: E402
from section import (bar_area, build_section, clear_spacing, clear_spacing_min,   # noqa: E402
                     describe_bars, lateral_support)

VERSION = "apec-col-design 0.1.0"

# Mirror of references/apec_standards.md -- keep the two in sync.
DEFAULTS = {
    "frame": "SMF",
    "phi_rule": "nscp2015",
    "section": {"shape": "rect", "cover": 40.0, "dbt": 10.0, "dagg": 20.0},
    "materials": {"fc": 27.579, "fy": 413.686, "fyt": 275.79, "Es": 200000.0, "lam": 1.0},
    "loads": {"f1": 0.5, "rho": 1.0, "I": 1.0, "orthogonal": False},
    "geometry": {"k": 1.0, "second_order": True, "sway": True},
    "design": {"bar_sizes": [16, 20, 25, 28, 32, 36], "hoop_sizes": [10, 12, 16],
               "min_bars_per_face": None, "max_bars_per_face": 10, "s_increment": 25.0,
               "s_min": 75.0, "s_target": 100.0, "shear_d": "actual", "vc_zero_in_lo": "code",
               "radial_dc": True},
}

TEMPLATE = {
    "id": "C1-GF",
    "frame": "SMF",
    "section": {"shape": "rect", "b": 500, "h": 500, "cover": 40},
    "materials": {"fc": 27.579, "fy": 413.686, "fyt": 413.686},
    "geometry": {"lu": 3200, "second_order": True},
    "loads": {"f1": 0.5, "rho": 1.0, "Ca": 0.523, "I": 1.0, "orthogonal": True},
    "cases": {
        "D":  {"P": 820, "Mx_top": -14, "Mx_bot": 8, "My_top": 10, "My_bot": -6, "Vx": 5, "Vy": 7},
        "L":  {"P": 260, "Mx_top": -6, "Mx_bot": 3, "My_top": 4, "My_bot": -2, "Vx": 2, "Vy": 3},
        "EX": {"P": 95, "Mx_top": 12, "Mx_bot": -15, "My_top": 175, "My_bot": -215, "Vx": 118, "Vy": 8},
        "EY": {"P": 140, "Mx_top": 185, "Mx_bot": -230, "My_top": 10, "My_bot": -12, "Vx": 7, "Vy": 128},
    },
    "joints": {
        "top": {"Mx": {"Mnb": [420, 420], "Mpr_b": [530, 530], "DF": 0.5},
                "My": {"Mnb": [390, 390], "Mpr_b": [490, 490], "DF": 0.5},
                "column_other": {"P": [700, 1300]}},
        "bottom": {"foundation": True},
    },
    "_check_mode_example": {"bars": {"db": 25, "nx": 4, "ny": 4},
                            "hoops": {"db": 12, "legs_x": 4, "legs_y": 4, "s_lo": 100, "s_mid": 150}},
}


# ============================================================================ utilities
def merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def rnd(x, n=3):
    if isinstance(x, float):
        if math.isnan(x):
            return None
        return x if math.isinf(x) else round(x, n)
    if isinstance(x, dict):
        return {k: rnd(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, n) for v in x]
    return x


class Checks:
    def __init__(self):
        self.items = []

    def add(self, cid, clause, page, status, value=None, limit=None, note=""):
        self.items.append({"id": cid, "clause": clause, "page": page, "status": status,
                           "value": value, "limit": limit, "note": note})

    def verdict(self):
        if any(c["status"] == "FAIL" for c in self.items):
            return "FAIL"
        return "OK with warnings" if any(c["status"] == "WARN" for c in self.items) else "OK"


FORCE_KEYS = ("P", "Mx_top", "Mx_bot", "My_top", "My_bot", "Vx", "Vy")


def demand_sets(cfg, warns):
    """Factored force sets.  Generated from `cases` (NSCP 2015 203.3.1) and, if given,
    user `combos` appended (flagged).  Each: {id, eq, name, seismic, factors, P, Mx_top,...}."""
    out, combos = [], []
    ld = cmb.settings(cfg.get("loads"))
    if cfg.get("cases"):
        cases = cfg["cases"]
        ctype = cmb.classify(list(cases), cfg.get("case_types"))
        if "E" in ctype.values() and not (cfg.get("loads") or {}).get("Ca"):
            warns.append("load cases include E but loads.Ca is not given -- Ev = 0.5 Ca I D "
                         "(NSCP 208.6.1, 2-219) is NOT included; give Ca for the project")
        combos = cmb.strength_combos(ctype, ld["f1"], ld["rho"], ld["Ca"], ld["I"],
                                     ld["orthogonal"], ld["omega0"])
        for c in combos:
            f = cmb.apply(c, cases)
            out.append({**{k: f.get(k, 0.0) for k in FORCE_KEYS}, "id": c["id"], "eq": c["eq"],
                        "name": c["name"], "seismic": c["seismic"], "factors": c["factors"],
                        "E_share": _e_share(c, cases, ctype)})
    for i, u in enumerate(cfg.get("combos") or [], 1):
        name = u.get("name", f"user {i}")
        seismic = u.get("seismic")
        if seismic is None:
            seismic = any(t in name.upper() for t in ("E", "EQ", "RS"))
        out.append({**{k: float(u.get(k, 0.0)) for k in FORCE_KEYS}, "id": f"X{i:02d}",
                    "eq": "user", "name": name, "seismic": bool(seismic), "factors": {},
                    "E_share": {"Vx": abs(float(u.get("Vx", 0.0))), "Vy": abs(float(u.get("Vy", 0.0)))}})
    if cfg.get("combos"):
        warns.append("pre-factored combinations were supplied -- they are checked as given and "
                     "are NOT verified against NSCP 2015 203.3.1; prefer unfactored 'cases'")
    if not out:
        raise ValueError("no demands: give unfactored 'cases' (preferred) or 'combos'")
    return out, combos


def _e_share(c, cases, ctype):
    sh = {"Vx": 0.0, "Vy": 0.0}
    for case, k in c["factors"].items():
        if ctype.get(case) == "E":
            for key in sh:
                sh[key] += k * cases[case].get(key, 0.0)
    return {k: abs(v) for k, v in sh.items()}


# ============================================================================ P-M-M
def pmm_check(col, demands, radial=False, early_fail=False):
    """D/C of every demand at both ends.  Returns (rows, worst)."""
    rows, worst = [], None
    for d in demands:
        for end in ("top", "bot"):
            P, Mx, My = d["P"] * 1e3, d[f"Mx_{end}"] * 1e6, d[f"My_{end}"] * 1e6
            r = col.check(P, Mx, My, radial=radial)
            cap = r.get("cap") or {}
            row = {"combo": d["id"], "eq": d["eq"], "end": end, "Pu": d["P"], "Mux": d[f"Mx_{end}"],
                   "Muy": d[f"My_{end}"], "DC_M": r["DC_M"], "DC_PMM": r.get("DC_PMM"),
                   "phiMn": (r["phiMn"] / 1e6) if r.get("phiMn") else r.get("phiMn"),
                   "phi": cap.get("phi"), "cls": cap.get("cls"), "theta_NA": cap.get("theta_deg"),
                   "status": r["status"]}
            rows.append(row)
            key = max(row["DC_M"], row["DC_PMM"] or 0.0)
            if worst is None or key > max(worst["DC_M"], worst["DC_PMM"] or 0.0):
                worst = row
            if early_fail and row["DC_M"] > 1.0 + 1e-9:
                return rows, worst
    return rows, worst


# ============================================================================ bars
def bar_candidates(sec_spec, dz, smf_frame, hx_lim, dagg):
    """Every perimeter layout within the spacing rules, lightest first."""
    out = []
    shape = sec_spec.get("shape", "rect")
    nmin = dz["min_bars_per_face"] or (3 if smf_frame else 2)
    for db in dz["bar_sizes"]:
        if shape == "rect":
            for nx in range(nmin, dz["max_bars_per_face"] + 1):
                for ny in range(nmin, dz["max_bars_per_face"] + 1):
                    out.append({"db": float(db), "nx": nx, "ny": ny, "n": 2 * nx + 2 * ny - 4})
        else:
            for n in range(6, 4 * dz["max_bars_per_face"] + 1):
                out.append({"db": float(db), "n": n})
    good = []
    for c in out:
        try:
            s = build_section(sec_spec, c)
        except ValueError:
            continue
        clr, pitch = clear_spacing(s)
        if clr < clear_spacing_min(c["db"], dagg) - 1e-9:
            continue
        if pitch is not None and pitch > hx_lim + 1e-9:
            continue
        c["Ast"], c["rho"] = s["Ast"], s["rho"]
        good.append(c)
    good.sort(key=lambda c: (round(c["Ast"], 3), c["n"] if "n" in c else 0, -c["db"]))
    return good


# ============================================================================ main
def design_one(inp):
    cfg = merge(DEFAULTS, inp)
    if cfg["design"]["min_bars_per_face"] is None:
        cfg["design"]["min_bars_per_face"] = 3 if cfg["frame"].upper() == "SMF" else 2
    sec_spec, mat, geo, dz = cfg["section"], cfg["materials"], cfg["geometry"], cfg["design"]
    fc, fy, fyt, Es, lam = mat["fc"], mat["fy"], mat["fyt"], mat.get("Es", 200000.0), mat.get("lam", 1.0)
    smf_frame = cfg["frame"].upper() == "SMF"
    rule = cfg["phi_rule"]
    ck, warns = Checks(), []
    demands, combos = demand_sets(cfg, warns)
    seis = [d for d in demands if d["seismic"]]
    if not seis:
        if smf_frame:
            warns.append("no seismic combination found -- the E-combination axial range for Mpr, "
                         "strong-column and Vc = 0 uses ALL combinations")
        seis = demands
    P_E = (min(d["P"] for d in seis), max(d["P"] for d in seis))
    P_all = (min(d["P"] for d in demands), max(d["P"] for d in demands))
    lu = geo.get("lu")
    if smf_frame and not lu:
        raise ValueError("geometry.lu (clear height, mm) is required for SMF columns")
    Ag_est = (sec_spec["b"] * sec_spec["h"]) if sec_spec.get("shape", "rect") == "rect" else \
        math.pi * sec_spec["D"] ** 2 / 4.0
    hx_lim, all_bars = smf.hx_rule(P_E[1], Ag_est, fc) if smf_frame else (math.inf, False)
    mode = "check" if cfg.get("bars") else "design"
    mode_h = "check" if cfg.get("hoops") else "design"

    def make(bars_spec):
        s = build_section(sec_spec, bars_spec)
        c = Column(s, fc, fy, Es, rule, beta1_override=mat.get("beta1"))
        return s, c

    # ------------------------------------------------------------------ longitudinal bars
    tried = 0
    if mode == "check":
        sec, col = make(cfg["bars"])
    else:
        rho_lim = (0.01, 0.06 if smf_frame else 0.08)
        chosen = None
        for cand in bar_candidates(sec_spec, dz, smf_frame, hx_lim, sec_spec.get("dagg")):
            if cand["rho"] < rho_lim[0] - 1e-9 or cand["rho"] > rho_lim[1] + 1e-9:
                continue
            tried += 1
            s, c = make(cand)
            _, worst = pmm_check(c, demands, radial=False, early_fail=True)
            if worst and worst["DC_M"] > 1.0 + 1e-9:
                continue
            if smf_frame and not _scwb_ok(c, P_E, cfg.get("joints")):
                continue
            chosen = (s, c)
            break
        if chosen is None:
            ck.add("longitudinal_selection", "P-M-M scan (0.01-0.06 Ag)" if smf_frame else
                   "P-M-M scan (0.01-0.08 Ag)", "-", "FAIL",
                   note="no perimeter layout within the reinforcement limits carries every "
                        "combination (and the strong-column rule) -- enlarge the section or f'c")
            sec, col = make({"db": dz["bar_sizes"][-1], "nx": dz["max_bars_per_face"],
                             "ny": dz["max_bars_per_face"]} if sec_spec.get("shape", "rect") == "rect"
                            else {"db": dz["bar_sizes"][-1], "n": 4 * dz["max_bars_per_face"]})
        else:
            sec, col = chosen

    # ------------------------------------------------------------------ P-M-M, all combos
    rows, worst = pmm_check(col, demands, radial=dz.get("radial_dc", True))
    if sec["n_bars"] == 0 or sec["Ast"] <= 0:
        ck.add("bars_present", "410.6.1.1 / 418.7.4.1", "4-71 / 4-115", "FAIL", 0, ">= 0.01 Ag",
               "no longitudinal reinforcement -- capacity is not zero-utilised, it is invalid")
    fails = [r for r in rows if r["DC_M"] > 1.0 + 1e-9 or (r["DC_PMM"] or 0.0) > 1.0 + 1e-9]
    ck.add("pmm_all_combinations", "422.4 strain compatibility | 22.4", "4-143 | 440-441",
           "OK" if not fails else "FAIL", round(max(worst["DC_M"], worst["DC_PMM"] or 0), 3), "<= 1.0",
           f"governing {worst['combo']} ({worst['eq']}) {worst['end']}: Pu {worst['Pu']:.1f} kN, "
           f"Mux {worst['Mux']:.1f}, Muy {worst['Muy']:.1f} kN.m; {len(fails)} of {len(rows)} "
           "demand points fail" if fails else
           f"governing {worst['combo']} ({worst['eq']}) {worst['end']}, {len(rows)} demand points")
    ck.add("axial_cap", "Table 422.4.2.1 | Table 22.4.2.1", "4-143 | 440",
           "OK" if P_all[1] * 1e3 <= col.phiPn_max + 1e-6 else "FAIL", round(P_all[1], 1),
           f"<= phiPn,max {col.phiPn_max / 1e3:.1f} kN")

    # ------------------------------------------------------------------ reinforcement limits
    rho = sec["rho"]
    rmax = 0.06 if smf_frame else 0.08
    ck.add("rho_min", "418.7.4.1 / 410.6.1.1", "4-115 / 4-71", "OK" if rho >= 0.01 - 1e-9 else "FAIL",
           round(rho, 5), ">= 0.01")
    ck.add("rho_max", "418.7.4.1 (SMF 0.06) / 410.6.1.1 (0.08)", "4-115 / 4-71",
           "OK" if rho <= rmax + 1e-9 else "FAIL", round(rho, 5), f"<= {rmax}")
    nmin = 6 if sec["shape"] == "circle" else 4
    ck.add("min_bar_count", "410.7.3.1 / 418.7.4.2", "4-71 / 4-115",
           "OK" if sec["n_bars"] >= nmin else "FAIL", sec["n_bars"], f">= {nmin}")
    clr, pitch = clear_spacing(sec)
    smin = clear_spacing_min(sec["db_max"], sec_spec.get("dagg"))
    ck.add("bar_clear_spacing", "ACI 318-25M 25.2.3 (NSCP 425.2.3)", "510",
           "OK" if clr >= smin - 1e-9 else "FAIL", round(clr, 1), f">= {smin:.0f} mm")
    if smf_frame and sec["layout"]["kind"] == "perimeter":
        lay = sec["layout"]
        if min(lay["nx"], lay["ny"]) < 3:
            ck.add("legs_per_face", "NIST GCR 8-917-1 guidance (not a code rule)", "17", "WARN",
                   min(lay["nx"], lay["ny"]), ">= 3 bars (hoop/crosstie legs) per face",
                   "a single perimeter hoop is legal but poorly confining")

    # ------------------------------------------------------------------ geometry / slenderness
    if smf_frame:
        if sec["shape"] == "rect":
            ok1, ok2 = sec["dmin"] >= 300.0, sec["dmin"] / sec["dmax"] >= 0.4
            ck.add("smf_least_dimension", "418.7.2.1(a) | 18.7.2.1(a)", "4-115 | 334",
                   "OK" if ok1 else "FAIL", sec["dmin"], ">= 300 mm")
            ck.add("smf_aspect", "418.7.2.1(b) | 18.7.2.1(b)", "4-115 | 334",
                   "OK" if ok2 else "FAIL", round(sec["dmin"] / sec["dmax"], 3), ">= 0.4")
        else:
            ck.add("smf_least_dimension", "418.7.2.1(a)", "4-115", "OK" if sec["D"] >= 300 else "FAIL",
                   sec["D"], ">= 300 mm")
    if lu:
        k = geo.get("k", 1.0)
        rdim = {"x": (0.25 * sec["D"]) if sec["shape"] == "circle" else 0.3 * sec["h"],
                "y": (0.25 * sec["D"]) if sec["shape"] == "circle" else 0.3 * sec["b"]}
        lim = 22.0 if geo.get("sway", True) else min(34.0 + 12.0 * geo.get("M1_M2", -1.0), 40.0)
        slen = max(k * lu / rdim["x"], k * lu / rdim["y"])
        st = "OK" if slen <= lim else ("WARN" if geo.get("second_order") else "FAIL")
        ck.add("slenderness", "406.2.5 | 6.2.5.1 (r = 0.3h / 0.25D, 6.2.5.2)", "4-36 | 76-78", st,
               round(slen, 1), f"<= {lim:g}",
               "" if slen <= lim else ("slender -- demands must come from a second-order (P-Delta) "
                                       "analysis; this skill does not magnify moments"
                                       if geo.get("second_order") else
                                       "slender and second_order=false: magnified moments required "
                                       "(406.6.4 / 406.7) -- not done here"))

    # ------------------------------------------------------------------ capacity summary
    cap = {"Po": col.Po / 1e3, "Pn_max": col.Pn_max / 1e3, "phiPn_max": col.phiPn_max / 1e3,
           "Pnt": col.Pnt / 1e3, "phiPnt": col.phiPnt / 1e3, "beta1": col.b1, "eps_ty": col.eps_ty,
           "phi_rule": rule}
    curves, curves_pr = {}, {}
    conv = lambda p: {k2: (v / 1e3 if k2 in ("Pn", "phiPn") else v / 1e6 if k2 in ("Mn", "phiMn", "Mx", "My")
                           else v) for k2, v in p.items()}
    for ax in ("x", "y"):
        curves[ax] = {"pos": [conv(p) for p in col.curve(ax, 1)], "neg": [conv(p) for p in col.curve(ax, -1)]}
        curves_pr[ax] = {"pos": [conv(p) for p in col.curve(ax, 1, fyf=1.25)],
                         "neg": [conv(p) for p in col.curve(ax, -1, fyf=1.25)]}
        bal = col.balanced(ax)
        cap[f"balanced_{ax}"] = {"Pb": bal["Pn"] / 1e3, "Mb": bal["Mn"] / 1e6}
        if P_all[1] * 1e3 > bal["Pn"]:
            ck.add(f"axial_above_balanced_{ax}", "NIST GCR 8-917-1 guidance (not a code rule)", "15",
                   "WARN", round(P_all[1], 1), f"<= Pb {bal['Pn'] / 1e3:.0f} kN",
                   "compression-controlled column -- ductility and axial capacity after spalling "
                   "are compromised; NIST recommends limiting design axial load to the balanced point")

    # ------------------------------------------------------------------ SMF
    smf_out, hoops = None, None
    if smf_frame:
        smf_out, hoops = _smf_block(cfg, sec, col, demands, P_E, P_all, hx_lim, all_bars, ck, warns,
                                    mode, dz, lam)
    else:
        hoops = _gravity_hoops(cfg, sec, col, demands, ck, dz, lam)

    # ------------------------------------------------------------------ load contours
    contours = {}
    pick = {worst["combo"] + "_" + worst["end"]: worst["Pu"]}
    for lab, pu in (("Pu_max", P_all[1]), ("Pu_min", P_all[0])):
        if all(abs(pu - v) > 1.0 for v in pick.values()):
            pick[lab] = pu
    for lab, pu in pick.items():
        if col.axial_limits_ok(pu * 1e3)[0]:
            contours[lab] = {"Pu": pu, "pts": [(p["phiMx"] / 1e6, p["phiMy"] / 1e6) for p in col.contour(pu * 1e3, 72)]}

    # ------------------------------------------------------------------ bresler (info)
    gov = worst
    br = col.bresler(gov["Pu"] * 1e3, gov["Mux"] * 1e6, gov["Muy"] * 1e6) if gov["Pu"] > 0 else None
    if br and br.get("phiPn"):
        br = {k: (v / 1e3 if k in ("phiPnx", "phiPny", "phiPno", "phiPn") else v) for k, v in br.items()}

    if cfg.get("phi_rule") == "nscp2015" and fy > 420:
        warns.append("fy > 420 MPa with the NSCP 2015 phi law: ACI 318-19+ (eps_ty + 0.003) gives a "
                     "lower phi in the transition zone -- rerun with phi_rule 'envelope'")
    schedule = {"longitudinal": describe_bars(sec), "Ast": sec["Ast"], "rho": sec["rho"]}
    if hoops:
        schedule.update(hoops.get("schedule", {}))
    return {
        "id": cfg.get("id"), "tool": VERSION, "member": "column", "mode": mode if mode == mode_h else f"{mode} bars / {mode_h} hoops", "frame": cfg["frame"],
        "phi_rule": rule,
        "basis": "NSCP 2015 (Ch. 4 = ACI 318M-14); coefficients read in ACI 318-25M where equal; "
                 "combinations NSCP 2015 203.3.1 from unfactored load cases",
        "verdict": ck.verdict(), "schedule": schedule,
        "section": {k: v for k, v in sec.items() if k not in ("poly",)},
        "materials": mat, "capacity": cap, "combinations": combos,
        "demands": [{k: v for k, v in d.items() if k != "factors"} for d in demands],
        "pmm": rows, "governing": worst, "bresler_governing": br, "pm_curves": curves,
        "pm_curves_probable": curves_pr, "contours": contours, "loads": cmb.settings(cfg.get("loads")),
        "cases": cfg.get("cases"), "geometry": geo,
        "smf": smf_out, "hoops": hoops, "checks": ck.items, "warnings": sorted(set(warns)),
        "candidates_tried": tried,
        "not_checked": [
            "development length, hooks and lap-splice LENGTHS (Ch. 25; 418.7.4.3 location is noted)",
            "joint shear and joint transverse reinforcement -- see joint.py / the project runner",
            "moment magnification of slender columns (406.6.4, 406.7) -- demands must be second-order",
            "columns supporting discontinued stiff members (418.7.5.6) unless flagged",
            "IMF / OMF-specific provisions (418.4, 418.3)", "composite, prestressed or hollow sections",
            "fire, durability, construction stages",
        ],
    }


def _scwb_ok(col, P_E, joints):
    if not joints:
        return True
    for end in ("top", "bottom"):
        j = (joints or {}).get(end) or {}
        if j.get("foundation"):
            continue
        oth = j.get("column_other") or {}
        for ax in ("Mx", "My"):
            if j.get(ax) and j[ax].get("Mnb") is not None:
                r = smf.scwb(col, ax[1], P_E, j[ax], oth.get("P"), oth.get(f"Mnc_{ax[1]}"),
                             has_other=not j.get("roof", False))
                if r and not r["ok"]:
                    return False
    return True


def _smf_block(cfg, sec, col, demands, P_E, P_all, hx_lim, all_bars, ck, warns, mode, dz, lam):
    geo, mat = cfg["geometry"], cfg["materials"]
    fc, fyt = mat["fc"], mat["fyt"]
    lu = geo["lu"]
    out = {"P_E": list(P_E), "P_all": list(P_all)}
    # ---------------- lo, hx, spacing limits
    lo = smf.lo_length(sec, lu)
    out["lo"] = lo
    legs_in = cfg.get("hoops") or None
    sup = lateral_support(sec, hx_lim, all_bars, legs_in)
    out["lateral_support"] = sup
    ck.add("hx", "418.7.5.2(e)/(f) | 18.7.5.2", "4-116 | 337", "OK" if sup["hx_ok"] else "FAIL",
           round(sup["hx"], 1), f"<= {hx_lim:.0f} mm" + (" with EVERY bar supported (Pu > 0.3 Ag f'c "
                                                         "or f'c > 70)" if all_bars else ""))
    ck.add("lateral_support_rule", "425.7.2.3 / 418.7.5.2(d),(f) | 25.7.2.3", "4-170/171 | 551-552",
           "OK" if sup["rule_ok"] else "FAIL", f"legs_x {sup['legs_x']}, legs_y {sup['legs_y']}",
           f">= {sup.get('min_legs_x', '-')}, {sup.get('min_legs_y', '-')}", sup["note"])
    db_min = sec["db_min"]
    smax_lo, parts = smf.s_max_lo(sec, db_min, sup["hx"])
    out["s_max_lo"], out["s_max_lo_parts"] = smax_lo, parts
    smax_mid = smf.s_max_mid(db_min)
    if mat["fy"] > 420:
        ck.add("smf_5db_grade550", "ACI 318-19+ 18.7.5.3(c) (not NSCP 2015)", "338", "WARN",
               round(5 * db_min, 1), "s <= 5 db for Grade 550 bars", "NSCP 418.7.5.3 prints 6 db only")
    # ---------------- confinement demand
    conf = smf.confinement(sec, fc, fyt, P_all[1], sup["nl"])
    out["confinement"] = conf
    # ---------------- design shear, both directions
    dirs = shr.shear_dirs(sec, sec["layout"], dz["shear_d"])
    joints = cfg.get("joints") or {}
    shear_out = {}
    for sdir, ax in (("y", "x"), ("x", "y")):          # shear along y <-> Mx ; along x <-> My
        jj = {end: (joints.get(end) or {}).get(f"M{ax}") for end in ("top", "bottom")}
        vu = max(abs(d[f"V{sdir}"]) for d in demands)
        ve_share = max(d["E_share"][f"V{sdir}"] for d in demands)
        ds = smf.design_shear(col, ax, lu, P_E, vu, ve_share, jj, P_all[0])
        g = dirs[sdir]
        vc_lo, vc_note = shr.vc_axial(fc, g["bw"], g["d"], sec["Ag"], P_E[0], lam)
        vc_mid, _ = shr.vc_axial(fc, g["bw"], g["d"], sec["Ag"], P_all[0], lam)
        zero = ds["vc_zero"] or dz["vc_zero_in_lo"] == "always"
        vc_lo_used = 0.0 if zero else vc_lo
        vs_lim = shr.vs_limit(fc, g["bw"], g["d"])
        vn_req = min(max(ds["Ve"] / shr.PHI_V, ds["V_at_Mn"]), ds["Ve"] / shr.PHI_V_SEISMIC_BRITTLE)
        vs_req_lo = max(vn_req - vc_lo_used, 0.0)
        vs_req_mid = max(vn_req - vc_mid, 0.0)
        ds.update({"dir": sdir, "bw": g["bw"], "d": g["d"], "Vc_lo_code": vc_lo, "Vc_lo_used": vc_lo_used,
                   "Vc_mid": vc_mid, "Vc_note": vc_note, "Vs_limit": vs_lim, "Vn_req": vn_req,
                   "Vs_req_lo": vs_req_lo, "Vs_req_mid": vs_req_mid,
                   "Av_s_req_lo": vs_req_lo * 1e3 / (min(fyt, 420.0) * g["d"]),
                   "Av_s_req_mid": vs_req_mid * 1e3 / (min(fyt, 420.0) * g["d"]),
                   "Av_s_min": shr.av_min_per_s(fc, g["bw"], fyt),
                   "vc_zero_basis": "418.7.6.2.1" if ds["vc_zero"] else (
                       "option vc_zero_in_lo = always (W&M 7th printed 1075 'prudent')" if zero else "")})
        shear_out[sdir] = ds
        ck.add(f"shear_section_{sdir}", "422.5.1.2 | 22.5.1.2 (0.66; NSCP prints 0.67)", "4-144 | 442",
               "OK" if vs_req_lo <= vs_lim + 1e-9 else "FAIL", round(ds["Ve"], 1),
               f"Vs req {vs_req_lo:.1f} <= {vs_lim:.1f} kN",
               "section too small for the capacity-design shear -- no hoop fixes it" if vs_req_lo > vs_lim else "")
        warns += ds["notes"]
    out["shear"] = shear_out
    # ---------------- strong column / weak beam
    scwb_out = {}
    for end in ("top", "bottom"):
        j = joints.get(end) or {}
        if j.get("foundation"):
            scwb_out[end] = {"note": "footing -- 418.7.3 does not apply at the base"}
            continue
        oth = j.get("column_other") or {}
        for ax in ("Mx", "My"):
            if not j.get(ax) or j[ax].get("Mnb") is None:
                continue
            has_other = not j.get("roof", False)
            r = smf.scwb(col, ax[1], P_E, j[ax], oth.get("P"), oth.get(f"Mnc_{ax[1]}"), has_other)
            scwb_out[f"{end}_{ax}"] = r
            worst_row = min(r["rows"], key=lambda z: z["ratio"])
            status = "OK" if r["ok"] else "FAIL"
            note = f"Mnc this {r['Mnc_this']:.1f} + other {r['Mnc_other']:.1f} kN.m ({r['other_source']})"
            if not r["ok"] and not has_other and P_E[1] * 1e3 < sec["Ag"] * mat["fc"] / 10.0:
                status = "WARN"
                note += ("; NSCP 418.7.3.1 has no roof exemption -- ACI 318-19+ 18.7.3.1 would exempt "
                         "this joint (Pu < Ag f'c/10): engineer's decision")
            ck.add(f"scwb_{end}_{ax}", "418.7.3.2 | Eq. 18.7.3.2", "4-115 | 335", status,
                   round(worst_row["ratio"], 3), ">= 1.2", note)
    if not scwb_out or all("note" in v for v in scwb_out.values() if isinstance(v, dict)):
        warns.append("strong-column/weak-beam (418.7.3.2) NOT checked -- give joints.<end>.Mx/My.Mnb")
    out["scwb"] = scwb_out
    # ---------------- hoops
    hoops = _smf_hoops(cfg, sec, col, sup, conf, shear_out, smax_lo, smax_mid, lo, ck, dz, mode, hx_lim,
                       all_bars)
    return out, hoops


def _hoop_capacity_rect(sec, sup, db_h, conf):
    ab = bar_area(db_h)
    return {"Ash_x": sup["legs_x"] * ab, "Ash_y": sup["legs_y"] * ab, "Ab": ab,
            "s_conf_x": sup["legs_x"] * ab / (conf["ratio"] * sec["bc_y"]),
            "s_conf_y": sup["legs_y"] * ab / (conf["ratio"] * sec["bc_x"])}


def _smf_hoops(cfg, sec, col, sup, conf, shear_out, smax_lo, smax_mid, lo, ck, dz, mode, hx_lim, all_bars):
    fyt = cfg["materials"]["fyt"]
    fyt_v = min(fyt, 420.0)
    db_long = sec["db_max"]
    tie_min = 12.0 if db_long >= 36.0 else 10.0
    inc, smin_pr = dz["s_increment"], dz["s_min"]
    rect = sec["shape"] == "rect"

    def limits(db_h, legs_x, legs_y):
        ab = bar_area(db_h)
        lim = {"geometric (418.7.5.3)": smax_lo}
        if rect:
            lim["Ash legs||x (Table 418.7.5.4)"] = legs_x * ab / (conf["ratio"] * sec["bc_y"])
            lim["Ash legs||y (Table 418.7.5.4)"] = legs_y * ab / (conf["ratio"] * sec["bc_x"])
        else:
            Dc = sec["Dc"]
            lim["rho_s (Table 418.7.5.4)"] = 4.0 * ab * (Dc - db_h) / (conf["rho_s"] * Dc * Dc)
            if sec.get("hoop") == "spiral":
                lim["spiral clear pitch <= 75 mm (425.7.3.1)"] = 75.0 + db_h
        for sdir, legs in (("x", legs_x), ("y", legs_y)):
            sh = shear_out[sdir]
            av = legs * ab
            if sh["Vs_req_lo"] > 0:
                lim[f"shear V{sdir} in lo"] = av * fyt_v * sh["d"] / (sh["Vs_req_lo"] * 1e3)
            lim[f"s_max shear {sdir} (Table 10.7.6.5.2)"] = shr.s_max(sh["d"], sh["Vs_req_lo"], cfg["materials"]["fc"],
                                                                     sh["bw"])
        return lim

    def mid_limits(db_h, legs_x, legs_y):
        ab = bar_area(db_h)
        lim = {"418.7.5.5 (6db, 150)": smax_mid,
               "425.7.2.1 (16db, 48dbt, least dim)": min(16.0 * sec["db_min"], 48.0 * db_h, sec["dmin"])}
        for sdir, legs in (("x", legs_x), ("y", legs_y)):
            sh = shear_out[sdir]
            av = legs * ab
            if sh["Vs_req_mid"] > 0:
                lim[f"shear V{sdir} beyond lo"] = av * fyt_v * sh["d"] / (sh["Vs_req_mid"] * 1e3)
            if sh["Ve"] > 0.5 * shr.PHI_V * sh["Vc_mid"]:
                lim[f"Av,min {sdir} (10.6.2.2)"] = av / sh["Av_s_min"]
            lim[f"s_max shear {sdir}"] = shr.s_max(sh["d"], sh["Vs_req_mid"], cfg["materials"]["fc"], sh["bw"])
        return lim

    if cfg.get("hoops"):
        h = cfg.get("hoops") or {}
        db_h = float(h.get("db", 10.0))
        legs_x, legs_y = sup["legs_x"], sup["legs_y"]
        s_lo, s_mid = float(h.get("s_lo", h.get("s", 100.0))), float(h.get("s_mid", h.get("s", 150.0)))
        chosen = (db_h, legs_x, legs_y, s_lo, s_mid)
    else:
        chosen = None
        base_x, base_y = sup["legs_x"], sup["legs_y"]
        max_x = sec["layout"].get("ny", 2) if rect else 2
        max_y = sec["layout"].get("nx", 2) if rect else 2
        def direction(label):
            """Which leg set a governing limit belongs to (None = geometric: legs do not help)."""
            if "||x" in label or "Vx" in label or label.endswith(" x (Table 10.7.6.5.2)"):
                return "x"
            if "||y" in label or "Vy" in label or label.endswith(" y (Table 10.7.6.5.2)"):
                return "y"
            return None

        def round_s(s_lim):
            s = math.floor(s_lim / inc + 1e-9) * inc
            if s < smin_pr:                      # finer rounding before giving up on the size
                s = math.floor(s_lim / 10.0 + 1e-9) * 10.0
            return s

        options, tight = [], []
        for db_h in [d for d in dz["hoop_sizes"] if d >= tie_min]:
            lx, ly = base_x, base_y
            while True:
                lim = limits(db_h, lx, ly)
                s = round_s(min(lim.values()))
                if s >= smin_pr:
                    options.append((db_h, lx, ly, s))
                    break
                gov = min(lim, key=lim.get)
                dirn = direction(gov)
                if s >= 50.0:
                    tight.append((db_h, lx, ly, s))
                if not rect or dirn is None or (lx >= max_x and ly >= max_y):
                    break
                if dirn == "x" and lx < max_x:
                    lx += 1
                elif dirn == "y" and ly < max_y:
                    ly += 1
                else:
                    break
        if not options and tight:
            options = tight
            ck.add("hoop_spacing_practical", "APEC practical minimum (not vault-cited)", "-", "WARN",
                   max(o[3] for o in tight), f">= {smin_pr:g} mm",
                   "the code limits force hoops closer than the office minimum -- consider larger longitudinal "
                   "bars (6 db), more legs, or a larger hoop")
        # least transverse steel per metre (sum of leg areas / s); within 5 % of the least,
        # the larger spacing (easier to place); s_target only breaks remaining ties
        vol = {o: (o[1] + o[2]) * o[0] ** 2 / o[3] for o in options}
        pick = None
        if options:
            vmin = min(vol.values())
            near = [o for o in options if vol[o] <= 1.05 * vmin]
            pick = max(near, key=lambda o: (o[3] >= dz["s_target"], o[3], -o[0]))
        if pick:
            db_h, lx, ly, s_lo = pick
            mlim = mid_limits(db_h, lx, ly)
            s_mid = math.floor(min(mlim.values()) / inc + 1e-9) * inc
            chosen = (db_h, lx, ly, s_lo, max(s_mid, s_lo))
        else:
            ck.add("hoop_selection", "418.7.5.3-.4 / 418.7.6", "4-116/117", "FAIL",
                   note="no hoop size / leg count reaches s >= s_min in lo -- enlarge the section, "
                        "raise fyt, or add bars (more supported bars, more legs)")
            db_h = max(dz["hoop_sizes"])
            chosen = (db_h, sup["legs_x"], sup["legs_y"], smin_pr, smin_pr)
    db_h, legs_x, legs_y, s_lo, s_mid = chosen
    ab = bar_area(db_h)
    # ---------------- checks on the chosen hoops
    lim_lo = limits(db_h, legs_x, legs_y)
    lim_mid = mid_limits(db_h, legs_x, legs_y)
    ck.add("tie_size", "425.7.2.2 (10 mm <= D32; 12 mm >= D36)", "4-170", "OK" if db_h >= tie_min else "FAIL",
           db_h, f">= {tie_min:g} mm")
    ck.add("hoop_spacing_lo", "418.7.5.3 | 18.7.5.3", "4-116 | 338",
           "OK" if s_lo <= smax_lo + 1e-9 else "FAIL", s_lo, f"<= {smax_lo:.0f} mm",
           ", ".join(f"{k} {v:.0f}" for k, v in smf.s_max_lo(sec, sec["db_min"], sup["hx"])[1].items()))
    if rect:
        for lab, legs, bc in (("x", legs_x, sec["bc_y"]), ("y", legs_y, sec["bc_x"])):
            need = conf["ratio"] * s_lo * bc
            ck.add(f"Ash_legs_parallel_{lab}", "Table 418.7.5.4 | Table 18.7.5.4", "4-117 | 338",
                   "OK" if legs * ab >= need - 1e-6 else "FAIL", round(legs * ab, 1),
                   f">= {need:.1f} mm2 (expr. ({conf['governs']}), bc = {bc:.0f})")
    else:
        rs = smf.rho_s_provided(ab, db_h, s_lo, sec["Dc"])
        ck.add("rho_s", "Table 418.7.5.4 (d)-(f)", "4-117 | 338", "OK" if rs >= conf["rho_s"] - 1e-9 else "FAIL",
               round(rs, 5), f">= {conf['rho_s']:.5f}", conf.get("note", ""))
        clear = s_lo - db_h
        dg = cfg["section"].get("dagg") or 20.0
        ck.add("spiral_clear_pitch", "425.7.3.1", "4-171 | 553-554",
               "OK" if max(25.0, 4.0 / 3.0 * dg) - 1e-9 <= clear <= 75.0 + 1e-9 else "FAIL",
               round(clear, 1), f"{max(25.0, 4.0 / 3.0 * dg):.0f} to 75 mm")
    phis = {}
    for sdir, legs in (("x", legs_x), ("y", legs_y)):
        sh = shear_out[sdir]
        av = legs * ab
        vs_lo = min(shr.vs_provided(av, fyt, sh["d"], s_lo), sh["Vs_limit"])
        vn_lo = sh["Vc_lo_used"] + vs_lo
        phi = shr.PHI_V if vn_lo >= sh["V_at_Mn"] - 1e-9 else shr.PHI_V_SEISMIC_BRITTLE
        phis[sdir] = phi
        ck.add(f"shear_lo_V{sdir}", "418.7.6 + 421.2.4.1 | 18.7.6, 21.2.4.1", "4-117, 4-141 | 339-340, 435",
               "OK" if phi * vn_lo >= sh["Ve"] - 1e-6 else "FAIL", round(phi * vn_lo, 1),
               f">= Ve {sh['Ve']:.1f} kN",
               f"phi {phi:.2f} ({'Vn >= V at Mn' if phi == 0.75 else 'Vn < V at Mn -> 0.60'}), Vc "
               f"{sh['Vc_lo_used']:.1f}{' (= 0, ' + sh['vc_zero_basis'] + ')' if sh['Vc_lo_used'] == 0 else ''}, "
               f"Vs {vs_lo:.1f} kN; Ve from {'beams' if sh['Ve_cap'] < sh['Ve_col'] else 'column Mpr'}")
        vs_mid = min(shr.vs_provided(av, fyt, sh["d"], s_mid), sh["Vs_limit"])
        vn_mid = sh["Vc_mid"] + vs_mid
        phi_m = shr.PHI_V if vn_mid >= sh["V_at_Mn"] - 1e-9 else shr.PHI_V_SEISMIC_BRITTLE
        ck.add(f"shear_mid_V{sdir}", "418.7.6 / 422.5 beyond lo", "4-117, 4-145",
               "OK" if phi_m * vn_mid >= sh["Ve"] - 1e-6 else "FAIL", round(phi_m * vn_mid, 1),
               f">= Ve {sh['Ve']:.1f} kN", f"phi {phi_m:.2f}, Vc {sh['Vc_mid']:.1f} (Nu = least Pu "
                                            f"{sh['P_all_min']:.0f} kN), Vs {vs_mid:.1f} kN")
    ck.add("hoop_spacing_mid", "418.7.5.5 / 425.7.2.1 / Table 10.7.6.5.2", "4-116 | 339, 551, 177",
           "OK" if s_mid <= min(lim_mid.values()) + 1e-9 else "FAIL", s_mid,
           f"<= {min(lim_mid.values()):.0f} mm", min(lim_mid, key=lim_mid.get))
    lo_txt = (f"D{db_h:g} hoops + crossties: {legs_x} legs || x, {legs_y} legs || y @ {s_lo:g} mm over "
              f"lo = {lo:.0f} mm from each joint face" if rect else
              f"D{db_h:g} {'spiral' if sec.get('hoop') == 'spiral' else 'circular hoops'} @ {s_lo:g} mm over lo = {lo:.0f} mm")
    schedule = {
        "hoops_lo": lo_txt,
        "hoops_mid": f"same set @ {s_mid:g} mm beyond lo",
        "first_hoop": "bottom hoop <= s/2 above slab/footing, top hoop <= s/2 below the lowest slab bar "
                      "(<= 75 mm below the shallowest beam bar where beams frame all four sides) -- 410.7.6.2 | 10.7.6.2, p. 176",
        "lap_splice": f"centre half of the clear height only, tension (Class B) lap, hoops @ <= {min(s_lo, smax_lo):g} mm "
                      "over the lap -- 418.7.4.3 | 18.7.4.4",
        "joint": "continue lo hoops through the joint (418.8.3; half may be allowed where beams frame all "
                 "four sides and cover >= 3/4 of the column face) -- see the joint result",
    }
    return {"db": db_h, "legs_x": legs_x, "legs_y": legs_y, "s_lo": s_lo, "s_mid": s_mid, "lo": lo,
            "phi_shear": phis, "limits_lo": lim_lo, "limits_mid": lim_mid, "schedule": schedule}


def _gravity_hoops(cfg, sec, col, demands, ck, dz, lam):
    """Non-seismic column: ties per 425.7.2 and shear per 422.5 with the analysis Vu."""
    mat = cfg["materials"]
    fc, fyt = mat["fc"], mat["fyt"]
    db_long = sec["db_max"]
    tie_min = 12.0 if db_long >= 36.0 else 10.0
    h = cfg.get("hoops") or {}
    db_h = float(h.get("db", tie_min))
    sup = lateral_support(sec, math.inf, False, h if h else None)
    dirs = shr.shear_dirs(sec, sec["layout"], dz["shear_d"])
    s_geo = min(16.0 * sec["db_min"], 48.0 * db_h, sec["dmin"])
    lim = {"425.7.2.1": s_geo}
    Pmin = min(d["P"] for d in demands)
    for sdir in ("x", "y"):
        g = dirs[sdir]
        vu = max(abs(d[f"V{sdir}"]) for d in demands)
        vc, _ = shr.vc_axial(fc, g["bw"], g["d"], sec["Ag"], Pmin, lam)
        vs_req = max(vu / shr.PHI_V - vc, 0.0)
        legs = sup["legs_x"] if sdir == "x" else sup["legs_y"]
        av = legs * bar_area(db_h)
        if vs_req > 0:
            lim[f"shear V{sdir}"] = av * min(fyt, 420.0) * g["d"] / (vs_req * 1e3)
        if vu > 0.5 * shr.PHI_V * vc:
            lim[f"Av,min {sdir}"] = av / shr.av_min_per_s(fc, g["bw"], fyt)
        lim[f"s_max {sdir}"] = shr.s_max(g["d"], vs_req, fc, g["bw"])
        ck.add(f"shear_section_{sdir}", "422.5.1.2", "4-144", "OK" if vs_req <= shr.vs_limit(fc, g["bw"], g["d"])
               else "FAIL", round(vu, 1), f"Vs req {vs_req:.1f} kN")
    s_allow = math.floor(min(lim.values()) / dz["s_increment"] + 1e-9) * dz["s_increment"]
    s = float(h.get("s", s_allow))
    ck.add("tie_spacing", "425.7.2.1 / 422.5 / Table 10.7.6.5.2", "4-170 | 551, 177",
           "OK" if s <= min(lim.values()) + 1e-9 else "FAIL", s, f"<= {min(lim.values()):.0f} mm",
           min(lim, key=lim.get))
    ck.add("lateral_support_rule", "425.7.2.3", "4-170/171", "OK" if sup["rule_ok"] else "FAIL",
           f"legs_x {sup['legs_x']}, legs_y {sup['legs_y']}", "every corner and alternate bar, <= 150 mm clear")
    return {"db": db_h, "legs_x": sup["legs_x"], "legs_y": sup["legs_y"], "s": s, "limits": lim,
            "schedule": {"ties": f"D{db_h:g} ties ({sup['legs_x']} legs || x, {sup['legs_y']} || y) @ {s:g} mm"}}


# ============================================================================ output
def summary(res):
    lines = [f"{res['id']}  [column, {res['frame']}, {res['mode']}]  VERDICT: {res['verdict']}"]
    sc = res["schedule"]
    lines.append(f"  bars: {sc['longitudinal']}  rho {sc['rho']:.4f}")
    for k in ("hoops_lo", "hoops_mid", "ties"):
        if sc.get(k):
            lines.append(f"  {k}: {sc[k]}")
    g = res["governing"]
    lines.append(f"  governing: {g['combo']} {g['eq']} {g['end']}  Pu {g['Pu']:.1f} kN  Mux {g['Mux']:.1f}  "
                 f"Muy {g['Muy']:.1f} kN.m  DC_M {g['DC_M']:.3f}  DC_PMM {g['DC_PMM'] if g['DC_PMM'] is None else round(g['DC_PMM'], 3)}")
    if res.get("smf"):
        for sdir, sh in res["smf"]["shear"].items():
            lines.append(f"  V{sdir}: Mpr {sh['Mpr']:.1f} kN.m at P {sh['P_at_Mpr']:.0f}  Ve {sh['Ve']:.1f} kN "
                         f"(col {sh['Ve_col']:.1f}, cap {sh['Ve_cap']:.1f}, analysis {sh['Vu_analysis']:.1f})  "
                         f"Vc=0 in lo: {sh['Vc_lo_used'] == 0}")
    for c in res["checks"]:
        if c["status"] in ("FAIL", "WARN"):
            lines.append(f"  {c['status']:<4} {c['id']}: {c['value']} vs {c['limit']}  [{c['clause']}] {c['note']}")
    for w in res["warnings"]:
        lines.append(f"  note: {w}")
    return "\n".join(lines)


def main(argv):
    if "--template" in argv:
        print(json.dumps(TEMPLATE, indent=2)); return 0
    if "--defaults" in argv:
        print(json.dumps(DEFAULTS, indent=2)); return 0
    args = [a for a in argv if not a.startswith("--")]
    opts = {a: argv[i + 1] for i, a in enumerate(argv) if a in ("--out", "--report", "--plots") and i + 1 < len(argv)}
    args = [a for a in args if a not in opts.values()]
    if not args:
        print(__doc__); return 2
    data = json.load(open(args[0]))
    cases = data["cases_list"] if "cases_list" in data else ([data] if "members" not in data else [])
    out = [rnd(design_one(c)) for c in cases]
    result = out[0] if len(out) == 1 else {"cases": out, "verdicts": {r["id"]: r["verdict"] for r in out}}
    if "--out" in opts:
        json.dump(result, open(opts["--out"], "w"), indent=2, default=str)
    else:
        print(json.dumps(result, indent=2, default=str))
    if "--report" in opts or "--plots" in opts:
        import report
        for r in out:
            if "--plots" in opts:
                import plots
                os.makedirs(opts["--plots"], exist_ok=True)
                r["figures"] = plots.column_figures(r, opts["--plots"])
            if "--report" in opts:
                path = opts["--report"] if len(out) == 1 else opts["--report"].replace(".md", f"_{r['id']}.md")
                open(path, "w").write(report.column_md(r))
    if "--summary" in argv:
        print("\n\n".join(summary(r) for r in out), file=sys.stderr)
    return 1 if any(r["verdict"] == "FAIL" for r in out) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
