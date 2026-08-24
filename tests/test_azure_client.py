from __future__ import annotations

import asyncio
import base64
import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from urllib.parse import quote, quote_plus

import httpx
import pytest

from doc_azure.azure_client import (
    ALLOWED_OPERATIONS,
    AzureReadClient,
    AzureReadError,
    RequestRecord,
    is_allowlisted_read,
)


class SequencedTransport:
    """Return complete HTTP responses in order while recording real requests."""

    def __init__(
        self,
        responses: Sequence[
            tuple[int, dict[str, object] | bytes, dict[str, str]] | Exception
        ],
    ) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("unexpected HTTP request")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        status, payload, headers = response
        if isinstance(payload, bytes):
            return httpx.Response(
                status,
                content=payload,
                headers=headers,
                request=request,
            )
        return httpx.Response(
            status,
            json=payload,
            headers=headers,
            request=request,
        )


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def run(coroutine: Awaitable[dict[str, object]]) -> dict[str, object]:
    return asyncio.run(coroutine)


def make_client(
    http: httpx.AsyncClient,
    *,
    pat: str = "test-pat",
    semaphore: asyncio.Semaphore | None = None,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AzureReadClient:
    return AzureReadClient(
        http,
        "https://dev.azure.com/example-org",
        pat,
        semaphore or asyncio.Semaphore(2),
        sleeper=sleeper,
    )


def test_allows_only_semantic_reads() -> None:
    allowed_gets = (
        "/project/_apis/wiki/wikis/wiki-id/pages/35",
        "/_apis/work/processes",
        "/_apis/work/processes/process-id",
        "/_apis/work/processes/process-id/workitemtypes",
        "/_apis/work/processes/process-id/workitemtypes/wit-ref/fields",
        "/_apis/work/processes/process-id/workitemtypes/wit-ref/states",
        "/_apis/work/processes/process-id/workitemtypes/wit-ref/rules",
        "/_apis/work/processes/process-id/workitemtypes/wit-ref/layout",
        "/_apis/work/processes/process-id/behaviors",
        "/_apis/work/processes/process-id/workitemtypesbehaviors/wit-ref/behaviors",
        "/project/_apis/wit/workitems/123",
    )
    for path in allowed_gets:
        assert is_allowlisted_read("GET", path), path

    assert is_allowlisted_read("POST", "/project/_apis/wit/wiql")
    assert is_allowlisted_read("POST", "/project/_apis/wit/workitemsbatch")
    assert not is_allowlisted_read("POST", "/project/_apis/wit/queries")
    assert not is_allowlisted_read("POST", "/nested/project/_apis/wit/wiql")
    assert not is_allowlisted_read("PATCH", "/_apis/work/processes/x")
    assert not is_allowlisted_read("X-HTTP-Method-Override", "/project/_apis/wit/wiql")
    assert all(operation.method in {"GET", "POST"} for operation in ALLOWED_OPERATIONS)


@pytest.mark.parametrize(
    "path",
    (
        "https://evil.invalid/_apis/work/processes",
        "//evil.invalid/_apis/work/processes",
        "/_apis/work/processes?api-version=999.0",
        "/_apis/work/processes#fragment",
        "/_apis/work/processes/../wit",
        "/_apis/work/processes/%2e%2e/wit",
        "/_apis/work/processes/%252f",
        "/_apis/work/processes\\x",
    ),
)
def test_rejects_absolute_or_noncanonical_paths(path: str) -> None:
    assert not is_allowlisted_read("GET", path)


@pytest.mark.parametrize(
    "base_url",
    (
        "http://dev.azure.com/example-org",
        "https://evil.invalid/example-org",
        "https://user:password@dev.azure.com/example-org",
        "https://dev.azure.com/example-org?token=value",
        "https://dev.azure.com/example-org#fragment",
        "https://dev.azure.com",
        "https://dev.azure.com/org/extra",
    ),
)
def test_rejects_base_urls_outside_one_azure_organization(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        AzureReadClient(
            httpx.AsyncClient(),
            base_url,
            "test-pat",
            asyncio.Semaphore(1),
        )


def test_forces_api_version_and_returns_a_json_object() -> None:
    transport = SequencedTransport([(200, {"count": 1}, {"X-Trace": "trace-1"})])

    async def scenario() -> tuple[dict[str, object], AzureReadClient]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = make_client(http)
            result = await client.request_json(
                "GET",
                "/_apis/work/processes",
                query={"$top": "1", "API-Version": "999", "api-version": "8"},
            )
            return result, client

    result, client = asyncio.run(scenario())

    assert result == {"count": 1}
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.method == "GET"
    assert request.url.params.get_list("api-version") == ["7.1"]
    assert request.url.params["$top"] == "1"
    assert client.request_records == (
        RequestRecord("GET", "/_apis/work/processes"),
    )


def test_builds_auth_internally_and_exposes_no_header_override() -> None:
    transport = SequencedTransport([(200, {"count": 0}, {})])

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            await make_client(http, pat="safe-pat").request_json(
                "GET", "/_apis/work/processes"
            )

    asyncio.run(scenario())

    expected = "Basic " + base64.b64encode(b":safe-pat").decode("ascii")
    assert transport.requests[0].headers["Authorization"] == expected
    assert "headers" not in inspect.signature(AzureReadClient.request_json).parameters


@pytest.mark.parametrize("key", ("pat", "access_token", "Authorization", "secret"))
def test_rejects_credential_query_keys_before_http(key: str) -> None:
    transport = SequencedTransport([])

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError, match="credential"):
                await make_client(http).request_json(
                    "GET", "/_apis/work/processes", query={key: "not-a-secret"}
                )

    asyncio.run(scenario())
    assert transport.requests == []


def test_rejects_literal_encoded_or_authorization_query_values_without_leaking() -> None:
    pat = "a/b private value"
    basic = base64.b64encode(f":{pat}".encode()).decode()
    secret_values = (
        pat,
        quote(pat, safe=""),
        quote_plus(pat),
        f"Authorization: Basic {basic}",
    )
    transport = SequencedTransport([])

    async def scenario() -> list[str]:
        messages = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = make_client(http, pat=pat)
            for value in secret_values:
                with pytest.raises(AzureReadError) as raised:
                    await client.request_json(
                        "GET",
                        "/_apis/work/processes",
                        query={"continuationToken": value},
                    )
                messages.append(str(raised.value))
        return messages

    messages = asyncio.run(scenario())

    assert transport.requests == []
    for message in messages:
        assert pat not in message
        assert quote(pat, safe="") not in message
        assert basic not in message
        assert "Authorization" not in message


def test_serializes_only_valid_wiql_query_bodies() -> None:
    transport = SequencedTransport([(200, {"workItems": []}, {})])

    async def scenario() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            return await make_client(http).request_json(
                "POST",
                "/project/_apis/wit/wiql",
                body={"query": "SELECT [System.Id] FROM WorkItems"},
            )

    assert asyncio.run(scenario()) == {"workItems": []}
    assert transport.requests[0].read() == (
        b'{"query":"SELECT [System.Id] FROM WorkItems"}'
    )
    assert transport.requests[0].headers["Content-Type"] == "application/json"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    (
        ("GET", "/_apis/work/processes", {"unexpected": "body"}),
        ("POST", "/project/_apis/wit/wiql", None),
        ("POST", "/project/_apis/wit/wiql", {}),
        ("POST", "/project/_apis/wit/wiql", {"query": ""}),
        ("POST", "/project/_apis/wit/wiql", {"query": "SELECT", "extra": True}),
        ("POST", "/project/_apis/wit/workitemsbatch", None),
        ("POST", "/project/_apis/wit/workitemsbatch", {"ids": []}),
        ("POST", "/project/_apis/wit/workitemsbatch", {"ids": [True]}),
        ("POST", "/project/_apis/wit/workitemsbatch", {"ids": [1], "extra": True}),
    ),
)
def test_rejects_bodies_outside_query_endpoint_schemas(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    transport = SequencedTransport([])

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError, match="body"):
                await make_client(http).request_json(method, path, body=body)

    asyncio.run(scenario())
    assert transport.requests == []


