"""Gate G1.3.2 bounded operator-document transport.

This module materializes the document boundary already frozen by Gate G1.3.
It reads one selected document at a time into RAM, hashes the complete bounded
artifact before parsing, emits only a descriptive receipt, and retains no body.
It does not contact receiver status routes or acquire RF.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from experiments.live_instrument.models import strict_json_value

from .g1_3_search import G13SearchPlan


DESCRIPTOR_MARKERS = (
    "api",
    "json",
    "xml",
    "yaml",
    "receiver",
    "directory",
    "automation",
    "machine-readable",
    "authentication",
    "ttl",
    "cache-control",
    "status",
    "kiwisdr",
    "openwebrx",
    "websdr",
)
LINK_HINTS = (
    "api",
    ".json",
    ".xml",
    ".yaml",
    "directory",
    "receiver",
    "list",
    "map",
    "/public",
)


class DocumentFetchState(str, Enum):
    SUCCESS = "SUCCESS"
    DESCRIPTION_ERROR = "DESCRIPTION_ERROR"


@dataclass(frozen=True, slots=True)
class G132DocumentPlan:
    parent_plan_hash: str
    selected_document_urls: tuple[str, ...]
    maximum_document_bytes: int = 1_048_576
    request_timeout_s: float = 15.0
    retry_count: int = 0
    maximum_documents_per_candidate: int = 2
    maximum_descriptor_links: int = 20
    status_requests_allowed: bool = False
    rf_requests_allowed: bool = False

    @classmethod
    def for_selected_urls(
        cls, selected_document_urls: Sequence[str]
    ) -> "G132DocumentPlan":
        return cls(
            parent_plan_hash=G13SearchPlan().plan_hash,
            selected_document_urls=tuple(selected_document_urls),
        )

    def validate(self) -> None:
        parent = G13SearchPlan()
        parent.validate()
        if self.parent_plan_hash != parent.plan_hash:
            raise ValueError("Gate G1.3.2 must bind the frozen G1.3 plan")
        if not 1 <= len(self.selected_document_urls) <= parent.maximum_candidate_mechanisms:
            raise ValueError("selected document count is outside the frozen bound")
        if len(set(self.selected_document_urls)) != len(self.selected_document_urls):
            raise ValueError("selected document URLs must be unique")
        for url in self.selected_document_urls:
            _validate_public_document_url(url)
        if self.maximum_document_bytes != parent.maximum_document_bytes:
            raise ValueError("document byte limit must remain frozen")
        if self.request_timeout_s != parent.request_timeout_s:
            raise ValueError("document timeout must remain frozen")
        if self.retry_count != parent.retry_count:
            raise ValueError("document retry count must remain frozen")
        if self.maximum_documents_per_candidate != parent.maximum_documents_per_candidate:
            raise ValueError("per-candidate document bound must remain frozen")
        if self.maximum_descriptor_links != 20:
            raise ValueError("descriptor link bound is frozen at twenty")
        if self.status_requests_allowed or self.rf_requests_allowed:
            raise ValueError("document audit cannot request receiver status or RF")

    @property
    def plan_hash(self) -> str:
        self.validate()
        return _hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class OperatorDocumentReceipt:
    requested_url: str
    final_url: str | None
    state: str
    artifact_sha256: str | None
    artifact_byte_count: int
    hashed_before_parsing: bool
    http_status: int | None
    content_type: str | None
    cache_control: str | None
    etag: str | None
    last_modified: str | None
    title: str | None
    present_markers: tuple[str, ...]
    candidate_links: tuple[str, ...]
    detail: str
    request_count: int
    retry_count: int
    raw_document_persisted: bool
    status_request_count: int
    rf_activity: str

    def strict_json(self) -> str:
        return json.dumps(
            strict_json_value(asdict(self)),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class _DescriptorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self.title_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() == "title":
            self._in_title = True
        if tag.casefold() != "a":
            return
        for name, value in attrs:
            if name.casefold() == "href" and value:
                self.links.append(value)
                return

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def describe_document_bytes(
    plan: G132DocumentPlan,
    *,
    requested_url: str,
    final_url: str,
    status: int,
    headers: Mapping[str, str],
    body: bytes,
) -> OperatorDocumentReceipt:
    """Hash a complete bounded artifact, then derive a minimal descriptor."""

    plan.validate()
    if requested_url not in plan.selected_document_urls:
        raise ValueError("document is not in the frozen selected URL set")
    _validate_public_document_url(final_url)
    if len(body) > plan.maximum_document_bytes:
        raise ValueError("document exceeds the frozen 1 MiB bound")

    artifact_hash = sha256(body).hexdigest()
    normalized_headers = {str(key).casefold(): str(value) for key, value in headers.items()}
    content_type = normalized_headers.get("content-type")
    encoding = _charset(content_type)
    text = body.decode(encoding, errors="replace")
    lowered = text.casefold()
    markers = tuple(marker for marker in DESCRIPTOR_MARKERS if marker in lowered)
    title, links = _html_descriptor(
        text,
        base_url=final_url,
        maximum_links=plan.maximum_descriptor_links,
    )
    receipt = OperatorDocumentReceipt(
        requested_url=requested_url,
        final_url=final_url,
        state=DocumentFetchState.SUCCESS.value,
        artifact_sha256=artifact_hash,
        artifact_byte_count=len(body),
        hashed_before_parsing=True,
        http_status=status,
        content_type=content_type,
        cache_control=normalized_headers.get("cache-control"),
        etag=normalized_headers.get("etag"),
        last_modified=normalized_headers.get("last-modified"),
        title=title,
        present_markers=markers,
        candidate_links=links,
        detail="bounded document hashed before descriptor extraction",
        request_count=1,
        retry_count=0,
        raw_document_persisted=False,
        status_request_count=0,
        rf_activity="ZERO",
    )
    receipt.strict_json()
    return receipt


def fetch_selected_documents(
    plan: G132DocumentPlan,
) -> tuple[OperatorDocumentReceipt, ...]:
    """Fetch every frozen URL once, preserving errors as description errors."""

    plan.validate()
    return tuple(_fetch_one(plan, url) for url in plan.selected_document_urls)


def _fetch_one(plan: G132DocumentPlan, url: str) -> OperatorDocumentReceipt:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.1",
            "User-Agent": "Satellite-RF-Observatory-G1.3.2/1.0 descriptive-audit",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=plan.request_timeout_s) as response:
            body = response.read(plan.maximum_document_bytes + 1)
            if len(body) > plan.maximum_document_bytes:
                return _error_receipt(url, "document exceeded the frozen 1 MiB bound")
            return describe_document_bytes(
                plan,
                requested_url=url,
                final_url=response.geturl(),
                status=response.status,
                headers=dict(response.headers.items()),
                body=body,
            )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        return _error_receipt(url, f"{type(error).__name__}: {error}")


def _error_receipt(url: str, detail: str) -> OperatorDocumentReceipt:
    receipt = OperatorDocumentReceipt(
        requested_url=url,
        final_url=None,
        state=DocumentFetchState.DESCRIPTION_ERROR.value,
        artifact_sha256=None,
        artifact_byte_count=0,
        hashed_before_parsing=False,
        http_status=None,
        content_type=None,
        cache_control=None,
        etag=None,
        last_modified=None,
        title=None,
        present_markers=(),
        candidate_links=(),
        detail=detail,
        request_count=1,
        retry_count=0,
        raw_document_persisted=False,
        status_request_count=0,
        rf_activity="ZERO",
    )
    receipt.strict_json()
    return receipt


def _html_descriptor(
    text: str, *, base_url: str, maximum_links: int
) -> tuple[str | None, tuple[str, ...]]:
    parser = _DescriptorParser()
    parser.feed(text)
    title = _collapse_space(" ".join(parser.title_parts)) or None
    selected: list[str] = []
    seen: set[str] = set()
    for href in parser.links:
        absolute = _normalized_link(urljoin(base_url, href))
        if absolute is None or absolute in seen:
            continue
        lowered = absolute.casefold()
        if not any(hint in lowered for hint in LINK_HINTS):
            continue
        seen.add(absolute)
        selected.append(absolute)
        if len(selected) == maximum_links:
            break
    return title, tuple(selected)


def _normalized_link(url: str) -> str | None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _validate_public_document_url(url: str) -> None:
    if _normalized_link(url) != url:
        raise ValueError("document URL must be canonical public HTTP(S) without fragment")


def _charset(content_type: str | None) -> str:
    if content_type is None:
        return "utf-8"
    match = re.search(r"charset\s*=\s*['\"]?([^;'\"\s]+)", content_type, re.I)
    return match.group(1) if match else "utf-8"


def _collapse_space(value: str) -> str:
    return " ".join(value.split())


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        strict_json_value(value),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
