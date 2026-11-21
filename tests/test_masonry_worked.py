"""Worked examples written out by hand (inputs, steps, answer) and reproduced by the calculators.
Clause basis: vault notes NSCP2015-204-T204-2, -208.9, -710, -709, -207D.3/207D.4, -708.2.4, -304, -206.6."""
import math

import pytest

from concretedesignpy.masonry import fence, partition


def test_worked_partition_interior_100chb():
    """JB Tower-type interior partition: 100 mm CHB (t = 90 mm specified), 16.5 kN/m³ units, ungrouted, plastered both
    faces, h = 3.0 m, no stiffeners, floor at hx = 20 m of hr = 40 m, Zone 4, Ca = 0.44, Ip = 1.0.
    1. Table 204-2: 1.05 + 2 × 0.24 = 1.53 kPa.
    2. Table 208-13 partitions ap = 1.0, Rp = 3.0. Eq. 208-28: (1.0 × 0.44 × 1.0/3.0)(1 + 3 × 20/40) × 1.53
       = 0.146667 × 2.5 × 1.53 = 0.5610 kPa; ≥ 0.7CaIpWp = 0.4712; ≤ 4CaIpWp = 2.693 → Fp = 0.561 kPa.
    3. §710.4 Table 710-4 interior nonbearing: h/t = 3000/100 = 30 ≤ 36 → OK; empirical design holds.
    4. §709.4.1.3: one 12 mm bar at ≤ 1.2 m (vertical, within 400 mm of ends) or horizontal 12 mm at ≤ 1.2 m /
       1 × MW11 at ≤ 400 mm (t ≤ 100 mm); isolate from the frame (§709.4.1.2). No stiffeners required by §710.4."""
    r = partition(dict(h_mm=3000, l_mm=None, t_nom_mm=100, t_spec_mm=90, unit_density_kN_m3=16.5,
                       grout_spacing="none", plastered_faces=2, location="interior", fm_MPa=6.9, fy_MPa=275,
                       mortar="S", special_inspection=False, zone=4, Ca=0.44, Ip=1.0, hx_m=20, hr_m=40,
                       face_shell_mm=22))
    i = r["intermediate"]
    assert i["wall_kPa"] == pytest.approx(1.53)
    assert i["Fp_kPa"] == pytest.approx(0.5610, rel=1e-4)
    emp = next(c for c in r["checks"] if c["id"] == "empirical_710")
    assert emp["ratio"] == pytest.approx(30 / 36) and emp["ok"]
    assert r["design"]["vertical"] == {"bar_db_mm": 12.0, "spacing_mm": 1200.0,
                                       "basis": "§709.4.1.3 minimum, within 400 mm of wall ends"}
    assert r["design"]["horizontal"]["or_joint_reinforcement"].startswith("1 × MW11")
    assert r["design"]["stiffener_spacing_mm"] is None
    assert r["ok"]


def test_worked_partition_exterior_needs_stiffeners():
    """Same wall as exterior skin: Table 710-4 exterior nonbearing 18 → 3000/100 = 30 > 18; no 100 mm reinforced
    option passes (h'/t = 3000/90 = 33 > 30), so stiffeners at ≤ 18 × 100 = 1800 mm."""
    r = partition(dict(h_mm=3000, l_mm=None, t_nom_mm=100, t_spec_mm=90, unit_density_kN_m3=16.5,
                       grout_spacing="none", plastered_faces=2, location="exterior", wind_kPa=1.2, fm_MPa=6.9,
                       fy_MPa=275, mortar="S", special_inspection=False, zone=4, Ca=0.44, Ip=1.0, hx_m=20, hr_m=40,
                       face_shell_mm=22))
    assert r["design"]["stiffener_spacing_mm"] == pytest.approx(1800.0)
    assert not r["ok"]


