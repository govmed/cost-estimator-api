import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.project_template import ProjectTemplate
from app.schemas.template import (
    TemplateCreate, TemplateSummary, TemplateInstantiateRequest, TemplateInstantiateResponse,
)
from app.schemas.validation import validate_project_blob
from app.services.audit_service import append_audit

router = APIRouter(prefix="/templates", tags=["templates"])

ORG_DEFAULT = "org_demo"


def _org(user: User) -> str:
    return getattr(user, "org_id", None) or ORG_DEFAULT


def _strip_ids(blob: dict) -> dict:
    """Remove user-specific IDs and dates from a project blob before storing as a template."""
    import copy
    t = copy.deepcopy(blob)
    proj = t.get("project", {})
    # Keep structural fields; strip identity
    for field in ("id", "ownerId", "orgId", "createdAt", "updatedAt", "activeScenarioId", "baseScenarioId"):
        proj.pop(field, None)
    for sc in t.get("scenarios", []):
        for field in ("id", "projectId", "parentScenarioId", "createdBy", "createdAt", "updatedAt"):
            sc.pop(field, None)
        for res in sc.get("resources", []):
            for f in ("id", "scenarioId"):
                res.pop(f, None)
        for cli in sc.get("cloudLineItems", []):
            for f in ("id", "scenarioId"):
                cli.pop(f, None)
        for ocli in sc.get("otherCostLineItems", []):
            for f in ("id", "scenarioId"):
                ocli.pop(f, None)
    return t


def _rehydrate(template_json: dict, name: str, client: str, currency: str, owner_id: str, org_id: str) -> dict:
    """Stamp fresh IDs and owner info onto a template blob to create a real project."""
    import copy
    blob = copy.deepcopy(template_json)
    proj = blob.get("project", {})
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    proj.update({
        "id": project_id, "name": name, "client": client,
        "baseCurrency": currency, "ownerId": owner_id, "orgId": org_id,
        "status": "draft", "createdAt": now, "updatedAt": now,
    })

    scenario_ids: list[str] = []
    for i, sc in enumerate(blob.get("scenarios", [])):
        sc_id = str(uuid.uuid4())
        scenario_ids.append(sc_id)
        sc.update({
            "id": sc_id, "projectId": project_id,
            "isBase": i == 0,
            "order": i + 1,
            "createdBy": owner_id, "createdAt": now, "updatedAt": now,
        })
        for res in sc.get("resources", []):
            res.update({"id": str(uuid.uuid4()), "scenarioId": sc_id})
        for cli in sc.get("cloudLineItems", []):
            cli.update({"id": str(uuid.uuid4()), "scenarioId": sc_id})
        for ocli in sc.get("otherCostLineItems", []):
            ocli.update({"id": str(uuid.uuid4()), "scenarioId": sc_id})

    proj["activeScenarioId"] = scenario_ids[0] if scenario_ids else ""
    proj["baseScenarioId"] = scenario_ids[0] if scenario_ids else ""
    blob["project"] = proj
    return blob, project_id


# ── List / Get ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TemplateSummary])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(ProjectTemplate)
        .filter(
            ProjectTemplate.org_id == _org(current_user),
            ProjectTemplate.is_public == True,  # noqa: E712
        )
        .order_by(ProjectTemplate.name)
        .all()
    )


@router.get("/{template_id}", response_model=TemplateSummary)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = db.get(ProjectTemplate, template_id)
    if not tmpl or tmpl.org_id != _org(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tmpl


# ── Create from project ────────────────────────────────────────────────────────

@router.post("", response_model=TemplateSummary, status_code=status.HTTP_201_CREATED)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.get(Project, data.source_project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    stripped = _strip_ids(project.state_json)
    proj_meta = stripped.get("project", {})

    tmpl = ProjectTemplate(
        id=str(uuid.uuid4()),
        org_id=_org(current_user),
        name=data.name,
        description=data.description,
        engagement_type=proj_meta.get("engagementType", "FixedFee"),
        engagement_context=proj_meta.get("engagementContext", "Modernization"),
        is_public=data.is_public,
        template_json=stripped,
        created_by=current_user.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


# ── Instantiate ────────────────────────────────────────────────────────────────

@router.post("/{template_id}/instantiate", response_model=TemplateInstantiateResponse)
def instantiate_template(
    template_id: str,
    data: TemplateInstantiateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = db.get(ProjectTemplate, template_id)
    if not tmpl or tmpl.org_id != _org(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    blob, project_id = _rehydrate(
        tmpl.template_json,
        name=data.name, client=data.client, currency=data.base_currency,
        owner_id=current_user.id, org_id=_org(current_user),
    )
    validate_project_blob(blob)

    project = Project(
        id=project_id,
        owner_id=current_user.id,
        name=data.name,
        client=data.client,
        status="draft",
        state_json=blob,
    )
    db.add(project)
    append_audit(
        db, project_id=project_id, user_id=current_user.id,
        action_kind="project.create",
        action_data={"name": data.name, "client": data.client, "from_template": tmpl.id},
    )
    db.commit()
    return TemplateInstantiateResponse(
        project_id=project_id,
        message=f"Project '{data.name}' created from template '{tmpl.name}'.",
    )


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = db.get(ProjectTemplate, template_id)
    if not tmpl or (tmpl.created_by != current_user.id and tmpl.org_id != _org(current_user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db.delete(tmpl)
    db.commit()
