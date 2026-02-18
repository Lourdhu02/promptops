"""
Core data models for PromptOps
Maps to the PostgreSQL schema we just created
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, DateTime, Float, Integer, 
    Boolean, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


# ══════════════════════════════════════════════════════════════════════════════
# SQLAlchemy ORM Models (Database)
# ══════════════════════════════════════════════════════════════════════════════

class PromptVersion(Base):
    """Stores each version of a prompt with Git-like versioning"""
    __tablename__ = "prompt_versions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    content = Column(Text, nullable=False)
    hash = Column(String(64), unique=True, nullable=False)
    parent_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True)
    author = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tags = Column(JSON, default=list)
    # RENAMED: metadata -> prompt_metadata (metadata is reserved by SQLAlchemy)
    prompt_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    parent = relationship("PromptVersion", remote_side=[id], backref="children")
    eval_results = relationship("EvalResult", back_populates="version", cascade="all, delete-orphan")
    # Removed deployments relationship to avoid ambiguity
    reviews = relationship("Review", back_populates="version")


class EvalResult(Base):
    """Stores evaluation scores for each prompt version"""
    __tablename__ = "eval_results"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False)
    score_accuracy = Column(Float, nullable=True)
    score_hallucination = Column(Float, nullable=True)
    score_relevance = Column(Float, nullable=True)
    score_latency_p95 = Column(Float, nullable=True)
    score_consistency = Column(Float, nullable=True)
    dataset_id = Column(PGUUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    version = relationship("PromptVersion", back_populates="eval_results")


class Deployment(Base):
    """Records deployment events and active versions per environment"""
    __tablename__ = "deployments"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False)
    environment = Column(String(50), nullable=False)
    deployed_at = Column(DateTime, default=datetime.utcnow)
    deployed_by = Column(String(255), nullable=False)
    rollback_version_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships - specify which FK to use
    version = relationship("PromptVersion", foreign_keys=[version_id])


class ABTest(Base):
    """A/B test configuration and results"""
    __tablename__ = "ab_tests"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version_a_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False)
    version_b_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False)
    traffic_split = Column(Float, default=0.5)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="running")
    winner_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True)
    p_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Dataset(Base):
    """Evaluation dataset metadata"""
    __tablename__ = "datasets"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    format = Column(String(50), nullable=False)
    rows = Column(Integer, default=0)
    file_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Review(Base):
    """PR-style review for prompt versions"""
    __tablename__ = "reviews"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id = Column(PGUUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False)
    reviewer = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    version = relationship("PromptVersion", back_populates="reviews")


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas (API validation & serialization)
# ══════════════════════════════════════════════════════════════════════════════

class PromptVersionSchema(BaseModel):
    """Pydantic schema for PromptVersion"""
    id: UUID
    content: str
    hash: str
    parent_id: Optional[UUID] = None
    author: str
    timestamp: datetime
    tags: List[str] = Field(default_factory=list)
    prompt_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True


class EvalResultSchema(BaseModel):
    """Pydantic schema for EvalResult"""
    id: UUID
    version_id: UUID
    score_accuracy: Optional[float] = None
    score_hallucination: Optional[float] = None
    score_relevance: Optional[float] = None
    score_latency_p95: Optional[float] = None
    score_consistency: Optional[float] = None
    dataset_id: Optional[UUID] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeploymentSchema(BaseModel):
    """Pydantic schema for Deployment"""
    id: UUID
    version_id: UUID
    environment: str
    deployed_at: datetime
    deployed_by: str
    is_active: bool
    
    class Config:
        from_attributes = True