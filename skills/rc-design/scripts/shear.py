"""
shear.py -- RC beam shear: Vc, Vs, Av/s, s_max.

Basis (NSCP 2015 422.5 = ACI 318M-14; pages are ACI 318-25M printed)
---------------------------------------------------------------------
* Vc = lam sqrt(f'c) bw d / 6 ............. NSCP 422.5.5.1 / ACI 318M-14 (the 318-19
  Table 22.5.5.1 rho_w / lam_s form is an EDITION CHANGE, not used -- CLAUSES.md A.2)
* axial compression (1 + Nu/(14 Ag)) ....... W&M Eq. (6-13aM), p. 282 -- no upper cap
* axial tension (1 + 0.29 Nu/Ag) >= 0 ...... ACI 318M-14 22.5.7.1
* phi = 0.75 ................................ ACI 318-25M Table 21.2.1(b)
* Vs = Av fyt d / s ......................... 22.5.8.5.3
* section limit Vu <= phi(Vc + 0.66 sqrt(f'c) bw d)  22.5.1.2, p. 442 -- a CROSS-SECTION
  limit: no stirrup spacing rescues a section that fails it
* Av,min/s = max(0.062 sqrt(f'c) bw/fyt, 0.35 bw/fyt)  Table 9.6.3.4, p. 151
  (required when Vu > 0.5 phi Vc, 9.6.3.1 -- APEC applies it throughout, conservative)
* s_max along: d/2 <= 600, or d/4 <= 300 when Vs > 0.33 sqrt(f'c) bw d
  s_max across (leg spacing): d, or d/2 ..... Table 9.7.6.2.2, p. 160
* fyt used in Vs capped at 420 MPa ......... 20.2.2.4 (NSCP 420.2.2.4)

Not checked: deep beams (9.9), shear friction, openings, hollow sections.
Units: kN, mm, MPa.
"""

import math

PHI_V = 0.75


def vc_nscp(fc, bw, d, h, Nu_kN=0.0, lam=1.0):
    """Concrete shear strength (kN). Nu positive = compression."""
    ag = bw * h
    base = lam * math.sqrt(fc) * bw * d / 6.0
    if Nu_kN > 0:
        v, note = (1.0 + Nu_kN * 1e3 / (14.0 * ag)) * base, "axial compression"
    elif Nu_kN < 0:
        v, note = max(0.0, (1.0 + 0.29 * Nu_kN * 1e3 / ag) * base), "axial tension"
    else:
        v, note = base, "no axial load"
    return v / 1e3, note


def av_min_per_s(fc, bw, fyt):
    return max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)


def s_max_shear(d, Vs_kN, fc, bw):
    """Table 9.7.6.2.2: (along, across) in mm."""
    if Vs_kN * 1e3 > 0.33 * math.sqrt(fc) * bw * d:
        return min(d / 4.0, 300.0), d / 2.0
    return min(d / 2.0, 600.0), d


def shear_demand(Vu_kN, fc, fyt, bw, d, h, Nu_kN=0.0, lam=1.0, vc_zero=False):
    """Required Av/s (mm2/mm, all legs) for Vu. vc_zero: SMF hinge rule 18.6.5.2.

    The 22.5.1.2 section limit is evaluated with the 22.5 value of Vc even where
    18.6.5.2 zeroes Vc for the transverse steel (the limit is a cross-section
    dimension requirement, not a strength sum).
    """
    fyt_d = min(fyt, 420.0)
    vc, note = vc_nscp(fc, bw, d, h, Nu_kN, lam)
    vc_used = 0.0 if vc_zero else vc
    vs_req = max(Vu_kN / PHI_V - vc_used, 0.0)
    vs_lim = 0.66 * math.sqrt(fc) * bw * d / 1e3
    section_ok = Vu_kN <= PHI_V * (vc + vs_lim) + 1e-9
    av_s = vs_req * 1e3 / (fyt_d * d)
    avmin = av_min_per_s(fc, bw, fyt_d)
    s_along, s_across = s_max_shear(d, vs_req, fc, bw)
    return {
        "Vu": Vu_kN, "Vc": vc, "Vc_note": note, "Vc_used": vc_used, "Vc_zeroed_18_6_5_2": vc_zero,
        "Vs_req": vs_req, "Vs_limit_22_5_1_2": vs_lim, "phiVn_max": PHI_V * (vc + vs_lim),
        "section_ok": section_ok, "Av_s_req": av_s, "Av_s_min": avmin,
        "s_max_along": s_along, "s_max_across": s_across, "fyt_used": fyt_d,
        "status": "OK" if section_ok else "UNSAFE - enlarge section (22.5.1.2)",
    }


def shear_capacity(fc, fyt, bw, d, h, n_legs, db_s, s, Nu_kN=0.0, lam=1.0, vc_zero=False):
    """phi*Vn (kN) of provided stirrups."""
    vc, _ = vc_nscp(fc, bw, d, h, Nu_kN, lam)
    vc = 0.0 if vc_zero else vc
    av = n_legs * math.pi / 4.0 * db_s ** 2
    vs = av * min(fyt, 420.0) * d / s / 1e3 if s > 0 else 0.0
    vs = min(vs, 0.66 * math.sqrt(fc) * bw * d / 1e3)
    return PHI_V * (vc + vs)


if __name__ == "__main__":
    import json, sys
    print(json.dumps(shear_demand(**json.loads(sys.argv[1])), indent=2))
