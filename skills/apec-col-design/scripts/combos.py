"""
combos.py -- NSCP 2015 load combinations (Section 203) generated from UNFACTORED load cases.

Every factored force in apec-col-design comes out of this module: members are designed
for the envelope of the combinations below, never for a single hand-picked factored set.

Basis -- NSCP 2015 Vol. I, read visually 2026-09-28 (image-only scan, _Scanned/)
--------------------------------------------------------------------------------
Strength, Section 203.3.1 (folio 2-11):
    203-1   1.4(D + F)
    203-2   1.2(D + F + T) + 1.6(L + H) + 0.5(Lr or R)
    203-3   1.2D + 1.6(Lr or R) + (f1 L or 0.5W)
    203-4   1.2D + 1.0W + f1 L + 0.5(Lr or R)
    203-5   1.2D + 1.0E + f1 L
    203-6   0.9D + 1.0W + 1.6H
    203-7   0.9D + 1.0E + 1.6H
    f1 = 1.0 for floors in places of public assembly, live loads > 4.8 kPa and garage
         live load; 0.5 for other live loads.
Earthquake load, Section 208.6.1 (folio 2-219):
    E  = rho Eh + Ev                                   (208-18)
    Em = Omega0 Eh                                     (208-19)
    Ev = "an addition of 0.5 Ca I D to the dead load effect, D, for Strength Design,
         and may be taken as zero for Allowable Stress Design"
    rho: 1.0 <= rho <= 1.5, <= 1.25 for SMF (not dual); 1.0 in Zone 2 / for drift.
  Ev is applied with BOTH senses: (1.2 +/- ev)D and (0.9 +/- ev)D with ev = 0.5 Ca I,
  each with +/- rho Eh.  The literal "+E" pairs +Ev only with +Eh and so misses
  (0.9 - ev)D + rho Eh -- the uplift case on the column that +Eh puts in tension.
  The permutation is a superset of both readings; nothing it adds can unconserve.
Allowable stress, Section 203.4.1 basic (folio 2-11) -- no stress increase:
    203-8   D + F
    203-9   D + H + F + L + T
    203-10  D + H + F + (Lr or R)
    203-11  D + H + F + 0.75[L + T + (Lr or R)]   (printed "0.75[L + T(Lr or R)]" -- the
                                                    '+' before (Lr or R) is missing on
                                                    the page; read as the sum, which is
                                                    the conservative reading)
    203-12  D + H + F + (0.6W or E/1.4)
Section 203.4.2 alternate basic (folio 2-11) -- one-third increase permitted with W or E:
    203-13  D + H + F + 0.75[L + Lr + (0.6W or E/1.4)]   (printed with the same dropped '+')
    203-14  0.6D + 0.6W + H
    203-15  0.6D + E/1.4 + H
    203-16  D + L + (Lr or R)
    203-17  D + L + 0.6W
    203-18  D + L + E/1.4
Special seismic, Section 203.5 (folio 2-11), only where Section 208 requires it:
    203-19  1.2D + f1 L + 1.0Em          203-20  0.9D +/- 1.0Em
Orthogonal effects, Section 208.7.1 (folio 2-221): in Zones 2 and 4, for a column in two
    or more intersecting lateral systems (and plan irregularity Types 1 (both axes) / 5),
    design for 100 % of the seismic forces in one direction + 30 % in the other, unless
    the column's seismic axial load in either direction is < 20 % of its axial capacity.

APEC design criteria Section 3.6 (project document, not vault basis) lists 203-1..203-12
with F, T, R and Lr dropped; with those cases absent this module reproduces that list
exactly.  Two corrections to that sheet: the ASD set is Section 203.4.1 (Section 203.3.2
is "Other Loads" = ponding), and NSCP's 203-11 carries 0.75(Lr or R) as well as 0.75L.

Load cases are named freely; their TYPE is inferred from the name or given explicitly:
    D  (D, DL, SW, SDL, SD, DEAD...)   L (L, LL, LIVE)   Lr (LR, RLL, ROOF...)   R (RAIN)
    W  (W*, WIND*)   E (E*, EQ*, RS*, SX, SY)   H (H, EARTH, SOIL)   F (F, FLUID)   T (T, TEMP)
"""

import re

TYPE_PATTERNS = (
    ("Lr", r"^(LR|RLL|ROOFL.*|ROOF_?LIVE|LROOF)$"),
    ("D", r"^(D|DL|DEAD.*|SW|SELF.*|SDL|SD|SIDL|SUPER.*|FIN.*|PARTITION.*|CLADDING.*)$"),
    ("L", r"^(L|LL|LIVE.*|L\d+|LL\d+)$"),
    ("R", r"^(R|RAIN.*)$"),
    ("W", r"^(W|WIND.*|W[XYZ+\-].*|WX|WY)$"),
    ("E", r"^(E|EQ.*|E[XY].*|RS.*|SX|SY|SEIS.*|EARTHQ.*)$"),
    ("H", r"^(H|EARTH.*|SOIL.*|LAT.*)$"),
    ("F", r"^(F|FLUID.*)$"),
    ("T", r"^(T|TEMP.*|THERM.*)$"),
)


