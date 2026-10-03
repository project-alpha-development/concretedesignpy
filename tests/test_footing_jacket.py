"""Footing jacketing - verification against a published example and statics.

Three independent references, none of which is the module's own output:

1. PUBLISHED EXAMPLE (the no-jacket limit). With no wings and no overlay
   the check must reduce to an ordinary isolated footing. The benchmark is
   Structural Mind vault, Design Procedures note 04, "Shear & Flexure
   Design of Spread Footings", worked example (computed there by
   dp_foundation.py, clauses read from ACI 318-25M):

       B x L x h = 2.0 x 3.0 x 0.60 m, column 400 x 400, 8-D20 long bars,
       cover 75 mm, f'c = 28 MPa, fy = 420 MPa, Pu = 1250 kN, Mu = 210 kN*m

       q_nu = 208.3 kPa
       one-way shear, long direction:  Vu = 408.2 kN at d = 515 mm,
                                       phi Vc = 694.9 kN (13.2.6.2(a))
       two-way shear:  bo = 3620 mm, d = 505 mm, Vu = 1079.4 kN,
                       vu = 0.5904 MPa, row (a) 1.7462 MPa, phi vc = 1.3096 MPa
       flexure, long:  Mu = 436.2 kN*m, phi Mn = 478.7 kN*m, As,min = 2160 mm^2
       flexure, short: Mu = 200.0 kN*m, d = 495 mm, As,min = 3240 mm^2

2. HAND CALCULATION of a jacketed footing (WORKED below). The numbers in
   the test were worked by hand from the formulas in the clause register,
   and are written out in the docstring of TestWorkedExample.

3. STATICS. The closed-form strip resultants are compared with a numerical
   integration of the two-stage pressure field over the footing plan.
"""

import math

import pytest

from concretedesignpy.calculators.footing_jacket import (
    NOT_CHECKED,
    _strip,
    footing_jacket_check,
)

PUBLISHED = dict(
    B0=2000, L0=3000, h0=600, fc0=28, fy0=420,
    n0_L=8, db0_L=20, n0_B=11, db0_B=20, cover0=75,
    cB=400, cL=400,
    eB=0, eL=0, t_top=0, fcj=28, fyj=420,
    nj_L=0, dbj_L=0, nj_B=0, dbj_B=0, cover_j=75,
    surface="roughened",
    nd_L=0, ndt_L=0, nd_B=0, ndt_B=0, db_dowel=16, fy_dowel=420, z_dowel=100,
    db_tie=0, s_tie=0, fy_tie=420,
    P=900, ML=150, MB=0, qa=250,
    Pu=1250, MuL=210, MuB=0,
    P0=0, M0L=0, M0B=0, shored=True,
)

WORKED = dict(
    B0=2000, L0=3000, h0=600, fc0=21, fy0=275,
    n0_L=8, db0_L=20, n0_B=15, db0_B=20, cover0=75,
    cB=400, cL=400,
    eB=600, eL=600, t_top=200, fcj=28, fyj=415,
    nj_L=8, dbj_L=20, nj_B=10, dbj_B=20, cover_j=75,
    surface="roughened",
    nd_L=14, ndt_L=7, nd_B=20, ndt_B=10, db_dowel=20, fy_dowel=415, z_dowel=100,
    db_tie=12, s_tie=300, fy_tie=415,
    P=1500, ML=180, MB=60, qa=200,
    Pu=2000, MuL=260, MuB=90,
    P0=700, M0L=0, M0B=0, shored=False,
    column_engaged=True,
)


def run(base=WORKED, **overrides):
    return footing_jacket_check(**{**base, **overrides})


# ------------------------------------------------------ 1. published example


@pytest.fixture(scope="module")
def published():
    return run(PUBLISHED)


@pytest.fixture(scope="module")
def worked():
    return run()


