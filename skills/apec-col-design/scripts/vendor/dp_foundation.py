"""
dp_foundation.py — the PYTHON HALF of the "MIDAS + Python" spread-footing procedure.

MIDAS does the analysis.  This module does every acceptance check, twice where the
two governing documents disagree, and refuses where the vault cannot support an
answer.

    Companion notes (Design Procedures (MIDAS + Python)/):
      01 - Foundation Design Route Map ... Service-Factored Split
      02 - Stability - Sliding, Overturning & Uplift
      03 - Bearing Pressure & Settlement
      04 - Shear & Flexure Design of Spread Footings
      05 - Crack Control & Serviceability

UNITS - SI throughout, and stated in every docstring.
    force  kN          moment  kN-m        stress/pressure  kPa for soil, MPa for concrete
    length m for footing plan/statics, mm for section geometry and reinforcement
    area   m2 for soil bearing, mm2 for reinforcement
Every function's docstring names its own units.  Nothing here converts silently.

CITATION FORMAT - as the vault requires: file, clause, printed page.  Every function
that implements a code provision carries its citation in its docstring.  Page numbers
are PRINTED pages (folio `N-M` for NSCP).  Every citation was taken from the notes
listed above; none was invented here.

THREE HONESTY RULES, ENFORCED IN CODE, NOT IN COMMENTS
  1. NOT VAULT-CITED values never acquire a default.
       - `FS` for sliding, overturning and uplift is a REQUIRED argument with no
         default, and every result it touches carries the NOT_CITED flag.  NSCP
         delegates the factor of safety to the geotechnical report (§304.1(e),
         folio `3-12`) and ACI 318 prints none at all - verified negative over both
         editions, note 02 §2.
  2. NO SETTLEMENT LIMIT EXISTS in either code.  `settlement_report()` refuses to
     return a pass/fail; it returns the value and says where the criterion must come
     from.  Verified negative on ACI 318-25M and on NSCP Chapters 3 and 4, note 03 §4.
  3. EVERY NSCP-SOURCED CONSTANT carries the marker
     "OCR-transcribed, not visually confirmed (2026-08-25)" in the docstring that
     uses it.  NSCP 2015 is an image-only scan; no page of it may be quoted from a
     text search.

DIVERGENCES - both codes are computed and both are returned, never averaged.  The
five live ones in this module:
    one-way V_c        ACI 318-25M Table 22.5.5.1 (lambda_s, rho_w) vs NSCP flat 0.17
    two-way v_c        lambda_s present in ACI, absent in NSCP
    phi transition     ACI eps_ty+0.003 vs NSCP fixed 0.005
    A_s,min            ACI flat 0.0018 vs NSCP two-tier Table 407.6.1.1/408.6.1.1
    S&T steel          ACI flat 0.0018 vs NSCP retained pre-2019 two-tier table
In PH practice NSCP 2015 governs.  ACI 318-25M enters when a client or peer reviewer
asks for the current ACI edition; say which one you designed to, on the sheet.

DEPENDENCIES - Python 3 standard library only.  numpy is not imported: these have to
run anywhere, including a site laptop with a bare interpreter.

RUN     python3 dp_foundation.py --selftest      (exits non-zero if any guard fails)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from math import sqrt, isclose

__all__ = [
    "Code", "Loads", "Result", "Refusal",
    "nscp_strength_combinations", "nscp_service_combinations",
    "base_area_required", "bearing_pressure", "presumptive_bearing",
    "settlement_report",
    "check_sliding", "check_overturning", "check_uplift", "stability_load_case",
    "vc_one_way", "vc_two_way", "critical_sections", "flexural_design",
    "min_flexural_steel", "band_reinforcement", "bearing_strength_concrete",
    "max_bar_spacing", "shrinkage_temperature_steel", "crack_width_limit",
]

# --------------------------------------------------------------------------- flags
NOT_CITED = "(not vault-cited)"
NSCP_OCR = "OCR-transcribed, not visually confirmed (2026-08-25)"
REFUSAL = "The reference folder does not contain enough basis to support this answer."

#: Table 20.5.1.3.1, ACI 318-25M printed 421 - "Cast against and permanently in
#: contact with ground / All / All -> 75 mm".  NSCP twin Table 420.6.1.3.1, folio
#: `4-136`, also 75 mm.  Foundations are routed here by §13.2.9.1, printed 211.
COVER_CAST_AGAINST_GROUND_MM = 75.0
COVER_EXPOSED_LARGE_BAR_MM = 50.0     # No. 19 - No. 57, exposed to weather / ground
COVER_EXPOSED_SMALL_BAR_MM = 40.0     # No. 16 and smaller, exposed to weather / ground

ES_REBAR_MPA = 200000.0               # E_s for deformed reinforcement, MPa


# ------------------------------------------------------------- guard bookkeeping
# Vault convention: the script counts its own assertion guards and prints the total.
# DISTINCT guards are counted by tag; EXECUTIONS count every time a tag is evaluated,
# so a check run 50 times inside a loop is 1 distinct guard and 50 executions.
_GUARDS: dict[str, int] = {}


def guard(tag: str, condition: bool, message: str = "") -> bool:
    """Register and evaluate one assertion guard.  Raises AssertionError on failure.

    tag        stable identifier - one tag is one DISTINCT guard however often it runs
    condition  the thing that must be true
    message    what to print when it is not
    """
    _GUARDS[tag] = _GUARDS.get(tag, 0) + 1
    if not condition:
        raise AssertionError(f"GUARD FAILED [{tag}] {message}")
    return True


def guard_totals() -> tuple[int, int]:
    """Return (distinct guards, guard executions) recorded so far."""
    return len(_GUARDS), sum(_GUARDS.values())


def guard_table() -> str:
    """Per-tag guard ledger, most-executed first."""
    rows = sorted(_GUARDS.items(), key=lambda kv: (-kv[1], kv[0]))
    out = [f"  {'guard tag':<44s} {'executions':>10s}"]
    out += [f"  {t:<44s} {n:>10d}" for t, n in rows]
    return "\n".join(out)


# ------------------------------------------------------------------- basic types
class Code:
    """Which document a divergent check is being answered against.

    Plain string constants rather than enum.Enum so that the caller may pass either
    `Code.NSCP2015` or the bare string "NSCP2015" - both work.
    """
    NSCP2015 = "NSCP2015"
    ACI318_25M = "ACI318-25M"
    BOTH = "BOTH"

    ALL = (NSCP2015, ACI318_25M)

    @staticmethod
    def check(code: str) -> str:
        if code not in (Code.NSCP2015, Code.ACI318_25M, Code.BOTH):
            raise ValueError(
                f"unknown code {code!r}; use one of "
                f"{Code.NSCP2015!r}, {Code.ACI318_25M!r}, {Code.BOTH!r}")
        return code


@dataclass(frozen=True)
class Loads:
    """One load resultant at the underside of the footing, tagged with its LEVEL.

    UNITS   P, Vx, Vy in kN (P positive downward/compression); Mx, My in kN-m.
            Mx bends about the x-axis and therefore acts in the B (short) direction;
            My acts in the L direction.

    ==THE LEVEL TAG IS THE WHOLE POINT OF THIS CLASS.==  Note 01's finding is that
    the service and factored sets are two different bookkeeping columns and mixing
    them is the failure mode:

      SERVICE   sizes the base area against the soil.
        Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
        Vol.1.pdf`, §413.3.1.1, p. `4-84` - base area from UNFACTORED forces.
        OCR-transcribed, not visually confirmed (2026-08-25).
        Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §301.3, p. `3-3` and §304.3,
        p. `3-13` - allowable values pair with the §203.4 ASD combinations.
        OCR-transcribed, not visually confirmed (2026-08-25).

      FACTORED  designs the concrete.
        Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
        §13.2.6.3, p. 208 - factored loads and corresponding induced reactions.
        Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §413.2.6.1, folio `4-83`.
        OCR-transcribed, not visually confirmed (2026-08-25).

    Adding a service set to a factored set raises.  There is no `.to_factored()` and
    there never will be: the factors live in the combination tables, not on a load.
    """
    P: float
    Vx: float = 0.0
    Vy: float = 0.0
    Mx: float = 0.0
    My: float = 0.0
    level: str = "service"
    combo: str = ""

    SERVICE = "service"
    FACTORED = "factored"

    def __post_init__(self) -> None:
        if self.level not in (Loads.SERVICE, Loads.FACTORED):
            raise ValueError(
                f"level must be {Loads.SERVICE!r} or {Loads.FACTORED!r}, "
                f"got {self.level!r}")

    def __add__(self, other: "Loads") -> "Loads":
        if not isinstance(other, Loads):
            return NotImplemented
        guard("loads.no_level_mixing", self.level == other.level,
              f"refusing to add a {self.level} set to a {other.level} set "
              "- note 01 §1: gross for sizing, net for flexure and shear, and the "
              "two columns never meet")
        return Loads(self.P + other.P, self.Vx + other.Vx, self.Vy + other.Vy,
                     self.Mx + other.Mx, self.My + other.My, self.level,
                     f"{self.combo}+{other.combo}".strip("+"))

    @property
    def H(self) -> float:
        """Horizontal resultant, kN."""
        return sqrt(self.Vx ** 2 + self.Vy ** 2)


def require_service(loads: Loads, what: str) -> None:
    """Refuse a factored set where the Code demands an unfactored one."""
    guard("require_service_level", loads.level == Loads.SERVICE,
          f"{what} must be run on SERVICE loads (NSCP §413.3.1.1, folio `4-84`, "
          f"{NSCP_OCR}); got a {loads.level} set")


def require_factored(loads: Loads, what: str) -> None:
    """Refuse a service set where the Code demands a factored one."""
    guard("require_factored_level", loads.level == Loads.FACTORED,
          f"{what} must be run on FACTORED loads (ACI 318-25M §13.2.6.3, p. 208; "
          f"NSCP §413.2.6.1, folio `4-83`, {NSCP_OCR}); got a {loads.level} set")


@dataclass
class Result:
    """One reported quantity, with its limit, its verdict and its provenance.

    `passed is None` means DELIBERATELY NO VERDICT - the criterion has no basis in
    `vault/reference/`.  Settlement is the standing example.
    """
    name: str
    value: float
    units: str = ""
    limit: float | None = None
    passed: bool | None = None
    basis: str = ""
    flags: tuple[str, ...] = ()

    def __str__(self) -> str:
        lim = "-" if self.limit is None else f"{self.limit:,.4g}"
        verdict = {True: "PASS", False: "FAIL", None: "NO VERDICT"}[self.passed]
        flags = ("  " + " ".join(self.flags)) if self.flags else ""
        return (f"{self.name:<46s} {self.value:>14,.4f} {self.units:<8s} "
                f"limit {lim:>12s}  {verdict:<10s}{flags}")


@dataclass
class Refusal:
    """A refusal to answer, carrying the vault's exact sentence.

    Returned - never silently replaced by a default - wherever `vault/reference/`
    cannot support the answer.
    """
    subject: str
    sentence: str = REFUSAL
    pointers: tuple[str, ...] = ()

    def __bool__(self) -> bool:      # a Refusal is never truthy
        return False

    def __str__(self) -> str:
        head = f"REFUSAL - {self.subject}\n  {self.sentence}"
        if self.pointers:
            head += "\n" + "\n".join(f"    - {p}" for p in self.pointers)
        return head


# ===========================================================================
# 1 - LOAD COMBINATIONS                                            (note 01 §2)
# ===========================================================================

def nscp_strength_combinations(*, service_level_wind: bool,
                               L_may_be_reduced: bool = False) -> list[tuple[str, dict]]:
    """NSCP Table 405.3.1 strength combinations, as data.

    UNITS - dimensionless load factors.  Keys are load symbols: D, L, LrR (= L_r or
    R), W, E, T, H.  "(Lr or R)" is carried as one symbol LrR because the Code prints
    it as one term.

    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §405.3.1 and Table 405.3.1, p. `4-34`.
    OCR-transcribed, not visually confirmed (2026-08-25).

    THE RIDER THAT GETS FORGOTTEN - §405.3.5, same page, same OCR marker:
    "If wind load W is based on service-level loads, 1.6W shall be used in place of
    1.0W in Eqs. 405.3.1d and 405.3.1f, and 0.8W in place of 0.5W in Eq. 405.3.1c."
    `service_level_wind` is therefore a REQUIRED keyword: if your wind case came out
    of an ASD wind calculation, the 1.0W rows in the table are wrong until scaled.

    §405.3.3 (p. `4-34`, same OCR marker) permits L to be reduced to 0.5 in (c), (d)
    and (e), EXCEPT for garages, areas of public assembly, and where L > 4.8 kPa -
    `L_may_be_reduced` applies that reduction and the caller owns the exception test.

    §405.3.6 - the load factor on T shall not be less than 1.0.
    §405.3.8 - lateral earth pressure H: 1.6 where H adds to the effect, 0.9 where the
    load is permanent and counteracts, and H omitted where it is non-permanent and
    counteracts.  Both are returned by `nscp_H_and_T_factors()` rather than baked in,
    because the sign of H's contribution is a per-case decision.

    Returns a list of (equation label, {symbol: factor}) in Table order.  Eq. (c) is
    expanded into its two printed alternatives.
    """
    w_c = 0.8 if service_level_wind else 0.5      # §405.3.5 rider on Eq. (c)
    w_df = 1.6 if service_level_wind else 1.0     # §405.3.5 rider on Eqs. (d) and (f)
    L_cde = 0.5 if L_may_be_reduced else 1.0      # §405.3.3

    rider = "1.6W/0.8W per §405.3.5" if service_level_wind else "W already strength-level"
    combos: list[tuple[str, dict]] = [
        (f"405.3.1a  1.4D", {"D": 1.4}),
        (f"405.3.1b  1.2D + 1.6L + 0.5(Lr or R)", {"D": 1.2, "L": 1.6, "LrR": 0.5}),
        (f"405.3.1c-L  1.2D + 1.6(Lr or R) + {L_cde}L   [{rider}]",
         {"D": 1.2, "LrR": 1.6, "L": L_cde}),
        (f"405.3.1c-W  1.2D + 1.6(Lr or R) + {w_c}W   [{rider}]",
         {"D": 1.2, "LrR": 1.6, "W": w_c}),
        (f"405.3.1d  1.2D + {w_df}W + {L_cde}L + 0.5(Lr or R)   [{rider}]",
         {"D": 1.2, "W": w_df, "L": L_cde, "LrR": 0.5}),
        (f"405.3.1e  1.2D + 1.0E + {L_cde}L", {"D": 1.2, "E": 1.0, "L": L_cde}),
        (f"405.3.1f  0.9D + {w_df}W   [{rider}]", {"D": 0.9, "W": w_df}),
        (f"405.3.1g  0.9D + 1.0E", {"D": 0.9, "E": 1.0}),
    ]
    return combos


def nscp_H_and_T_factors() -> dict:
    """§405.3.6 and §405.3.8 riders on T and H, returned rather than baked in.

    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §§405.3.6, 405.3.8, p. `4-34`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    """
    return {
        "T_min_factor": 1.0,
        "H_adds_to_effect": 1.6,
        "H_permanent_and_counteracts": 0.9,
        "H_non_permanent_and_counteracts": "OMIT H entirely",
    }


def nscp_service_combinations() -> dict:
    """NSCP §203.4 allowable-stress combinations - the set Chapter 4 does not contain.

    UNITS - dimensionless load factors, and a printed-text form for the two the OCR
    could not fully resolve.

    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §203.4, p. `2-11`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Note 01 §2.3 also corrects the register: the Chapter 2 offset in the front half is
    PDF - 55, not the -52/-53 the register carries; `2-11` = PDF 66.

    ==NSCP Chapter 4 contains NO ASD combinations.==  §405.3 is strength design only
    and §405.2.2 defers the loads themselves to the general building code, so the
    service combinations that §413.3.1.1 requires in order to size a base area are in
    Chapter 2.  An engineer who stays inside Chapter 4 cannot size a footing.
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §405.3 / §405.2.2, p. `4-34`.
    OCR-transcribed, not visually confirmed (2026-08-25).

    Two honesty flags travel with the return value and are not removable:
      * (203-11)'s bracket contents read ambiguously under OCR.  The transcription is
        returned as printed text, NOT as factors, so nothing can consume it by accident.
      * (203-13), (203-16), (203-17) and (203-18) were NOT TRANSCRIBED by the research
        behind note 01.  They are listed as absent, not guessed.

    The one-third allowable-stress increase attaches to the ALTERNATE basic set only,
    never to the basic set - Table 304-1's general footnote records the same allowance.
    """
    return {
        "basic": [
            ("203-8   D + F", {"D": 1.0, "F": 1.0}),
            ("203-9   D + H + F + L", {"D": 1.0, "H": 1.0, "F": 1.0, "L": 1.0}),
            ("203-10  D + H + F + (Lr or R)",
             {"D": 1.0, "H": 1.0, "F": 1.0, "LrR": 1.0}),
            ("203-12  D + H + F + (0.6W or E/1.4)",
             {"D": 1.0, "H": 1.0, "F": 1.0, "W": 0.6, "E": 1.0 / 1.4}),
        ],
        "basic_untranscribed": [
            ("203-11  D + H + F + 0.75[L + T (Lr or R)]",
             "as printed text only - the bracket contents read ambiguously under OCR; "
             "verify against the printed page before use"),
        ],
        "alternate_basic": [
            ("203-14  0.6D + 0.6W + H", {"D": 0.6, "W": 0.6, "H": 1.0}),
            ("203-15  0.6D + E/1.4 + H", {"D": 0.6, "E": 1.0 / 1.4, "H": 1.0}),
        ],
        "alternate_basic_not_transcribed": ("203-13", "203-16", "203-17", "203-18"),
        "one_third_increase": (
            "permitted for the ALTERNATE basic set only (§203.4); Table 304-1's "
            "general footnote records the same allowance for combinations including "
            "wind or earthquake.  The digest does not resolve which of Table 304-1's "
            "columns the footnote reaches - verify on the printed page."),
        "flags": (NSCP_OCR,),
    }


# ===========================================================================
# 2 - BEARING AGAINST THE SOIL                                     (note 03)
# ===========================================================================

def base_area_required(P_service: float, q_allow: float) -> Result:
    """Base area from UNFACTORED load and the permissible soil pressure.

    UNITS   P_service kN (service-level vertical resultant, GROSS - it must already
            include the footing self-weight and the backfill over it, because that is
            what the soil feels);  q_allow kPa;  returns m2.

    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §413.3.1.1, p. `4-84`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    ==NSCP says "unfactored" in MANDATORY text; ACI 318-25M §13.3.1.1 (printed
    211-212) does not - in ACI the only normative "unfactored" footing-sizing clause
    is §14.3.2.2 (printed 223) and that is PLAIN CONCRETE ONLY.  In PH practice the
    governing code therefore states the service-load sizing rule directly, which is
    the cleaner basis to cite.==
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §414.3.2.2, folio `4-87` - "Base area
    of footing shall be determined from unfactored forces and moments transmitted by
    footing to soil and permissible soil pressure ...".
    OCR-transcribed, not visually confirmed (2026-08-25).
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    R13.2.6.1, p. 208 - base area from allowable geotechnical strength and
    SERVICE-LEVEL load combinations.  Non-mandatory commentary.
    Basis: `Manuals/Wight MacGregor - Reinforced Concrete Mechanics and Design
    7th.pdf`, Eq. (15-6), p. 833 - "where D and L refer to the unfactored service
    dead and live loads."  (Register correction from note 03 §3.2: Eq. (15-6) is on
    printed 833; Eqs. (15-7) and (15-8) are on printed 834.  The vault's old
    "Eqs. 15-6 to 15-8, p. 833" is wrong.)

    The one-third increase of Eq. (15-7)'s `1.33 q_a` is NOT applied here.  Under NSCP
    the equivalent permission attaches to the §203.4 ALTERNATE basic set only; apply
    it deliberately by passing an already-increased `q_allow`, and say so on the sheet.
    """
    if q_allow <= 0:
        raise ValueError("q_allow must be positive, kPa")
    guard("base_area.positive_service_load", P_service > 0,
          "net downward service load required to size a base area")
    A = P_service / q_allow
    return Result("required base area A = P_service / q_allow", A, "m2",
                  basis="NSCP §413.3.1.1 folio `4-84`; W&McG Eq. (15-6) p. 833",
                  flags=(NSCP_OCR, "GROSS service pressure - self-weight and "
                                   "overburden included"))


def bearing_pressure(P: float, Mx: float, My: float, B: float, L: float,
                     *, q_allow: float | None = None) -> dict:
    """Biaxial contact pressure on a rigid rectangular base, with an explicit kern test.

    UNITS   P kN (service, gross, positive downward); Mx, My kN-m; B, L m.
            Returns q in kPa.  B is the short plan dimension convention used
            throughout this module; Mx is the moment producing eccentricity across B.

        q = P/(B L) * (1 +- 6 e_B/B +- 6 e_L/L),     e_B = Mx/P,  e_L = My/P

    ==The linear expression is elementary statics and is (not vault-cited).==  Note 02
    §4.1 records that Wight & MacGregor's own linear-distribution expression is
    Eq. (15-4), printed 831, but the research did NOT transcribe it - so the equation
    is used here as statics, not quoted as a code equation.

    WHAT *IS* CITED is the kern rule, which is the only thing that makes the linear
    expression legitimate:
    Basis: `Manuals/Wight MacGregor - Reinforced Concrete Mechanics and Design
    7th.pdf`, Eq. (15-5), p. 831 - "For a rectangular footing, this occurs when the
    eccentricity exceeds e_k = l/6 or e_k = b/6 ... referred to as the kern distance.
    Loads applied within the kern ... will cause compression over the entire area."

    Outside the kern part of the base LIFTS OFF and this expression is no longer the
    pressure distribution - it returns a fictitious tension.  That is exactly why
    q_min <= 0 is the uplift trigger and why `in_kern` is reported, not inferred.

    Basis: `ACI 318-25M ...pdf`, §13.3.1.2, p. 212; NSCP twin §413.3.1.2, folio
    `4-84`, identical wording and value.  OCR-transcribed, not visually confirmed
    (2026-08-25).

    Returns a dict; `results` holds the Result rows for printing.
    """
    if B <= 0 or L <= 0:
        raise ValueError("B and L must be positive, m")
    guard("bearing.positive_vertical_load", P > 0,
          "net vertical load is zero or uplift - bearing pressure undefined; "
          "run check_uplift() instead")
    A = B * L
    e_B = abs(Mx) / P
    e_L = abs(My) / P
    q_avg = P / A
    q_max = q_avg * (1.0 + 6.0 * e_B / B + 6.0 * e_L / L)
    q_min = q_avg * (1.0 - 6.0 * e_B / B - 6.0 * e_L / L)
    kern_ratio = e_B / B + e_L / L                 # <= 1/6 keeps full contact
    in_kern = kern_ratio <= 1.0 / 6.0 + 1e-12

    rows = [
        Result("eccentricity e_B = Mx/P", e_B, "m",
               limit=B / 6.0, passed=e_B <= B / 6.0 + 1e-12,
               basis="W&McG Eq. (15-5) p. 831 (kern e_k = b/6)"),
        Result("eccentricity e_L = My/P", e_L, "m",
               limit=L / 6.0, passed=e_L <= L / 6.0 + 1e-12,
               basis="W&McG Eq. (15-5) p. 831 (kern e_k = l/6)"),
        Result("kern ratio e_B/B + e_L/L", kern_ratio, "-",
               limit=1.0 / 6.0, passed=in_kern,
               basis="W&McG Eq. (15-5) p. 831",
               flags=() if in_kern else ("PARTIAL UPLIFT - the base lifts off; the "
                                         "linear q distribution below is FICTITIOUS "
                                         "and q_min is not a real tension",)),
        Result("q_min", q_min, "kPa", limit=0.0, passed=q_min > -1e-12,
               basis="full contact requires q_min >= 0"),
    ]
    if q_allow is not None:
        rows.append(Result("q_max vs allowable", q_max, "kPa", limit=q_allow,
                           passed=q_max <= q_allow,
                           basis="service combination - NSCP §304.3 folio `3-13`, "
                                 "§301.3 folio `3-3`; ACI R13.2.6.1 p. 208",
                           flags=(NSCP_OCR,)))
    return {"A": A, "e_B": e_B, "e_L": e_L, "q_avg": q_avg,
            "q_max": q_max, "q_min": q_min, "kern_ratio": kern_ratio,
            "in_kern": in_kern, "partial_uplift": not in_kern,
            "statics_flag": NOT_CITED + " - the linear q expression is statics; "
                            "W&McG Eq. (15-4) p. 831 was not transcribed",
            "results": rows}


# --- NSCP Table 304-1 --------------------------------------------------------
# Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines Vol.1.pdf`,
# Table 304-1 (§304.2), folio `3-13`.
# OCR-transcribed, not visually confirmed (2026-08-25).
# Rows 1-2 crop-confirmed at 550 dpi under multiple OCR configurations.
# ROWS 3-5 WERE READ AT 150 dpi ONLY - provisional, re-verify before relying on them.
_PROVISIONAL_150DPI = ("150 dpi read only - PROVISIONAL, re-verify at high "
                       "resolution before relying on this row")

