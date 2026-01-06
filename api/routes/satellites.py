# api/routes/satellites.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db, Satellite
from api.schemas import SatelliteDTO

router = APIRouter(prefix="/satellites", tags=["Satellites"])

@router.get("/", response_model=List[SatelliteDTO])
def get_satellites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Satellite).offset(skip).limit(limit).all()
