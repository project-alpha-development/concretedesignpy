# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""Freestanding CHB wall / fence cantilevered from its footing — Gap #177, Forbes Park.

Wind: NSCP 2015 §207D.3–207D.4 solid freestanding wall (vault ``nscp2015.wind_other``), Case A/B and the
Case C end zone. Seismic: §208.9 Eq. 208-28, Table 208-13 "masonry or concrete fences over 1.8 m".
Stem: unreinforced (empirical §710.4 only — the §707.3 allowables are on the missing p.7-31) or reinforced
(``wall_out_of_plane`` with support='cantilever'). Footing: Table 304-1 bearing and sliding, FS 1.5 (§206.6
via §104.3.1), on the §203.4.1 basic ASD combinations.
"""

from nscp2015 import elements, foundations, loads, seismic, wind, wind_other
from nscp2015 import combos
from nscp2015 import masonry as mas

from concretedesignpy.clause import clause
from concretedesignpy.masonry.wall_oop import (chk, flag, material_rules, not_checked, require, summarize,
                                               wall_out_of_plane)


@clause("NSCP2015-207D.3", "NSCP2015-207D.4", "NSCP2015-207D.4-F1", "NSCP2015-207A.6")
def fence_wind(H_m, L_m, V_kph, exposure, Kzt, zone):
    """Design wind pressure on a solid freestanding wall at grade (s = h). zone 'body' → Case A/B;
    'end' → the larger of Case A and Case C over 0 to s from a free end. Returns dict (kPa)."""
    if zone not in ("body", "end"):
        raise ValueError("wind_zone must be 'body' (Case A/B) or 'end' (Case C, first s from a free end)")
    s_over_h, B_over_s = 1.0, L_m / H_m
    Kz = wind_other.Kz_207D(H_m, exposure)
    Kd = wind.Kd("solid_wall_or_sign")
    qh = wind_other.qz_207D(Kz, Kzt, Kd, wind.kph_to_mps(V_kph))          # N/m²
    G = wind.G_RIGID_DEFAULT
    CfA = wind_other.Cf_sign_AB(s_over_h, B_over_s)
    CfC = None
    if B_over_s >= 2:
        # Case C, first region (0 to s from the free end). Only printed B/s columns are coded: take the larger of
        # the bracketing columns (conservative); vault applies note 4 (s/h > 0.8).
        cols = sorted(wind_other.CF_SIGN_C)
        lo = max([c for c in cols if c <= B_over_s], default=cols[0])
        hi = min([c for c in cols if c >= B_over_s], default=cols[-1])
        CfC = max(wind_other.Cf_sign_C(lo, "0-1", s_over_h), wind_other.Cf_sign_C(hi, "0-1", s_over_h))
    pA = qh * G * CfA / 1000.0
    pC = qh * G * CfC / 1000.0 if CfC else None
    pmin = wind_other.minimum_force_other(1.0) / 1000.0
    return {"Kz": Kz, "Kzt": Kzt, "Kd": Kd, "qh_kPa": qh / 1000.0, "G": G, "B_over_s": B_over_s,
            "Cf_caseA": CfA, "Cf_caseC_end": CfC, "p_caseA_kPa": pA, "p_caseC_end_kPa": pC, "p_min_kPa": pmin,
            "zone": zone, "p_design_kPa": max(pA, (pC or 0.0) if zone == "end" else 0.0, pmin)}


@clause("NSCP2015-208.9", "NSCP2015-103-T103-1", "NSCP2015-208.4.2")
def fence_seismic(H_m, wall_kPa, Ca, Ip):
    """Fp per unit wall area (kPa) for a fence at grade: hx = 0, hr = H → (1 + 3hx/hr) = 1."""
    ap, Rp = elements.TABLE_208_13["masonry_concrete_fences_over_1_8m"]
    Fp, d = elements.Fp(Ca, Ip, wall_kPa, ap, Rp, 0.0, H_m, detail=True)
    return {"ap": ap, "Rp": Rp, "Fp_kPa": Fp, "detail": d}


@clause("NSCP2015-304", "NSCP2015-206.6", "NSCP2015-203.4")
def fence_footing(H_m, wall_kPa, p_wind_kPa, Fp_kPa, ftg):
    """Strip footing, per metre: B_mm (width), D_mm (thickness), Df_mm (depth to underside), soil_class (Table 304-1),
    gamma_c_kN_m3; wall centred on the footing. Overturning and sliding FS ≥ 1.5, bearing ≤ qa, on D + 0.6W and
    D + E/1.4 (§203.4.1 basic set). Soil over the footing and passive resistance are ignored (conservative)."""
    B, D, Df = ftg["B_mm"] / 1000.0, ftg["D_mm"] / 1000.0, ftg["Df_mm"] / 1000.0
    cls, gc = int(ftg["soil_class"]), float(ftg["gamma_c_kN_m3"])
    Wwall = wall_kPa * (H_m + Df - D)            # stem weight per m (stem continues below grade to the footing)
    Wftg = gc * B * D
    P = Wwall + Wftg
    qa = foundations.allowable_bearing(cls, ftg["B_mm"], ftg["Df_mm"], wind_or_seismic=False)
    out, worst = [], None
    for cid, f in combos.asd_basic():
        fW, fE = f.get("W", 0.0), f.get("E", 0.0)
        if not (fW or fE):
            continue
        q = fW * p_wind_kPa + fE * Fp_kPa                       # kPa on the exposed face
        Hlat = q * H_m
        MOT = Hlat * (H_m / 2.0 + Df)                           # about the footing underside
        MR = P * B / 2.0
        try:
            fs_s_R = foundations.sliding_resistance(cls, P, contact_area_m2=B)
        except NotImplementedError:                     # rock classes 1–2: no Table 304-1 sliding value
            fs_s_R = None
        fs_s, fs_o, _ = loads.retaining_wall_checks(Hlat, fs_s_R if fs_s_R is not None else 0.0, MOT, MR)
        fs_s = fs_s if fs_s_R is not None else None
        e = MOT / P
        qmax = P / B * (1 + 6 * e / B) if e <= B / 6 else 2 * P / (3 * (B / 2 - e)) if e < B / 2 else None
        r = {"combo": cid, "H_kN": Hlat, "MOT_kNm": MOT, "MR_kNm": MR, "P_kN": P, "R_slide_kN": fs_s_R,
             "FS_sliding": fs_s, "FS_overturning": fs_o, "e_m": e, "qmax_kPa": qmax}
        out.append(r)
        if worst is None or min(fs_s or fs_o, fs_o) < min(worst["FS_sliding"] or worst["FS_overturning"],
                                                          worst["FS_overturning"]):
            worst = r
    return {"qa_kPa": qa, "W_wall_kN": Wwall, "W_footing_kN": Wftg, "cases": out, "governing": worst,
            "qmax_kPa": None if any(c["qmax_kPa"] is None for c in out) else max(c["qmax_kPa"] for c in out)}


@clause("NSCP2015-710", "NSCP2015-707.3", "NSCP2015-708.2.4", "NSCP2015-707.2", "NSCP2015-204-T204-2")
def fence(p):
    """p: H_mm (above grade), L_m (length between returns/ends), t_nom_mm, t_spec_mm, unit_density_kN_m3,
    grout ('solid'|'partial'|'ungrouted'), plastered_faces, fm_MPa (unless existing), fy_MPa, mortar,
    special_inspection, zone, Ca, V_kph, exposure, Kzt, wind_zone 'body'|'end', method 'SD'|'ASD';
    reinforced: bar_db_mm, bar_s_mm (omit both for unreinforced); optional Ip (default from Table 103-1 / 208-1),
    face_shell_mm, footing {B_mm, D_mm, Df_mm, soil_class, gamma_c_kN_m3}, existing."""
    require(p, "H_mm", "L_m", "t_nom_mm", "t_spec_mm", "unit_density_kN_m3", "grout", "plastered_faces", "fy_MPa",
            "mortar", "special_inspection", "zone", "Ca", "V_kph", "exposure", "Kzt", "wind_zone", "method")
    H_m, tn = float(p["H_mm"]) / 1000.0, float(p["t_nom_mm"])
    grout = p["grout"]
    reinforced = p.get("bar_db_mm") is not None and p.get("bar_s_mm") is not None
    checks, notes = [], []
    occ = mas.fence_occupancy(H_m)
    Ip = float(p["Ip"]) if p.get("Ip") is not None else seismic.IMPORTANCE[occ][1]
    if grout == "solid":
        gkey = "full"
    elif grout == "ungrouted":
        gkey = "none"
    else:
        gkey = p.get("bar_s_mm") if p.get("bar_s_mm") in (400, 600, 800) else 800   # 800 row when wider (heavier)
    w = mas.chb_wall_weight(p["unit_density_kN_m3"], gkey, tn, int(p["plastered_faces"]))
    wd = fence_wind(H_m, float(p["L_m"]), float(p["V_kph"]), p["exposure"], float(p["Kzt"]), p["wind_zone"])
    eq = fence_seismic(H_m, w, float(p["Ca"]), Ip)
    if H_m <= 1.8:
        notes.append("Table 208-13 names fences over 1.8 m; the same ap = 1.0, Rp = 3.0 used (hub reading)")
    notes.append("wind_zone 'body' = Case A/B; 'end' = Case C over the first s from a free end or gate "
                 "(run both for a full check)")
    inter = {"occupancy": occ, "Ip": Ip, "wall_kPa": w, "wind": wd, "seismic": eq}

    stem = None
    if not reinforced or grout == "ungrouted":
        ratio = mas.cantilever_ht_max(hollow=True)
        checks += material_rules(int(p["zone"]), p["mortar"], grout, p["special_inspection"], p["method"])
        checks.append(chk("empirical_cantilever", "§710.4 cantilever h/t ≤ 4 (hollow units)", H_m * 1000 / tn, ratio,
                          "NSCP2015-710", "",
                          rf"\frac{{h}}{{t}} = \frac{{{H_m * 1000:.0f}}}{{{tn:.0f}}} = {H_m * 1000 / tn:.1f} \le 4"))
        checks.append(not_checked("unreinforced_stress", "Unreinforced stem flexural tension and shear",
                                  "NSCP 2015 §707.3.1–707.3.8 allowables are on printed p.7-31, missing from the hub "
                                  "scan (Gap List)", "NSCP2015-707.3"))
    else:
        q = dict(method=p["method"], support="cantilever", h_mm=p["H_mm"], t_nom_mm=tn, t_spec_mm=p["t_spec_mm"],
                 grout=grout, fm_MPa=p.get("fm_MPa"), fy_MPa=p["fy_MPa"], mortar=p["mortar"],
                 special_inspection=p["special_inspection"], zone=p["zone"], bar_db_mm=p["bar_db_mm"],
                 bar_s_mm=p["bar_s_mm"], wall_kPa=w, wind_kPa=wd["p_design_kPa"], seismic_kPa=eq["Fp_kPa"],
                 Ca=p["Ca"], Ip=Ip, face_shell_mm=p.get("face_shell_mm"), existing=p.get("existing"))
        stem = wall_out_of_plane(q)
        checks += stem["checks"]
        notes += stem["notes"]

    ftg = None
    if p.get("footing"):
        ftg = fence_footing(H_m, w, wd["p_design_kPa"], eq["Fp_kPa"], p["footing"])
        g = ftg["governing"]
        checks.append(chk("overturning", f"FS overturning ≥ 1.5 ({g['combo']})", 1.5, g["FS_overturning"],
                          "NSCP2015-206.6", "",
                          rf"FS_{{OT}} = \frac{{M_R}}{{M_{{OT}}}} = \frac{{{g['MR_kNm']:.2f}}}{{{g['MOT_kNm']:.2f}}}"
                          rf" = {g['FS_overturning']:.2f} \ge 1.5"))
        if g["FS_sliding"] is None:
            checks.append(not_checked("sliding", "FS sliding ≥ 1.5", "Table 304-1 gives no sliding value for rock "
                                      "classes 1–2", "NSCP2015-304"))
        else:
            checks.append(chk("sliding", f"FS sliding ≥ 1.5 ({g['combo']})", 1.5, g["FS_sliding"], "NSCP2015-304", "",
                              rf"FS_s = \frac{{R}}{{H}} = \frac{{{g['R_slide_kN']:.2f}}}{{{g['H_kN']:.2f}}}"
                              rf" = {g['FS_sliding']:.2f} \ge 1.5"))
        if ftg["qmax_kPa"] is None:
            checks.append(flag("bearing", "Resultant within the footing (e < B/2)", False, "NSCP2015-304",
                               r"e \ge B/2"))
        else:
            checks.append(chk("bearing", "qmax ≤ qa (Table 304-1)", ftg["qmax_kPa"], ftg["qa_kPa"], "NSCP2015-304",
                              "kPa", rf"q_{{max}} = {ftg['qmax_kPa']:.1f} \le q_a = {ftg['qa_kPa']:.1f}\ \text{{kPa}}"))
        notes.append("FS 1.5 from §206.6 applied to the fence via §104.3.1; retained soil across the wall is not "
                     "modelled (a grade difference makes it a retaining wall)")
    else:
        checks.append(not_checked("footing", "Footing overturning / sliding / bearing", "no footing data given",
                                  "NSCP2015-304"))
    s_ = summarize(checks)
    return {"calculator": "fence", "inputs": p, "intermediate": inter, "stem": stem and stem["intermediate"],
            "footing": ftg, "checks": checks, "notes": notes,
            "basis": sorted({"NSCP2015-103-T103-1", "NSCP2015-204-T204-2", "NSCP2015-207D.3", "NSCP2015-207D.4",
                             "NSCP2015-207D.4-F1", "NSCP2015-208.9", "NSCP2015-710", "NSCP2015-707.3",
                             "NSCP2015-304", "NSCP2015-206.6"} | set(stem["basis"] if stem else [])), **s_}
