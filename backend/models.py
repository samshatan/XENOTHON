from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(BaseModel):
    name: str
    status: str = "pending"  # pending | running | done | error
    message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RedFlag(BaseModel):
    severity: str  # low | medium | high | critical
    category: str
    description: str


class JobResult(BaseModel):
    job_id: str
    trust_score: float = Field(ge=0, le=100)
    verdict: str  # AUTHENTIC | SUSPICIOUS | FRAUDULENT
    red_flags: List[RedFlag] = []
    agent_results: Dict[str, Any] = {}
    summary: str = ""
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class JobState(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    filename: str = ""
    file_path: str = ""
    agents: Dict[str, AgentStatus] = Field(default_factory=dict)
    result: Optional[JobResult] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None
