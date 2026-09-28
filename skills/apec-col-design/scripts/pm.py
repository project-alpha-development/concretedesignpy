"""
pm.py -- strain-compatibility P-M (uniaxial) and P-M-M (biaxial) strength of RC columns.

Basis (ACI 318-25M printed page | NSCP 2015 folio -- NSCP pages read visually 2026-09-28)
---------------------------------------------------------------------------------------
* plane sections, eps_cu = 0.003, tension in concrete ignored
                              22.2.1-22.2.2, p. 437-438 | 422.2 ;  422.4.1.1, 4-143
* beta1 ..................... Table 22.2.2.4.3, p. 438-439 | 422.2.2.4.3
* 0.85 f'c over depth a = beta1 c, measured PERPENDICULAR to the neutral axis (W&M 7th
  Ex 11-5, printed 568-571); a bar inside the block carries As (fs - 0.85 f'c)
  (W&M Eq. (11-13b), printed 535-536)
* steel elastic-perfectly plastic, Es = 200 000 MPa    20.2.2.1-.2, p. 411
* Po = 0.85 f'c (Ag - Ast) + fy Ast                    Eq. (22.4.2.2), p. 441 | Eq. (422.4.2.2), 4-143
  (318-25M caps fy at 550 MPa there; NSCP 2015 prints no cap -- the cap is applied, it
  only bites above Grade 550)
* Pn,max = 0.80 Po ties / 0.85 Po spirals              Table 22.4.2.1, p. 440 | Table 422.4.2.1, 4-143
* Pnt = -fy Ast                                        22.4.3.1 | 422.4.3.1, 4-144
* phi (Table 421.2.2 / 21.2.2): compression-controlled at eps_t <= eps_ty = fy/Es
  (0.65 ties, 0.75 spirals), tension-controlled 0.90, linear between
    rule "nscp2015" (default) -- tension-controlled at eps_t >= 0.005   NSCP Table 421.2.2, 4-140
    rule "aci318-19"          -- at eps_ty + 0.003                       318-25M Table 21.2.2, p. 432
    rule "aci318-25"          -- 318-19 law + the 21.2.2.3 cap: for 0.1 f'c Ag <= Pn <= Pn,bal,
                                 phi <= interpolation 0.90 -> phi_cc     318-25M 21.2.2.3, p. 433
    rule "envelope"           -- the least of the three
  NSCP 421.2.2.1 prints "Grade 280 ... eps_ty = 0.002" where 318-14 says Grade 420; the
  script always uses eps_ty = fy/Es (the clause's first sentence), never the 0.002 option.
* biaxial: the neutral axis is swept in direction as well as depth, and the MOMENT vector
  is matched to the demand direction -- the neutral axis is NOT perpendicular to the
  moment vector in general (W&M 7th printed 571-572: 25.9 deg vs 30 deg in Ex 11-5).
* Bresler reciprocal load (information only): 1/phiPn = 1/phiPnx + 1/phiPny - 1/phiPno
                                                       W&M Eq. (11-31), printed 568

D/C definitions reported
* DC_M   -- |Mu| / phiMn(Pu, same moment direction): the load-contour ratio at the
            factored axial load (W&M 7th strain-compatibility method, printed 567).
* DC_PMM -- 1/lambda where lambda (Pu, Mux, Muy) first touches the surface: the radial
            ratio that MIDAS / ETABS report.  Both are 1.0 on the surface.
* Pu > phiPn,max, or Pu below phiPnt, has NO moment capacity: D/C = inf, never 0.

Units: N, mm, MPa internally.
"""

import math

from section import compression_block, extent

ES = 200000.0
ECU = 0.003
PHI_RULES = ("nscp2015", "aci318-19", "aci318-25", "envelope")
INF = float("inf")


def beta1(fc):
    if fc <= 28.0:
        return 0.85
    if fc >= 55.0:
        return 0.65
    return max(0.85 - 0.05 * (fc - 28.0) / 7.0, 0.65)


