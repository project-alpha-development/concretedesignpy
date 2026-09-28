# NSCP 2015 clause map for apec-col-design — with vault links

**Governing code:** NSCP 2015 Vol. I (Ch. 4 = ACI 318M-14 in Philippine numbering; Ch. 2 loads).
**Readable stand-in:** `ACI 318-25M` in `vault/reference/`, **printed = PDF − 1** (text layer).
**NSCP 2015 is image-only** (`reference/_Scanned/…`). ✅ = folio **rendered and read visually on
2026-09-28** for this skill (renders at 110–300 dpi). Other NSCP folios come from the vault notes
named below and must be read before being quoted as verified.
NSCP Ch. 4 offsets drift (PDF − 325 / − 324 island at PDF 432–447); Ch. 2 front half PDF − 55,
§208 band PDF − 52 — read the folio off the page.

Vault root: `~/Desktop/Programs/structural-mind/Structural Mind/vault/`

| Vault note / source | What it gives this skill |
|---|---|
| `Internal Learning/04 - Week 4 — Column Detailing & Standards` | column clause map with NSCP twin folios (410.6/410.7, 425.7, 406.2.5, 418.7) |
| `Concrete/05 - Beam-Column Joint Check (SMRF)` | joint procedure (1.25 fy, Vcol, Vj, γ, Aj) — ⚠ see *Findings* |
| `OpenSees/column_models/pmm.py` + README | biaxial penalty grows with axial load; NA ≠ moment direction |
| `Design Procedures (MIDAS + Python)/01–05` + `dp_foundation.py` | footing route map, ASD/strength split, bearing, stability, shear, flexure (vendored) |
| `concretedesignpy/CLAUSES.md` (Option A) | NSCP 2015 governs; ACI 318-19+ changes are edition changes, not fixes |
| `Manuals/Wight MacGregor … 7th.pdf` (printed = PDF − 1) | Ex 11-1, 11-5, 11-7, 19-2, 19-3 benchmarks; Eqs. 11-17/18, 11-31, 15-5 |
| `Seismic Design of RC Buildings — Moehle` | column Ve and the beam-moment split (printed 564–568) |
| `NIST GCR 8-917-1` (printed = PDF − 4) | SMF column/joint procedure, balanced-point and 3-leg guidance (printed 13–17) |

## Load combinations (combos.py)

| Item | NSCP 2015 | Folio | Status |
|---|---|---|---|
| Strength 203-1 … 203-7, f1 = 0.5 / 1.0 | §203.3.1 | 2-11 | ✅ |
| Ponding 1.2P | §203.3.2 | 2-11 | ✅ (not generated — add as a case if needed) |
| ASD basic 203-8 … 203-12, no increase | §203.4.1 | 2-11 | ✅ — 203-11 prints `0.75[L + T(Lr or R)]`, read as the sum |
| ASD alternate 203-13 … 203-18, ⅓ increase with W or E | §203.4.2 | 2-11 | ✅ — 203-13 prints the same dropped `+` |
| Special seismic 203-19/20 with Em = Ω0 Eh | §203.5; Eq. 208-19 | 2-11; 2-219 | ✅ |
| E = ρEh + Ev; Ev = +0.5 Ca I D (strength), 0 (ASD); ρ 1.0–1.5, ≤ 1.25 SMF | §208.6.1, Eqs. 208-18/-20 | 2-219 | ✅ |
| Non-concurrent principal directions, except 208.7.2 | §208.6.1 (last para.) | 2-219 | ✅ |
| Orthogonal effects 100 % + 30 % (or SRSS); 20 %-of-capacity exception | §208.7.1 | 2-221 | ✅ |
| Symbols D E F H L Lr P R T W | §203.2 | 2-10 | ✅ |

## Axial–flexural strength (section.py, pm.py)

