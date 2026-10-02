# Changelog - concretedesignpy

## Unreleased | October 2, 2026

### Fixed
- **`skills/rc-design/` -- SMF beam width check `smf_bw` used the larger of
  0.3h and 250 mm; NSCP 2015 requires the smaller.** NSCP 2015 §418.6.2.1(b)
  (printed 4-113, read visually 2026-10-02) says "at least the smaller of
  0.3h and 250 mm", as does ACI 318-19 §18.6.2.1(b) ("lesser of 0.3h and
  10 in."). The `max` came from ACI 318-25M p. 327, which prints "larger of"
  (the 2026 errata restates it) -- an edition change that is not applied,
  because NSCP 2015 governs (Option A). A 200 x 500 SMF beam (limit 150 mm)
  was reported FAIL and is now OK. `scripts/seismic.py` (check, limit text,
  docstring, note on the check), `references/nscp_clauses.md` (register row
  and a new edition-position row), and four guards in
  `tests/run_benchmarks.py` (200 x 500 OK, 100 x 500 FAIL, 250 x 1000 OK,
  240 x 1000 FAIL). No other check changed. The installed copy in
  `~/.claude/skills/rc-design/` already carries the same three files.

## Unreleased | September 28, 2026

### Added
- **`skills/apec-col-design/` -- Claude Code skill for NSCP 2015 RC columns,
  SMF joints and spread footings, with a project runner that compiles beam
  (via rc-design) + column + joint + footing results into one zip.**
  Every member is designed for the NSCP 2015 §203.3.1 combinations generated
  from its unfactored load cases (E = ρEh + Ev with ±Ev paired with ±Eh,
  Ev = 0.5CaID, optional 100/30 orthogonal per §208.7.1); footings add the
  §203.4.1 service set and the 0.6D stability rows. Columns: strain-
  compatibility P-M and P-M-M (neutral axis rotated to the demand moment
  direction; load-contour and radial D/C; Bresler as a cross-check), NSCP
  418.7 strong column / weak beam, ℓo, hx, Table 418.7.5.4 confinement,
  capacity-design Ve from Mpr over the axial range with the beam cap,
  Vc = 0 in ℓo and the §421.2.4.1 φ = 0.60 rule. Joints: 418.8 on the
  rectified joint_shear basis. Footings: the vault's `dp_foundation.py`
  (vendored unchanged) plus a no-tension pressure solver and moment transfer
  in punching. NSCP folios 2-10/2-11, 2-219, 2-221, 4-115..4-118, 4-140/141,
  4-143..4-145 were read visually. Benchmarks: W&M 7th Ex 11-1, 11-5, 11-7,
  19-2, 19-3, vault Concrete/05, NSCP combination factors, footing statics
  (`python3 skills/apec-col-design/tests/run_benchmarks.py`, 79 checks).
  The existing `calculators/column_interaction.py` / `column_biaxial.py`
  were not modified. Install by copying the folder to
  `~/.claude/skills/apec-col-design/`.

## Unreleased | September 27, 2026