def test_accepts_work_item_batch_read_schema() -> None:
    transport = SequencedTransport([(200, {"count": 2, "value": []}, {})])
    body = {
        "ids": [10, 20],
        "fields": ["System.Id", "System.Title"],
        "$expand": "Relations",
        "errorPolicy": "Omit",
    }

    async def scenario() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            return await make_client(http).request_json(
                "POST", "/project/_apis/wit/workitemsbatch", body=body
            )

    assert asyncio.run(scenario()) == {"count": 2, "value": []}


def test_redirect_is_rejected_without_second_request() -> None:
    transport = SequencedTransport(
        [(302, b"redirect", {"Location": "https://evil.invalid/next"})]
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport), follow_redirects=True
        ) as http:
            with pytest.raises(AzureReadError, match="redirect"):
                await make_client(http).request_json("GET", "/_apis/work/processes")

    asyncio.run(scenario())
    assert len(transport.requests) == 1


@pytest.mark.parametrize("status", (401, 403))
def test_authentication_errors_are_never_retried(status: int) -> None:
    transport = SequencedTransport([(status, {"message": "denied"}, {})])
    sleeper = RecordingSleeper()

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError, match=f"HTTP {status}"):
                await make_client(http, sleeper=sleeper).request_json(
                    "GET", "/_apis/work/processes"
                )

    asyncio.run(scenario())
    assert len(transport.requests) == 1
    assert sleeper.delays == []


