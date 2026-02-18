from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import User
from app.processing.jobs import run_pipeline
from app.schemas import PipelineRunOut

router = APIRouter(prefix="/api/v1", tags=["pipeline"])


@router.post("/pipeline/run", response_model=PipelineRunOut)
def trigger_pipeline(user: User = Depends(get_current_user)):
    return PipelineRunOut(**run_pipeline(user.id))
