#!/usr/bin/env python3
"""
design_beam.py -- run flexure, shear, torsion, SMF seismic, serviceability and the
torsion merge for one or more RC beams; write one JSON.

    python3 design_beam.py input.json [--out result.json] [--summary]
    python3 design_beam.py --template            # example input
    python3 design_beam.py --defaults            # APEC defaults in force

Basis: NSCP 2015 (beam chapters = ACI 318M-14), coefficients read from ACI 318-25M
where the editions agree -- see references/nscp_clauses.md. Office defaults (bar
sizes, cover, rounding, materials) are APEC practice, NOT code -- see
references/apec_standards.md; every one is overridable in the input JSON.

Design mode (no "provided" block): bars and stirrups are SELECTED.
Check mode ("provided" block): the given bars/stirrups are CHECKED, nothing is resized.
Zero capacity is never reported as zero utilisation. Any FAIL makes the verdict FAIL.
"""

import copy
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flexure import bar_area, check_face, design_face                     # noqa: E402
from shear import PHI_V, shear_capacity, shear_demand                      # noqa: E402
from torsion import torsion_design, torsion_geometry                       # noqa: E402
from seismic import capacity_shear, detailing_checks, hoop_limits           # noqa: E402
from serviceability import crack_control, deflection, min_depth            # noqa: E402
from combine import pick_stirrups, side_bars, split_al                     # noqa: E402

VERSION = "rc-design 0.1.0"

# Mirror of references/apec_standards.md -- keep the two in sync.
DEFAULTS = {
    "frame": "SMF",
    "phi_rule": "nscp2015",
    "torsion_type": "equilibrium",
    "section": {"cover": 40.0, "dbs": 12.0, "dagg": 20.0},
    "materials": {"fc": 27.579, "fy": 413.686, "fyt": 275.79, "lam": 1.0},
    "bars": {"db_top": 20.0, "db_bot": 20.0, "n_legs": 2, "max_layers": 2,
             "main_sizes": [12, 16, 20, 25, 28, 32, 36],
             "stirrup_sizes": [10, 12, 16], "s_increment": 25.0, "s_min": 75.0},
    "gravity": {"wD": 0.0, "wL": 0.0, "ev": 0.0, "fL": 1.0, "Pu": 0.0},
    "service": {"support": "both_continuous", "sustained_L": 0.25, "months": 60,
                "limit_case": "attached_likely_damaged", "ie_law": "envelope"},
}

TEMPLATE = {
    "id": "2G1",
    "frame": "SMF",
    "section": {"b": 400, "h": 700, "cover": 40, "dbs": 12},
    "materials": {"fc": 27.579, "fy": 413.686, "fyt": 275.79},
    "span": {"L": 7.0},
    "columns": {"hc_i": 600, "hc_j": 600, "c1": 600, "c2": 600},
    "demand": {
        "I": {"Mu_neg": 320, "Mu_pos": 160, "Vu": 210, "Tu": 12, "Nu": 0},
        "M": {"Mu_neg": 40, "Mu_pos": 190, "Vu": 60, "Tu": 6, "Nu": 0},
        "J": {"Mu_neg": 330, "Mu_pos": 165, "Vu": 215, "Tu": 12, "Nu": 0},
    },
    "gravity": {"wD": 28.0, "wL": 12.0, "ev": 0.0, "Pu": 0},
    "service": {"support": "both_continuous", "wD": 28.0, "wL": 12.0},
    "bars": {"db_top": 25, "db_bot": 25, "n_legs": 2},
    "_provided_example_for_check_mode": {
        "I": {"top": [5, 25], "bot": [3, 25]}, "M": {"top": [2, 25], "bot": [4, 25]},
        "J": {"top": [5, 25], "bot": [3, 25]},
        "stirrups": {"hinge": [2, 12, 100], "mid": [2, 12, 150]}},
}

STATIONS = ("I", "M", "J")


def merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def rnd(x, n=2):
    if isinstance(x, float):
        return None if math.isnan(x) else (x if math.isinf(x) else round(x, n))
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