def test_worked_fence_2400():
    """Forbes-Park-type fence, H = 2.4 m, L = 30 m, 200 mm CHB (t = 190), 16.5 kN/m³, fully grouted, plastered both
    faces, f'm = 10 MPa, fy = 275 MPa, 12 mm @ 400 centred (d = 95), special inspection, SD, Zone 4, Ca = 0.44,
    V = 258.4 km/h, Exposure B, Kzt = 1.0, body of wall (Case A).
    1. Table 103-1: H > 1.5 m → Occ. V → Ip = 1.0. Table 204-2: 3.59 + 2 × 0.24 = 4.07 kPa.
    2. Wind §207D: Kz(2.4 m, B) = 0.572; Kd = 0.85; V = 258.4/3.6 = 71.778 m/s;
       qh = 0.613 × 0.572 × 1.0 × 0.85 × 71.778² = 1535.5 N/m²; G = 0.85; s/h = 1, B/s = 12.5 → Cf(A) = 1.30;
       p = 1.5355 × 0.85 × 1.30 = 1.6967 kPa (> 0.77 minimum).
    3. Seismic: Table 208-13 fences ap 1.0, Rp 3.0, hx = 0 → Eq. 208-28 = 0.44/3 × 4.07 = 0.597 < 0.7 × 0.44 × 4.07
       = 1.2536 kPa → Fp = 1.2536 kPa (wind governs).
    4. Stem per 400 mm strip, combo 203-6 (0.9D + 1.0W): wu = 1.6967 × 0.4 = 0.6787 N/mm;
       Pu = 0.9 × 4.07 × 0.4 × 2.4 = 3.5165 kN. M1 = 0.6787 × 2400²/2 = 1.9547 kN·m.
       S = 400 × 190²/6 = 2.4067e6; fr = 0.33√10 = 1.0436 → Mcr = 2.5115 kN·m > M1 → Ig = 400 × 190³/12 = 2.2863e8.
       Δtop = 0.6787 × 2400⁴/(8 × 7500 × 2.2863e8) = 1.641 mm; Mu = 1.9547 + 3.5165 × 1.641e-3 = 1.9604 kN·m.
       Ase = 113.10 + 3516.5/275 = 125.88 mm²; a = (3516.5 + 113.10 × 275)/(0.85 × 10 × 400) = 10.18 mm;
       Mn = 125.88 × 275 × (95 − 5.09) = 3.1125 kN·m; φMn = 0.8 × 3.1125 = 2.4900 kN·m; ratio 0.787.
    5. Footing B = 1.2 m, D = 0.3 m, Df = 0.9 m, Table 304-1 class 4, γc = 23.6:
       Wwall = 4.07 × (2.4 + 0.9 − 0.3) = 12.21 kN/m; Wftg = 23.6 × 1.2 × 0.3 = 8.496; P = 20.706 kN/m.
       D + 0.6W: H = 0.6 × 1.6967 × 2.4 = 2.443 kN/m; MOT = 2.443 × (1.2 + 0.9) = 5.131; MR = 20.706 × 0.6 = 12.424
       → FS_OT = 2.42 ≥ 1.5. Sliding 0.25 × 20.706 = 5.177 → FS = 2.12 ≥ 1.5.
       e = 5.131/20.706 = 0.248 > B/6 = 0.2 → qmax = 2 × 20.706/(3 × (0.6 − 0.248)) = 39.2 kPa ≤ qa = 75 × 2.0 = 150."""
    r = fence(dict(H_mm=2400, L_m=30, t_nom_mm=200, t_spec_mm=190, unit_density_kN_m3=16.5, grout="solid",
                   plastered_faces=2, fm_MPa=10, fy_MPa=275, mortar="S", special_inspection=True, zone=4, Ca=0.44,
                   V_kph=258.4, exposure="B", Kzt=1.0, wind_zone="body", method="SD", bar_db_mm=12, bar_s_mm=400,
                   footing=dict(B_mm=1200, D_mm=300, Df_mm=900, soil_class=4, gamma_c_kN_m3=23.6)))
    i = r["intermediate"]
    assert i["occupancy"] == "V" and i["Ip"] == 1.0 and i["wall_kPa"] == pytest.approx(4.07)
    qh = 0.613 * 0.572 * 1.0 * 0.85 * (258.4 / 3.6) ** 2 / 1000
    assert i["wind"]["qh_kPa"] == pytest.approx(qh, rel=1e-6)
    assert i["wind"]["p_design_kPa"] == pytest.approx(qh * 0.85 * 1.30, rel=1e-6)
    assert i["seismic"]["Fp_kPa"] == pytest.approx(0.7 * 0.44 * 4.07)
    g = r["stem"]["sd_governing"]
    assert g["combo"] == "203-6"
    assert g["Mu"] / 1e6 == pytest.approx(1.9604, rel=1e-3)
    assert g["phiMn"] / 1e6 == pytest.approx(2.4900, rel=1e-3)
    assert next(c for c in r["checks"] if c["id"] == "flexure_sd")["ratio"] == pytest.approx(0.787, abs=1e-3)
    f = r["footing"]["governing"]
    assert f["FS_overturning"] == pytest.approx(2.42, abs=0.01) and f["FS_sliding"] == pytest.approx(2.12, abs=0.01)
    assert r["footing"]["qmax_kPa"] == pytest.approx(39.2, abs=0.1) and r["footing"]["qa_kPa"] == 150.0
    assert r["ok"] and not r["complete"]          # cantilever deflection limit is not printed → not_checked