def infer_type(name):
    n = name.strip().upper()
    for t, pat in TYPE_PATTERNS:
        if re.match(pat, n):
            return t
    return None


def classify(case_names, types=None):
    """{case_name: type}.  Explicit `types` win; unknown names raise (no silent drop)."""
    out = {}
    for c in case_names:
        t = (types or {}).get(c) or infer_type(c)
        if t not in ("D", "L", "Lr", "R", "W", "E", "H", "F", "T"):
            raise ValueError(f"load case {c!r}: type unknown -- give it in 'case_types' "
                             "(one of D, L, Lr, R, W, E, H, F, T)")
        out[c] = t
    return out


def _by_type(ctype):
    groups = {}
    for c, t in ctype.items():
        groups.setdefault(t, []).append(c)
    return groups


def _add(f, cases, k):
    for c in cases or ():
        f[c] = f.get(c, 0.0) + k


def horizontal_E_variants(e_cases, rho=1.0, orthogonal=False, factor=1.0):
    """[(label, {case: factor})] for the horizontal earthquake component.
    Without orthogonal: +/- each direction.  With orthogonal (208.7.1): +/-100 % of one
    direction with +/-30 % of each other direction."""
    out = []
    k = rho * factor
    for e in e_cases:
        others = [o for o in e_cases if o != e]
        if orthogonal and others:
            for s in (1, -1):
                for o in others:
                    for so in (1, -1):
                        lab = f"{'+' if s > 0 else '-'}{e}{'+' if so > 0 else '-'}0.3{o}"
                        out.append((lab, {e: s * k, o: so * 0.3 * k}))
        else:
            for s in (1, -1):
                out.append((f"{'+' if s > 0 else '-'}{e}", {e: s * k}))
    return out


def strength_combos(ctype, f1=0.5, rho=1.0, Ca=0.0, I=1.0, orthogonal=False,
                    omega0=None, ev_senses=(1, -1)):
    """NSCP 2015 Section 203.3.1 (+203.5 when omega0 is given).  Returns a list of
    {"name", "eq", "factors": {case: factor}, "seismic", "wind"}."""
    g = _by_type(ctype)
    D, L, H, F, T = g.get("D"), g.get("L"), g.get("H"), g.get("F"), g.get("T")
    LrR = [("Lr", g["Lr"])] if g.get("Lr") else []
    if g.get("R"):
        LrR.append(("R", g["R"]))
    W, E = g.get("W", []), g.get("E", [])
    ev = 0.5 * Ca * I
    out = []

    def combo(eq, text, fac, seismic=False, wind=False):
        clean = {c: round(v, 6) for c, v in fac.items() if abs(v) > 1e-12}
        out.append({"eq": eq, "name": text, "factors": clean, "seismic": seismic, "wind": wind,
                    "kind": "strength"})

    # 203-1
    f = {}
    _add(f, D, 1.4); _add(f, F, 1.4)
    combo("203-1", "1.4(D+F)", f)
    # 203-2
    for tag, lr in (LrR or [(None, None)]):
        f = {}
        _add(f, D, 1.2); _add(f, F, 1.2); _add(f, T, 1.2)
        _add(f, L, 1.6); _add(f, H, 1.6); _add(f, lr, 0.5)
        combo("203-2", "1.2(D+F+T)+1.6(L+H)" + (f"+0.5{tag}" if tag else ""), f)
    # 203-3
    for tag, lr in (LrR or [(None, None)]):
        base = {}
        _add(base, D, 1.2); _add(base, lr, 1.6)
        pre = "1.2D" + (f"+1.6{tag}" if tag else "")
        if L:
            f = dict(base); _add(f, L, f1)
            combo("203-3", f"{pre}+{f1:g}L", f)
        for w in W:
            for s in (1, -1):
                f = dict(base); f[w] = f.get(w, 0.0) + 0.5 * s
                combo("203-3", f"{pre}{'+' if s > 0 else '-'}0.5{w}", f, wind=True)
    # 203-4
    for tag, lr in (LrR or [(None, None)]):
        for w in W:
            for s in (1, -1):
                f = {}
                _add(f, D, 1.2); _add(f, L, f1); _add(f, lr, 0.5)
                f[w] = f.get(w, 0.0) + 1.0 * s
                combo("203-4", f"1.2D{'+' if s > 0 else '-'}1.0{w}+{f1:g}L"
                      + (f"+0.5{tag}" if tag else ""), f, wind=True)
    # 203-5 and 203-7 with E = rho Eh + Ev
    for lab, eh in horizontal_E_variants(E, rho, orthogonal):
        for sv in ev_senses:
            f = {}
            _add(f, D, 1.2 + sv * ev); _add(f, L, f1)
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            evt = f"{'+' if sv > 0 else '-'}Ev" if ev else ""
            combo("203-5", f"1.2D{evt}+{f1:g}L{lab}", f, seismic=True)
            if not ev:
                break
    for w in W:
        for s in (1, -1):
            f = {}
            _add(f, D, 0.9); _add(f, H, 1.6)
            f[w] = f.get(w, 0.0) + 1.0 * s
            combo("203-6", f"0.9D{'+' if s > 0 else '-'}1.0{w}" + ("+1.6H" if H else ""), f, wind=True)
    for lab, eh in horizontal_E_variants(E, rho, orthogonal):
        for sv in ev_senses:
            f = {}
            _add(f, D, 0.9 + sv * ev); _add(f, H, 1.6)
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            evt = f"{'+' if sv > 0 else '-'}Ev" if ev else ""
            combo("203-7", f"0.9D{evt}{lab}" + ("+1.6H" if H else ""), f, seismic=True)
            if not ev:
                break
    # 203-19 / 203-20 (only where Section 208 calls for Em)
    if omega0:
        for lab, eh in horizontal_E_variants(E, 1.0, orthogonal, factor=omega0):
            f = {}
            _add(f, D, 1.2); _add(f, L, f1)
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            combo("203-19", f"1.2D+{f1:g}L+Em({lab}, Omega0={omega0:g})", f, seismic=True)
            f = {}
            _add(f, D, 0.9)
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            combo("203-20", f"0.9D+Em({lab}, Omega0={omega0:g})", f, seismic=True)
    return _dedupe(out)


