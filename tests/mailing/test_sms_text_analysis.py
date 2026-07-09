import pytest

from app.domains.mailing.enums import SmsMessageEncoding
from app.domains.mailing.services.sms_text_analysis import analyze_sms_text

LOREM_GSM = (
    "Lorem Ipsum is simply dummy text of the printing and typesetting industry. "
    "Lorem Ipsum has been the industry's standard dummy text ever since 1966, "
    "when designers at Letraset and James Mosley, the librarian at St Bride "
    "Printing Library in London, took a 1914 Cicero translation and scrambled it "
    "to make dummy text for Letraset's Body Type sheets."
)

CYRILLIC_UCS2 = (
    "GSM-7 — это 7-битная кодировка, поддерживающая базовые латинские символы, "
    "цифры и распространенные знаки, позволяющая использовать до 160 символов "
    "в одном сообщении. Когда вы используете символы за пределами алфавита "
    "GSM-7 — такие как эмодзи, кириллица или китайские иероглифы — телефон "
    "автоматически переключается на кодировку Unicode, которая позволяет только "
    "70 символов на сообщение."
)


@pytest.mark.parametrize(
    ("text", "encoding", "characters", "segments", "capacity"),
    [
        (LOREM_GSM, SmsMessageEncoding.GSM7, 346, 3, 459),
        (CYRILLIC_UCS2, SmsMessageEncoding.UCS2, 387, 6, 402),
    ],
)
def test_analyze_sms_text_reference_examples(
    text: str,
    encoding: SmsMessageEncoding,
    characters: int,
    segments: int,
    capacity: int,
) -> None:
    result = analyze_sms_text(text)
    assert result.encoding is encoding
    assert result.characters == characters
    assert result.segments == segments
    assert result.capacity == capacity
    assert result.remaining == capacity - result.units


def test_empty_text() -> None:
    result = analyze_sms_text("")
    assert result.segments == 0
    assert result.capacity == 0
    assert result.units == 0
    assert result.remaining == 0


def test_gsm7_extended_euro_counts_two_septets() -> None:
    result = analyze_sms_text("€")
    assert result.encoding is SmsMessageEncoding.GSM7
    assert result.units == 2
    assert result.segments == 1
    assert result.capacity == 160


def test_gsm7_single_vs_concat_boundary() -> None:
    single = analyze_sms_text("a" * 160)
    assert single.segments == 1
    assert single.capacity == 160
    assert single.per_segment_limit == 160

    concat = analyze_sms_text("a" * 161)
    assert concat.segments == 2
    assert concat.capacity == 306
    assert concat.is_concatenated is True
    assert concat.per_segment_limit == 153


def test_ucs2_emoji_uses_two_utf16_units() -> None:
    result = analyze_sms_text("😀")
    assert result.encoding is SmsMessageEncoding.UCS2
    assert result.characters == 1
    assert result.units == 2
    assert result.segments == 1


@pytest.mark.asyncio
async def test_analyze_text_api(
    client,
    auth_headers: dict[str, str],
) -> None:
    from tests.conftest import API_PREFIX

    response = await client.post(
        f"{API_PREFIX}/services/analyze-text",
        json={"text": LOREM_GSM},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["encoding"] == "gsm7"
    assert data["segments"] == 3
    assert data["characters"] == 346
    assert data["capacity"] == 459
