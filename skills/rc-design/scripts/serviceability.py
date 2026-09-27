"""
serviceability.py -- RC beam deflection and crack control (service loads).

Basis (ACI 318-25M printed page | NSCP 2015 twin)
-------------------------------------------------
* minimum h: l/16, l/18.5, l/21, l/8, x (0.4 + fy/700)   Table 9.3.1.1 / 9.3.1.1.1, p. 143
  -- if met, calculated deflections are not required (9.3.1) but are still reported
* Ec = 4700 sqrt(f'c) ................ 19.2.2.1(b), p. 394
* fr = 0.62 lam sqrt(f'c) ............ 19.2.3.1, p. 395 (the 318-25M print reads 0.062;
  the 14 May 2026 errata amends 19.2.3.1 -- 0.62 is the SI value, verify on the page)
* Mcr = fr Ig / yt ................... Eq. (24.2.3.5), p. 499
* Ie, two laws, governing = the SMALLER Ie (larger deflection):
    - Branson (NSCP 2015 / ACI 318-14): (Mcr/Ma)^3 Ig + [1 - (Mcr/Ma)^3] Icr <= Ig
      (318-25M R24.2.3.5, p. 499: "Before 2019, ACI 318 used a different equation (Branson 1965)")
    - Bischoff (ACI 318-19/-25): Icr / (1 - ((2/3)Mcr/Ma)^2 (1 - Icr/Ig)), Ig if Ma <= (2/3)Mcr
      Table 24.2.3.5, p. 499 -- R24.2.3.5 notes Branson under-predicts at low rho
* midspan Ie for simple and continuous spans, support for cantilevers   24.2.3.7, p. 499
* lambda_delta = xi / (1 + 50 rho'); xi 3/6/12/60+ months = 1.0/1.2/1.4/2.0
                                        Eq. (24.2.4.1.1), Table 24.2.4.1.3, p. 501
* limits l/180, l/360, l/480, l/240; cantilever l = 2 x projection   Table 24.2.2, p. 498
* crack control s <= lesser of 380(280/fs) - 2.5cc and 300(280/fs), fs = (2/3) fy permitted
                                        Table 24.3.2 / 24.3.2.1, p. 503 | NSCP Table 424.3.2, 4-158
  (constants identical in both codes -- vault Design Procedures/05)
* skin reinforcement when h > 900 mm ... 9.7.2.3, p. 153

Elastic deflection coefficients (5/384 etc.) and midspan moment coefficients are statics,
not code -- (not vault-cited); pass Ma from the analysis model to override them.
Units: kN/m, m, mm, MPa.
"""

import math

from flexure import ES, bar_area

MIN_H = {"simple": 16.0, "one_end_continuous": 18.5, "both_continuous": 21.0, "cantilever": 8.0}
# (deflection coeff k in delta = k w L^4 / EI, moment coeff m in M = m w L^2)
STATICS = {"simple": (5 / 384, 1 / 8), "one_end_continuous": (1 / 185, 9 / 128),
           "both_continuous": (1 / 384, 1 / 24), "cantilever": (1 / 8, 1 / 2)}
XI = {3: 1.0, 6: 1.2, 12: 1.4, 60: 2.0}
LIMITS = {"flat_roof": 180, "floor": 360, "attached_likely_damaged": 480,
          "attached_not_likely_damaged": 240}


def min_depth(L_m, support, fy, h):
    req = L_m * 1000 / MIN_H[support] * (0.4 + fy / 700.0)
    return {"h_min": req, "h": h, "ok": h >= req, "clause": "Table 9.3.1.1, p. 143"}


def cracked_inertia(b, d, As, dprime, As_c, n):
    """Transformed cracked section, compression steel (n - 1) A's."""
    a_ = b / 2.0
    b_ = n * As + (n - 1) * As_c
    c_ = -(n * As * d + (n - 1) * As_c * dprime)
    kd = (-b_ + math.sqrt(b_ * b_ - 4 * a_ * c_)) / (2 * a_)
    icr = b * kd ** 3 / 3.0 + n * As * (d - kd) ** 2 + (n - 1) * As_c * (kd - dprime) ** 2
    return kd, icr


def ie_laws(Ma, Mcr, Ig, Icr):
    if Ma <= 0:
        return Ig, Ig
    br = min(Ig, (Mcr / Ma) ** 3 * Ig + (1 - (Mcr / Ma) ** 3) * Icr) if Ma > Mcr else Ig
    if Ma <= 2.0 / 3.0 * Mcr:
        bi = Ig
    else:
        bi = Icr / (1 - ((2.0 / 3.0) * Mcr / Ma) ** 2 * (1 - Icr / Ig))
    return br, min(bi, Ig)


