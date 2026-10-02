"""
HTTP client for the Smithsonian Open Access API, served through api.data.gov.

The client sends searches built by ``query`` and turns records into models with
``parsing``. API failures become ``APIError`` with a short error code. The API
key is sent only in the ``X-Api-Key`` header so it never appears in request URLs
or logs.
"""

import json
import logging
from typing import Any, ClassVar, Dict, List, Optional
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from .config import Config
from .constants import KNOWN_UNIT_CODES, NMNH_AGGREGATE_CODE, UNIT_INFO
from .models import (
    APIError,
    CollectionSearchFilter,
    SearchResult,
    SmithsonianObject,
    SmithsonianUnit,
)
from .parsing import as_dict, as_list, parse_object_data, safe_int
from .query import build_search_query
from .utils import SingleFlight

logger = logging.getLogger(__name__)

BASE_URL = "https://api.si.edu/openaccess/api/v1.0/"

# The API accepts rows in 0..1000; larger values silently return 10 rows.
MAX_ROWS = 1000

DEFAULT_TIMEOUT_SECONDS = 30.0


def _object_id_candidates(object_id: str) -> List[str]:
    """
    ID formats to try with /content, most likely first.

    ``/content`` accepts search IDs (``ld1-...``) and EDAN URLs
    (``edanmdm:nmah_1448973``). Legacy dash IDs and bare record IDs are retried
    as EDAN URLs.
    """
    candidates = [object_id]
    lower = object_id.lower()
    if lower.startswith("edanmdm-"):
        candidates.append(f"edanmdm:{object_id[len('edanmdm-'):]}")
    elif not lower.startswith(("edanmdm:", "ld1-")):
        candidates.append(f"edanmdm:{object_id}")
    return candidates


