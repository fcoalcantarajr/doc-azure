import base64
import inspect
import io
import json
from unittest import TestCase
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus
from urllib.request import Request

import doc_azure.azure_client as azure_client
from doc_azure.azure_client import (
    ApiResponse,
    AzureClient,
    AzureReadError,
    _redact,
    is_allowlisted_read,
)


class _JsonResponse:
    def __init__(self, payload, headers):
        self._payload = payload
        self.headers = headers

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class _RawResponse:
    def __init__(self, raw_payload, headers=None):
        self._raw_payload = raw_payload
        self.headers = headers or {}

    def read(self):
        return self._raw_payload


class _BrokenRead:
    def read(self, size=-1):
        raise OSError("body unavailable")

    def close(self):
        pass


class ReadOnlyBoundaryTests(TestCase):
    def test_redirect_handler_fails_closed_before_following_location(self):
        handler_class = getattr(azure_client, "_RejectRedirectHandler", None)
        self.assertIsNotNone(handler_class)
        handler = handler_class()
        request = Request("https://example.com/org/_apis/work/processes")

        with self.assertRaises(HTTPError) as raised:
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {"Location": "https://other.example/next"},
                "https://other.example/next",
            )

        self.assertEqual(raised.exception.code, 302)
        self.assertIn("redirect", str(raised.exception).lower())

    def test_allows_get_process_metadata(self):
        self.assertTrue(
            is_allowlisted_read(
                "GET",
                "/_apis/work/processes/process-id/workitemtypes",
            )
        )

    def test_allows_every_documented_get_family(self):
        allowed_paths = (
            "/project/_apis/wiki/wikis/wiki-id/pages/35",
            "/_apis/work/processes/process-id/behaviors",
            "/project/_apis/wit/workitems/123",
            "/_apis/wit/workitems/123/fields",
        )

        for path in allowed_paths:
            with self.subTest(path=path):
                self.assertTrue(is_allowlisted_read("GET", path))

    def test_allows_documented_post_queries(self):
        self.assertTrue(is_allowlisted_read("POST", "/project/_apis/wit/wiql"))
        self.assertTrue(
            is_allowlisted_read("POST", "/project/_apis/wit/workitemsbatch")
        )

    def test_rejects_post_query_creation_and_mutating_verbs(self):
        self.assertFalse(is_allowlisted_read("POST", "/project/_apis/wit/queries"))
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertFalse(
                    is_allowlisted_read(method, "/_apis/work/processes/x")
                )

    def test_rejects_post_subresources_and_method_override(self):
        self.assertFalse(is_allowlisted_read("POST", "/project/_apis/wit/wiql/x"))
        self.assertFalse(
            is_allowlisted_read("X-HTTP-Method-Override", "/_apis/wit/wiql")
        )

    def test_rejects_absolute_hosts_fragments_and_paths_outside_allowlist(self):
        rejected_paths = (
            "https://evil.example/_apis/work/processes",
            "//evil.example/_apis/work/processes",
            "/_apis/work/processes#fragment",
            "/project/_apis/wit/wiql%2Fextra",
            "/project/_apis/wit/queries",
        )

        for path in rejected_paths:
            with self.subTest(path=path):
                self.assertFalse(is_allowlisted_read("GET", path))

    def test_rejects_path_query_string_so_only_query_argument_can_add_parameters(self):
        self.assertFalse(
            is_allowlisted_read(
                "GET",
                "/_apis/work/processes?api-version=999.0",
            )
        )

    def test_rejects_residual_percent_escapes_after_one_decode(self):
        for path in (
            "/_apis/work/processes/%252f",
            "/_apis/work/processes/%252e%252e",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_allowlisted_read("GET", path))

    def test_error_message_redacts_pat(self):
        def failing_transport(request, timeout):
            raise URLError("connection failed")

        client = AzureClient(
            "https://example.com/org",
            "top-secret",
            failing_transport,
        )

        with self.assertRaises(AzureReadError) as raised:
            client.request_json("GET", "/_apis/work/processes")

        self.assertNotIn("top-secret", str(raised.exception))
        self.assertNotIn("Authorization", str(raised.exception))

    def test_request_encodes_only_allowlisted_route_and_fixed_api_version(self):
        seen = {}

        def transport(request, timeout):
            seen["request"] = request
            seen["timeout"] = timeout
            return _JsonResponse({"count": 1}, {"X-Trace": "trace-1"})

        client = AzureClient("https://example.com/org/", "safe-pat", transport)
        response = client.request_json(
            "GET",
            "/_apis/work/processes",
            query={"$top": "1", "api-version": "invalid"},
        )

        self.assertEqual(
            seen["request"].full_url,
            "https://example.com/org/_apis/work/processes?%24top=1&api-version=7.1",
        )
        self.assertEqual(seen["request"].method, "GET")
        self.assertEqual(seen["timeout"], 30)
        self.assertIsInstance(response, ApiResponse)
        self.assertEqual(response.payload, {"count": 1})
        self.assertEqual(response.headers, {"X-Trace": "trace-1"})
        self.assertEqual(response.url, seen["request"].full_url)

    def test_request_replaces_api_version_case_insensitively(self):
        seen = {}

        def transport(request, timeout):
            seen["url"] = request.full_url
            return _JsonResponse({"count": 0}, {})

        client = AzureClient("https://example.com/org", "safe-pat", transport)
        client.request_json(
            "GET",
            "/_apis/work/processes",
            query={"API-Version": "999.0", "api-VERSION": "8.0", "$top": "2"},
        )

        self.assertEqual(
            seen["url"],
            "https://example.com/org/_apis/work/processes?%24top=2&api-version=7.1",
        )

    def test_response_url_redacts_sensitive_query_values(self):
        def transport(request, timeout):
            return _JsonResponse({"count": 0}, {})

        client = AzureClient("https://example.com/org", "local-secret", transport)
        response = client.request_json(
            "GET",
            "/_apis/work/processes",
            query={"pat": "sensitive-param-value"},
        )

        # Sensitive key "pat" gets redacted, and PAT is never exposed
        self.assertNotIn("local-secret", response.url)
        self.assertNotIn("authorization", response.url)
        self.assertIn("%3Credacted%3E", response.url)

    def test_query_with_pat_is_rejected_before_transport_and_never_leaks(self):
        pat = "a/b secret"
        encoded_pat = quote(pat, safe="")

        def transport(request, timeout):
            self.fail("transport must not receive a query containing the PAT")

        client = AzureClient("https://example.com/org", pat, transport)

        for secret_value in (pat, encoded_pat, quote_plus(pat)):
            with self.subTest(secret_value=secret_value):
                with self.assertRaises(AzureReadError) as raised:
                    client.request_json(
                        "GET",
                        "/_apis/work/processes",
                        query={"continuationToken": secret_value},
                    )
                message = str(raised.exception)
                self.assertNotIn(pat, message)
                self.assertNotIn(encoded_pat, message)

    def test_query_with_authorization_material_is_rejected_but_continuation_token_is_allowed(self):
        seen = {}

        def transport(request, timeout):
            seen["url"] = request.full_url
            return _JsonResponse({"count": 0}, {})

        client = AzureClient("https://example.com/org", "safe-pat", transport)
        client.request_json(
            "GET",
            "/_apis/work/processes",
            query={"continuationToken": "page-2"},
        )
        self.assertIn("continuationToken=page-2", seen["url"])

        with self.assertRaises(AzureReadError) as raised:
            client.request_json(
                "GET",
                "/_apis/work/processes",
                query={"filter": "Proxy-Authorization: Custom credential"},
            )
        self.assertNotIn("Custom", str(raised.exception))

    def test_redact_removes_literal_and_encoded_pat_without_erasing_common_text(self):
        pat = "a/b secret"
        encoded_pat = quote(pat, safe="")
        plus_pat = quote_plus(pat)
        message = (
            f"Basic science; {pat}; {encoded_pat}; {plus_pat}; "
            "Proxy-Authorization: Custom credential"
        )

        redacted = _redact(message, pat)

        self.assertIn("Basic science", redacted)
        self.assertNotIn(pat, redacted)
        self.assertNotIn(encoded_pat, redacted)
        self.assertNotIn(plus_pat, redacted)
        self.assertNotIn("credential", redacted)

    def test_post_body_is_json_and_client_does_not_expose_arbitrary_headers(self):
        seen = {}

        def transport(request, timeout):
            seen["request"] = request
            return _JsonResponse({"workItems": []}, {})

        client = AzureClient("https://example.com/org", "safe-pat", transport)
        client.request_json(
            "POST",
            "/project/_apis/wit/wiql",
            body={"query": "SELECT [System.Id] FROM WorkItems"},
        )

        request = seen["request"]
        self.assertEqual(request.data, b'{"query":"SELECT [System.Id] FROM WorkItems"}')
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertIsNone(request.get_header("X-http-method-override"))
        self.assertNotIn("headers", inspect.signature(client.request_json).parameters)
        expected_auth = "Basic " + base64.b64encode(b":safe-pat").decode("ascii")
        self.assertEqual(request.get_header("Authorization"), expected_auth)

    def test_get_body_is_rejected_before_transport(self):
        def transport(request, timeout):
            self.fail("GET with a body must not reach transport")

        client = AzureClient("https://example.com/org", "safe-pat", transport)

        with self.assertRaisesRegex(AzureReadError, "bodies"):
            client.request_json(
                "GET", "/_apis/work/processes", body={"unexpected": "body"}
            )

    def test_non_json_post_body_becomes_safe_read_error_before_transport(self):
        def transport(request, timeout):
            self.fail("non-JSON body must not reach transport")

        client = AzureClient("https://example.com/org", "safe-pat", transport)

        with self.assertRaises(AzureReadError) as raised:
            client.request_json(
                "POST",
                "/project/_apis/wit/wiql",
                body={"unsupported": object()},
            )

        self.assertNotIn("safe-pat", str(raised.exception))

    def test_invalid_json_response_becomes_safe_read_error(self):
        def transport(request, timeout):
            return _RawResponse(b"{")

        client = AzureClient("https://example.com/org", "safe-pat", transport)

        with self.assertRaises(AzureReadError) as raised:
            client.request_json("GET", "/_apis/work/processes")

        self.assertNotIn("safe-pat", str(raised.exception))

    def test_json_array_response_becomes_safe_read_error(self):
        def transport(request, timeout):
            return _RawResponse(b"[]")

        client = AzureClient("https://example.com/org", "safe-pat", transport)

        with self.assertRaises(AzureReadError) as raised:
            client.request_json("GET", "/_apis/work/processes")

        self.assertNotIn("safe-pat", str(raised.exception))

    def test_http_error_with_unreadable_body_becomes_safe_read_error(self):
        def transport(request, timeout):
            raise HTTPError(
                request.full_url,
                500,
                "Server Error",
                {},
                _BrokenRead(),
            )

        client = AzureClient("https://example.com/org", "safe-pat", transport)

        with self.assertRaises(AzureReadError) as raised:
            client.request_json("GET", "/_apis/work/processes")

        self.assertIn("HTTP 500", str(raised.exception))
        self.assertNotIn("safe-pat", str(raised.exception))

    def test_response_headers_remove_authorization_schemes_but_keep_common_text(self):
        def transport(request, timeout):
            return _JsonResponse(
                {"count": 0},
                {
                    "Authorization": "Custom secret",
                    "Proxy-Authorization": "Odd secret",
                    "WWW-Authenticate": "Bearer realm=example",
                    "X-Note": "Basic science",
                },
            )

        client = AzureClient("https://example.com/org", "safe-pat", transport)
        response = client.request_json("GET", "/_apis/work/processes")

        self.assertNotIn("Authorization", response.headers)
        self.assertNotIn("Proxy-Authorization", response.headers)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer realm=example")
        self.assertEqual(response.headers["X-Note"], "Basic science")

    def test_request_rejects_disallowed_routes_before_transport(self):
        def transport(request, timeout):
            self.fail("transport must not be called for a rejected route")

        client = AzureClient("https://example.com/org", "safe-pat", transport)

        with self.assertRaisesRegex(AzureReadError, "not allowlisted"):
            client.request_json("POST", "/project/_apis/wit/queries")

    def test_http_error_is_capped_and_redacts_authorization_like_remote_body(self):
        body = b"Authorization: Basic remote-secret\n" + (b"x" * 600)

        def failing_transport(request, timeout):
            raise HTTPError(
                request.full_url,
                403,
                "Forbidden",
                {},
                io.BytesIO(body),
            )

        client = AzureClient("https://example.com/org", "local-secret", failing_transport)

        with self.assertRaises(AzureReadError) as raised:
            client.request_json("GET", "/_apis/work/processes")

        message = str(raised.exception)
        self.assertIn("HTTP 403", message)
        self.assertNotIn("local-secret", message)
        self.assertNotIn("remote-secret", message)
        self.assertNotIn("Authorization", message)
        self.assertLessEqual(len(message), 700)
