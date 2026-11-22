# Module:      test_plane_client.py
# Description: Tests for plane_work_item_client against the local stub: paging, shape checks, no retry, redirects, pacing.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       tests only; real HTTP goes to the local stub on 127.0.0.1
# Version:     1.0
# ChangeLog:
#   - First version.

import plane_sync_test_support  # noqa: F401  (puts the scripts folder on the module path)
import unittest

from connectors.plane.plane_work_item_client import PlaneApiError, PlaneWorkItemClient
from connector_helpers import MockClient
from connectors.plane.plane_sync_settings import PlaneAddressError
from plane_stub_server import WORKSPACE, FailRule, PROJECT_ID, PlaneStubServer, StubItem
from plane_sync_test_support import FAKE_TOKEN, StubHttp, StubTestCase, make_client, make_settings


class TestClient(StubTestCase):
    def test_list_projects_and_states(self) -> None:
        projects = self.client.list_projects()
        self.assertEqual([(p.project_id, p.project_key) for p in projects], [(PROJECT_ID, "T")])
        self.assertEqual(self.client.list_state_ids(PROJECT_ID)["Backlog"], "st-backlog")

    def test_list_work_items_follows_the_cursor(self) -> None:
        client = make_client(self.stub.base_url, self.settings, page_size=2)
        items = client.list_work_items(PROJECT_ID)
        self.assertEqual([i.number for i in items], [1, 2, 3, 4, 5])
        self.assertEqual(len(self.stub.calls_matching("GET", "/work-items/")), 3)
        first = self.stub.calls_matching("GET", "/work-items/")[0]
        self.assertEqual(first.query["fields"], ["id,sequence_id,name,state,external_id"])
        self.assertEqual(first.query["per_page"], ["2"])

    def test_cursor_that_does_not_advance_is_a_shape_error(self) -> None:
        self.stub.state.stuck_cursor = True
        self.stub.state.request_cap = 20
        with self.assertRaises(PlaneApiError) as caught:
            make_client(self.stub.base_url, self.settings, page_size=2).list_work_items(PROJECT_ID)
        self.assertIn("cursor did not advance", str(caught.exception))

    def test_create_update_comment_and_get(self) -> None:
        card = self.client.create_work_item(PROJECT_ID, name="New one", state_id="st-backlog")
        self.assertEqual(card.number, self.local_highest + 1)
        self.client.update_work_item(PROJECT_ID, card.work_item_id, {"external_id": "T-6"})
        comment_id = self.client.post_comment(PROJECT_ID, card.work_item_id, "<p>x</p>", "key1")
        self.assertEqual(comment_id, "cm-1")
        body = self.stub.state.comments[0]
        self.assertEqual((body["comment_html"], body["external_id"], body["external_source"]), ("<p>x</p>", "key1", "tollgate"))
        fetched = self.client.get_work_item(PROJECT_ID, card.work_item_id)
        self.assertEqual(fetched.external_id, "T-6")
        self.assertIsNone(self.client.get_work_item(PROJECT_ID, card.work_item_id).description_html)

    def test_token_is_sent_in_the_header_and_content_type_is_json(self) -> None:
        self.client.list_projects()
        headers = {name.lower(): value for name, value in self.stub.state.calls[0].headers.items()}
        self.assertEqual(headers["x-api-key"], FAKE_TOKEN)
        self.assertEqual(headers["content-type"], "application/json")

    def test_a_500_reply_is_not_retried(self) -> None:
        self.stub.state.fail_rules.append(FailRule("POST", "/work-items/", 500))
        with self.assertRaises(PlaneApiError) as caught:
            self.client.create_work_item(PROJECT_ID, name="x", state_id="st-backlog")
        self.assertEqual(caught.exception.status, 500)
        self.assertEqual(len(self.stub.calls_matching("POST", "/work-items/")), 1)

    def test_error_message_has_method_path_status_and_no_host_or_token(self) -> None:
        self.stub.state.fail_rules.append(FailRule("GET", "/projects/", 503))
        with self.assertRaises(PlaneApiError) as caught:
            self.client.list_projects()
        message = str(caught.exception)
        self.assertTrue(message.startswith("GET projects/ failed: status 503"))
        self.assertNotIn("127.0.0.1", message)
        self.assertNotIn(FAKE_TOKEN, message)
        self.assertNotIn("stub failure", message)

    def test_redirect_is_an_error_and_is_not_followed(self) -> None:
        other = PlaneStubServer().start()
        self.addCleanup(other.stop)
        target = f"{other.base_url}/api/v1/workspaces/ws-test/projects/"
        self.stub.state.fail_rules.append(FailRule("GET", "/projects/", 302, location=target))
        with self.assertRaises(PlaneApiError) as caught:
            self.client.list_projects()
        self.assertEqual(caught.exception.status, 302)
        self.assertEqual(other.state.calls, [])

    def test_unreachable_server_raises_with_no_status(self) -> None:
        dead = PlaneStubServer().start()
        url = dead.base_url
        dead.stop()
        with self.assertRaises(PlaneApiError) as caught:
            make_client(url, make_settings()).list_projects()
        self.assertIsNone(caught.exception.status)
        self.assertNotIn("127.0.0.1", str(caught.exception))

    def test_reply_without_sequence_id_is_a_shape_error(self) -> None:
        self.stub.state.items.append(StubItem("wi-x", 6, "bad"))
        original = self.stub.state.items[-1]
        original.number = "six"  # type: ignore[assignment]
        with self.assertRaises(PlaneApiError) as caught:
            self.client.list_work_items(PROJECT_ID)
        self.assertIn("sequence_id", str(caught.exception))

    def test_description_is_none_when_absent_and_text_when_present(self) -> None:
        self.stub.state.items[0].description_html = "<p>hi</p>"
        item = self.client.get_work_item(PROJECT_ID, "wi-1")
        self.assertEqual(item.description_html, "<p>hi</p>")

    def test_calls_are_paced(self) -> None:
        now = [0.0]
        slept: list[float] = []

        def fake_sleep(seconds: float) -> None:
            slept.append(seconds)
            now[0] += seconds

        client = PlaneWorkItemClient(
            self.stub.base_url, WORKSPACE, FAKE_TOKEN, StubHttp(), external_source="tollgate",
            min_seconds_between_calls=1.2, timeout_seconds=5.0, page_size=100,
            allow_insecure_http=True, sleep=fake_sleep, clock=lambda: now[0],
        )
        client.list_projects()
        now[0] += 0.5
        client.list_projects()
        self.assertEqual(len(slept), 1)
        self.assertAlmostEqual(slept[0], 0.7)

    def test_every_call_goes_through_the_http_object_it_was_given(self) -> None:
        mock = MockClient({("GET", "https://plane.example.invalid/api/v1/workspaces/ws-test/projects/?per_page=100"):
                           {"status": 200, "body": {"results": [{"id": "p1", "identifier": "T"}],
                                                    "next_page_results": False}}})
        client = PlaneWorkItemClient("https://plane.example.invalid/", WORKSPACE, FAKE_TOKEN, mock,
                                     external_source="tollgate", min_seconds_between_calls=0.0,
                                     timeout_seconds=5.0, page_size=100)
        self.assertEqual([p.project_id for p in client.list_projects()], ["p1"])
        self.assertEqual(len(mock.calls), 1)
        self.assertEqual(mock.calls[0]["kwargs"]["headers"]["X-API-Key"], FAKE_TOKEN)
        self.assertEqual(self.stub.state.calls, [])

    def test_the_client_refuses_http_unless_told_otherwise(self) -> None:
        args = dict(external_source="tollgate", min_seconds_between_calls=0.0, timeout_seconds=5.0, page_size=10)
        with self.assertRaises(PlaneAddressError):
            PlaneWorkItemClient("http://plane.example.invalid", WORKSPACE, FAKE_TOKEN, MockClient(), **args)
        PlaneWorkItemClient("http://127.0.0.1:9", WORKSPACE, FAKE_TOKEN, MockClient(), allow_insecure_http=True, **args)
        PlaneWorkItemClient("https://plane.example.invalid", WORKSPACE, FAKE_TOKEN, MockClient(), **args)

    def test_a_non_json_reply_is_a_shape_error(self) -> None:
        mock = MockClient({("GET", "https://plane.example.invalid/api/v1/workspaces/ws-test/projects/?per_page=100"):
                           {"status": 200, "body": "not json"}})
        client = PlaneWorkItemClient("https://plane.example.invalid", WORKSPACE, FAKE_TOKEN, mock,
                                     external_source="tollgate", min_seconds_between_calls=0.0,
                                     timeout_seconds=5.0, page_size=100)
        with self.assertRaises(PlaneApiError) as caught:
            client.list_projects()
        self.assertIn("not valid JSON", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
