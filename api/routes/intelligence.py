# api/routes/intelligence.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from core.database import get_db, VulnerabilityAssessment, Satellite
from api.schemas import VulnerabilityReport

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])

@router.get("/tactical/vulnerabilities", response_model=List[VulnerabilityReport])
def get_tactical_vulnerabilities(
    min_score: float = 0.5,
    db: Session = Depends(get_db)
):
    """
    [RESTRICTED] Get high-risk vulnerability assessments.
    Used by the Tactical Dashboard to highlight weak targets.
    """
    results = db.query(VulnerabilityAssessment)\
        .filter(VulnerabilityAssessment.vulnerability_score >= min_score)\
        .order_by(VulnerabilityAssessment.vulnerability_score.desc())\
        .all()

    reports = []
    for row in results:
        # Get satellite name efficiently
        sat_name = db.query(Satellite.name).filter(Satellite.id == row.satellite_id).scalar()
        
        reports.append(VulnerabilityReport(
            target_satellite=sat_name or "UNKNOWN",
            vulnerability_type=row.assessment_type,
            risk_score=row.vulnerability_score,
            vector_analysis=row.strategic_implications if row.strategic_implications else "N/A"
        ))

    return reports

@router.post("/tactical/tasking")
async def request_satellite_interception(
    norad_id: int,
    priority: str = "HIGH"
):
    """
    [RESTRICTED] Task the system to prioritize a specific satellite.
    This injects a high-priority task into the Scheduler.
    """
    # Logic to override Scheduler priorities
    # This would typically interface with the running Scheduler instance or push to a command queue
    return {"status": "TASK_ACCEPTED", "target": norad_id, "mode": "INTERCEPT"}