class SmithsonianAPIClient:
    """
    Client for interacting with the Smithsonian Open Access API.

    This client handles authentication, query building and data transformation
    for the Smithsonian collections available through api.data.gov.
    """

    # Unit codes from /terms/unit_code, shared by all clients in the process,
    # and the request that fetches them, shared by concurrent callers.
    _unit_codes_cache: ClassVar[Optional[List[str]]] = None
    _unit_codes_flight: ClassVar[SingleFlight[List[str]]] = SingleFlight()

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        """
        Initialize the API client.

        Args:
            api_key: API key. If not provided, it will be read from `Config.API_KEY`.
            base_url: API base URL.
            timeout: Request timeout in seconds.
            transport: Optional httpx transport, e.g. a mock transport for tests.

        Raises:
            ValueError: If no API key is available.
        """
        key = api_key or Config.API_KEY
        if not key or not key.strip():
            raise ValueError(
                "API key is required. Please provide one or set it in the config."
            )
        self.api_key = key.strip()
        self.base_url = base_url
        self.timeout = timeout
        self._transport = transport
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "SmithsonianAPIClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize the HTTP session. The API key is sent only as a header."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                headers={
                    "X-Api-Key": self.api_key,
                    "User-Agent": Config.USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                transport=self._transport,
            )

    async def disconnect(self) -> None:
        """Close the HTTP session."""
        if self.session:
            session, self.session = self.session, None
            await session.aclose()

    def _build_search_params(self, filters: CollectionSearchFilter) -> Dict[str, Any]:
        """
        Build query parameters for search requests.

        Args:
            filters: Search filter parameters

        Returns:
            Dictionary with ``q``, ``start``, ``rows`` (clamped to 0..1000) and,
            when a non-default order is requested, ``sort``
        """
        params: Dict[str, Any] = {
            "q": build_search_query(filters),
            "start": max(0, int(filters.offset or 0)),
            "rows": max(0, min(int(filters.limit or 0), MAX_ROWS)),
        }
        if filters.sort and filters.sort != "relevancy":
            params["sort"] = filters.sort
        if filters.row_group == "archives":
            params["row_group"] = "archives"
        return params

    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request to the API.

        Args:
            endpoint: API endpoint path
            params: Query parameters (an ``api_key`` entry is ignored)

        Returns:
            JSON response data

        Raises:
            APIError: If the request fails
        """
        if not self.session:
            await self.connect()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        # The key travels in the X-Api-Key header only, never in the URL.
        request_params = {k: v for k, v in (params or {}).items() if k != "api_key"}

        try:
            # Log only the known search fields, never the parameter dict as a whole
            logger.debug(
                "GET %s q=%s start=%s rows=%s",
                url,
                request_params.get("q"),
                request_params.get("start"),
                request_params.get("rows"),
            )

            if self.session is None:
                raise APIError(
                    error="session_error",
                    message="Failed to initialize HTTP session",
                    details=None,
                    status_code=None,
                )

            response = await self.session.get(url, params=request_params)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise APIError(
                    error="invalid_response",
                    message=f"Unexpected response type from {url}",
                    status_code=response.status_code,
                    details={"url": url},
                )
            return data

        except APIError:
            raise
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 404:
                logger.debug("Resource not found: %s", url)
                raise APIError(
                    error="not_found",
                    message="Resource not found",
                    status_code=status_code,
                    details={"url": url},
                ) from e
            if status_code == 429:
                error_msg = f"Rate limit temporarily exceeded for {url}"
                logger.error(error_msg)
                raise APIError(
                    error="rate_limit_exceeded",
                    message=error_msg,
                    status_code=status_code,
                    details={"url": url},
                ) from e
            if status_code == 403:
                raise self._forbidden_error(e.response, url) from e
            error_msg = f"HTTP {status_code} error for {url}"
            logger.error(error_msg)
            raise APIError(
                error="http_error",
                message=error_msg,
                status_code=status_code,
                details={"url": url},
            ) from e
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"Invalid JSON from {url}"
            logger.error(error_msg)
            raise APIError(
                error="invalid_response",
                message=error_msg,
                status_code=None,
                details={"url": url},
            ) from e
        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Request failed: {type(e).__name__}: {e}"
            logger.error(error_msg)
            raise APIError(
                error="request_error",
                message=error_msg,
                status_code=None,
                details={"exception_type": type(e).__name__},
            ) from e

    @staticmethod
    def _forbidden_error(response: httpx.Response, url: str) -> APIError:
        """
        Classify an HTTP 403 response.

        api.data.gov rejects a missing or invalid key with a JSON body such as
        ``{"error": {"code": "API_KEY_INVALID", ...}}``. A firewall in front of the
        API answers queries that look like SQL, script or path injection
        (``' OR 1=1 --``, ``<script>``, ``../``) with an HTML "Request Rejected"
        page instead, which says nothing about the key.

        Args:
            response: The 403 response.
            url: Request URL without parameters, for the error details.

        Returns:
            APIError: ``query_rejected`` for the firewall page, ``api_key_rejected``
            for key errors, ``http_error`` otherwise.
        """
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            message = (
                "The Smithsonian API firewall rejected the request (HTTP 403). "
                "This is not an API key problem: rephrase the query without "
                "text that looks like SQL, HTML/script tags or file paths."
            )
            logger.warning("Request rejected by the API firewall: %s", url)
            return APIError(
                error="query_rejected",
                message=message,
                status_code=403,
                details={"url": url},
            )
        error = as_dict(body.get("error"))
        code = error.get("code") if isinstance(error.get("code"), str) else None
        if code and code.startswith("API_KEY"):
            message = f"The API key was rejected ({code}): {error.get('message')}"
            logger.error(message)
            return APIError(
                error="api_key_rejected",
                message=message,
                status_code=403,
                details={"url": url, "code": code},
            )
        message = f"HTTP 403 error for {url}"
        logger.error(message)
        return APIError(
            error="http_error",
            message=message,
            status_code=403,
            details={"url": url},
        )

    async def count_matches(self, query: str, row_group: Optional[str] = None) -> int:
        """
        Count records matching a raw ``q`` query without fetching rows.

        Args:
            query: Query string in API syntax.
            row_group: "archives" to count archive records instead of objects.

        Returns:
            int: Number of matching records.

        Raises:
            APIError: If the request fails.
        """
        params: Dict[str, Any] = {"q": query, "start": 0, "rows": 0}
        if row_group == "archives":
            params["row_group"] = "archives"
        data = await self._make_request("search", params)
        return int(as_dict(data.get("response")).get("rowCount") or 0)

    async def search_collections(self, filters: CollectionSearchFilter) -> SearchResult:
        """
        Search the Smithsonian collections.

        Rows that cannot be parsed are logged and skipped. ``next_offset`` is based
        on the rows the API returned, so skipped rows are not fetched again.

        Args:
            filters: Search parameters and filters

        Returns:
            Search results with objects and pagination info

        Raises:
            APIError: If the request fails.
        """
        params = self._build_search_params(filters)
        response_data = await self._make_request("search", params)
        response = as_dict(response_data.get("response"))
        rows = as_list(response.get("rows"))

        objects = []
        for row in rows:
            try:
                objects.append(parse_object_data(row))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                row_id = row.get("id") if isinstance(row, dict) else None
                logger.warning(
                    "Skipping search row %s that failed to parse: %s", row_id, exc
                )

        total_count = safe_int(response.get("rowCount")) or 0
        start = params["start"]
        next_start = start + len(rows)
        has_more = bool(rows) and next_start < total_count

        return SearchResult(
            objects=objects,
            total_count=total_count,
            returned_count=len(objects),
            offset=start,
            has_more=has_more,
            next_offset=next_start if has_more else None,
        )

    async def get_object_by_id(self, object_id: str) -> Optional[SmithsonianObject]:
        """
        Get detailed information about a specific object.

        The ID is tried as given first. Legacy ``edanmdm-`` IDs and bare record
        IDs (``nmah_1448973``) are then retried as EDAN URLs
        (``edanmdm:nmah_1448973``). The first successful lookup is returned.

        Args:
            object_id: Object identifier (search ID, EDAN URL or record ID)

        Returns:
            Object details or None if not found

        Raises:
            ValueError: If object_id is empty.
            APIError: For errors other than not-found.
        """
        if not object_id or not str(object_id).strip():
            raise ValueError("object_id cannot be empty")
        object_id = str(object_id).strip()

        candidates = _object_id_candidates(object_id)
        for attempt_id in candidates:
            endpoint = f"/content/{quote(attempt_id, safe=':-_.~')}"
            try:
                logger.debug("Trying object ID format: %s", attempt_id)
                response_data = await self._make_request(endpoint)
            except APIError as e:
                if e.error == "not_found" or e.status_code == 404:
                    logger.debug("Object not found with ID format %s", attempt_id)
                    continue
                logger.error("API error trying ID format %s: %s", attempt_id, e)
                raise

            record = response_data.get("response")
            if not isinstance(record, dict) or not record:
                logger.warning("Malformed response for object %s", attempt_id)
                continue
            try:
                result = parse_object_data(record)
            except (ValueError, ValidationError) as exc:
                raise APIError(
                    error="invalid_response",
                    message=f"Could not parse object {attempt_id}: {exc}",
                    status_code=None,
                    details={"object_id": attempt_id},
                ) from exc
            logger.debug("Retrieved object using ID format: %s", attempt_id)
            return result

        logger.info(
            "Object %s not found (tried %d ID formats)", object_id, len(candidates)
        )
        return None

    async def get_unit_codes(self, refresh: bool = False) -> List[str]:
        """
        Get the unit codes used by the search index.

        Codes come from ``GET /terms/unit_code`` and are cached for the life of the
        process; concurrent callers share one request. The built-in list is used
        if the endpoint fails.

        Args:
            refresh: Fetch again even if cached.

        Returns:
            List[str]: Unit codes such as ``NMAH`` and ``NMNHPALEO``.

        Raises:
            APIError: If the API key is rejected; other failures use the list.
        """
        cached = SmithsonianAPIClient._unit_codes_cache
        if cached is not None and not refresh:
            return list(cached)
        codes = await SmithsonianAPIClient._unit_codes_flight.run(
            "unit_codes", self._fetch_unit_codes
        )
        return list(codes)

    async def _fetch_unit_codes(self) -> List[str]:
        """
        Request the unit codes and cache them.

        Returns:
            List[str]: The codes, or the built-in list if the endpoint fails.

        Raises:
            APIError: If the API key is rejected.
        """
        try:
            data = await self._make_request("terms/unit_code")
        except APIError as exc:
            if exc.error == "api_key_rejected":
                raise
            logger.warning("Could not fetch unit codes, using built-in list: %s", exc)
            return list(KNOWN_UNIT_CODES)
        terms = [
            term.strip()
            for term in as_list(as_dict(data.get("response")).get("terms"))
            if isinstance(term, str) and term.strip()
        ]
        if not terms:
            return list(KNOWN_UNIT_CODES)
        SmithsonianAPIClient._unit_codes_cache = terms
        return list(terms)

    @classmethod
    def clear_unit_code_cache(cls) -> None:
        """Forget cached unit codes so the next call fetches them again."""
        cls._unit_codes_cache = None
        cls._unit_codes_flight.clear()

    @staticmethod
    def _unit_from_code(code: str) -> SmithsonianUnit:
        """Build a SmithsonianUnit from the static unit information."""
        return SmithsonianUnit(
            code=code, name=UNIT_INFO.get(code, {}).get("name", code)
        )

    async def get_units(self) -> List[SmithsonianUnit]:
        """
        Get the Smithsonian units/museums available as search filters.

        Includes every code from ``/terms/unit_code`` plus ``NMNH``, which covers
        all National Museum of Natural History departments.

        Returns:
            List of Smithsonian units
        """
        codes = await self.get_unit_codes()
        units = [self._unit_from_code(code) for code in codes]
        if NMNH_AGGREGATE_CODE not in codes:
            position = next(
                (
                    i
                    for i, code in enumerate(codes)
                    if code.startswith(NMNH_AGGREGATE_CODE)
                ),
                len(units),
            )
            units.insert(position, self._unit_from_code(NMNH_AGGREGATE_CODE))
        return units


# Utility function for creating client instance
async def create_client(api_key: Optional[str] = None) -> SmithsonianAPIClient:
    """
    Create and initialize an API client.

    Args:
        api_key: Optional API key. If not provided, it will be read from `Config.API_KEY`.

    Returns:
        Initialized API client
    """
    client = SmithsonianAPIClient(api_key)
    await client.connect()
    return client