| Check | ACI 318-25M | Printed p. | NSCP 2015 | Folio |
|---|---|---|---|---|
| strain compatibility, εcu = 0.003, no concrete tension | §22.2.1–22.2.2.2 | 437–438 | §422.2; §422.4.1.1 | 4-143 ✅ (422.4.1.1) |
| β1 | Table 22.2.2.4.3 | 438–439 | Table 422.2.2.4.3 | — |
| steel elasto-plastic, Es 200 000 | §20.2.2.1–.2 | 411 | §420.2.2 | — |
| Po = 0.85f′c(Ag − Ast) + fyAst | Eq. (22.4.2.2) (+ fy ≤ 550) | 441 | Eq. (422.4.2.2) (no fy cap printed) | 4-143 ✅ |
| Pn,max = 0.80 Po ties / 0.85 Po spirals | Table 22.4.2.1 | 440 | Table 422.4.2.1 | 4-143 ✅ |
| Pnt,max = fy Ast | §22.4.3.1 | — | §422.4.3.1 | 4-144 ✅ |
| φ by εt: 0.65/0.75 → 0.90, tension-controlled at 0.005 | Table 21.2.2 (318-19+: εty + 0.003) | 432 | Table 421.2.2 | 4-140 ✅ |
| εty = fy/Es | §21.2.2.1 | 433 | §421.2.2.1 (prints “Grade 280 … 0.002”) | 4-140 ✅ |
| φ cap 0.1f′cAg ≤ Pn ≤ Pn,bal (318-25 only) | §21.2.2.3 | 433 | — (not in NSCP) | — |
| biaxial: NA rotates ≠ moment vector | W&M §11-7, Ex 11-5 | 567–572 | — | — |
| circular segment A, A·ȳ | W&M Eqs. (11-17), (11-18) | 539 | — | — |
| Bresler reciprocal load (information) | W&M Eq. (11-31) | 568 | — | — |
| ρ 0.01–0.08 (non-SMF) | §10.6.1.1 | 171 | §410.6.1.1 | 4-71 (vault IL/04) |
| min bars 3 / 4 / 6 | §10.7.3.1 | 172 | §410.7.3.1 | 4-71 (vault IL/04) |
| column bar clear spacing ≥ 40 mm, 1.5db, 4/3 dagg | §25.2.3 | 510 | §425.2.3 | — |
| slenderness k ℓu/r ≤ 22 (sway), r = 0.3h / 0.25D | §6.2.5.1–.2 | 76–78 | §406.2.5 | 4-36 (vault IL/04) |

## Special moment frame columns (smf.py) — NSCP §418.7 read in full

| Check | ACI 318-25M | Printed p. | NSCP 2015 | Folio |
|---|---|---|---|---|
| least dimension ≥ 300; ratio ≥ 0.4 | §18.7.2.1 | 334 | §418.7.2.1 | 4-115 ✅ |
| ΣMnc ≥ (6/5)ΣMnb, lowest Mnc for the E axial force, both sways, slab steel in Mnb | Eq. (18.7.3.2) | 335 | Eq. (418.7.3.2) | 4-115 ✅ |
| roof exemption Pu < Agf′c/10 | §18.7.3.1 (318-19+) | 335 | **absent** in §418.7.3.1 | 4-115 ✅ |
| 418.7.3.3 alternative (column ignored, → 418.14) | §18.7.3.3 | 335 | §418.7.3.3 | 4-115 ✅ |
| 0.01 ≤ ρ ≤ 0.06 | §18.7.4.1 | 336 | §418.7.4.1 | 4-115 ✅ |
| ≥ 6 bars with circular hoops | §18.7.4.2 | 336 | §418.7.4.2 | 4-115 ✅ |
| lap splices centre half, tension, confined | §18.7.4.4 | 336 | §418.7.4.3 | 4-115 ✅ |
| bond-splitting 1.25ℓd ≤ ℓu/2 or Ktr ≥ 1.2db | §18.7.4.3 (318-19+) | 336 | **absent** | 4-115 ✅ |
| ℓo ≥ max(depth, ℓu/6, 450) | §18.7.5.1 | 336 | §418.7.5.1 | 4-116 ✅ |
| hoops (a)–(d); hx ≤ 350; (f) every bar + hx ≤ 200 when Pu > 0.3Agf′c or f′c > 70 | §18.7.5.2 | 337 | §418.7.5.2 | 4-116 ✅ |
| s ≤ min(dmin/4, 6db, so); so = 100 + (350 − hx)/3 ∈ [100, 150] | §18.7.5.3 (+5db Gr 550) | 338 | §418.7.5.3 (6db only) | 4-116 ✅ |
| Ash/(s bc) (a)(b)(c), ρs (d)(e)(f); kf, kn | Table 18.7.5.4, Eq. 18.7.5.4a/b | 338 | Table 418.7.5.4, Eq. 418.7.5.4a/b | 4-116/117 ✅ |
| ⅓ label fix `Ash/(s bc)` | ACI 318-25(SI) Errata 14 May 2026 | — | — | (vault reference/README) |
| beyond ℓo: s ≤ min(6db, 150) | §18.7.5.5 | 339 | §418.7.5.5 | 4-116 ✅ |
| discontinued stiff members; cover > 100 mm | §18.7.5.6–.7 | 339 | §418.7.5.6–.7 | 4-116/117 ✅ |
| Ve from Mpr over the Pu range; ≤ beam-Mpr joint shear; ≥ analysis | §18.7.6.1.1 | 339 | §418.7.6.1.1 | 4-117 ✅ |
| Vc = 0 in ℓo (EQ shear ≥ ½ and Pu < Agf′c/20) | §18.7.6.2.1 | 340 | §418.7.6.2.1 | 4-117 ✅ |
| φ shear 0.75; 0.60 if Vn < V at Mn (members resisting E in SMF) | Table 21.2.1(b); §21.2.4.1 | 430; 435 | Table 421.2.1(b); §421.2.4.1 | 4-140/141 ✅ |
| bottom/top tie ≤ s/2 from slab; ≤ 75 mm below beam bars | §10.7.6.2.1–.2 | 176 | §410.7.6.2 | — |

