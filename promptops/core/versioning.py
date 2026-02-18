"""
Versioning engine - Git-style prompt versioning
Handles hashing, parent chains, and version storage
"""
import hashlib
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os

from promptops.core.models import Base, PromptVersion

# Load environment
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found in .env")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def compute_hash(content: str, metadata: Dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of prompt content + metadata
    This is the content-addressed identifier
    """
    # Combine content and stable metadata for hashing
    hashable = {
        "content": content,
        "model": metadata.get("model", ""),
        "temperature": metadata.get("temperature", 0.7),
        "version": metadata.get("version", "1.0.0"),
    }
    
    # Convert to stable JSON string
    import json
    stable_str = json.dumps(hashable, sort_keys=True)
    
    # Compute SHA-256
    return hashlib.sha256(stable_str.encode()).hexdigest()


def parse_prompt_file(file_path: Path) -> Dict[str, Any]:
    """
    Parse a YAML prompt file
    Returns dict with content, metadata, etc.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"Empty or invalid YAML file: {file_path}")
    
    # Extract content (required)
    content = data.get("content", "")
    if not content:
        raise ValueError(f"No 'content' field in {file_path}")
    
    # Extract metadata
    metadata = {
        "name": data.get("name", file_path.stem),
        "version": data.get("version", "1.0.0"),
        "model": data.get("model", "gpt-4"),
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens"),
        "top_p": data.get("top_p"),
    }
    
    # Extract tags
    tags = data.get("tags", [])
    
    return {
        "content": content.strip(),
        "metadata": metadata,
        "tags": tags,
    }


def get_current_head(db: Session, project_name: str = "main") -> Optional[PromptVersion]:
    """
    Get the current HEAD version (most recent commit)
    """
    return db.query(PromptVersion)\
        .order_by(desc(PromptVersion.timestamp))\
        .first()


def create_version(
    content: str,
    metadata: Dict[str, Any],
    tags: list[str],
    author: str,
    message: str,
    db: Session,
    parent_id: Optional[UUID] = None,
) -> PromptVersion:
    """
    Create a new prompt version and store in database
    
    This is the core commit operation:
    1. Compute content hash
    2. Check if this exact version already exists (deduplication)
    3. Create version record with parent reference
    4. Store in PostgreSQL
    """
    # Compute hash
    version_hash = compute_hash(content, metadata)
    
    # Check if this exact version already exists
    existing = db.query(PromptVersion)\
        .filter(PromptVersion.hash == version_hash)\
        .first()
    
    if existing:
        # This exact prompt already exists - just return it
        return existing
    
    # Add commit message to metadata
    full_metadata = {**metadata, "commit_message": message}
    
    # Create new version
    new_version = PromptVersion(
        content=content,
        hash=version_hash,
        parent_id=parent_id,
        author=author,
        timestamp=datetime.utcnow(),
        tags=tags,
        prompt_metadata=full_metadata,  # FIXED: use prompt_metadata
    )
    
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    
    return new_version


def get_version_by_hash(db: Session, version_hash: str) -> Optional[PromptVersion]:
    """
    Retrieve a version by its hash
    """
    return db.query(PromptVersion)\
        .filter(PromptVersion.hash == version_hash)\
        .first()


def get_version_history(
    db: Session, 
    limit: int = 10,
    start_from: Optional[UUID] = None
) -> list[PromptVersion]:
    """
    Get version history (commit log)
    Traces back through parent references
    """
    versions = []
    
    if start_from:
        current = db.query(PromptVersion)\
            .filter(PromptVersion.id == start_from)\
            .first()
    else:
        # Start from HEAD
        current = get_current_head(db)
    
    # Walk back through parents
    count = 0
    while current and count < limit:
        versions.append(current)
        if current.parent_id:
            current = db.query(PromptVersion)\
                .filter(PromptVersion.id == current.parent_id)\
                .first()
        else:
            break
        count += 1
    
    return versions


def get_diff(version_a: PromptVersion, version_b: PromptVersion) -> Dict[str, Any]:
    """
    Compute diff between two versions
    Returns line-by-line diff
    """
    import difflib
    
    lines_a = version_a.content.splitlines(keepends=True)
    lines_b = version_b.content.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=f"version {version_a.hash[:8]}",
        tofile=f"version {version_b.hash[:8]}",
        lineterm=""
    )
    
    return {
        "hash_a": version_a.hash,
        "hash_b": version_b.hash,
        "diff_lines": list(diff),
        "author_a": version_a.author,
        "author_b": version_b.author,
        "timestamp_a": version_a.timestamp,
        "timestamp_b": version_b.timestamp,
    }