def design_one(inp):
    cfg = merge(DEFAULTS, inp)
    sec, mat, bars = cfg["section"], cfg["materials"], cfg["bars"]
    b, h, cover, dbs = sec["b"], sec["h"], sec["cover"], sec["dbs"]
    dagg = sec.get("dagg")
    fc, fy, fyt, lam = mat["fc"], mat["fy"], mat["fyt"], mat.get("lam", 1.0)
    smf = cfg["frame"].upper() == "SMF"
    rule = cfg["phi_rule"]
    ck, warns = Checks(), []
    prov = cfg.get("provided")
    mode = "check" if prov else "design"
    dem = {s: {"Mu_neg": 0.0, "Mu_pos": 0.0, "Vu": 0.0, "Tu": 0.0, "Nu": 0.0, **cfg["demand"].get(s, {})}
           for s in STATIONS}
    col = cfg.get("columns") or {}
    L = cfg["span"]["L"]
    if col.get("hc_i") and col.get("hc_j"):
        ln, ln_assumed = L - (col["hc_i"] + col["hc_j"]) / 2000.0, False
    else:
        ln, ln_assumed = cfg["span"].get("ln", L), "ln" not in cfg["span"]
    span = {"L": L, "ln": ln, "ln_assumed": ln_assumed}

    if fy > 420 and rule == "nscp2015":
        warns.append("fy > 420 MPa with the NSCP 2015 phi law: ACI 318-19 Table 21.2.2 gives "
                     "6-15 % lower phi -- rerun with phi_rule 'envelope' to see the gap")
    if fc > 70:
        warns.append("f'c > 70 MPa: sqrt(f'c) in shear/torsion is limited (22.5.3.1)")

    geo = torsion_geometry(b, h, cover, dbs)
    d_est = {"top": h - cover - dbs - bars["db_top"] / 2.0, "bot": h - cover - dbs - bars["db_bot"] / 2.0}

    # ---------------------------------------------------------------- torsion
    tor = {}
    for s in STATIONS:
        tor[s] = torsion_design(dem[s]["Tu"], dem[s]["Vu"], b, h, min(d_est.values()), cover, dbs,
                                fc, fy, fyt, dem[s]["Nu"], lam, cfg["torsion_type"])
        if tor[s]["required"]:
            ck.add(f"torsion_section_{s}", "22.7.7.1 | NSCP 422.7.7.1", "466",
                   "OK" if tor[s]["section_ok"] else "FAIL",
                   tor[s]["stress_combined"], tor[s]["stress_limit"], "MPa")
            if fyt > 420 or fy > 420:
                warns.append("torsion steel stresses capped at 420 MPa (ACI 318M-14 22.7.2.1)")
        warns += tor[s]["notes"]
    al_split = {s: split_al(tor[s]["Al_design"], geo["x0"], geo["y0"], geo["ph"]) for s in STATIONS}

    # ---------------------------------------------------------------- flexure
    fl = {s: {} for s in STATIONS}
    faces = {"top": ("Mu_neg", "db_top", "bot"), "bot": ("Mu_pos", "db_bot", "top")}
    chosen = {s: {} for s in STATIONS}
    as_flex = {}
    if prov:
        for s in STATIONS:
            chosen[s] = {"top": tuple(prov[s]["top"]), "bot": tuple(prov[s]["bot"])}
    else:
        for s in STATIONS:
            for face, (mk, dbk, other) in faces.items():
                extra = al_split[s][face]
                sb = side_bars(geo["y0"], al_split[s]["side_each"], 150.0, bars["main_sizes"])
                extra += sb.get("carry_to_corners", 0.0)
                r = design_face(abs(dem[s][mk]), b, h, cover, dbs, fc, fy, bars[dbk], 2,
                                bars[faces[other][1]], rule, dagg, bars["max_layers"],
                                allow_413=not smf, extra_as=extra)
                chosen[s][face] = (r["n"], bars[dbk]) if r.get("n") else (None, bars[dbk])
                if r.get("n"):
                    as_flex[(s, face)] = r["As_flex_prov"]
                if not r.get("n"):
                    ck.add(f"flexure_select_{s}_{face}", "flexure scan", "-", "FAIL", note=r["reason"])
        # SMF moment-strength ratios (18.6.3.2): add bottom/top bars until they hold
        if smf and all(chosen[s][f][0] for s in STATIONS for f in ("top", "bot")):
            for _ in range(60):
                caps = _caps(chosen, b, h, cover, dbs, fc, fy, rule, dagg, dem)
                fixed = True
                for e in ("I", "J"):
                    if caps[e]["bot"]["Mn"] < 0.5 * caps[e]["top"]["Mn"]:
                        n, db = chosen[e]["bot"]; chosen[e]["bot"] = (n + 1, db); fixed = False
                mmax = max(caps[e][f]["Mn"] for e in ("I", "J") for f in ("top", "bot"))
                for s in STATIONS:
                    for f in ("top", "bot"):
                        if caps[s][f]["Mn"] < 0.25 * mmax:
                            n, db = chosen[s][f]; chosen[s][f] = (n + 1, db); fixed = False
                if fixed:
                    break
    ok_bars = all(chosen[s][f][0] for s in STATIONS for f in ("top", "bot"))
    for s in STATIONS:
        for f in ("top", "bot"):
            if not chosen[s][f][0]:
                # never let a missing face fall through to a passing verdict (Software/12 D1)
                ck.add(f"bars_present_{s}_{f}", "18.6.3.1 / 9.6.1.2", "328 / 149", "FAIL",
                       chosen[s][f][0], ">= 2 bars", "no reinforcement on this face -- capacity is zero")
    # Crack control (Table 24.3.2) on the tension faces: add bars of the same size
    # until the spacing passes -- more, smaller-spaced bars, never a larger fs.
    if not prov and ok_bars:
        for s, f in (("M", "bot"), ("I", "top"), ("J", "top")):
            for _ in range(20):
                n, db = chosen[s][f]
                cc_ = crack_control(b, h, cover, dbs, n, db, fy, dagg=dagg)
                if cc_["ok"]:
                    break
                chosen[s][f] = (n + 1, db)
    caps = _caps(chosen, b, h, cover, dbs, fc, fy, rule, dagg, dem, allow_413=not smf) if ok_bars else {}
    for s in caps:
        for face, (mk, _, _) in faces.items():
            r = caps[s][face]
            fl[s][face] = r
            need_al = al_split[s][face]
            dc = r["DC"]
            ck.add(f"flexure_{s}_{face}", "22.2 / 9.5.1.1 | NSCP 422.2", "438 / 147",
                   "OK" if dc <= 1.0 else "FAIL", round(dc, 3), "<= 1.0",
                   f"phiMn {r['phiMn']:.1f} vs Mu {r['Mu']:.1f} kN.m, {r['classification']}")
            ck.add(f"as_min_{s}_{face}", "9.6.1.2" + ("" if smf else " / 9.6.1.3"), "149",
                   "OK" if (r["As_min_ok"] if not smf else r["As_prov"] >= r["As_min"]) else "FAIL",
                   round(r["As_prov"]), f">= {r['As_min']:.0f} mm2",
                   "4/3 As,req exemption used" if r.get("As_min_exempt_9_6_1_3") and not smf else "")
            ck.add(f"eps_t_{s}_{face}", "NSCP 2015 eps_t >= 0.004 (318-25M R9.3.3.1)", "144",
                   "OK" if r["eps_t"] >= 0.004 else "FAIL", round(r["eps_t"], 5), ">= 0.004")
            if r["classification"] != "tension-controlled" and abs(dem[s][mk]) > 0:
                ck.add(f"tension_controlled_{s}_{face}", "ACI 318-19/-25 9.3.3.1 (not NSCP 2015)", "144",
                       "WARN", r["classification"], "tension-controlled",
                       "legal under NSCP 2015, prohibited under ACI 318-19+")
            if need_al > 0:
                flex_need = as_flex.get((s, face))
                if flex_need is None:
                    flex_need = r["As_req_closed_form"] if r["As_req_closed_form"] is not None else math.inf
                need = flex_need + need_al
                ck.add(f"torsion_Al_{s}_{face}", "9.5.4.3 (torsion Al added to flexure)", "147",
                       "OK" if r["As_prov"] >= need - 1e-6 else "FAIL", round(r["As_prov"]),
                       f">= {need:.0f} mm2 (flexure {flex_need:.0f} + Al share {need_al:.0f})")

    # ---------------------------------------------------------------- seismic
    seis = None
    d_st = {s: min(fl[s]["top"]["d"], fl[s]["bot"]["d"]) for s in fl} if caps else {s: min(d_est.values()) for s in STATIONS}
    if smf and caps:
        grav = cfg["gravity"]
        seis = capacity_shear({e: chosen[e] for e in ("I", "J")}, {"b": b, "h": h, "cover": cover, "dbs": dbs, "dagg": dagg},
                              {"fc": fc, "fy": fy}, span, grav, grav.get("Pu", 0.0))
        warns += seis["warnings"]
        for c in detailing_checks({"b": b, "h": h}, {"fc": fc, "fy": fy}, span, chosen,
                                  {s: {f: caps[s][f] for f in ("top", "bot")} for s in STATIONS},
                                  d_st, {"c1": col.get("c1"), "c2": col.get("c2"),
                                         "hc_i": col.get("hc_i"), "hc_j": col.get("hc_j")}, lam):
            ck.items.append(c)
        if ln_assumed:
            ck.add("smf_ln", "18.6.5.1 clear span", "331-333", "WARN", L, "ln = L - column depth",
                   "column depths not given")

    # ---------------------------------------------------------------- shear + stirrups
    zones = {("hinge" if smf else "ends"): ("I", "J"), "mid": ("M",)}
    stir, shear_out = {}, {}
    db_small = min(chosen[s][f][1] for s in STATIONS for f in ("top", "bot"))
    for zone, sts in zones.items():
        worst = None
        for s in sts:
            vu = abs(dem[s]["Vu"])
            vc_zero = False
            if seis:
                if zone == "hinge":
                    vu = max(vu, seis["Ve"]); vc_zero = seis["Vc_zero_in_hinge"]
                else:
                    ve_mid = seis["Vpr"] + seis["wu"] * max(seis["ln"] / 2.0 - 2.0 * h / 1000.0, 0.0)
                    vu = max(vu, ve_mid)
            d = d_st[s]
            sd = shear_demand(vu, fc, fyt, b, d, h, dem[s]["Nu"], lam, vc_zero)
            at_s = tor[s]["At_s"]
            smax = sd["s_max_along"]
            if tor[s]["required"]:
                smax = min(smax, tor[s]["s_max"])
            if seis:
                hl = hoop_limits(d, h, db_small, fy)
                smax = min(smax, hl["s_hinge_max"] if zone == "hinge" else hl["s_outside_max"])
            sd.update({"station": s, "At_s": at_s, "s_max_governing": smax})
            shear_out[s] = sd
            ck.add(f"shear_section_{s}", "22.5.1.2 | NSCP 422.5.1.2", "442",
                   "OK" if sd["section_ok"] else "FAIL", round(vu, 1), f"<= {sd['phiVn_max']:.1f} kN")
            if worst is None:
                worst = dict(sd)
            else:  # envelope of the zone's stations
                for k_ in ("Av_s_req", "At_s", "Av_s_min", "Vu"):
                    worst[k_] = max(worst[k_], sd[k_])
                for k_ in ("s_max_governing", "s_max_across"):
                    worst[k_] = min(worst[k_], sd[k_])
                worst["Vc_zeroed_18_6_5_2"] = worst["Vc_zeroed_18_6_5_2"] or sd["Vc_zeroed_18_6_5_2"]
        sd = worst
        s_across = sd["s_max_across"]
        legs = max(bars["n_legs"], math.ceil(geo["x0"] / s_across) + 1)
        if seis and zone == "hinge":
            legs = max(legs, math.ceil(geo["x0"] / 350.0) + 1)
        legs += legs % 2 if legs > 2 and legs % 2 else 0
        avmin = max(sd["Av_s_min"], 0.0)
        if prov:
            n_l, db_s, s_p = prov["stirrups"].get(zone) or prov["stirrups"].get("hinge") or prov["stirrups"]["ends"]
            cap = shear_capacity(fc, fyt, b, min(d_st[s] for s in sts), h, n_l, db_s, s_p,
                                 max(dem[s]["Nu"] for s in sts), lam, sd["Vc_zeroed_18_6_5_2"])
            a_leg = math.pi / 4 * db_s ** 2
            need = max(sd["Av_s_req"] + 2 * sd["At_s"], avmin)
            ok = n_l * a_leg / s_p >= need - 1e-9 and a_leg / s_p >= sd["Av_s_req"] / n_l + sd["At_s"] - 1e-9
            s_ok = s_p <= sd["s_max_governing"]
            stir[zone] = {"legs": n_l, "db": db_s, "s": s_p, "phiVn": cap, "Av_s_req_total": need,
                          "Av_s_prov": n_l * a_leg / s_p, "s_max": sd["s_max_governing"],
                          "status": "OK" if ok and s_ok else "FAIL",
                          "reason": "; ".join(x for x in (
                              "" if ok else f"Av/s {n_l * a_leg / s_p:.3f} < required {need:.3f} mm2/mm "
                                            "(or per-leg Av/(n s) + At/s short)",
                              "" if s_ok else f"s {s_p:g} > s_max {sd['s_max_governing']:.0f} mm") if x)}
        else:
            stir[zone] = pick_stirrups(sd["Av_s_req"], sd["At_s"], avmin, sd["s_max_governing"], legs,
                                       bars["stirrup_sizes"], bars["s_increment"], bars["s_min"])
        stir[zone]["closed_hoops"] = bool(seis and zone == "hinge") or any(tor[s]["required"] for s in sts)
        ck.add(f"stirrups_{zone}", "9.6.3.4 / 9.6.4.2 / 9.7.6 / 18.6.4", "151-160, 330-331",
               stir[zone]["status"], stir[zone].get("s"), f"<= {sd['s_max_governing']:.0f} mm",
               stir[zone].get("reason", ""))
    if seis:
        hl = hoop_limits(min(d_st.values()), h, db_small, fy)
        stir["hinge"].update({"zone_length": hl["hinge_length"], "first_hoop": hl["first_hoop_max"]})

    # ---------------------------------------------------------------- torsion side bars
    side = {}
    for s in STATIONS:
        s_st = stir[next(iter(zones)) if s != "M" else "mid"].get("s") or 150.0
        side[s] = side_bars(geo["y0"], al_split[s]["side_each"], s_st, bars["main_sizes"])
        if tor[s]["required"]:
            dbl = max(0.042 * s_st, 10.0)
            ck.add(f"torsion_long_bar_size_{s}", "9.7.5.2", "158",
                   "OK" if min(chosen[s]["top"][1], chosen[s]["bot"][1]) >= dbl else "FAIL",
                   min(chosen[s]["top"][1], chosen[s]["bot"][1]), f">= {dbl:.1f} mm")

    # ---------------------------------------------------------------- serviceability
    serv = {}
    sv = cfg["service"]
    serv["min_depth"] = min_depth(L, sv["support"], fy, h)
    ck.add("min_depth", "Table 9.3.1.1", "143", "OK" if serv["min_depth"]["ok"] else "WARN",
           h, f">= {serv['min_depth']['h_min']:.0f} mm", "if not met, calculated deflection governs")
    if caps:
        mb, mt = fl["M"]["bot"], fl["M"]["top"]
        wd, wl = sv.get("wD", cfg["gravity"].get("wD", 0.0)), sv.get("wL", cfg["gravity"].get("wL", 0.0))
        if wd or sv.get("Ma_DL"):
            dp = cover + dbs + chosen["M"]["top"][1] / 2.0
            serv["deflection"] = deflection(b, h, mb["d"], dp, mb["As_prov"], mt["As_prov"], fc, fy, L,
                                            sv["support"], wd, wl, sv["sustained_L"], sv["months"],
                                            sv["limit_case"], lam, sv.get("Ma_D"), sv.get("Ma_DL"),
                                            sv["ie_law"])
            dfl = serv["deflection"]
            ck.add("deflection_L", "Table 24.2.2 (l/360)", "498",
                   "OK" if dfl["ok_L_immediate"] else "FAIL", round(dfl["delta_L"], 2),
                   f"<= {dfl['limit_L_immediate']:.1f} mm")
            if dfl["limit_after_attachment"]:
                ck.add("deflection_after_attachment", f"Table 24.2.2 ({sv['limit_case']})", "498",
                       "OK" if dfl["ok_after_attachment"] else "FAIL",
                       round(dfl["delta_after_attachment"], 2), f"<= {dfl['limit_after_attachment']:.1f} mm")
        else:
            warns.append("no service loads given -- deflection not calculated")
        n_b, db_b = chosen["M"]["bot"]
        serv["crack_bottom_M"] = crack_control(b, h, cover, dbs, n_b, db_b, fy, sv.get("Ma_service_pos"),
                                               mb["d"], mt["As_prov"], None, fc, dagg)
        for e in ("I", "J"):
            n_t, db_t = chosen[e]["top"]
            serv[f"crack_top_{e}"] = crack_control(b, h, cover, dbs, n_t, db_t, fy, sv.get("Ma_service_neg"),
                                                   fl[e]["top"]["d"], fl[e]["bot"]["As_prov"], None, fc, dagg)
        for k_, v in serv.items():
            if k_.startswith("crack"):
                ck.add(k_, "Table 24.3.2 | NSCP Table 424.3.2", "503 | 4-158", "OK" if v["ok"] else "FAIL",
                       round(v["s_provided"], 1), f"<= {v['s_max']:.1f} mm", v["fs_source"])
        if h > 900:
            ck.add("skin_reinforcement", "9.7.2.3", "153", "WARN", h, "h > 900 mm",
                   "provide skin bars over h/2 from the tension face at <= Table 24.3.2 spacing")

    schedule = {s: {"top": _bars_str(chosen[s]["top"]), "bot": _bars_str(chosen[s]["bot"]),
                    "side_each_face": (f"{side[s]['n_per_face']}-D{side[s]['db']:g}"
                                       if side[s].get("db") else None)} for s in STATIONS}
    schedule["stirrups"] = {z: (f"{v['legs']}-leg D{v['db']:g} @ {v['s']:g}" if v.get("s") else v.get("status"))
                            for z, v in stir.items()}
    if seis:
        schedule["stirrups"]["hinge"] += f" over 2h = {2 * h:g} mm, first hoop <= 50 mm (closed hoops)"

    return {
        "id": cfg.get("id"), "tool": VERSION, "mode": mode, "frame": cfg["frame"], "phi_rule": rule,
        "basis": "NSCP 2015 (ACI 318M-14 beam provisions); coefficients from ACI 318-25M where equal",
        "verdict": ck.verdict(), "schedule": schedule,
        "flexure": fl, "torsion": tor, "shear": shear_out, "stirrups": stir, "seismic": seis,
        "serviceability": serv, "span": span, "checks": ck.items,
        "warnings": sorted(set(warns)),
        "not_checked": [
            "development length, hooks, lap-splice lengths and locations (Ch. 25, 18.6.3.3)",
            "bar cut-off points (9.7.3)", "joint shear (18.8.4) -- use concretedesignpy joint_shear",
            "strong-column/weak-beam (18.7.3)", "IMF/OMF-specific rules (18.4, 18.3)",
            "flanged-section flexure and T-beam Acp", "hollow-section torsion",
            "deep beams (9.9)", "fire, durability, fatigue",
        ],
    }


