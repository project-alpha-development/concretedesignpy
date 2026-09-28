"""
section.py -- column cross-section geometry for apec-col-design.

Axes (W&M 7th Fig. 11-35, printed 566): origin at the geometric centroid, x along the
width b, y along the depth h.  +Mx compresses the +y fibres, +My compresses the +x
fibres; compression is positive.  Units: mm, mm2.

A section is a plain dict so it serialises straight into the result JSON:

    rect   {"shape": "rect",   "b", "h", "cover", "dbt", "hoop": "rect", "bars": [...], ...}
    circle {"shape": "circle", "D",      "cover", "dbt", "hoop": "spiral" | "circular", ...}

bars: [{"x", "y", "db", "A", "face"}]; perimeter layouts also carry "nx"/"ny" (rect) or
"n" (circle) so the lateral-support rule can be evaluated.

Concrete compression block
* rect   -- the rectangle clipped by the half-plane n.p >= s_max - a (exact polygon).
* circle -- a circular segment, W&M 7th Eqs. (11-17)/(11-18), printed 539 (exact):
            A = R^2 (psi - sin psi cos psi),  A.ybar = (2/3) R^3 sin^3 psi,
            cos psi = (R - a)/R.

Detailing geometry
* clear spacing of column bars >= max(40 mm, 1.5 db, 4/3 dagg)
                                   ACI 318-25M 25.2.3, p. 510
* lateral support: every corner and alternate bar at a tie corner, no unsupported bar
  more than 150 mm clear from a supported one   ACI 318-25M 25.7.2.3, p. 551-552 |
                                   NSCP 425.7.2.3, 4-170/171 (vault Internal Learning/04)
* SMF: c/c spacing hx of supported bars <= 350 mm; <= 200 mm with EVERY bar supported
  when Pu > 0.3 Ag f'c or f'c > 70 MPa   NSCP 418.7.5.2(e),(f), 4-116 (read 2026-09-28)
* bc, Ach measured to the OUTSIDE of the hoops (ACI 318-25M 2.2 notation); the legs
  parallel to y pair with bc measured along x, and vice versa (R18.7.5.4, p. 338)
"""

import math

UNSUPPORTED_CLEAR_MAX = 150.0      # 25.7.2.3 / 425.7.2.3


def bar_area(db):
    return math.pi / 4.0 * db * db


# --------------------------------------------------------------------------- layouts
def rect_perimeter_bars(b, h, cover, dbt, db, nx, ny, edge=None):
    """nx bars on each face parallel to x (top y=+y0 and bottom y=-y0), ny bars on each
    face parallel to y (left/right), corners shared.  Total 2nx + 2ny - 4."""
    if nx < 2 or ny < 2:
        raise ValueError("a rectangular perimeter layout needs nx >= 2 and ny >= 2")
    e = edge if edge else cover + dbt + db / 2.0
    x0, y0 = b / 2.0 - e, h / 2.0 - e
    if x0 <= 0 or y0 <= 0:
        raise ValueError("bars do not fit inside the cover")
    a = bar_area(db)
    xs = [-x0 + 2.0 * x0 * i / (nx - 1) for i in range(nx)]
    ys = [-y0 + 2.0 * y0 * j / (ny - 1) for j in range(ny)]
    bars = []
    for x in xs:
        bars.append({"x": x, "y": y0, "db": db, "A": a, "face": "top"})
        bars.append({"x": x, "y": -y0, "db": db, "A": a, "face": "bot"})
    for y in ys[1:-1]:
        bars.append({"x": -x0, "y": y, "db": db, "A": a, "face": "left"})
        bars.append({"x": x0, "y": y, "db": db, "A": a, "face": "right"})
    return bars, {"x0": x0, "y0": y0, "edge": e, "pitch_x": 2.0 * x0 / (nx - 1),
                  "pitch_y": 2.0 * y0 / (ny - 1)}


