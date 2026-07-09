# Анализ текста SMS (`/services/analyze-text`)

Документ для UI: превью длины и числа сегментов при вводе текста сообщения или шаблона. Расчёт соответствует типичной сегментации SMS (GSM 03.38 / UCS-2, concatenated SMS с UDH).

## Общее

- **Base path:** `/api/v1`
- **Аутентификация:** заголовок `X-API-Key` (как у остальных защищённых методов)
- **OpenAPI tag:** `services`
- **Метод:** `POST /api/v1/services/analyze-text`
- **Назначение:** только расчёт; текст в БД не сохраняется

Ограничение длины входа совпадает с созданием сообщения: **1–1600** символов Unicode (`MessageCreate.text`).

---

## Запрос

```http
POST /api/v1/services/analyze-text
Content-Type: application/json
X-API-Key: <key>
```

```json
{
  "text": "Текст для проверки"
}
```

| Поле | Тип | Ограничения |
|------|-----|-------------|
| `text` | string | `minLength: 1`, `maxLength: 1600` |

**422** — пустая строка, слишком длинный текст или невалидный JSON.

---

## Ответ

```json
{
  "encoding": "gsm7",
  "characters": 346,
  "units": 346,
  "segments": 3,
  "capacity": 459,
  "remaining": 113,
  "per_segment_limit": 153,
  "is_concatenated": true,
  "non_gsm_characters": []
}
```

| Поле | Тип | Для UI (человекочитаемо) |
|------|-----|---------------------------|
| `encoding` | `"gsm7"` \| `"ucs2"` | Кодировка сегментации |
| `characters` | number | **Символов** — `длина строки` (символы Unicode, как в поле ввода) |
| `units` | number | Единицы, по которым режут SMS (см. ниже); для отладки / продвинутого UI |
| `segments` | number | **Сообщений** — сколько SMS уйдёт на сеть |
| `capacity` | number | **Лимит** — максимум `units` в текущем числе сегментов (не «макс. символов в одном SMS» в абстракции) |
| `remaining` | number | Сколько `units` ещё влезет, пока не понадобится следующий сегмент: `capacity - units` |
| `per_segment_limit` | number | Лимит `units` на один сегмент в текущем режиме (160 / 153 / 70 / 67) |
| `is_concatenated` | boolean | `true`, если `segments > 1` (многочастное SMS) |
| `non_gsm_characters` | string[] | Уникальные символы **вне GSM-7**; если непустой — выбран `ucs2` (подсказка «эти символы уменьшают лимит») |

Рекомендуемая строка в форме:

> Сообщений: **{segments}** · Символов: **{characters}** · Лимит: **{capacity}**

Для UCS-2 при наличии эмодзи `characters` может быть меньше, чем «ощущаемая» длина в графемах: в `units` учитываются UTF-16 code units (эмодзи = 2).

---

## Принцип расчёта

### 1. Выбор кодировки

Текст целиком относится к **одному** режиму:

1. Если **каждый** символ входит в алфавит **GSM-7** (базовая таблица GSM 03.38 + extension: `|^{}[~]\€` и обратный слэш) → `encoding: "gsm7"`.
2. Если есть **хотя бы один** символ вне GSM-7 (кириллица, длинное тире `—`, эмодзи, китайские иероглифы и т.д.) → `encoding: "ucs2"`. Список таких символов — в `non_gsm_characters` (порядок по первому появлению в тексте).

Переключение бинарное: один кириллический символ в длинной латинице переводит **весь** текст в UCS-2.

### 2. Что такое `units`

| `encoding` | `units` |
|------------|---------|
| `gsm7` | **Septets** (7-битные единицы). Обычный GSM-символ = 1. Символы из extension-таблицы (`€`, `|`, `^`, …) = **2** septets (ESC + символ). |
| `ucs2` | **UTF-16 code units** (как в 3GPP для UCS-2 SMS). Символы BMP (латиница, кириллица) = 1 unit на символ. Суррогатные пары (типичные эмодзи) = **2** units на один emoji. |

`characters` всегда `len(text)` в Python-смысле (кодовые точки Unicode). Для кириллицы без эмодзи обычно `characters === units`. Для GSM-7 латиницы без extension чаще всего тоже.

### 3. Число сегментов (`segments`)

**GSM-7:**

| Условие | Сегментов | `per_segment_limit` | `capacity` |
|---------|-----------|---------------------|------------|
| `units ≤ 160` | 1 | 160 | 160 |
| `units > 160` | `ceil(units / 153)` | 153 | `segments × 153` |

**UCS-2:**

| Условие | Сегментов | `per_segment_limit` | `capacity` |
|---------|-----------|---------------------|------------|
| `units ≤ 70` | 1 | 70 | 70 |
| `units > 70` | `ceil(units / 67)` | 67 | `segments × 67` |

Числа **153** и **67** — лимит на сегмент в **склеенном** (concatenated) SMS: часть места занимает UDH (заголовок склейки). Поэтому второй и далее сегменты «короче», чем первый одиночный (160 / 70).

`remaining = capacity - units` (при `segments > 0`).

### 4. Примеры (эталон бэкенда)

**Только латиница (GSM-7), 346 символов:**

- `units = 346`, `segments = 3` (`ceil(346/153)`), `capacity = 459` (`3×153`), `remaining = 113`

**Кириллица + типографское тире `—` (UCS-2), 387 символов:**

- `units = 387`, `segments = 6` (`ceil(387/67)`), `capacity = 402` (`6×67`), `remaining = 15`
- `non_gsm_characters` содержит как минимум `—` и символы кириллицы

---

## Интеграция в UI

- Вызывать при изменении текста (debounce 200–400 ms), не блокируя отправку рассылки.
- Показывать предупреждение, если `segments > 1` или `encoding === "ucs2"` (дороже / меньше символов на сегмент).
- При непустом `non_gsm_characters` можно подсветить символы или tooltip: «из-за этих символов лимит 70/67, а не 160/153».
- Лимит **1600** на `text` в API создания сообщения не равен «1600 SMS» — при UCS-2 длинный текст даёт много `segments`; анализатор показывает фактическое `segments`.

---

## Ошибки

| Код | Когда |
|-----|--------|
| **401** | Нет или неверный `X-API-Key` |
| **422** | Валидация тела (`text` пустой или > 1600) |

---

## TypeScript (ориентир)

```ts
type SmsMessageEncoding = "gsm7" | "ucs2";

interface SmsTextAnalyzeRequest {
  text: string;
}

interface SmsTextAnalyzeResponse {
  encoding: SmsMessageEncoding;
  characters: number;
  units: number;
  segments: number;
  capacity: number;
  remaining: number;
  per_segment_limit: number;
  is_concatenated: boolean;
  non_gsm_characters: string[];
}
```

Схема в OpenAPI: тег `services`, operation `analyze_mailing_text`.
