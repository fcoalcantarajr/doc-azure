"""A narrowly allowlisted Azure DevOps JSON client.

The client deliberately supports only operations that cannot persist Azure
DevOps state: selected GET endpoints plus WIQL and work-item batch reads.
"""

import base64
import json
import re
from dataclasses import dataclass
from typing import Callable, Mapping, Pattern
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class AzureReadError(RuntimeError):
    """Raised when a read request is rejected or cannot be completed safely."""


@dataclass(frozen=True)
class ReadOperation:
    """An HTTP method and the normalized Azure REST path it may use."""

    method: str
    path_pattern: Pattern[str]


@dataclass(frozen=True)
class ApiResponse:
    """A JSON object returned by an allowlisted Azure REST request."""

    payload: Mapping[str, object]
    headers: Mapping[str, str]
    url: str


READ_OPERATIONS = (
    ReadOperation("GET", re.compile(r"^/[^/]+/_apis/wiki/wikis/[^/]+/pages(?:/[0-9]+)?$")),
    ReadOperation("GET", re.compile(r"^/_apis/work/processes(?:/.*)?$")),
    ReadOperation(
        "GET",
        re.compile(r"^/[^/]+/_apis/wit/(?:wiql|workitemsbatch|workitems(?:/.*)?)$"),
    ),
    ReadOperation(
        "GET", re.compile(r"^/_apis/wit/(?:wiql|workitemsbatch|workitems(?:/.*)?)$")
    ),
)

_POST_SUFFIXES = ("/_apis/wit/wiql", "/_apis/wit/workitemsbatch")
_SENSITIVE_QUERY_KEYS = re.compile(r".*(?:authorization|auth|pat|token|secret).*", re.I)
_AUTHORIZATION_HEADER = re.compile(
    r"\b(?:proxy-)?authorization\s*:\s*[^\r\n]*",
    re.I,
)
_AUTHORIZATION_MATERIAL = re.compile(
    r"(?:^|[\r\n])\s*(?:proxy-)?authorization\s*[:=]\s*\S+",
    re.I,
)
_AUTHORIZATION_HEADER_NAME = re.compile(r"(?:proxy-)?authorization", re.I)

Transport = Callable[[Request, float], object]


