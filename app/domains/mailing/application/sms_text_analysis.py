"""SMS text length and segment analysis (GSM 03.38 / UCS-2)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domains.mailing.enums import SmsMessageEncoding

# GSM 03.38 default alphabet (basic table, one septet per character).
GSM7_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ "
    "!\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)

# Extension table: encoded as ESC + char (two septets).
GSM7_EXTENDED = frozenset("|^{}[~]\\€")

GSM7_SINGLE_LIMIT = 160
GSM7_CONCAT_LIMIT = 153
UCS2_SINGLE_LIMIT = 70
UCS2_CONCAT_LIMIT = 67


def is_gsm7_char(char: str) -> bool:
    return char in GSM7_BASIC or char in GSM7_EXTENDED


def count_gsm7_septets(text: str) -> int:
    total = 0
    for char in text:
        if char in GSM7_BASIC:
            total += 1
        elif char in GSM7_EXTENDED:
            total += 2
        else:
            raise ValueError(f"Character not in GSM-7: {char!r}")
    return total


def count_ucs2_units(text: str) -> int:
    return len(text.encode("utf-16-be")) // 2


def detect_encoding(text: str) -> tuple[SmsMessageEncoding, list[str]]:
    non_gsm: list[str] = []
    seen: set[str] = set()
    for char in text:
        if not is_gsm7_char(char) and char not in seen:
            seen.add(char)
            non_gsm.append(char)
    if non_gsm:
        return SmsMessageEncoding.UCS2, non_gsm
    return SmsMessageEncoding.GSM7, []


def _segments_and_capacity(
    units: int,
    *,
    single_limit: int,
    concat_limit: int,
) -> tuple[int, int, int]:
    if units == 0:
        return 0, 0, single_limit
    if units <= single_limit:
        return 1, single_limit, single_limit
    segments = math.ceil(units / concat_limit)
    capacity = segments * concat_limit
    return segments, capacity, concat_limit


@dataclass(frozen=True, slots=True)
class SmsTextAnalysis:
    encoding: SmsMessageEncoding
    characters: int
    units: int
    segments: int
    capacity: int
    remaining: int
    per_segment_limit: int
    is_concatenated: bool
    non_gsm_characters: tuple[str, ...]


def analyze_sms_text(text: str) -> SmsTextAnalysis:
    encoding, non_gsm = detect_encoding(text)
    characters = len(text)

    if encoding is SmsMessageEncoding.GSM7:
        units = count_gsm7_septets(text)
        segments, capacity, per_segment = _segments_and_capacity(
            units,
            single_limit=GSM7_SINGLE_LIMIT,
            concat_limit=GSM7_CONCAT_LIMIT,
        )
    else:
        units = count_ucs2_units(text)
        segments, capacity, per_segment = _segments_and_capacity(
            units,
            single_limit=UCS2_SINGLE_LIMIT,
            concat_limit=UCS2_CONCAT_LIMIT,
        )

    remaining = capacity - units if segments > 0 else 0
    return SmsTextAnalysis(
        encoding=encoding,
        characters=characters,
        units=units,
        segments=segments,
        capacity=capacity,
        remaining=remaining,
        per_segment_limit=per_segment,
        is_concatenated=segments > 1,
        non_gsm_characters=tuple(non_gsm),
    )
