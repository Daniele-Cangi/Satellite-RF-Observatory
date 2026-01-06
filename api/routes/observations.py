# api/routes/observations.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db, Observation

from api.schemas import ObservationDTO

router = APIRouter(prefix="/observations", tags=["Observations"])

@router.get("/", response_model=List[ObservationDTO])
def get_observations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Observation).offset(skip).limit(limit).all()
