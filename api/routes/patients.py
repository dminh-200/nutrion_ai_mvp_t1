"""Router bệnh nhân mẫu giả lập (data/patients_seed.json)."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import SamplePatientOut, SamplePatientsResponse
from db.repo import load_sample_patients

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/samples", response_model=SamplePatientsResponse)
def list_sample_patients() -> SamplePatientsResponse:
    """Nạp 30 bệnh nhân mẫu giả lập từ db.repo.load_sample_patients."""
    raw = load_sample_patients()
    patients = [SamplePatientOut(**p) for p in raw]
    return SamplePatientsResponse(patients=patients)