def circle_bars(D, cover, dbt, db, n, start_deg=90.0, edge=None):
    """n bars equally spaced on a circle; the first at start_deg (90 = top)."""
    if n < 4:
        raise ValueError("a circular layout needs at least 4 bars (6 for spirals / SMF hoops)")
    e = edge if edge else cover + dbt + db / 2.0
    rb = D / 2.0 - e
    if rb <= 0:
        raise ValueError("bars do not fit inside the cover")
    a = bar_area(db)
    bars = []
    for k in range(n):
        t = math.radians(start_deg) + 2.0 * math.pi * k / n
        bars.append({"x": rb * math.cos(t), "y": rb * math.sin(t), "db": db, "A": a, "face": "ring"})
    return bars, {"rb": rb, "edge": e, "pitch": 2.0 * rb * math.sin(math.pi / n)}


def custom_bars(rows):
    """rows: [[x, y, db], ...] or [[x, y, db, A], ...] (mm, mm2)."""
    out = []
    for r in rows:
        x, y, db = float(r[0]), float(r[1]), float(r[2])
        a = float(r[3]) if len(r) > 3 and r[3] else bar_area(db)
        out.append({"x": x, "y": y, "db": db, "A": a, "face": "custom"})
    return out


def build_section(spec, bars_spec=None):
    """spec: {"shape": "rect", "b", "h", "cover", "dbt"} or {"shape": "circle", "D", ...}.
    bars_spec: {"db", "nx", "ny"} | {"db", "n"} | {"custom": [[x, y, db(, A)], ...]}."""
    shape = spec.get("shape", "rect").lower()
    cover, dbt = float(spec.get("cover", 40.0)), float(spec.get("dbt", 10.0))
    sec = {"shape": shape, "cover": cover, "dbt": dbt, "edge": spec.get("edge"),
           "dagg": spec.get("dagg")}
    if shape in ("rect", "rectangular", "square"):
        b, h = float(spec["b"]), float(spec["h"])
        sec.update({"shape": "rect", "b": b, "h": h, "Ag": b * h,
                    "bc_x": b - 2.0 * cover, "bc_y": h - 2.0 * cover,
                    "hoop": spec.get("hoop", "rect")})
        sec["Ach"] = sec["bc_x"] * sec["bc_y"]
        sec["poly"] = [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, h / 2), (-b / 2, h / 2)]
        sec["dmin"], sec["dmax"] = min(b, h), max(b, h)
    elif shape in ("circle", "circular", "round"):
        D = float(spec["D"])
        sec.update({"shape": "circle", "D": D, "Ag": math.pi * D * D / 4.0,
                    "Dc": D - 2.0 * cover, "hoop": spec.get("hoop", "spiral")})
        sec["Ach"] = math.pi * sec["Dc"] ** 2 / 4.0
        sec["dmin"] = sec["dmax"] = D
    else:
        raise ValueError(f"unknown section shape {shape!r} (rect or circle)")

    if bars_spec:
        if bars_spec.get("custom"):
            sec["bars"] = custom_bars(bars_spec["custom"])
            sec["layout"] = {"kind": "custom"}
        elif sec["shape"] == "rect":
            nx, ny, db = int(bars_spec["nx"]), int(bars_spec["ny"]), float(bars_spec["db"])
            sec["bars"], lay = rect_perimeter_bars(sec["b"], sec["h"], cover, dbt, db, nx, ny,
                                                   sec.get("edge"))
            sec["layout"] = {"kind": "perimeter", "nx": nx, "ny": ny, "db": db, **lay}
        else:
            n, db = int(bars_spec["n"]), float(bars_spec["db"])
            sec["bars"], lay = circle_bars(sec["D"], cover, dbt, db, n,
                                           float(bars_spec.get("start_deg", 90.0)), sec.get("edge"))
            sec["layout"] = {"kind": "ring", "n": n, "db": db, **lay}
    else:
        sec["bars"], sec["layout"] = [], {"kind": "none"}
    sec["Ast"] = sum(bb["A"] for bb in sec["bars"])
    sec["rho"] = sec["Ast"] / sec["Ag"]
    sec["n_bars"] = len(sec["bars"])
    sec["db_min"] = min((bb["db"] for bb in sec["bars"]), default=0.0)
    sec["db_max"] = max((bb["db"] for bb in sec["bars"]), default=0.0)
    return sec