def _caps(chosen, b, h, cover, dbs, fc, fy, rule, dagg, dem, allow_413=True):
    caps = {}
    for s, f in chosen.items():
        (nt, dbt), (nb, dbb) = f["top"], f["bot"]
        caps[s] = {
            "top": check_face(abs(dem[s]["Mu_neg"]), b, h, cover, dbs, fc, fy, nt, dbt, nb, dbb, rule, dagg, allow_413),
            "bot": check_face(abs(dem[s]["Mu_pos"]), b, h, cover, dbs, fc, fy, nb, dbb, nt, dbt, rule, dagg, allow_413),
        }
    return caps


def _bars_str(nd):
    n, db = nd
    return f"{n}-D{db:g}" if n else "NONE FOUND"


def summary(res):
    lines = [f"{res['id']}  [{res['frame']}, {res['mode']}]  VERDICT: {res['verdict']}"]
    for s in STATIONS:
        sc = res["schedule"][s]
        lines.append(f"  {s}: top {sc['top']:<9} bot {sc['bot']:<9}" + (f" sides {sc['side_each_face']}" if sc["side_each_face"] else ""))
    for z, v in res["schedule"]["stirrups"].items():
        lines.append(f"  stirrups {z}: {v}")
    if res.get("seismic"):
        se = res["seismic"]
        lines.append(f"  Mpr- I/J {se['Mpr_neg_I']:.1f}/{se['Mpr_neg_J']:.1f}  Mpr+ I/J {se['Mpr_pos_I']:.1f}/{se['Mpr_pos_J']:.1f} kN.m"
                     f"  ln {se['ln']:.3f} m  Vpr {se['Vpr']:.1f}  Ve {se['Ve']:.1f} kN  Vc=0: {se['Vc_zero_in_hinge']}")
    bad = [c for c in res["checks"] if c["status"] in ("FAIL", "WARN")]
    for c in bad:
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
    if not args:
        print(__doc__); return 2
    data = json.load(open(args[0]))
    cases = data["cases"] if "cases" in data else [data]
    out = [rnd(design_one(c), 3) for c in cases]
    result = out[0] if len(out) == 1 else {"cases": out, "verdicts": {r["id"]: r["verdict"] for r in out}}
    if "--out" in argv:
        path = argv[argv.index("--out") + 1]
        json.dump(result, open(path, "w"), indent=2, default=str)
    else:
        print(json.dumps(result, indent=2, default=str))
    if "--summary" in argv:
        print("\n\n".join(summary(r) for r in out), file=sys.stderr)
    return 1 if any(r["verdict"] == "FAIL" for r in out) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
