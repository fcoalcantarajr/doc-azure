"""Semantically read-only access to the Azure DevOps REST API."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Pattern
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit

import httpx


class AzureReadError(RuntimeError):
    """Raised when a request cannot be completed inside the read boundary."""


@dataclass(frozen=True)
class AllowedOperation:
    """An exact HTTP method and Azure REST path family permitted for reads."""

    method: str
    path_pattern: Pattern[str]


@dataclass(frozen=True)
class RequestRecord:
    """A sanitized receipt for one real HTTP attempt."""

    method: str
    path: str

    def __post_init__(self) -> None:
        if self.method not in {"GET", "POST"}:
            raise ValueError("request record method is not a permitted read method")
        if _normalize_path(self.path) != self.path or "?" in self.path:
            raise ValueError("request record path must be a sanitized relative path")


_SEGMENT = r"[^/?#]+"


def _route(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


ALLOWED_OPERATIONS = (
    AllowedOperation(
        "GET",
        _route(rf"^/{_SEGMENT}/_apis/wiki/wikis/{_SEGMENT}/pages/[0-9]+$"),
    ),
    AllowedOperation("GET", _route(r"^/_apis/work/processes$")),
    AllowedOperation("GET", _route(rf"^/_apis/work/processes/{_SEGMENT}$")),
    AllowedOperation(
        "GET",
        _route(
            rf"^/_apis/work/processes/{_SEGMENT}/(?:workitemtypes|behaviors)$"
        ),
    ),
    AllowedOperation(
        "GET",
        _route(
            rf"^/_apis/work/processes/{_SEGMENT}/workitemtypes/{_SEGMENT}"
            r"(?:/(?:fields|states|rules|layout))?$"
        ),
    ),
    AllowedOperation(
        "GET",
        _route(
            rf"^/_apis/work/processes/{_SEGMENT}/workitemtypesbehaviors/"
            rf"{_SEGMENT}/behaviors$"
        ),
    ),
    AllowedOperation(
        "GET",
        _route(rf"^/{_SEGMENT}/_apis/wit/wiql(?:/{_SEGMENT})?$"),
    ),
    AllowedOperation(
        "GET",
        _route(rf"^/{_SEGMENT}/_apis/wit/workitems(?:/[0-9]+)?$"),
    ),
    AllowedOperation("POST", _route(rf"^/{_SEGMENT}/_apis/wit/wiql$")),
    AllowedOperation(
        "POST", _route(rf"^/{_SEGMENT}/_apis/wit/workitemsbatch$")
    ),
)

RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
MAX_ATTEMPTS = 5
DEFAULT_RETRY_DELAY = 1.0
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "authorization",
        "proxyauthorization",
        "pat",
        "token",
        "accesstoken",
        "secret",
        "credential",
        "password",
        "apikey",
    }
)
_AUTHORIZATION_MATERIAL = re.compile(
    r"\b(?:proxy-)?authorization\s*[:=]\s*[^\r\n]*", re.IGNORECASE
)

AsyncSleeper = Callable[[float], Awaitable[None]]


def is_allowlisted_read(method: str, path: str) -> bool:
    """Return whether ``method`` and ``path`` form an approved query."""

    normalized_path = _normalize_path(path)
    if normalized_path is None:
        return False
    normalized_method = method.upper()
    return any(
        operation.method == normalized_method
        and operation.path_pattern.fullmatch(normalized_path)
        for operation in ALLOWED_OPERATIONS
    )


class AzureReadClient:
    """Reuse one async HTTP client while enforcing the semantic read boundary."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        pat: str,
        semaphore: asyncio.Semaphore,
        sleeper: AsyncSleeper = asyncio.sleep,
    ) -> None:
        if not isinstance(pat, str) or not pat:
            raise ValueError("pat must be a non-empty string")
        self._http = http
        self._base_url = _normalize_base_url(base_url)
        self._pat = pat
        self._semaphore = semaphore
        self._sleeper = sleeper
        self._request_records: list[RequestRecord] = []

    @property
    def request_records(self) -> tuple[RequestRecord, ...]:
        """Return immutable sanitized receipts for all real HTTP attempts."""

        return tuple(self._request_records)

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Return one JSON object from an explicitly approved read operation."""

        normalized_method = method.upper()
        normalized_path = _normalize_path(path)
        if normalized_path is None or not is_allowlisted_read(
            normalized_method, normalized_path
        ):
            raise AzureReadError(f"{normalized_method} request is not allowlisted")

        parameters = _validated_query(query, self._pat)
        validated_body = _validated_body(
            normalized_method, normalized_path, body, self._pat
        )
        url = f"{self._base_url}{normalized_path}"
        headers = {
            "Accept": "application/json",
            "Authorization": _basic_authorization(self._pat),
        }

        for attempt in range(1, MAX_ATTEMPTS + 1):
            record = RequestRecord(normalized_method, normalized_path)
            try:
                async with self._semaphore:
                    self._request_records.append(record)
                    response = await self._http.request(
                        normalized_method,
                        url,
                        params=parameters,
                        json=validated_body,
                        headers=headers,
                        follow_redirects=False,
                    )
            except httpx.RequestError as error:
                detail = _redact(str(error), self._pat)[:500]
                raise AzureReadError(
                    f"{normalized_method} {normalized_path} failed: {detail}"
                ) from None

            if 300 <= response.status_code < 400:
                raise AzureReadError(
                    f"{normalized_method} {normalized_path} redirect rejected "
                    f"(HTTP {response.status_code})"
                )

            if response.status_code in RETRYABLE_STATUSES and attempt < MAX_ATTEMPTS:
                await self._sleeper(_retry_delay(response.headers.get("Retry-After")))
                continue

            if response.status_code >= 400:
                detail = _redact(response.text, self._pat)[:500]
                raise AzureReadError(
                    f"{normalized_method} {normalized_path} HTTP "
                    f"{response.status_code}: {detail}"
                )

            try:
                payload = response.json()
            except (UnicodeError, ValueError):
                raise AzureReadError(
                    f"{normalized_method} {normalized_path} returned an invalid "
                    "JSON object"
                ) from None
            if not isinstance(payload, dict):
                raise AzureReadError(
                    f"{normalized_method} {normalized_path} returned an invalid "
                    "JSON object"
                )
            return payload

        raise AssertionError("retry loop exhausted without returning or raising")


def _normalize_base_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    path_segments = [segment for segment in parts.path.split("/") if segment]
    if (
        parts.scheme != "https"
        or parts.hostname != "dev.azure.com"
        or parts.netloc.lower() != "dev.azure.com"
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or len(path_segments) != 1
        or "%" in parts.path
        or path_segments[0] in {".", ".."}
    ):
        raise ValueError("base_url must identify one HTTPS dev.azure.com organization")
    return urlunsplit(("https", "dev.azure.com", f"/{path_segments[0]}", "", ""))


def _normalize_path(path: str) -> str | None:
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return None
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        return None
    if "\\" in path or "\x00" in path or "%" in path or path.endswith("/"):
        return None
    segments = path[1:].split("/")
    if not segments or any(
        not segment
        or segment in {".", ".."}
        or any(ord(character) < 32 for character in segment)
        for segment in segments
    ):
        return None
    return path


def _validated_query(
    query: Mapping[str, object] | None, pat: str
) -> tuple[tuple[str, object], ...]:
    parameters: list[tuple[str, object]] = []
    for raw_key, value in (query or {}).items():
        if not isinstance(raw_key, str) or not raw_key:
            raise AzureReadError("query contains an invalid parameter name")
        normalized_key = re.sub(r"[^a-z0-9]", "", raw_key.casefold())
        if normalized_key in _SENSITIVE_QUERY_KEYS:
            raise AzureReadError("query contains credential material")
        if raw_key.casefold() == "api-version":
            continue
        if _contains_credential_material(str(value), pat):
            raise AzureReadError("query contains credential material")
        parameters.append((raw_key, value))
    parameters.append(("api-version", "7.1"))
    return tuple(parameters)


def _validated_body(
    method: str,
    path: str,
    body: Mapping[str, object] | None,
    pat: str,
) -> dict[str, object] | None:
    if method == "GET":
        if body is not None:
            raise AzureReadError("GET body is forbidden for Azure reads")
        return None
    if not isinstance(body, Mapping):
        raise AzureReadError("POST read body must be a JSON object")

    materialized = dict(body)
    if path.casefold().endswith("/_apis/wit/wiql"):
        query = materialized.get("query")
        if set(materialized) != {"query"} or not isinstance(query, str) or not query:
            raise AzureReadError("WIQL read body must contain only a non-empty query")
    elif path.casefold().endswith("/_apis/wit/workitemsbatch"):
        _validate_batch_body(materialized)
    else:
        raise AzureReadError("POST body is forbidden outside approved query routes")

    try:
        serialized = json.dumps(materialized, separators=(",", ":"))
    except (TypeError, ValueError):
        raise AzureReadError("POST read body must be JSON serializable") from None
    if _contains_credential_material(serialized, pat):
        raise AzureReadError("POST read body contains credential material")
    return materialized


def _validate_batch_body(body: dict[str, object]) -> None:
    allowed_keys = {"ids", "fields", "$expand", "errorPolicy"}
    ids = body.get("ids")
    if not set(body).issubset(allowed_keys):
        raise AzureReadError("work-items-batch body contains an unsupported field")
    if (
        not isinstance(ids, list)
        or not ids
        or len(ids) > 200
        or any(not isinstance(item, int) or isinstance(item, bool) for item in ids)
    ):
        raise AzureReadError("work-items-batch body requires 1 to 200 integer ids")
    fields = body.get("fields")
    if fields is not None and (
        not isinstance(fields, list)
        or any(not isinstance(field, str) or not field for field in fields)
    ):
        raise AzureReadError("work-items-batch body fields must be non-empty strings")
    expand = body.get("$expand")
    if expand is not None and not isinstance(expand, str):
        raise AzureReadError("work-items-batch body $expand must be a string")
    error_policy = body.get("errorPolicy")
    if error_policy is not None and error_policy not in {"Fail", "Omit"}:
        raise AzureReadError("work-items-batch body errorPolicy is invalid")


def _basic_authorization(pat: str) -> str:
    encoded = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _retry_delay(retry_after: str | None) -> float:
    if retry_after is None:
        return DEFAULT_RETRY_DELAY
    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(retry_after)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_RETRY_DELAY


def _contains_credential_material(value: str, pat: str) -> bool:
    return _AUTHORIZATION_MATERIAL.search(value) is not None or any(
        variant in value for variant in _secret_variants(pat)
    )


def _redact(value: str, pat: str) -> str:
    redacted = value
    for variant in _secret_variants(pat):
        redacted = redacted.replace(variant, "<redacted>")
    return _AUTHORIZATION_MATERIAL.sub("<redacted>", redacted)


def _secret_variants(pat: str) -> tuple[str, ...]:
    if not pat:
        return ()
    variants = {
        pat,
        quote(pat, safe=""),
        quote_plus(pat),
        base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii"),
    }
    return tuple(sorted(variants, key=len, reverse=True))