def service_combos(ctype, orthogonal=False, alternate=False, stability_rows=True):
    """NSCP 2015 Section 203.4.1 basic set (+ Section 203.4.2 alternate set when
    alternate=True).  stability_rows adds the 0.6D rows 203-14/203-15 to the basic set for
    overturning / sliding / uplift ONLY (vault Design Procedures/02: the 0.6D rows are what
    strip the restoring dead load).  Each combo carries `one_third` = True where a
    one-third allowable-stress increase is permitted (alternate set with W or E)."""
    g = _by_type(ctype)
    D, L, H, F, T = g.get("D"), g.get("L"), g.get("H"), g.get("F"), g.get("T")
    LrR = [("Lr", g["Lr"])] if g.get("Lr") else []
    if g.get("R"):
        LrR.append(("R", g["R"]))
    W, E = g.get("W", []), g.get("E", [])
    out = []

    def combo(eq, text, fac, seismic=False, wind=False, one_third=False, use="bearing"):
        clean = {c: round(v, 6) for c, v in fac.items() if abs(v) > 1e-12}
        out.append({"eq": eq, "name": text, "factors": clean, "seismic": seismic, "wind": wind,
                    "kind": "service", "one_third": one_third, "use": use})

    def base(dk=1.0):
        f = {}
        _add(f, D, dk); _add(f, H, 1.0); _add(f, F, 1.0)
        return f

    if not alternate:
        f = {}
        _add(f, D, 1.0); _add(f, F, 1.0)
        combo("203-8", "D+F", f)
        f = base(); _add(f, L, 1.0); _add(f, T, 1.0)
        combo("203-9", "D+H+F+L+T", f)
        for tag, lr in LrR:
            f = base(); _add(f, lr, 1.0)
            combo("203-10", f"D+H+F+{tag}", f)
        for tag, lr in (LrR or [(None, None)]):
            f = base(); _add(f, L, 0.75); _add(f, T, 0.75); _add(f, lr, 0.75)
            combo("203-11", "D+H+F+0.75(L+T" + (f"+{tag}" if tag else "") + ")", f)
        for w in W:
            for s in (1, -1):
                f = base(); f[w] = f.get(w, 0.0) + 0.6 * s
                combo("203-12", f"D+H+F{'+' if s > 0 else '-'}0.6{w}", f, wind=True)
        for lab, eh in horizontal_E_variants(E, 1.0, orthogonal, factor=1.0 / 1.4):
            f = base()
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            combo("203-12", f"D+H+F+({lab})/1.4", f, seismic=True)
        if stability_rows:
            for w in W:
                for s in (1, -1):
                    f = {}
                    _add(f, D, 0.6); _add(f, H, 1.0); f[w] = f.get(w, 0.0) + 0.6 * s
                    combo("203-14", f"0.6D{'+' if s > 0 else '-'}0.6{w}+H", f, wind=True,
                          use="stability")
            for lab, eh in horizontal_E_variants(E, 1.0, orthogonal, factor=1.0 / 1.4):
                f = {}
                _add(f, D, 0.6); _add(f, H, 1.0)
                for c, k in eh.items():
                    f[c] = f.get(c, 0.0) + k
                combo("203-15", f"0.6D+({lab})/1.4+H", f, seismic=True, use="stability")
    else:
        for tag, lr in (LrR or [(None, None)]):
            for w in W:
                for s in (1, -1):
                    f = base(); _add(f, L, 0.75); _add(f, lr, 0.75); f[w] = f.get(w, 0.0) + 0.75 * 0.6 * s
                    combo("203-13", f"D+H+F+0.75(L" + (f"+{tag}" if tag else "")
                          + f"{'+' if s > 0 else '-'}0.6{w})", f, wind=True, one_third=True)
            for lab, eh in horizontal_E_variants(E, 1.0, orthogonal, factor=0.75 / 1.4):
                f = base(); _add(f, L, 0.75); _add(f, lr, 0.75)
                for c, k in eh.items():
                    f[c] = f.get(c, 0.0) + k
                combo("203-13", f"D+H+F+0.75(L" + (f"+{tag}" if tag else "") + f"+({lab})/1.4)",
                      f, seismic=True, one_third=True)
        for w in W:
            for s in (1, -1):
                f = {}
                _add(f, D, 0.6); _add(f, H, 1.0); f[w] = f.get(w, 0.0) + 0.6 * s
                combo("203-14", f"0.6D{'+' if s > 0 else '-'}0.6{w}+H", f, wind=True, one_third=True)
        for lab, eh in horizontal_E_variants(E, 1.0, orthogonal, factor=1.0 / 1.4):
            f = {}
            _add(f, D, 0.6); _add(f, H, 1.0)
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            combo("203-15", f"0.6D+({lab})/1.4+H", f, seismic=True, one_third=True)
        for tag, lr in (LrR or [(None, None)]):
            f = {}
            _add(f, D, 1.0); _add(f, L, 1.0); _add(f, lr, 1.0)
            combo("203-16", "D+L" + (f"+{tag}" if tag else ""), f)
        for w in W:
            for s in (1, -1):
                f = {}
                _add(f, D, 1.0); _add(f, L, 1.0); f[w] = f.get(w, 0.0) + 0.6 * s
                combo("203-17", f"D+L{'+' if s > 0 else '-'}0.6{w}", f, wind=True, one_third=True)
        for lab, eh in horizontal_E_variants(E, 1.0, orthogonal, factor=1.0 / 1.4):
            f = {}
            _add(f, D, 1.0); _add(f, L, 1.0)
            for c, k in eh.items():
                f[c] = f.get(c, 0.0) + k
            combo("203-18", f"D+L+({lab})/1.4", f, seismic=True, one_third=True)
    return _dedupe(out)