class TestPublishedExampleNoJacket:
    @pytest.fixture
    def r(self, published):
        return published

    def test_factored_pressure(self, r):
        assert r["qu1"] == pytest.approx(208.3, abs=0.05)

    def test_one_way_shear(self, r):
        assert r["d_L"] == pytest.approx(515.0)
        assert r["Vu_L"] == pytest.approx(408.2, abs=0.05)
        assert r["phiVc_L"] == pytest.approx(694.9, abs=0.05)

    def test_two_way_shear(self, r):
        assert r["bo"] == pytest.approx(3620.0)
        assert r["d_p"] == pytest.approx(505.0)
        assert r["Vu_p"] == pytest.approx(1079.4, abs=0.05)
        assert r["v_uv"] == pytest.approx(0.5904, abs=5e-5)
        assert r["vc_a"] == pytest.approx(1.7462, abs=5e-5)
        assert r["v_c"] == r["vc_a"]
        assert r["phi_vc"] == pytest.approx(1.3096, abs=5e-5)

    def test_flexure_long_direction(self, r):
        assert r["Mu_L"] == pytest.approx(436.2, abs=0.05)
        assert r["phiMn_L"] == pytest.approx(478.7, abs=0.05)
        assert r["As_min_L"] == pytest.approx(2160.0)
        assert r["phi_f_L"] == pytest.approx(0.90)

    def test_flexure_short_direction(self, r):
        assert r["Mu_B"] == pytest.approx(200.0, abs=0.05)
        assert r["d_B"] == pytest.approx(495.0)
        assert r["As_min_B"] == pytest.approx(3240.0)

    def test_table_22_6_5_2_is_the_2025_form(self, r):
        """Rows (b) and (c) of ACI 318-25M read (0.17 + 0.33/beta) and
        (0.17 + 0.083 alpha_s d/bo), not the 0.17(1 + 2/beta) of earlier
        editions. Note 04 lists (c)/lambda_s = 2.7264/0.8138 = 3.3502."""
        root = math.sqrt(28)
        assert r["vc_b"] == pytest.approx(0.50 * root)
        assert r["vc_c"] == pytest.approx(3.3502, abs=2e-4)

    def test_no_jacket_makes_the_jacket_checks_not_applicable(self, r):
        for key in ("wflex_ok_L", "wshear_ok_L", "if_ok_L", "ov_ok_L",
                    "wflex_ok_B", "wshear_ok_B", "if_ok_B", "ov_ok_B"):
            assert r[key] is True
        assert r["Mu_w_L"] == 0 and r["Vuh_L"] == 0
        assert r["overall_pass"] is True


# ------------------------------------------------------ 2. hand calculation


