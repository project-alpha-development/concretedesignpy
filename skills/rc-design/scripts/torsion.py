"""
torsion.py -- RC beam torsion: T_th, At/s, Al, section check.

Basis (NSCP 2015 422.7 = ACI 318M-14; pages are ACI 318-25M printed). Solid sections only.
-----------------------------------------------------------------------------------------
* Acp = b h, pcp = 2(b + h) .............. gross outline (flanges ignored -- conservative)
* Aoh, ph on the STIRRUP centreline ...... R22.7.6.1, p. 465 (never the main bar)
* phi Tth = phi 0.083 lam sqrt(f'c) Acp^2/pcp sqrt(1 + Nu/(0.33 Ag lam sqrt(f'c)))
                                           Table 22.7.4.1(a),(c), p. 463
* phi Tcr = same with 0.33 ................ Table 22.7.5.1, p. 464
* compatibility torsion: Tu may be reduced to phi Tcr  22.7.3.2, p. 461 -- the adjoining
  members must then carry the redistributed moments (22.7.3.3)
* At/s = Tu / (phi 1.7 Aoh fyt), theta 45 . Eq. (22.7.6.1a), 22.7.6.1.1 (Ao = 0.85 Aoh),
                                           22.7.6.1.2(a), p. 465-466  -- PER LEG
* Al = (At/s) ph (fyt/fy) = Tu ph / (phi 1.7 Aoh fy)   Eq. (22.7.6.1b), p. 465 (1.7, not 2)
* Al,min = 0.42 sqrt(f'c) Acp/fy - max(At/s, 0.175 bw/fyt) ph fyt/fy   9.6.4.3, p. 152
* section: sqrt((Vu/bw d)^2 + (Tu ph/(1.7 Aoh^2))^2) <= phi (Vc/(bw d) + 0.66 sqrt(f'c))
                                           22.7.7.1, p. 466
* s_max = min(ph/8, 300) ................. 9.7.6.3.3, p. 160 (300, never 305)
* closed stirrups / hoops ................ 9.7.6.3.1, p. 160
* Al distributed around the perimeter at <= 300 mm, a bar in every corner,
  db >= max(0.042 s, 10 mm) ................ 9.7.5.1-9.7.5.2, p. 158
* fy, fyt for torsion <= 420 MPa ......... ACI 318M-14 22.7.2.1

Not checked: hollow sections (Table 22.7.4.1(b)), flanged Acp, prestressed members.
Units: kN, kN.m, mm, MPa.
"""

import math

from shear import PHI_V, vc_nscp


def torsion_geometry(b, h, cover, dbs):
    x0 = b - 2.0 * cover - dbs
    y0 = h - 2.0 * cover - dbs
    return {"Acp": b * h, "pcp": 2.0 * (b + h), "x0": x0, "y0": y0,
            "Aoh": x0 * y0, "ph": 2.0 * (x0 + y0)}


def torsion_design(Tu_kNm, Vu_kN, b, h, d, cover, dbs, fc, fy, fyt, Nu_kN=0.0, lam=1.0,
                   torsion_type="equilibrium"):
    g = torsion_geometry(b, h, cover, dbs)
    fy_t, fyt_t = min(fy, 420.0), min(fyt, 420.0)
    ag = b * h
    ratio = 1.0 + Nu_kN * 1e3 / (0.33 * ag * lam * math.sqrt(fc))
    axial = math.sqrt(max(0.0, ratio))
    k = lam * math.sqrt(fc) * g["Acp"] ** 2 / g["pcp"] * axial / 1e6
    phi_tth = PHI_V * 0.083 * k
    phi_tcr = PHI_V * 0.33 * k
    Tu = abs(Tu_kNm)
    notes = []
    if torsion_type == "compatibility" and Tu > phi_tcr:
        notes.append(f"compatibility torsion: Tu {Tu:.2f} reduced to phi*Tcr {phi_tcr:.2f} kN.m "
                     "(22.7.3.2) -- redistribute to adjoining members (22.7.3.3)")
        Tu = phi_tcr
    out = {"Tu_input": abs(Tu_kNm), "Tu_design": Tu, "phiTth": phi_tth, "phiTcr": phi_tcr,
           "torsion_type": torsion_type, **g, "notes": notes,
           "fy_used": fy_t, "fyt_used": fyt_t}
    if Tu < phi_tth:
        out.update({"required": False, "At_s": 0.0, "Al": 0.0, "Al_min": 0.0,
                    "Al_design": 0.0, "section_ok": True, "s_max": None,
                    "status": "NEGLECT (Tu < phi*Tth)"})
        return out
    at_s = Tu * 1e6 / (PHI_V * 1.7 * g["Aoh"] * fyt_t)
    al = at_s * g["ph"] * fyt_t / fy_t
    al_min = (0.42 * math.sqrt(fc) * g["Acp"] / fy_t
              - max(at_s, 0.175 * b / fyt_t) * g["ph"] * fyt_t / fy_t)
    vc, _ = vc_nscp(fc, b, d, h, Nu_kN, lam)
    v1 = abs(Vu_kN) * 1e3 / (b * d)
    v2 = Tu * 1e6 * g["ph"] / (1.7 * g["Aoh"] ** 2)
    lhs = math.hypot(v1, v2)
    rhs = PHI_V * (vc * 1e3 / (b * d) + 0.66 * math.sqrt(fc))
    ok = lhs <= rhs
    out.update({"required": True, "At_s": at_s, "Al": al, "Al_min": max(al_min, 0.0),
                "Al_design": max(al, al_min, 0.0), "stress_combined": lhs, "stress_limit": rhs,
                "section_ok": ok, "s_max": min(g["ph"] / 8.0, 300.0),
                "status": "DESIGN FOR TORSION" if ok else "UNSAFE - enlarge section (22.7.7.1)"})
    return out


if __name__ == "__main__":
    import json, sys
    print(json.dumps(torsion_design(**json.loads(sys.argv[1])), indent=2))