## Column shear (shear.py)

| Check | ACI 318-25M | Printed p. | NSCP 2015 | Folio |
|---|---|---|---|---|
| Vn = Vc + Vs | §22.5.1.1 | — | §422.5.1.1 | 4-144 ✅ |
| section limit | Eq. (22.5.1.2) **0.66** | 442 | Eq. (422.5.1.2) prints **0.67** | 4-144 ✅ |
| Vc = 0.17λ√f′c bw d | — (318-19+ Table 22.5.5.1 differs) | — | Eq. (422.5.5.1) | 4-145 ✅ |
| Vc with compression 0.17(1 + Nu/14Ag) | — | — | Eq. (422.5.6.1) | 4-145 ✅ |
| Vc with tension 0.17(1 + Nu/3.5Ag) ≥ 0 | — | — | Eq. (422.5.7.1) | 4-145 ✅ |
| circular d = 0.8D, bw = D | §22.5.2.1(b),(c) (+(a) 0.8h rect.) | 443 | §422.5.2.2 | 4-144 ✅ |
| √f′c ≤ 8.3; fyt ≤ 420 in Vs | §22.5.3.1, §22.5.3.3 | 443 | §422.5.3.1, .3.3 | 4-144 ✅ |
| Av,min where Vu > 0.5φVc | §10.6.2.1–.2 | 172 | §410.6.2 | — |
| s max d/2 ≤ 600 (d/4 ≤ 300) | Table 10.7.6.5.2 | 177 | Table 410.7.6.5.2 | — |
| biaxial shear interaction (318-19+ only → WARN) | §22.5.1.10–.11 | 442–443 | — | — |

## Joints (joint.py) — NSCP §418.8 read at 4-117/4-118

| Check | ACI 318-25M | Printed p. | NSCP 2015 | Folio |
|---|---|---|---|---|
| bar forces 1.25 fy | §18.8.2.1 | 340 | §418.8.2.1 | 4-117 ✅ |
| column dimension ≥ 20db (26db LW) | §18.8.2.3 | 340–341 | §418.8.2.3 | 4-118 ✅ |
| joint depth ≥ ½ beam depth | §18.8.2.3(c) | 341 | §418.8.2.4 | 4-118 ✅ |
| joint hoops = column ℓo hoops; half + s ≤ 150 with four beams ≥ ¾ column width | §18.8.3.1–.2 | 341 | §418.8.3.1–.2 | 4-118 ✅ |
| Vn = 1.7 / 1.2 / 1.0 λ√f′c Aj | Table 18.8.4.3 (8 rows — edition change) | 342 | Table 418.8.4.1 (3 rows) | 4-118 ✅ |
| face confined if beam ≥ ¾ effective joint width | — | — | §418.8.4.2 | 4-118 ✅ |
| Aj = h × bj; bj ≤ b + h, b + 2x, never > column | §18.8.4.3; R15.5.2.2 | 342; 231–232 | §418.8.4.3 | 4-118 ✅ |
| φ = 0.85 | §21.2.4.4 | 435 | §421.2.4.3 | 4-141 ✅ |
| ℓdh = fy db/(5.4λ√f′c) ≥ 8db, 150 | §18.8.5.1 | 342 | §418.8.5.1 | 4-118 ✅ |
| Vcol from ΣMpr between column mid-heights | — | — | NIST GCR 8-917-1 §5.2 Figs 5-4/5-5 | printed 13–14 |