def test_429_honors_retry_after_before_retrying() -> None:
    transport = SequencedTransport(
        [
            (429, {"message": "slow down"}, {"Retry-After": "2.5"}),
            (200, {"count": 0}, {}),
        ]
    )
    sleeper = RecordingSleeper()

    async def scenario() -> tuple[dict[str, object], tuple[RequestRecord, ...]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = make_client(http, sleeper=sleeper)
            payload = await client.request_json("GET", "/_apis/work/processes")
            return payload, client.request_records

    payload, records = asyncio.run(scenario())

    assert payload == {"count": 0}
    assert sleeper.delays == [2.5]
    assert len(transport.requests) == 2
    assert records == (
        RequestRecord("GET", "/_apis/work/processes"),
        RequestRecord("GET", "/_apis/work/processes"),
    )


def test_transient_retry_is_capped_at_five_attempts() -> None:
    pat = "local-private-value"
    transport = SequencedTransport(
        [(503, {"message": f"Authorization: Basic remote {pat}"}, {})] * 5
    )
    sleeper = RecordingSleeper()

    async def scenario() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError) as raised:
                await make_client(http, pat=pat, sleeper=sleeper).request_json(
                    "GET", "/_apis/work/processes"
                )
            return str(raised.value)

    message = asyncio.run(scenario())

    assert len(transport.requests) == 5
    assert sleeper.delays == [1.0, 1.0, 1.0, 1.0]
    assert "HTTP 503" in message
    assert pat not in message
    assert "Authorization" not in message


def test_non_retryable_http_error_is_sanitized_and_capped() -> None:
    pat = "local-private-value"
    body = b"Authorization: Basic remote-private-value\n" + (b"x" * 800)
    transport = SequencedTransport([(400, body, {})])

    async def scenario() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError) as raised:
                await make_client(http, pat=pat).request_json(
                    "GET", "/_apis/work/processes"
                )
            return str(raised.value)

    message = asyncio.run(scenario())

    assert len(transport.requests) == 1
    assert "HTTP 400" in message
    assert pat not in message
    assert "remote-private-value" not in message
    assert "Authorization" not in message
    assert len(message) < 700


def test_transport_error_is_not_retried_and_is_sanitized() -> None:
    pat = "transport-private-value"
    request = httpx.Request("GET", "https://dev.azure.com/example-org")
    transport = SequencedTransport(
        [httpx.ConnectError(f"failed with {pat}", request=request)]
    )

    async def scenario() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError) as raised:
                await make_client(http, pat=pat).request_json(
                    "GET", "/_apis/work/processes"
                )
            return str(raised.value)

    message = asyncio.run(scenario())
    assert len(transport.requests) == 1
    assert pat not in message


@pytest.mark.parametrize("payload", (b"{", b"[]", b"null"))
def test_invalid_json_object_response_fails_closed(payload: bytes) -> None:
    transport = SequencedTransport([(200, payload, {})])

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            with pytest.raises(AzureReadError, match="JSON object"):
                await make_client(http).request_json("GET", "/_apis/work/processes")

    asyncio.run(scenario())


def test_shared_semaphore_gates_the_real_http_call() -> None:
    transport = SequencedTransport([(200, {"count": 0}, {})])

    async def scenario() -> dict[str, object]:
        semaphore = asyncio.Semaphore(0)
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            task = asyncio.create_task(
                make_client(http, semaphore=semaphore).request_json(
                    "GET", "/_apis/work/processes"
                )
            )
            await asyncio.sleep(0)
            assert transport.requests == []
            semaphore.release()
            return await task

    assert asyncio.run(scenario()) == {"count": 0}
