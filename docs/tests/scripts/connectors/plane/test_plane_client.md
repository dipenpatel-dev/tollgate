---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: tollgate
source_file: tests/scripts/connectors/plane/test_plane_client.py    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE
last_updated: 2026-11-20
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: [scripts/connectors/plane/plane_work_item_client.py, scripts/connectors/plane/plane_sync_settings.py]         # source files under test, relative paths from repo root
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

Tests for the Plane client, the small class that makes seven paced calls to a Plane server (projects, states, work items, comments). They check paging, the shape checks on replies, that a failed call is never retried, that a redirect is an error, that error messages leave out the host and the token, the pause between calls, that every call goes through the http object the client is given, and that plain `http://` is refused unless the caller says otherwise. Most tests call a local stub server on `127.0.0.1`; a few use a mock http object and make no network call.

## Dependencies

**Depends on.**
- Under test: [[plane_work_item_client]] / [plane_work_item_client](../../../../scripts/connectors/plane/plane_work_item_client.md) for `PlaneApiError` and `PlaneWorkItemClient` {src:tests/scripts/connectors/plane/test_plane_client.py:13}; [[plane_sync_settings]] / [plane_sync_settings](../../../../scripts/connectors/plane/plane_sync_settings.md) for `PlaneAddressError` {src:tests/scripts/connectors/plane/test_plane_client.py:15}.
- Test support in the same folder: [[plane_sync_test_support]] / [plane_sync_test_support](plane_sync_test_support.md) {src:tests/scripts/connectors/plane/test_plane_client.py:17}; [[plane_stub_server]] / [plane_stub_server](plane_stub_server.md) {src:tests/scripts/connectors/plane/test_plane_client.py:16}. The first import of the support module also puts the `scripts` folder on the import path, which the later imports need {src:tests/scripts/connectors/plane/test_plane_client.py:10} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:29-31}.
- Mock http: `MockClient` from [[connector_helpers]] / [connector_helpers](../../../harness/connector_helpers.md) {src:tests/scripts/connectors/plane/test_plane_client.py:14}.
- Standard library: `unittest` {src:tests/scripts/connectors/plane/test_plane_client.py:11}.

**Used by.** Run by [[run]] / [run](run.md) through the pattern `test_*.py` {src:tests/scripts/connectors/plane/run.sh:6}. `git grep` for `test_plane_client` outside `docs/` finds no other reference (searched 2026-11-20).

## Behavior

Fixtures. `StubTestCase.setUp` starts a stub server, makes five stub work items numbered 1 to 5, and builds a client pointed at the stub {src:tests/scripts/connectors/plane/plane_sync_test_support.py:107-117}. The client uses `StubHttp`, which only talks to `127.0.0.1`, never follows a redirect, and re-raises an http error {src:tests/scripts/connectors/plane/plane_sync_test_support.py:60-77}. The fake token is built at run time from a random string {src:tests/scripts/connectors/plane/plane_sync_test_support.py:47-52}.

Tests in `TestClient` (fifteen):
1. `test_list_projects_and_states`: one project `(proj-t, T)` and the `Backlog` state id come back {src:tests/scripts/connectors/plane/test_plane_client.py:21-24}; see {src:scripts/connectors/plane/plane_work_item_client.py:191-210}.
2. `test_list_work_items_follows_the_cursor`: with page size 2 the five items come back in three GET calls, and the first call asks for the listed fields and `per_page=2` {src:tests/scripts/connectors/plane/test_plane_client.py:26-33}. The client loops while the reply says more pages exist {src:scripts/connectors/plane/plane_work_item_client.py:176-189}.
3. `test_cursor_that_does_not_advance_is_a_shape_error`: a stub that repeats its cursor makes the client stop with `cursor did not advance` {src:tests/scripts/connectors/plane/test_plane_client.py:35-40}; the check is `next_cursor == cursor` {src:scripts/connectors/plane/plane_work_item_client.py:187-188}.
4. `test_create_update_comment_and_get`: create gives number 6, update sets `external_id`, the comment is stored with its html, key and source `tollgate`, the comment id is `cm-1`, a fetch shows `T-6`, and the description is `None` {src:tests/scripts/connectors/plane/test_plane_client.py:42-52}; see {src:scripts/connectors/plane/plane_work_item_client.py:221-243}.
5. `test_token_is_sent_in_the_header_and_content_type_is_json`: the first call carries `x-api-key` with the token and `content-type: application/json` {src:tests/scripts/connectors/plane/test_plane_client.py:54-58}; the client builds those headers once {src:scripts/connectors/plane/plane_work_item_client.py:140}.
6. `test_a_500_reply_is_not_retried`: a failing POST raises `PlaneApiError` with status 500 and the stub sees one POST {src:tests/scripts/connectors/plane/test_plane_client.py:60-65}. `_send` makes one request and has no loop {src:scripts/connectors/plane/plane_work_item_client.py:160-166}.
7. `test_error_message_has_method_path_status_and_no_host_or_token`: a 503 gives a message that starts `GET projects/ failed: status 503` and holds neither the host, the token nor the stub body {src:tests/scripts/connectors/plane/test_plane_client.py:67-75}. The message is built from method, path, status and reason only {src:scripts/connectors/plane/plane_work_item_client.py:52-57}.
8. `test_redirect_is_an_error_and_is_not_followed`: a 302 raises an error with status 302 and a second stub receives no call {src:tests/scripts/connectors/plane/test_plane_client.py:77-85}. See the first note below.
9. `test_unreachable_server_raises_with_no_status`: a stopped server gives an error with status `None` and no host in the message {src:tests/scripts/connectors/plane/test_plane_client.py:87-94}; see {src:scripts/connectors/plane/plane_work_item_client.py:163-166}.
10. `test_reply_without_sequence_id_is_a_shape_error`: an item whose number is the text `six` raises an error that names `sequence_id` {src:tests/scripts/connectors/plane/test_plane_client.py:96-102}; the check is on the type of the field {src:scripts/connectors/plane/plane_work_item_client.py:79-81}.
11. `test_description_is_none_when_absent_and_text_when_present`: a stub description comes back as text {src:tests/scripts/connectors/plane/test_plane_client.py:104-107}.
12. `test_calls_are_paced`: with a fake clock and a fake sleep, calls 0.5 seconds apart and a minimum of 1.2 seconds make exactly one sleep of 0.7 {src:tests/scripts/connectors/plane/test_plane_client.py:109-126}, matching `_pace` {src:scripts/connectors/plane/plane_work_item_client.py:142-147}. The first call does not sleep because no start time is saved yet {src:scripts/connectors/plane/plane_work_item_client.py:143}.
13. `test_every_call_goes_through_the_http_object_it_was_given`: with a mock keyed to one exact URL, `list_projects` returns the mock's project, makes one call, and sends `X-API-Key` {src:tests/scripts/connectors/plane/test_plane_client.py:128-138}. The URL is `address + /api/v1/workspaces/<slug>/projects/?per_page=100` {src:scripts/connectors/plane/plane_work_item_client.py:131} {src:scripts/connectors/plane/plane_work_item_client.py:157}.
14. `test_the_client_refuses_http_unless_told_otherwise`: `http://` raises `PlaneAddressError`; `http://127.0.0.1:9` with the allow flag and plain `https://` are accepted {src:tests/scripts/connectors/plane/test_plane_client.py:140-145}; see {src:scripts/connectors/plane/plane_work_item_client.py:129-130}.
15. `test_a_non_json_reply_is_a_shape_error`: a text body `not json` raises an error that says `not valid JSON` {src:tests/scripts/connectors/plane/test_plane_client.py:147-155}; see {src:scripts/connectors/plane/plane_work_item_client.py:105-108}.

