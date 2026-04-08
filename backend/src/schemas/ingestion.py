from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RawFileStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RawMessageChunkStatus(StrEnum):
    NEW = "NEW"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"
    DUPLICATE_LOCAL = "DUPLICATE_LOCAL"


class ORMBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RawFileBase(BaseModel):
    file: str
    file_name: str = Field(max_length=255)
    content: str = ""
    source: str | None = None
    processed: bool = False
    process_started_at: datetime | None = None
    process_finished_at: datetime | None = None
    notes: str | None = None
    dedupe_stats: dict[str, Any] = Field(default_factory=dict)
    status: RawFileStatus = RawFileStatus.PENDING
    owner_id: UUID | None = None


class RawFileCreate(RawFileBase):
    pass


class RawFileUpdate(BaseModel):
    file: str | None = None
    file_name: str | None = Field(default=None, max_length=255)
    content: str | None = None
    source: str | None = None
    processed: bool | None = None
    process_started_at: datetime | None = None
    process_finished_at: datetime | None = None
    notes: str | None = None
    dedupe_stats: dict[str, Any] | None = None
    status: RawFileStatus | None = None
    owner_id: UUID | None = None


class RawFileOut(ORMBaseSchema, RawFileBase):
    id: UUID
    uploaded_at: datetime


class RawFileResponse(BaseModel):
    data: RawFileOut


class RawMessageChunkBase(BaseModel):
    rawfile_id: UUID
    message_start: datetime | None = None
    sender: str | None = Field(default=None, max_length=255)
    raw_text: str
    cleaned_text: str | None = None
    split_into: int = 0
    status: RawMessageChunkStatus = RawMessageChunkStatus.NEW
    user_id: UUID | None = None


class RawMessageChunkCreate(RawMessageChunkBase):
    pass


class RawMessageChunkUpdate(BaseModel):
    message_start: datetime | None = None
    sender: str | None = Field(default=None, max_length=255)
    raw_text: str | None = None
    cleaned_text: str | None = None
    split_into: int | None = None
    status: RawMessageChunkStatus | None = None
    user_id: UUID | None = None


class RawMessageChunkOut(ORMBaseSchema, RawMessageChunkBase):
    id: UUID
    created_at: datetime


class RawMessageChunkResponse(BaseModel):
    data: RawMessageChunkOut


class FileProcessBase(BaseModel):
    file: str
    status: str = "Queued"
    progress: int = 0


class FileProcessCreate(FileProcessBase):
    pass


class FileProcessUpdate(BaseModel):
    file: str | None = None
    status: str | None = None
    progress: int | None = None


class FileProcessOut(ORMBaseSchema, FileProcessBase):
    id: UUID
    created_at: datetime


class FileProcessResponse(BaseModel):
    data: FileProcessOut


class ParseRawFileTaskPayload(BaseModel):
    rawfile_id: UUID


class RawFileProcessResult(BaseModel):
    rawfile_id: UUID
    created: int
    ignored: int
    completed_at: datetime


class ChunkEmbedTaskPayload(BaseModel):
    raw_message_chunk_id: UUID


class ChunkStatusUpdatePayload(BaseModel):
    raw_message_chunk_id: UUID
    status: RawMessageChunkStatus
