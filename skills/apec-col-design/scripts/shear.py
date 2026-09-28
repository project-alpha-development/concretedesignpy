"""
shear.py -- one-way shear of RC columns with axial load (NSCP 2015 = ACI 318M-14).

Basis (NSCP folio read visually 2026-09-28 | ACI 318-25M printed page)
---------------------------------------------------------------------
* Vn = Vc + Vs .......................... 422.5.1.1, 4-144 | 22.5.1.1
* section limit Vu <= phi(Vc + 0.66 sqrt(f'c) bw d)
                                          422.5.1.2, 4-144 prints 0.67; ACI 318-25M Eq.
                                          (22.5.1.2), p. 442 prints 0.66 -- the smaller is
                                          used (conservative by 1.5 %)
* Vc, axial compression: 0.17 (1 + Nu/(14 Ag)) lam sqrt(f'c) bw d
                                          Eq. (422.5.6.1), 4-145 (Nu + for compression)
* Vc, axial tension: 0.17 (1 + Nu/(3.5 Ag)) lam sqrt(f'c) bw d >= 0
                                          Eq. (422.5.7.1), 4-145 (Nu - for tension)
  (the 318-19+ Table 22.5.5.1 rho_w / lam_s form is an EDITION change, not used)
* sqrt(f'c) <= 8.3 MPa .................. 422.5.3.1, 4-144 | 22.5.3.1, p. 443
* fyt in Vs <= 420 MPa .................. 422.5.3.3 -> 420.2.2.4 | 22.5.3.3, p. 443
* circular: d = 0.8 D, bw = D ........... 422.5.2.2, 4-144 | 22.5.2.1(b),(c), p. 443
  (rectangular: d to the extreme layer, as W&M 7th Ex 19-2; 318-25M 22.5.2.1(a) also
   permits 0.8h -- option "shear_d": "0.8h")
* phi = 0.75; 0.60 where Vn < shear at nominal moment strength (SMF members designed
  for E) ................................ Table 421.2.1(b), 4-140; 421.2.4.1, 4-141 |
                                          21.2.4.1, p. 435
* Av,min = max(0.062 sqrt(f'c), 0.35) bw s / fyt where Vu > 0.5 phi Vc
                                          ACI 318-25M 10.6.2.1-.2, p. 172
* s max: Vs <= 0.33 sqrt(f'c) bw d -> min(d/2, 600), else min(d/4, 300)
                                          ACI 318-25M Table 10.7.6.5.2, p. 177
* biaxial shear (ACI 318-19+ only, NOT NSCP 2015): if both Vu/phiVn > 0.5, the sum
  <= 1.5 .............................. ACI 318-25M 22.5.1.10-.11, p. 442-443 -- reported
                                          as a WARN, never a FAIL
Units: kN, mm, MPa at the interface.
"""

import math

PHI_V = 0.75
PHI_V_SEISMIC_BRITTLE = 0.60
SECTION_LIMIT_COEF = 0.66


def sqrt_fc(fc):
    return min(math.sqrt(fc), 8.3)


def vc_axial(fc, bw, d, Ag, Nu_kN=0.0, lam=1.0):
    """Concrete shear strength with axial load (kN).  Nu > 0 compression."""
    base = 0.17 * lam * sqrt_fc(fc) * bw * d
    nu = Nu_kN * 1e3
    if nu > 0:
        return (1.0 + nu / (14.0 * Ag)) * base / 1e3, "422.5.6.1 (axial compression)"
    if nu < 0:
        return max(0.0, (1.0 + nu / (3.5 * Ag)) * base) / 1e3, "422.5.7.1 (axial tension)"
    return base / 1e3, "422.5.5.1 (no axial load)"


def vs_limit(fc, bw, d):
    return SECTION_LIMIT_COEF * math.sqrt(fc) * bw * d / 1e3


def vs_provided(Av, fyt, d, s):
    return Av * min(fyt, 420.0) * d / s / 1e3 if s > 0 else 0.0


def av_min_per_s(fc, bw, fyt):
    fyt = min(fyt, 420.0)
    return max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)


def s_max(d, Vs_kN, fc, bw):
    if Vs_kN * 1e3 > 0.33 * math.sqrt(fc) * bw * d:
        return min(d / 4.0, 300.0)
    return min(d / 2.0, 600.0)


def shear_dirs(sec, lay_d=None, mode="actual"):
    """Geometry for the two shear directions.  'x' = shear acting along x (resisted by
    legs parallel to x, d measured along x, bw = h); 'y' = along y (legs parallel to y,
    d along y, bw = b)."""
    if sec["shape"] == "circle":
        D = sec["D"]
        g = {"bw": D, "d": 0.8 * D, "h": D}
        return {"x": dict(g), "y": dict(g)}
    b, h = sec["b"], sec["h"]
    edge = (lay_d or {}).get("edge") or (sec["cover"] + sec["dbt"] + sec.get("db_max", 20.0) / 2.0)
    if mode == "0.8h":
        dx, dy = 0.8 * b, 0.8 * h
    else:
        dx, dy = b - edge, h - edge
    return {"x": {"bw": h, "d": dx, "h": b}, "y": {"bw": b, "d": dy, "h": h}}


def biaxial_interaction(rx, ry):
    """ACI 318-19+ 22.5.1.10-.11 on demand/capacity ratios (information)."""
    if rx <= 0.5 or ry <= 0.5:
        return {"applies": False, "sum": rx + ry, "ok": True}
    return {"applies": True, "sum": rx + ry, "ok": rx + ry <= 1.5}