TABLE_304_1: dict[int, dict] = {
    1: dict(material='"Intact" Tuffaceous Sandstone',
            q_allow_kPa=1000.0, lateral_bearing_kPa_per_m=300.0,
            sliding_coefficient=None, sliding_resistance_kPa=None,
            gate="UCT_min = 3 MPa and RQD >= 70", uct_min_MPa=3.0, rqd_min=70.0,
            width_increase_allowed=True, flags=()),
    2: dict(material='"Lightly Weathered" Tuffaceous Sandstone',
            q_allow_kPa=500.0, lateral_bearing_kPa_per_m=150.0,
            sliding_coefficient=None, sliding_resistance_kPa=None,
            gate="UCT_min = 1 MPa and RQD >= 50", uct_min_MPa=1.0, rqd_min=50.0,
            width_increase_allowed=True, flags=()),
    3: dict(material="Sandy Gravel and/or Gravel (GW, GP)",
            q_allow_kPa=100.0, lateral_bearing_kPa_per_m=30.0,
            sliding_coefficient=0.35, sliding_resistance_kPa=None,
            gate=None, uct_min_MPa=None, rqd_min=None,
            width_increase_allowed=True, flags=(_PROVISIONAL_150DPI,)),
    4: dict(material=("Well-graded Sand, Poorly-graded Sand, Silty Sand, Clayey "
                      "Sand, Silty Gravel, Clayey Gravel (SW, SP, SM, SC, GM, GC)"),
            q_allow_kPa=75.0, lateral_bearing_kPa_per_m=25.0,
            sliding_coefficient=0.25, sliding_resistance_kPa=None,
            gate=None, uct_min_MPa=None, rqd_min=None,
            width_increase_allowed=True, flags=(_PROVISIONAL_150DPI,)),
    5: dict(material="Clay, Sandy Clay, Silty Clay, Clayey Silt (CL, ML, MH, CH)",
            q_allow_kPa=50.0, lateral_bearing_kPa_per_m=15.0,
            sliding_coefficient=None, sliding_resistance_kPa=7.0,
            gate=None, uct_min_MPa=None, rqd_min=None,
            width_increase_allowed=False,
            flags=(_PROVISIONAL_150DPI,
                   "footnote c: no increase shall be allowed for an increase of "
                   "WIDTH - depth increments only")),
}

PRESUMPTIVE_MIN_WIDTH_MM = 300.0
PRESUMPTIVE_MIN_DEPTH_MM = 300.0
PRESUMPTIVE_INCREMENT_MM = 300.0
PRESUMPTIVE_INCREMENT_FRACTION = 0.20
PRESUMPTIVE_MAX_FACTOR = 3.0


