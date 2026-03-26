from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from mellow_chat_runtime.infra.database import ChatSession


@dataclass
class EffectiveModelSelection:
    provider: str
    model: str
    mode: str
    source: str
    catalog_id: Optional[str] = None
    label: Optional[str] = None
    role_tags: list[str] = field(default_factory=list)
    status: Optional[str] = None


class ModelRoutingService:
    """Resolve model selection while keeping session precedence explicit."""

    def __init__(self, default_provider: str = "ollama") -> None:
        self._default_provider = default_provider

    def resolve(
        self,
        session: ChatSession,
        llm_service: object,
        mode: str = "fast",
        request_provider: Optional[str] = None,
        request_model: Optional[str] = None,
        request_catalog_id: Optional[str] = None,
        request_mode: Optional[str] = None,
        request_catalog_entry: Optional[Dict[str, Any]] = None,
        session_catalog_entry: Optional[Dict[str, Any]] = None,
    ) -> EffectiveModelSelection:
        cleaned_mode = (mode or "fast").strip().lower() or "fast"
        explicit_provider = (request_provider or "").strip()
        explicit_model = (request_model or "").strip()
        explicit_mode = (request_mode or "").strip().lower()
        catalog_id = (request_catalog_id or "").strip() or None

        if explicit_provider and explicit_model:
            if catalog_id:
                if not request_catalog_entry:
                    raise ValueError("Model catalog entry not found")
                self._validate_explicit_against_catalog(
                    provider=explicit_provider,
                    model=explicit_model,
                    mode=explicit_mode or None,
                    catalog_entry=request_catalog_entry,
                )
            resolved_mode = explicit_mode or str((request_catalog_entry or {}).get("default_mode") or cleaned_mode).strip().lower() or cleaned_mode
            return EffectiveModelSelection(
                provider=explicit_provider,
                model=explicit_model,
                mode=resolved_mode,
                source="explicit_request",
                catalog_id=catalog_id,
                label=str((request_catalog_entry or {}).get("label") or "").strip() or None,
                role_tags=self._role_tags(request_catalog_entry),
                status=str((request_catalog_entry or {}).get("status") or "").strip() or None,
            )

        if catalog_id:
            if not request_catalog_entry:
                raise ValueError("Model catalog entry not found")
            return EffectiveModelSelection(
                provider=str(request_catalog_entry.get("provider") or self._default_provider).strip(),
                model=str(request_catalog_entry.get("model") or "").strip(),
                mode=str(request_catalog_entry.get("default_mode") or cleaned_mode).strip().lower() or cleaned_mode,
                source="catalog",
                catalog_id=catalog_id,
                label=str(request_catalog_entry.get("label") or "").strip() or None,
                role_tags=self._role_tags(request_catalog_entry),
                status=str(request_catalog_entry.get("status") or "").strip() or None,
            )

        if session.selected_model_provider and session.selected_model_name:
            return EffectiveModelSelection(
                provider=session.selected_model_provider,
                model=session.selected_model_name,
                mode=(session.selected_model_mode or cleaned_mode).strip().lower() or cleaned_mode,
                source="session",
                catalog_id=(session.selected_model_catalog_id or None),
                label=str((session_catalog_entry or {}).get("label") or "").strip() or None,
                role_tags=self._role_tags(session_catalog_entry),
                status=str((session_catalog_entry or {}).get("status") or "").strip() or None,
            )

        model_name = llm_service.get_model_for_mode(cleaned_mode)  # type: ignore[attr-defined]
        return EffectiveModelSelection(
            provider=self._default_provider,
            model=model_name,
            mode=cleaned_mode,
            source="system_default",
        )

    def _validate_explicit_against_catalog(
        self,
        *,
        provider: str,
        model: str,
        mode: Optional[str],
        catalog_entry: Dict[str, Any],
    ) -> None:
        expected_provider = str(catalog_entry.get("provider") or "").strip()
        expected_model = str(catalog_entry.get("model") or "").strip()
        expected_mode = str(catalog_entry.get("default_mode") or "").strip().lower()
        if provider != expected_provider or model != expected_model:
            raise ValueError("Explicit model selection does not match the catalog entry")
        if mode and mode.strip().lower() != expected_mode:
            raise ValueError("Explicit model mode does not match the catalog entry")

    def _role_tags(self, catalog_entry: Optional[Dict[str, Any]]) -> list[str]:
        if not isinstance(catalog_entry, dict):
            return []
        values = catalog_entry.get("role_tags", [])
        if not isinstance(values, list):
            return []
        return [str(item).strip() for item in values if str(item).strip()]