class TestWorkedExample:
    """Existing 2.0 x 3.0 x 0.60 m footing (f'c 21, fy 275) under a 400 mm
    column, enlarged by 600 mm on every side with a 200 mm overlay
    (f'c 28, fy 415). Unshored, 700 kN on the footing at casting.

    Geometry   B = 3200, L = 4200, h = 800, A0 = 6.00 m^2, A = 13.44 m^2
    Service    P = 1500, ML = 180, MB = 60; increment 800 kN
        q0 = 700/6.00 = 116.67 kPa         q1 = 800/13.44 = 59.52 kPa
        old corner: 6(180)(3.0)/(3.2 x 4.2^3) = 13.67
                    6(60)(2.0)/(4.2 x 3.2^3)  =  5.23
        q_old,max = 116.67 + 59.52 + 13.67 + 5.23 = 195.09 kPa
        wing corner: 6(180)/(3.2 x 4.2^2) + 6(60)/(4.2 x 3.2^2) = 27.50
        q_wing,max = 59.52 + 27.50 = 87.03 kPa
    Factored   Pu = 2000, MuL = 260, MuB = 90; increment 1300 kN
      L direction, column face: a0 = 1.3 m, a = 1.9 m
        Mu = 700(1.3^2)/(2 x 3.0) + 1300(1.9^2)/(2 x 4.2)
             + 260(1.9^2)(2 x 4.2 + 0.4)/4.2^3
           = 197.17 + 558.69 + 111.49 = 867.3 kN*m
        T = 2513(275) + 2513(415) = 1734.1 kN, a = 30.36 mm, d = 715
        phi Mn = 0.9(1734.1)(0.715 - 0.01518) = 1092.2 kN*m
      one-way shear at d = 0.715 m
        Vu = 700(0.585)/3.0 + 1300(1.185)/4.2
             + 6(260)(1.185)(2.1 + 0.915)/4.2^3
           = 136.50 + 366.79 + 75.23 = 578.5 kN
        phi Vc = 0.75(0.17)sqrt(21)(3200)(715) = 1336.8 kN
      B direction, column face: a0 = 0.8 m, a = 1.4 m
        Mu = 700(0.8^2)/(2 x 2.0) + 1300(1.4^2)/(2 x 3.2)
             + 90(1.4^2)(2 x 3.2 + 0.4)/3.2^3 = 112.0 + 398.1 + 36.6 = 546.7
      two-way shear, d = 705: b1 = b2 = 1105, bo = 4420, Ac = 1.2210 m^2
        Vu = 2000 - 700(1.2210)/6.00 - 1300(1.2210)/13.44 = 1739.4 kN
        vuv = 1739.4e3/(4420 x 705) = 0.5582 MPa
        gamma_v = 0.4, Jc = 6.987e11 mm^4
        + 0.4(260e6)(552.5)/6.987e11 = 0.0822
        + 0.4(90e6)(552.5)/6.987e11  = 0.0285     vu = 0.6689 MPa
        phi vc = 0.75(0.33)sqrt(21) = 1.1342 MPa
      end wing (e = 0.6 m, root at 1.5 m from the centre)
        Vu = 1300(0.6)/4.2 + 6(260)(0.6)(2.1 + 1.5)/4.2^3 = 231.2 kN
        Mu = 1300(0.6^2)/(2 x 4.2) + 260(0.6^2)(2.4 + 9.0)/4.2^3 = 70.1 kN*m
        shear friction: 14-D20 = 4398.2 mm^2, mu = 1.0, fy = 415
        phi Vn = 0.75(4398.2)(415) = 1368.9 kN (cap 0.2(21)(2000)(600) = 5040 kN)
        steel across the old face: 7-D20 dowels + 8-D20 = 4712.4 mm^2
        >= 0.0018(3200)(800) = 4608 mm^2
      minimum steel at the column, Eq. (8.6.1.2)
        lambda_s = sqrt(2/(1 + 705/250)) = 0.7236
        trigger = 0.75(0.17)sqrt(21)(0.7236) = 0.4228 MPa < vuv = 0.5582: applies
        b_slab = 400 + 3(800) = 2800 mm
        As fy needed = 5(0.5582)(2800)(4420)/(0.75 x 40) = 1151.4 kN
        bars parallel to L in 2800: 2513.3(275) + 2513.3(415)(800/1200) = 1386.5 kN
        bars parallel to B in 2800: 15-D20, 4712.4(275)(2800/3000) = 1209.5 kN
      overlay, L direction, at the column face
        Vuh = 700(1.3)/3.0 + [1300(1.9)/4.2 + 6(260)(1.9)(2.3)/4.2^3](2.0/3.2)
            = 303.33 + (588.10 + 92.02)(0.625) = 728.4 kN
        rho_v = 113.1/300^2 = 0.001257 >= 0.35/415 = 0.000843
        vnh = 1.8 + 0.6(0.001257)(415) = 2.113 MPa
        phi Vnh = 0.75(2.113)(2000)(715) = 2266 kN
    """

    @pytest.fixture
    def r(self, worked):
        return worked

    def test_bearing(self, r):
        assert r["q0"] == pytest.approx(116.67, abs=0.01)
        assert r["q1"] == pytest.approx(59.52, abs=0.01)
        assert r["q_old_max"] == pytest.approx(195.09, abs=0.02)
        assert r["q_wing_max"] == pytest.approx(87.03, abs=0.02)
        assert r["q_max"] == r["q_old_max"]
        assert r["bearing_ok"] and r["contact_ok"] and r["contact_u_ok"]

    def test_flexure_at_the_column_face(self, r):
        assert r["Mu_L"] == pytest.approx(867.3, abs=0.1)
        assert r["phiMn_L"] == pytest.approx(1092.2, abs=0.1)
        assert r["Mu_B"] == pytest.approx(546.7, abs=0.1)
        assert r["flex_ok_L"] and r["flex_ok_B"]

    def test_one_way_shear(self, r):
        assert r["Vu_L"] == pytest.approx(578.5, abs=0.1)
        assert r["phiVc_L"] == pytest.approx(1336.8, abs=0.1)

    def test_two_way_shear(self, r):
        assert r["bo"] == pytest.approx(4420.0)
        assert r["Vu_p"] == pytest.approx(1739.4, abs=0.1)
        assert r["v_uv"] == pytest.approx(0.5582, abs=1e-4)
        assert r["gamma_v_L"] == pytest.approx(0.4)
        assert r["v_uM_L"] == pytest.approx(0.0822, abs=1e-4)
        assert r["v_uM_B"] == pytest.approx(0.0285, abs=1e-4)
        assert r["v_u"] == pytest.approx(0.6689, abs=1e-4)
        assert r["phi_vc"] == pytest.approx(1.1342, abs=1e-4)

    def test_wing_and_interface(self, r):
        assert r["Vu_w_L"] == pytest.approx(231.2, abs=0.1)
        assert r["Mu_w_L"] == pytest.approx(70.1, abs=0.1)
        assert r["Avf_L"] == pytest.approx(4398.2, abs=0.1)
        assert r["phiVn_if_L"] == pytest.approx(1368.9, abs=0.1)
        assert r["Vn_cap_L"] == pytest.approx(5040.0)
        assert r["As_w_L"] == pytest.approx(4712.4, abs=0.1)
        assert r["wAs_min_ok_L"] and r["wAs_min_ok_B"]

    def test_minimum_steel_at_the_column(self, r):
        assert r["lam_s"] == pytest.approx(0.7236, abs=1e-4)
        assert r["v_trigger"] == pytest.approx(0.4228, abs=1e-4)
        assert r["as2_applies"] is True
        assert r["bslab_L"] == 2800 and r["bslab_B"] == 2800
        assert r["T_slab_min_L"] == pytest.approx(1151.4, abs=0.1)
        assert r["T_slab_L"] == pytest.approx(1386.5, abs=0.1)
        assert r["T_slab_B"] == pytest.approx(1209.5, abs=0.1)
        assert r["as2_ok_L"] and r["as2_ok_B"]

    def test_overlay_horizontal_shear(self, r):
        assert r["Vuh_L"] == pytest.approx(728.4, abs=0.1)
        assert r["rho_v"] == pytest.approx(0.001257, abs=1e-6)
        assert r["rho_v_min"] == pytest.approx(0.000843, abs=1e-6)
        assert r["vnh"] == pytest.approx(2.113, abs=1e-3)
        assert r["phiVnh_L"] == pytest.approx(2266.0, abs=1.0)

    def test_passes(self, r):
        assert r["overall_pass"] is True


