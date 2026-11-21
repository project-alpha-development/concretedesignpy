# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""Reinforced CHB shear wall, in plane — NSCP 2015 §708.2.5 (SD).

Vn = Vs only (Amv ρn fy): Vm needs Cd from "Table 708-2", which NSCP 2015 does not print, so Vm = 0
(conservative; it is also the §708.2.5.5 item 3 form near the base). The Table 708-1 Vn cap is not_checked
(units inconsistent as printed). Mn by strain compatibility (εmu 0.003, 0.85f'm over a = 0.85c, bars
elastic-perfectly plastic, compression steel ignored).
"""

import math

from nscp2015 import masonry as mas

from concretedesignpy.clause import clause
from concretedesignpy.masonry.wall_oop import chk, flag, material_rules, not_checked, require, summarize


def _bars(Lw, s):
    """Bar positions from the compression edge: first and last 100 mm from the ends, ≤ s apart (§709.4.2.3)."""
    n = max(2, math.ceil((Lw - 200.0) / s) + 1)
    return [100.0 + i * (Lw - 200.0) / (n - 1) for i in range(n)]


def _Mn(Lw, t_c, fm, fy, Ab, xs, Pu):
    """Strain compatibility: find c with C − T = Pu; Mn about Lw/2 (N·mm). t_c = compression width."""
    Es, emu = mas.ES_MASONRY, mas.EMU

    def forces(c):
        a = min(mas.stress_block_a(c), Lw)
        C = 0.85 * fm * a * t_c
        T, MT = 0.0, 0.0
        for x in xs:
            eps = emu * (x - c) / c                                    # + tension
            f = max(min(Es * eps, fy), -fy)
            if f > 0:                                                  # compression steel ignored
                T += f * Ab
                MT += f * Ab * (x - Lw / 2.0)
        return C, T, MT, a

    lo, hi = 1e-3, Lw / 0.85
    for _ in range(200):
        c = 0.5 * (lo + hi)
        C, T, _, _ = forces(c)
        if C - T > Pu:
            hi = c
        else:
            lo = c
    C, T, MT, a = forces(c)
    return C * (Lw / 2.0 - a / 2.0) + MT, c


@clause("NSCP2015-708.2.5", "NSCP2015-708.1", "NSCP2015-708.2", "NSCP2015-706.1.12", "NSCP2015-708.2.4")
def wall_in_plane(p):
    """p: Lw_mm, h_mm, t_nom_mm, t_spec_mm, grout ('solid'|'partial'), fm_MPa, fy_MPa, mortar, special_inspection,
    zone, Pu_kN, Mu_kNm, Vu_kN, vert_db_mm, vert_s_mm, horiz_db_mm, horiz_s_mm; face_shell_mm if partial."""
    require(p, "Lw_mm", "h_mm", "t_nom_mm", "t_spec_mm", "grout", "fm_MPa", "fy_MPa", "mortar", "special_inspection",
            "zone", "Pu_kN", "Mu_kNm", "Vu_kN", "vert_db_mm", "vert_s_mm", "horiz_db_mm", "horiz_s_mm")
    Lw, t, tn = float(p["Lw_mm"]), float(p["t_spec_mm"]), float(p["t_nom_mm"])
    fm, fy, grout, zone = float(p["fm_MPa"]), float(p["fy_MPa"]), p["grout"], int(p["zone"])
    if grout == "ungrouted":
        raise ValueError("reinforced shear wall needs grout 'solid' or 'partial'")
    Pu, Mu, Vu = float(p["Pu_kN"]) * 1e3, float(p["Mu_kNm"]) * 1e6, float(p["Vu_kN"]) * 1e3
    checks = material_rules(zone, p["mortar"], grout, p["special_inspection"], "SD")
    checks.append(flag("fm_range", "10 ≤ f'm ≤ 28 MPa", mas.fm_inplane_range_ok(fm), "NSCP2015-708.2.5",
                       rf"10 \le f'_m = {fm:.1f} \le 28"))
    checks.append(flag("fy_max", "fy ≤ 420 MPa", mas.fy_sd_ok(fy), "NSCP2015-708.2"))
    fs_ = float(p.get("face_shell_mm") or 0.0)
    if grout == "partial" and not fs_:
        raise KeyError("face_shell_mm is required for a partially grouted wall")
    t_c = t if grout == "solid" else 2.0 * fs_         # shear area / compression width (face shells, conservative)
    Amv = t_c * Lw
    Ag = t * Lw
    Av = math.pi * float(p["vert_db_mm"]) ** 2 / 4.0
    Ah = math.pi * float(p["horiz_db_mm"]) ** 2 / 4.0
    sv, sh = float(p["vert_s_mm"]), float(p["horiz_s_mm"])
    rho_v, rho_h = Av / (t * sv), Ah / (t * sh)
    inter = {"Amv_mm2": Amv, "Ag_mm2": Ag, "rho_v": rho_v, "rho_h": rho_h}

    # minimum steel
    if zone == 4:
        z = mas.zone4_wall_reinforcement_ok(rho_v, rho_h, sv, sh, min(float(p["vert_db_mm"]), float(p["horiz_db_mm"])))
        checks.append(flag("min_steel_z4", "Zone 4: ρv+ρh ≥ 0.002, each ≥ 0.001, s ≤ 1.2 m, db ≥ 10", z["ok"],
                           "NSCP2015-706.1.12",
                           rf"\rho_v + \rho_h = {rho_v:.5f} + {rho_h:.5f} = {rho_v + rho_h:.5f} \ge 0.002"))
    else:
        zr = mas.zone_min_reinforcement(2)
        checks.append(flag("min_steel_z2", "Zone 2: bars ≥ 130 mm², vertical ≤ 1.2 m, horizontal ≤ 3.0 m",
                           Av >= 130 and Ah >= 130 and sv <= zr["vertical_spacing_max_mm"]
                           and sh <= zr["horizontal_spacing_max_mm"], "NSCP2015-706.1.12"))
    checks.append(flag("v_vs_h", "Vertical steel ≥ ½ horizontal", mas.vertical_to_horizontal_ok(rho_v, rho_h),
                       "NSCP2015-708.2.5", rf"\rho_v = {rho_v:.5f} \ge 0.5\rho_h = {0.5 * rho_h:.5f}"))
    smax = mas.horizontal_spacing_base_max(tn)
    checks.append(chk("h_spacing_base", "Horizontal spacing in base region ≤ min(3t, 600)", sh, smax,
                      "NSCP2015-708.2.5", "mm", rf"s_h = {sh:.0f} \le {smax:.0f}\ \text{{mm}}"))

    # axial
    phi_ax = mas.PHI_SD["wall_inplane_axial"]
    Po = mas.Po_inplane(fm, Ag if grout == "solid" else Amv, Av * len(_bars(Lw, sv)), fy)
    checks.append(chk("axial", "Pu ≤ 0.80φPo (φ 0.65)", Pu / 1e3, 0.80 * phi_ax * Po / 1e3, "NSCP2015-708.2.5", "kN",
                      rf"P_u = {Pu / 1e3:.1f} \le 0.80\phi P_o = {0.80 * phi_ax * Po / 1e3:.1f}\ \text{{kN}}"))

    # flexure
    xs = _bars(Lw, sv)
    Mn, c = _Mn(Lw, t_c, fm, fy, Av, xs, Pu)
    Pb = mas.Pb_inplane(fm, t_c, Lw - 100.0, fy)
    phi_f = mas.phi_inplane_axial(Pu, fm, Amv, Pb, True, fy)
    inter.update({"bars": len(xs), "c_mm": c, "Mn_kNm": Mn / 1e6, "phi_flexure": phi_f, "Pb_kN": Pb / 1e3})
    checks.append(chk("flexure", "Mu ≤ φMn", Mu / 1e6, phi_f * Mn / 1e6, "NSCP2015-708.2.5", "kN·m",
                      rf"M_u = {Mu / 1e6:.1f} \le \phi M_n = {phi_f:.3f} \times {Mn / 1e6:.1f} = {phi_f * Mn / 1e6:.1f}"
                      r"\ \text{kN·m}"))
    fr = mas.fr(fm, grout)
    Mcr = mas.Mcr(t * Lw ** 2 / 6.0, fr)
    k = mas.Mn_to_Mcr_min(grout)
    checks.append(chk("mn_mcr", f"Mn ≥ {k}Mcr", k * Mcr / 1e6, Mn / 1e6, "NSCP2015-708.2.5", "kN·m",
                      rf"{k}M_{{cr}} = {k}\,S f_r = {k * Mcr / 1e6:.1f} \le M_n = {Mn / 1e6:.1f}\ \text{{kN·m}}"))

    # shear
    rho_n = Ah / (t_c * sh)
    Vn = mas.Vs_inplane(Amv, rho_n, fy)
    phi_v = mas.PHI_SD["wall_inplane_shear"]
    inter.update({"rho_n": rho_n, "Vn_kN": Vn / 1e3})
    checks.append(chk("shear", "Vu ≤ φVn, Vn = Amv ρn fy (Vm = 0)", Vu / 1e3, phi_v * Vn / 1e3, "NSCP2015-708.2.5",
                      "kN", rf"V_u = {Vu / 1e3:.1f} \le \phi A_{{mv}}\rho_n f_y = {phi_v * Vn / 1e3:.1f}\ \text{{kN}}"))
    checks.append(not_checked("vn_max", "Vn ≤ Table 708-1 maximum", "Table 708-1 prints mixed units; Cd "
                              "(Table 708-2) not printed — vault Gap List", "NSCP2015-708.2"))
    checks.append(not_checked("boundary", "Boundary members (strain > 0.0015 at Rw = 1.5)",
                              "needs the Rw = 1.5 strain analysis — not in this calculator", "NSCP2015-708.2.5"))
    s_ = summarize(checks)
    return {"calculator": "wall_in_plane", "inputs": p, "intermediate": inter, "checks": checks,
            "notes": ["Vm = 0: Cd is not printed in NSCP 2015 Ch.7",
                      "Compression width/shear area: face shells only for partial grout (conservative)",
                      "φ for flexure from §708.1.4.3.1 with φPn taken as Pu"],
            "basis": ["NSCP2015-701", "NSCP2015-706.1.12", "NSCP2015-708.1", "NSCP2015-708.2", "NSCP2015-708.2.4",
                      "NSCP2015-708.2.5"], **s_}
