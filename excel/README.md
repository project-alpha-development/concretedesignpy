# Footing Jacket - Excel calculator

`APEC-Footing-Jacket.xlsx` is the spreadsheet form of
`concretedesignpy/calculators/footing_jacket.py`: enlargement of an existing
isolated footing per ACI 562-25 with ACI 318-25M as the design-basis code and
ASCE 41-17 C8.7 for the existing contact pressure. The formulas are live;
yellow cells are the inputs and every other cell is locked. Sheet 2,
"Theory", sets out the equations behind each section as locked pictures with
the clause and printed page under each; they are typeset for the workbook,
not copied from the standards.
`APEC-Footing-Jacket-sample.pdf` is the printout of the sample inputs.

The workbook is generated, not hand-edited. The generator is the `excel/` kit
of the `apec-cfrp-beam` repository (`excel/footing.py`), which loads this
repository's solver by path:

```bash
python3 excel/build.py --password <password> --only footing   # in apec-cfrp-beam
python3 excel/verify.py footing
```

`verify.py` recalculates the workbook without Excel for 32 input cases and
compares every named cell (200 per case) with what `footing_jacket_check`
returns, so a change to the solver needs the sheet changed with it. The
protection password is passed on the command line and is not stored in either
repository.

The sheet lists what it does not check (section 10.0) and its references with
the clauses used. The engineer of record owns the inputs and those checks.
