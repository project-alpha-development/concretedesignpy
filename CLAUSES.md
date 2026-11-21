# concretedesignpy — Clause Register (beam flexure, shear, torsion, joint shear)

**Generated** 2026-08-15 · **Basis** ACI 318-25M and Wight & MacGregor 7th, read from
`vault/reference/` · **Scope** `calculators/beam_moment.py`, `calculators/beam_shear.py`,
`calculators/joint_shear.py`

> [!abstract] What this file is
> Part A is the **clause register** — every provision these four modules implement, with the
> printed page it was verified on. Part B is the **rectification record** against
> `Software/14 - concretedesignpy Review`. Part C is **what is still open**.
>
> Every page below was opened and read. The four numeric tables (18.8.4.3, 22.7.4.1(a),
> 22.7.5.1, 15.5.2.2's figure) were read from a **rendered image**, not a text search, because
> the extraction interleaves their rows. An adversarial pass then corrected **three citations
> in the audit note itself** before this file was issued — see Part B.5.
>
> ⛔ **This file covers the four beam/joint modules only.** `column_jacket*`, `frp_*`,
> `column_biaxial/flexural/interaction`, `moment_curvature`, `development_length`,
> `beam_deflection`, `mander`, `rebar_layout`, `mgt/` and `stress-strain/` are **out of scope
> and were not reviewed or touched**. Several of those legitimately target ACI 318-19.

---

## 0. Basis position — read before using any number in this file

| Question | Position |
|---|---|
| Which edition do these modules target? | **NSCP 2015**, the governing Philippine code, whose beam and joint provisions follow **ACI 318M-14**. Decided explicitly, 2026-08-15 (Option A). |
| What did they *claim* before? | **ACI 318-19**, in every docstring. They never implemented it. Right code, wrong label — worse than the reverse, because it passes review. Corrected. |
| So the pre-2019 φ law is a bug? | **No.** `εt ≥ 0.005` is NSCP 2015 / ACI 318-14 and is **correct as written**. ACI 318-19/-25 Table 21.2.2 replaced it with `εt ≥ εty + 0.003` (+7.5 % at Grade 550, +15.5 % at Grade 690). Moving is an **edition change**, not a fix. |
| So the 3-row joint γ table is a bug? | **No.** `{1.7, 1.2, 1.0}` **is** NSCP 2015 Table 418.8.4.1. ACI 318-25M Table 18.8.4.3 has **eight** rows. Same answer: edition change, not a fix. |
| Is the missing size-effect `λs` a bug? | **No**, and it should not be added under NSCP 2015. It arrives with ACI 318-19 Table 22.5.5.1 for `Av < Av,min`. |
| Does NSCP 2015 govern acceptance? | **Yes.** ACI 318-25M is cited here as the *readable, page-verifiable* statement of provisions NSCP 2015 carries. Where the two round differently, **the SI value printed in ACI 318M is used**. |

**Page-offset register used (from `reference/README.md`, re-verified this pass):**

| File | Offset | Verified on |
|---|---|---|
| `ACI 318-25M - Building Code Requirements for Structural Concrete.pdf` | printed = **PDF − 1** | pp. 149, 151, 152, 160, 231, 232, 342, 430, 435, 442, 445, 463, 464, 465, 466 |
| `Manuals/Wight MacGregor - Reinforced Concrete Mechanics and Design 7th.pdf` | printed = **PDF − 1** | pp. 148, 170, 281, 282, 297, 349, 352, 353, 358, 363, 364, 366, 967, 1076 |
| `_Scanned/NSCP 2015 … Vol.1.pdf` | Ch. 4 folios are **chapter-relative** | ⚠ **not opened this pass** — see Part C |

⚠ **`ACI 318-19` on file is the INCH-POUND edition.** Nothing numeric is cited to it here;
`ACI 318-25M` is used for every coefficient.

⚠ **W&M 7th is written to ACI 318-14**, so it is a benchmark for **arithmetic, not for
provisions** — it cannot catch an edition finding, and it prints the pre-2019 φ rule on p. 169.
It also **rounds where the Code does not**: two pins in the test suite are deliberately looser
than 1 % for exactly this reason (Part B.4).

---

## Part A — Clause register

### A.1 Beam flexure — `beam_moment.calculate_beam_moment`

| Implemented as | Provision | Basis | Printed | Verdict |
|---|---|---|---|---|
| `_calculate_beta_one` | `β1` incl. the `f'c ≥ 55 → 0.65` floor | ACI 318-25M Table 22.2.2.4.3 | 438–439 | ✅ exact |
| `0.85 f'c a b` | Equivalent rectangular stress distribution | ACI 318-25M §22.2.2.4 | 438 | ✅ exact |
| `_strength_reduction_factor` | φ, tension-controlled at `εt ≥ 0.005` | **NSCP 2015 / ACI 318-14** | — | ✅ correct for NSCP; **not** 318-19 Table 21.2.2 (printed 430) |
| `Cs = A's(f's − 0.85 f'c)` for bars inside `a` | compression bars displace counted concrete | W&M Ex 4-4 step 5 | 170 | ✅ **fixed 2026-08-15** |
| *(absent)* | `As,min` | ACI 318-25M §9.6.1.2 | 149 | ⛔ **not checked — stated in the docstring** |
| *(absent)* | `ρ ≤ 0.025`, `Mn+ ≥ 0.5 Mn−` | ACI 318-25M §18.6.3.1 / §18.6.3.2 | — | ⛔ **not checked — stated in the docstring** |
| non-convergence → `ValueError` | — *(software)* | — | — | ⭐ raises rather than reporting a silent zero |

### A.2 Beam shear — `beam_shear`

| Implemented as | Provision | Basis | Printed | Verdict |
|---|---|---|---|---|
| `Vc = λ√f'c bw d / 6` | `Vc` for nonprestressed members | **ACI 318M-14 / NSCP 422.5** | — | ✅ correct for NSCP |
| `(1 + Nu/(14 Ag)) λ√f'c bw d / 6` | `Vc` with axial compression, §22.5.6.1 | W&M **Eq. (6-13a)** / **Eq. (6-13aM)** | 281 / 282 | ✅ **fixed 2026-08-15 — the unsupported cap was deleted** |
| `(1 + 0.29 Nu/Ag) λ√f'c bw d / 6` | `Vc` with axial tension | ACI 318M-14 §22.5.7.1 | — | ⚠ 0.29 ≈ 1/3.5; W&M Eq. (6-13bM) prints 1/3.33. **~2 % textbook rounding, not a bug** |
| `Vs = Av fyt d / s` | shear reinforcement strength | ACI 318-25M §22.5.8.5.3 | — | ✅ exact |
| `max(0.062√f'c bw/fyt, 0.35 bw/fyt)` | `Av,min` | ACI 318-25M **Table 9.6.3.4(a)/(b)** | **151** | ✅ **unified 2026-08-15** (was 1/16 in two places) |
| `Vu ≤ φ(Vc + 0.66√f'c bw d)` | cross-sectional limit | ACI 318-25M **§22.5.1.2** | **442** | ✅ **enforced everywhere 2026-08-15** |
| `s_max = min(d/2, 600)`, halved above `Vs = ⅓√f'c bw d` | stirrup spacing | ACI 318-25M Table 9.7.6.2.2 | 160 | ✅ exact |

### A.3 Beam torsion — `beam_shear.shear_torsion_design`

**The package's only implementation of §22.7.** The second one, `beam_torsion.torsion_design`,
was **deleted** 2026-08-15.

| Implemented as | Provision | Basis | Printed | Verdict |
|---|---|---|---|---|
| `Aoh` on the **stirrup** centreline | area enclosed by the outermost closed transverse reinforcement | ACI 318-25M **R22.7.6.1** | **465** | ✅ exact (`db_stirrup`, never the main bar) |
| `Tth = 0.083 λ√f'c Acp²/pcp · √(1 + Nu/(0.33 Ag λ√f'c))` | threshold torsion, solid section, rows (a) and (c) | ACI 318-25M **Table 22.7.4.1(a)** | **463** | ✅ **coefficient and `Nu` term both fixed 2026-08-15** |
| `Tcr = 0.33 λ√f'c Acp²/pcp · √(same)` | cracking torsion, rows (a) and (c) | ACI 318-25M **Table 22.7.5.1** | **464** | ✅ **fixed 2026-08-15** |
| `At/s = Tu/(φ · 1.7 Aoh · fyt)` | `Tn = 2 Ao At fyt cot θ / s`, `Ao = 0.85 Aoh`, θ = 45° | ACI 318-25M **Eq. (22.7.6.1a)** · **§22.7.6.1.1** · **§22.7.6.1.2(a)** | 465 · **466** · 466 | ✅ exact |
| `Aℓ = (Tu/φ) ph / (1.7 Aoh fy) cot θ` | `Tn = 2 Ao Aℓ fy tan θ / ph`, same `Ao`, same θ | ACI 318-25M **Eq. (22.7.6.1b)** · W&M **Eq. (7-36)** | 465 · 349 | ✅ **fixed 2026-08-15** (was `2 Aoh` → 15.00 % short) |
| `Aℓ,min = 0.42√f'c Acp/fy − (At/s) ph (fyt/fy)` | minimum longitudinal torsion steel | ACI 318-25M **§9.6.4.3(a)** | **152** | ✅ **coefficient fixed 2026-08-15** (was 5/12) · ⚠ see Part C |
| `(Av + 2At)/s ≥ max(0.062√f'c bw/fyt, 0.35 bw/fyt)` | minimum transverse for combined | ACI 318-25M §9.6.4.2 | 152 | ✅ exact |
| `s_max = min(ph/8, 300)` | torsional stirrup spacing | ACI 318-25M **§9.7.6.3.3** · W&M | **160** · 353 | ✅ exact (**300 mm**, never 305) |
| combined `√(v_shear² + v_torsion²) ≤ φ(Vc/bw d + 0.66√f'c)` | cross-sectional limit, solid | ACI 318-25M §22.7.7.1 | 466 | ✅ exact |
| *(absent)* | hollow-section rows, Table 22.7.4.1(b) | ACI 318-25M §22.7.4.1 | 463 | ⛔ **not implemented — stated in the docstring** |
| *(absent)* | torsional redistribution | ACI 318-25M §22.7.3 | — | ⛔ **not implemented — stated in the docstring** |

### A.4 Beam–column joint shear — `joint_shear.joint_shear_check`

| Implemented as | Provision | Basis | Printed | Verdict |
|---|---|---|---|---|
| `T = 1.25 As fy` | probable tensile force at the joint face | ACI 318-25M **§18.8.2.1** | **342** | ✅ exact |
| `Vj = T1 + T2 − Vcol` | joint shear at mid-height | ACI 318-25M §18.8.4.1 | 342 | ✅ exact · ⚠ see Part C |
| `bj = min(bcol, b + h, b + 2x)` | effective joint width | ACI 318-25M **§15.5.2.2** + **R15.5.2.2** | **231–232** | ✅ **column cap added 2026-08-15** |
| `x` measured **beam face → column face** | §15.5.2.2(b) is `2(b/2 + x) ≡ b + 2x`; Fig. R15.5.2.2 draws `b + 2x` | ACI 318-25M Fig. R15.5.2.2 | 232 | ✅ equivalent — **documented so it is not "fixed" back** |
| `γ ∈ {1.7, 1.2, 1.0}` | nominal joint shear strength | **NSCP 2015 Table 418.8.4.1** | 4-118 | ✅ correct for NSCP · ⚠ **carried, not re-read** — Part C |
| `λ ∈ {0.75, 1.0}` | lightweight / normalweight | ACI 318-25M **Table 15.5.2.1 footnote [1]** | **231** | ✅ **constrained 2026-08-15** |
| `φ = 0.85`, not overridable | SMF joints and diagonally reinforced coupling beams | ACI 318-25M **§21.2.4.4** | **435** | ✅ **fixed 2026-08-15** |
| *(absent)* | joint transverse reinforcement, bar development, column/beam strength ratio | — | — | ⛔ **not checked — stated in the docstring** |

---

### A.5 Masonry — `concretedesignpy.masonry` (interim)
Clause register lives in the Mind vault manifest (`03_Modelling/Solvers/manifests/concretedesignpy.json`,
entries with `register: masonry …`); notes NSCP2015-701 … -710, -204-T204-2, -103-T103-1, ASCE41-17-11.2.

## Part B — Rectification record

Against `Software/14 - concretedesignpy Review — Beam Flexure, Shear, Torsion & Joint Shear`,
§8. Nine commits on `rectify/note-14-beam-torsion-joint`.

### B.1 Closed

| # | Finding | Fix | Effect |
|---|---|---|---|
| **P0** | F-7 — two implementations of §22.7, 1000× apart | `beam_torsion.py` **deleted**; `/api/beam/torsion` → `shear_torsion_design()`; template's dead `t_threshold`/`torsion_status` keys replaced | φT_th **7 957.84 → 7.958 kN·m**; *"MAY NEGLECT"/"PASS"* → *"Design for Torsion"*; the UI now renders at all |
| **P1a** | F-9 — `Aℓ` 15.00 % short | `2·φ·aoh` → `1.7·φ·aoh` | **694 → 816.2 mm²** (book 816) |
| **P1b** | F-10 — no column cap on `Aj` | `column_width` **required, keyword-only**; `bj = min(bcol, b+h, b+2x)` | spandrel `Aj` **300 000 → 240 000 mm²**, φVn **−20 %**; omitting the argument now raises `TypeError` |
| **P2a** | F-3, F-4 | `Av,min` on both branches; §22.5.1.2 cap returns `spacing = None` + explicit `UNSAFE` | wide light web: **s 400 → 314 mm**; over-stressed sections return no spacing at all |
| **P2b** | F-11 | enum → `NSCP_2015_TABLE_418_8_4_1`; `λ` constrained; `φ` fixed; **unknown `joint_config` now raises instead of scoring 1.0** | values unchanged (Option A) |
| **P3** | F-1 | `Cs = A's(f's − 0.85 f'c)`, **inside depth `a` only** | W&M Ex 4-4 `c` **5.99 → 6.184 in.** (book 6.2); `Mn` 428.2 → 426.7 k-ft |
| **P3** | F-5 | the §22.5.6.1 second branch **deleted** | **no numeric change** — see B.3 |
| **P3** | F-6 | one `Av,min` constant, 0.062 | 0.8 % where branch (a) governs |
| **P3** | §4.4 | `Nu` term added to both thresholds; `1/12`→`0.083`, `1/3`→`0.33`, `5/12`→`0.42`; `vs_status` surfaced | φT_th **−0.40 %**, φT_cr **−1.00 %**, both **toward designing for torsion** |
| **P4** | — | three modules and two templates relabelled NSCP 2015; each states what it does **not** check | — |
| **F-8** | `Aoh` on the main bar | **moot by deletion** — the surviving function always used `db_stirrup` | — |
| **F-2** | strain-based φ | **not applicable under Option A** — recorded, not applied | — |

### B.2 Before / after

| Quantity | Before | After | Change | Book | After vs book |
|---|---|---|---|---|---|
| Ex 4-1M `Mn` (kN·m) | 272.50 | 272.50 | — | 273 | −0.18 % |
| Ex 4-4 `Mn` (k-ft) | 428.2 | 426.7 | −0.35 % | 428 | −0.30 % |
| Ex 4-4 `c` (in.) | 5.992 | **6.184** | **+3.20 %** | 6.2 | **−0.26 %** |
| Ex 6-1M `Vc` (kN) | 152.5 | 152.5 | — | 153 | −0.33 % |
| Ex 6-1M `s` (mm) | 214.12 | 214.12 | — | 215 | −0.41 % |
| Ex 7-2 φT_th (kN·m) | 7.9898 | **7.958** | −0.40 % | 7.959 | **−0.02 %** |
| Ex 7-2 φT_cr (kN·m) | 31.959 | 31.640 | −1.00 % | — | — |
| Ex 7-2 `At/s` (mm²/mm) | 0.5183 | 0.5183 | — | 0.5183 | 0.00 % |
| Ex 7-2 `Aℓ` (mm²) | 693.76 | **816.2** | **+17.65 %** | 819.4 | **−0.39 %** |
| Ex 19-3 `Vj` (kN) | 1838.0 | 1838.0 | — | 1837.1 | +0.05 % |
| Ex 19-3 `Aj` (mm²) | 371 612 | 371 612 | — | 371 612 | 0.00 % |
| Ex 19-3 φVn (kN) | 2820.0 | 2820.0 | — | 2753 | +2.43 % ⚠ |
| Spandrel `Aj` (mm²) | 300 000 | **240 000** | **−20.00 %** | 240 000 | **0.00 %** |
| Spandrel φVn (kN) | 2293.9 | **1835.1** | **−20.00 %** | — | — |

⚠ The Ex 19-3 φVn **+2.43 % is not an error** — W&M works in psi with γ = 20; NSCP 2015 and
ACI 318M print **1.7**, and 20/12 = 1.667. SI-vs-inch-pound rounding of one coefficient
(W&M Eq. 17-22b, printed 967).

### B.3 F-5 — downgraded twice, then deleted rather than replaced

The audit called the §22.5.6.1 second branch *"wrong on the page, numerically inert"*. Both
halves were re-tested.

- **Inert, proved rather than sampled.** The ratio of the two branches is
  `1.8(1 + 0.3q)/(1 + q/14)` with `q = Nu/Ag ≥ 0`. It equals **1.8 at `Nu = 0`** and only rises,
  because `0.3 > 1/14`. `min()` could never select it. 200 000 random sections: **zero hits.**
- ⛔ **But the replacement had no basis either.** **ACI 318-25M §22.5.6.1 (printed 445) is
  *"Vc for prestressed members"*** — the clause number in the audit is 318-14's. The provision
  the code implements is **W&M Eq. (6-13a), printed 281**, labelled *"Axial compression
  (ACI Code Section 22.5.6.1)"* in the book, and its SI form **Eq. (6-13aM), printed 282** —
  **with no upper bound at all**. The `0.42λ√f'c bw d √(1 + 0.29 Nu/Ag)` cap named in the audit
  **is not in `reference/`**; the audit's own §6 table left its printed page blank.

**Action taken:** the branch was **deleted**, leaving exactly the citable expression. No number
moved.

### B.4 Tests — 113 cases where there were none

`tests/` held three files, all `column_jacket`. There was **no test anywhere** on the four
modules, which is how a 1000× error shipped.

| File | Cases |
|---|---|
| `tests/test_beam_flexure.py` | 17 |
| `tests/test_beam_shear.py` | 18 |
| `tests/test_beam_torsion.py` | 18 |
| `tests/test_joint_shear.py` | 31 |
| `tests/test_qaqc_independent_recomputation.py` | 29 |
| **full suite** | **242 passed** |

Textbook pins: W&M **4-1M** (148), **4-4** (170–171), **6-1M** (297–300), **7-2** (358–362),
**7-3** (363–367), **19-3** (1076–1078). Plus regression pins on every fix,
**order-of-magnitude unit-sanity tests** — the class of bug P0 was — and no-silent-acceptance
tests.

⚠ **Two pins are deliberately looser than 1 %, and say so in their own docstrings:**

- **W&M 19-3 φVn at 3 %** — the γ = 20 psi vs 1.7 SI rounding above.
- **W&M 7-3 `Aℓ,min` at 2 %** — §9.6.4.3(a) prints **0.42** in SI where the inch-pound form
  W&M uses is `5√f'c Acp/fy`. ACI's SI 0.42 is **1.16 % above** the exact conversion of the 5,
  so **that example cannot be reproduced inside 1 % by a *correct* SI implementation.**

`tests/test_qaqc_independent_recomputation.py` re-derives **27 reported values along an
independent arithmetic path** written straight from the printed clause — the
`column_jacket_design._selfcheck` idiom. **27/27 pass, worst deviation +0.08 %.** A pass means
the module is internally consistent with the provision **as printed**; it is **not** a statement
about any design.

### B.5 Three citations in the audit note were wrong

Reported, not silently worked around. The audit note's §8.1 now carries them.

| Audit says | Actually |
|---|---|
| `Ao = 0.85 Aoh` (§22.7.6.1.1) at printed **465** | printed **466**. Eq. (22.7.6.1b) itself *is* on 465 |
| λ ∈ {0.75, 1.0} is **Table 18.8.4.3 footnote [1]** | **Table 15.5.2.1 footnote [1], printed 231**. 18.8.4.3's footnote [1] is *"Aj shall be calculated in accordance with 15.5.2.2"* |
| **ACI 318-25M §22.5.6.1** is the axial cap | §22.5.6.1 in 318-25M is **`Vc` for prestressed members**, printed 445. See B.3 |

---

## Part C — Still open

| # | Item | Why it is open |
|---|---|---|
| **C-1** | **NSCP 2015 Table 418.8.4.1, printed 4-118, is carried — not re-read.** | NSCP 2015 Vol. I in `reference/` is **image-only**; the folio is quoted from a prior vault note (`Concrete/05`). The value is corroborated by ACI 318M-14, but the page itself is **unverified**. |
| **C-2** | **Option B — migrate to ACI 318-19/-25.** | A decision, not a defect. It moves φ (Table 21.2.2, printed 430), `Vc` (`λs`, Table 22.5.5.1 / §22.5.5.1.3, printed 444–445) and the joint γ table (Table 18.8.4.3, printed 342, eight rows), and **changes every existing result**. |
| **C-3** | **`Aℓ,min` uses one `fy` for both `fy` and `fyt`.** | §9.6.4.3's `(fyt/fy)` ratio is silently 1.0. True before and after this pass; **not closed by it.** |
| **C-4** | **`joint_shear_check` always sums both bar groups.** | For an **exterior** joint only one beam frames in, and the caller must pass zeros. Nothing in the signature says so. |
| **C-5** | **Hollow-section torsion is not implemented.** | Table 22.7.4.1(b) and the §22.7.7.1(b) hollow limit. The docstring says so; the geometry (`Aoh`, `ph`) is still correct for a hollow section. |
| **C-6** | **Longitudinal torsion steel is returned as an area, not distributed.** | §9.7.5.1 caps its spacing at 300 mm, so a deep beam needs more than four corner bars. Not the module's job today, but the caller must know. |
| **C-7** | **`As,min`, `ρ ≤ 0.025`, §18.6.3.1/.2 are not checked.** | `calculate_beam_moment` computes capacity; it does not certify a section. Now stated in the docstring. |

---

## Part D — Calculation sheets (v0.9.0)

Three printable A4 sheets expose Parts A and B to a reader:
`beam_flexure_report`, `beam_shear_report`, `joint_shear_report` in
`calculators/beam_report.py`, behind `POST /api/beam/flexure-report`,
`POST /api/beam/shear-report` and `POST /api/joint/shear-report`.

Every provision in Part A that a sheet applies appears on that sheet as a
REFERENCES | CALCULATIONS | RESULT row carrying its clause and printed
page, so the register and the output cannot drift apart silently.

### D.1 Two verdict fields, and why

| Field | Means | On these three sheets |
|---|---|---|
| `adequate` | every check the sheet **actually computed** is satisfied | varies with the demand; `null` when no demand was supplied |
| `complete` | every check the **provision requires** was actually performed | **always `false`** — see Part C |

Collapsing these into one boolean is what lets a report say *adequate*
about a section whose `As,min` was never looked at. The printed verdict
banner shows both: the headline is `adequate`, and the caveat beneath it
names how many required checks were not performed.

### D.2 QAQC on every sheet

Each report carries a `qaqc` block that re-derives its own reported values
along a separate arithmetic path written longhand from the printed clause.
**10 checks on flexure, 11 on shear, 11 on the joint.** A 69-case sweep
across all three returns **753/753**.

The joint sheet's `Aj within the column cross-section` row asserts
R15.5.2.2 as an invariant on the reported `Aj` rather than recomputing the
same `min()` that produced it — it is the check that would have caught
F-10 from the output side.

⚠ A QAQC pass means the sheet is internally consistent with the provision
**as printed**. It is not a statement about any design, and it does not
replace the textbook pins — an implementation and a re-derivation can
agree and both be wrong about the Code.

### D.3 What the sheets are tested by

| Layer | Suite | Cases |
|---|---|---|
| calculators | `tests/test_beam_*.py`, `tests/test_joint_shear.py` | 84 |
| server QAQC | `tests/test_qaqc_independent_recomputation.py` | 29 |
| report + HTTP | `tests/test_e2e_reports.py` | 54 |
| renderer | `tests/js/calcsheet.test.js` (Jest, jsdom) | 69 |

`test_e2e_reports.py::test_renderer_reads_only_keys_the_server_sends` is a
**contract test across the page/payload boundary**. Both UI defects this
repo has shipped — `result.t_threshold` and `result.vu_joint` — were a
template reading a key its module never returned. Neither a Python test
nor a JS test can see that; only a test spanning the two can.

---

## Verification status

| # | Check | Status |
|---|---|---|
| V1 | Every printed page in Part A opened and read this pass | ✅ |
| V2 | Tables 18.8.4.3, 22.7.4.1(a), 22.7.5.1 and Fig./§15.5.2.2 read from a **rendered image**, not a text search | ✅ |
| V3 | Every fix carries a regression test at the acceptance number | ✅ |
| V4 | F-5's inertness re-proved **analytically** (bound 1.8) as well as by sweep (200 000 rows) | ✅ |
| V5 | F-1 re-swept (n = 4 000) after the fix, and the residual tail attributed to the **hand model**, not the code | ✅ |
| V6 | Before/after harness run and tabulated (B.2) | ✅ |
| V7 | **NSCP 2015 Ch. 4 folios** | ⚠ **carried, not verified** — C-1 |
| V8 | Out-of-scope modules | ⛔ **not reviewed, not touched** |

> [!warning] What a green test suite here does and does not mean
> 242 passing tests mean these modules reproduce six printed worked examples and are internally
> consistent with the provisions as printed. They do **not** certify a design. The functions
> compute capacity against a demand you supply; the omissions in Part C are real, and the
> Engineer of Record owns them.