def presumptive_bearing(soil_class: int, width_mm: float, depth_mm: float,
                        *, uct_MPa: float | None = None,
                        rqd_percent: float | None = None) -> dict:
    """NSCP Table 304-1 presumptive values, with the width/depth increase rule.

    UNITS   width_mm, depth_mm in mm (depth is INTO NATURAL GRADE);
            uct_MPa in MPa; rqd_percent in percent.  Returns kPa and kPa/m.

    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, Table 304-1 (§304.2), folio `3-13`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Rows 1-2 crop-confirmed at 550 dpi; ROWS 3-5 READ AT 150 dpi ONLY and returned
    with a PROVISIONAL flag that this function will not remove.

    THE GATE - §304.2, folio `3-13`, same OCR marker: the table is a fallback "when
    no exhaustive geotechnical site assessment and investigation is performed", and
    "Use of these values requires that the foundation design engineer has, at the
    least, carried out an inspection of the site".  "Mud, organic silt, organic clays,
    peat or unprepared fill shall not be assumed to have a presumptive load-bearing
    capacity" without substantiating data.

    THE INCREASE RULE - Table 304-1 general footnotes, folio `3-13`, same OCR marker:
    values are for footings of minimum 300 mm width and 300 mm depth into natural
    grade; "An increase of 20 % is allowed per additional 300 mm of width and/or
    depth, to a maximum of three times the designated value."
    Row 5 carries footnote c - "No increase shall be allowed for an increase of
    width" - so only depth increments are counted there.

    THE ROCK ROWS ARE A MATERIAL QUALIFICATION, NOT A BONUS.  Rows 1 and 2 state UCT
    and RQD inside the row, as conditions of membership in the class, so `uct_MPa` and
    `rqd_percent` are REQUIRED for those rows and have no default.  ==Quoting
    1,000 kPa without UCT >= 3 MPa and RQD >= 70 in hand is not a code-compliant use
    of Table 304-1 - it is a number taken out of a class the site has not been shown
    to belong to.==

    These are ALLOWABLE-STRESS values and pair only with the §203.4 service
    combinations - §301.3 folio `3-3` and §304.3 folio `3-13`, same OCR marker.  The
    one-third increase attaches to the ALTERNATE basic set only and is NOT applied
    here; it is returned as a permission for the caller to take deliberately.

    NSCP prescribes NO factor of safety - it delegates it.  §304.1(e), folio `3-12`,
    same OCR marker: the geotechnical report shall disclose the "Factor of Safety (FS)
    assumed".
    """
    if soil_class not in TABLE_304_1:
        raise ValueError(f"soil_class must be 1..5 (NSCP Table 304-1); got {soil_class}")
    row = TABLE_304_1[soil_class]
    flags = list(row["flags"]) + [NSCP_OCR]

    # --- the UCT / RQD gate on the two rock rows: evidenced, never defaulted -----
    if row["gate"] is not None:
        if uct_MPa is None or rqd_percent is None:
            raise ValueError(
                f"Table 304-1 row {soil_class} ({row['material']}) states "
                f"{row['gate']} INSIDE the row, as a condition of membership in the "
                "class.  uct_MPa and rqd_percent are required arguments for this row "
                "and have no default - supply the tested values or use a different row.")
        guard("presumptive.rock_uct_gate", uct_MPa >= row["uct_min_MPa"],
              f"row {soil_class} requires UCT >= {row['uct_min_MPa']} MPa; got {uct_MPa}")
        guard("presumptive.rock_rqd_gate", rqd_percent >= row["rqd_min"],
              f"row {soil_class} requires RQD >= {row['rqd_min']}; got {rqd_percent}")
        flags.append("UCT/RQD evidenced by the caller - record the test report, its "
                     "date and its author as a PROJECT FACT")

    # --- the +20 % per 300 mm rule, capped at 3x --------------------------------
    n_depth = max(0, int((depth_mm - PRESUMPTIVE_MIN_DEPTH_MM) // PRESUMPTIVE_INCREMENT_MM))
    if row["width_increase_allowed"]:
        n_width = max(0, int((width_mm - PRESUMPTIVE_MIN_WIDTH_MM) // PRESUMPTIVE_INCREMENT_MM))
    else:
        n_width = 0
        flags.append("footnote c - width increments SUPPRESSED for row 5")
    n = n_width + n_depth
    factor_uncapped = 1.0 + PRESUMPTIVE_INCREMENT_FRACTION * n
    factor = min(factor_uncapped, PRESUMPTIVE_MAX_FACTOR)
    guard("presumptive.increase_cap_3x", factor <= PRESUMPTIVE_MAX_FACTOR + 1e-12,
          "Table 304-1 footnote caps the increase at three times the designated value")

    below_min = width_mm < PRESUMPTIVE_MIN_WIDTH_MM or depth_mm < PRESUMPTIVE_MIN_DEPTH_MM
    if below_min:
        flags.append("BELOW the 300 mm minimum width and/or depth the table is "
                     "written for - Table 304-1 gives no value here; no reduction "
                     "rule is printed and none is invented")

    q_base = row["q_allow_kPa"]
    return {
        "soil_class": soil_class,
        "material": row["material"],
        "q_allow_base_kPa": q_base,
        "increments_width": n_width,
        "increments_depth": n_depth,
        "increase_factor_uncapped": factor_uncapped,
        "increase_factor": factor,
        "capped_at_3x": factor_uncapped > PRESUMPTIVE_MAX_FACTOR,
        "q_allow_kPa": q_base * factor,
        "lateral_bearing_kPa_per_m": row["lateral_bearing_kPa_per_m"],
        "sliding_coefficient": row["sliding_coefficient"],
        "sliding_resistance_kPa": row["sliding_resistance_kPa"],
        "gate": row["gate"],
        "one_third_increase": ("permitted with the §203.4 ALTERNATE basic "
                               "combinations including wind or earthquake - NOT "
                               "applied here.  The digest does not resolve which of "
                               "Table 304-1's columns the footnote reaches; verify "
                               "against the printed page."),
        "factor_of_safety": ("NSCP prescribes none - §304.1(e) folio `3-12` requires "
                             "the geotechnical report to STATE the FS assumed"),
        "flags": tuple(flags),
        "results": [
            Result(f"q_allow, Table 304-1 row {soil_class}", q_base * factor, "kPa",
                   basis="NSCP Table 304-1 (§304.2) folio `3-13`",
                   flags=tuple(flags)),
            Result("width/depth increase factor", factor, "-",
                   limit=PRESUMPTIVE_MAX_FACTOR, passed=True,
                   basis="Table 304-1 general footnote - +20 % per 300 mm, max 3x",
                   flags=(NSCP_OCR,)),
        ],
    }


def settlement_report(settlement_mm: float, *, source: str,
                      differential_mm: float | None = None,
                      criterion_mm: float | None = None,
                      criterion_source: str | None = None) -> dict:
    """Report a settlement.  ==This function REFUSES to pass or fail it.==

    UNITS   settlement_mm, differential_mm, criterion_mm in mm.
            `source` is a required string: whose number this is, from which report,
            of which revision and date.  A settlement is a PROJECT FACT.

    ==NO SETTLEMENT LIMIT EXISTS IN EITHER CODE.  Verified negative, both, each with
    its own control - note 03 §4.==

    ACI 318-25M: every occurrence of "settlement" is qualitative, differential
    settlement as a load effect T.  The closest clauses are
      Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
      §4.4.5, p. 60 - "Structural systems shall be designed to accommodate anticipated
      volume change and differential settlement."
      Basis: `ACI 318-25M ...pdf`, R4.4.5, p. 60 - "Geotechnical recommendations to
      allow for nominal values of differential settlement and heave are not normally
      included in design load combinations for ordinary building structures."
      Non-mandatory commentary.
    Control that proves the search works: `grep -c -i "Table 24.2.2"` (the DEFLECTION
    limit table) returns 6, so the method finds serviceability limit tables when they
    exist; the settlement-limit search returns 0.

    NSCP 2015: no numeric settlement limit in Chapter 3 or Chapter 4.  In Chapter 3
    settlement is a REPORTING requirement only -
      Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §303.7 - the report shall state the
      "Expected total and differential settlement".
      OCR-transcribed, not visually confirmed (2026-08-25).  The digest records the
      clause but NOT its folio, so no page is quoted.

    THE TRAP: NSCP §306.4 Method 2, folio `3-18`, prints "0.05 mm/kN of test load".
    That is a PILE LOAD-TEST allowable-capacity criterion, not a footing settlement
    limit, and must never be quoted as one.
    OCR-transcribed, not visually confirmed (2026-08-25).

    ==Therefore the 25 mm limit in common office use is (not vault-cited).==  If a
    criterion is supplied it is recorded, attributed, and reported alongside the value
    with the flag that it has no code basis - the comparison is printed, the VERDICT
    is not, because a verdict implies an authority that does not exist.

    And the MIDAS point: a Winkler spring model returns q/k_s, an elastic bedding
    deflection with no consolidation, no stratigraphy, no stress history and no
    coupling between footings.  It is not a settlement prediction.
    """
    if not source or not str(source).strip():
        raise ValueError("`source` is required - a settlement is a project fact and "
                         "must be attributed (who, which report, which revision, "
                         "what date)")
    rows = [
        Result("total settlement (reported)", settlement_mm, "mm",
               limit=criterion_mm, passed=None,
               basis="PROJECT FACT - " + source,
               flags=("NO CODE BASIS FOR ANY LIMIT - ACI 318-25M and NSCP 2015 both "
                      "verified negative (note 03 §4)", NOT_CITED)),
    ]
    if differential_mm is not None:
        rows.append(Result("differential settlement (reported)", differential_mm, "mm",
                           limit=None, passed=None,
                           basis="PROJECT FACT - " + source,
                           flags=("NO CODE BASIS FOR ANY LIMIT", NOT_CITED)))
    margin = None
    if criterion_mm is not None:
        margin = criterion_mm - settlement_mm
        if not criterion_source:
            raise ValueError(
                "a settlement criterion has NO code basis; if you supply one you must "
                "also supply `criterion_source` - who set it, and when.  NSCP "
                "§304.1(e) folio `3-12` and §303.7 make this the geotechnical "
                "engineer's number, not the structural engineer's.")
    return {
        "settlement_mm": settlement_mm,
        "differential_mm": differential_mm,
        "criterion_mm": criterion_mm,
        "criterion_source": criterion_source,
        "margin_mm": margin,
        "verdict": None,
        "refusal": Refusal(
            "settlement acceptance criterion",
            pointers=(
                "ACI 318-25M §4.4.5 / R4.4.5, printed 60 - qualitative only, no limit",
                "NSCP §303.7 - the geotechnical REPORT shall state expected total and "
                "differential settlement; the Code sets no limit "
                "(OCR-transcribed, not visually confirmed (2026-08-25); folio not "
                "recorded by the digest)",
                "NSCP §306.4 Method 2, folio `3-18`, 0.05 mm/kN is a PILE LOAD-TEST "
                "criterion and is NOT a footing settlement limit",
                "W&McG Ch. 9 serviceability table, p. 470 - 'about 3/4 in. in 25 ft' "
                "is a textbook TOLERANCE attributed to the authors, US-customary, and "
                "the source prints no SI equivalent - never a criterion",
                "The criterion must come from the GEOTECHNICAL REPORT, attributed and "
                "dated, and flagged (not vault-cited) wherever it drives acceptance",
            )),
        "results": rows,
        "flags": (NOT_CITED, NSCP_OCR),
    }


# ===========================================================================
# 3 - STABILITY: SLIDING, OVERTURNING, UPLIFT                      (note 02)
# ===========================================================================
#
# ==NEITHER CODE PRINTS A NUMERIC FACTOR OF SAFETY.  VERIFIED NEGATIVE, BOTH,
#   EACH WITH ITS OWN CONTROL - note 02 §2.==
#
#   ACI 318-25M and ACI 318-19, whole documents, complete `pdftotext -layout` text
#   layer (702 and 628 PDF pages): `grep -c -i "factor of safety"` returns 0 in both.
#   Control on the same corpus: "strength reduction factor" returns 52.
#   The only foundation-context occurrence of "overturning" or "sliding" is §13.2.6.1,
#   printed 208, which DEFERS to the general building code:
#     "Foundations shall be proportioned for bearing effects, stability against
#      overturning and sliding at the soil-foundation interface in accordance with
#      the general building code."
#     Basis: `ACI 318-25M ...pdf`, §13.2.6.1, p. 208.  Verified twice - text layer
#     and 350 dpi render + OCR.  Word-for-word identical in ACI 318-19 §13.2.6.1,
#     printed 194.
#
#   NSCP 2015: all 27 pages of Chapter 3 swept, none found.  Control: "factor of
#   safety" found twice, both out of scope - §304.1(e) (the delegation) and §307.1.2
#   (timber piles).  NSCP requires overturning to be RESISTED and traced down -
#     Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §208.5.1.5 Overturning, p. `2-213`.
#     OCR-transcribed, not visually confirmed (2026-08-25).
#     (The clause is §208.5.1.5, NOT §208.7.  §208.7 is the cross-reference inside it.)
#   - and delegates the number:
#     Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §304.1(e), p. `3-12` - the report
#     shall present "Calculations carried out and Factor of Safety (FS) assumed".
#     OCR-transcribed, not visually confirmed (2026-08-25).
#
#   Consequence, enforced below: `FS` is a REQUIRED keyword argument on all three
#   checks.  It has no default.  Every Result it produces carries NOT_CITED.
#   Never write "per NSCP" or "per ACI" next to a 1.5 or a 2.0.  Neither code says it.
#
# The free-body mechanics itself is elementary statics and is (not vault-cited) - a
# search of W&McG Chapter 15 for "overturn", "sliding" and "factor of safety" returns
# only the soil phi values and the FS = 2.5-3 sentence inside q_a.  The RESISTANCE
# VALUES the statics consumes are citable, and are cited.

_FS_FLAG = (NOT_CITED + " - FS has NO code basis; NSCP §304.1(e) folio `3-12` "
            "delegates it to the geotechnical report, ACI 318 prints none at all")


def check_sliding(*, H: float, N: float, area: float, dead_load: float, FS: float,
                  mu: float | None = None,
                  cohesive_resistance_kPa: float | None = None,
                  silts_or_clays: bool = False,
                  passive_kN: float = 0.0) -> dict:
    """Sliding at the soil-foundation interface, with BOTH NSCP ceilings applied.

    UNITS   H kN (driving horizontal resultant, service level);
            N kN (normal force on the soil = the vertical resultant actually present);
            area m2 (base contact area, for the cohesive rows);
            dead_load kN (the MINIMUM dead load likely to be in place);
            passive_kN kN (0.0 unless the project has decided to count it);
            FS dimensionless, REQUIRED, no default.

    TABLE 304-1 GIVES TWO ALTERNATIVE RESISTANCE MECHANISMS AND THEY ARE NOT ADDITIVE.
    Granular rows get a friction COEFFICIENT (row 3: 0.35, row 4: 0.25); the cohesive
    row gets a flat sliding RESISTANCE in kPa (row 5: 7).  Exactly one of `mu` and
    `cohesive_resistance_kPa` may be supplied.  ==Applying 0.25 to a clay because
    "sand is 0.25 and this is close enough" is not a Table 304-1 reading.==
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §304.2 / Table 304-1, p. `3-13`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Rows 3-5 (30/0.35, 25/0.25, 15/7) were read at 150 dpi ONLY - provisional.

    CEILING 1 - Table 304-1 footnote, p. `3-13`, same OCR marker:
      "In no case shall the lateral sliding resistance exceed one-half the dead load."
    Applied to the TOTAL lateral sliding resistance.

    CEILING 2 - §305.7.4.1, same OCR marker:
      "The frictional resistance for retaining walls and slabs on silts and clays
       shall be limited to one half of the normal force imposed on the soil by the
       weight of the footing or slab."
    Applied to the FRICTION component when `silts_or_clays=True`.
    ==The digest transcribed §305.7.4.1 WITHOUT its folio.==  It sits in Chapter 3
    (`3-N` = PDF - 297).  Locate and record the folio before issuing a calculation
    that relies on it - that caveat is returned in `flags` and is not removable here.

    PASSIVE RESISTANCE defaults to ZERO.  The lateral-bearing column of Table 304-1 is
    a resistance per metre of embedment and accumulates with burial, but it requires
    movement to mobilise, it disappears if the soil in front is later excavated for
    services, and on a fresh backfill it is not the material the table describes.
    All three cautions are practice, not code, and are (not vault-cited).  Decide once
    per project whether passive is counted and say so on the sheet.

    THE SECOND ROUTE, recorded so the team recognises it - W&McG p. 829 gives soil
    resistance factors (vertical 0.5; sliding on friction 0.8; sliding on cohesion
    0.6) and then says "virtually all building footings in North America are designed
    by using allowable-stress design applied to failures of the soil."  ==Those are
    phi factors for the SOIL in a US limit-states framework.  They are not NSCP
    provisions and NSCP does not adopt them.==  This function does not implement them.
    """
    if (mu is None) == (cohesive_resistance_kPa is None):
        raise ValueError(
            "supply exactly one of `mu` (Table 304-1 granular rows 3-4) or "
            "`cohesive_resistance_kPa` (Table 304-1 cohesive row 5).  They are "
            "ALTERNATIVES, not additives - Table 304-1 folio `3-13`.")
    if area <= 0:
        raise ValueError("area must be positive, m2")

    flags = [_FS_FLAG, NSCP_OCR, _PROVISIONAL_150DPI]
    notes: list[str] = []

    friction_raw = 0.0
    cohesion_raw = 0.0
    if mu is not None:
        friction_raw = mu * N
    else:
        cohesion_raw = cohesive_resistance_kPa * area

    # --- Ceiling 2: §305.7.4.1, friction only, silts and clays -----------------
    friction = friction_raw
    ceiling2 = None
    if silts_or_clays and mu is not None:
        ceiling2 = 0.5 * N
        if friction_raw > ceiling2:
            friction = ceiling2
            notes.append(f"NSCP §305.7.4.1 ceiling applied: friction cut from "
                         f"{friction_raw:,.2f} kN to 0.5N = {ceiling2:,.2f} kN")
        flags.append("§305.7.4.1 folio NOT RECORDED by the digest - locate and record "
                     "it before issuing a calculation that relies on this ceiling")

    resistance_raw = friction + cohesion_raw + passive_kN

    # --- Ceiling 1: Table 304-1 footnote, total lateral sliding resistance ------
    ceiling1 = 0.5 * dead_load
    resistance = resistance_raw
    if resistance_raw > ceiling1:
        resistance = ceiling1
        notes.append(f"Table 304-1 footnote ceiling applied: total lateral sliding "
                     f"resistance cut from {resistance_raw:,.2f} kN to one-half the "
                     f"dead load = {ceiling1:,.2f} kN")
    guard("sliding.half_dead_load_ceiling", resistance <= ceiling1 + 1e-9,
          "Table 304-1 footnote: lateral sliding resistance shall not exceed "
          "one-half the dead load")
    if silts_or_clays and mu is not None:
        guard("sliding.half_normal_force_ceiling", friction <= 0.5 * N + 1e-9,
              "NSCP §305.7.4.1: friction on silts and clays limited to one half of "
              "the normal force")

    fs_computed = float("inf") if H <= 0 else resistance / H
    return {
        "H": H, "N": N,
        "friction_raw_kN": friction_raw, "friction_kN": friction,
        "cohesion_kN": cohesion_raw, "passive_kN": passive_kN,
        "resistance_raw_kN": resistance_raw, "resistance_kN": resistance,
        "ceiling_half_dead_load_kN": ceiling1,
        "ceiling_half_normal_force_kN": ceiling2,
        "governing_ceiling": ("half dead load (Table 304-1 footnote)"
                              if resistance_raw > ceiling1 else "none - uncapped"),
        "FS_required": FS, "FS_computed": fs_computed,
        "passed": fs_computed >= FS,
        "notes": tuple(notes),
        "flags": tuple(flags),
        "results": [Result("FS sliding", fs_computed, "-", limit=FS,
                           passed=fs_computed >= FS,
                           basis="statics; resistances from NSCP Table 304-1 folio "
                                 "`3-13` and §305.7.4.1",
                           flags=tuple(flags))],
    }


def check_overturning(*, M_driving: float, N_resisting: float, dimension: float,
                      FS: float, direction: str = "B",
                      reduction: float = 0.0) -> dict:
    """Overturning about the TOE - the downstream edge of the base.

    UNITS   M_driving kN-m (base shear x its height above the base, plus any moment
            applied at the base by the column);
            N_resisting kN (the vertical resultant available to resist, acting through
            the base centroid);
            dimension m (the plan dimension in the direction checked);
            FS dimensionless, REQUIRED, no default;
            `reduction` a fraction (0.0-1.0) applied to the DRIVING moment.

        M_R = N_resisting * dimension / 2      FS = M_R / M_driving

    ==The free-body arithmetic is elementary statics and is (not vault-cited).==
    Neither ACI 318 nor NSCP prints an overturning equation for a spread footing, and
    W&McG Chapter 15 does not either - note 02 §3.

    WHAT IS CITED is that the check must be made, at the soil-foundation interface -
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §13.2.6.1, p. 208; and that overturning effects "shall be carried down to the
    foundation" -
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §208.5.1.5 Overturning, p. `2-213`.
    OCR-transcribed, not visually confirmed (2026-08-25).

    ==THE LOAD COMBINATION IS THE WHOLE CHECK.==  Run `stability_load_case()` first.
    Under the §203.4 ALTERNATE basic set the restoring dead load is factored DOWN to
    0.6D - (203-14) 0.6D + 0.6W + H and (203-15) 0.6D + E/1.4 + H.  A designer who
    checks overturning under 1.0D is checking the wrong case: 1.0D overstates the
    restoring moment by two-thirds relative to 0.6D and can turn a failing footing
    into a passing one on paper.
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §203.4, p. `2-11`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Run it with the lateral load in BOTH directions.

    `reduction` is provided because ASCE 7-22 §12.13.4 permits one at the
    soil-foundation interface, but ==ASCE 7-22 is not the governing PH code and this
    module does not import that allowance==; it defaults to 0.0 and any non-zero value
    is flagged (not vault-cited) here, to be justified on the sheet against whatever
    document the project has adopted.
    """
    if not 0.0 <= reduction < 1.0:
        raise ValueError("reduction must be in [0.0, 1.0)")
    flags = [_FS_FLAG, NSCP_OCR]
    if reduction:
        flags.append(NOT_CITED + f" - driving moment reduced {reduction:.0%}; no "
                     "NSCP basis is claimed for that reduction in this module")
    M_R = N_resisting * dimension / 2.0
    M_O = M_driving * (1.0 - reduction)
    fs_computed = float("inf") if M_O <= 0 else M_R / M_O
    return {
        "direction": direction,
        "M_driving_raw": M_driving, "M_driving": M_O, "M_resisting": M_R,
        "N_resisting": N_resisting, "lever_arm": dimension / 2.0,
        "FS_required": FS, "FS_computed": fs_computed,
        "passed": fs_computed >= FS,
        "flags": tuple(flags),
        "results": [Result(f"FS overturning ({direction})", fs_computed, "-",
                           limit=FS, passed=fs_computed >= FS,
                           basis="statics about the toe; ACI §13.2.6.1 p. 208 "
                                 "requires the check and defers the number",
                           flags=tuple(flags))],
    }


def check_uplift(*, T_uplift: float, N_resisting: float, FS: float,
                 variable_contents_included: bool = False) -> dict:
    """Net tension at the base.

    UNITS   T_uplift kN (net upward force from the governing combination);
            N_resisting kN (restoring weight actually present on the design day);
            FS dimensionless, REQUIRED, no default.

    ==The free-body arithmetic is elementary statics and is (not vault-cited).==

    WHAT MUST NOT BE COUNTED AS RESTORING WEIGHT - note 02 §3.3, and this is the trap
    the vault has already caught in issued work (finding F6, `Foundation Design
    (MIDAS)/02`):
      * equipment OPERATING weight, i.e. weight with contents - a tank full of liquid,
        a hopper full of product, a movable tray are all absent on the day the design
        wind blows.  ==Ask the vendor for EMPTY and OPERATING weights separately,
        carry them as two load cases, and drop the contents case from the
        wind-governed stability checks.==
      * soil overburden the excavation drawings show being removed;
      * a slab-on-grade that is not structurally connected;
      * any surcharge that is not permanent.
    The BASIS for that rule is cited in `Foundation Design (MIDAS)/02` and is not in
    the digests behind note 02, so it is not restated as a citation here - it is
    enforced as a required declaration instead: `variable_contents_included=True`
    raises, because there is no legitimate reason to pass it.
    """
    if variable_contents_included:
        raise ValueError(
            "variable equipment CONTENTS weight is in the restoring load.  Strip it. "
            "Operating (contents-inclusive) weight is not dead load for the purpose "
            "of resisting uplift, overturning or sliding - see `Foundation Design "
            "(MIDAS)/02`, finding F6, which carries the basis.")
    flags = [_FS_FLAG]
    fs_computed = float("inf") if T_uplift <= 0 else N_resisting / T_uplift
    return {
        "T_uplift": T_uplift, "N_resisting": N_resisting,
        "net_kN": N_resisting - T_uplift,
        "base_in_net_tension": T_uplift > N_resisting,
        "FS_required": FS, "FS_computed": fs_computed,
        "passed": fs_computed >= FS,
        "flags": tuple(flags),
        "results": [Result("FS uplift", fs_computed, "-", limit=FS,
                           passed=fs_computed >= FS,
                           basis="statics; ACI §13.2.6.1 p. 208 defers the number",
                           flags=tuple(flags))],
    }


def stability_load_case(D: float, *, W: float = 0.0, E: float = 0.0, H: float = 0.0,
                        dead_factor_used: float | None = None) -> dict:
    """Build the §203.4 ALTERNATE BASIC (0.6D) combinations and check what was used.

    UNITS   D, W, E, H all kN or kN-m - whatever the caller is combining, consistently.
            `dead_factor_used` is the factor the caller actually applied to the
            RESISTING dead load; pass it and this function will tell you if it is wrong.

        (203-14)   0.6D + 0.6W + H
        (203-15)   0.6D + E/1.4 + H

    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §203.4, p. `2-11`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Register correction (note 02 §3.2 / note 03 §2.4): the Chapter 2 offset in the
    front half is PDF - 55, not the register's -52/-53; `2-11` = PDF 66.

    ==The 0.6D rows are what strip the dead load down.  They are the reason
    overturning and uplift are checked at service level and not under 1.0D.==  The
    dead load is the RESISTING term, so the governing case is the one that has the
    least of it while the lateral load is at full value.  The same logic is why 0.9D
    appears in the strength set at Table 405.3.1(f) and (g).

    The one-third allowable-stress increase is permitted for the ALTERNATE set only.

    ⚠ (203-13), (203-16), (203-17) and (203-18) were NOT TRANSCRIBED by the research
    behind note 01.  Read them off the printed page before using them; their form is
    not assumed here.
    """
    combos = {
        "203-14  0.6D + 0.6W + H": 0.6 * D + 0.6 * W + H,
        "203-15  0.6D + E/1.4 + H": 0.6 * D + E / 1.4 + H,
    }
    warnings: list[str] = []
    if dead_factor_used is not None and dead_factor_used > 0.6 + 1e-12:
        warnings.append(
            f"⛔ the resisting dead load was factored at {dead_factor_used:.2f}D, not "
            "0.6D.  NSCP §203.4 alternate basic combinations (203-14) and (203-15) "
            f"factor it DOWN to 0.6D; at {dead_factor_used:.2f}D the restoring moment "
            f"is overstated by {dead_factor_used / 0.6 - 1.0:.0%}.  A designer who "
            "checks overturning under 1.0D is checking the wrong case.")
    return {
        "combinations": combos,
        "governing_resisting_D": 0.6 * D,
        "dead_factor_used": dead_factor_used,
        "warnings": tuple(warnings),
        "not_transcribed": ("203-13", "203-16", "203-17", "203-18"),
        "one_third_increase": "alternate basic set only (§203.4)",
        "flags": (NSCP_OCR,),
    }


# ===========================================================================
# 4 - SHEAR AND FLEXURE                                            (note 04)
# ===========================================================================

PHI_SHEAR = 0.75          # ACI Table 21.2.1(b) p. 430; NSCP Table 421.2.1(b) `4-139`
PHI_BEARING = 0.65        # ACI Table 21.2.1(d) p. 430; NSCP Table 421.2.1(d) `4-139`
PHI_PLAIN_CONCRETE = 0.60  # ACI Table 21.2.1(f) p. 430; NSCP Table 421.2.1(i) `4-139`
SQRT_FC_CAP_MPA = 8.3     # ACI §22.6.3.1 p. 451 (two-way); NSCP §422.5.3.1 `4-145`


def lambda_s(d_mm: float) -> float:
    """ACI size-effect factor.  lambda_s = sqrt(2/(1 + d/250)) <= 1.  d in MILLIMETRES.

    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §22.5.5.1.3, p. 445.  `d` in mm.

    ==NSCP 2015 HAS NO SIZE-EFFECT FACTOR AT ALL.==  Verified negative across all 207
    pages of NSCP Chapter 4: "size effect"/"size-effect" 0 hits, "d/250" 0 hits,
    "1 + d" 0 hits.  Controls on the same OCR corpus: "size" 49 hits, "419.2.4" (the
    lambda lightweight factor) on 12 pages - the search works and the absence is real.
    So this function is an ACI 318-25M function and is never applied to an NSCP result.

    R22.6.5.2 (printed 454) states when it bites: for d > 250 mm the size effect
    reduces two-way shear strength below 0.33*sqrt(f'c)*b_o*d.  ==Every spread footing
    this office designs has d > 250 mm.==
    """
    if d_mm <= 0:
        raise ValueError("d must be positive, mm")
    v = sqrt(2.0 / (1.0 + d_mm / 250.0))
    result = min(v, 1.0)
    guard("lambda_s.upper_bound_1", result <= 1.0 + 1e-15,
          "§22.5.5.1.3 caps lambda_s at 1.0")
    return result


def vc_one_way(*, fc: float, bw: float, d: float,
               rigid_and_continuously_soil_supported: bool,
               rho_w: float | None = None, Nu: float = 0.0,
               Ag: float | None = None, lam: float = 1.0,
               Av_at_least_Avmin: bool = False,
               net_axial_tension: bool = False) -> dict:
    """One-way shear strength, BOTH codes, side by side.  ==This is the divergence.==

    UNITS   fc MPa; bw, d mm; Nu N (positive compression, negative tension);
            Ag mm2; rho_w = A_s/(b_w d) dimensionless.  Returns V_c in N.

    -- NSCP 2015 ------------------------------------------------------------------
        V_c = 0.17 * lambda * sqrt(f'c) * b_w * d
    "unless a more detailed calculation is made in accordance with Table 422.5.5.1."
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §422.5.5.1, folio `4-145`.
    OCR-transcribed, not visually confirmed (2026-08-25).
    That is the ACI 318-14 form: flat coefficient, no size effect, no rho_w term.
    NSCP caps sqrt(f'c) at 8.3 MPa for one-way shear -
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §422.5.3.1, folio `4-145`, same OCR
    marker.  ⚠ The research digest records NO ACI 318-25M counterpart for the ONE-WAY
    sqrt(f'c) cap, so no equivalence is claimed: the cap is applied to the NSCP branch
    only and that asymmetry is reported in `flags`.
    NSCP handles axial load in separate clauses rather than inside a table -
    §422.5.6.1 V_c = 0.17(1 + N_u/(14 A_g)) lambda sqrt(f'c) b_w d (compression) and
    §422.5.7.1 V_c = 0.17(1 + N_u/(3.5 A_g)) lambda sqrt(f'c) b_w d (significant
    tension), "V_c shall not be less than zero", folio `4-145`, same OCR marker.

    -- ACI 318-25M Table 22.5.5.1, printed 444, all three rows -------------------
        (a)  [0.17*lambda*sqrt(f'c)              + N_u/(6 A_g)] b_w d   A_v >= A_v,min
        (b)  [0.66*lambda*rho_w^(1/3)*sqrt(f'c)  + N_u/(6 A_g)] b_w d   A_v >= A_v,min
        (c)  [0.66*lambda_s*lambda*rho_w^(1/3)*sqrt(f'c) + N_u/(6 A_g)] b_w d
                                                                        A_v <  A_v,min
    Notes verbatim: "1. Axial load N_u is positive for compression and negative for
    tension.  2. V_c shall not be taken less than zero."
    ==A spread footing normally has no shear reinforcement, so it lands in row (c) -
    the row that carries both lambda_s and rho_w.  That is the whole problem.==
    Bounds - Basis: `ACI 318-25M ...pdf`, §22.5.5.1.1, p. 445:
      V_c shall not be taken greater than 0.42*lambda*sqrt(f'c)*b_w*d;
      V_c need not be taken less than 0.083*lambda*sqrt(f'c)*b_w*d, except for
      elements in net axial tension or where §18.6.5.2 / §18.7.6.2.1 apply.
    Basis: `ACI 318-25M ...pdf`, §22.5.5.1.2, p. 445 - N_u/(6 A_g) shall not be taken
    greater than 0.05 f'c.
    Basis: `ACI 318-25M ...pdf`, §22.5.5.1.3, p. 445 - lambda_s.

    -- §13.2.6.2, THE CONCESSION, AND ITS GATE ----------------------------------
    "For shallow foundation members CONTINUOUSLY SUPPORTED BY SOIL AND DESIGNED BASED
     ON THE ASSUMPTION OF RIGID BEHAVIOR of the shallow member, (a) and (b) shall be
     permitted: (a) For one-way shear strength, V_c shall be taken as
     V_c = 0.17*lambda*sqrt(f'c)*b_w*d  (b) For two-way shear strength, the size
     effect factor, lambda_s, specified in 22.6, shall be taken equal to 1.0."
    Basis: `ACI 318-25M ...pdf`, §13.2.6.2, p. 208.  Verified verbatim by 350 dpi
    render plus OCR against the text layer.

    ==`rigid_and_continuously_soil_supported` HAS NO DEFAULT.  THE CALLER MUST
    ASSERT IT.==  Its commentary says why:
      "Shallow foundation members or portions of these members that are DESIGNED
       CONSIDERING THE STIFFNESS INTERACTION BETWEEN THE SOIL AND THE MEMBER may not
       benefit from the conservative stress distributions resulting from the rigid
       foundation assumption."
    Basis: `ACI 318-25M ...pdf`, R13.2.6.2, p. 208.  Non-mandatory commentary.
    ⛔ A meshed MIDAS footing on compression-only surface springs IS a
    stiffness-interaction model - that is its entire purpose.  Having bought the
    refinement you cannot also claim the concession that exists because the rigid
    assumption is conservative.  Decide the basis BEFORE meshing, and never mix.

    ACI 318-19 said something materially different - §13.2.6.2, printed 194, let you
    neglect ONLY the size-effect factor, leaving the rho_w form of V_c standing, and
    imposed NO gate.  Work issued against 318-19 is not automatically compliant with
    318-25M, and vice versa.

    IN PH PRACTICE NSCP 2015 GOVERNS and already gives the flat form unconditionally -
    there is no concession to forfeit.  The gate bites when the office elects to
    design to ACI 318-25M.  Say which code you designed to, on this specific check.
    """
    if fc <= 0 or bw <= 0 or d <= 0:
        raise ValueError("fc, bw and d must be positive (MPa, mm, mm)")
    flags = [NSCP_OCR]

    # ---- NSCP branch -----------------------------------------------------------
    sqrt_fc_nscp = min(sqrt(fc), SQRT_FC_CAP_MPA)
    vc_nscp = 0.17 * lam * sqrt_fc_nscp * bw * d
    guard("vc_one_way.nscp_not_negative", vc_nscp >= 0.0,
          "NSCP §422.5.7.1: V_c shall not be less than zero")

    # ---- ACI branch ------------------------------------------------------------
    sqrt_fc_aci = sqrt(fc)          # no ONE-WAY cap recorded for ACI in the digest
    flags.append("ACI one-way sqrt(f'c) is UNCAPPED here: the digest records no ACI "
                 "318-25M counterpart to NSCP §422.5.3.1's 8.3 MPa one-way cap, so "
                 "no equivalence is claimed")

    axial_term = 0.0
    if Nu != 0.0:
        if Ag is None or Ag <= 0:
            raise ValueError("Ag (mm2) is required whenever Nu != 0 - "
                             "ACI Table 22.5.5.1 carries N_u/(6 A_g)")
        axial_term = Nu / (6.0 * Ag)
        cap = 0.05 * fc                                   # §22.5.5.1.2
        if axial_term > cap:
            axial_term = cap
            flags.append("§22.5.5.1.2 applied: N_u/(6 A_g) capped at 0.05 f'c")
        guard("vc_one_way.aci_axial_term_cap", axial_term <= 0.05 * fc + 1e-12,
              "§22.5.5.1.2: N_u/(6 A_g) shall not be taken greater than 0.05 f'c")

    ls = lambda_s(d)
    gate_applied = bool(rigid_and_continuously_soil_supported)
    aci_rows: dict[str, float | None] = {"(a)": None, "(b)": None, "(c)": None}

    if gate_applied:
        vc_aci = 0.17 * lam * sqrt_fc_aci * bw * d
        aci_route = ("§13.2.6.2(a) - flat 0.17*lambda*sqrt(f'c)*b_w*d, the concession "
                     "for a member continuously supported by soil AND designed on the "
                     "assumption of RIGID behaviour")
        bounded = vc_aci
        floor_applied = False
        ceiling_applied = False
    else:
        if rho_w is None or rho_w <= 0:
            raise ValueError(
                "rho_w is required when the §13.2.6.2 gate is NOT asserted: "
                "Table 22.5.5.1 rows (b) and (c) carry rho_w^(1/3).  A footing on "
                "springs is a stiffness-interaction model (R13.2.6.2, printed 208) "
                "and owes the full table.")
        aci_rows["(a)"] = (0.17 * lam * sqrt_fc_aci + axial_term) * bw * d
        aci_rows["(b)"] = (0.66 * lam * rho_w ** (1.0 / 3.0) * sqrt_fc_aci
                           + axial_term) * bw * d
        aci_rows["(c)"] = (0.66 * ls * lam * rho_w ** (1.0 / 3.0) * sqrt_fc_aci
                           + axial_term) * bw * d
        if Av_at_least_Avmin:
            vc_aci = max(aci_rows["(a)"], aci_rows["(b)"])   # "Either of" (a) or (b)
            aci_route = "Table 22.5.5.1, A_v >= A_v,min - either of rows (a) and (b)"
        else:
            vc_aci = aci_rows["(c)"]
            aci_route = ("Table 22.5.5.1 row (c), A_v < A_v,min - the normal spread "
                         "footing case, carrying BOTH lambda_s and rho_w")
        ceiling = 0.42 * lam * sqrt_fc_aci * bw * d       # §22.5.5.1.1
        floor = 0.083 * lam * sqrt_fc_aci * bw * d        # §22.5.5.1.1
        bounded = min(vc_aci, ceiling)
        ceiling_applied = vc_aci > ceiling
        floor_applied = False
        if not net_axial_tension and bounded < floor:
            bounded = floor
            floor_applied = True
        guard("vc_one_way.aci_upper_bound", bounded <= ceiling + 1e-6,
              "§22.5.5.1.1: V_c shall not be taken greater than "
              "0.42*lambda*sqrt(f'c)*b_w*d")
    vc_aci_final = max(bounded, 0.0)
    guard("vc_one_way.aci_not_negative", vc_aci_final >= 0.0,
          "Table 22.5.5.1 Note 2: V_c shall not be taken less than zero")

    codes_agree = isclose(vc_nscp, vc_aci_final, rel_tol=1e-12, abs_tol=1e-9)
    return {
        "V_c_NSCP2015_N": vc_nscp,
        "V_c_ACI318_25M_N": vc_aci_final,
        "aci_table_rows_N": aci_rows,
        "aci_route": aci_route,
        "aci_gate_asserted": gate_applied,
        "aci_floor_0083_applied": floor_applied if not gate_applied else False,
        "aci_ceiling_042_applied": ceiling_applied if not gate_applied else False,
        "lambda_s": ls,
        "codes_agree": codes_agree,
        "governs_in_PH": "NSCP2015",
        "phi_shear": PHI_SHEAR,
        "phi_Vc_NSCP_N": PHI_SHEAR * vc_nscp,
        "phi_Vc_ACI_N": PHI_SHEAR * vc_aci_final,
        "divergence_note": (
            "IDENTICAL - §13.2.6.2's gate was asserted, so ACI hands the flat form "
            "back and both codes give 0.17*lambda*sqrt(f'c)*b_w*d"
            if codes_agree else
            "DIVERGENT - ACI 318-25M Table 22.5.5.1 carries lambda_s and rho_w; NSCP "
            "2015 has neither.  In PH practice NSCP governs and the flat form is "
            "available unconditionally.  Where the job is run to ACI 318-25M on a "
            "spring-supported model, do NOT take the flat V_c."),
        "flags": tuple(flags),
        "results": [
            Result("V_c one-way, NSCP 2015 §422.5.5.1", vc_nscp / 1000.0, "kN",
                   basis="NSCP §422.5.5.1 folio `4-145`", flags=(NSCP_OCR,)),
            Result("V_c one-way, ACI 318-25M", vc_aci_final / 1000.0, "kN",
                   basis=aci_route),
        ],
    }


def vc_two_way(*, fc: float, bo: float, dx: float, dy: float, beta: float,
               column_case: str, rigid_and_continuously_soil_supported: bool,
               lam: float = 1.0) -> dict:
    """Two-way (punching) shear stress, BOTH codes, side by side.

    UNITS   fc MPa; bo mm (critical perimeter); dx, dy mm (the two effective depths);
            beta = long side / short side of the column, load or reaction area.
            Returns v_c in MPa and V_c in N.

    `column_case` is one of "interior", "edge", "corner" and sets alpha_s = 40/30/20.
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §22.6.5.3, p. 455.  NSCP twin §422.6.5.3, folio `4-148`, identical values.
    OCR-transcribed, not visually confirmed (2026-08-25).
    ⭐ READ THE COMMENTARY DEFINITION, NOT THE LABEL - "The terms 'interior columns,'
    'edge columns,' and 'corner columns' in this provision refer to critical sections
    with a continuous slab on four, three, and two sides, respectively."
    Basis: `ACI 318-25M ...pdf`, R22.6.5.3, p. 455.  Non-mandatory commentary.
    ==An isolated pad footing under an interior building column normally has footing
    on all four sides of the perimeter and is therefore an "interior" case,
    alpha_s = 40.  Classify from the geometry of the FOOTING, every time.==

    d IS THE AVERAGE OF THE TWO DIRECTIONS -
    Basis: `ACI 318-25M ...pdf`, §22.6.2.1, p. 451.  NSCP twin §422.6.2.1, folio
    `4-147`, identical.  OCR-transcribed, not visually confirmed (2026-08-25).
    ⭐ Not cosmetic in a footing: the two mats sit one bar diameter apart so dx != dy
    always.  Punching uses the average; FLEXURE in each direction uses that
    direction's own d.  Getting this backwards is a common calculator bug.

    b_o is located so that it is a MINIMUM but need not be closer than d/2 -
    Basis: `ACI 318-25M ...pdf`, §22.6.4.1, p. 451.  NSCP twin §422.6.4.1, folio
    `4-147`, identical wording including both sub-items.  Same OCR marker.

    sqrt(f'c) for two-way shear shall not exceed 8.3 MPa -
    Basis: `ACI 318-25M ...pdf`, §22.6.3.1, p. 451.  NSCP twin §422.6.3.1, folio
    `4-147`, also 8.3 MPa.  Same OCR marker.

    -- ACI 318-25M Table 22.6.5.2, printed 454 - LEAST of (a), (b), (c) ----------
        (a)  0.33 * lambda_s * lambda * sqrt(f'c)
        (b)  (0.17 + 0.33/beta) * lambda_s * lambda * sqrt(f'c)
        (c)  (0.17 + 0.083*alpha_s*d/b_o) * lambda_s * lambda * sqrt(f'c)
    -- NSCP 2015 Table 422.6.5.2, folio `4-148` - LEAST of (a), (b), (c) ---------
        (a)  0.33 * lambda * sqrt(f'c)
        (b)  0.17 * (1 + 2/beta) * lambda * sqrt(f'c)
        (c)  0.083 * (2 + alpha_s*d/b_o) * lambda * sqrt(f'c)
    OCR-transcribed, not visually confirmed (2026-08-25).

    ==THE ONE SUBSTANTIVE DIVERGENCE IN THIS TABLE IS lambda_s.  NSCP has no
    size-effect factor at all; ACI 318-25M applies it to all three rows.==  The
    remaining differences are PRINTING FORM: NSCP's row (b) expands to 0.17 + 0.34/beta
    against ACI's printed 0.17 + 0.33/beta, and NSCP's row (c) leading term expands to
    0.166 against ACI's printed 0.17.  A 0.01 difference - plausibly ACI rounding its
    own factored form, plausibly an OCR digit.  NOT RESOLVED, NSCP not visually
    confirmed; both are computed and both are returned.

    §13.2.6.2(b) sets lambda_s = 1.0 for a member continuously supported by soil AND
    designed on the assumption of rigid behaviour, and then the two tables become
    numerically equivalent to within that rounding.  ==The gate argument has no
    default here either.==
    """
    alpha_map = {"interior": 40.0, "edge": 30.0, "corner": 20.0}
    if column_case not in alpha_map:
        raise ValueError(f"column_case must be one of {sorted(alpha_map)}; "
                         f"got {column_case!r}.  Classify from the geometry of the "
                         "FOOTING (continuous on four/three/two sides), not from "
                         "where the column sits in the building - R22.6.5.3 p. 455.")
    if fc <= 0 or bo <= 0 or dx <= 0 or dy <= 0 or beta < 1.0:
        raise ValueError("fc, bo, dx, dy must be positive and beta >= 1")
    alpha_s = alpha_map[column_case]
    d_avg = 0.5 * (dx + dy)                       # §22.6.2.1 / §422.6.2.1
    sq = min(sqrt(fc), SQRT_FC_CAP_MPA)           # §22.6.3.1 / §422.6.3.1
    guard("vc_two_way.sqrt_fc_cap_83", sq <= SQRT_FC_CAP_MPA + 1e-12,
          "§22.6.3.1 / §422.6.3.1: sqrt(f'c) for two-way shear <= 8.3 MPa")

    ls = 1.0 if rigid_and_continuously_soil_supported else lambda_s(d_avg)

    aci = {
        "(a)": 0.33 * ls * lam * sq,
        "(b)": (0.17 + 0.33 / beta) * ls * lam * sq,
        "(c)": (0.17 + 0.083 * alpha_s * d_avg / bo) * ls * lam * sq,
    }
    nscp = {
        "(a)": 0.33 * lam * sq,
        "(b)": 0.17 * (1.0 + 2.0 / beta) * lam * sq,
        "(c)": 0.083 * (2.0 + alpha_s * d_avg / bo) * lam * sq,
    }
    vc_aci = min(aci.values())
    vc_nscp = min(nscp.values())
    gov_aci = min(aci, key=lambda k: aci[k])
    gov_nscp = min(nscp, key=lambda k: nscp[k])

    return {
        "alpha_s": alpha_s, "d_avg": d_avg, "lambda_s": ls,
        "rows_ACI318_25M_MPa": aci, "rows_NSCP2015_MPa": nscp,
        "v_c_ACI318_25M_MPa": vc_aci, "v_c_NSCP2015_MPa": vc_nscp,
        "governing_row_ACI": gov_aci, "governing_row_NSCP": gov_nscp,
        "V_c_ACI318_25M_N": vc_aci * bo * d_avg,
        "V_c_NSCP2015_N": vc_nscp * bo * d_avg,
        "phi_shear": PHI_SHEAR,
        "size_effect_applied": ls < 1.0,
        "governs_in_PH": "NSCP2015",
        "divergence_note": (
            "lambda_s = 1.0 by §13.2.6.2(b) - the two tables now agree to within the "
            "printed-form rounding (ACI 0.33/beta vs NSCP 0.34/beta; ACI 0.17 vs NSCP "
            "0.166), which is NOT resolved"
            if ls == 1.0 else
            f"lambda_s = {ls:.4f} applies in ACI and has no NSCP counterpart - "
            "R22.6.5.2 printed 454 says the size effect reduces two-way strength "
            "below 0.33*sqrt(f'c) for d > 250 mm, and every spread footing this "
            "office designs has d > 250 mm"),
        "flags": (NSCP_OCR,
                  "row (b)/(c) coefficient mismatch 0.33 vs 0.34 and 0.17 vs 0.166 is "
                  "UNRESOLVED - plausibly ACI rounding, plausibly an OCR digit"),
        "results": [
            Result(f"v_c two-way, NSCP 2015 (row {gov_nscp})", vc_nscp, "MPa",
                   basis="NSCP Table 422.6.5.2 folio `4-148`", flags=(NSCP_OCR,)),
            Result(f"v_c two-way, ACI 318-25M (row {gov_aci})", vc_aci, "MPa",
                   basis="ACI Table 22.6.5.2 p. 454"),
        ],
    }


def critical_sections(*, supported_member: str, member_dim_mm: float, d_mm: float,
                      base_plate_dim_mm: float | None = None) -> dict:
    """Locate the critical sections.  Moment first, then shear MEASURED FROM IT.

    UNITS   member_dim_mm, base_plate_dim_mm, d_mm in mm.  All distances are returned
            as offsets from the CENTRELINE of the supported member, in mm.

    `supported_member` is one of the four rows of Table 13.2.7.1, printed 210:
        "column"                   -> face of column or pedestal
        "pedestal"                 -> face of column or pedestal
        "column_with_base_plate"   -> halfway between face of column and edge of the
                                      steel base plate  (requires base_plate_dim_mm)
        "concrete_wall"            -> face of wall
        "masonry_wall"             -> halfway between centre and face of masonry wall
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    Table 13.2.7.1, p. 210.  Identical in ACI 318-19, printed 195.
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, Table 413.2.7.1, folio `4-83` - same four rows, same wording.
    OCR-transcribed, not visually confirmed (2026-08-25).

    ⭐ THE SUBTLETY - shear sections are measured FROM the moment section:
      "The location of critical section for factored shear in accordance with 7.4.3
       and 8.4.3 for one-way shear or 8.4.4.1 for two-way shear shall be MEASURED FROM
       THE LOCATION OF THE CRITICAL SECTION FOR M_u IN 13.2.7.1."
    Basis: `ACI 318-25M ...pdf`, §13.2.7.2, p. 210.
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §413.2.7.2, folio `4-83`, same OCR
    marker.
    "The critical section for shear is measured from the face of the supported member
     (column, pedestal, or wall), EXCEPT FOR MASONRY WALLS AND MEMBERS SUPPORTED ON
     STEEL BASE PLATES."
    Basis: `ACI 318-25M ...pdf`, R13.2.7.2, p. 210.  Non-mandatory commentary.
    ==Base plates are the common case in this office's steel-column-on-pad details.==

    One-way shear at d from the moment section, for non-prestressed slabs -
    Basis: `ACI 318-25M ...pdf`, §7.4.3.2, p. 101 and §8.4.3.2, p. 118, subject to
    (a) the support reaction introduces compression into the end region, (b) loads are
    applied at or near the top surface, (c) no concentrated load occurs between the
    face of support and the critical section.  ⚠ Read (a) and (b) against an
    UPWARD-loaded footing before using the d offset; they fail outright if a
    concentrated reaction (a pile, a stub column) sits between face and section.
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, §407.4.3.2, folio `4-43`, same OCR
    marker.

    Two-way perimeter at d/2 - Basis: `ACI 318-25M ...pdf`, §8.4.4.1.1, p. 118,
    routing to §22.6; NSCP §408.4.4.1.1, folio `4-50`, routing to §422.6.4.
    Same OCR marker.

    BOTH CHECKS ARE MANDATORY - "Design shear strength of slabs in the vicinity of
    columns, concentrated loads, or reaction areas shall be THE MORE SEVERE of
    8.5.3.1.1 and 8.5.3.1.2."  Basis: `ACI 318-25M ...pdf`, §8.5.3.1, p. 121.
    It is not "whichever looks worse" by judgement; both are computed.

    Circular or regular polygon members may be treated as SQUARE MEMBERS OF EQUIVALENT
    AREA - side = sqrt(pi*D^2/4), not the diameter.  It is a permission, not a
    requirement.  Basis: `ACI 318-25M ...pdf`, §13.2.7.3, p. 211; NSCP §413.2.7.3,
    folio `4-84`, same OCR marker.  Use `equivalent_square_side()`.
    """
    rows = ("column", "pedestal", "column_with_base_plate",
            "concrete_wall", "masonry_wall")
    if supported_member not in rows:
        raise ValueError(f"supported_member must be one of {rows}; "
                         f"got {supported_member!r} - Table 13.2.7.1 has four rows")
    if member_dim_mm <= 0 or d_mm <= 0:
        raise ValueError("member_dim_mm and d_mm must be positive, mm")

    face = member_dim_mm / 2.0
    if supported_member in ("column", "pedestal", "concrete_wall"):
        m = face
        rule = "face of column, pedestal or wall"
    elif supported_member == "column_with_base_plate":
        if base_plate_dim_mm is None:
            raise ValueError("base_plate_dim_mm is required for the "
                             "'column_with_base_plate' row of Table 13.2.7.1")
        if base_plate_dim_mm < member_dim_mm:
            raise ValueError("base plate is narrower than the column - check the input")
        m = 0.5 * (face + base_plate_dim_mm / 2.0)
        rule = "halfway between face of column and edge of steel base plate"
    else:  # masonry_wall
        m = face / 2.0
        rule = "halfway between centre and face of masonry wall"

    guard("critical_sections.datum_within_member_or_plate",
          m >= 0.0, "critical section datum must be a positive offset")
    return {
        "supported_member": supported_member,
        "rule": rule,
        "moment_section_from_centreline_mm": m,
        "one_way_shear_offset_from_moment_section_mm": d_mm,
        "one_way_shear_from_centreline_mm": m + d_mm,
        "two_way_perimeter_offset_from_moment_section_mm": d_mm / 2.0,
        "two_way_perimeter_from_centreline_mm": m + d_mm / 2.0,
        "both_checks_mandatory": ("ACI §8.5.3.1 p. 121 - the MORE SEVERE of one-way "
                                 "(§22.5) and two-way (§22.6); neither may be skipped "
                                 "on judgement"),
        "flags": (NSCP_OCR,),
        "results": [
            Result("critical section for M_u, from centreline", m, "mm",
                   basis=f"ACI Table 13.2.7.1 p. 210 / NSCP Table 413.2.7.1 `4-83` "
                         f"- {rule}", flags=(NSCP_OCR,)),
            Result("one-way shear section, from centreline", m + d_mm, "mm",
                   basis="ACI §13.2.7.2 p. 210 - d measured FROM the moment section"),
            Result("two-way perimeter, from centreline", m + d_mm / 2.0, "mm",
                   basis="ACI §13.2.7.2 p. 210 - d/2 measured FROM the moment section"),
        ],
    }


def equivalent_square_side(diameter_mm: float) -> float:
    """Square of EQUIVALENT AREA for a circular column - side = sqrt(pi D^2/4), mm.

    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §13.2.7.3, p. 211 - "Circular or regular polygon-shaped concrete columns or
    pedestals shall be permitted to be treated as square members of equivalent area".
    NSCP twin §413.2.7.3, folio `4-84`, identical permission.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Note the wording is equivalent AREA, not equivalent diameter.
    """
    from math import pi
    if diameter_mm <= 0:
        raise ValueError("diameter must be positive, mm")
    return sqrt(pi * diameter_mm ** 2 / 4.0)


# --------------------------------------------------------------------- flexure

def beta1(fc: float, code: str = Code.ACI318_25M) -> float:
    """Equivalent-stress-block depth factor beta_1.  f'c in MPa, dimensionless out.

    -- ACI 318-25M Table 22.2.2.4.3, printed 439 --------------------------------
        (a)  17 <= f'c <= 28  ->  0.85
        (b)  28 <  f'c <  55  ->  0.85 - 0.05*(f'c - 28)/7
        (c)       f'c >= 55   ->  0.65
    -- NSCP 2015 Table 422.2.2.4.3, folio `4-142` -------------------------------
        same three expressions, but transcribed with 28 < f'c <= 55 for row (b) and
        f'c > 55 for row (c).
    OCR-transcribed, not visually confirmed (2026-08-25).

    ⚠ ==THE INEQUALITY SIGNS AT THE 55 MPa BOUNDARY ARE TRANSCRIBED DIFFERENTLY, AND
    INEQUALITY SIGNS ARE EXACTLY WHAT OCR GETS WRONG.==  As transcribed, at exactly
    f'c = 55 MPa ACI lands in row (c) (0.65) and NSCP in row (b) (0.6571).  Do not
    design at exactly 55 MPa off this function - read the NSCP page, or step the
    specified strength away from the boundary.  Irrelevant to the 21-35 MPa concrete
    this office pours for footings.  The divergence is raised as a flag by
    `flexural_design()`.

    ⚠ The ACI 318-25 (SI) Errata of May 14, 2026 touches R22.2.2.4.3 on p. 438 -
    "Change 8000 psi to 55 MPa" - a missed conversion in the COMMENTARY ONLY.
    Table 22.2.2.4.3 itself is correct as printed.
    Basis: `ACI 318-25( SI) Errata 2026.pdf`, item "R22.2.2.4.3, pg. 438".

    a = beta_1 * c, with a uniform concrete stress of 0.85 f'c over the equivalent
    compression zone -
    Basis: `ACI 318-25M ...pdf`, §22.2.2.4.1, p. 438.  NSCP twin §422.2.2.4.1, folio
    `4-142`, identical.  OCR-transcribed, not visually confirmed (2026-08-25).
    """
    Code.check(code)
    if fc < 17.0:
        raise ValueError("Table 22.2.2.4.3 starts at f'c = 17 MPa; "
                         f"got {fc} MPa - no value is printed below it")
    if fc <= 28.0:
        return 0.85
    if code == Code.ACI318_25M:
        return 0.65 if fc >= 55.0 else 0.85 - 0.05 * (fc - 28.0) / 7.0
    # NSCP as transcribed: row (b) is 28 < f'c <= 55, row (c) is f'c > 55
    return 0.65 if fc > 55.0 else 0.85 - 0.05 * (fc - 28.0) / 7.0


def phi_flexure(eps_t: float, fy: float, code: str, *, spiral: bool = False,
                Es: float = ES_REBAR_MPA) -> float:
    """Strength reduction factor for a flexural section, from the net tensile strain.

    UNITS   eps_t dimensionless; fy MPa; Es MPa.  Dimensionless out.

    -- ACI 318-25M Table 21.2.2, printed 432 ------------------------------------
        eps_t <= eps_ty                       compression-controlled  0.75 spiral / 0.65
        eps_ty < eps_t < eps_ty + 0.003       transition
            0.75 + 0.15(eps_t - eps_ty)/0.003   (spiral)
            0.65 + 0.25(eps_t - eps_ty)/0.003   (other)
        eps_t >= eps_ty + 0.003               tension-controlled       0.90
      Footnote [1], verbatim: "For sections classified as transition, it shall be
      permitted to use phi corresponding to compression-controlled sections."
    -- NSCP 2015 Table 421.2.2, folio `4-140` -----------------------------------
        eps_t <= eps_ty                       0.75 spiral / 0.65
        eps_ty < eps_t < 0.005                transition
            0.75 + 0.15(eps_t - eps_ty)/(0.005 - eps_ty)   (spiral)
            0.65 + 0.25(eps_t - eps_ty)/(0.005 - eps_ty)   (other)
        eps_t >= 0.005                        0.90
      §421.2.2.1: "For deformed reinforcement, eps_ty shall be f_y/E_s.  For Grade 280
      deformed reinforcement, it shall be permitted to take eps_ty equal to 0.002."
    OCR-transcribed, not visually confirmed (2026-08-25).

    ==REAL DIVERGENCE: NSCP's transition band is anchored on the fixed value 0.005;
    ACI 318-25M's is anchored on eps_ty + 0.003.  Different rule, same intent.==  For
    Grade 420 (eps_ty = 0.0021) ACI's tension-controlled threshold is 0.0051 and
    NSCP's is a flat 0.005 - close, but not the same number, and they separate as f_y
    rises.  ==A single hard-coded 0.005 is an NSCP function, not an ACI one.==  That is
    why `code` is a REQUIRED argument here and has no default.

    eps_t is "the tensile strain calculated in the extreme tension reinforcement at
    nominal strength, exclusive of strains due to prestress, creep, shrinkage, and
    temperature."  Basis: `ACI 318-25M ...pdf`, R21.2.2, p. 430.  Non-mandatory
    commentary.
    """
    Code.check(code)
    if fy <= 0 or Es <= 0:
        raise ValueError("fy and Es must be positive, MPa")
    eps_ty = fy / Es
    lo, hi = (0.75, 0.90) if spiral else (0.65, 0.90)
    span = 0.15 if spiral else 0.25
    if eps_t <= eps_ty:
        return lo
    top = eps_ty + 0.003 if code == Code.ACI318_25M else 0.005
    denom = 0.003 if code == Code.ACI318_25M else (0.005 - eps_ty)
    if denom <= 0:
        # NSCP's band collapses once eps_ty >= 0.005 (f_y >= 1000 MPa) - out of scope
        raise ValueError("NSCP's transition band is degenerate for eps_ty >= 0.005; "
                         "no value is printed for that case and none is invented")
    if eps_t >= top:
        return hi
    return lo + span * (eps_t - eps_ty) / denom


def flexural_design(*, fc: float, fy: float, b: float, d: float, As: float,
                    spiral: bool = False, Es: float = ES_REBAR_MPA) -> dict:
    """Singly-reinforced rectangular flexural strength, with BOTH phi rules returned.

    UNITS   fc, fy, Es MPa; b, d mm; As mm2.  Returns M_n in N-mm and phi*M_n in N-mm
            (divide by 1e6 for kN-m).

        a = A_s f_y / (0.85 f'c b)        c = a / beta_1        a = beta_1 c
        eps_t = 0.003 (d - c) / c
        M_n = A_s f_y (d - a/2)

    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §22.2.2.1, p. 438 - maximum strain at the extreme compression fibre = 0.003.
    NSCP twin §422.2.2.1, folio `4-142`, same value.
    OCR-transcribed, not visually confirmed (2026-08-25).
    Basis: `ACI 318-25M ...pdf`, §22.2.2.2, p. 438 - tensile strength of concrete
    neglected.
    Basis: `ACI 318-25M ...pdf`, §22.2.2.4.1, p. 438 - uniform 0.85 f'c over the
    equivalent compression zone, a = beta_1 c.  NSCP twin §422.2.2.4.1, folio `4-142`.
    Same OCR marker.
    beta_1 from `beta1()`; phi from `phi_flexure()`.

    ==BOTH transition bands are computed and BOTH phi values are returned.==  Which one
    you may use is a decision about which code the job is designed to, and this
    function will not make it for you.
    """
    if As <= 0 or b <= 0 or d <= 0:
        raise ValueError("As, b and d must be positive (mm2, mm, mm)")
    a = As * fy / (0.85 * fc * b)
    b1_aci = beta1(fc, Code.ACI318_25M)
    b1_nscp = beta1(fc, Code.NSCP2015)
    guard("flexure.compression_block_within_section", a < d,
          f"a = {a:.1f} mm is not less than d = {d:.1f} mm - the section is not "
          "singly-reinforced-tension-controlled and this function does not cover it")

    out: dict = {"a_mm": a, "beta1_ACI318_25M": b1_aci, "beta1_NSCP2015": b1_nscp,
                 "beta1_boundary_flag": None, "M_n_Nmm": As * fy * (d - a / 2.0)}
    if not isclose(b1_aci, b1_nscp, rel_tol=0, abs_tol=1e-12):
        out["beta1_boundary_flag"] = (
            f"beta_1 DIVERGES at f'c = {fc} MPa: ACI {b1_aci:.4f} vs NSCP "
            f"{b1_nscp:.4f}.  The inequality signs at the 55 MPa boundary are "
            "transcribed differently and OCR gets inequality signs wrong.  Do not "
            "design at exactly 55 MPa off this module.")

    for tag, b1, code in (("ACI318_25M", b1_aci, Code.ACI318_25M),
                          ("NSCP2015", b1_nscp, Code.NSCP2015)):
        c = a / b1
        eps_t = 0.003 * (d - c) / c
        phi = phi_flexure(eps_t, fy, code, spiral=spiral, Es=Es)
        Mn = As * fy * (d - a / 2.0)
        out[f"c_mm_{tag}"] = c
        out[f"eps_t_{tag}"] = eps_t
        out[f"phi_{tag}"] = phi
        out[f"phiMn_Nmm_{tag}"] = phi * Mn

    eps_ty = fy / Es
    out["eps_ty"] = eps_ty
    out["tension_controlled_threshold_ACI"] = eps_ty + 0.003
    out["tension_controlled_threshold_NSCP"] = 0.005
    out["phi_diverges"] = not isclose(out["phi_ACI318_25M"], out["phi_NSCP2015"],
                                      rel_tol=0, abs_tol=1e-12)
    out["divergence_note"] = (
        "phi AGREES between the codes at this strain"
        if not out["phi_diverges"] else
        f"phi DIVERGES: ACI {out['phi_ACI318_25M']:.4f} (band top eps_ty+0.003 = "
        f"{eps_ty + 0.003:.5f}) vs NSCP {out['phi_NSCP2015']:.4f} (band top fixed "
        "0.005).  In PH practice NSCP governs; say on the sheet which you used.")
    out["governs_in_PH"] = "NSCP2015"
    out["flags"] = (NSCP_OCR,)
    out["results"] = [
        Result("phi*M_n, NSCP 2015", out["phiMn_Nmm_NSCP2015"] / 1e6, "kN-m",
               basis="NSCP Table 421.2.2 folio `4-140`", flags=(NSCP_OCR,)),
        Result("phi*M_n, ACI 318-25M", out["phiMn_Nmm_ACI318_25M"] / 1e6, "kN-m",
               basis="ACI Table 21.2.2 p. 432"),
    ]
    return out


def min_flexural_steel(*, footing_type: str, fc: float, fy: float,
                       Ag_mm2: float, bw_mm: float | None = None,
                       d_mm: float | None = None) -> dict:
    """Minimum flexural reinforcement.  ==For a strip footing the answer is AMBIGUOUS.==

    UNITS   fc, fy MPa; Ag_mm2, bw_mm, d_mm.  Returns A_s,min in mm2.

    `footing_type` is one of "two_way_isolated", "mat", "one_way_strip".

    -- TWO-WAY ISOLATED FOOTING - clean answer ----------------------------------
    "The design and detailing of two-way isolated footings shall be in accordance with
     this section and the applicable provisions of CHAPTER 7 AND CHAPTER 8."
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §13.3.3.1, p. 212.  NSCP twin §413.3.3.1, folio `4-84`, routes to "Sections 407
    and 408".  OCR-transcribed, not visually confirmed (2026-08-25).
    "A minimum area of flexural reinforcement, A_s,min, OF 0.0018 A_g shall be
     provided."  Basis: `ACI 318-25M ...pdf`, §7.6.1.1, p. 102; and §8.6.1.1, p. 122
    ("...near the tension face of the slab in the direction of the span under
     consideration").
    ⭐ Because §13.3.3.1 routes ONLY to Chapters 7 and 8, the slab-type 0.0018 A_g
    governs a two-way isolated footing - not the beam minimum.

    -- MAT - clean answer -------------------------------------------------------
    "Minimum reinforcement in nonprestressed mat foundations shall be in accordance
     with 8.6.1.1."  Basis: `ACI 318-25M ...pdf`, §13.3.4.4, p. 213.  NSCP twin
    §413.3.4.4, folio `4-85`, routes to §408.6.1.1.  Same OCR marker.

    -- NSCP'S MINIMUM IS A DIFFERENT NUMBER - a live divergence ------------------
        f_y <  420 MPa  ->  0.0020 A_g
        f_y >= 420 MPa  ->  greater of 0.0018 * 420/f_y * A_g  and  0.0014 A_g
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, Table 407.6.1.1 (folio `4-44`) and Table 408.6.1.1 (folio `4-52`) -
    identical to each other.  OCR-transcribed, not visually confirmed (2026-08-25).
    ⚠ NSCP still carries the older two-tier ratios; ACI 318-19 collapsed them to a
    single 0.0018.  For Grade 420 they agree exactly (0.0018 * 420/420 = 0.0018),
    which is the normal PH case and why this divergence stays invisible.  For Grade
    275/280 NSCP requires 0.0020, MORE than ACI's 0.0018; for Grade 550 NSCP gives
    0.0014, LESS.  ==Check f_y before assuming the two codes agree.==

    -- ONE-WAY / STRIP FOOTING - ⛔ THE CODE DOES NOT RESOLVE IT -----------------
    "The design and detailing of one-way shallow foundations, including strip
     footings, combined footings, and grade beams, shall be in accordance with this
     section and the applicable provisions of CHAPTER 7 AND CHAPTER 9."
    Basis: `ACI 318-25M ...pdf`, §13.3.2.1, p. 212.  NSCP twin §413.3.2.1, folio
    `4-84`, routes to "Sections 407 and 409".  Same OCR marker.
    Chapter 7 gives 0.0018 A_g.  Chapter 9 gives the LARGER of
        (a) 0.25*sqrt(f'c)/f_y * b_w * d      (b) 1.4/f_y * b_w * d
    Basis: `ACI 318-25M ...pdf`, §9.6.1.2, p. 149.  ⭐ ERRATUM - APPLY IT: the ACI
    318-25 (SI) Errata of May 14, 2026, item "9.6.1.2, pg. 149", reads "Change 80,000
    psi to 550 MPa."  The printed f_y cap is a missed conversion.
    Basis: `ACI 318-25( SI) Errata 2026.pdf`, item "9.6.1.2, pg. 149".
    ==§13.3.2.1 invokes BOTH and does not say which governs.  The ambiguity is in the
    code text itself.  It is not resolved here, and no clause is invented to resolve
    it.==  Both values are returned, `resolved` is False and `status` is "AMBIGUOUS".
    Decide it as a documented PROJECT POSITION (the conservative reading is to satisfy
    both), record the decision in the project note, and mark it as an engineering
    interpretation, not a citation.
    🔴 NSCP §409.6.1.2 could not be read - its expressions (a) and (b) did not resolve
    under any of roughly eight OCR crop and page-segmentation configurations.  No
    value is quoted for it.  A Refusal is returned in `nscp_strip_refusal`.
    """
    types = ("two_way_isolated", "mat", "one_way_strip")
    if footing_type not in types:
        raise ValueError(f"footing_type must be one of {types}")
    if fy <= 0 or Ag_mm2 <= 0:
        raise ValueError("fy and Ag_mm2 must be positive")

    aci_ch7 = 0.0018 * Ag_mm2
    if fy < 420.0:
        nscp_ratio, nscp_branch = 0.0020, "f_y < 420 MPa -> 0.0020 A_g"
    else:
        nscp_ratio = max(0.0018 * 420.0 / fy, 0.0014)
        nscp_branch = (f"f_y >= 420 MPa -> greater of 0.0018*420/f_y = "
                       f"{0.0018 * 420.0 / fy:.6f} and 0.0014 -> {nscp_ratio:.6f}")
    nscp = nscp_ratio * Ag_mm2

    out: dict = {
        "footing_type": footing_type,
        "As_min_ACI318_25M_Ch7_mm2": aci_ch7,
        "As_min_NSCP2015_mm2": nscp,
        "NSCP_branch": nscp_branch,
        "codes_agree": isclose(aci_ch7, nscp, rel_tol=1e-12),
        "governs_in_PH": "NSCP2015",
        "fy_cap_note": ("ACI §9.6.1.2's f_y cap is 550 MPa after the May 14 2026 SI "
                        "errata (printed '80,000 psi' is a missed conversion)"),
        "flags": (NSCP_OCR,),
        "status": "RESOLVED",
        "resolved": True,
        "nscp_strip_refusal": None,
    }
    if fy > 550.0:
        out["flags"] = out["flags"] + (
            f"f_y = {fy} MPa exceeds ACI §9.6.1.2's 550 MPa cap (errata-corrected)",)

    if footing_type == "one_way_strip":
        if bw_mm is None or d_mm is None:
            raise ValueError("bw_mm and d_mm are required for a one-way / strip "
                             "footing - ACI §9.6.1.2's expressions are b_w d forms")
        ch9_a = 0.25 * sqrt(fc) / fy * bw_mm * d_mm
        ch9_b = 1.4 / fy * bw_mm * d_mm
        ch9 = max(ch9_a, ch9_b)
        out.update({
            "As_min_ACI318_25M_Ch9_a_mm2": ch9_a,
            "As_min_ACI318_25M_Ch9_b_mm2": ch9_b,
            "As_min_ACI318_25M_Ch9_mm2": ch9,
            "As_min_conservative_both_mm2": max(aci_ch7, ch9),
            "status": "AMBIGUOUS",
            "resolved": False,
            "ambiguity": (
                "ACI §13.3.2.1 (printed 212) routes a one-way / strip footing to BOTH "
                "Chapter 7 (0.0018 A_g) and Chapter 9 (larger of 0.25*sqrt(f'c)/f_y "
                "b_w d and 1.4/f_y b_w d) and DOES NOT SAY WHICH GOVERNS.  The "
                "ambiguity is in the code text.  It is not resolved here.  NSCP "
                "§413.3.2.1 (folio `4-84`) has the same routing structure and the "
                "same unresolved ambiguity, and NSCP §413 contains no minimum "
                "reinforcement specific to strip or isolated footings."),
            "nscp_strip_refusal": Refusal(
                "NSCP §409.6.1.2 minimum flexural reinforcement for a strip footing "
                "designed as a §409 beam",
                pointers=(
                    "NSCP §409.6.1.2's expressions (a) and (b) did not resolve under "
                    "any of roughly eight OCR crop and page-segmentation "
                    "configurations - note 04 §4.3",
                    "Read the page visually before setting the minimum for a strip "
                    "footing designed as an NSCP §409 beam",
                )),
        })
        out["results"] = [
            Result("A_s,min Ch. 7 route (0.0018 A_g)", aci_ch7, "mm2",
                   basis="ACI §7.6.1.1 p. 102"),
            Result("A_s,min Ch. 9 route (larger of a, b)", ch9, "mm2",
                   basis="ACI §9.6.1.2 p. 149 + SI errata 2026"),
            Result("A_s,min conservative - satisfy BOTH", max(aci_ch7, ch9), "mm2",
                   passed=None,
                   basis="ENGINEERING INTERPRETATION, not a citation",
                   flags=("AMBIGUOUS - §13.3.2.1 routes to both chapters and the "
                          "code does not resolve which governs", NOT_CITED)),
        ]
    else:
        out["results"] = [
            Result("A_s,min NSCP 2015 (two-tier)", nscp, "mm2",
                   basis="NSCP Table 407.6.1.1 `4-44` / Table 408.6.1.1 `4-52`",
                   flags=(NSCP_OCR,)),
            Result("A_s,min ACI 318-25M (flat 0.0018 A_g)", aci_ch7, "mm2",
                   basis="ACI §7.6.1.1 p. 102 / §8.6.1.1 p. 122"),
        ]
    return out


def band_reinforcement(As_total: float, B: float, L: float) -> dict:
    """Short-direction band rule for a rectangular footing.  gamma_s = 2/(beta + 1).

    UNITS   As_total mm2 (total short-direction steel required);
            B, L m or mm - only their RATIO is used, so any consistent pair works.
            B is the SHORT side and L the LONG side; they are sorted defensively.

    "(a) Reinforcement in the long direction shall be distributed uniformly across
     entire width of footing.  (b) For reinforcement in the short direction, a portion
     of the total reinforcement, gamma_s A_s, shall be distributed uniformly over a
     BAND WIDTH EQUAL TO THE LENGTH OF SHORT SIDE OF FOOTING, centered on centerline of
     column or pedestal.  Remainder of reinforcement required in the short direction,
     (1 - gamma_s) A_s, shall be distributed uniformly outside the center band width",

        gamma_s = 2 / (beta + 1)        beta = long side / short side

    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §13.3.3.3 and Eq. (13.3.3.3), p. 212.  Unchanged from ACI 318-19, printed 197.
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, §413.3.3.3 and Eq. (413.3.3.3), folio `4-84` - IDENTICAL wording and
    identical equation.  OCR-transcribed, not visually confirmed (2026-08-25).
    ⭐ No divergence here.  Both codes print the same rule.

    THE PRACTICAL ALTERNATIVE THE CODE ITSELF OFFERS:
      "To minimize potential construction errors in placing bars, a common practice is
       to increase the amount of reinforcement in the short direction by 2beta/(beta+1)
       and space it uniformly along the long dimension of the footing (CRSI Handbook
       1984; Fling 1987)."
    Basis: `ACI 318-25M ...pdf`, R13.3.3.3, p. 212.  Non-mandatory commentary.
    ⭐ Prefer this route on drawings - two bar spacings in one direction is the detail
    that gets built wrong.  It is a COMMENTARY practice; say so on the sheet.

    THE TWO CASES WHERE NO BAND IS NEEDED:
      square two-way footings - uniform in both directions.
      Basis: `ACI 318-25M ...pdf`, §13.3.3.2, p. 212.  ⚠ The research digest records
      no NSCP twin for this clause, so none is cited; §413.3.3.2 was not captured.
      one-way footings - uniform across the entire width.
      Basis: `ACI 318-25M ...pdf`, §13.3.2.2, p. 212.  NSCP twin §413.3.2.2, folio
      `4-84`, identical.  OCR-transcribed, not visually confirmed (2026-08-25).
    """
    if As_total <= 0 or B <= 0 or L <= 0:
        raise ValueError("As_total, B and L must be positive")
    short, long_ = (B, L) if B <= L else (L, B)
    beta = long_ / short
    gamma_s = 2.0 / (beta + 1.0)
    guard("band.gamma_s_bounds", 0.0 < gamma_s <= 1.0 + 1e-15,
          "gamma_s = 2/(beta+1) is in (0, 1] for beta >= 1")
    square = isclose(beta, 1.0, rel_tol=0, abs_tol=1e-12)
    return {
        "beta": beta, "gamma_s": gamma_s,
        "short_side": short, "long_side": long_,
        "band_width": short,
        "As_in_band_mm2": gamma_s * As_total,
        "As_outside_band_mm2": (1.0 - gamma_s) * As_total,
        "As_uniform_alternative_mm2": As_total * (2.0 * beta / (beta + 1.0)),
        "uniform_alternative_multiplier": 2.0 * beta / (beta + 1.0),
        "square_no_band_required": square,
        "flags": (NSCP_OCR,) + (("square footing - §13.3.3.2 p. 212: distribute "
                                 "uniformly in BOTH directions, no band",) if square
                                else ()),
        "results": [
            Result("gamma_s = 2/(beta + 1)", gamma_s, "-",
                   basis="ACI Eq. (13.3.3.3) p. 212 / NSCP Eq. (413.3.3.3) `4-84`",
                   flags=(NSCP_OCR,)),
            Result("A_s in central band (width = short side)", gamma_s * As_total,
                   "mm2", basis="ACI §13.3.3.3(b) p. 212"),
            Result("A_s outside the band", (1.0 - gamma_s) * As_total, "mm2",
                   basis="ACI §13.3.3.3(b) p. 212"),
            Result("A_s uniform, R13.3.3.3 alternative", 
                   As_total * (2.0 * beta / (beta + 1.0)), "mm2",
                   basis="ACI R13.3.3.3 p. 212 - COMMENTARY practice, say so",
                   flags=("non-mandatory commentary",)),
        ],
    }


def bearing_strength_concrete(*, fc: float, A1_mm2: float,
                              supporting_surface_wider_all_sides: bool,
                              A2_mm2: float | None = None) -> dict:
    """Concrete bearing strength at the column / pedestal interface.  phi = 0.65.

    UNITS   fc MPa; A1_mm2, A2_mm2 mm2.  Returns B_n and phi*B_n in N.

    This is a DIFFERENT CHECK WITH THE SAME NAME as soil bearing: a FACTORED-LOAD
    strength check on the CONCRETE, in Chapter 22, not a service check on the soil.

        phi B_n >= B_u
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §22.8.3.1, p. 468.  NSCP twin §422.8.3.1, folio `4-152`.
    OCR-transcribed, not visually confirmed (2026-08-25).

    "A_1 is the loaded area, and A_2 is the area of the lower base of the largest
     frustum of a pyramid, cone, or tapered wedge contained wholly within the support
     and having its upper base equal to the loaded area.  The sides of the pyramid,
     cone, or tapered wedge shall be sloped 1 VERTICAL TO 2 HORIZONTAL."
    Basis: `ACI 318-25M ...pdf`, §22.8.3.2, p. 468.  NSCP twin §422.8.3.2, folio
    `4-152`, same wording.  Same OCR marker.

    Table 22.8.3.2, printed 469 - nominal bearing strength:
        supporting surface wider on all sides than the loaded area:
            LESSER OF   (a) sqrt(A2/A1) * (0.85 f'c A1)
                        (b) 2 * (0.85 f'c A1)
        other cases:    (c) 0.85 f'c A1
    NSCP twin Table 422.8.3.2, folio `4-152`, same rows.  Same OCR marker.

    ⚠ ==QUOTE IT AS PRINTED.==  Both codes state the enhancement as "LESSER OF (a) and
    (b)" - a comparison of two strengths.  They do NOT print it as an inequality
    sqrt(A2/A1) <= 2 on the radical.  The numerical outcome is the same, but a
    calculator that prints the inequality form is not quoting the Code; it is
    paraphrasing it.  This function computes (a) and (b) and takes the lesser, and
    reports the radical separately as a diagnostic only.

    phi for bearing = 0.65 - Basis: `ACI 318-25M ...pdf`, Table 21.2.1(d), p. 430.
    NSCP twin Table 421.2.1(d), folio `4-139`, also 0.65.  Same OCR marker.

    "No minimum depth is given for the support, which will most likely be CONTROLLED
     BY THE PUNCHING SHEAR REQUIREMENTS OF 22.6."
    Basis: `ACI 318-25M ...pdf`, R22.8.3.2, pp. 468-469.  Non-mandatory commentary.
    ⭐ Read that plainly: bearing rarely governs the footing depth - punching does.

    ⭐ VERDICT ON THIS CHECK: NSCP and ACI 318-25M AGREE COMPLETELY.  Same equation,
    same frustum geometry, same 1:2 slope, same phi = 0.65.  Cite NSCP as governing
    and ACI as confirming.
    """
    if fc <= 0 or A1_mm2 <= 0:
        raise ValueError("fc and A1 must be positive (MPa, mm2)")
    base = 0.85 * fc * A1_mm2
    if supporting_surface_wider_all_sides:
        if A2_mm2 is None or A2_mm2 < A1_mm2:
            raise ValueError("A2 (>= A1) is required when the supporting surface is "
                             "wider on all sides - it is the lower base of the 1:2 "
                             "frustum contained wholly within the support")
        a = sqrt(A2_mm2 / A1_mm2) * base
        b = 2.0 * base
        Bn = min(a, b)
        row = "(a)" if a <= b else "(b)"
        detail = {"row_a_N": a, "row_b_N": b, "sqrt_A2_over_A1": sqrt(A2_mm2 / A1_mm2)}
    else:
        Bn = base
        row = "(c)"
        detail = {"row_c_N": base}
    guard("bearing_concrete.lesser_of_form", Bn <= 2.0 * base + 1e-6,
          "Table 22.8.3.2 - the enhancement is bounded by row (b), 2*(0.85 f'c A1)")
    return {
        "B_n_N": Bn, "phi": PHI_BEARING, "phi_B_n_N": PHI_BEARING * Bn,
        "governing_row": row, "detail": detail,
        "printed_form": "LESSER OF (a) and (b) - as printed; NOT an inequality on "
                        "the radical",
        "codes_agree": True,
        "flags": (NSCP_OCR,),
        "results": [Result(f"phi*B_n, Table 22.8.3.2 row {row}",
                           PHI_BEARING * Bn / 1000.0, "kN",
                           basis="ACI §22.8 p. 468-469 / NSCP §422.8 folio `4-152`; "
                                 "phi = 0.65 Table 21.2.1(d) p. 430",
                           flags=(NSCP_OCR, "NSCP and ACI agree completely"))],
    }


# ===========================================================================
# 5 - CRACK CONTROL AND SERVICEABILITY                             (note 05)
# ===========================================================================

def max_bar_spacing(f_s: float | None = None,
                    c_c: float = COVER_CAST_AGAINST_GROUND_MM,
                    *, fy: float | None = None) -> dict:
    """Maximum spacing of bonded deformed reinforcement.  ==This IS the crack control.==

    UNITS   f_s MPa; c_c mm; returns s in mm.

        s = LESSER OF    380 * (280/f_s) - 2.5 c_c
                         300 * (280/f_s)

    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    Table 24.3.2, p. 503.  Verified twice in the research pass - text layer plus a
    400 dpi render OCR.
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, Table 424.3.2, folio `4-158`.
    OCR-transcribed, not visually confirmed (2026-08-25).  Every constant was read at
    400 dpi twice and re-read at 700 dpi three times under three tesseract
    configurations, all agreeing.
    ⭐ ==The constants 380 / 280 / 2.5 / 300 are IDENTICAL in both.  One calculator
    serves both codes for this check.==  A matching pair is as useful a finding as a
    divergence.

    c_c is "the least distance from surface of deformed or prestressed reinforcement
    to the tension face."  Basis: `ACI 318-25M ...pdf`, §24.3.2, p. 503; NSCP
    §424.3.2, folio `4-158`, same OCR marker.

    ==THERE IS NO `<=` CHAIN IN THE PRINTED TABLE.  The two expressions are joined by
    the words "Lesser of".==  Code that implements `min(expr1, expr2)` is right; code
    that implements `expr1 <= expr2` as a CHECK is wrong.

    f_s - "Stress f_s in deformed reinforcement closest to the tension face at service
    loads shall be calculated based on the UNFACTORED MOMENT, or it shall be permitted
    to take f_s as (2/3) f_y."
    Basis: `ACI 318-25M ...pdf`, §24.3.2.1, p. 503; NSCP §424.3.2.1, folio `4-158`,
    same OCR marker.
    Pass `f_s` when you have computed it from M_service; pass `fy` and this function
    applies the (2/3) f_y permission and flags that it did.  Supplying neither raises.

    c_c DEFAULTS TO 75 mm - the footing bottom-mat case.
    "Cast against and permanently in contact with ground / All / All -> 75 mm."
    Basis: `ACI 318-25M ...pdf`, Table 20.5.1.3.1, p. 421, charged by §20.5.1.3.1;
    foundations are routed here by §13.2.9.1, p. 211.
    Basis: `_Scanned/NSCP 2015 ... Vol.1.pdf`, Table 420.6.1.3.1, folio `4-136`, also
    75 mm; §420.6.1.3.4 (`4-137`) restates it for bundled bars.  Same OCR marker.

    THE SANITY ANCHOR ACI ITSELF PRINTS, and the non-closure it creates:
      "For the case of beams with Grade 420 reinforcement and 50 mm clear cover to the
       primary reinforcement, with f_s = 280 MPa, the maximum bar spacing is 250 mm."
    Basis: `ACI 318-25M ...pdf`, R24.3.2, p. 503.  Non-mandatory commentary.
    ⚠ Substituting into the SI table gives 380(1.0) - 2.5(50) = 255 mm against the
    commentary's printed 250 mm.  ==The difference is a rounding INSIDE THE COMMENTARY,
    not a different rule.  Use the table; treat 250 mm as the commentary's rounded
    illustration.==  The self-test asserts 255 and records 250 explicitly so the 5 mm
    is visible rather than hidden.

    THE SCOPE CAVEAT WORTH CARRYING: §24.3 is headed "Distribution of flexural
    reinforcement in ONE-WAY slabs and beams" (printed 502).  A two-way isolated
    footing reaches its spacing limit through Chapter 8 instead - §8.7.2.2, printed
    125, reached from §13.3.3.1, printed 212.  Note 05 §4 develops this; the numbers
    here are Table 24.3.2's.
    """
    flags: list[str] = [NSCP_OCR]
    if f_s is None:
        if fy is None:
            raise ValueError("supply f_s (from the unfactored moment) or fy (to take "
                             "the §24.3.2.1 permission f_s = (2/3) f_y).  There is no "
                             "default stress.")
        f_s = (2.0 / 3.0) * fy
        flags.append("f_s taken as (2/3) f_y by the §24.3.2.1 / §424.3.2.1 permission "
                     "- a PERMISSION, not the rule; a footing with a genuinely low "
                     "service stress gets a more generous spacing from M_service")
    if f_s <= 0 or c_c < 0:
        raise ValueError("f_s must be positive (MPa) and c_c non-negative (mm)")

    expr1 = 380.0 * (280.0 / f_s) - 2.5 * c_c
    expr2 = 300.0 * (280.0 / f_s)
    s = min(expr1, expr2)
    guard("spacing.lesser_of_not_a_check", s <= expr1 + 1e-12 and s <= expr2 + 1e-12,
          "Table 24.3.2 is a 'Lesser of', implemented as min(), never as a check")
    if s <= 0:
        flags.append("the first expression has gone non-positive at this cover and "
                     "stress - the table gives no spacing here; re-examine f_s and c_c")
    return {
        "f_s_MPa": f_s, "c_c_mm": c_c,
        "expr1_380_mm": expr1, "expr2_300_mm": expr2,
        "s_max_mm": s,
        "governing_expression": "380(280/f_s) - 2.5 c_c" if expr1 <= expr2
                                else "300(280/f_s)",
        "codes_agree": True,
        "commentary_anchor_mm": 250.0,
        "commentary_anchor_note": ("R24.3.2 p. 503 prints 250 mm for Grade 420, "
                                   "c_c = 50 mm, f_s = 280 MPa; the table gives 255 mm "
                                   "- a rounding inside the commentary"),
        "flags": tuple(flags),
        "results": [Result("max bar spacing s", s, "mm",
                           basis="ACI Table 24.3.2 p. 503 / NSCP Table 424.3.2 "
                                 "folio `4-158` - constants identical",
                           flags=tuple(flags))],
    }


def shrinkage_temperature_steel(fy: float, Ag_mm2: float,
                                code: str = Code.BOTH) -> dict:
    """Shrinkage and temperature reinforcement.  ==A live divergence.==

    UNITS   fy MPa; Ag_mm2 mm2 (GROSS concrete area).  Returns mm2.

    -- ACI 318-25M - one scalar --------------------------------------------------
      "The ratio of deformed shrinkage and temperature reinforcement area to gross
       concrete area shall be greater than or equal to 0.0018."
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    §24.4.3.2, p. 505.  Identical single-ratio form in ACI 318-19.
    ACI states the reason for the deletion of the old table itself:
      "Previous editions of the Code permitted a reduction ... for reinforcement with
       yield strength greater than 420 MPa.  However, THE MECHANICS OF CRACKING SUGGEST
       THAT INCREASED YIELD STRENGTH PROVIDES NO BENEFIT FOR THE CONTROL OF CRACKING."
    Basis: `ACI 318-25M ...pdf`, R24.4.3.2, p. 505.  Non-mandatory commentary.
    ==Any vault note, template or office spreadsheet carrying a "Table 24.4.3.2" is
    running on ACI 318-14 or earlier.  Find it and date it.==

    -- NSCP 2015 STILL CARRIES THE DELETED TABLE - three branches ----------------
        f_y <  420 MPa  ->  0.0020
        f_y >= 420 MPa  ->  greater of 0.0018 * 420/f_y  and  0.0014
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, Table 424.4.3.2, folio `4-159`.
    OCR-transcribed, not visually confirmed (2026-08-25).

    ⚠ ==RESOLVE THIS DELIBERATELY - DO NOT AVERAGE.==  NSCP 2015 governs in PH practice
    and permits a reduction ACI has withdrawn on stated mechanical grounds.  ACI's flat
    0.0018 is compliant with NSCP for f_y >= 420 because it is never less than the
    branch it replaces - but it IS less than NSCP's 0.0020 for f_y < 420, so the flat
    ratio is NOT uniformly conservative.  Check the branch before assuming.  For Grade
    420 the two agree exactly at 0.0018, which is why the divergence stays invisible on
    most PH projects until someone specifies Grade 550.

    SPACING AND DEVELOPMENT MATCH: maximum spacing the lesser of 5h and 450 mm, and
    the steel "shall develop f_y in tension".
    Basis: `ACI 318-25M ...pdf`, §24.4.3.3 and §24.4.3.4, p. 505; NSCP §424.4.3.3 and
    §424.4.3.4, folio `4-159`.  Same OCR marker.
    ⭐ Note the scope sentences differ AS TRANSCRIBED - NSCP §424.4.1 (`4-159`) carries
    an explicit "in one-way slabs" scope that the ACI §24.4.3 charging sentence as
    transcribed does not.  Only the clause text was captured, not the section heading
    above it, so CHECK THIS ON THE PAGE before relying on it.

    NOT THE SAME REQUIREMENT AS MINIMUM FLEXURAL STEEL, even at the same number:
    S&T steel may be distributed between the two faces; minimum flexural reinforcement
    "should be placed as close as practicable to the face of the concrete in tension
    due to applied loads."  Basis: `ACI 318-25M ...pdf`, R7.6.1.1, p. 102.
    Non-mandatory commentary.  ==You cannot satisfy a footing's minimum FLEXURAL steel
    by counting a top mat placed for shrinkage.==
    """
    Code.check(code)
    if fy <= 0 or Ag_mm2 <= 0:
        raise ValueError("fy and Ag_mm2 must be positive")
    aci_ratio = 0.0018
    if fy < 420.0:
        nscp_ratio = 0.0020
        branch = "f_y < 420 MPa -> 0.0020"
    else:
        nscp_ratio = max(0.0018 * 420.0 / fy, 0.0014)
        branch = (f"f_y >= 420 MPa -> greater of 0.0018*420/f_y = "
                  f"{0.0018 * 420.0 / fy:.6f} and 0.0014")
    diverges = not isclose(aci_ratio, nscp_ratio, rel_tol=0, abs_tol=1e-12)
    return {
        "ratio_ACI318_25M": aci_ratio,
        "ratio_NSCP2015": nscp_ratio,
        "NSCP_branch": branch,
        "As_ACI318_25M_mm2": aci_ratio * Ag_mm2,
        "As_NSCP2015_mm2": nscp_ratio * Ag_mm2,
        "diverges": diverges,
        "governs_in_PH": "NSCP2015",
        "aci_conservative_here": aci_ratio >= nscp_ratio,
        "divergence_note": (
            "the two agree exactly at this f_y" if not diverges else
            f"DIVERGENT: ACI flat {aci_ratio:.4f} vs NSCP {nscp_ratio:.6f} "
            f"({branch}).  " + ("ACI is the more conservative here."
                                if aci_ratio > nscp_ratio else
                                "⚠ ACI's flat ratio is LESS than NSCP's here - the "
                                "flat ratio is not uniformly conservative.")),
        "max_spacing_rule": "lesser of 5h and 450 mm (§24.4.3.3 / §424.4.3.3)",
        "anchorage_rule": "shall develop f_y in tension (§24.4.3.4 / §424.4.3.4)",
        "flags": (NSCP_OCR,),
        "results": [
            Result("A_s,ST NSCP 2015", nscp_ratio * Ag_mm2, "mm2",
                   basis="NSCP Table 424.4.3.2 folio `4-159`", flags=(NSCP_OCR,)),
            Result("A_s,ST ACI 318-25M", aci_ratio * Ag_mm2, "mm2",
                   basis="ACI §24.4.3.2 p. 505"),
        ],
    }


def crack_width_limit(*_args, **_kwargs) -> Refusal:
    """==THERE IS NO CRACK-WIDTH LIMIT IN THIS LIBRARY.  This function refuses.==

    Returns a `Refusal` carrying the vault's exact sentence.  It takes and ignores any
    arguments deliberately, so that a caller who reaches for it with an exposure class,
    a bar size or a service moment still gets the refusal rather than a TypeError that
    might be "fixed" by inventing a signature.

    THE CODE'S OWN POINTER GOES OFF-FILE:
      "If crack width or leakage prevention is a design limit state, refer to ACI
       PRC-224 or ACI CODE-350 for recommended reinforcement ratios."
    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    R24.4.3.2, p. 505.  Non-mandatory commentary.
    🔴 Neither ACI PRC-224 nor ACI CODE-350 is in `vault/reference/`.  A `find` across
    the whole reference tree for *224*, *350* and *318* returns exactly five files:
    ACI 318-19, the ACI 318-25 SI Errata, ACI 318-25M, the CRSI Design Guide on ACI
    318-19, and `_Scanned/ACI 350 (3-20).pdf` - which is image-only (56 pages, text
    layer contains only the watermark "@seismicisolation"), was identified from a
    300 dpi OCR render and NOT visually verified, and out of which no numeric value
    has been read.

    WHAT THE CODE DOES SAY, and it settles the argument the team keeps having:
      "The Code provisions for spacing are intended to limit surface cracks to a width
       that is generally acceptable in practice ... corrosion is not clearly correlated
       with surface crack widths in the range normally found with reinforcement
       stresses at service load levels.  For this reason, THE CODE DOES NOT
       DIFFERENTIATE BETWEEN INTERIOR AND EXTERIOR EXPOSURES."
    Basis: `ACI 318-25M ...pdf`, R24.3.2, p. 503.  Non-mandatory commentary.
      "... clear experimental evidence is not available regarding the crack width
       beyond which a corrosion danger exists (ACI PRC-222)."
    Basis: `ACI 318-25M ...pdf`, R24.3.5, p. 504.  Non-mandatory commentary.
    ==So the spacing rule IS the crack control.  There is nothing behind it to look
    up.==  Use `max_bar_spacing()`.

    NSCP: §428 uses crack width only as a LOAD-TEST MEASUREMENT (folio `4-190`);
    §424.3 and §413 contain no numeric crack-width limit.
    OCR-transcribed, not visually confirmed (2026-08-25).
    """
    return Refusal(
        "numeric crack-width limit for a spread footing",
        pointers=(
            "ACI 318-25M R24.4.3.2, printed 505, sends crack-width design to ACI "
            "PRC-224 or ACI CODE-350 - NEITHER IS IN vault/reference/",
            "`_Scanned/ACI 350 (3-20).pdf` is on file but is image-only, was "
            "identified by OCR of a 300 dpi render and is NOT visually verified; no "
            "numeric value has been read out of it",
            "ACI R24.3.2, printed 503 - the SPACING rule is the crack control, and "
            "the Code does not differentiate interior from exterior exposure",
            "ACI R24.3.5, printed 504 - 'clear experimental evidence is not available "
            "regarding the crack width beyond which a corrosion danger exists'",
            "NSCP §428, folio `4-190` - crack width appears only as a load-test "
            "measurement (OCR-transcribed, not visually confirmed (2026-08-25))",
            "Use max_bar_spacing() - ACI Table 24.3.2 / NSCP Table 424.3.2",
        ))


def cover_table() -> dict:
    """Specified concrete cover, mm.  ==A footing gets the largest cover in the Code.==

    Basis: `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf`,
    Table 20.5.1.3.1, p. 421.  §20.5.1.3.1 charges it; Table 20.5.1.3.2 (prestressed
    cast-in-place, p. 421) gives the same 75 mm for the cast-against-ground row.
    Foundations are routed here by §13.2.9.1, p. 211.
    Basis: `_Scanned/NSCP 2015 - National Structural Code of the Philippines
    Vol.1.pdf`, Table 420.6.1.3.1, folio `4-136`; §420.6.1.3.4 (`4-137`) restates the
    75 mm rule independently for bundled bars.
    OCR-transcribed, not visually confirmed (2026-08-25).

    Cover feeds the spacing formula directly through c_c, so the 75 mm bottom-mat case
    is the default in `max_bar_spacing()`.
    """
    return {
        "cast_against_and_permanently_in_contact_with_ground":
            COVER_CAST_AGAINST_GROUND_MM,
        "exposed_to_weather_or_ground__No19_to_No57": COVER_EXPOSED_LARGE_BAR_MM,
        "exposed_to_weather_or_ground__No16_and_smaller": COVER_EXPOSED_SMALL_BAR_MM,
        "not_exposed__slabs_joists_walls__No43_No57": 40.0,
        "not_exposed__slabs_joists_walls__No36_and_smaller": 19.0,
        "not_exposed__beams_columns_pedestals_ties": 40.0,
        "flags": (NSCP_OCR,),
    }


# ===========================================================================
# 6 - SELF-TEST
# ===========================================================================
# Vault convention: the script counts its own assertion guards and prints the total,
# reporting DISTINCT guards separately from EXECUTIONS.  A guard inside a loop is one
# distinct guard however many times it runs - see `lambda_s` monotonicity below, which
# is a single tag executed several hundred times.

def _selftest() -> bool:
    print("=" * 92)
    print("dp_foundation.py - SELF-TEST")
    print("=" * 92)

    # -- 1  band rule -------------------------------------------------------------
    b1 = band_reinforcement(1000.0, 3.0, 3.0)
    b2 = band_reinforcement(1000.0, 2.0, 4.0)
    guard("selftest.gamma_s_beta1", isclose(b1["gamma_s"], 1.0, rel_tol=0, abs_tol=1e-15),
          f"gamma_s(beta=1) must be 1.0, got {b1['gamma_s']!r}")
    guard("selftest.gamma_s_beta2", isclose(b2["gamma_s"], 2.0 / 3.0, rel_tol=1e-15),
          f"gamma_s(beta=2) must be 2/3, got {b2['gamma_s']!r}")
    guard("selftest.band_split_sums_to_total",
          isclose(b2["As_in_band_mm2"] + b2["As_outside_band_mm2"], 1000.0,
                  rel_tol=1e-12),
          "gamma_s A_s + (1 - gamma_s) A_s must be the total")
    guard("selftest.r13333_alternative",
          isclose(b2["uniform_alternative_multiplier"], 4.0 / 3.0, rel_tol=1e-12),
          "R13.3.3.3's practical alternative is 2*beta/(beta+1) = 4/3 at beta = 2")
    print(f"  [1] band rule        gamma_s(1) = {b1['gamma_s']:.6f}   "
          f"gamma_s(2) = {b2['gamma_s']:.6f}   "
          f"R13.3.3.3 multiplier = {b2['uniform_alternative_multiplier']:.6f}")

    # -- 2  the kern --------------------------------------------------------------
    B, L, P = 2.0, 3.0, 1000.0
    e_target = B / 6.0
    at_kern = bearing_pressure(P, Mx=P * e_target, My=0.0, B=B, L=L)
    concentric = bearing_pressure(P, Mx=0.0, My=0.0, B=B, L=L)
    guard("selftest.kern_qmin_zero", abs(at_kern["q_min"]) < 1e-9,
          f"at e = B/6 the heel is on the point of lifting: q_min must be 0, got "
          f"{at_kern['q_min']!r}")
    guard("selftest.kern_qmax_twice_uniform",
          isclose(at_kern["q_max"], 2.0 * P / (B * L), rel_tol=1e-12),
          "at e = B/6, q_max is twice the uniform P/BL")
    guard("selftest.concentric_uniform",
          isclose(concentric["q_max"], concentric["q_min"], rel_tol=0, abs_tol=1e-12),
          "at e = 0 the distribution is uniform: q_max must equal q_min")
    outside = bearing_pressure(P, Mx=P * (B / 5.0), My=0.0, B=B, L=L)
    guard("selftest.kern_partial_uplift_flagged", outside["partial_uplift"] is True,
          "e > B/6 must set the partial-uplift flag - the linear q is fictitious there")
    print(f"  [2] kern             q_min(e=B/6) = {at_kern['q_min']:.3e} kPa   "
          f"q_max = q_min at e=0: {concentric['q_max']:.4f} kPa   "
          f"e > B/6 flags partial uplift: {outside['partial_uplift']}")

    # -- 3  lambda_s --------------------------------------------------------------
    guard("selftest.lambda_s_at_250", isclose(lambda_s(250.0), 1.0, rel_tol=1e-15),
          f"lambda_s(d=250) must be 1.0, got {lambda_s(250.0)!r}")
    prev = lambda_s(1.0)
    n_exec = 0
    for d_mm in range(1, 3001, 5):        # ONE distinct guard, many executions
        v = lambda_s(float(d_mm))
        guard("selftest.lambda_s_monotone_and_bounded",
              v <= 1.0 + 1e-15 and v <= prev + 1e-15,
              f"lambda_s must be <= 1 and non-increasing in d; broke at d = {d_mm} mm")
        prev = v
        n_exec += 1
    guard("selftest.lambda_s_below_one_above_250", lambda_s(600.0) < 1.0,
          "lambda_s falls below 1.0 as soon as d > 250 mm - R22.6.5.2 printed 454")
    print(f"  [3] lambda_s         lambda_s(250) = {lambda_s(250.0):.6f}   "
          f"lambda_s(600) = {lambda_s(600.0):.6f}   "
          f"monotone guard executed {n_exec} times (1 distinct guard)")

    # -- 4  bar spacing -----------------------------------------------------------
    # ==ACI's printed commentary anchor for this exact case is 250 mm (R24.3.2, p.503).
    #   The TABLE gives 255 mm.  The 5 mm is a rounding INSIDE THE COMMENTARY, and it
    #   is asserted here explicitly so that it is visible rather than hidden.==
    s50 = max_bar_spacing(f_s=280.0, c_c=50.0)
    guard("selftest.spacing_expr1_255", isclose(s50["expr1_380_mm"], 255.0, rel_tol=1e-12),
          f"380(280/280) - 2.5(50) must be 255 mm, got {s50['expr1_380_mm']!r}")
    guard("selftest.spacing_expr2_300", isclose(s50["expr2_300_mm"], 300.0, rel_tol=1e-12),
          "300(280/280) must be 300 mm")
    guard("selftest.spacing_governing_is_min",
          isclose(s50["s_max_mm"], min(255.0, 300.0), rel_tol=1e-12),
          "Table 24.3.2 is a 'Lesser of' - the governing value is min(255, 300)")
    guard("selftest.spacing_commentary_anchor_is_250",
          isclose(s50["commentary_anchor_mm"], 250.0, rel_tol=0, abs_tol=1e-12)
          and abs(s50["expr1_380_mm"] - s50["commentary_anchor_mm"]) == 5.0,
          "ACI R24.3.2 p. 503 prints 250 mm for this case; the table gives 255 mm - "
          "the 5 mm rounding lives in the commentary and is recorded, not smoothed")
    s75 = max_bar_spacing(f_s=280.0, c_c=75.0)
    guard("selftest.spacing_cover75_1925", isclose(s75["s_max_mm"], 192.5, rel_tol=1e-12),
          f"max_bar_spacing(f_s=280, c_c=75) must be 192.5 mm, got {s75['s_max_mm']!r}")
    s_default = max_bar_spacing(fy=420.0)
    guard("selftest.spacing_default_cover_is_75",
          isclose(s_default["c_c_mm"], 75.0, rel_tol=0, abs_tol=1e-12)
          and isclose(s_default["s_max_mm"], 192.5, rel_tol=1e-12),
          "the footing bottom-mat default is 75 mm cover with f_s = (2/3) f_y")
    print(f"  [4] bar spacing      c_c=50: expr1 = {s50['expr1_380_mm']:.1f} mm, "
          f"expr2 = {s50['expr2_300_mm']:.1f} mm, governing = {s50['s_max_mm']:.1f} mm "
          f"(ACI commentary anchor 250 mm - 5 mm rounding, recorded)")
    print(f"                       c_c=75: s = {s75['s_max_mm']:.1f} mm   "
          f"default (fy=420, 75 mm cover): s = {s_default['s_max_mm']:.1f} mm")

    # -- 5  two-way v_c reduces to 0.33 lambda sqrt(f'c) ---------------------------
    fc = 28.0
    tw = vc_two_way(fc=fc, bo=200.0, dx=500.0, dy=520.0, beta=1.0,
                    column_case="interior",
                    rigid_and_continuously_soil_supported=True)
    target = 0.33 * sqrt(fc)
    guard("selftest.two_way_reduces_to_033",
          isclose(tw["v_c_ACI318_25M_MPa"], target, rel_tol=1e-12)
          and isclose(tw["v_c_NSCP2015_MPa"], target, rel_tol=1e-12)
          and tw["governing_row_ACI"] == "(a)" and tw["governing_row_NSCP"] == "(a)",
          "with beta -> 1 and alpha_s d / b_o large, row (a) governs and v_c is "
          "0.33 lambda sqrt(f'c) in BOTH tables")
    cap = vc_two_way(fc=100.0, bo=4000.0, dx=500.0, dy=520.0, beta=1.5,
                     column_case="interior",
                     rigid_and_continuously_soil_supported=True)
    guard("selftest.two_way_sqrt_fc_cap",
          isclose(cap["v_c_ACI318_25M_MPa"], 0.33 * SQRT_FC_CAP_MPA, rel_tol=1e-12),
          "sqrt(f'c) is capped at 8.3 MPa for two-way shear - §22.6.3.1 / §422.6.3.1")
    flex = vc_two_way(fc=fc, bo=4000.0, dx=500.0, dy=520.0, beta=1.5,
                      column_case="interior",
                      rigid_and_continuously_soil_supported=False)
    guard("selftest.two_way_lambda_s_only_in_aci",
          flex["v_c_ACI318_25M_MPa"] < flex["v_c_NSCP2015_MPa"],
          "with the gate NOT asserted, lambda_s reduces the ACI value and has no NSCP "
          "counterpart - the one substantive divergence in Table 22.6.5.2")
    print(f"  [5] two-way v_c      beta->1, large alpha_s d/b_o: "
          f"ACI {tw['v_c_ACI318_25M_MPa']:.5f} = NSCP {tw['v_c_NSCP2015_MPa']:.5f} "
          f"= 0.33*sqrt(f'c) = {target:.5f} MPa")
    print(f"                       gate false: ACI {flex['v_c_ACI318_25M_MPa']:.5f} < "
          f"NSCP {flex['v_c_NSCP2015_MPa']:.5f} MPa   (lambda_s = {flex['lambda_s']:.5f})")

    # -- 6  one-way V_c: equal with the gate, divergent without --------------------
    gated = vc_one_way(fc=28.0, bw=1000.0, d=600.0,
                       rigid_and_continuously_soil_supported=True)
    guard("selftest.one_way_gate_true_codes_equal", gated["codes_agree"] is True
          and isclose(gated["V_c_NSCP2015_N"], gated["V_c_ACI318_25M_N"], rel_tol=1e-12),
          "with §13.2.6.2 asserted, ACI hands the flat form back and the two codes "
          "give the identical V_c")
    slender = vc_one_way(fc=28.0, bw=1000.0, d=600.0, rho_w=0.0018,
                         rigid_and_continuously_soil_supported=False)
    guard("selftest.one_way_gate_false_codes_differ",
          slender["codes_agree"] is False
          and slender["V_c_ACI318_25M_N"] < slender["V_c_NSCP2015_N"],
          "for a slender footing off a spring model, Table 22.5.5.1 row (c) with "
          "lambda_s and rho_w gives materially less than NSCP's flat form")
    guard("selftest.one_way_floor_0083_bounds_the_loss",
          slender["aci_floor_0083_applied"] is True
          and isclose(slender["V_c_ACI318_25M_N"],
                      0.083 * sqrt(28.0) * 1000.0 * 600.0, rel_tol=1e-12),
          "§22.5.5.1.1 floors V_c at 0.083 lambda sqrt(f'c) b_w d - just under half "
          "the flat 0.17 form; that floor is the honest mitigation")
    try:
        vc_one_way(fc=28.0, bw=1000.0, d=600.0,
                   rigid_and_continuously_soil_supported=False)
        raised = False
    except ValueError:
        raised = True
    guard("selftest.one_way_requires_rho_w_when_ungated", raised,
          "with the gate not asserted, rho_w is mandatory - the caller owes the full "
          "table, not a silent fallback to the flat form")
    ratio = slender["V_c_ACI318_25M_N"] / slender["V_c_NSCP2015_N"]
    print(f"  [6] one-way V_c      gate TRUE  : NSCP = ACI = "
          f"{gated['V_c_NSCP2015_N'] / 1000.0:,.1f} kN")
    print(f"                       gate FALSE : NSCP {slender['V_c_NSCP2015_N'] / 1000:,.1f} kN"
          f"  vs ACI {slender['V_c_ACI318_25M_N'] / 1000:,.1f} kN  "
          f"(ratio {ratio:.3f}; §22.5.5.1.1 floor applied)")

    # -- 7  phi: agreement and the transition-band divergence ----------------------
    fy = 420.0
    eps_ty = fy / ES_REBAR_MPA                                    # 0.0021
    tc = 0.0060                                                   # >= 0.005 and >= eps_ty+0.003
    guard("selftest.phi_agree_tension_controlled",
          isclose(phi_flexure(tc, fy, Code.ACI318_25M), 0.90, rel_tol=0, abs_tol=1e-15)
          and isclose(phi_flexure(tc, fy, Code.NSCP2015), 0.90, rel_tol=0, abs_tol=1e-15),
          "for Grade 420 both codes give phi = 0.90 once the section is "
          "tension-controlled under both rules (eps_t >= eps_ty + 0.003 = 0.0051)")
    mid = 0.0035                                                  # inside both bands
    pa, pn = (phi_flexure(mid, fy, Code.ACI318_25M),
              phi_flexure(mid, fy, Code.NSCP2015))
    guard("selftest.phi_differ_in_transition", not isclose(pa, pn, rel_tol=0, abs_tol=1e-9),
          f"inside the transition band the two rules must differ; got ACI {pa!r} and "
          f"NSCP {pn!r}")
    # ==Recorded, not smoothed: at EXACTLY eps_t = 0.005 the two do NOT agree.  NSCP's
    #   band top is a fixed 0.005 (phi = 0.90); ACI's is eps_ty + 0.003 = 0.0051, so ACI
    #   is still in transition there.  The brief's "agree at eps_t >= 0.005" holds for
    #   eps_t >= 0.0051, not at the NSCP band edge itself.==
    pa5, pn5 = (phi_flexure(0.005, fy, Code.ACI318_25M),
                phi_flexure(0.005, fy, Code.NSCP2015))
    guard("selftest.phi_band_edge_0005_divergence",
          isclose(pn5, 0.90, rel_tol=0, abs_tol=1e-15) and pa5 < 0.90
          and abs(pn5 - pa5) > 1e-3,
          "at eps_t = 0.005 exactly, NSCP is tension-controlled (0.90) while ACI is "
          "still in transition - this is the divergence note 04 §4.2 flags")
    print(f"  [7] phi              eps_t = 0.0060 : ACI {phi_flexure(tc, fy, Code.ACI318_25M):.4f}"
          f" = NSCP {phi_flexure(tc, fy, Code.NSCP2015):.4f}")
    print(f"                       eps_t = 0.0035 : ACI {pa:.4f} vs NSCP {pn:.4f}   "
          f"(transition, DIVERGENT)")
    print(f"                       eps_t = 0.0050 : ACI {pa5:.4f} vs NSCP {pn5:.4f}   "
          f"(NSCP band top is fixed 0.005; ACI's is eps_ty+0.003 = {eps_ty + 0.003:.5f})")

    # -- 8  presumptive bearing: the +20 % rule and its 3x cap ---------------------
    big = presumptive_bearing(3, width_mm=3000.0, depth_mm=3000.0)
    guard("selftest.presumptive_cap_is_exactly_3x",
          isclose(big["increase_factor"], 3.0, rel_tol=0, abs_tol=1e-12)
          and big["capped_at_3x"] is True,
          f"Table 304-1 caps the increase at exactly three times the designated value; "
          f"got {big['increase_factor']!r}")
    guard("selftest.presumptive_capped_value",
          isclose(big["q_allow_kPa"], 300.0, rel_tol=1e-12),
          "row 3 base 100 kPa x 3 = 300 kPa at the cap")
    one_step = presumptive_bearing(3, width_mm=600.0, depth_mm=300.0)
    guard("selftest.presumptive_20pc_per_300mm",
          isclose(one_step["increase_factor"], 1.20, rel_tol=1e-12),
          "one additional 300 mm of width is +20 %")
    n_exec2 = 0
    for w in range(300, 6001, 150):
        for dep in range(300, 6001, 300):
            f = presumptive_bearing(3, width_mm=float(w), depth_mm=float(dep))
            guard("selftest.presumptive_factor_never_exceeds_3",
                  f["increase_factor"] <= 3.0 + 1e-12,
                  f"cap breached at w={w}, d={dep}")
            n_exec2 += 1
    clay = presumptive_bearing(5, width_mm=3000.0, depth_mm=600.0)
    guard("selftest.presumptive_row5_no_width_increase",
          clay["increments_width"] == 0 and isclose(clay["increase_factor"], 1.20,
                                                    rel_tol=1e-12),
          "row 5 footnote c: no increase for an increase of WIDTH - depth only")
    try:
        presumptive_bearing(1, width_mm=1000.0, depth_mm=1000.0)
        rock_raised = False
    except ValueError:
        rock_raised = True
    guard("selftest.presumptive_rock_gate_required", rock_raised,
          "rows 1 and 2 state UCT and RQD inside the row; they are required arguments "
          "with no default")
    rock = presumptive_bearing(1, width_mm=300.0, depth_mm=300.0,
                               uct_MPa=3.5, rqd_percent=80.0)
    guard("selftest.presumptive_rock_with_evidence",
          isclose(rock["q_allow_kPa"], 1000.0, rel_tol=1e-12),
          "with UCT and RQD evidenced, row 1 gives 1,000 kPa at the base geometry")
    print(f"  [8] presumptive      +20 %/300 mm: factor(600,300) = "
          f"{one_step['increase_factor']:.2f}   cap: factor(3000,3000) = "
          f"{big['increase_factor']:.2f} (exactly 3x)   "
          f"cap guard executed {n_exec2} times (1 distinct guard)")

    # -- 9  the honesty rules themselves -------------------------------------------
    sl = check_sliding(H=100.0, N=800.0, area=6.0, dead_load=800.0, FS=1.5, mu=0.35)
    guard("selftest.FS_flag_present",
          any(NOT_CITED in f for f in sl["flags"]),
          "every FS-bearing result must carry the (not vault-cited) flag")
    capped = check_sliding(H=100.0, N=2000.0, area=6.0, dead_load=400.0, FS=1.5, mu=0.35)
    guard("selftest.sliding_half_dead_load_applied",
          isclose(capped["resistance_kN"], 200.0, rel_tol=1e-12),
          "Table 304-1 footnote: total lateral sliding resistance <= one-half the "
          "dead load (0.5 x 400 = 200 kN), not 0.35 x 2000 = 700 kN")
    clay_sl = check_sliding(H=100.0, N=800.0, area=6.0, dead_load=5000.0, FS=1.5,
                            mu=0.9, silts_or_clays=True)
    guard("selftest.sliding_half_normal_force_applied",
          isclose(clay_sl["friction_kN"], 400.0, rel_tol=1e-12),
          "NSCP §305.7.4.1: friction on silts and clays limited to one half of the "
          "normal force (0.5 x 800 = 400 kN), not 0.9 x 800 = 720 kN")
    try:
        check_sliding(H=100.0, N=800.0, area=6.0, dead_load=800.0, FS=1.5,
                      mu=0.25, cohesive_resistance_kPa=7.0)
        both_raised = False
    except ValueError:
        both_raised = True
    guard("selftest.sliding_mechanisms_not_additive", both_raised,
          "Table 304-1's friction coefficient and flat sliding resistance are "
          "ALTERNATIVES, not additives")
    st = settlement_report(18.0, source="Geotech report Rev.B, 2026-08-12, J. Cruz",
                           criterion_mm=25.0,
                           criterion_source="client brief 2026-07-30, cl. 4.2")
    guard("selftest.settlement_refuses_verdict",
          st["verdict"] is None and st["results"][0].passed is None
          and isinstance(st["refusal"], Refusal)
          and st["refusal"].sentence == REFUSAL,
          "settlement_report() must refuse to pass or fail and must carry the exact "
          "refusal sentence")
    cw = crack_width_limit(exposure="severe", bar="20 mm")
    guard("selftest.crack_width_refuses",
          isinstance(cw, Refusal) and cw.sentence == REFUSAL and bool(cw) is False,
          "crack_width_limit() must return the exact refusal sentence and be falsy")
    strip = min_flexural_steel(footing_type="one_way_strip", fc=28.0, fy=420.0,
                               Ag_mm2=1000.0 * 600.0, bw_mm=1000.0, d_mm=530.0)
    guard("selftest.strip_min_steel_is_ambiguous",
          strip["status"] == "AMBIGUOUS" and strip["resolved"] is False
          and isinstance(strip["nscp_strip_refusal"], Refusal),
          "§13.3.2.1 routes a strip footing to both Chapter 7 and Chapter 9 and does "
          "not resolve which governs - the result must say AMBIGUOUS")
    two_way = min_flexural_steel(footing_type="two_way_isolated", fc=28.0, fy=420.0,
                                 Ag_mm2=1000.0 * 600.0)
    guard("selftest.two_way_min_steel_resolved",
          two_way["status"] == "RESOLVED" and two_way["codes_agree"] is True,
          "for Grade 420 the two-way isolated footing minimum is 0.0018 A_g under "
          "both codes")
    st275 = shrinkage_temperature_steel(275.0, 1000.0 * 600.0)
    guard("selftest.st_divergence_grade275",
          st275["diverges"] is True and isclose(st275["ratio_NSCP2015"], 0.0020,
                                                rel_tol=1e-12)
          and st275["aci_conservative_here"] is False,
          "for f_y < 420 NSCP requires 0.0020 and ACI's flat 0.0018 is LESS - the "
          "flat ratio is not uniformly conservative")
    st550 = shrinkage_temperature_steel(550.0, 1000.0 * 600.0)
    guard("selftest.st_divergence_grade550",
          st550["diverges"] is True and isclose(st550["ratio_NSCP2015"], 0.0014,
                                                rel_tol=1e-12),
          "for Grade 550 NSCP gives the greater of 0.001375 and 0.0014 -> 0.0014")
    print(f"  [9] honesty rules    FS flagged {NOT_CITED} - OK;  sliding ceilings "
          f"{capped['resistance_kN']:.0f} kN and {clay_sl['friction_kN']:.0f} kN - OK")
    print(f"                       settlement: NO VERDICT - OK;  crack width: refusal "
          f"- OK;  strip A_s,min: {strip['status']} - OK")

    # -- 10  load-level separation and the 0.6D helper -----------------------------
    try:
        Loads(1000.0, level="service") + Loads(1400.0, level="factored")
        mixed = False
    except AssertionError:
        mixed = True
    guard("selftest.load_levels_never_mix", mixed,
          "a service set added to a factored set must raise - note 01 §1")
    sc = nscp_strength_combinations(service_level_wind=True)
    labels = dict((lbl.split()[0], f) for lbl, f in sc)
    guard("selftest.wind_rider_16W",
          isclose(labels["405.3.1d"]["W"], 1.6, rel_tol=1e-12)
          and isclose(labels["405.3.1f"]["W"], 1.6, rel_tol=1e-12)
          and isclose(labels["405.3.1c-W"]["W"], 0.8, rel_tol=1e-12),
          "§405.3.5: 1.6W in place of 1.0W in (d) and (f), 0.8W in place of 0.5W in (c)")
    sc0 = nscp_strength_combinations(service_level_wind=False)
    labels0 = dict((lbl.split()[0], f) for lbl, f in sc0)
    guard("selftest.wind_rider_off",
          isclose(labels0["405.3.1d"]["W"], 1.0, rel_tol=1e-12)
          and isclose(labels0["405.3.1c-W"]["W"], 0.5, rel_tol=1e-12),
          "without the rider the table's printed 1.0W and 0.5W stand")
    lc = stability_load_case(1000.0, W=200.0, dead_factor_used=1.0)
    guard("selftest.one_point_zero_D_warned",
          len(lc["warnings"]) == 1 and "0.6D" in lc["warnings"][0],
          "checking overturning under 1.0D must produce a warning - §203.4 alternate "
          "basic combinations factor the resisting dead load down to 0.6D")
    lc06 = stability_load_case(1000.0, W=200.0, dead_factor_used=0.6)
    guard("selftest.zero_point_six_D_clean", lc06["warnings"] == (),
          "0.6D produces no warning")
    svc = nscp_service_combinations()
    guard("selftest.203_untranscribed_declared",
          set(svc["alternate_basic_not_transcribed"]) ==
          {"203-13", "203-16", "203-17", "203-18"}
          and len(svc["basic_untranscribed"]) == 1,
          "the untranscribed §203.4 equations must be declared absent, never guessed")
    print(f"  [10] combinations    service/factored never mix - OK;  §405.3.5 rider "
          f"1.6W/0.8W - OK;  1.0D overturning warned - OK")

    # -- 11  critical sections and concrete bearing --------------------------------
    cs_col = critical_sections(supported_member="column", member_dim_mm=500.0,
                               d_mm=530.0)
    guard("selftest.critical_section_column_face",
          isclose(cs_col["moment_section_from_centreline_mm"], 250.0, rel_tol=1e-12)
          and isclose(cs_col["one_way_shear_from_centreline_mm"], 780.0, rel_tol=1e-12)
          and isclose(cs_col["two_way_perimeter_from_centreline_mm"], 515.0,
                      rel_tol=1e-12),
          "column row: moment at the face, one-way at face + d, two-way at face + d/2")
    cs_bp = critical_sections(supported_member="column_with_base_plate",
                              member_dim_mm=300.0, d_mm=400.0,
                              base_plate_dim_mm=600.0)
    guard("selftest.critical_section_base_plate_moves_datum",
          isclose(cs_bp["moment_section_from_centreline_mm"], 225.0, rel_tol=1e-12)
          and isclose(cs_bp["one_way_shear_from_centreline_mm"], 625.0, rel_tol=1e-12),
          "base plate: datum is halfway between column face (150) and plate edge "
          "(300) = 225 mm, and BOTH shear sections move with it - §13.2.7.2 p. 210")
    cs_mw = critical_sections(supported_member="masonry_wall", member_dim_mm=400.0,
                              d_mm=300.0)
    guard("selftest.critical_section_masonry_inward",
          isclose(cs_mw["moment_section_from_centreline_mm"], 100.0, rel_tol=1e-12),
          "masonry wall: halfway between centre (0) and face (200) = 100 mm")
    br = bearing_strength_concrete(fc=28.0, A1_mm2=500.0 * 500.0,
                                   supporting_surface_wider_all_sides=True,
                                   A2_mm2=2000.0 * 2000.0)
    guard("selftest.bearing_lesser_of_caps_at_2",
          isclose(br["B_n_N"], 2.0 * 0.85 * 28.0 * 250000.0, rel_tol=1e-12)
          and br["governing_row"] == "(b)",
          "sqrt(A2/A1) = 4 here, so row (b) - the 'lesser of' - governs at "
          "2*(0.85 f'c A1); quoted as printed, not as an inequality on the radical")
    guard("selftest.bearing_phi_065",
          isclose(br["phi"], 0.65, rel_tol=0, abs_tol=1e-15),
          "phi for bearing = 0.65, ACI Table 21.2.1(d) p. 430 / NSCP Table "
          "421.2.1(d) folio `4-139`")
    print(f"  [11] sections        column face 250 mm -> V at 780 mm, punching at "
          f"515 mm;  base plate datum {cs_bp['moment_section_from_centreline_mm']:.0f} mm")
    print(f"                       concrete bearing phi*B_n = "
          f"{br['phi_B_n_N'] / 1000.0:,.0f} kN, row {br['governing_row']} (lesser of)")

    # -- 12  flexural design end to end --------------------------------------------
    fx = flexural_design(fc=28.0, fy=420.0, b=1000.0, d=530.0, As=1800.0)
    guard("selftest.flexure_beta1_085_at_28",
          isclose(fx["beta1_ACI318_25M"], 0.85, rel_tol=1e-12)
          and isclose(fx["beta1_NSCP2015"], 0.85, rel_tol=1e-12),
          "beta_1 = 0.85 for 17 <= f'c <= 28 in both tables")
    guard("selftest.flexure_a_beta1_c",
          isclose(fx["a_mm"], fx["beta1_ACI318_25M"] * fx["c_mm_ACI318_25M"],
                  rel_tol=1e-12),
          "a = beta_1 c - §22.2.2.4.1 p. 438")
    b1a, b1n = beta1(55.0, Code.ACI318_25M), beta1(55.0, Code.NSCP2015)
    guard("selftest.beta1_55MPa_boundary_divergence",
          not isclose(b1a, b1n, rel_tol=0, abs_tol=1e-12)
          and isclose(b1a, 0.65, rel_tol=1e-12),
          "at exactly 55 MPa the transcribed inequality signs put ACI in row (c) and "
          "NSCP in row (b) - flagged, not smoothed")
    print(f"  [12] flexure         phi*M_n NSCP {fx['phiMn_Nmm_NSCP2015'] / 1e6:,.1f} kN-m"
          f"   ACI {fx['phiMn_Nmm_ACI318_25M'] / 1e6:,.1f} kN-m   "
          f"eps_t = {fx['eps_t_ACI318_25M']:.5f}")
    print(f"                       beta_1 at exactly 55 MPa: ACI {b1a:.4f} vs NSCP "
          f"{b1n:.4f} - transcription boundary, flagged")

    # -- 13  overturning, uplift, base area, equivalent square ---------------------
    ot = check_overturning(M_driving=300.0, N_resisting=900.0, dimension=2.4, FS=2.0,
                           direction="B")
    guard("selftest.overturning_lever_arm",
          isclose(ot["M_resisting"], 900.0 * 1.2, rel_tol=1e-12)
          and isclose(ot["FS_computed"], 1080.0 / 300.0, rel_tol=1e-12),
          "M_R = N * d/2 about the toe, FS = M_R / M_O")
    guard("selftest.overturning_FS_flagged",
          any(NOT_CITED in f for f in ot["flags"]) and ot["passed"] is True,
          "the overturning FS must carry the (not vault-cited) flag")
    up = check_uplift(T_uplift=200.0, N_resisting=260.0, FS=1.5)
    guard("selftest.uplift_fs_and_flag",
          isclose(up["FS_computed"], 1.3, rel_tol=1e-12) and up["passed"] is False
          and any(NOT_CITED in f for f in up["flags"]),
          "FS uplift = N/T, flagged, and 1.3 < 1.5 must FAIL")
    try:
        check_uplift(T_uplift=200.0, N_resisting=900.0, FS=1.5,
                     variable_contents_included=True)
        contents_raised = False
    except ValueError:
        contents_raised = True
    guard("selftest.uplift_rejects_variable_contents", contents_raised,
          "equipment operating (contents-inclusive) weight must not be counted as "
          "restoring load - Foundation Design (MIDAS)/02, finding F6")
    ba = base_area_required(1200.0, 100.0)
    guard("selftest.base_area_service_only",
          isclose(ba.value, 12.0, rel_tol=1e-12)
          and any(NSCP_OCR in f for f in ba.flags),
          "A = P_service / q_allow, with the NSCP OCR marker attached")
    try:
        require_service(Loads(1400.0, level=Loads.FACTORED), "base area sizing")
        svc_raised = False
    except AssertionError:
        svc_raised = True
    guard("selftest.base_area_refuses_factored", svc_raised,
          "sizing a base area from a factored set must raise - NSCP §413.3.1.1 "
          "folio `4-84` says UNFACTORED in mandatory text")
    eq = equivalent_square_side(600.0)
    guard("selftest.equivalent_square_is_area_not_diameter",
          isclose(eq, sqrt(3.141592653589793 * 600.0 ** 2 / 4.0), rel_tol=1e-12)
          and eq < 600.0,
          "§13.2.7.3 p. 211 says equivalent AREA, not equivalent diameter")
    guard("selftest.cover_cast_against_ground_75",
          isclose(cover_table()["cast_against_and_permanently_in_contact_with_ground"],
                  75.0, rel_tol=0, abs_tol=1e-12),
          "Table 20.5.1.3.1 p. 421 / NSCP Table 420.6.1.3.1 folio `4-136`: 75 mm")
    hT = nscp_H_and_T_factors()
    guard("selftest.H_and_T_riders",
          isclose(hT["T_min_factor"], 1.0, rel_tol=1e-12)
          and isclose(hT["H_adds_to_effect"], 1.6, rel_tol=1e-12)
          and isclose(hT["H_permanent_and_counteracts"], 0.9, rel_tol=1e-12),
          "§405.3.6 and §405.3.8 riders")
    print(f"  [13] stability       FS_OT = {ot['FS_computed']:.3f} (req 2.0) PASS;  "
          f"FS_uplift = {up['FS_computed']:.3f} (req 1.5) FAIL - both flagged")
    print(f"                       base area = {ba.value:.2f} m2 from SERVICE load; "
          f"equivalent square for D600 = {eq:.1f} mm")

    distinct, executions = guard_totals()
    print("-" * 92)
    print(guard_table())
    print("-" * 92)
    print(f"  ASSERTION GUARDS - DISTINCT: {distinct}      EXECUTIONS: {executions}")
    print("  (a guard inside a loop is ONE distinct guard however many times it runs)")
    print("=" * 92)
    print("  ALL SELF-TESTS PASSED")
    return True


def _banner_flags() -> None:
    print()
    print("STANDING FLAGS carried by every run of this module")
    print("  * FS for sliding / overturning / uplift  ->  " + NOT_CITED)
    print("      NSCP §304.1(e) folio `3-12` delegates it; ACI 318 prints none "
          "(verified negative, both editions)")
    print("  * settlement limit                       ->  " + NOT_CITED
          + "; no verdict is issued")
    print("  * every NSCP constant                    ->  " + NSCP_OCR)
    print("  * Table 304-1 rows 3, 4, 5               ->  150 dpi read only, "
          "PROVISIONAL")
    print("  * NSCP §305.7.4.1                        ->  folio not recorded by the "
          "digest")
    print("  * crack width, NSCP §409.6.1.2           ->  refusal returned")
    print("  * the linear q = P/A(1 +- 6e/B) form     ->  statics, " + NOT_CITED)
    print()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        try:
            _selftest()
        except AssertionError as exc:
            print(f"\n*** SELF-TEST FAILED ***\n{exc}", file=sys.stderr)
            d, e = guard_totals()
            print(f"guards distinct {d}, executions {e}", file=sys.stderr)
            sys.exit(1)
        _banner_flags()
        sys.exit(0)
    print(__doc__)
    print("Run  python3 dp_foundation.py --selftest")
