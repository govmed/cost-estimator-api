"""
Structural validation for project state_json blobs.

Validates that the blob has the required top-level shape before storing it.
We don't re-implement the full TypeScript type system in Python — instead we
check the invariants that, if violated, would cause the engine to crash or
produce nonsensical output:

  1. project.id is a non-empty string
  2. project.baseCurrency is a known currency code
  3. project.targetMarginPct / contingencyPct / managementReservePct are numbers in [0, 100]
  4. scenarios is a list, each item has id + projectId matching project.id
  5. Each scenario has resources / cloudLineItems / otherCostLineItems as lists
  6. Exactly one scenario has isBase = true

These checks run on every project save and prevent data corruption from
bad imports, manual edits, or bugs in client code.
"""

from typing import Any
from fastapi import HTTPException, status

VALID_CURRENCIES = {"USD", "EUR", "GBP", "INR", "CAD", "AUD", "BRL"}
VALID_STATUSES = {"draft", "underReview", "approved", "archived"}
VALID_ENGAGEMENT_TYPES = {"FixedFee", "TimeAndMaterials", "CappedTM", "Milestone", "OutcomeBased"}


def _err(msg: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Project validation failed: {msg}",
    )


def validate_project_blob(state_json: dict[str, Any]) -> None:
    """Raise HTTP 422 if the project blob fails structural validation."""
    project = state_json.get("project")
    scenarios = state_json.get("scenarios")

    if not isinstance(project, dict):
        _err("'project' key must be an object")
    if not isinstance(scenarios, list):
        _err("'scenarios' key must be an array")

    # Project fields
    if not project.get("id") or not isinstance(project["id"], str):
        _err("project.id must be a non-empty string")

    currency = project.get("baseCurrency")
    if currency not in VALID_CURRENCIES:
        _err(f"project.baseCurrency must be one of {sorted(VALID_CURRENCIES)}")

    for pct_field in ("targetMarginPct", "contingencyPct", "managementReservePct"):
        val = project.get(pct_field)
        if val is None:
            _err(f"project.{pct_field} is required")
        if not isinstance(val, (int, float)) or not (0 <= val <= 100):
            _err(f"project.{pct_field} must be a number in [0, 100]")

    project_id = project["id"]

    # Scenarios
    if len(scenarios) == 0:
        _err("scenarios must contain at least one entry")

    base_count = 0
    seen_ids: set[str] = set()

    for i, sc in enumerate(scenarios):
        if not isinstance(sc, dict):
            _err(f"scenarios[{i}] must be an object")

        sc_id = sc.get("id")
        if not sc_id or not isinstance(sc_id, str):
            _err(f"scenarios[{i}].id must be a non-empty string")

        if sc_id in seen_ids:
            _err(f"duplicate scenario id: {sc_id!r}")
        seen_ids.add(sc_id)

        if sc.get("projectId") != project_id:
            _err(
                f"scenarios[{i}].projectId ({sc.get('projectId')!r}) "
                f"does not match project.id ({project_id!r})"
            )

        for list_field in ("resources", "cloudLineItems", "otherCostLineItems"):
            if not isinstance(sc.get(list_field), list):
                _err(f"scenarios[{i}].{list_field} must be an array")

        if sc.get("isBase") is True:
            base_count += 1

    if base_count == 0:
        _err("exactly one scenario must have isBase = true (found 0)")
    if base_count > 1:
        _err(f"exactly one scenario must have isBase = true (found {base_count})")
