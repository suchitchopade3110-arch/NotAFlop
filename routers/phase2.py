from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.smart_data_layer import gather_signals

router = APIRouter()


class ValidateRequest(BaseModel):
    keyword: str        # core keyword extracted from transcript


@router.post("/validate")
async def validate(body: ValidateRequest):
    """Gather live market signals for the idea keyword."""
    keyword = body.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is empty.")

    signals = await gather_signals(keyword)
    return signals