def deflection(b, h, d, dprime, As, As_c, fc, fy, L_m, support, wD, wL, sustained_L=0.25,
               months=60, limit_case="attached_likely_damaged", lam=1.0,
               Ma_D=None, Ma_DL=None, ie_law="envelope"):
    """Immediate + long-term deflection of the governing span section."""
    ec = 4700.0 * math.sqrt(fc)
    fr = 0.62 * lam * math.sqrt(fc)
    ig = b * h ** 3 / 12.0
    mcr = fr * ig / (h / 2.0) / 1e6                       # kN.m
    n = ES / ec
    kd, icr = cracked_inertia(b, d, As, dprime, As_c, n)
    k, m = STATICS[support]
    L = L_m * 1000.0
    ma_d = Ma_D if Ma_D is not None else m * wD * L_m ** 2
    ma_dl = Ma_DL if Ma_DL is not None else m * (wD + wL) * L_m ** 2
    ma_sus = ma_d + sustained_L * (ma_dl - ma_d)

    def delta(w_kNm, ma):
        br, bi = ie_laws(ma, mcr, ig, icr)
        ie = {"branson": br, "bischoff": bi}.get(ie_law, min(br, bi))
        # w in kN/m == N/mm
        return k * w_kNm * L ** 4 / (ec * ie), ie, br, bi

    dD, ieD, _, _ = delta(wD, ma_d)
    dDL, ieDL, brDL, biDL = delta(wD + wL, ma_dl)
    dL = max(dDL - dD, 0.0)
    w_sus = wD + sustained_L * wL
    # sustained deflection with the D+L cracked stiffness (load history: member cracked at D+L)
    d_sus = k * w_sus * L ** 4 / (ec * ieDL)
    rho_p = As_c / (b * d)
    # Table 24.2.4.1.3 is tabulated only; between rows take the next longer duration (conservative)
    xi = XI[min([k_ for k_ in XI if k_ >= months] or [60])]
    lam_d = xi / (1 + 50 * rho_p)
    d_lt = lam_d * d_sus
    span_for_limit = 2 * L if support == "cantilever" else L
    lim_ll = span_for_limit / LIMITS["floor"]
    after = d_lt + dL
    lim_after = span_for_limit / LIMITS[limit_case] if limit_case in LIMITS else None
    return {
        "Ec": ec, "fr": fr, "Ig": ig, "Icr": icr, "kd": kd, "n": n, "Mcr": mcr,
        "Ma_D": ma_d, "Ma_DL": ma_dl, "Ma_sustained": ma_sus,
        "Ie_DL_branson": brDL, "Ie_DL_bischoff": biDL, "Ie_law": ie_law, "Ie_DL_used": ieDL,
        "delta_D": dD, "delta_L": dL, "delta_sustained": d_sus, "xi": xi, "rho_prime": rho_p,
        "lambda_delta": lam_d, "delta_longterm": d_lt, "delta_after_attachment": after,
        "limit_L_immediate": lim_ll, "ok_L_immediate": dL <= lim_ll,
        "limit_after_attachment": lim_after, "limit_case": limit_case,
        "ok_after_attachment": (after <= lim_after) if lim_after else None,
        "note": "Ma from statics coefficients" if Ma_DL is None else "Ma from analysis",
    }


def crack_control(b, h, cover, dbs, n, db, fy, Ma_service_kNm=None, d=None, As_c=0.0,
                  dprime=None, fc=None, dagg=None):
    """Table 24.3.2 spacing check of the tension-face layer."""
    cc = cover + dbs
    if Ma_service_kNm and d and fc:
        ec = 4700.0 * math.sqrt(fc)
        nmod = ES / ec
        As = n * bar_area(db)
        kd, icr = cracked_inertia(b, d, As, dprime or cc + db / 2, As_c, nmod)
        fs = nmod * Ma_service_kNm * 1e6 * (d - kd) / icr
        fs_src = "cracked section at service Ma"
    else:
        fs = 2.0 / 3.0 * fy
        fs_src = "(2/3) fy, 24.3.2.1"
    s1 = 380.0 * (280.0 / fs) - 2.5 * cc
    s2 = 300.0 * (280.0 / fs)
    smax = min(s1, s2)
    from flexure import layer_layout
    per = (layer_layout(n, db, b, cover, dbs, dagg) or [n])[0]
    s_act = (b - 2 * cc - db) / (per - 1) if per > 1 else b - 2 * cc
    out = {"fs": fs, "fs_source": fs_src, "cc": cc, "s_max": smax, "s_provided": s_act,
           "ok": s_act <= smax, "clause": "Table 24.3.2, p. 503 | NSCP Table 424.3.2, 4-158"}
    out["skin_reinforcement_required"] = h > 900.0
    return out
