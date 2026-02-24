
"""
FastAPI application for PromptOps
Serves prompts to production applications
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from promptops.core.models import PromptVersion, Deployment
from promptops.core.versioning import SessionLocal, get_version_by_hash
from promptops.deploy.engine import DeploymentEngine

app = FastAPI(
    title="PromptOps API",
    description="Git-style version control for LLM prompts",
    version="0.1.0"
)

# CORS middleware for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class PromptResponse(BaseModel):
    """Response when fetching a prompt"""
    content: str
    hash: str
    version: str
    model: str
    temperature: float
    metadata: Dict[str, Any]
    tags: list[str]
    deployed_at: datetime
    environment: str


class DeployRequest(BaseModel):
    """Request to deploy a version"""
    version_hash: str
    environment: str
    deployed_by: str


class DeployResponse(BaseModel):
    """Response after deployment"""
    success: bool
    version_hash: str
    environment: str
    deployed_at: datetime
    message: str


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """API health check"""
    return {
        "service": "PromptOps API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/prompts/{environment}/active", response_model=PromptResponse)
async def get_active_prompt(
    environment: str,
    name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get the currently active prompt for an environment
    
    This is the primary endpoint production apps use to fetch prompts
    
    Args:
        environment: dev, staging, or prod
        name: Optional prompt name filter
    
    Returns:
        The active prompt content and metadata
    """
    # Try Redis cache first
    engine = DeploymentEngine()
    cached = engine.get_from_cache(environment, name)
    
    if cached:
        return cached
    
    # Cache miss - fetch from database
    deployment = db.query(Deployment)\
        .filter(Deployment.environment == environment)\
        .filter(Deployment.is_active == True)\
        .order_by(Deployment.deployed_at.desc())\
        .first()
    
    if not deployment:
        raise HTTPException(
            status_code=404,
            detail=f"No active prompt found for environment: {environment}"
        )
    
    version = deployment.version
    
    response = PromptResponse(
        content=version.content,
        hash=version.hash,
        version=version.prompt_metadata.get("version", "1.0.0"),
        model=version.prompt_metadata.get("model", "gpt-4"),
        temperature=version.prompt_metadata.get("temperature", 0.7),
        metadata=version.prompt_metadata,
        tags=version.tags,
        deployed_at=deployment.deployed_at,
        environment=environment
    )
    
    # Store in cache
    engine.set_cache(environment, response.dict(), name)
    
    return response


@app.post("/deploy", response_model=DeployResponse)
async def deploy_version(
    request: DeployRequest,
    db: Session = Depends(get_db)
):
    """
    Deploy a specific prompt version to an environment
    
    Args:
        version_hash: Hash of the version to deploy
        environment: Target environment (dev/staging/prod)
        deployed_by: Who is deploying
    
    Returns:
        Deployment confirmation
    """
    # Get the version
    version = get_version_by_hash(db, request.version_hash)
    
    if not version:
        raise HTTPException(
            status_code=404,
            detail=f"Version not found: {request.version_hash}"
        )
    
    # Deactivate current deployment
    current = db.query(Deployment)\
        .filter(Deployment.environment == request.environment)\
        .filter(Deployment.is_active == True)\
        .all()
    
    for dep in current:
        dep.is_active = False
    
    # Create new deployment
    deployment = Deployment(
        version_id=version.id,
        environment=request.environment,
        deployed_by=request.deployed_by,
        deployed_at=datetime.utcnow(),
        is_active=True
    )
    
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    
    # Invalidate cache
    engine = DeploymentEngine()
    engine.invalidate_cache(request.environment)
    
    return DeployResponse(
        success=True,
        version_hash=version.hash,
        environment=request.environment,
        deployed_at=deployment.deployed_at,
        message=f"Successfully deployed {version.hash[:8]} to {request.environment}"
    )


@app.post("/rollback/{environment}")
async def rollback_deployment(
    environment: str,
    db: Session = Depends(get_db)
):
    """
    Rollback to the previous deployment
    
    Args:
        environment: Which environment to rollback
    
    Returns:
        Rollback confirmation
    """
    # Get current deployment
    current = db.query(Deployment)\
        .filter(Deployment.environment == environment)\
        .filter(Deployment.is_active == True)\
        .order_by(Deployment.deployed_at.desc())\
        .first()
    
    if not current:
        raise HTTPException(
            status_code=404,
            detail=f"No active deployment in {environment}"
        )
    
    # Get previous deployment
    previous = db.query(Deployment)\
        .filter(Deployment.environment == environment)\
        .filter(Deployment.id != current.id)\
        .order_by(Deployment.deployed_at.desc())\
        .first()
    
    if not previous:
        raise HTTPException(
            status_code=400,
            detail="No previous deployment to rollback to"
        )
    
    # Swap active status
    current.is_active = False
    previous.is_active = True
    
    db.commit()
    
    # Invalidate cache
    engine = DeploymentEngine()
    engine.invalidate_cache(environment)
    
    return {
        "success": True,
        "rolled_back_from": current.version.hash[:8],
        "rolled_back_to": previous.version.hash[:8],
        "environment": environment,
        "message": f"Rolled back to {previous.version.hash[:8]}"
    }


@app.get("/deployments/{environment}/history")
async def get_deployment_history(
    environment: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get deployment history for an environment
    
    Args:
        environment: Which environment
        limit: Max number of deployments to return
    
    Returns:
        List of deployments
    """
    deployments = db.query(Deployment)\
        .filter(Deployment.environment == environment)\
        .order_by(Deployment.deployed_at.desc())\
        .limit(limit)\
        .all()
    
    return {
        "environment": environment,
        "count": len(deployments),
        "deployments": [
            {
                "version_hash": d.version.hash[:8],
                "deployed_at": d.deployed_at,
                "deployed_by": d.deployed_by,
                "is_active": d.is_active,
            }
            for d in deployments
        ]
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check - verifies database and Redis connectivity
    """
    from promptops.deploy.engine import DeploymentEngine
    
    # Check database
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    
    # Check Redis
    engine = DeploymentEngine()
    redis_status = "connected" if engine.redis_available else "unavailable"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.utcnow()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
