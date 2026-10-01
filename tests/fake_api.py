"""
In-process stand-in for the Smithsonian Open Access API, used by tool tests.

``FakeAPI`` answers the requests the client makes (search, content, stats and
terms) from data set up by each test and records every request, so tests can run
the real tool, client and parsing code with no network access.
"""

import json
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import unquote

import httpx

SearchResponse = Union[Dict[str, Any], httpx.Response]

DEFAULT_UNIT_CODES = [
    "AAA",
    "NMAA",
    "NMAH",
    "NMAfA",
    "NMNHBOTANY",
    "NMNHPALEO",
    "NPG",
    "SAAM",
    "SIL",
]

DEFAULT_STATS = {
    "time": "2026-09",
    "total_objects": 1050,
    "metrics": {"CC0_records": 600, "CC0_records_with_CC0_media": 300},
    "units": [
        {"unit": "NMAH", "total_objects": 400, "metrics": {"CC0_records": 300}},
        {"unit": "NMNHBOTANY", "total_objects": 250, "metrics": {"CC0_records": 250}},
        {"unit": "NMNHPALEO", "total_objects": 50, "metrics": {"CC0_records": 50}},
        {"unit": "SAAM", "total_objects": 200, "metrics": {"CC0_records": 0}},
        {"unit": "AAA", "total_objects": 100, "metrics": {}},
        {"unit": "NMAA", "total_objects": 30, "metrics": {"CC0_records": 30}},
        {"unit": "FSG", "total_objects": 20, "metrics": {"CC0_records": 5}},
    ],
}


