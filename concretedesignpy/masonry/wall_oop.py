# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""Reinforced CHB wall, out of plane — NSCP 2015 §708.2.4 (SD) or §707.2 (ASD).

Every clause value comes from the Mind vault (package apec-provisions: ``nscp2015.masonry`` and friends).
This module only assembles them. Units: mm, N, MPa inside; kPa and kN/m at the edges (names say so).
Results are per reinforcing-bar strip of width s (the bar spacing) and per metre of wall.
"""

import math

from nscp2015 import combos
from nscp2015 import masonry as mas
from asce41_17 import masonry as a41

from concretedesignpy.clause import clause

BASIS_OOP = ["NSCP2015-701", "NSCP2015-706.2", "NSCP2015-706.3", "NSCP2015-706.1.12"]


# ---------------------------------------------------------------- result helpers (shared by the subpackage)
def chk(cid, label, demand, limit, clause_id, units="", tex=""):
    """One check: demand ≤ limit. ratio = demand/limit."""
    ratio = demand / limit if limit else math.inf
    return {"id": cid, "label": label, "demand": demand, "limit": limit, "ratio": ratio,
            "ok": ratio <= 1.0 + 1e-9, "units": units, "clause": clause_id, "tex": tex}


def flag(cid, label, ok, clause_id, tex=""):
    """A pass/fail rule with no ratio (e.g. a material restriction)."""
    return {"id": cid, "label": label, "demand": None, "limit": None, "ratio": None, "ok": bool(ok),
            "units": "", "clause": clause_id, "tex": tex}


def not_checked(cid, label, reason, clause_id):
    return {"id": cid, "label": label, "status": "not_checked", "reason": reason, "ok": None, "clause": clause_id,
            "demand": None, "limit": None, "ratio": None, "units": "", "tex": ""}


def summarize(checks):
    ran = [c for c in checks if c.get("ok") is not None]
    ratios = [c["ratio"] for c in ran if c.get("ratio") is not None]
    return {"ok": all(c["ok"] for c in ran), "complete": all(c.get("ok") is not None for c in checks),
            "governing_ratio": max(ratios) if ratios else None,
            "not_checked": [c["id"] for c in checks if c.get("ok") is None]}


def require(params, *names):
    """No favourable defaults: these keys must be present and not None."""
    missing = [n for n in names if params.get(n) is None]
    if missing:
        raise KeyError("required input(s) missing: " + ", ".join(missing))


def material_rules(zone, mortar, grout, special_inspection, method):
    """Zone/material restrictions that hold for any masonry design."""
    if zone not in (2, 4):
        raise ValueError("zone must be 2 or 4 (NSCP 2015 Fig. 208-1)")
    if grout not in ("solid", "partial", "ungrouted"):
        raise ValueError("grout must be 'solid', 'partial' or 'ungrouted'")
    if mortar not in ("M", "S", "N", "O"):
        raise ValueError("mortar must be M, S, N or O")
    if not isinstance(special_inspection, bool):
        raise TypeError("special_inspection must be true or false")
    out = [flag("mortar_zone2", "No Type O mortar in the load-resisting system (Zone 2/4)", mortar != "O",
                "NSCP2015-706.1.12", r"\text{mortar} = " + mortar + r" \neq O")]
    if zone == 4:
        out.append(flag("mortar_zone4", "No Type N mortar in the load-resisting system (Zone 4)", mortar != "N",
                        "NSCP2015-706.1.12", r"\text{mortar} = " + mortar + r" \neq N"))
    if method == "SD":
        out.append(flag("sd_special_inspection", "Strength design needs special inspection", special_inspection,
                        "NSCP2015-708.1"))
    return out


# ---------------------------------------------------------------- section per bar strip
def strip_section(t, s, grout, face_shell):
    """Area, I, S, r of a strip of width s. Solid grout: full t. Partial/ungrouted: face shells only
    (grouted cells ignored — conservative for stresses and deflection)."""
    if grout == "solid":
        A, I = s * t, s * t ** 3 / 12.0
    else:
        if not face_shell:
            raise KeyError("face_shell_mm is required for partially grouted or ungrouted CHB")
        A = 2.0 * face_shell * s
        I = s * (t ** 3 - (t - 2.0 * face_shell) ** 3) / 12.0
    return {"A": A, "I": I, "S": I / (t / 2.0), "r": math.sqrt(I / A)}


# ---------------------------------------------------------------- existing-wall mode (Gap #176)
@clause("NSCP2015-705.3", "ASCE41-17-11.2")
def existing_fm_and_kappa(existing):
    """f'm of an existing wall from §705.3.5 cut prisms or Table 705-1, and κ from ASCE 41-17 §11.2.4 / Table 6-1
    (analogy — ASCE 41 is written for buildings). Returns (fm, kappa or None, notes, checks)."""
    src = existing.get("fm_source")
    checks, notes = [], []
    if src == "cut_prisms":
        mean, ok = mas.cut_prism_ok(existing["prism_set_strengths_MPa"], existing["fm_specified_MPa"],
                                    bool(existing.get("corrected_by_standard_21_17")))
        fm = mean
        checks.append(flag("fm_cut_prisms", "§705.3.5 cut-prism mean ≥ specified f'm", ok, "NSCP2015-705.3",
                           rf"\bar f_{{prism}} = {mean:.2f} \ge f'_m = {existing['fm_specified_MPa']:.2f}\ \text{{MPa}}"))
    elif src == "unit_strength":
        fm = mas.fm_from_unit_strength(existing["unit"], existing["unit_strength_MPa"], existing["mortar"])
        notes.append("f'm from Table 705-1 (unit strength method)")
    else:
        raise ValueError("existing.fm_source must be 'cut_prisms' or 'unit_strength'")
    checks.append(flag("fm_min", "Actual f'm ≥ 4 MPa", mas.fm_actual_min_ok(fm), "NSCP2015-705.3",
                       rf"f'_m = {fm:.2f} \ge 4\ \text{{MPa}}"))
    k = existing.get("kappa")
    if k:
        kappa = a41.knowledge_factor_masonry(k["table_6_1"], k["damaged_untested"], k["cov_over_25pct"],
                                             k["archaic_uncertain"])
        notes.append("κ per ASCE 41-17 §11.2.4 / Table 6-1 applied to capacities — ANALOGY: ASCE 41 covers buildings")
    else:
        kappa = None
        checks.append(not_checked("kappa", "Knowledge factor κ",
                                  "no κ inputs given (ASCE 41-17 §11.2.4 + Table 6-1); capacities not reduced",
                                  "ASCE41-17-11.2"))
    return fm, kappa, notes, checks


# ---------------------------------------------------------------- main calculator
@clause("NSCP2015-708.2.4", "NSCP2015-708.1", "NSCP2015-707.2", "NSCP2015-707.1", "NSCP2015-706.2",
        "NSCP2015-706.3", "NSCP2015-203.3", "NSCP2015-203.4")
def wall_out_of_plane(p):
    """Reinforced CHB wall under out-of-plane load. p (dict):
    required: method 'SD'|'ASD', support 'simple'|'cantilever', h_mm, t_nom_mm, t_spec_mm, grout, fm_MPa (unless
      existing), fy_MPa, mortar, special_inspection, zone, bar_db_mm, bar_s_mm, wall_kPa;
    lateral (at least one): wind_kPa (W, strength level), seismic_kPa (E horizontal, strength level; needs Ca, Ip);
    optional: P_top_kN_per_m (dead), e_mm, d_mm (default t_spec/2, centred bar), face_shell_mm, bond, existing."""
    require(p, "method", "support", "h_mm", "t_nom_mm", "t_spec_mm", "grout", "fy_MPa", "mortar",
            "special_inspection", "zone", "bar_db_mm", "bar_s_mm", "wall_kPa")
    method, support = p["method"], p["support"]
    if method not in ("SD", "ASD") or support not in ("simple", "cantilever"):
        raise ValueError("method must be SD|ASD and support simple|cantilever")
    W = float(p.get("wind_kPa") or 0.0)
    Eh = float(p.get("seismic_kPa") or 0.0)
    if W <= 0 and Eh <= 0:
        raise ValueError("give wind_kPa and/or seismic_kPa (out-of-plane load)")
    if Eh > 0:
        require(p, "Ca", "Ip")
    grout, zone, mortar, si = p["grout"], int(p["zone"]), p["mortar"], p["special_inspection"]
    checks = material_rules(zone, mortar, grout, si, method)
    notes, basis = [], list(BASIS_OOP)

    kappa = None
    if p.get("existing"):
        fm, kappa, n2, c2 = existing_fm_and_kappa(p["existing"])
        notes += n2
        checks += c2
        basis += ["NSCP2015-705.3", "ASCE41-17-11.2", "ASCE41-17-6.2.4"]
    else:
        require(p, "fm_MPa")
        fm = float(p["fm_MPa"])
    kap = kappa if kappa is not None else 1.0

    h, t, tn = float(p["h_mm"]), float(p["t_spec_mm"]), float(p["t_nom_mm"])
    s, db, fy = float(p["bar_s_mm"]), float(p["bar_db_mm"]), float(p["fy_MPa"])
    if grout == "ungrouted":
        raise ValueError("a reinforced wall needs grouted bar cells: use grout 'partial' or 'solid'")
    d = float(p.get("d_mm") or t / 2.0)
    As = math.pi * db ** 2 / 4.0
    b = mas.effective_width(tn, s, p.get("bond", "running"))
    sec = strip_section(t, s, grout, p.get("face_shell_mm"))
    Em = mas.Em(fm)
    n = mas.ES_MASONRY / Em
    span_w = s / 1000.0                                   # m of wall per strip
    wD_strip = float(p["wall_kPa"]) * span_w             # kN/m of height per strip
    Ptop = float(p.get("P_top_kN_per_m") or 0.0) * span_w  # kN per strip
    e = float(p.get("e_mm") or 0.0)
    # weight above the critical section: mid-height (simple) or base (cantilever)
    hw = h / 2.0 if support == "simple" else h
    Pwall = wD_strip * hw / 1000.0                        # kN
    Ev_coef = 0.5 * float(p["Ca"]) * float(p["Ip"]) if Eh > 0 else 0.0

    inter = {"fm_MPa": fm, "Em_MPa": Em, "n": n, "As_mm2": As, "b_eff_mm": b, "d_mm": d, "strip_mm": s,
             "A_strip_mm2": sec["A"], "I_strip_mm4": sec["I"], "S_strip_mm3": sec["S"], "r_mm": sec["r"],
             "rho": As / (b * d), "kappa": kappa}
    if support == "simple":
        h_eff = mas.effective_height(h, True)
    else:
        h_eff = mas.effective_height(h, False)
    inter["h_eff_mm"] = h_eff
    L_lever = h  # span (simple) or cantilever height

    per_combo = []
    if method == "SD":
        basis += ["NSCP2015-708.1", "NSCP2015-708.2", "NSCP2015-708.2.4", "NSCP2015-203.3"]
        checks.append(flag("t_min_sd", "§708.2.4.4: wall thickness ≥ 150 mm (nominal)", tn >= 150.0,
                           "NSCP2015-708.2.4", rf"t = {tn:.0f} \ge 150\ \text{{mm}}"))
        checks.append(flag("db_max_sd", "Bar ≤ 28 mm", db <= 28.0, "NSCP2015-708.2"))
        # ρ ≤ 0.5 ρb, P from 1.0D (§708.2.3.3)
        P_bal = (Pwall + Ptop) * 1000.0
        rho_b = mas.rho_balanced(fm, fy, b, d, P_bal)
        inter["rho_b"] = rho_b
        checks.append(chk("rho_max", "ρ ≤ 0.5ρb", As / (b * d), 0.5 * rho_b, "NSCP2015-708.2.4", "",
                          rf"\rho = \frac{{A_s}}{{bd}} = {As / (b * d):.5f} \le 0.5\rho_b = {0.5 * rho_b:.5f}"))
        for cid, f in combos.strength():
            fW, fE = f.get("W", 0.0), f.get("E", 0.0)
            if (fW and W > 0) or (fE and Eh > 0):
                fD = f.get("D", 0.0)
                if fE:
                    fD = fD + Ev_coef if fD > 1.0 else fD - Ev_coef     # Ev = 0.5CaID, critical sign (§208)
                wu = (fW * W + fE * Eh) * span_w                         # kN/m per strip = N/mm
                per_combo.append((cid, fD, wu))
        worst = None
        for cid, fD, wu in per_combo:
            Puw, Puf = fD * Pwall * 1000.0, fD * Ptop * 1000.0
            r = _sd_case(support, wu, h, Puw, Puf, e, As, fy, fm, b, d, sec, grout, kap)
            r["combo"], r["D_factor"], r["wu_N_per_mm"] = cid, fD, wu
            if worst is None or r.get("ratio", 0) > worst.get("ratio", 0):
                worst = r
        inter["sd_governing"] = worst
        if worst.get("not_checked"):
            checks.append(not_checked("flexure_sd", "Out-of-plane flexure (SD)", worst["not_checked"],
                                      "NSCP2015-708.2.4"))
        else:
            ktex = r"\kappa" if kappa else ""
            mu_txt = (r"M_u = \frac{w_u h^2}{8} + P_u\Delta_u" if support == "simple"
                      else r"M_u = \frac{w_u H^2}{2} + P_u\Delta_{top}")
            checks.append(chk("flexure_sd", f"Mu ≤ φMn ({worst['combo']})", worst["Mu"] / 1e6,
                              worst["phiMn"] / 1e6, "NSCP2015-708.2.4", "kN·m/strip",
                              mu_txt + rf" = {worst['Mu'] / 1e6:.3f} \le {ktex}\phi A_{{se}} f_y"
                              rf"(d - a/2) = {worst['phiMn'] / 1e6:.3f}\ \text{{kN·m}}"))
            Vu = worst["wu_N_per_mm"] * (h / 2.0 if support == "simple" else h)
            phiVn = kap * mas.PHI_SD["wall_oop_shear"] * mas.Vn_oop(sec["A"], fm)
            checks.append(chk("shear_sd", "Vu ≤ φVn (Eq. 708-26, φ 0.60)", Vu / 1e3, phiVn / 1e3,
                              "NSCP2015-708.2.4", "kN/strip",
                              rf"V_u = {Vu / 1e3:.2f} \le \phi\,0.166 A_{{mv}}\sqrt{{f'_m}} = {phiVn / 1e3:.2f}\ \text{{kN}}"))
            notes.append("Out-of-plane wall shear: Eq. 708-26 and φ = 0.60 applied to Pu ≤ 0.04f'mAg walls "
                         "(no shear equation is printed for that case — vault note flag)")
        if support == "simple":
            checks.append(_service_deflection(W, Eh, span_w, h, Pwall, Ptop, fm, sec, grout, As, fy, b, d, n))
        else:
            checks.append(not_checked("deflection", "Δs ≤ 0.007h", "Eq. 708-27 to 708-29 are for simple supports; "
                                      "cantilever deflection limit not printed", "NSCP2015-708.2.4"))
    else:
        basis += ["NSCP2015-707.1", "NSCP2015-707.2", "NSCP2015-203.4"]
        notes.append("ASD with the §203.4.1 basic combinations, no one-third increase (vault note NSCP2015-707.1)")
        checks.append(flag("db_max_asd", "Bar ≤ 32 mm", db <= 32.0, "NSCP2015-707.2"))
        if h_eff / t > 30.0:
            checks.append(not_checked("slenderness_asd", "h'/t ≤ 30 for the simple ASD stress check",
                                      f"h'/t = {h_eff / t:.1f} > 30: §707.2.14.2 needs a second-order analysis",
                                      "NSCP2015-707.2"))
        k, j = mas.kj_from_np(n, As / (b * d))
        inter.update({"k": k, "j": j})
        Fb = kap * mas.Fb(fm, si)
        Fa = kap * mas.Fa(fm, h_eff, sec["r"], si)
        Fs = mas.Fs(fy, "deformed")
        Fv = kap * mas.Fv_flexural(fm, False, si)
        inter.update({"Fa_MPa": Fa, "Fb_MPa": Fb, "Fs_MPa": Fs, "Fv_MPa": Fv,
                      "asd_factor": mas.asd_masonry_factor(si)})
        worst = None
        for cid, f in combos.asd_basic():
            fW, fE = f.get("W", 0.0), f.get("E", 0.0)
            if not ((fW and W > 0) or (fE and Eh > 0)):
                continue
            w = (fW * W + fE * Eh) * span_w                      # N/mm
            M = w * L_lever ** 2 / (8.0 if support == "simple" else 2.0)
            V = w * (L_lever / 2.0 if support == "simple" else L_lever)
            P = f.get("D", 1.0) * (Pwall + Ptop) * 1000.0
            fa = P / sec["A"]
            fb = mas.fb_flexure(M, b, d, k, j)
            fs = mas.fs_flexure(M, As, j, d)
            fv = mas.fv_stress(V, b, j, d)
            u = mas.unity(fa, Fa, fb, Fb)
            r = {"combo": cid, "w_N_per_mm": w, "M": M, "V": V, "P": P, "fa": fa, "fb": fb, "fs": fs, "fv": fv,
                 "unity": u, "ratio": max(u, fs / Fs, fv / Fv)}
            if worst is None or r["ratio"] > worst["ratio"]:
                worst = r
        inter["asd_governing"] = worst
        g = worst
        mtxt = r"\frac{wh^2}{8}" if support == "simple" else r"\frac{wH^2}{2}"
        checks.append(chk("unity_asd", f"fa/Fa + fb/Fb ≤ 1 ({g['combo']})", g["unity"], 1.0, "NSCP2015-707.2", "",
                          rf"M = {mtxt} = {g['M'] / 1e6:.3f}\ \text{{kN·m}};\ \frac{{f_a}}{{F_a}} + \frac{{f_b}}{{F_b}}"
                          rf" = \frac{{{g['fa']:.3f}}}{{{Fa:.3f}}} + \frac{{{g['fb']:.3f}}}{{{Fb:.3f}}} = {g['unity']:.3f} \le 1"))
        checks.append(chk("fs_asd", "fs ≤ Fs", g["fs"], Fs, "NSCP2015-707.2", "MPa",
                          rf"f_s = \frac{{M}}{{A_s j d}} = {g['fs']:.1f} \le F_s = {Fs:.1f}\ \text{{MPa}}"))
        checks.append(chk("fv_asd", "fv ≤ Fv (no shear steel)", g["fv"], Fv, "NSCP2015-707.2", "MPa",
                          rf"f_v = \frac{{V}}{{bjd}} = {g['fv']:.3f} \le F_v = {Fv:.3f}\ \text{{MPa}}"))
    s_ = summarize(checks)
    return {"calculator": "wall_out_of_plane", "method": method, "support": support, "inputs": p,
            "intermediate": inter, "checks": checks, "notes": notes, "basis": sorted(set(basis)), **s_}


def _sd_case(support, wu, h, Puw, Puf, e, As, fy, fm, b, d, sec, grout, kap):
    """One factored combination, SD. Returns Mu, phiMn, ratio (N, mm)."""
    if not mas.axial_stress_ratio_ok(Puw, Puf, sec["A"], fm):
        return {"not_checked": "(Pw+Pf)/Ag > 0.04f'm: §708.2.4.5 walls are outside this calculator", "ratio": 0}
    if support == "simple":
        r = mas.slender_wall_oop(wu, h, Puw, Puf, e, As, fy, fm, b, d, sec["I"], sec["S"], grout)
        r["phiMn"] *= kap
        r["ratio"] = r["Mu"] / r["phiMn"]
        return r
    # Cantilever (fence): §708.2.4.3 → mechanics. Δtop = wu H⁴/(8 Em I); I = Ig if M ≤ Mcr else Icr.
    # shortcut: P-Δ = Pu × Δtop (whole weight at the tip lever — conservative), one pass; refine for slender stems.
    Pu = Puw + Puf
    Em = mas.Em(fm)
    n = mas.ES_MASONRY / Em
    Mcr = mas.Mcr(sec["S"], mas.fr(fm, grout))
    M1 = wu * h * h / 2.0
    Icr = mas.Icr_rect(b, d, n, mas.Ase(As, fy, Pu))
    I = sec["I"] if M1 <= Mcr else Icr
    dtop = wu * h ** 4 / (8.0 * Em * I)
    Mu = M1 + Pu * dtop
    Mn = mas.Mn_oop(As, fy, Pu, d, fm, b)
    phiMn = kap * mas.PHI_SD["wall_oop_flexure"] * Mn
    return {"Pu": Pu, "Mu": Mu, "Mn": Mn, "phiMn": phiMn, "delta_u": dtop, "Mcr": Mcr, "Icr": Icr,
            "ratio": Mu / phiMn, "ok": Mu <= phiMn}


def _service_deflection(W, Eh, span_w, h, Pwall, Ptop, fm, sec, grout, As, fy, b, d, n):
    """Eq. 708-27 to 708-29 at service level, with P-Δ. Service lateral = 0.6W or E/1.4 (the §203.4 ASD factors,
    since NSCP W and E are strength-level — flagged)."""
    ws = max(0.6 * W, Eh / 1.4) * span_w
    P = (Pwall + Ptop) * 1000.0
    Em = mas.Em(fm)
    Mcr = mas.Mcr(sec["S"], mas.fr(fm, grout))
    Icr = mas.Icr_rect(b, d, n, mas.Ase(As, fy, 0.0))
    dl = 0.0
    for _ in range(100):
        Ms = ws * h * h / 8.0 + P * dl
        dn = mas.deflection_service(Ms, Mcr, h, Em, sec["I"], Icr)
        if abs(dn - dl) < 1e-6:
            break
        dl = dn
    lim = mas.deflection_limit_oop(h)
    return chk("deflection", "Δs ≤ 0.007h (service, P-Δ)", dl, lim, "NSCP2015-708.2.4", "mm",
               rf"\Delta_s = {dl:.2f} \le 0.007h = {lim:.1f}\ \text{{mm}}")