# ------------------------------------------------------------- 3. statics


def _rect(f, x0, x1, y0, y1, n=200):
    """Midpoint rule over a rectangle; zero if the rectangle is empty."""
    if x1 <= x0 or y1 <= y0:
        return 0.0
    dx, dy = (x1 - x0) / n, (y1 - y0) / n
    return sum(f(x0 + (i + 0.5) * dx, y0 + (j + 0.5) * dy)
               for i in range(n) for j in range(n)) * dx * dy


def _integrate(case, r):
    """Numerical integration of the two-stage factored pressure field.

    Each stage is integrated over its own footprint, so no cell straddles
    the edge of the old footing. Returns the total reaction, the moment
    about the column face and the shear beyond d from it (heavy L side),
    and the load inside the punching perimeter.
    """
    def stage(P, ML, MB, B, L):     # kN/mm^2; x along B, y along L
        return lambda x, y: (P / (B * L) + 12e3 * ML * y / (B * L ** 3)
                             + 12e3 * MB * x / (L * B ** 3))

    stages = [
        (stage(r["P0e"], r["M0Le"], r["M0Be"], case["B0"], case["L0"]),
         case["B0"] / 2, case["L0"] / 2),
        (stage(r["dPu"], r["dMuL"], r["dMuB"], r["B"], r["L"]),
         r["B"] / 2, r["L"] / 2),
    ]
    face = case["cL"] / 2.0
    total = moment = shear = inside = 0.0
    for q, hx, hy in stages:
        total += _rect(q, -hx, hx, -hy, hy)
        moment += _rect(lambda x, y: q(x, y) * (y - face) / 1000.0,
                        -hx, hx, face, hy)
        shear += _rect(q, -hx, hx, face + r["d_L"], hy)
        px, py = min(hx, r["b2"] / 2), min(hy, r["b1"] / 2)
        inside += _rect(q, -px, px, -py, py)
    return total, moment, shear, inside