## Diagram

<!-- Skipped: one stub server and one mock http object; the fixtures are listed in Behavior. -->

## Notes

- **A test that proves less than its name.** `test_redirect_is_an_error_and_is_not_followed` passes because the test's own `StubHttp` refuses to follow redirects {src:tests/scripts/connectors/plane/plane_sync_test_support.py:55-57} {src:tests/scripts/connectors/plane/plane_sync_test_support.py:64}. The client has no redirect handling of its own. It also asserts status 302 {src:tests/scripts/connectors/plane/test_plane_client.py:84}, which the real http client never produces: on a redirect it raises `RedirectRefused`, which has no status code {src:scripts/connectors/registry.py:240-245}, so the client would record status `None` {src:scripts/connectors/plane/plane_work_item_client.py:92-94}. The real path is not exercised here.
- **A test that cannot fail.** The last assertion in `test_every_call_goes_through_the_http_object_it_was_given` says the stub saw no call {src:tests/scripts/connectors/plane/test_plane_client.py:138}. The client in that test points at `plane.example.invalid`, not at the stub {src:tests/scripts/connectors/plane/test_plane_client.py:132}, so the stub could never be called.
- **Code and description.** The header says the tests cover "paging, shape checks, no retry, redirects, pacing" {src:tests/scripts/connectors/plane/test_plane_client.py:2}. Each has a test (see the redirect note above). The test named `..._without_sequence_id...` actually sets the field to text, not removes it {src:tests/scripts/connectors/plane/test_plane_client.py:99}. The `Date:` field is empty {src:tests/scripts/connectors/plane/test_plane_client.py:4}.
- **Machine and Python dependence.** `test_unreachable_server_raises_with_no_status` stops a server and then calls its old port {src:tests/scripts/connectors/plane/test_plane_client.py:88-91}. If another program took that port in between, the test would fail; this is unlikely. The tests need loopback networking {src:tests/scripts/connectors/plane/plane_stub_server.py:177}. No fixed machine path or Python version dependence found.
- **Unchecked inputs (product code the tests drive).** The address only has to start with `https://` unless the allow flag is set; nothing else about it is checked here {src:scripts/connectors/plane/plane_work_item_client.py:129-130}. The workspace slug and the ids are URL-quoted before use {src:scripts/connectors/plane/plane_work_item_client.py:131} {src:scripts/connectors/plane/plane_work_item_client.py:192-218}. The comment text and the card name go into the request body without a check in this class {src:scripts/connectors/plane/plane_work_item_client.py:223} {src:scripts/connectors/plane/plane_work_item_client.py:235-239}. The key goes in a header to whatever address was given {src:scripts/connectors/plane/plane_work_item_client.py:140}. The real http client checks the address before sending {src:scripts/connectors/registry.py:230}.
- **Writes to shared files.** None. The tests write only to temporary folders made by the support class {src:tests/scripts/connectors/plane/plane_sync_test_support.py:109-115}; the stub keeps its state in memory {src:tests/scripts/connectors/plane/plane_stub_server.py:57-64}.
