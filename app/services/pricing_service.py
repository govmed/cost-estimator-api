"""
Cloud pricing service.

Azure:  Live fetch from the public Azure Retail Prices API (no auth, CORS-open).
AWS:    Seed JSON bundled with the repo, refreshable via the /pricing/aws/refresh
        admin endpoint. AWS bulk pricing files are 300MB+ so live fetching isn't
        practical — the seed covers the most common instance types.

Both providers cache in-process with a 24-hour TTL.
"""

import time
import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL = 86_400  # 24 hours

# { (provider, region): (fetched_at, data) }
_cache: dict[tuple[str, str], tuple[float, dict]] = {}

SEED_DIR = Path(__file__).parent.parent.parent / "seed" / "cloud-pricing"

# ── Azure ─────────────────────────────────────────────────────────────────────

AZURE_SERVICES = [
    "Virtual Machines",
    "Azure Kubernetes Service",
    "Storage",
    "Azure Database for PostgreSQL",
    "SQL Database",
    "Bandwidth",
    "Azure Monitor",
    "Azure Blob Storage",
]

_AZURE_CATEGORY_MAP = {
    "Virtual Machines": "Compute",
    "Azure Kubernetes Service": "Compute",
    "Storage": "Storage",
    "Azure Blob Storage": "Storage",
    "Azure Database for PostgreSQL": "Database",
    "SQL Database": "Database",
    "Bandwidth": "Networking",
    "Azure Monitor": "Observability",
}


def _fetch_azure_live(region: str) -> dict:
    """Fetch from the Azure Retail Prices API. Returns our catalog shape."""
    entries: list[dict] = []
    for service in AZURE_SERVICES:
        url = "https://prices.azure.com/api/retail/prices"
        params = {
            "$filter": (
                f"serviceName eq '{service}' "
                f"and armRegionName eq '{region}' "
                "and priceType eq 'Consumption'"
            ),
            "$top": 100,
        }
        try:
            resp = httpx.get(url, params=params, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("Items", [])
            for item in items:
                sku = item.get("armSkuName") or item.get("skuName", "")
                unit_cost = item.get("retailPrice", 0)
                if unit_cost <= 0:
                    continue
                entries.append({
                    "category": _AZURE_CATEGORY_MAP.get(service, "Other"),
                    "service": item.get("productName") or service,
                    "sku": sku,
                    "pricingModel": "OnDemand",
                    "unitCost": unit_cost,
                    "unitName": item.get("unitOfMeasure", "hour"),
                    "notes": item.get("meterName"),
                })
        except Exception as exc:
            logger.warning("Azure pricing fetch failed for service %s: %s", service, exc)

    return {
        "provider": "azure",
        "region": region,
        "regionDisplayName": region,
        "currency": "USD",
        "effectiveDate": time.strftime("%Y-%m-%d"),
        "version": "live",
        "isIllustrative": len(entries) == 0,
        "environmentMultiplierDefaults": {
            "dev": 0.25, "test": 0.35, "staging": 0.5, "prod": 1.0, "dr": 0.4
        },
        "entries": entries,
    }


def get_azure_pricing(region: str = "eastus") -> dict:
    key = ("azure", region)
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]

    try:
        data = _fetch_azure_live(region)
        logger.info("Fetched %d Azure entries for %s", len(data["entries"]), region)
    except Exception as exc:
        logger.error("Azure live pricing failed, falling back to seed: %s", exc)
        data = _load_seed("azure")

    _cache[key] = (now, data)
    return data


# ── AWS ───────────────────────────────────────────────────────────────────────

def get_aws_pricing(region: str = "us-east-1") -> dict:
    key = ("aws", region)
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]

    data = _load_seed("aws")
    _cache[key] = (now, data)
    return data


def _load_seed(provider: str) -> dict:
    """Load the bundled seed catalog for a provider."""
    candidates = list(SEED_DIR.glob(f"{provider}-*.json"))
    if not candidates:
        return {
            "provider": provider, "region": "", "currency": "USD",
            "effectiveDate": "", "version": "seed", "isIllustrative": True,
            "environmentMultiplierDefaults": {"dev": 0.3, "test": 0.4, "staging": 0.6, "prod": 1.0, "dr": 0.45},
            "entries": [],
        }
    with open(candidates[0]) as f:
        return json.load(f)


def invalidate_cache(provider: str | None = None) -> None:
    """Force a refresh on next request."""
    if provider:
        keys_to_drop = [k for k in _cache if k[0] == provider]
    else:
        keys_to_drop = list(_cache.keys())
    for k in keys_to_drop:
        del _cache[k]
