from pydantic import BaseModel, Field
from app.domains.mailing.enums import SmsMessageEncoding


class SmsTextAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1600)


class SmsTextAnalyzeResponse(BaseModel):
    encoding: SmsMessageEncoding
    characters: int = Field(description="Длина строки (символов Unicode)")
    units: int = Field(
        description="Единицы для сегментации: septets (GSM-7) или UTF-16 code units (UCS-2)"
    )
    segments: int = Field(description="Число SMS-сообщений (сегментов)")
    capacity: int = Field(description="Лимит: максимум units в текущем числе сегментов")
    remaining: int = Field(description="Свободно units до заполнения текущих сегментов")
    per_segment_limit: int = Field(
        description="Лимит units на один сегмент (160/153 или 70/67)"
    )
    is_concatenated: bool
    non_gsm_characters: list[str] = Field(
        default_factory=list,
        description="Символы вне GSM-7, из-за которых выбрана UCS-2",
    )