## Footings (footing.py → vendor/dp_foundation.py)

The clause register lives in the vendored engine's docstrings and in vault Design Procedures 01–05.
Added here: NSCP §203.3.1 / §203.4 combinations (2-11 ✅), §422.5.5.1 one-way Vc (4-145 ✅), and moment
transfer in punching by eccentric shear — ACI 318-25M §8.4.2.2.2, §8.4.4.2.2–.3, R8.4.4.2.3,
printed 116–119 (NSCP §408.4.4.2 not read). The no-tension pressure plane is statics (not vault-cited);
it reproduces the closed-form uniaxial partial-contact result to 0.03 %.

## Edition positions (read before quoting a number)

| Item | This skill | Why |
|---|---|---|
| φ law | `nscp2015`: tension-controlled at εt ≥ 0.005 | NSCP Table 421.2.2. `aci318-19` = εty + 0.003; `aci318-25` adds §21.2.2.3; `envelope` = least |
| εty | fy/Es always | NSCP 421.2.2.1's “Grade 280 … 0.002” option is not used |
| Shear section limit | 0.66 | ACI prints 0.66, NSCP prints 0.67 — the smaller is conservative |
| One-way Vc | 0.17 λ√f′c (NSCP) | rc-design uses ⅙ (0.167, 2 % lower) — both legal |
| SMF spacing | 6db (NSCP); 5db for Gr 550 reported as WARN | 318-19+ added 5db |
| Strong column at the roof | checked (NSCP has no exemption); WARN when 318-19+ would exempt | §418.7.3.1 vs §18.7.3.1 |
| Joint γ | NSCP 3-row table | 318-25M 8-row table is an edition change |
| Table 418.7.5.4 row (f) | 0.35 kf Pu/(fyt Ach) (no kn) | NSCP prints kf kn; kn is defined for rectilinear hoops only |
| Pu for 418.7.5.2(f) | largest compression of the E combinations | the clause says so |
| Pu for Table 418.7.5.4 (c)/(f) | largest compression of ALL combinations | conservative; W&M Ex 19-2 uses the gravity combination |
| Mnc for strong column | Mn at Pn = Pu (nominal diagram), least over the E range | clause text; W&M Ex 19-2 reads the φ-chart instead |
| φ for SMF column shear | literal §421.2.4.1: 0.60 unless Vn ≥ shear at Mn | W&M/NIST examples take 0.75 without the check |

## Findings raised while building this skill

1. **Vault Concrete/05, worked example §5:** γ = 1.7 is taken for 400 mm beams on a 600 mm column.
   NSCP §418.8.4.2 (4-118 ✅) counts a face as confined only when the beam width is ≥ ¾ of the
   effective joint width (≥ 450 mm) → γ = 1.0, φVn = 1619 kN < Vj ≈ 1772 kN — the example joint
   **fails**. Pinned in `tests/benchmarks/vault_c05_joint.json`.
2. **APEC design criteria §3.6 (project document):** the ASD set is NSCP **§203.4.1**, not §203.3.2
   (which is ponding); NSCP's 203-11 carries 0.75(Lr or R) with 0.75L; 203-2/203-3 carry 0.5/1.6(Lr or R).
   With Lr, R, F, T absent the generated set reduces exactly to the §3.6 list.
3. **NSCP 2015 misprints noted (not “fixed”, flagged):** Table 418.7.5.4 (f) kn; 203-11/203-13
   dropped `+`; §421.2.2.1 “Grade 280”; Eq. 422.5.1.2 coefficient 0.67.
4. **W&M 7th Fig. 19-27** chart reads (φMn 490/520/430 kip-ft) match neither φMn(Pn = Pu) nor
   φMn(φPn = Pu) of the stated section; not pinned. Mpr (835) is reproduced to 0.5 %.

## Not in this skill (say so in the report)

Development/splice LENGTHS (Ch. 25 — only the 418.8.5.1 hook in joints), moment magnification
(406.6.4/406.7 — demands must be second-order when slender), IMF/OMF columns (418.4/418.3),
walls, composite/prestressed/hollow columns, combined/mat/pile foundations, settlement.
If a question needs one of these and the vault has no basis, use the vault refusal sentence:
> The reference folder does not contain enough basis to support this answer.
