import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
from models.schemas import TranscribeResponse, FilterRequest, FilterResponse
from services.groq_client import transcribe_audio
from agents import narrow_problem, pitch_clarity
from core.config import AUDIO_MAX_BYTES

router = APIRouter()


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)):
    """Receive audio blob → return transcript via GROQ Whisper."""

    # Size guard
    contents = await audio.read()
    if len(contents) > AUDIO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large. Max 10 MB.")

    if not contents:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        transcript = await transcribe_audio(contents, filename=audio.filename or "pitch.webm")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Transcription failed: {str(e)}")

    if not transcript:
        raise HTTPException(status_code=422, detail="No speech detected. Please re-record.")

    return TranscribeResponse(transcript=transcript)


@router.post("/filter", response_model=FilterResponse)
async def filter_idea(body: FilterRequest):
    """Run Narrow Problem Filter + Pitch Clarity Scorer in parallel."""

    transcript = body.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript is empty.")

    # Run both agents in parallel
    narrow_result, clarity_result = await asyncio.gather(
        narrow_problem.run(transcript),
        pitch_clarity.run(transcript),
    )

    both_passed = narrow_result.passed and clarity_result.passed
    verdict = "pass" if both_passed else "fail"

    # Single feedback string on fail — surface the weakest signal
    feedback = None
    if not both_passed:
        if not narrow_result.passed and not clarity_result.passed:
            feedback = f"{narrow_result.feedback} Also: {clarity_result.feedback}"
        elif not narrow_result.passed:
            feedback = narrow_result.feedback
        else:
            feedback = clarity_result.feedback

    return FilterResponse(
        verdict=verdict,
        narrow_problem=narrow_result,
        pitch_clarity=clarity_result,
        feedback=feedback,
    )