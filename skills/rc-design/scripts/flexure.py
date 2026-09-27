"""
flexure.py -- RC beam flexure: As req'd, As,min, eps_t, phi*Mn.

Basis (see references/nscp_clauses.md for pages)
-----------------------------------------------
Governing code is NSCP 2015 (beam provisions = ACI 318M-14). Coefficients are
read from ACI 318-25M, printed page = PDF - 1, where the two editions agree.

* beta1 ................ ACI 318-25M Table 22.2.2.4.3, p. 438-439 (NSCP 422.2.2.4.3)
* 0.85 f'c a b block ... ACI 318-25M 22.2.2.4, p. 438
* displaced concrete ... W&M 7th Eq. (4-31) / Ex 4-4 step 5, p. 167 / 170:
                         a compression bar INSIDE depth a carries A's(f's - 0.85 f'c)
* phi .................. rule "nscp2015" (default): tension-controlled at eps_t >= 0.005
                         (NSCP 2015 / ACI 318-14, as rectified in concretedesignpy
                         CLAUSES.md, Option A). Rule "aci318-19": eps_ty + 0.003
                         (ACI 318-25M Table 21.2.2, p. 432). Rule "envelope": the lesser.
                         At fy <= 420 the two differ by <= 1 %; above 420 by 6-15 %.
* As,min ............... ACI 318-25M 9.6.1.2, p. 149: max(0.25 sqrt(f'c)/fy, 1.4/fy) bw d;
                         9.6.1.3 exemption (As >= 4/3 As,req) where allowed.
* eps_t floor .......... NSCP 2015 / ACI 318-14: nonprestressed beams eps_t >= 0.004
                         (ACI 318-25M R9.3.3.1, p. 144 records the 0.004 limit it replaced).
* bar clear spacing .... ACI 318-25M 25.2.1, p. 509: >= max(25 mm, db, 4/3 dagg);
                         layers 25.2.2 (>= 25 mm clear; APEC uses max(25, db)).

Zero capacity is never scored as a zero utilisation: D/C = inf.
Units: mm, MPa, N internally; kN and kN.m at the interface.
"""

import math

ES = 200000.0
ECU = 0.003


def bar_area(db):
    return math.pi / 4.0 * db * db


def beta1(fc):
    if fc <= 28.0:
        return 0.85
    if fc >= 55.0:
        return 0.65
    return max(0.85 - 0.05 * (fc - 28.0) / 7.0, 0.65)


def phi_flexure(eps_t, eps_ty, rule="nscp2015"):
    """Return (phi, classification) for a nonprestressed section, other transverse."""
    def _law(limit):
        if eps_t >= limit:
            return 0.90, "tension-controlled"
        if eps_t <= eps_ty:
            return 0.65, "compression-controlled"
        return 0.65 + 0.25 * (eps_t - eps_ty) / (limit - eps_ty), "transition"

    if rule == "nscp2015":
        return _law(0.005)
    if rule == "aci318-19":
        return _law(eps_ty + 0.003)
    if rule == "envelope":
        a, b = _law(0.005), _law(eps_ty + 0.003)
        return a if a[0] <= b[0] else b
    raise ValueError("phi_rule must be nscp2015, aci318-19 or envelope")


def as_min(fc, fy, bw, d):
    """ACI 318-25M 9.6.1.2 (NSCP 409.6.1.2). fy capped at 550 MPa (errata 2026)."""
    fy = min(fy, 550.0)
    return max(0.25 * math.sqrt(fc) / fy, 1.4 / fy) * bw * d


def clear_spacing_min(db, dagg=None):
    s = max(25.0, db)
    if dagg:
        s = max(s, 4.0 / 3.0 * dagg)
    return s


def bars_per_layer(b, cover, dbs, db, dagg=None):
    """How many bars of diameter db fit across b in one layer (25.2.1)."""
    usable = b - 2.0 * (cover + dbs) - db          # c/c reach of the two outer bars
    if usable < 0:
        return 1 if b - 2.0 * (cover + dbs) >= db else 0
    return int(math.floor(usable / (db + clear_spacing_min(db, dagg)) + 1e-9)) + 1


