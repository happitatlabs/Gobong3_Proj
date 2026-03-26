from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from mellow_chat_runtime import app_state
from mellow_chat_runtime.core.domain_lookup_store import get_domain_store
from mellow_chat_runtime.infra.database import ChatSession, get_db, get_or_create_session, get_or_create_user

router = APIRouter(tags=["Models"])


class ModelDescriptor(BaseModel):
    provider: str = Field(..., min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=120)
    mode: Optional[str] = Field(default=None, max_length=50)
    catalog_id: Optional[str] = Field(default=None, max_length=120)
    label: Optional[str] = None
    role_tags: List[str] = Field(default_factory=list)
    status: Optional[Literal["active", "deprecated"]] = None
    source: Optional[Literal["explicit_request", "catalog", "session", "system_default"]] = None


class ModelSelectionPayload(BaseModel):
    provider: Optional[str] = Field(default=None, max_length=80)
    model: Optional[str] = Field(default=None, max_length=120)
    mode: Optional[str] = Field(default=None, max_length=50)
    catalog_id: Optional[str] = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_payload(self) -> "ModelSelectionPayload":
        has_explicit = bool((self.provider or "").strip() and (self.model or "").strip())
        has_catalog = bool((self.catalog_id or "").strip())
        if not has_explicit and not has_catalog:
            raise ValueError("Either provider/model or catalog_id is required")
        if bool((self.provider or "").strip()) ^ bool((self.model or "").strip()):
            raise ValueError("provider and model must be provided together")
        return self


class SelectModelRequest(BaseModel):
    session_id: Optional[int] = None
    selection: ModelSelectionPayload


class SelectModelResponse(BaseModel):
    session_id: int
    selected: ModelDescriptor
    source: str = "session"


class ModelCatalogResponseItem(BaseModel):
    id: str
    label: str
    provider: str
    model: str
    default_mode: str
    role_tags: List[str] = Field(default_factory=list)
    audiences: List[Literal["user", "admin"]] = Field(default_factory=list)
    status: Literal["active", "deprecated"]
    description: str = ""


def _user_from_header(x_user: Optional[str]) -> str:
    return (x_user or "default_user").strip() or "default_user"


def _store():
    settings = app_state.settings
    data_path = getattr(settings, "domain_data_file", None) if settings else None
    return get_domain_store(data_path=data_path)


def _clean_tags(values: object) -> List[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _catalog_entry_or_400(catalog_id: str) -> dict:
    item = _store().get_model_catalog_item(catalog_id)
    if not item:
        raise HTTPException(status_code=400, detail="Model catalog entry not found")
    return item


def _build_descriptor(
    *,
    provider: str,
    model: str,
    mode: Optional[str],
    source: str,
    catalog_id: Optional[str] = None,
    catalog_entry: Optional[dict] = None,
) -> ModelDescriptor:
    catalog_entry = catalog_entry or {}
    return ModelDescriptor(
        provider=provider,
        model=model,
        mode=mode,
        catalog_id=catalog_id,
        label=str(catalog_entry.get("label") or "").strip() or None,
        role_tags=_clean_tags(catalog_entry.get("role_tags", [])),
        status=str(catalog_entry.get("status") or "").strip() or None,
        source=source,
    )


def _resolve_selection_payload(selection: ModelSelectionPayload) -> ModelDescriptor:
    explicit_provider = (selection.provider or "").strip()
    explicit_model = (selection.model or "").strip()
    explicit_mode = (selection.mode or "").strip().lower() or None
    catalog_id = (selection.catalog_id or "").strip() or None
    has_explicit = bool(explicit_provider and explicit_model)
    catalog_entry = _catalog_entry_or_400(catalog_id) if catalog_id else None

    if has_explicit:
        if catalog_entry is not None:
            expected_provider = str(catalog_entry.get("provider") or "").strip()
            expected_model = str(catalog_entry.get("model") or "").strip()
            expected_mode = str(catalog_entry.get("default_mode") or "").strip().lower() or None
            if explicit_provider != expected_provider or explicit_model != expected_model:
                raise HTTPException(status_code=400, detail="Explicit model selection does not match the catalog entry")
            if explicit_mode and explicit_mode != expected_mode:
                raise HTTPException(status_code=400, detail="Explicit model mode does not match the catalog entry")
            return _build_descriptor(
                provider=explicit_provider,
                model=explicit_model,
                mode=explicit_mode or expected_mode,
                source="explicit_request",
                catalog_id=catalog_id,
                catalog_entry=catalog_entry,
            )
        return _build_descriptor(
            provider=explicit_provider,
            model=explicit_model,
            mode=explicit_mode,
            source="explicit_request",
        )

    if catalog_entry is None:
        raise HTTPException(status_code=400, detail="Model catalog entry not found")
    return _build_descriptor(
        provider=str(catalog_entry.get("provider") or "").strip(),
        model=str(catalog_entry.get("model") or "").strip(),
        mode=str(catalog_entry.get("default_mode") or "").strip().lower() or None,
        source="catalog",
        catalog_id=catalog_id,
        catalog_entry=catalog_entry,
    )


def _catalog_response(item: dict) -> ModelCatalogResponseItem:
    return ModelCatalogResponseItem(
        id=str(item.get("id") or "").strip(),
        label=str(item.get("label") or "").strip(),
        provider=str(item.get("provider") or "").strip(),
        model=str(item.get("model") or "").strip(),
        default_mode=str(item.get("default_mode") or "").strip(),
        role_tags=_clean_tags(item.get("role_tags", [])),
        audiences=[str(value).strip() for value in item.get("audiences", []) if str(value).strip()],
        status=str(item.get("status") or "active").strip(),
        description=str(item.get("description") or "").strip(),
    )


@router.post("/models/select", response_model=SelectModelResponse)
async def select_model(
    request: SelectModelRequest,
    x_user: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = get_or_create_session(db=db, user_id=user.id, session_id=request.session_id)
    resolved = _resolve_selection_payload(request.selection)

    session.selected_model_provider = resolved.provider
    session.selected_model_name = resolved.model
    session.selected_model_mode = resolved.mode
    session.selected_model_catalog_id = resolved.catalog_id
    db.commit()
    db.refresh(session)

    return SelectModelResponse(session_id=session.id, selected=resolved, source="session")


@router.get("/models/catalog", response_model=List[ModelCatalogResponseItem])
async def list_model_catalog(
    audience: Optional[Literal["user", "admin"]] = Query(default=None),
    role_tag: Optional[str] = Query(default=None),
    status: Literal["active", "deprecated", "all"] = Query(default="active"),
):
    items = _store().list_model_catalog(audience=audience, role_tag=role_tag, status=status)
    return [_catalog_response(item) for item in items.values()]


@router.get("/models/sessions/{session_id}", response_model=SelectModelResponse)
async def get_selected_model(
    session_id: int,
    x_user: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id, ChatSession.is_active == True).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.selected_model_provider or not session.selected_model_name:
        raise HTTPException(status_code=404, detail="No model selected for this session")

    catalog_entry = _store().get_model_catalog_item(session.selected_model_catalog_id or "") if session.selected_model_catalog_id else {}
    descriptor = _build_descriptor(
        provider=session.selected_model_provider,
        model=session.selected_model_name,
        mode=session.selected_model_mode,
        source="session",
        catalog_id=session.selected_model_catalog_id,
        catalog_entry=catalog_entry,
    )
    return SelectModelResponse(session_id=session.id, selected=descriptor, source="session")
