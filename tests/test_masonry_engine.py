"""Engine tests: masonry calculators against the vault clause functions (no re-derivation here)."""
import math

import pytest

from nscp2015 import masonry as mas
from concretedesignpy.masonry import wall_out_of_plane, wall_in_plane, partition, fence, build_report

BASE = dict(fy_MPa=275, mortar="S", zone=4)


def _oop(**k):
    p = dict(method="SD", support="simple", h_mm=3000, t_nom_mm=150, t_spec_mm=140, grout="solid", fm_MPa=10,
             special_inspection=True, bar_db_mm=12, bar_s_mm=1000, wall_kPa=2.63, wind_kPa=1.0, **BASE)
    p.update(k)
    return wall_out_of_plane(p)


def test_oop_sd_matches_vault_slender_wall():
    """Strip = 1000 mm, b_eff = min(6×150, 1000) = 900; the vault slender_wall_oop with the same inputs must agree."""
    r = _oop()
    g = r["intermediate"]["sd_governing"]
    As = math.pi * 36
    v = mas.slender_wall_oop(g["wu_N_per_mm"], 3000, g["D_factor"] * 2.63 * 1.5 * 1000, 0, 0, As, 275, 10, 900, 70,
                             1000 * 140 ** 3 / 12, 1000 * 140 ** 2 / 6, "solid")
    assert r["ok"]
    assert g["Mu"] == pytest.approx(v["Mu"], rel=1e-9)
    assert g["phiMn"] == pytest.approx(v["phiMn"], rel=1e-9)


def test_no_favourable_defaults():
    for k in ("fm_MPa", "mortar", "grout", "special_inspection", "zone"):
        p = dict(method="SD", support="simple", h_mm=3000, t_nom_mm=150, t_spec_mm=140, grout="solid", fm_MPa=10,
                 special_inspection=True, bar_db_mm=12, bar_s_mm=600, wall_kPa=2.63, wind_kPa=1.0, **BASE)
        p.pop(k)
        with pytest.raises(KeyError):
            wall_out_of_plane(p)


def test_sd_without_special_inspection_fails_rule():
    r = _oop(special_inspection=False)
    assert not next(c for c in r["checks"] if c["id"] == "sd_special_inspection")["ok"]
    assert not r["ok"]


def test_asd_half_stress_without_inspection():
    a = _oop(method="ASD", special_inspection=True)["intermediate"]
    b = _oop(method="ASD", special_inspection=False)["intermediate"]
    assert b["Fb_MPa"] == pytest.approx(0.5 * a["Fb_MPa"])
    assert b["Fs_MPa"] == a["Fs_MPa"]                      # steel not halved


def test_zone4_type_n_mortar_flagged():
    r = _oop(mortar="N")
    assert not next(c for c in r["checks"] if c["id"] == "mortar_zone4")["ok"]


def test_inplane_shear_is_vs_only():
    p = dict(Lw_mm=4000, h_mm=3000, t_nom_mm=200, t_spec_mm=190, grout="solid", fm_MPa=13.8, special_inspection=True,
             Pu_kN=200, Mu_kNm=600, Vu_kN=180, vert_db_mm=16, vert_s_mm=600, horiz_db_mm=12, horiz_s_mm=400, **BASE)
    r = wall_in_plane(p)
    sh = next(c for c in r["checks"] if c["id"] == "shear")
    Vs = mas.Vs_inplane(190 * 4000, (math.pi * 36) / (190 * 400), 275)
    assert sh["limit"] == pytest.approx(0.6 * Vs / 1e3)
    assert next(c for c in r["checks"] if c["id"] == "vn_max")["ok"] is None
    assert not r["complete"]


def test_unreinforced_fence_stress_not_checked():
    p = dict(H_mm=1200, L_m=20, t_nom_mm=150, t_spec_mm=140, unit_density_kN_m3=16.5, grout="ungrouted",
             plastered_faces=2, fy_MPa=275, mortar="S", special_inspection=False, zone=4, Ca=0.44, V_kph=258.4,
             exposure="B", Kzt=1.0, wind_zone="body", method="ASD", fm_MPa=6.9)
    r = fence(p)
    nc = next(c for c in r["checks"] if c["id"] == "unreinforced_stress")
    assert nc["ok"] is None and "7-31" in nc["reason"]
    emp = next(c for c in r["checks"] if c["id"] == "empirical_cantilever")
    assert emp["ratio"] == pytest.approx((1200 / 150) / 4) and not emp["ok"]


def test_existing_mode_kappa_only_with_inputs():
    ex = {"fm_source": "cut_prisms", "prism_set_strengths_MPa": [9.5, 10.5, 11.0], "fm_specified_MPa": 10.0,
          "corrected_by_standard_21_17": True}
    r = _oop(fm_MPa=None, existing=ex)
    assert next(c for c in r["checks"] if c["id"] == "kappa")["ok"] is None          # no κ invented
    ex["kappa"] = {"table_6_1": 0.9, "damaged_untested": True, "cov_over_25pct": False, "archaic_uncertain": False}
    r2 = _oop(fm_MPa=None, existing=ex)
    assert r2["intermediate"]["kappa"] == 0.75
    g1, g2 = r["intermediate"]["sd_governing"], r2["intermediate"]["sd_governing"]
    assert g2["phiMn"] == pytest.approx(0.75 * g1["phiMn"])
    ex2 = {"fm_source": "unit_strength", "unit": "concrete", "unit_strength_MPa": 5.0, "mortar": "S"}
    with pytest.raises(NotImplementedError):                                          # below Table 705-1
        _oop(fm_MPa=None, existing=ex2)


def test_report_one_line_per_check():
    r = _oop()
    rep = build_report(r)
    assert len(rep["lines"]) == len(r["checks"]) and rep["status"].startswith("OK")


def test_fence_footing_on_rock_does_not_crash():
    from concretedesignpy.masonry.fence import fence_footing
    r = fence_footing(2.4, 4.07, 1.7, 1.25, dict(B_mm=900, D_mm=300, Df_mm=600, soil_class=2, gamma_c_kN_m3=23.6))
    assert r["governing"]["FS_sliding"] is None and r["qa_kPa"] > 0
