# NSCP 2015 clause map for rc-design — with vault links

**Governing code:** NSCP 2015 Vol. I, Chapter 4 (beam provisions = ACI 318M-14).
**Readable, page-checked stand-in:** `ACI 318-25M` in `vault/reference/`, **printed = PDF − 1**.
NSCP 2015 is image-only (`reference/_Scanned/…`): its folios below come from the vault's OCR/visual
reads (Internal Learning/01, Design Procedures/05) — **quote an NSCP folio only after reading the page**.
NSCP Ch. 4 offset: printed `4-N` = PDF − 324 (drifts to − 325 from §420.6 onward).

Vault root: `~/Desktop/Programs/structural-mind/Structural Mind/vault/`

| Vault note | What it gives this skill |
|---|---|
| `concretedesignpy/CLAUSES.md` (repo `~/Desktop/Projects/concretedesignpy`) | the rectified clause register for flexure / shear / torsion / joint — **Option A: NSCP 2015 governs** |
| `Software/14 - concretedesignpy Review …` | the audit CLAUSES.md rectifies (torsion 1000× bug, Al 1.7 vs 2, Av,min 0.062) |
| `Software/12 - rc-beam Solver Deep Review …` | Mpr with A′s, clear span ln, Vg with SDL + LL, silent-zero guards, φ edition gap |
| `Software/03 - rc-beam Computation Review` | first rc-beam review (Ve, φ, Vc = 0 in hinge) |
| `Internal Learning/01 - Week 1 — RC Beams …` | SMF detailing table with **NSCP twin folios**, Mpr/Ve, joint depth |
| `Design Procedures (MIDAS + Python)/05 - Crack Control & Serviceability` | Table 24.3.2 = NSCP Table 424.3.2 (identical constants), "Table 24.4.3.2 does not exist" |
| `Concrete/05 - Beam-Column Joint Check (SMRF)` | joint shear — out of scope here |

## Edition positions (read before quoting a number)

| Item | This skill | Why |
|---|---|---|
| φ flexure | `nscp2015`: tension-controlled at εt ≥ 0.005 | NSCP 2015 / 318-14. 318-19+ uses εty + 0.003 (Table 21.2.2, p. 432; R21.2.2, p. 431). ≤ 1 % apart at fy ≤ 420; **6–15 % apart above** → `phi_rule: envelope` |
| εt floor for beams | εt ≥ 0.004 = FAIL below; not tension-controlled = WARN | 318-14 limit; 318-19+ §9.3.3.1 requires tension-controlled (R9.3.3.1, p. 144) |
| Vc | ⅙λ√f′c bw d | NSCP 422.5.5.1. 318-19 Table 22.5.5.1 (ρw, λs) is an edition change — **not** a fix |
| Joint γ | not in this skill | NSCP Table 418.8.4.1 has 3 rows; 318-25M has 8 |
| Ie | both laws, smaller Ie governs | Branson = NSCP/318-14; Bischoff = 318-19+ Table 24.2.3.5 (p. 499) — R24.2.3.5 says Branson under-predicts at low ρ |
| fr | 0.62λ√f′c | 318-25M §19.2.3.1 (p. 395) prints 0.062; the 14 May 2026 errata amends that equation — confirm on the page |
| As,min fy cap | 550 MPa | §9.6.1.2 prints "80,000 psi" in the SI edition; errata → 550 MPa |
| SMF projection | 0.75 c1 | §18.6.2.1(c) prints 0.7; errata → 0.75 |
| SMF beam width | bw ≥ **smaller** of 0.3h and 250 mm | NSCP 418.6.2.1(b), 4-113 (page read 2026-10-02) = 318-14 / 318-19 "lesser of 0.3h and 10 in.". 318-25M §18.6.2.1(b) (p. 327, and the errata restatement) prints "**larger** of" — an edition change, **not** applied: a 200 × 500 beam (limit 150 mm) is OK |

## Clause register

