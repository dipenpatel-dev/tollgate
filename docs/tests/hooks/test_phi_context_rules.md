---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "tollgate"
source_file: "tests/hooks/test_phi_context_rules.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/phi_patterns.py"]
tags: [phi, context-rules, performance]
links: []
---

## Purpose

Tests the PHI context rules: name anchors, clue pairs, the pairing window, and the chunked scan. {src:tests/hooks/test_phi_context_rules.py:4} Every value comes from `fake_phi.py` and is built at run time, so no sample record sits in this file. {src:tests/hooks/test_phi_context_rules.py:7}

## Dependencies

Imports `fake_phi` and `clean_corpus` from the same folder, and from `hooks/phi_patterns.py` the names `CHUNK_SIZE`, `CONTEXT_WINDOW`, `CLINICAL_TERMS`, `Finding`, `Level`, `scan_for_phi`, `scan_levels` and `strongest_level`. {src:tests/hooks/test_phi_context_rules.py:19-34} Source under test: [phi_patterns](../../hooks/phi_patterns.md). Uses `unittest` and `time`.

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'`. {src:tests/hooks/test_phi_context_rules.py:9}

## Behavior

37 tests in seven classes. Expected results are three constants: a name finding at deny, a context finding at ask, and a lone clue finding at warn. {src:tests/hooks/test_phi_context_rules.py:36-38}

`NameAnchors` protects the name rule:

- A name label with a value denies, and a last name then first name after an anchor denies. {src:tests/hooks/test_phi_context_rules.py:53} {src:tests/hooks/test_phi_context_rules.py:56}
- The anchor and the value on different lines give the same result as one line. {src:tests/hooks/test_phi_context_rules.py:59}
- Upper case text, extra spaces and tabs still deny, and a spaced out upper case address is still flagged as an address. {src:tests/hooks/test_phi_context_rules.py:64}
- A JSON style name field is found. {src:tests/hooks/test_phi_context_rules.py:71}
- The older `scan_for_phi` function does not see the name rule. {src:tests/hooks/test_phi_context_rules.py:75}
- Headings, placeholders, SQL column names and class names are quiet. {src:tests/hooks/test_phi_context_rules.py:78} {src:tests/hooks/test_phi_context_rules.py:83}

`ClueCombinations` protects the pair rule. Two different kinds of clue close together give ask:

- A titled name with a clinical phrase, a street part with a clinical term, a name with an event date, an age and sex phrase with a clinical phrase, an age in years with a clinical term, and a name with a diagnosed phrase. {src:tests/hooks/test_phi_context_rules.py:89} {src:tests/hooks/test_phi_context_rules.py:93} {src:tests/hooks/test_phi_context_rules.py:105} {src:tests/hooks/test_phi_context_rules.py:109} {src:tests/hooks/test_phi_context_rules.py:113} {src:tests/hooks/test_phi_context_rules.py:117}
- An unlabeled phone alone only warns. With a clinical term the strongest level is ask and a context finding is present. {src:tests/hooks/test_phi_context_rules.py:97} {src:tests/hooks/test_phi_context_rules.py:100}
- A titled name, an age and sex phrase, or an event date alone only warns. {src:tests/hooks/test_phi_context_rules.py:121}
- A street alone and a clinical phrase alone are quiet. {src:tests/hooks/test_phi_context_rules.py:126}
- Two clues of the same kind do not pair. An event date is not its own second clue. {src:tests/hooks/test_phi_context_rules.py:130} {src:tests/hooks/test_phi_context_rules.py:134}
- A pair in upper case still asks. {src:tests/hooks/test_phi_context_rules.py:137}

`WindowLogic` protects the pairing distance:

- A pair with a gap of half the context window asks. A pair with a gap of twice the window is not paired and only warns. {src:tests/hooks/test_phi_context_rules.py:146} {src:tests/hooks/test_phi_context_rules.py:149}
- The clinical term list holds between 35 and 45 entries. {src:tests/hooks/test_phi_context_rules.py:152}

`NegativeGuards` protects against false alarms. These are quiet: headings, class and column names, clinical identifiers alone, a phrase about years of support, a year old item without a sex word, and the whole clean corpus. {src:tests/hooks/test_phi_context_rules.py:157} {src:tests/hooks/test_phi_context_rules.py:161} {src:tests/hooks/test_phi_context_rules.py:165} {src:tests/hooks/test_phi_context_rules.py:169} {src:tests/hooks/test_phi_context_rules.py:172} {src:tests/hooks/test_phi_context_rules.py:175}

`ChunkedScan` protects the split of large input into chunks:

- A name label and a clue pair that straddle a chunk boundary are still found. {src:tests/hooks/test_phi_context_rules.py:186} {src:tests/hooks/test_phi_context_rules.py:191}
- A payload placed after three chunks of filler is not skipped. {src:tests/hooks/test_phi_context_rules.py:196}
- Clean input twice the chunk size finishes under 5 seconds. {src:tests/hooks/test_phi_context_rules.py:200} {src:tests/hooks/test_phi_context_rules.py:39}

`BoundedMatching` protects against slow pattern matching. Each input must scan in under 5 seconds: long runs of capitalized words after an anchor or a title, a long run of numbers before an age phrase, and long repeated separator, event date and clinical phrase runs, each repeated 3000 times. {src:tests/hooks/test_phi_context_rules.py:212} {src:tests/hooks/test_phi_context_rules.py:217} {src:tests/hooks/test_phi_context_rules.py:39-40}

`SourceFilesStayFake` protects the scaffolding: this test file and `fake_phi.py` produce no findings when scanned. {src:tests/hooks/test_phi_context_rules.py:224}

What a failure means: a context rule now misses a name or pair (a possible leak), flags plain engineering text, pairs clues across too large a gap, loses a match at a chunk edge, or slows down enough to stall a hook.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The speed tests use a wall clock limit of 5 seconds, so a heavily loaded machine could fail them without a real regression. {src:tests/hooks/test_phi_context_rules.py:39} Test names with a `p` or `n` number prefix refer to numbered cases in a rule list that is not in this file. {unverified} Baseline behavior is covered separately in [test_phi_baseline](test_phi_baseline.md).