class TestStatics:
    def test_strip_resultants_at_midspan(self):
        """Half of a footing: P/2 and 1.5 M/L in shear, PL/8 and M/2 in moment."""
        V_P, V_M, M_P, M_M = _strip(1000.0, 200.0, 4000.0, 0.0)
        assert V_P == pytest.approx(500.0)
        assert V_M == pytest.approx(1.5 * 200.0 / 4.0)
        assert M_P == pytest.approx(1000.0 * 4.0 / 8.0)
        assert M_M == pytest.approx(100.0)

    def test_strip_beyond_the_edge_is_zero(self):
        assert _strip(1000.0, 200.0, 4000.0, 2500.0) == (0.0, 0.0, 0.0, 0.0)

    @pytest.mark.parametrize("overrides", [
        {},
        {"shored": True},
        {"M0L": 60.0, "M0B": 20.0},
    ])
    def test_closed_forms_match_the_integrated_pressure_field(self, overrides):
        case = {**WORKED, **overrides}
        r = footing_jacket_check(**case)
        total, moment, shear, inside = _integrate(case, r)
        assert total == pytest.approx(case["Pu"], rel=1e-9)
        assert r["Mu_L"] == pytest.approx(moment, rel=1e-4)
        assert r["Vu_L"] == pytest.approx(shear, rel=1e-9)
        assert r["Vu_p"] == pytest.approx(case["Pu"] - inside, rel=1e-9)


# ---------------------------------------------------------- load history


class TestLoadHistory:
    def test_shored_is_a_required_argument(self):
        case = {k: v for k, v in WORKED.items() if k != "shored"}
        with pytest.raises(TypeError):
            footing_jacket_check(**case)

    def test_shored_must_be_a_bool(self):
        with pytest.raises(ValueError, match="load history"):
            run(shored="no")

    def test_unshored_keeps_the_existing_pressure_on_the_old_footprint(self):
        u, s = run(), run(shored=True)
        assert u["q_old_max"] > s["q_old_max"]
        assert s["q0"] == 0 and s["P0e"] == 0
        assert s["q1"] == pytest.approx(1500 / 13.44, abs=0.01)

    def test_unshored_wings_carry_only_the_increment(self):
        u, s = run(), run(shored=True)
        assert u["dPu"] == 1300 and s["dPu"] == 2000
        for key in ("Mu_w_L", "Vu_w_L", "Mu_w_B", "Vu_w_B", "Mu_L", "Vu_L"):
            assert u[key] < s[key]

    def test_no_load_at_casting_is_the_same_as_shored(self):
        u, s = run(P0=0), run(P0=0, shored=True)
        for key in ("q_max", "Mu_L", "Vu_L", "Vu_p", "Vu_w_L", "Vuh_L"):
            assert u[key] == pytest.approx(s[key])

    def test_locked_in_load_is_not_factored(self):
        """Everything above the load at casting goes through the composite
        footing: the increment is Pu - P0, not Pu - 1.2 P0."""
        assert run()["dPu"] == WORKED["Pu"] - WORKED["P0"]

    def test_a_bearing_failure_under_the_old_footprint_fails_overall(self):
        r = run(P0=900)
        assert r["q_old_max"] > WORKED["qa"]
        assert r["bearing_ok"] is False and r["overall_pass"] is False

    def test_loss_of_contact_is_a_failure_not_a_result(self):
        r = run(ML=1500, MuL=2200)
        assert r["contact_ok"] is False and r["contact_u_ok"] is False
        assert r["overall_pass"] is False

    def test_a_load_below_the_load_at_casting_lifts_the_wings(self):
        r = run(P=600, Pu=650)
        assert r["dPu"] < 0
        assert r["contact_u_ok"] is False and r["overall_pass"] is False


# ------------------------------------------------------------- sections