| Script | Check | ACI 318-25M | Printed p. | NSCP 2015 twin (folio) |
|---|---|---|---|---|
| flexure | β1 | Table 22.2.2.4.3 | 438–439 | 422.2.2.4.3 |
| flexure | 0.85 f′c block; displaced concrete A′s(f′s − 0.85f′c) | §22.2.2.4; W&M Eq. (4-31) | 438; W&M 167 | 422.2.2.4 |
| flexure | φ law | Table 21.2.2 (318-19+) / 318-14 | 432 | 421.2.2 |
| flexure | As,min; 4/3 exemption | §9.6.1.2; §9.6.1.3 | 149 | 409.6.1.2 (4-64) |
| flexure | tension-controlled beams | §9.3.3.1 + R9.3.3.1 | 144 | 409.3.3.1 (318-14: εt ≥ 0.004) |
| flexure | bar clear spacing / layers | §25.2.1 / §25.2.2 | 509 | 425.2.1 |
| shear | Vc (NSCP form), axial | NSCP 422.5.5.1, 422.5.6.1, 422.5.7.1; W&M Eq. (6-13aM) | W&M 282 | 422.5 |
| shear | φ = 0.75 | Table 21.2.1(b) | 430 | 421.2.1 |
| shear | Vs = Av fyt d / s | §22.5.8.5.3 | 449 | 422.5.10.5.3 |
| shear | section limit Vu ≤ φ(Vc + 0.66√f′c bw d) | §22.5.1.2 | 442 | 422.5.1.2 |
| shear | Av,min/s | Table 9.6.3.4 | 151 | 409.6.3 (4-64) |
| shear | s max along / across | Table 9.7.6.2.2 | 160 | 409.7.6.2.2 (4-67) |
| torsion | Tth (solid, axial row) | Table 22.7.4.1(a),(c) | 463 | 422.7.4.1 |
| torsion | Tcr; compatibility redistribution | Table 22.7.5.1; §22.7.3.2–.3 | 464; 461 | 422.7.3, 422.7.5 |
| torsion | At/s, Al (Ao = 0.85 Aoh, θ = 45°) | Eq. (22.7.6.1a/b); §22.7.6.1.1–.2 | 465–466 | 422.7.6.1 |
| torsion | Aoh on stirrup centreline | R22.7.6.1 | 465 | — |
| torsion | Al,min (lesser of a, b) | §9.6.4.3 | 152 | 409.6.4.3 |
| torsion | (Av + 2At)/s min | §9.6.4.2 | 152 | 409.6.4.2 |
| torsion | section √(v² + vt²) ≤ φ(Vc/bwd + 0.66√f′c) | §22.7.7.1 | 466 | 422.7.7.1 |
| torsion | s ≤ min(ph/8, 300); closed stirrups | §9.7.6.3.3; §9.7.6.3.1 | 160 | 409.7.6.3 |
| combine | torsion steel added to flexure/shear steel | §9.5.4.3 | 147 | 409.5.4.3 |
| combine | Al around perimeter ≤ 300 mm, corner bars, db ≥ 0.042s, ≥ 10 | §9.7.5.1–.2 | 158 | 409.7.5 |
| seismic | geometry ln ≥ 4d, bw ≥ min(0.3h, 250) (NSCP wording — see edition positions), projection | §18.6.2.1 (+ errata) | 327 | 418.6.2.1 (4-113) |
| seismic | 2 continuous bars, As,min, ρ ≤ 0.025 / 0.02 | §18.6.3.1 | 328 | 418.6.3.1 (4-113) |
| seismic | ½ and ¼ moment-strength rules | §18.6.3.2 | 328 | 418.6.3.2 (4-113) |
| seismic | lap-splice locations | §18.6.3.3 | 328 | 418.6.3.3 (4-113) |
| seismic | hoop zone 2h; first hoop ≤ 50; s ≤ d/4, 150, 6db / 5db | §18.6.4.1, §18.6.4.4 | 330–331 | 418.6.4 (4-114) |
| seismic | outside zone s ≤ d/2 | §18.6.4.5 | 331 | 418.6.4.5 (4-114) |
| seismic | supported-bar spacing ≤ 350 mm | §18.6.4.2 | 330–331 | 418.6.4.2 |
| seismic | Mpr = 1.25 fy, φ = 1 | Notation | 24 | 402 |
| seismic | Ve from Mpr on ln, both sways; wu | §18.6.5.1, Fig. R18.6.5 | 331–333 | 418.6.5 (4-115) |
| seismic | Vc = 0 in hinge (Vpr ≥ ½Ve and Pu < Ag f′c/20) | §18.6.5.2 | 333 | 418.6.5 (4-115) |
| seismic | joint depth ≥ 20db/λ (Gr 420), 26db (Gr 550) | §18.8.2.3 | 340–341 | 418.8.2.3 (4-118) |
| service | minimum h, fy modifier | Table 9.3.1.1, §9.3.1.1.1 | 143 | 409.3.1.1 |
| service | Ec = 4700√f′c | §19.2.2.1(b) | 394 | 419.2.2.1 |
| service | fr | §19.2.3.1 (+ errata) | 395 | 419.2.3.1 |
| service | Mcr, Ie (Bischoff); Branson history | Eq. (24.2.3.5), Table 24.2.3.5, R24.2.3.5 | 499 | 424.2.3.5 (Branson) |
| service | midspan Ie; continuous average | §24.2.3.7; §24.2.3.6 | 499 | 424.2.3.6–.7 |
| service | λΔ = ξ/(1 + 50ρ′), ξ table | Eq. (24.2.4.1.1), Table 24.2.4.1.3 | 501 | 424.2.4.1 |
| service | deflection limits | Table 24.2.2 | 498 | Table 424.2.2 |
| service | crack-control spacing; fs = ⅔fy | Table 24.3.2, §24.3.2.1 | 503 | Table 424.3.2 (4-158) |
| service | skin reinforcement h > 900 | §9.7.2.3 | 153 | 409.7.2.3 (4-65) |
| service | cover 40 / 50 / 75 | Table 20.5.1.3.1 | 420–421 | Table 420.6.1.3.1 (4-136) |

## Not in this skill (say so in the report)

Development / hooks / splices (Ch. 25, §18.8.5), cut-off points (§9.7.3), joint shear (§18.8.4 —
use `concretedesignpy.calculators.joint_shear`), strong-column/weak-beam (§18.7.3), IMF §18.4,
flanged sections, hollow torsion, deep beams (§9.9).
If a question needs one of these and the vault has no basis, use the vault refusal sentence:
> The reference folder does not contain enough basis to support this answer.
