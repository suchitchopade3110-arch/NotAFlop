from fastapi import APIRouter, HTTPException

from models.schemas import ReportResponse, ReportSummary
from repositories import report_repository

router = APIRouter()


@router.get("/reports/{public_id}", response_model=ReportResponse)
async def get_report(public_id: str):
    doc = await report_repository.get_by_public_id(public_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return ReportResponse(**doc.model_dump())


@router.get("/sessions/{sid}/reports", response_model=list[ReportSummary])
async def list_session_reports(sid: str):
    docs = await report_repository.list_by_session(sid)
    return [ReportSummary(**doc.model_dump()) for doc in docs]
