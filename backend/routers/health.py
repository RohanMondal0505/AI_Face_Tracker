"""HTTP health endpoint."""

from fastapi import APIRouter

from ..config import MODEL_PATH

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {"status": "ok", "model_available": MODEL_PATH.is_file()}