def phi_law(eps_t, eps_ty, spiral=False, limit=0.005):
    """Table 421.2.2 shape with a given tension-controlled limit. (phi, class)."""
    lo = 0.75 if spiral else 0.65
    if eps_t >= limit:
        return 0.90, "tension-controlled"
    if eps_t <= eps_ty:
        return lo, "compression-controlled"
    return lo + (0.90 - lo) * (eps_t - eps_ty) / (limit - eps_ty), "transition"


class Column:
    """Strength of one column section.  sec from section.build_section()."""

    def __init__(self, sec, fc, fy, Es=ES, phi_rule="nscp2015", spiral=None, ecu=ECU,
                 beta1_override=None):
        if phi_rule not in PHI_RULES:
            raise ValueError(f"phi_rule must be one of {PHI_RULES}")
        self.sec, self.fc, self.fy, self.Es, self.ecu = sec, float(fc), float(fy), float(Es), ecu
        self.rule = phi_rule
        self.spiral = (sec.get("hoop") == "spiral") if spiral is None else bool(spiral)
        # beta1_override exists for textbook benchmarks in US units (W&M: 0.80 at 5 ksi,
        # where the SI expression at 34.47 MPa gives 0.804); design runs never set it.
        self.b1 = float(beta1_override) if beta1_override else beta1(self.fc)
        self.eps_ty = self.fy / self.Es
        self.bars = [(b["x"], b["y"], b["A"]) for b in sec["bars"]]
        self.Ag, self.Ast = sec["Ag"], sec["Ast"]
        self.Po = 0.85 * self.fc * (self.Ag - self.Ast) + min(self.fy, 550.0) * self.Ast
        self.alpha = 0.85 if self.spiral else 0.80
        self.phi_cc = 0.75 if self.spiral else 0.65
        self.Pn_max = self.alpha * self.Po
        self.phiPn_max = self.phi_cc * self.Pn_max
        self.Pnt = -self.fy * self.Ast
        self.phiPnt = 0.90 * self.Pnt
        self._geo = {}
        self._pbal = {}

    # ------------------------------------------------------------------ primitives
    def _g(self, theta):
        key = round(theta % (2.0 * math.pi), 12)
        g = self._geo.get(key)
        if g is None:
            nx, ny = math.cos(theta), math.sin(theta)
            smax, smin = extent(self.sec, nx, ny)
            bars = [(smax - (nx * x + ny * y), x, y, a) for x, y, a in self.bars]
            dt = max((d for d, _, _, _ in bars), default=smax - smin)
            g = (nx, ny, smax, smin, bars, dt)
            if len(self._geo) > 5000:
                self._geo.clear()
            self._geo[key] = g
        return g

    def state(self, theta, c, fyf=1.0):
        """Nominal resultants for compression normal at angle theta (rad, from +x) and
        neutral-axis depth c (mm, may be inf).  fyf = 1.25 gives the probable strength.
        Returns (Pn, Mx, My, eps_t) in N, N.mm; eps_t > 0 is tension."""
        nx, ny, smax, smin, bars, dt = self._g(theta)
        fyd = self.fy * fyf
        fc85 = 0.85 * self.fc
        if c == INF:
            fs = min(self.Es * self.ecu, fyd) - fc85
            P = fc85 * self.Ag
            Mx = My = 0.0
            for d, x, y, a in bars:
                F = fs * a
                P += F
                Mx += F * y
                My += F * x
            return P, Mx, My, -self.ecu
        a_blk = self.b1 * c
        A, cx, cy = compression_block(self.sec, nx, ny, a_blk)
        Cc = fc85 * A
        P, Mx, My = Cc, Cc * cy, Cc * cx
        k = self.ecu / c
        for d, x, y, a in bars:
            fs = self.Es * k * (c - d)
            if fs > fyd:
                fs = fyd
            elif fs < -fyd:
                fs = -fyd
            if d <= a_blk:
                fs -= fc85
            F = fs * a
            P += F
            Mx += F * y
            My += F * x
        return P, Mx, My, k * (dt - c)

    def pn_bal(self, theta):
        key = round(theta % (2.0 * math.pi), 12)
        if key not in self._pbal:
            dt = self._g(theta)[5]
            self._pbal[key] = self.state(theta, self.ecu * dt / (self.ecu + self.eps_ty))[0]
        return self._pbal[key]

    def phi(self, theta, Pn, eps_t):
        """(phi, classification) by the selected rule."""
        ety = self.eps_ty
        if self.rule == "nscp2015":
            return phi_law(eps_t, ety, self.spiral, 0.005)
        p19 = phi_law(eps_t, ety, self.spiral, ety + 0.003)
        if self.rule == "aci318-19":
            return p19
        p25 = p19
        lo = 0.10 * self.fc * self.Ag
        pb = self.pn_bal(theta)
        if pb > lo and lo <= Pn <= pb:
            cap = 0.90 + (self.phi_cc - 0.90) * (Pn - lo) / (pb - lo)
            if cap < p19[0]:
                p25 = (cap, p19[1] + " (21.2.2.3 cap)")
        if self.rule == "aci318-25":
            return p25
        p14 = phi_law(eps_t, ety, self.spiral, 0.005)
        return min((p14, p19, p25), key=lambda t: t[0])

    def design(self, theta, c):
        """(phiPn uncapped, phiMx, phiMy, phi, eps_t, Pn, Mx, My, cls)."""
        Pn, Mx, My, et = self.state(theta, c)
        ph, cls = self.phi(theta, Pn, et)
        return ph * Pn, ph * Mx, ph * My, ph, et, Pn, Mx, My, cls

    # ------------------------------------------------------------------ root finding
    def _c_grid(self, theta):
        nx, ny, smax, smin, bars, dt = self._g(theta)
        D = smax - smin
        return [D * 10.0 ** (-2.4 + 3.1 * i / 29.0) for i in range(30)] + [INF]

    @staticmethod
    def _illinois(f, lo, hi, flo, fhi, tol, it=80):
        """Root of f in [lo, hi] with f(lo) < 0 < f(hi) (hi may be inf -> bisect in u)."""
        if hi == INF:
            hi = lo * 4.0 + 1.0
            fh = f(hi)
            n = 0
            while fh < 0 and n < 60:
                lo, flo, hi = hi, fh, hi * 2.0
                fh = f(hi)
                n += 1
            fhi = fh
        side = 0
        c = lo
        for _ in range(it):
            c = hi - fhi * (hi - lo) / (fhi - flo) if fhi != flo else 0.5 * (lo + hi)
            if not (lo < c < hi):
                c = 0.5 * (lo + hi)
            fcv = f(c)
            if abs(hi - lo) < tol or fcv == 0.0:
                break
            if fcv < 0:
                lo, flo = c, fcv
                if side == -1:
                    fhi *= 0.5
                side = -1
            else:
                hi, fhi = c, fcv
                if side == 1:
                    flo *= 0.5
                side = 1
        return c

    def roots_phiP(self, theta, Pu, hint=None):
        """All c with phi*Pn(c) = Pu (N).  hint: a nearby c to try first (warm start)."""
        f = lambda c: self.design(theta, c)[0] - Pu
        D = self._g(theta)[2] - self._g(theta)[3]
        tol = 1e-7 * D
        if hint is not None and hint != INF and hint > 0:
            lo, hi = hint / 1.3, hint * 1.3
            flo, fhi = f(lo), f(hi)
            if flo < 0 < fhi:
                # a warm start is only trusted when the coarse grid is monotone here
                return [self._illinois(f, lo, hi, flo, fhi, tol)]
        grid = self._c_grid(theta)
        vals = [f(c) for c in grid]
        out = []
        for i in range(len(grid) - 1):
            if vals[i] < 0 <= vals[i + 1]:
                out.append(self._illinois(f, grid[i], grid[i + 1], vals[i], vals[i + 1], tol))
            elif vals[i] >= 0 > vals[i + 1]:
                g = lambda c: -f(c)
                out.append(self._illinois(g, grid[i], grid[i + 1], -vals[i], -vals[i + 1], tol))
        return out

    def c_for_Pn(self, theta, P, fyf=1.0):
        """Nominal (phi = 1): c with Pn(c) = P, or None if P is outside [Pnt, Po]."""
        f = lambda c: self.state(theta, c, fyf)[0] - P
        D = self._g(theta)[2] - self._g(theta)[3]
        grid = self._c_grid(theta)
        vals = [f(c) for c in grid]
        if vals[0] > 0:
            lo_c = grid[0]
            while vals[0] > 0 and lo_c > 1e-9 * D:
                lo_c *= 0.1
                vals[0] = f(lo_c)
            grid[0] = lo_c
            if vals[0] > 0:
                return None
        if vals[-1] < 0:
            return None
        for i in range(len(grid) - 1):
            if vals[i] < 0 <= vals[i + 1]:
                return self._illinois(f, grid[i], grid[i + 1], vals[i], vals[i + 1], 1e-7 * D)
        return None

    # ------------------------------------------------------------------ contour / capacity
    def contour_point(self, theta, Pu, hint=None):
        """Design moment vector at axial Pu for neutral-axis direction theta.  When phi*Pn
        is not monotone in c (possible with asymmetric steel) the root with the SMALLEST
        moment is used -- the conservative side of a doubled-back diagram."""
        roots = self.roots_phiP(theta, Pu, hint)
        best = None
        for c in roots:
            d = self.design(theta, c)
            m = math.hypot(d[1], d[2])
            if best is None or m < best[0]:
                best = (m, c, d)
        if best is None:
            return None
        m, c, d = best
        return {"theta": theta, "c": c, "phiMx": d[1], "phiMy": d[2], "phi": d[3],
                "eps_t": d[4], "Pn": d[5], "cls": d[8], "M": m}

    def contour(self, Pu, n=72):
        pts, hint = [], None
        for k in range(n):
            th = 2.0 * math.pi * k / n
            p = self.contour_point(th, Pu, hint)
            if p:
                pts.append(p)
                hint = p["c"]
        return pts

    def axial_limits_ok(self, Pu):
        tol = 1e-9 * max(1.0, abs(self.phiPn_max))
        if Pu > self.phiPn_max + tol:
            return False, "Pu exceeds phiPn,max (Table 422.4.2.1) -- no moment capacity"
        if Pu < self.phiPnt - tol:
            return False, "tension exceeds phiPnt = 0.9 fy Ast -- no moment capacity"
        return True, ""

    def capacity(self, Pu, psi):
        """Design moment capacity (N.mm) at axial Pu (N) in moment direction psi
        (rad, atan2(My, Mx)).  Returns dict with phiMn, the components and the neutral
        axis; phiMn = 0 when Pu is outside [phiPnt, phiPn,max]."""
        ok, why = self.axial_limits_ok(Pu)
        if not ok:
            return {"phiMn": 0.0, "status": why}
        ux, uy = math.cos(psi), math.sin(psi)
        th0 = math.pi / 2.0 - psi                         # exact for doubly symmetric uniaxial

        def side(p):
            return ux * p["phiMy"] - uy * p["phiMx"]       # cross(u, M): >0 -> M is CCW of u

        def along(p):
            return ux * p["phiMx"] + uy * p["phiMy"]

        p0 = self.contour_point(th0, Pu)
        if p0 is None:
            return self._capacity_by_contour(Pu, psi, "no root at the first neutral-axis trial")
        if abs(side(p0)) <= 1e-9 * max(p0["M"], 1.0) and along(p0) > 0:
            return self._pack(p0, psi)
        # bracket: moment vector rotates opposite to theta (psi ~ 90 deg - theta)
        s0 = side(p0)
        lo, plo = th0, p0
        found = None
        for step in (math.radians(v) for v in (5, 10, 20, 35, 50, 70, 90)):
            th = th0 + (step if s0 > 0 else -step)
            p = self.contour_point(th, Pu, plo["c"])
            if p is None:
                break
            if along(p) > 0 and (side(p) > 0) != (s0 > 0):
                found = (lo, plo, th, p)
                break
            lo, plo = th, p
        if found is None:
            return self._capacity_by_contour(Pu, psi, "bracket search failed")
        a, pa, b, pb = found
        sa = side(pa)
        for _ in range(40):
            m = 0.5 * (a + b)
            pm_ = self.contour_point(m, Pu, pa["c"])
            if pm_ is None:
                break
            if (side(pm_) > 0) == (sa > 0):
                a, pa, sa = m, pm_, side(pm_)
            else:
                b, pb = m, pm_
            if abs(b - a) < 1e-9:
                break
        # final: interpolate between the bracketing moment vectors on the ray
        return self._pack(self._ray_hit(pa, pb, ux, uy), psi)

    @staticmethod
    def _ray_hit(pa, pb, ux, uy):
        ax, ay, bx, by = pa["phiMx"], pa["phiMy"], pb["phiMx"], pb["phiMy"]
        ex, ey = bx - ax, by - ay
        den = ux * ey - uy * ex
        if abs(den) < 1e-30:
            return pa
        s = (ax * ey - ay * ex) / den                         # distance along the ray
        out = dict(pa)
        out["phiMx"], out["phiMy"], out["M"] = s * ux, s * uy, abs(s)
        return out

    def _capacity_by_contour(self, Pu, psi, why):
        pts = self.contour(Pu, 144)
        ux, uy = math.cos(psi), math.sin(psi)
        best = None
        for i in range(len(pts)):
            pa, pb = pts[i], pts[(i + 1) % len(pts)]
            ax, ay, bx, by = pa["phiMx"], pa["phiMy"], pb["phiMx"], pb["phiMy"]
            ex, ey = bx - ax, by - ay
            den = ux * ey - uy * ex
            if abs(den) < 1e-30:
                continue
            s = (ax * ey - ay * ex) / den
            t = (ax * uy - ay * ux) / den
            if s > 0 and -1e-9 <= t <= 1 + 1e-9 and (best is None or s < best[0]):
                best = (s, pa)
        if best is None:
            return {"phiMn": 0.0, "status": f"load contour does not enclose the demand direction ({why})"}
        s, pa = best
        out = dict(pa)
        out["phiMx"], out["phiMy"], out["M"] = s * ux, s * uy, s
        return self._pack(out, psi, note=f"contour fallback ({why})")

    @staticmethod
    def _pack(p, psi, note=""):
        return {"phiMn": p["M"], "phiMx": p["phiMx"], "phiMy": p["phiMy"], "phi": p["phi"],
                "eps_t": p["eps_t"], "c": p["c"], "theta_deg": math.degrees(p["theta"]) % 360.0,
                "psi_deg": math.degrees(psi) % 360.0, "cls": p["cls"], "status": "ok",
                "note": note}

    def check(self, Pu, Mux, Muy, radial=True):
        """D/C of a factored demand (N, N.mm).  Never returns 0 for an infeasible point."""
        mu = math.hypot(Mux, Muy)
        ok, why = self.axial_limits_ok(Pu)
        out = {"Pu": Pu, "Mux": Mux, "Muy": Muy, "Mu": mu}
        if not ok:
            out.update({"DC_M": INF, "DC_PMM": INF, "phiMn": 0.0, "status": why})
            return out
        if mu <= 1e-6 * max(1.0, abs(Pu)) * 1.0:
            dc_ax = Pu / self.phiPn_max if Pu >= 0 else Pu / self.phiPnt
            out.update({"DC_M": 0.0, "DC_PMM": dc_ax, "phiMn": None,
                        "status": "axial only -- DC_PMM = Pu / phiPn,max (or / phiPnt)"})
            return out
        psi = math.atan2(Muy, Mux)
        cap = self.capacity(Pu, psi)
        out["cap"] = cap
        out["phiMn"] = cap["phiMn"]
        out["DC_M"] = mu / cap["phiMn"] if cap["phiMn"] > 0 else INF
        out["status"] = cap["status"]
        if radial:
            out["DC_PMM"] = self.radial_dc(Pu, mu, psi, out["DC_M"])
        return out

    def radial_dc(self, Pu, mu, psi, dc_m):
        """1/lambda with (lambda Pu, lambda Mu) on the surface (same moment direction)."""
        def h(lam):
            P = lam * Pu
            ok, _ = self.axial_limits_ok(P)
            if not ok:
                return lam * mu                       # beyond the axial limits: outside
            cap = self.capacity(P, psi)["phiMn"]
            return lam * mu - cap
        lo, flo = 0.0, h(0.0)
        if flo >= 0:
            return INF
        hi = 1.0 / max(dc_m, 1e-6) if dc_m not in (0.0, INF) else 1.0
        fhi = h(hi)
        n = 0
        while fhi < 0 and n < 60:
            lo, flo = hi, fhi
            hi *= 1.6
            fhi = h(hi)
            n += 1
        if fhi < 0:
            return 0.0
        lam = self._illinois(h, lo, hi, flo, fhi, 1e-7 * hi, 60)
        return 1.0 / lam if lam > 0 else INF

    # ------------------------------------------------------------------ uniaxial curves
    def axis_theta(self, axis, sign=1):
        """Neutral-axis normal for uniaxial bending: 'x' -> +Mx compresses +y (90 deg)."""
        if axis == "x":
            return math.pi / 2.0 if sign >= 0 else 3.0 * math.pi / 2.0
        return 0.0 if sign >= 0 else math.pi

    @staticmethod
    def m_axis(theta, Mx, My):
        """Moment about the bending axis of a uniaxial state (projection)."""
        return Mx * math.sin(theta) + My * math.cos(theta)

    def curve(self, axis="x", sign=1, fyf=1.0):
        """Uniaxial interaction curve, pure compression -> pure tension.  Points carry
        nominal Pn, Mn (about the bending axis) and, for fyf = 1, the design values."""
        th = self.axis_theta(axis, sign)
        dt = self._g(th)[5]
        ety = self.eps_ty
        key_c = {self.ecu * dt / (self.ecu + e): tag for e, tag in (
            (0.0, "fs=0 at extreme bar"), (ety, "balanced (eps_t = eps_ty)"),
            (0.005, "eps_t = 0.005"), (ety + 0.003, "eps_t = eps_ty + 0.003"))}
        cs = [INF] + [dt * f for f in (3.0, 2.0, 1.5, 1.25, 1.1, 0.9, 0.8, 0.7, 0.6, 0.5,
                                       0.45, 0.4, 0.33, 0.28, 0.24, 0.2, 0.16, 0.13,
                                       0.1, 0.08, 0.06, 0.04, 0.02)]
        c0 = self.c_for_Pn(th, 0.0, fyf)
        if c0:
            key_c[c0] = "pure bending (Pn = 0)"
        cs = sorted(set(cs) | set(key_c), key=lambda c: -c if c != INF else -1e300)
        pts = []
        for c in cs:
            Pn, Mx, My, et = self.state(th, c, fyf)
            row = {"c": c, "Pn": Pn, "Mn": self.m_axis(th, Mx, My), "Mx": Mx, "My": My,
                   "eps_t": et, "tag": key_c.get(c, "")}
            if fyf == 1.0:
                ph, cls = self.phi(th, Pn, et)
                row.update({"phi": ph, "cls": cls, "phiPn": min(ph * Pn, self.phiPn_max),
                            "phiMn": ph * row["Mn"]})
            pts.append(row)
        Mt = sum(-self.fy * fyf * a * (y if axis == "x" else x) for x, y, a in self.bars)
        pts.append({"c": 0.0, "Pn": -self.fy * fyf * self.Ast, "Mn": Mt * sign, "Mx": 0.0,
                    "My": 0.0, "eps_t": INF, "tag": "pure tension", "phi": 0.90,
                    "cls": "tension-controlled", "phiPn": 0.90 * self.Pnt, "phiMn": 0.9 * Mt * sign})
        return pts

    def moment_at(self, axis, P, sign=1, fyf=1.0):
        """Nominal (phi = 1) moment about `axis` at axial P (N).  fyf = 1.25 -> Mpr."""
        th = self.axis_theta(axis, sign)
        c = self.c_for_Pn(th, P, fyf)
        if c is None:
            return None
        Pn, Mx, My, et = self.state(th, c, fyf)
        return {"M": abs(self.m_axis(th, Mx, My)), "c": c, "eps_t": et, "P": P}

    def moment_extreme(self, axis, Pmin, Pmax, fyf=1.0, kind="max", n=24):
        """Largest (or least) nominal moment about `axis` for P in [Pmin, Pmax], both
        bending senses.  Returns (M, P_at)."""
        if Pmax < Pmin:
            Pmin, Pmax = Pmax, Pmin
        best = None
        Ps = [Pmin + (Pmax - Pmin) * i / n for i in range(n + 1)] if Pmax > Pmin else [Pmin]
        for sign in (1, -1):
            for P in Ps:
                r = self.moment_at(axis, P, sign, fyf)
                m = r["M"] if r else 0.0
                if best is None or (m > best[0] if kind == "max" else m < best[0]):
                    best = (m, P, sign)
        if kind == "max" and Pmax > Pmin:                 # golden-section polish
            m0, P0, sgn = best
            a, b = max(Pmin, P0 - (Pmax - Pmin) / n), min(Pmax, P0 + (Pmax - Pmin) / n)
            g = (math.sqrt(5.0) - 1.0) / 2.0
            fm = lambda P: (self.moment_at(axis, P, sgn, fyf) or {"M": 0.0})["M"]
            x1, x2 = b - g * (b - a), a + g * (b - a)
            f1, f2 = fm(x1), fm(x2)
            for _ in range(40):
                if f1 > f2:
                    b, x2, f2 = x2, x1, f1
                    x1 = b - g * (b - a)
                    f1 = fm(x1)
                else:
                    a, x1, f1 = x1, x2, f2
                    x2 = a + g * (b - a)
                    f2 = fm(x2)
            if max(f1, f2) > m0:
                best = (max(f1, f2), x1 if f1 > f2 else x2, sgn)
        return best[0], best[1]

    def balanced(self, axis, sign=1):
        th = self.axis_theta(axis, sign)
        dt = self._g(th)[5]
        c = self.ecu * dt / (self.ecu + self.eps_ty)
        Pn, Mx, My, et = self.state(th, c)
        return {"c": c, "Pn": Pn, "Mn": abs(self.m_axis(th, Mx, My))}

    # ------------------------------------------------------------------ Bresler (info)
    def phiPn_at_e(self, axis, e):
        """Design axial capacity at uniaxial eccentricity e (mm) about `axis` (N)."""
        sign = 1 if e >= 0 else -1
        e = abs(e)
        th = self.axis_theta(axis, sign)
        if e < 1e-9:
            return self.phiPn_max
        f = lambda c: abs(self.m_axis(th, *self.state(th, c)[1:3])) - e * self.state(th, c)[0]
        grid = self._c_grid(th)
        vals = [f(c) for c in grid]
        for i in range(len(grid) - 1, 0, -1):
            if vals[i] <= 0 < vals[i - 1]:
                g = lambda c: -f(c)
                c = self._illinois(g, grid[i - 1], grid[i], -vals[i - 1], -vals[i],
                                   1e-7 * grid[i] if grid[i] != INF else 1e-3)
                Pn, Mx, My, et = self.state(th, c)
                ph, _ = self.phi(th, Pn, et)
                return min(ph * Pn, self.phiPn_max)
        return 0.0

    def bresler(self, Pu, Mux, Muy):
        """Bresler reciprocal load (information only; W&M Eq. (11-31), printed 568)."""
        if Pu <= 0:
            return {"valid": False, "note": "Bresler needs axial compression"}
        pnx = self.phiPn_at_e("x", abs(Mux) / Pu)
        pny = self.phiPn_at_e("y", abs(Muy) / Pu)
        pno = self.phi_cc * self.Po
        inv = (1.0 / pnx if pnx > 0 else INF) + (1.0 / pny if pny > 0 else INF) - 1.0 / pno
        phiPn = 1.0 / inv if inv > 0 and inv != INF else 0.0
        valid = phiPn >= 0.10 * self.fc * self.Ag * self.phi_cc
        return {"phiPnx": pnx, "phiPny": pny, "phiPno": pno, "phiPn": min(phiPn, self.phiPn_max),
                "ratio": Pu / phiPn if phiPn > 0 else INF, "valid": valid,
                "note": "" if valid else "below ~0.1 f'c Ag the reciprocal-load method is unreliable"}