def describe_bars(sec):
    lay = sec["layout"]
    if lay["kind"] == "perimeter":
        return (f"{sec['n_bars']}-D{lay['db']:g} ({lay['nx']} per b-face x {lay['ny']} per h-face)")
    if lay["kind"] == "ring":
        return f"{sec['n_bars']}-D{lay['db']:g} (ring)"
    if lay["kind"] == "custom":
        return f"{sec['n_bars']} bars (custom layout, Ast {sec['Ast']:.0f} mm2)"
    return "NONE"


# --------------------------------------------------------------------------- geometry
def clip_halfplane(poly, nx, ny, s0):
    """Sutherland-Hodgman: the part of polygon `poly` with nx*x + ny*y >= s0."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        sp, sq = nx * p[0] + ny * p[1] - s0, nx * q[0] + ny * q[1] - s0
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def area_centroid(poly):
    """Shoelace area and centroid of a simple polygon (any orientation)."""
    if len(poly) < 3:
        return 0.0, 0.0, 0.0
    a = cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    if abs(a) < 1e-12:
        return 0.0, 0.0, 0.0
    a *= 0.5
    return abs(a), cx / (6.0 * a), cy / (6.0 * a)


def extent(sec, nx, ny):
    """(s_max, s_min) of the concrete outline projected on the unit normal (nx, ny)."""
    if sec["shape"] == "circle":
        r = sec["D"] / 2.0
        return r, -r
    s = abs(nx) * sec["b"] / 2.0 + abs(ny) * sec["h"] / 2.0
    return s, -s


def compression_block(sec, nx, ny, a):
    """Area and centroid (x, y) of the concrete within depth a of the extreme compression
    fibre, measured along the unit normal (nx, ny) that points to the compression side."""
    smax, smin = extent(sec, nx, ny)
    if a <= 0:
        return 0.0, 0.0, 0.0
    if a >= smax - smin:
        return sec["Ag"], 0.0, 0.0
    if sec["shape"] == "circle":
        r = sec["D"] / 2.0
        psi = math.acos(max(-1.0, min(1.0, (r - a) / r)))
        area = r * r * (psi - math.sin(psi) * math.cos(psi))            # W&M Eq. (11-17)
        ybar = (2.0 / 3.0) * r ** 3 * math.sin(psi) ** 3 / area          # W&M Eq. (11-18)
        return area, ybar * nx, ybar * ny
    return area_centroid(clip_halfplane(sec["poly"], nx, ny, smax - a))


# --------------------------------------------------------------------------- detailing
def clear_spacing(sec):
    """Least clear distance between adjacent bars (mm) and the largest c/c pitch."""
    lay = sec["layout"]
    if lay["kind"] == "perimeter":
        db = lay["db"]
        return min(lay["pitch_x"], lay["pitch_y"]) - db, max(lay["pitch_x"], lay["pitch_y"])
    if lay["kind"] == "ring":
        return lay["pitch"] - lay["db"], lay["pitch"]
    bars = sec["bars"]
    best = math.inf
    for i in range(len(bars)):
        for j in range(i + 1, len(bars)):
            d = math.hypot(bars[i]["x"] - bars[j]["x"], bars[i]["y"] - bars[j]["y"])
            best = min(best, d - (bars[i]["db"] + bars[j]["db"]) / 2.0)
    return best, None


def clear_spacing_min(db, dagg=None):
    s = max(40.0, 1.5 * db)                      # 25.2.3
    if dagg:
        s = max(s, 4.0 / 3.0 * dagg)
    return s


def _face_min_support(n, pitch, db, hx_max, all_bars):
    """Fewest supported bars on one face of n equally spaced bars (both corners always
    supported) so that no two adjacent bars are unsupported (every corner and ALTERNATE
    bar), an unsupported bar is <= 150 mm clear from a supported one, and supported bars
    are <= hx_max c/c apart."""
    if all_bars or n <= 2 or pitch - db > UNSUPPORTED_CLEAR_MAX or 2.0 * pitch > hx_max:
        return n
    return (n + 1) // 2 if n % 2 else n // 2 + 1


def _face_gap(n, k, pitch):
    """k supported bars spread as evenly as possible over a face of n bars: the largest
    c/c between consecutive supported bars (mm) and that gap in pitches."""
    if n <= 1:
        return 0.0, 1
    if k >= n:
        return pitch, 1
    if k < 2:
        return math.inf, math.inf
    g = math.ceil((n - 1) / (k - 1) - 1e-9)
    return g * pitch, g


def lateral_support(sec, hx_max=350.0, all_bars=False, legs=None):
    """Tie-leg layout for a perimeter (rect) or ring (circle) layout.

    Returns legs_x (legs parallel to x), legs_y (legs parallel to y), nl (supported bars
    around the perimeter, for kn), hx (largest c/c between supported bars), and the check
    flags.  Without `legs` the fewest legs that satisfy the rule are returned (design);
    with `legs` = {"legs_x", "legs_y"} the provided hoops are evaluated (check).  A custom
    bar layout needs `legs` = {"legs_x", "legs_y", "nl", "hx"} from the user.
    """
    lay = sec["layout"]
    if lay["kind"] == "ring":
        return {"legs_x": 2, "legs_y": 2, "nl": lay["n"], "hx": lay["pitch"],
                "all_supported": True, "rule_ok": True, "hx_ok": lay["pitch"] <= hx_max + 1e-9,
                "note": "spiral / circular hoop supports every bar; Av counted as 2 legs"}
    if lay["kind"] != "perimeter":
        lg = legs or {}
        need = ("legs_x", "legs_y", "nl", "hx")
        ok = all(k in lg for k in need)
        return {"legs_x": lg.get("legs_x", 2), "legs_y": lg.get("legs_y", 2),
                "nl": lg.get("nl", sec["n_bars"]), "hx": lg.get("hx", math.inf),
                "all_supported": bool(lg.get("all_supported", False)), "rule_ok": ok,
                "hx_ok": lg.get("hx", math.inf) <= hx_max + 1e-9,
                "note": ("custom layout: legs/hx/nl as given by the user -- the lateral-support "
                         "rule was NOT verified by the script" if ok else
                         "custom layout without legs_x/legs_y/nl/hx -- lateral support UNVERIFIED")}
    nx, ny, db = lay["nx"], lay["ny"], lay["db"]
    px, py = lay["pitch_x"], lay["pitch_y"]
    kx_min = _face_min_support(nx, px, db, hx_max, all_bars)   # supported bars per b-face
    ky_min = _face_min_support(ny, py, db, hx_max, all_bars)   # supported bars per h-face
    # a supported bar on a b-face (top/bottom) is held by a leg parallel to y, and vice versa
    legs_y, legs_x = kx_min, ky_min
    if legs:                                   # provided hoops: the user's leg counts govern
        legs_x, legs_y = int(legs.get("legs_x", legs_x)), int(legs.get("legs_y", legs_y))
    kx, ky = min(legs_y, nx), min(legs_x, ny)
    hx1, g1 = _face_gap(nx, kx, px)
    hx2, g2 = _face_gap(ny, ky, py)

    def _face_ok(g, pitch):
        return g <= 1 or (g == 2 and pitch - db <= UNSUPPORTED_CLEAR_MAX)

    all_sup = kx >= nx and ky >= ny
    rule_ok = _face_ok(g1, px) and _face_ok(g2, py) and (all_sup or not all_bars)
    hx = max(hx1, hx2)
    return {"legs_x": legs_x, "legs_y": legs_y, "nl": 2 * kx + 2 * ky - 4, "hx": hx,
            "min_legs_x": ky_min, "min_legs_y": kx_min, "all_supported": all_sup,
            "rule_ok": rule_ok, "hx_ok": hx <= hx_max + 1e-9,
            "note": "legs parallel to x resist Vx and confine across bc_y; legs parallel to y "
                    "resist Vy and confine across bc_x"}