def layer_layout(n, db, b, cover, dbs, dagg=None):
    """Split n bars into layers. Returns list of bar counts, bottom layer first."""
    per = bars_per_layer(b, cover, dbs, db, dagg)
    if per < 2 and n > 1:
        per = max(per, 1)
    if per <= 0:
        return None
    layers, left = [], n
    while left > 0:
        k = min(per, left)
        layers.append(k)
        left -= k
    return layers


def face_layers(n, db, b, h, cover, dbs, dagg=None, vclear=None):
    """Bar layers of one face as (depth_from_THAT_face, area). Layer pitch db + max(25, db)."""
    counts = layer_layout(n, db, b, cover, dbs, dagg)
    if counts is None:
        return None
    pitch = db + (vclear if vclear is not None else max(25.0, db))
    y0 = cover + dbs + db / 2.0
    return [(y0 + i * pitch, k * bar_area(db)) for i, k in enumerate(counts)]


def section_capacity(b, h, fc, fy, tension, compression=(), phi_rule="nscp2015",
                     fy_factor=1.0, es=ES):
    """Strain-compatibility capacity of a rectangular section at P = 0.

    tension, compression: iterables of (depth_from_TENSION_face, area) and
    (depth_from_COMPRESSION_face, area). Returns dict (kN.m). fy_factor = 1.25
    gives the probable-strength steel stress used for Mpr (phi reported but the
    caller uses Mn).
    """
    fyd = fy * fy_factor
    b1 = beta1(fc)
    bars = [(h - y, a) for y, a in tension] + [(y, a) for y, a in compression]
    bars = [(d, a) for d, a in bars if a > 0]
    as_t = sum(a for _, a in tension)
    if as_t <= 0:
        return {"ok": False, "reason": "no tension steel", "Mn": 0.0, "phiMn": 0.0,
                "phi": 0.0, "c": 0.0, "a": 0.0, "eps_t": 0.0, "classification": "no-steel",
                "dt": 0.0, "d": 0.0, "As": 0.0}
    dt = max(h - y for y, _ in tension)
    d_cent = sum((h - y) * a for y, a in tension) / as_t

    def forces(c):
        a = min(b1 * c, h)
        cc = 0.85 * fc * a * b
        out = []
        for d, area in bars:
            eps = ECU * (c - d) / c                # compression positive
            fs = max(-fyd, min(fyd, eps * es))
            if fs > 0 and d < a:
                fs = max(fs - 0.85 * fc, 0.0)      # displaced concrete, W&M Eq. (4-31)
            out.append((d, fs * area))
        return a, cc, out

    def net(c):
        a, cc, out = forces(c)
        return cc + sum(f for _, f in out)

    lo, hi = 1e-6, 2.0 * h
    if net(hi) < 0:
        return {"ok": False, "reason": "no equilibrium (tension exceeds compression capacity)",
                "Mn": 0.0, "phiMn": 0.0, "phi": 0.0, "c": hi, "a": h, "eps_t": 0.0,
                "classification": "invalid", "dt": dt, "d": d_cent, "As": as_t}
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if net(mid) > 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-7:
            break
    c = 0.5 * (lo + hi)
    a, cc, out = forces(c)
    mn = -(cc * a / 2.0 + sum(f * d for d, f in out))   # moment about compression face, N.mm
    eps_t = ECU * (dt - c) / c
    phi, cls = phi_flexure(eps_t, fy / es, phi_rule)
    return {"ok": True, "Mn": mn / 1e6, "phiMn": phi * mn / 1e6, "phi": phi,
            "classification": cls, "c": c, "a": a, "eps_t": eps_t, "eps_ty": fy / es,
            "dt": dt, "d": d_cent, "As": as_t, "beta1": b1}