class _RejectRedirectHandler(HTTPRedirectHandler):
    """Stop redirects before urllib can repeat an authenticated request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "redirects are not permitted", headers, fp)


def _default_transport(request: Request, timeout: float) -> object:
    """Open one request only; redirects cannot copy Authorization elsewhere."""

    return build_opener(_RejectRedirectHandler).open(request, timeout=timeout)


def is_allowlisted_read(method: str, path: str) -> bool:
    """Return whether a method-path pair is a semantically read-only route."""

    normalized_path = _normalize_path(path)
    if normalized_path is None:
        return False

    normalized_method = method.upper()
    if normalized_method == "POST":
        return normalized_path.endswith(_POST_SUFFIXES)
    return any(
        operation.method == normalized_method
        and operation.path_pattern.fullmatch(normalized_path)
        for operation in READ_OPERATIONS
    )


class AzureClient:
    """Execute only Azure REST reads through an injectable transport."""

    def __init__(
        self,
        base_url: str,
        pat: str,
        transport: Transport = _default_transport,
        *,
        timeout: float = 30,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._pat = pat
        self._transport = transport
        self._timeout = timeout

    def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> ApiResponse:
        """Request a JSON object from a route permitted by the read allowlist."""

        normalized_path = _normalize_path(path)
        normalized_method = method.upper()
        if normalized_path is None or not is_allowlisted_read(method, path):
            raise AzureReadError(f"{normalized_method} request is not allowlisted")
        if body is not None and normalized_method != "POST":
            raise AzureReadError("request bodies are only allowed for POST read queries")
        _validate_query(query, self._pat)

        try:
            request_url = self._build_url(normalized_path, query)
            safe_url = _sanitize_url(request_url, self._pat)
            request = self._build_request(normalized_method, request_url, body)
        except (TypeError, UnicodeError, ValueError):
            raise AzureReadError(
                f"{normalized_method} request could not be constructed safely"
            ) from None

        try:
            response = self._transport(request, self._timeout)
            payload = _decode_json_object(response.read())
        except HTTPError as error:
            response_message = _read_http_error(error)
            raise AzureReadError(
                f"{normalized_method} {safe_url} HTTP {error.code}: "
                f"{_redact(response_message, self._pat)[:500]}"
            ) from None
        except (URLError, OSError, ValueError, json.JSONDecodeError) as error:
            message = getattr(error, "reason", str(error))
            raise AzureReadError(
                f"{normalized_method} {safe_url} failed: "
                f"{_redact(str(message), self._pat)[:500]}"
            ) from None

        return ApiResponse(
            payload=payload,
            headers=_safe_response_headers(response.headers),
            url=safe_url,
        )

    def _build_url(
        self, normalized_path: str, query: Mapping[str, str] | None
    ) -> str:
        parameters = {
            key: value
            for key, value in (query or {}).items()
            if key.lower() != "api-version"
        }
        parameters["api-version"] = "7.1"
        encoded_path = quote(normalized_path, safe="/-._~")
        return f"{self._base_url}{encoded_path}?{urlencode(parameters)}"

    def _build_request(
        self, method: str, url: str, body: Mapping[str, object] | None
    ) -> Request:
        headers = {
            "Accept": "application/json",
            "Authorization": _basic_authorization(self._pat),
        }
        encoded_body = None
        if body is not None:
            encoded_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return Request(url, data=encoded_body, headers=headers, method=method)


def _normalize_base_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    if (
        parts.scheme != "https"
        or not parts.netloc
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("base_url must be an HTTPS origin with an optional path")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def _normalize_path(path: str) -> str | None:
    """Return a canonical relative path, rejecting URL injection primitives."""

    parts = urlsplit(path)
    if (
        not path
        or parts.scheme
        or parts.netloc
        or parts.query
        or parts.fragment
        or not parts.path.startswith("/")
    ):
        return None

    decoded_path = unquote(parts.path)
    if "\\" in decoded_path or "\x00" in decoded_path or "%" in decoded_path:
        return None

    segments: list[str] = []
    for segment in decoded_path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not segments:
                return None
            segments.pop()
        else:
            segments.append(segment)
    return "/" + "/".join(segments)


def _basic_authorization(pat: str) -> str:
    encoded = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _validate_query(query: Mapping[str, str] | None, pat: str) -> None:
    for value in (query or {}).values():
        query_value = str(value)
        if _contains_pat(query_value, pat) or _AUTHORIZATION_MATERIAL.search(
            query_value
        ):
            raise AzureReadError("query contains credential material")


def _decode_json_object(raw_payload: bytes) -> Mapping[str, object]:
    payload = json.loads(raw_payload.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Azure response must be a JSON object")
    return payload


def _read_http_error(error: HTTPError) -> str:
    if error.fp is None:
        return error.reason if isinstance(error.reason, str) else str(error.reason)
    try:
        raw_body = error.read(500)
    except (OSError, TypeError, ValueError):
        return "response body unavailable"
    if isinstance(raw_body, bytes):
        return raw_body.decode("utf-8", errors="replace")
    return str(raw_body)[:500]


def _safe_response_headers(headers: object) -> Mapping[str, str]:
    items = getattr(headers, "items", lambda: ())()
    return {
        str(name): str(value)
        for name, value in items
        if not _AUTHORIZATION_HEADER_NAME.fullmatch(str(name))
    }


def _sanitize_url(url: str, pat: str) -> str:
    parts = urlsplit(url)
    safe_parameters = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        safe_parameters.append(
            (key, "<redacted>" if _SENSITIVE_QUERY_KEYS.fullmatch(key) else value)
        )
    safe_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(safe_parameters), "")
    )
    return _redact(safe_url, pat)


def _redact(value: str, pat: str) -> str:
    redacted = value
    for secret_variant in _pat_variants(pat):
        redacted = redacted.replace(secret_variant, "<redacted>")
    return _AUTHORIZATION_HEADER.sub("<redacted>", redacted)


def _contains_pat(value: str, pat: str) -> bool:
    return any(secret_variant in value for secret_variant in _pat_variants(pat))


def _pat_variants(pat: str) -> tuple[str, ...]:
    if not pat:
        return ()
    variants = {pat, quote(pat, safe=""), urlencode({"value": pat})[6:]}
    return tuple(sorted(variants, key=len, reverse=True))