class TestSections:
    def test_lesser_concrete_strength_governs(self):
        assert run()["fc"] == 21
        assert run(fc0=35)["fc"] == 28

    def test_sqrt_fc_is_capped(self):
        assert run(fc0=80, fcj=80)["sqrt_fc"] == pytest.approx(8.3)

    def test_minimum_flexural_steel_is_on_the_jacketed_gross_section(self):
        r = run()
        assert r["As_min_L"] == pytest.approx(0.0018 * 3200 * 800)
        short = run(nj_B=0, dbj_B=0)
        assert short["As_min_ok_B"] is False and short["overall_pass"] is False

    def test_plain_footing_is_refused(self):
        with pytest.raises(ValueError, match="plain concrete"):
            run(n0_L=0, nj_L=0)

    def test_overlay_does_not_deepen_punching_unless_the_column_is_engaged(self):
        engaged, loose = run(), run(column_engaged=False)
        assert engaged["d_p"] == pytest.approx(705.0)
        assert loose["d_p"] == pytest.approx(505.0)
        assert loose["punch_ratio"] > engaged["punch_ratio"]
        assert loose["punch_ok"] is False

    def test_untied_overlay_is_not_counted_in_one_way_shear_either(self):
        """The section moves in to d - t,top from the column face and Vc
        loses the overlay: d_v = 715 - 200 = 515 mm."""
        tied, loose = run(), run(column_engaged=False)
        assert tied["d_v_L"] == pytest.approx(715.0)
        assert loose["d_v_L"] == pytest.approx(515.0)
        assert loose["phiVc_L"] == pytest.approx(
            0.75 * 0.17 * math.sqrt(21) * 3200 * 515 / 1000)
        assert loose["Vu_L"] > tied["Vu_L"]
        assert loose["shear_ratio_L"] > 1.5 * tied["shear_ratio_L"]
        assert loose["phiMn_L"] == tied["phiMn_L"]      # flexure stays composite

    def test_wing_root_needs_minimum_steel_too(self):
        """The existing bars stop at the old face; only the bottom dowels
        and the new bars cross it."""
        r = run(ndt_L=3)
        assert r["As_w_L"] < r["As_min_L"] <= r["As_L"]
        assert r["wAs_min_ok_L"] is False and r["overall_pass"] is False

    def test_light_steel_at_the_column_fails_eq_8_6_1_2(self):
        r = run(n0_B=11)
        assert r["T_slab_B"] == pytest.approx(3455.8 * 275 * 2800 / 3000 / 1000,
                                              abs=0.1)
        assert r["as2_ok_B"] is False and r["punch_ok"] is True
        assert r["overall_pass"] is False

    def test_eq_8_6_1_2_does_not_apply_at_low_shear(self):
        r = run(Pu=1300, P=1000)
        assert r["v_uv"] < r["v_trigger"]
        assert r["as2_applies"] is False and r["T_slab_min_L"] == 0
        assert r["as2_ok_L"] and r["as2_ok_B"]

    def test_untied_overlay_does_not_widen_b_slab(self):
        assert run(column_engaged=False)["bslab_L"] == 400 + 3 * 600

    def test_minimum_effective_depth(self):
        assert run()["d_min_ok"] is True
        thin = run(h0=220, t_top=0, db_tie=0)
        assert thin["d_B"] < 150 and thin["d_min_ok"] is False

    def test_no_overlay_ignores_the_engagement_flag(self):
        a = run(t_top=0, db_tie=0, column_engaged=False)
        b = run(t_top=0, db_tie=0, column_engaged=True)
        assert a["d_p"] == b["d_p"]

    def test_alpha_s_is_restricted_to_the_code_values(self):
        with pytest.raises(ValueError, match="alpha_s"):
            run(alpha_s=35)


# ------------------------------------------------------------ interfaces