def as_req_closed_form(Mu_kNm, b, d, fc, fy, phi=0.90):
    """Singly reinforced As from Mu (information only). None if compression steel is needed."""
    if Mu_kNm <= 0:
        return 0.0
    Rn = Mu_kNm * 1e6 / (phi * b * d * d)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    if disc < 0:
        return None
    return 0.85 * fc / fy * (1.0 - math.sqrt(disc)) * b * d


def check_face(Mu_kNm, b, h, cover, dbs, fc, fy, n_t, db_t, n_c=0, db_c=0,
               phi_rule="nscp2015", dagg=None, allow_413=True, extra_as=0.0):
    """Capacity check of one face with given bars. Mu >= 0 (magnitude)."""
    t = face_layers(n_t, db_t, b, h, cover, dbs, dagg)
    if t is None:
        return {"ok": False, "reason": "bars do not fit", "DC": math.inf}
    comp = face_layers(n_c, db_c, b, h, cover, dbs, dagg) if n_c else []
    cap = section_capacity(b, h, fc, fy, t, comp or (), phi_rule)
    d = cap.get("d") or (h - cover - dbs - db_t / 2.0)
    asmin = as_min(fc, fy, b, d)
    as_rq = as_req_closed_form(Mu_kNm, b, d, fc, fy)
    as_prov = n_t * bar_area(db_t)
    exempt = allow_413 and as_rq is not None and as_prov >= 4.0 / 3.0 * as_rq
    cap.update({
        "Mu": Mu_kNm, "n": n_t, "db": db_t, "layers": len(t), "As_prov": as_prov,
        "As_min": asmin, "As_req_closed_form": as_rq, "As_min_ok": as_prov >= asmin or exempt,
        "As_min_exempt_9_6_1_3": bool(exempt and as_prov < asmin),
        "extra_As_for_torsion": extra_as,
        "DC": (Mu_kNm / cap["phiMn"]) if cap["phiMn"] > 0 else (0.0 if Mu_kNm <= 0 else math.inf),
        "eps_t_ok": cap.get("eps_t", 0) >= 0.004,
    })
    return cap


def design_face(Mu_kNm, b, h, cover, dbs, fc, fy, db_t, n_c=2, db_c=None,
                phi_rule="nscp2015", dagg=None, max_layers=2, n_min=2, n_max=40,
                allow_413=True, extra_as=0.0):
    """Smallest bar count of db_t that passes phi*Mn >= Mu, As,min, eps_t >= 0.004,
    fits in max_layers, and carries extra_as (torsion Al share) on top of the
    flexural steel (ACI 318-25M 9.5.4.3: torsion steel is ADDED).

    phi*Mn is not monotone in n (phi drops as eps_t falls), so every n is scanned.
    """
    db_c = db_c or db_t
    first_flex = None
    for n in range(max(n_min, 2), n_max + 1):
        r = check_face(Mu_kNm, b, h, cover, dbs, fc, fy, n, db_t, n_c, db_c,
                       phi_rule, dagg, allow_413)
        if not r.get("ok") or r["layers"] > max_layers:
            continue
        if r["phiMn"] >= Mu_kNm and r["As_min_ok"] and r["eps_t_ok"]:
            first_flex = first_flex or r
            if r["As_prov"] >= first_flex["As_prov"] + extra_as - 1e-6:
                r["As_flex_prov"] = first_flex["As_prov"]
                r["extra_As_for_torsion"] = extra_as
                r["status"] = "OK"
                return r
    return {"ok": False, "status": "FAIL", "n": None, "db": db_t, "Mu": Mu_kNm,
            "DC": math.inf,
            "reason": (f"no count of D{db_t:g} (<= {n_max} bars, <= {max_layers} layers) gives "
                       f"phi*Mn >= {Mu_kNm:.1f} kN.m with eps_t >= 0.004"
                       + (f" plus {extra_as:.0f} mm2 torsion Al" if extra_as else "")
                       + " -- enlarge the section or use a larger bar")}


if __name__ == "__main__":
    import json, sys
    a = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(check_face(**a), indent=2, default=str))
