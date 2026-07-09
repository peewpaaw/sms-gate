from fastapi import APIRouter
from app.deps import CurrentUserDep
from app.domains.mailing.services.sms_text_analysis import analyze_sms_text
from app.domains.mailing.schemas import (
    SmsTextAnalyzeRequest,
    SmsTextAnalyzeResponse,
)


router = APIRouter(prefix="/services", tags=["services"])


@router.post(
    "/analyze-text",
    summary="Анализ текста SMS",
    description=(
        "Подсчёт сегментов SMS: GSM-7 (160/153) или UCS-2 (70/67) при символах вне GSM."
    ),
)
async def analyze_mailing_text(
    _current_user: CurrentUserDep,
    payload: SmsTextAnalyzeRequest,
) -> SmsTextAnalyzeResponse:
    analysis = analyze_sms_text(payload.text)
    return SmsTextAnalyzeResponse(
        encoding=analysis.encoding,
        characters=analysis.characters,
        units=analysis.units,
        segments=analysis.segments,
        capacity=analysis.capacity,
        remaining=analysis.remaining,
        per_segment_limit=analysis.per_segment_limit,
        is_concatenated=analysis.is_concatenated,
        non_gsm_characters=list(analysis.non_gsm_characters),
    )