def make_row(  # pylint: disable=too-many-arguments,too-many-locals
    object_id: str,
    title: str,
    unit_code: str = "NMAH",
    *,
    record_id: Optional[str] = None,
    object_type: Optional[str] = None,
    makers: Optional[List[str]] = None,
    date: Optional[str] = None,
    on_view: bool = False,
    exhibition: Optional[str] = None,
    building: Optional[str] = None,
    images: int = 0,
    notes: Optional[List[Dict[str, str]]] = None,
    record_link: Optional[str] = None,
    guid: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a search row or /content record in the API's JSON shape.

    Args:
        object_id: Search id such as ``ld1-...``.
        title: Record title (may contain HTML).
        unit_code: Unit code of the record.
        record_id: record_ID, defaults to ``<unit>_<id suffix>``.
        object_type: Object type term.
        makers: Maker names, labelled as makers.
        date: Display date.
        on_view: Whether the record is on physical exhibit.
        exhibition: Exhibition title.
        building: Exhibition building.
        images: Number of image media items.
        notes: freetext notes entries.
        record_link: descriptiveNonRepeating.record_link.
        guid: descriptiveNonRepeating.guid.

    Returns:
        Dict[str, Any]: The row.
    """
    descriptive: Dict[str, Any] = {
        "record_ID": record_id or f"{unit_code.lower()}_{object_id.split('-')[-1]}",
        "unit_code": unit_code,
        "title": {"label": "Title", "content": title},
    }
    if record_link:
        descriptive["record_link"] = record_link
    if guid:
        descriptive["guid"] = guid
    if images:
        descriptive["online_media"] = {
            "mediaCount": images,
            "media": [
                {
                    "type": "Images",
                    "content": f"https://ids.si.edu/ids/deliveryService?id={object_id}-{i}",
                    "thumbnail": f"https://ids.si.edu/ids/deliveryService?id={object_id}-{i}&max=150",
                    "caption": f"View {i}",
                    "usage": {"access": "CC0"},
                }
                for i in range(images)
            ],
        }
    indexed: Dict[str, Any] = {}
    freetext: Dict[str, Any] = {}
    if object_type:
        indexed["object_type"] = [object_type]
    if on_view:
        indexed["onPhysicalExhibit"] = ["Yes"]
    if exhibition:
        block = {"exhibitionTitle": exhibition}
        if building:
            block["building"] = building
        indexed["exhibition"] = [block]
    if makers:
        freetext["name"] = [{"label": "maker", "content": name} for name in makers]
        freetext["name"].append({"label": "donor", "content": "Not A Maker"})
    if date:
        freetext["date"] = [{"label": "date made", "content": date}]
    if notes:
        freetext["notes"] = notes
    return {
        "id": object_id,
        "title": title,
        "unitCode": unit_code,
        "type": "edanmdm",
        "url": f"edanmdm:{descriptive['record_ID']}",
        "content": {
            "descriptiveNonRepeating": descriptive,
            "indexedStructured": indexed,
            "freetext": freetext,
        },
    }


def search_payload(rows: List[Dict[str, Any]], total: Optional[int] = None) -> Dict:
    """
    Wrap rows in a /search response body.

    Args:
        rows: Rows to return.
        total: rowCount, defaulting to the number of rows.

    Returns:
        Dict: The response body.
    """
    return {
        "status": 200,
        "responseCode": 1,
        "response": {
            "rows": rows,
            "rowCount": len(rows) if total is None else total,
            "message": "content found",
        },
    }


class FakeAPI:
    """Routes client requests to canned data and records them."""

    def __init__(self) -> None:
        self.requests: List[httpx.Request] = []
        self.search: Callable[[Dict[str, str]], SearchResponse] = (
            lambda params: search_payload([])
        )
        self.records: Dict[str, Dict[str, Any]] = {}
        self.stats: Union[Dict[str, Any], httpx.Response] = DEFAULT_STATS
        self.unit_codes: List[str] = list(DEFAULT_UNIT_CODES)

    @property
    def searches(self) -> List[Dict[str, str]]:
        """Query parameters of every /search request."""
        return [
            dict(request.url.params)
            for request in self.requests
            if request.url.path.endswith("/search")
        ]

    def paths(self) -> List[str]:
        """Endpoint paths of every request, relative to the API base."""
        return [request.url.path.split("/v1.0/", 1)[-1] for request in self.requests]

    def add_record(self, row: Dict[str, Any]) -> None:
        """Make a row available from /content under its id and EDAN URL."""
        self.records[row["id"]] = row
        self.records[row["url"]] = row

    async def handle(self, request: httpx.Request) -> httpx.Response:
        """
        Answer one request.

        Args:
            request: The outgoing request.

        Returns:
            httpx.Response: The canned response.
        """
        self.requests.append(request)
        path = request.url.path.split("/v1.0/", 1)[-1]
        if path == "search":
            return self._respond(self.search(dict(request.url.params)), request)
        if path == "stats":
            stats = self.stats
            if isinstance(stats, httpx.Response):
                return self._respond(stats, request)
            return self._respond({"status": 200, "response": stats}, request)
        if path == "terms/unit_code":
            body = {"status": 200, "response": {"terms": self.unit_codes}}
            return self._respond(body, request)
        if path.startswith("content/"):
            record = self.records.get(unquote(path[len("content/") :]))
            if record is None:
                return httpx.Response(404, json={"error": "not found"}, request=request)
            return self._respond({"status": 200, "response": record}, request)
        return httpx.Response(404, request=request)

    @staticmethod
    def _respond(body: SearchResponse, request: httpx.Request) -> httpx.Response:
        """Turn a body or response into a response bound to the request."""
        if isinstance(body, httpx.Response):
            return httpx.Response(
                body.status_code,
                headers=body.headers,
                content=body.content,
                request=request,
            )
        return httpx.Response(200, content=json.dumps(body), request=request)


def html_403() -> httpx.Response:
    """The firewall's HTML 'Request Rejected' page."""
    return httpx.Response(
        403,
        headers={"content-type": "text/html"},
        content=b"<html><head><title>Request Rejected</title></head></html>",
    )


def key_403() -> httpx.Response:
    """api.data.gov's JSON response to an invalid key."""
    return httpx.Response(
        403,
        json={"error": {"code": "API_KEY_INVALID", "message": "An invalid key"}},
    )