class TestInterfaces:
    def test_dowel_yield_is_capped_at_420(self):
        r = run(fy_dowel=520)
        assert r["fy_sf"] == 420
        assert r["Vn_raw_L"] == pytest.approx(1.0 * r["Avf_L"] * 420 / 1000)

    def test_unroughened_surface_uses_0_6_without_lambda(self):
        assert run(surface="not_roughened")["mu"] == 0.6
        assert run(surface="not_roughened", lam=0.75)["mu"] == 0.6

    def test_lightweight_lambda_is_limited_to_0_85_in_mu(self):
        assert run(lam=0.9)["mu"] == pytest.approx(0.85)
        assert run(lam=0.75)["mu"] == pytest.approx(0.75)

    def test_higher_friction_caps_need_a_roughened_normalweight_surface(self):
        assert run()["cap_stress"] == pytest.approx(0.2 * 21)
        assert run(fc0=40, fcj=40)["cap_stress"] == pytest.approx(3.3 + 0.08 * 40)
        assert run(fc0=40, fcj=40, surface="not_roughened")["cap_stress"] == 5.5
        assert run(fc0=40, fcj=40, lam=0.85)["cap_stress"] == 5.5

    def test_overlay_takes_the_longitudinal_transfer(self):
        """With an overlay the old footing hands its tension to the new
        concrete through the horizontal surface (16.4), so the old faces
        carry the wing shear only."""
        r = run()
        assert r["N_strip_L"] == 0 and r["N_strip_B"] == 0
        assert r["Vu_if_L"] == pytest.approx(r["Vu_w_L"])

    def test_wings_beside_the_section_load_the_old_faces_along_their_length(self):
        """WORKED without the overlay (h = 600, d = 515 and 495).

        L flexure: T = 1734.1 kN, a = 30.36 mm, Mn = 1734.1(0.515 - 0.01518)
        = 866.8 kN*m, Mu = 867.3 so the bars are at yield (ratio capped at 1).
        One side wing, 600 wide, holds 4-D20 = 1256.6(415) = 521.5 kN and
        its share of the block balances 0.85(21)(30.36)(600) = 325.2 kN.
        N = 521.5 - 325.2 = 196.3 kN, on each half of a SIDE face.
        Side face: Vu,w = 269.5 kN, resultant sqrt(269.5^2 + (2 x 196.3)^2)
        = 476.2 kN.

        B flexure: T = 4712.4(275) + 3141.6(415) = 2599.7 kN, a = 34.68 mm,
        Mn = 2599.7(0.495 - 0.01734) = 1241.8 kN*m, Mu/Mn = 546.7/1241.8
        = 0.4403. One end wing holds 5-D20 = 651.9 kN against
        0.85(21)(34.68)(600) = 371.4 kN.
        N = 280.5(0.4403) = 123.5 kN, on each half of an END face.
        End face: sqrt(231.2^2 + (2 x 123.5)^2) = 338.3 kN.
        Side face strength: 0.75(20 x 314.16)(415) = 1955.6 kN.

        ACI 562-25 R9.4.5.3 is the basis for resolving the two shears into
        one.
        """
        r = run(t_top=0, db_tie=0)
        assert r["N_strip_L"] == pytest.approx(196.3, abs=0.1)
        assert r["N_strip_B"] == pytest.approx(123.5, abs=0.1)
        assert r["Vu_if_B"] == pytest.approx(476.2, abs=0.1)
        assert r["Vu_if_L"] == pytest.approx(338.3, abs=0.1)
        assert r["if_ratio_B"] == pytest.approx(476.2 / 1955.6, abs=1e-3)

    def test_longitudinal_transfer_can_govern_the_dowels(self):
        light = run(t_top=0, db_tie=0, nd_B=4, ndt_B=2)
        assert light["Vu_w_B"] <= light["phiVn_if_B"] < light["Vu_if_B"]
        assert light["if_ok_B"] is False

    def test_no_wing_beside_the_section_means_no_longitudinal_transfer(self):
        r = run(t_top=0, db_tie=0, eB=0, nd_B=0, ndt_B=0, nj_L=0, dbj_L=0)
        assert r["N_strip_L"] == 0
        assert r["N_strip_B"] > 0          # the end wings still hold bars

    def test_no_dowels_fails_the_wing(self):
        r = run(nd_L=0, ndt_L=0)
        assert r["if_ok_L"] is False and r["overall_pass"] is False

    def test_required_dowel_area(self):
        r = run(t_top=0, db_tie=0)
        assert r["Avf_req_L"] == pytest.approx(
            r["Vu_if_L"] * 1000 / (0.75 * 1.0 * 415))

    def test_overlay_without_wings_may_rely_on_bond(self):
        """Row (a) of Table 16.4.4.1: no ties needed where nothing pulls the
        overlay off the old footing."""
        r = run(eB=0, eL=0, nd_L=0, ndt_L=0, nd_B=0, ndt_B=0,
                nj_L=0, dbj_L=0, nj_B=0, dbj_B=0, db_tie=0, s_tie=0,
                P=900, Pu=1100, P0=400, qa=400)
        assert r["bond_allowed"] is True
        assert r["vnh"] == 0.55 and r["rho_v"] == 0
        assert r["phiVnh_L"] == pytest.approx(0.75 * 0.55 * 2000 * 715 / 1000)

    def test_wings_need_ties_under_the_overlay(self):
        """ACI 318-25M 16.4.1.2: soil pressure on the wings lifts an overlay
        cast with them, so bond alone is not credited."""
        r = run(db_tie=0, s_tie=0)
        assert r["bond_allowed"] is False
        assert r["vnh"] == 0 and r["ov_ok_L"] is False
        assert r["overall_pass"] is False

    def test_ties_below_the_minimum_earn_nothing(self):
        """Avf,min of 16.4.6.1 belongs to rows (b), (c) and (d) alike."""
        r = run(s_tie=400)
        assert r["rho_v"] < r["rho_v_min"]
        assert r["ties_min_ok"] is False
        assert r["vnh_c"] == 0 and r["vnh_sf"] == 0 and r["vnh"] == 0

    def test_minimum_tie_ratio_uses_the_capped_yield(self):
        assert run(fy_tie=500)["rho_v_min"] == pytest.approx(0.35 / 420)

    def test_row_c_is_capped_at_3_5(self):
        r = run(db_tie=25, s_tie=150)
        assert r["vnh_c"] == 3.5

    def test_unroughened_overlay_is_shear_friction_only(self):
        r = run(surface="not_roughened")
        assert r["vnh_a"] == 0 and r["vnh_c"] == 0
        assert r["vnh"] == pytest.approx(0.6 * r["rho_v"] * 415)

    def test_unroughened_surface_does_not_comply_with_aci_562(self):
        """ACI 562-25 9.4.4.3: an intentionally roughened substrate shall be
        specified. The numbers are still produced, for assessment."""
        r = run(surface="not_roughened")
        assert r["surface_ok"] is False and r["overall_pass"] is False
        assert run(PUBLISHED, surface="not_roughened")["surface_ok"] is True

    def test_tie_spacing_limit(self):
        assert run()["s_tie_max"] == 600
        thin = run(t_top=100)
        assert thin["s_tie_max"] == 400 and thin["tie_spacing_ok"] is True
        wide = run(t_top=60, s_tie=300)
        assert wide["s_tie_max"] == 240 and wide["tie_spacing_ok"] is False

    def test_unknown_surface_is_refused(self):
        with pytest.raises(ValueError, match="surface"):
            run(surface="monolithic")


# -------------------------------------------------------------- contract


class TestContract:
    def test_enlargement_in_one_direction_only(self):
        r = run(eB=0, nd_B=0, ndt_B=0)
        assert r["wing_B"] is False and r["wing_L"] is True
        assert r["Vu_w_B"] == 0 and r["if_ok_B"] is True

    def test_gaps_are_reported_with_every_result(self):
        r = run()
        assert r["not_checked"] is NOT_CHECKED and len(NOT_CHECKED) >= 8

    def test_every_check_is_in_the_verdict(self):
        r = run()
        flags = [k for k in r if k.endswith("_ok") or "_ok_" in k]
        gated = [k for k in flags
                 if not k.startswith(("yield_ok", "ties_min_ok"))]
        assert all(r[k] for k in gated) == r["overall_pass"]

    @pytest.mark.parametrize("bad", [
        {"B0": 0}, {"fc0": -21}, {"eL": -100}, {"qa": 0}, {"cB": 2000},
        {"ndt_L": 15},
    ])
    def test_nonsense_geometry_is_refused(self, bad):
        with pytest.raises(ValueError):
            run(**bad)
