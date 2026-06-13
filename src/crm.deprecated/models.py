"""CRM record models — Pydantic v2.

Used by the repository layer for validation on the way in/out of SQLite.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Tier = Literal["S1", "S2", "S3"]
InteractionType = Literal["email", "call", "meeting", "note", "message"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def _new_id() -> str:
    return uuid4().hex


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_id)
    display_name: str = Field(min_length=1, max_length=300)
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = Field(default=None, max_length=64)
    company: Optional[str] = Field(default=None, max_length=300)
    role: Optional[str] = Field(default=None, max_length=200)
    tier: Tier = "S2"
    notes: Optional[str] = None
    merged_into: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)

    @field_validator("primary_email", mode="before")
    @classmethod
    def _empty_email_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_id)
    contact_id: str
    source_type: str = Field(min_length=1, max_length=64)
    source_external_id: Optional[str] = Field(default=None, max_length=300)
    raw_blob: Optional[str] = None
    tier: Tier = "S2"
    captured_at: str = Field(default_factory=_now_iso)


class Interaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_id)
    contact_id: str
    interaction_type: InteractionType
    ts: str = Field(default_factory=_now_iso)
    summary: Optional[str] = Field(default=None, max_length=1000)
    body: Optional[str] = None
    source_id: Optional[str] = None
    tier: Tier = "S2"
    created_at: str = Field(default_factory=_now_iso)


class MergeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_id)
    primary_contact_id: str
    merged_contact_id: str
    operator_id: str
    reason: Optional[str] = None
    fields_overridden: Optional[str] = None  # JSON string
    prev_hash: str = ""
    hash: str
    merged_at: str = Field(default_factory=_now_iso)