### Added
- **`skills/rc-design/` -- Claude Code skill for NSCP 2015 RC beam design.**
  Standalone scripts (`flexure`, `shear`, `torsion`, `seismic`,
  `serviceability`, `combine`, `design_beam`) that design or check a beam
  at I / M / J and write one JSON: flexure with As,min and eps_t, shear,
  torsion (Al merged into As, At into Av), SMF capacity design (Mpr with
  A's, Ve on the clear span, Vc = 0 in the hinge) with 418.6 detailing,
  and deflection / crack control. Follows the Option A basis in
  `CLAUSES.md` and the rc-beam review findings (vault Software/12).
  Benchmarks: APEC rc-beam beam id 25 and W&M Ex 4-1M, 4-4, 6-1M, 7-2
  (`python3 skills/rc-design/tests/run_benchmarks.py`). Install by copying
  the folder to `~/.claude/skills/rc-design/`.

## Version 0.10.0 | August 15, 2026

Solver-workbench redesign of the web UI, and a fix for the Railway
deploy that had been crash-looping since the Jest suite landed.

### Added
- **VIKTOR-style solver layout on every calculator.** Each page is now a
  left parametrization panel (sticky, collapsible sections) and a right
  set of tabbed views (Results / Report / Calc Sheet where the page has
  one). The tab bar is built at runtime from `[data-view]` panels by the
  new `static/js/solver.js`; Plotly charts in a hidden tab are resized on
  activation, so nothing renders at zero width.
- **Run bar with live status.** An Update button (plus Ctrl/Cmd+Enter from
  anywhere), an opt-in Auto mode (debounced re-run on parameter change,
  remembered per page in localStorage), and a status chip driven by
  instrumenting `fetch` for `/api/*` POSTs: parameters changed → running →
  up to date with elapsed time, or error. Pages contribute no code to any
  of this.
- **App shell.** A dark grouped sidebar rendered on every page from a new
  single-source calculator registry (`webapp/nav.py` — the landing page,
  sidebar and breadcrumbs all read it), a breadcrumb topbar, and a
  searchable landing page. Icons are Lucide path data inlined as a Jinja
  macro (`_icons.html`), so no icon CDN and no icon-name drift.
- **Design system.** `style.css` rewritten around tokens (Inter for UI,
  JetBrains Mono for numbers) while keeping the legacy class vocabulary
  (`results-panel`, `report-*`, `form-*`, …) styled, so page-internal
  markup upgraded without logic edits. KPI strips and verdict chips are
  available to all pages.

### Fixed
- **Railway deploy: `gunicorn: command not found`.** `package.json`
  (added for the Jest suite) made Nixpacks detect the repo as a Node app,
  so `pip install -r requirements.txt` never ran. `nixpacks.toml` now pins
  `providers = ["python"]`, and the Procfile/railway.json start commands
  use `python -m gunicorn`, which survives PATH differences.
- **Per-run success toasts removed.** Run feedback lives in the status
  chip; toasts are reserved for errors.
- **Every report equation was boxed, and grew two scrollbars.** The
  border and background turned a report into a stack of cards. The
  vertical scrollbar was never needed at all: `overflow-x: auto` on its
  own leaves the other axis `visible`, which CSS computes to `auto`, so
  MathJax's 1em block margin was enough to raise a scrollbar on content
  that already fitted. Both axes are named now, the box is gone, MathJax's
  own margin goes with it (the wrapper owns the spacing), and where a
  genuinely wide equation still scrolls sideways the bar stays hidden
  until the pointer is over it.
- **The column jacketing sheet starved its calculations column.**
  REFERENCES and RESULTS were a fixed 168px each, which was free while
  the report spanned the page and crippling once it moved into the
  solver's views column: 336px of fixed track left the calculations
  143px, so nearly every equation overflowed sideways. The tracks are
  proportional now, and below the width where three columns stay readable
  the sheet collapses to one labelled column — the fallback `.cs-sheet`
  already uses on A4. It is keyed to the container, not the viewport,
  because that column is narrow on a wide screen and full width on a
  narrow one. At 1280px the calculations column goes from 143px to 479px
  and the equations that overflow drop from 14 to 2.
- **The A4 sheet was shaving the top off tall glyphs.** Pre-existing, and
  it printed that way: `.cs-eq` hid its vertical overflow while MathJax's
  box sits a hair above its line box, so roughly the top 1.5px of a
  fraction bar or a radical was clipped on the deliverable. Vertical
  padding gives that overhang somewhere to live — measured back to zero
  clipped glyphs across all 16 equations on the shear sheet.

### Changed
- The version badge moved from the old navbar to the sidebar foot; the
  e2e pin (`test_navbar_version_tracks_the_package`) follows the element
  and now also asserts the element exists.
- The calculator JavaScript is byte-identical across the redesign except
  one line in `column-interaction.html` that relabelled its now-removed
  in-form submit button (it would have thrown on null). All 296 pytest
  cases — including the column-jacket page-source pins — and the 69-case
  Jest suite pass unchanged.

## Version 0.9.0 | August 15, 2026

Printable A4 calculation sheets for beam flexure, beam shear and joint
shear, with server-side QAQC, a Jest suite on the renderer, and
end-to-end tests across the page/payload boundary.

### Fixed
- **The navbar badge read `v0.7 | NSCP 2015 / ACI 318-19`.** It was a
  literal string in `base.html`, it had gone stale, and it was wrong on
  both halves — the beam and joint modules are NSCP 2015 (= ACI 318M-14),
  not 318-19. The version is now injected from `concretedesignpy.__version__`
  by a context processor, so it cannot drift again, and the edition label
  lives in exactly one place. The long form, on hover, says the edition is
  per module.
- **The flexure report shipped the solver's entire iteration log.** Several
  hundred neutral-axis trial rows, roughly 40 kB per response, none of it
  used by the sheet, and carrying the string `"Infinity"` in the ratio
  column of every pre-convergence row. Dropped from the report; the
  calculator endpoint that wants it still returns it.
- **`calcsheet.js` left an orphaned `</span>` behind a rejected tag.**
  `<span class="evil">x</span>` rendered as `x</span>`. No attribute ever
  survived so it was never an injection, but stray markup on a printed
  sheet is a defect in its own right. Close tags are now balanced against
  open tags.
- **The sheet's two 40 mm side columns did not shrink.** Below roughly
  760 px the calculations column collapsed to nothing. It now stacks to a
  single labelled column on narrow screens; print is unaffected, being
  always 182 mm.
- **Wide tables pushed the page sideways.** Each data table now scrolls
  inside its own block.

### Added
- **`calculators/beam_report.py`** — three calculation sheets in the
  `column_jacket_design` idiom: `beam_flexure_report`,
  `beam_shear_report`, `joint_shear_report`. Each returns `provenance`,
  `request_echo`, REFERENCES | CALCULATIONS | RESULT `sections`,
  `summary`, `qaqc`, `advisories`, `governing_checks`, `unavailable`,
  `adequate` and `complete`.

  Four properties are load-bearing:

  1. **QAQC is computed on the server.** Every report re-derives its own
     reported values along a separate arithmetic path written longhand
     from the printed clause. The client renders a table and holds no
     equation. 10 checks on flexure, 11 on shear, 11 on the joint; 753/753
     across a 69-case sweep.
  2. **Advisories are part of the answer**, not a footnote. Nothing
     truncates, filters or hides one.
  3. **A check with no model is recorded, not faked.** `As,min`, joint
     transverse reinforcement and the rest land in `unavailable`.
  4. **A demand is optional; a verdict is not invented without one.**
     `mu_demand` omitted gives `adequate: null` and a neutral banner
     rather than a D/C of zero.

  `adequate` and `complete` are **two fields on purpose**. `adequate`
  means every check the sheet actually computed is satisfied; `complete`
  means every check the provision requires was actually performed, and is
  false while anything sits in `unavailable`. Collapsing them into one
  boolean is what lets a report say "adequate" about a section whose
  `As,min` was never looked at.

- **Three endpoints**: `POST /api/beam/flexure-report`,
  `POST /api/beam/shear-report`, `POST /api/joint/shear-report`. The joint
  route does not read `phi` from the payload — Section 21.2.4.4 fixes it
  at 0.85.
- **`static/css/calcsheet.css`** — one stylesheet, three calculators. Real
  `@page { size: A4 portrait; margin: 14mm 14mm 16mm }`, and the on-screen
  sheet is clamped to **182 mm**, which is A4 less those margins, so the
  screen view and the printed view are the same document rather than two
  layouts. Break control keeps headings with their sections, repeats table
  headers across a fold, and `print-color-adjust: exact` stops Chrome
  printing the PASS chips white.
- **`static/js/calcsheet.js`** — UMD renderer, browser and Jest. It holds
  no engineering: it compares nothing and derives nothing, because a
  renderer that recomputes is a second implementation and this repository
  has already shipped one of those by accident.
- **`tests/js/calcsheet.test.js`** — 69 Jest cases, 98% statements, 94%
  branches, 100% functions. What they assert is what makes a printed sheet
  trustworthy: nothing the server sends is silently dropped, a null is
  never rendered as a zero, the three verdict states stay three, and
  untrusted text cannot inject markup.
- **`tests/test_e2e_reports.py`** — 54 end-to-end cases through a real
  Flask app over real JSON. Including **a contract test between the page
  and the payload**: every top-level key the renderer reads must exist in
  every report the server sends. That is the test that would have caught
  `result.t_threshold` and `result.vu_joint` — two shipped UI defects that
  no Python test and no Jest test could see, because each lived on the
  other side of the boundary.
- `npm test` runs the front-end suite; `pytest` runs 296 Python tests.

### Known gaps
The sheets report; they do not certify. Every one of them carries a
non-empty `unavailable` list, so `complete` is false on all three by
construction: flexure does not check `As,min`, `rho <= 0.025` or the SMF
relations; shear does not cover torsion, deep beams or shear friction;
the joint does not check transverse reinforcement, bar development or the
column-to-beam strength ratio. The joint sheet also **always sums both bar
groups**, so an exterior joint needs the caller to pass zeros — it is the
first advisory on every joint sheet, and nothing in the inputs can detect
it. Full list in `CLAUSES.md` Part C.

## Version 0.8.0 | August 15, 2026

Rectification of `Software/14 - concretedesignpy Review — Beam Flexure, Shear,
Torsion & Joint Shear`. All nine items closed. Clause register in
[`CLAUSES.md`](CLAUSES.md).

### Governing edition — decided, and recorded

**These modules target NSCP 2015 (= ACI 318M-14), the governing Philippine
code.** Every docstring previously claimed ACI 318-19 and none implemented it.
Because Option A was adopted, the pre-2019 φ law, the ACI 318-14 `Vc` with no
size-effect `λs`, and the three-row joint γ table are all **correct as written
and were left alone** — only the labels and the genuine defects were touched.
Migrating to ACI 318-19/-25 is an edition change that moves φ, `Vc` and the
joint table together and changes every existing result; it is recorded as open,
not done.

The edition is **per module**. `column_jacket*` and the other out-of-scope
modules legitimately do target ACI 318-19 and were not reviewed or touched.

### Removed
- **`calculators/beam_torsion.py` is deleted.** It computed `φTth` in N·m and
  compared it against a `Tu` the web form supplied in kN·m, so it returned
  `"MAY NEGLECT"` and `"status": "PASS"` for a beam 4.8× over the threshold.
  `At/s` was 1000× low by the same error, and the §22.7.7.1 crushing terms were
  mis-scaled by two further, different factors (shear ~100× low, torsion ~10⁵×
  low) so `combined_stress` could never reach the limit. The five scale factors
  were individually plausible, which is how they survived; the root cause was
  two implementations of §22.7 in one package, so the duplicate was deleted
  rather than patched. `POST /api/beam/torsion` now calls
  `beam_shear.shear_torsion_design()`.
- **The unsupported `Vc` axial cap `0.3√f'c bw d (1 + 0.3 Nu/Ag)`** is removed
  from `shear_torsion_design()` and `shear_design()`. Nothing in the reference
  folder supports it, ACI 318-25M §22.5.6.1 is about prestressed members, and
  W&M Eq. (6-13a)/(6-13aM) — the provision actually implemented — carries no
  upper bound. It was also provably inert: the ratio of the two branches is
  `1.8(1 + 0.3q)/(1 + q/14)` with `q = Nu/Ag ≥ 0`, minimum 1.8 at `Nu = 0` and
  rising, so `min()` never selected it. **No number changed.**

### Fixed
- **`Aℓ` was 15.00 % short on every section, unconservatively.** The divisor is
  `1.7 Aoh`, not `2 Aoh`: Eq. (22.7.6.1b) is `Tn = (2 Ao Aℓ fy / ph) tan θ` and
  §22.7.6.1.1 permits `Ao = 0.85 Aoh`. W&M Ex 7-2: **694 → 816.2 mm²** against
  the book's 816.
- **The effective joint width had no column cap.** `joint_shear_check` now
  takes a **required, keyword-only** `column_width` and computes
  `bj = min(column_width, b + h, b + 2x)`. A 500 mm spandrel on a 400 × 600
  column: **Aj 300 000 → 240 000 mm²**, φVn −20 %. A 700 mm beam was +75 %.
  Omitting the argument raises `TypeError` rather than silently reproducing the
  old answer.
- **`compute_shear_spacing()` skipped `Av,min` whenever `Vu > φVc`** and had no
  `Vs ≤ ⅔√f'c bw d` test at all — two guards its two sibling functions both
  have. `Av,min` now enters the `min()` on both branches, and an over-stressed
  section returns **`spacing = None`** with an explicit `UNSAFE` status naming
  both numbers. A section the Code forbids must not come back carrying a
  spacing that looks usable.
- **The `Nu` term of the torsion thresholds was omitted entirely.** `Nu` was an
  argument of `shear_torsion_design()` and was never used for torsion. Tables
  22.7.4.1(a) and 22.7.5.1 row (c) multiply by
  `√(1 + Nu/(0.33 Ag λ√f'c))`, `Nu` positive for compression. Omitting it is
  conservative under compression and **unconservative under net tension**. The
  radicand is clamped at zero, so heavy tension drives the thresholds to zero
  and torsion is always designed for.
- **Three coefficients were rounded away from the printed value, all in the
  direction of neglect:** `Tth` used `1/12` against the printed **0.083**
  (+0.4 %), `Tcr` used `1/3` against **0.33** (+1.0 %), and `Aℓ,min` used
  `5/12` against **0.42** (§9.6.4.3(a)). All three now carry the printed value.
  W&M Ex 7-2 `φTth` lands at **7.958** against the book's 7.959.
- **Compression bars did not displace the concrete the Whitney block already
  counted.** `Cs = A's(f's − 0.85 f'c)` per W&M Ex 4-4 step 5, applied **only to
  bars inside depth `a`** — a bar in compression but below `a` sits in cracked
  concrete and displaces nothing. **This is cosmetic on `Mn` and is reported as
  such:** over 4 000 sections `Mn` was overstated by a median +0.05 %, max
  +1.05 %, because a smaller `c` gave back what the overstated `Cs` took. What
  was actually wrong was `c` — W&M Ex 4-4 goes from 5.99 in. (−3.35 %) to
  **6.184 in.** (−0.26 %) against the book's 6.2.
- **Two `Av,min` constants existed in one package** — 0.062 (ACI 318M) in
  `compute_shear_spacing()` and `1/16 = 0.0625` (W&M Eq. 6-20M's rounding) in
  the two design functions. Now one constant, **0.062**, per Table 9.6.3.4.
- **An unrecognised `joint_config` silently scored 1.0** via
  `dict.get(cfg, 1.0)`. It now raises.
- **`shear_status` was computed and discarded**, `overall_check` being returned
  under that key, so `"UNSAFE - Vs exceeds limit"` could never reach a caller.
  Returned as `vs_status`. **No verdict changes** — `vs_req_raw > vs_max` and
  `vu > vu_max` are the same inequality, so the "lost" string always agreed
  with the one that was returned. A dead local, not a recovered check.
- **Dead template keys in two calculators.** `beam-torsion.html` read
  `result.t_threshold` and `result.torsion_status`, and `joint-shear.html` read
  `result.vu_joint` and `result.vn_joint`. None of the four is a key its module
  returns, so those lines had never rendered.

### Changed
- `λ` for joint shear is constrained to **0.75 or 1.0**; anything else raises.
- **`φ` for special-moment-frame joint shear is fixed at 0.85** and is no longer
  read from the request payload. §21.2.4.4 gives no caller discretion. The form
  field is disabled and annotated.
- The joint γ map is now the module-level constant
  `NSCP_2015_TABLE_418_8_4_1`, documented as a three-row table, with the ACI
  318-25M Table 18.8.4.3 eight-row successor recorded beside it.
- Every in-scope docstring now states its governing edition **and what the
  function does not check** — `As,min`, `ρ ≤ 0.025`, §18.6.3.1/.2 for flexure;
  deep beams, shear friction, torsional redistribution and hollow sections for
  shear/torsion; joint transverse reinforcement, bar development and the
  strength ratio for joints.
- `calculators/__init__` now exports `shear_design` and `shear_torsion_design`.

### Added
- **`CLAUSES.md`** — clause register, rectification record, before/after table,
  and what is still open.
- **113 tests across five files**, on four modules that had **none**:
  `test_beam_flexure.py`, `test_beam_shear.py`, `test_beam_torsion.py`,
  `test_joint_shear.py`, and `test_qaqc_independent_recomputation.py`. Full
  suite **242 passed**. Each file carries textbook pins with the printed page in
  the docstring, regression pins at each fix's acceptance number,
  **order-of-magnitude unit-sanity tests** — the class of bug the deleted module
  was — and no-silent-acceptance tests.
- The QAQC file re-derives **27 reported values along an independent arithmetic
  path** written straight from the printed clause, in the same idiom as
  `column_jacket_design._selfcheck`. Run it standalone for a tabular sheet:

      python tests/test_qaqc_independent_recomputation.py

  27/27 pass, worst deviation +0.08 %.

### Known gaps
Two test pins are deliberately looser than 1 %, and say so in their own
docstrings. **W&M Ex 19-3 φVn at 3 %:** the book works in psi with γ = 20 while
NSCP 2015 and ACI 318M print 1.7, and 20/12 = 1.667. **W&M Ex 7-3 `Aℓ,min` at
2 %:** ACI's SI 0.42 is 1.16 % above the exact conversion of the inch-pound
`5√f'c Acp/fy`, so that example cannot be reproduced inside 1 % by a *correct*
SI implementation. A ~2 % gap against this textbook is not automatically a bug.

**NSCP 2015 Table 418.8.4.1 is carried, not re-read** — the reference copy is
image-only. `Aℓ,min` still uses one `fy` for both `fy` and `fyt`, so
§9.6.4.3's `(fyt/fy)` ratio is silently 1.0. `joint_shear_check` always sums
both bar groups, so an exterior joint needs the caller to pass zeros. Hollow-
section torsion is not implemented. Full list in `CLAUSES.md` Part C.

## Version 0.7.4 | August 15, 2026

### Changed
- **Provenance deleted from the client submission** (user direction,
  2026-08-15). It is retained in full in the Internal Review, where the engine
  version and SHA-256 are what make a number auditable a year later. The
  client report now ends at the Results Summary.
- **Internal note identifiers are stripped from the calculation sheet.** Two
  reached the client report: one hard-coded here, and one arriving from the
  server inside `monolithic.clause`, which ends `"; TN-RET-001 Core Technical
  Requirements 4"`. A static scan of the template could not have caught the
  second, so `step()` now runs both its reference and its description through
  `pubRef()`, which drops any sentence or clause naming an internal note and
  keeps the published citation.

### Fixed
- `pubRef()` filtered sentences before clauses, so a citation carrying no full
  stop matched as a whole and its published half was discarded with the
  internal one — the Lampropoulos reference collapsed to the generic fallback.
  Filtering now runs innermost-first.

### Known gaps in the client submission
Removing the provenance block also removed the document-level code-basis
statement, which an independent review considered one of the two genuinely
client-appropriate lines in it. The submitted report currently has no title
block, no issue date, no revision identifier, no responsibility block (named
Engineer of Record, licence, signature), no page numbering, no scope-of-
reliance statement, and no statement of where the existing-column input data
came from. Individual checks still cite their ACI/ASCE clauses in the
REFERENCES column. These are documentary gaps, not computational ones, and
are recorded here rather than fixed because a title block needs project
inputs that this calculator does not yet collect.

---

## Version 0.7.3 | August 15, 2026

### Changed
- **The client report now carries no advisory content at all** — not the text,
  not the codes, not the count (user direction, 2026-08-15, given after
  reviewing the v0.7.2 disclosure block on screen). The report runs Input
  Summary → Calculation Sheet → Detailing → QAQC → Results Summary →
  Provenance, and the word "advisory" does not appear in it.
- The disclosure summary (count, critical count, full code list, and the note
  that the exclusion was directed) moves to the head of the **Internal Review**
  panel, so the Engineer of Record still sees in one line what the calculation
  raised. It is still built from the response, never hand-written.
- The client verdict no longer references advisories, which would have been a
  reference to something the document does not contain. It is now a pure scope
  statement: the report covers the computed code checks only, is not a
  statement that the retrofit is safe or complete, and is subject to the
  review and judgement of the Engineer of Record. The verdict must not
  overclaim even when the caveats are filed elsewhere.

### Decision record
- v0.7.2 omitted the advisory text but disclosed the codes; v0.7.3 removes the
  disclosure too. The concern — that an omission which leaves no trace on the
  signed sheet is indistinguishable from an answer that never had the finding
  — was raised and the direction was reaffirmed. That is the Engineer of
  Record's call to make; this entry is the record of it.

---

## Version 0.7.2 | August 15, 2026

### Changed
- **Advisories separated from the client report** (user direction, 2026-08-15;
  the report is submitted to a client). The report no longer reproduces the
  advisory text. It carries a **disclosure block** instead — the count, the
  critical count, and every advisory code with its severity, built from the
  response and never hand-written — stating that the omission was directed.
  Both halves are pinned by tests: reverting the omission needs a new
  decision, and losing the disclosure would turn a directed omission into a
  silent one, which is indistinguishable from an answer that never had the
  finding.
- Advisories now render in a separate **Internal Review** panel, marked as
  excluded from the client submission and deliberately placed outside the
  report container so no selector can sweep it into the client print.
- **Two print modes** — *Print Client Report* (default) and *Print Internal
  Review*, keyed off a `body.print-internal` class. The internal handler
  clears the class in a `finally`, so a cancelled dialog cannot leave the page
  armed to print advisories into the next client report.
- The verdict's closing sentence is now doubled: on screen it points at the
  Internal Review panel; on the client copy it states that advisories are
  issued separately. A verdict that pointed at advisories the document does
  not contain would be a dangling reference on the sheet that gets signed.

---

## Version 0.7.1 | August 15, 2026

### Added
- **Calculation-sheet report for Column Jacketing** — the page report now
  follows the APEC three-column REFERENCES | CALCULATIONS | RESULTS format:
  a 31-row Input Summary (Symbol | Input | Description | Value, every field
  echoed so the report is self-contained), eight numbered calculation
  sections with symbolic and substituted equations, a Results Summary table,
  and the detailing/advisories/provenance blocks
- **Server-side QAQC block** — `column_jacket_design()` results now carry a
  `qaqc` section: 16 independent recomputations (9 for a partial jacket)
  that re-derive reported values from the raw inputs along separate
  arithmetic paths — geometry, bar counts and areas, Po and phi*Pn,max
  longhand, phi*Mn at Pu by re-interpolating the returned curve, the full
  shear stack, v_u summation, and Mander f'cc from the reported f_l. The
  page renders the table; it compares nothing itself. A deliberate-corruption
  test proves the block can actually fail
- **Professional figures** — the section drawing gains true dimension lines
  with witness ticks (B, H), a leader for t, centrelines and a labelled core;
  the P-M chart gains the demand annotation and drops the raw nominal
  envelope, which reached Po and pure tension and crushed the design curves
  into a corner of the axes

### Improved
- QAQC comparisons coerce numpy booleans so results stay JSON-serialisable

---

## Version 0.7.0 | August 15, 2026

### Added
- **RC Column Concrete Jacketing** — new modules `calculators/column_jacket.py`
  (engine) and `calculators/column_jacket_design.py` (design boundary), per
  TN-RET-001, ACI 318-19, ACI 562-16 and ASCE 41-17:
  - P-M interaction of the composite section using a **single** ACI stress
    block with β₁ from the extreme compression fibre. Giving each concrete its
    own β₁c is physically inverted and unconservative; it remains available as
    `stress_block='per_material'` for comparison only
  - Mander confinement with **k_e computed from the actual tie and bar
    geometry**, not assumed. A plain perimeter hoop gives k_e ≈ 0.40, not the
    0.80 assumed by habit, which overstates f'cc by roughly 12%
  - One-way shear with `d` taken from the **actual extreme tension bar**, so
    the shear check and the interaction diagram agree about where the steel is
  - Interface shear transfer reporting **both** ACI capacity routes (shear
    friction and the Table 16.4.4.2 bond route) and picking neither
  - Unshored-jacket preload split, stiffness feedback, detailing checks, axial
    strength, and induced-eccentricity geometry
  - Lampropoulos et al. (2012) monolithic coefficients **reported and never
    applied**, with both the corrected and uncorrected results side by side
  - Partial (one/two-opposite/three-sided) jackets compute geometry, axial
    strength and P-M interaction, and declare the checks that have no model
    instead of answering with four-sided behaviour. Two *adjacent* faces are
    refused outright — that section's capacity is a biaxial surface
  - Every result carries `provenance` (including a SHA-256 of the engine
    source) and an `advisories` list of traps the arithmetic cannot rule out
- **Column Jacketing calculator page** — `/calculator/column-jacket`, backed by
  `POST /api/column-jacket/design`. All 35 inputs, P-M interaction chart
  (existing vs jacketed with the demand point), a dimensioned section figure
  drawn from the engine's own bar coordinates, a MathJax calculation report,
  detailing table, and the full advisories panel. Ported from the APEC
  jacketing service's browser calculator, keeping its two load-bearing
  properties: the page holds no equations or engine constants — every number
  and both figures come from the server — and advisories render in full,
  never filtered, capped or truncated (the hover reveal only unpaints the
  remainder, and print reveals everything)
- **Test suite** — first `tests/` directory in the repo, 109 tests covering the
  jacketing engine, its design boundary, and the web layer. Independent
  recomputations are separated from labelled regression pins

### Changed
- `setup.py` version synced to `__init__.__version__` (it had been left at
  0.5.0 while the package reported 0.6.0)
- Navbar version badge was hardcoded `v0.3`; now `v0.7`
- README: retrofitting/strengthening features, library usage, testing section,
  and the ACI 562-16 / fib B14 / Lampropoulos references

---

## Version 0.4.0 | April 5, 2026

### Added
- **Advanced Moment-Curvature Analysis** — Hognestad parabolic concrete model with fiber-layer approach, axial load support, 60-point smooth curve
- **4-Panel Section Analysis** — Strain/stress charts with full section visualization
- **Strength Reduction Factor Plot** — Phi plot matching ACI 318-19 Table 21.2.2 with projected design values
- **Confinement Effectiveness Charts** — 19-ratio curves with projections, Fig. 5 style (Mander et al.)
- **Biaxial Confinement** — Full biaxial formulas in Mander report
- **Rebar Input Improvement** — Bar diameter and quantity inputs replace direct As entry, auto-compute area
- **Complete Mander Report** — 13-step transparent report with all intermediate calculations, paper references
- **Excel Export** — Stirrup spacing design with Excel export (beam shear)
- **Print Report** — Print-ready output with engineering notation

### Improved
- Moment-curvature page rewritten with Plotly charts, section visualization, QAQC report
- Mander report enhanced with paper references, placeholders, biaxial formulas, summary
- Confinement chart: inverted y-axis, fixed title/label overlap, 19 ratio curves
- Beam shear page rewritten with MathJax report, Plotly charts, clean layout
- RC section diagram: proper stirrup legs, force arrows, Vc vs Nu/Ag chart
- Split layout (inputs left, output right) for better UX
- Combined shear & torsion design with ACI 318M-14 references

### Fixed
- Phi plot: fixed x-axis range matching reference design
- Confinement chart: inverted y-axis, fixed title/label overlap
- RC section: top bars at all legs, black fill, proper rendering
- Vc vs Nu/Ag chart matching ACI 318M-14 Fig. R22.5.6.1 exactly
- d/c dimensions, Tu curved arrow, Tu input fixes

### Changed
- Replaced FLECHA attribution with Hognestad (1951) paper reference
- Updated README: removed Railway deploy section, improved documentation

---

## Version 0.3 | 2025

### Added
- Column P-M interaction diagram with Plotly
- Joint shear verification for special moment frames
- Development length hook geometry
- Alternative inertia calculator
- Mander confined concrete model
- Moment-curvature 6-point analysis
- Flask web application with Plotly charts and MathJax reports
- Railway/Heroku deployment support

---

## Version 0.2 | 2025

### Added
- Beam shear and torsion calculators
- Beam deflection calculator
- Column flexural strength ratio
- Web interface with route-based API

---

## Version 0.1.1 | March 3, 2025

### Added
- **RC Beam Solver** — Computation of Beam Capacity based on NSCP 2015 with validation checks
- **Midas RC Pushover MGT Generator** — Initial development (partial implementation)
