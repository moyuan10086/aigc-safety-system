"""Resolve dashboard source IPs into coarse regions with a small TTL cache."""

from __future__ import annotations

import ipaddress
import json
import time
from collections import defaultdict
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

_CACHE_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, str]] = {}


def _local_region(value: str) -> str | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "未知来源"
    if address.is_loopback:
        return "本机"
    if address.is_private:
        return "内网 / 测试"
    if address.is_reserved or address.is_unspecified or address.is_multicast:
        return "保留网段"
    return None


def _lookup_public_regions(addresses: list[str]) -> dict[str, str]:
    now = time.monotonic()
    result: dict[str, str] = {}
    missing: list[str] = []
    for address in addresses:
        cached = _cache.get(address)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            result[address] = cached[1]
        else:
            missing.append(address)
    if not missing:
        return result

    payload = json.dumps([{"query": address} for address in missing]).encode("utf-8")
    request = Request(
        "http://ip-api.com/batch?fields=status,country,regionName,city,query",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "aigc-safety-dashboard/1.0"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=1.8) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        rows = []

    by_query = {str(row.get("query")): row for row in rows if isinstance(row, dict)}
    for address in missing:
        row = by_query.get(address, {})
        if row.get("status") == "success":
            parts = [str(row.get(key) or "").strip() for key in ("country", "regionName", "city")]
            region = " · ".join(part for part in parts if part) or "公网来源"
        else:
            region = "公网来源"
        result[address] = region
        _cache[address] = (now, region)
    return result


def aggregate_source_regions(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public_addresses = [
        str(source.get("client_ip") or "")
        for source in sources
        if source.get("client_ip") and _local_region(str(source["client_ip"])) is None
    ]
    public_regions = _lookup_public_regions(list(dict.fromkeys(public_addresses)))
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sources": 0, "events": 0, "alerts": 0, "blocked": 0}
    )
    for source in sources:
        address = str(source.get("client_ip") or "")
        region = _local_region(address) or public_regions.get(address, "公网来源")
        item = totals[region]
        item["sources"] += 1
        item["events"] += max(0, int(source.get("events") or 0))
        item["alerts"] += max(0, int(source.get("alerts") or 0))
        item["blocked"] += max(0, int(source.get("blocked") or 0))
    return [
        {"region": region, **counts}
        for region, counts in sorted(totals.items(), key=lambda item: (-item[1]["events"], item[0]))
    ]
