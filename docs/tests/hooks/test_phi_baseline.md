---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "tollgate"
source_file: "tests/hooks/test_phi_baseline.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/phi_patterns.py"]
tags: [phi, baseline, regression]
links: []
---

## Purpose

A baseline regression for PHI detection. It pins what the detector flags and what it ignores today, so new rules can be added without changing old behavior. {src:tests/hooks/test_phi_baseline.py:9-11} It also checks the level API (deny, ask, warn). {src:tests/hooks/test_phi_baseline.py:4} Fixture values are built at run time from `fake_phi.py` and `clean_corpus.py`, so this doc and the test source hold no real looking record. {src:tests/hooks/test_phi_baseline.py:10-11}

## Dependencies

Imports the helper modules `fake_phi` and `clean_corpus` from the same folder, and from `hooks/phi_patterns.py` the names `DEFAULT_LEVEL`, `LABEL_LEVELS`, `Finding`, `Level`, `scan_for_phi`, `scan_levels`, `scan_structured` and `strongest_level`. {src:tests/hooks/test_phi_baseline.py:24-39} Source under test: [phi_patterns](../../hooks/phi_patterns.md). Uses `unittest` only.

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'`. {src:tests/hooks/test_phi_baseline.py:13} This is the same discover step that [run](run.md) uses. {src:tests/hooks/run.sh:198}

## Behavior

22 tests in five classes. A helper joins the findings of the text scan and the structured scan. {src:tests/hooks/test_phi_baseline.py:42-43}

`BaselineLabeledPatterns` protects the labeled value rules:

- Each kind of labeled value built by the fixture module is flagged with its own label. {src:tests/hooks/test_phi_baseline.py:47}
- A label with no value after it is quiet. {src:tests/hooks/test_phi_baseline.py:51}
- A labeled record number inside longer multi line text is found and reported once. {src:tests/hooks/test_phi_baseline.py:56}
- Lower case text is still flagged. {src:tests/hooks/test_phi_baseline.py:60}
- Fake names, streets, phones, dates and bare record number values without a label are quiet. {src:tests/hooks/test_phi_baseline.py:63}

`BaselineColumns` protects the structured scan:

- A JSON row with a PHI named column that holds data is flagged. {src:tests/hooks/test_phi_baseline.py:70}
- A CSV header with a data row is flagged. {src:tests/hooks/test_phi_baseline.py:74}
- A PHI named column holding no data is quiet. {src:tests/hooks/test_phi_baseline.py:78}

`CleanCorpus` protects against false alarms:

- The clean corpus holds at least 20 entries. {src:tests/hooks/test_phi_baseline.py:83}
- Each entry is quiet alone, and the whole corpus joined as one text is quiet. {src:tests/hooks/test_phi_baseline.py:86} {src:tests/hooks/test_phi_baseline.py:90}

`FakeValuesStayFake` protects the test scaffolding itself:

- The three scaffolding source files (the fixture builder, the clean corpus and this test) produce no findings when scanned. {src:tests/hooks/test_phi_baseline.py:99} {src:tests/hooks/test_phi_baseline.py:97}
- The fake phone, dates and record number use reserved fake ranges: a reserved 555 phone range, dates in the year 1900, and a record number with no digit run that could pass as real. {src:tests/hooks/test_phi_baseline.py:104}

`LevelApi` protects the level layer:

- The levels are deny, ask and warn, in that order. {src:tests/hooks/test_phi_baseline.py:112}
- Every current labeled rule and the column rule report deny. {src:tests/hooks/test_phi_baseline.py:115} {src:tests/hooks/test_phi_baseline.py:119}
- The set of labels from the level scan matches the old two function scans. {src:tests/hooks/test_phi_baseline.py:123}
- Clean text and an empty list give no findings, and a repeated finding is reported once. {src:tests/hooks/test_phi_baseline.py:128} {src:tests/hooks/test_phi_baseline.py:132}
- The default level is `Level.DENY`, and a full address gives deny with no unregistered label in the result. {src:tests/hooks/test_phi_baseline.py:136}
- `strongest_level` returns nothing for an empty list, ask over warn, and deny over both. {src:tests/hooks/test_phi_baseline.py:141}
- Findings sort strongest first. {src:tests/hooks/test_phi_baseline.py:147}

What a failure means: a change to the detector altered a result that was fixed on purpose. Either a rule now flags clean text, a rule stopped flagging a known case, or fake fixture code looks like real PHI to the scanner.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The unknown label test checks that `DEFAULT_LEVEL` is `Level.DENY`, and that a full address gives deny with `UNREGISTERED_LABEL` absent from the result. `ADDRESS` is in the level registry as deny, so the address result alone does not exercise the default. {src:tests/hooks/test_phi_baseline.py:136-139} {src:hooks/phi_patterns.py:207} The header says a full address is now flagged, so the quiet check uses a street alone. {src:tests/hooks/test_phi_baseline.py:7-8} Context rules are tested in [test_phi_context_rules](test_phi_context_rules.md).
