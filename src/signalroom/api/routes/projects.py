"""Projects API routes."""

from __future__ import annotations

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from signalroom.db.session import get_db
from signalroom.models.project import Project
from signalroom.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> List[Project]:
    """Lists all configured projects."""
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    """Creates a new project configuration."""
    project_id = payload.id or f"PRJ-{uuid.uuid4().hex[:8].upper()}"
    existing = db.query(Project).filter(Project.slug == payload.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with slug '{payload.slug}' already exists.",
        )

    project = Project(
        id=project_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        target_domains=payload.target_domains,
        default_markets=payload.default_markets,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    """Retrieves a single project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project {project_id} not found.")
    return project