def _dedupe(combos):
    seen, out = set(), []
    for c in combos:
        key = (c["kind"], c.get("use"), tuple(sorted(c["factors"].items())))
        if key in seen or not c["factors"]:
            continue
        seen.add(key)
        out.append(c)
    for i, c in enumerate(out, 1):
        c["id"] = f"{'U' if c['kind'] == 'strength' else 'S'}{i:02d}"
    return out


def apply(combo, cases):
    """Factored force set: sum over cases of factor x case forces.  cases: {case: {key: v}}.
    Keys missing from a case count as zero; a case named in the combo but absent from
    `cases` raises (no silent zero)."""
    out = {}
    for c, k in combo["factors"].items():
        if c not in cases:
            raise KeyError(f"combination {combo['id']} ({combo['name']}) needs load case {c!r}")
        for key, v in cases[c].items():
            if isinstance(v, (int, float)):
                out[key] = out.get(key, 0.0) + k * v
    return out


def settings(spec):
    """Normalise the 'loads' block of an input: f1, rho, Ca, I, orthogonal, omega0."""
    spec = spec or {}
    f1 = spec.get("f1", 0.5)
    if spec.get("public_assembly") or spec.get("garage") or spec.get("L_over_4_8kPa"):
        f1 = 1.0
    return {"f1": float(f1), "rho": float(spec.get("rho", 1.0)), "Ca": float(spec.get("Ca", 0.0)),
            "I": float(spec.get("I", 1.0)), "orthogonal": bool(spec.get("orthogonal", False)),
            "omega0": spec.get("omega0"), "alternate_asd": bool(spec.get("alternate_asd", False)),
            "stability_rows": bool(spec.get("stability_rows", True))}


def table(combos):
    """Markdown table of a combination list."""
    rows = ["| ID | NSCP Eq. | Combination | Factors |", "|---|---|---|---|"]
    for c in combos:
        fac = ", ".join(f"{k} {v:+.4g}" for k, v in c["factors"].items())
        rows.append(f"| {c['id']} | {c['eq']} | {c['name']} | {fac} |")
    return "\n".join(rows)
