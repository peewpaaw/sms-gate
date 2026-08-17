# Коммит `ac51718` — статистика сообщений для графиков

**Commit:** `ac51718afa62cdb8be99e70d313c418aaeadc120`  
**Сообщение:** `mailing stats init`

API для построения графика использования провайдеров: число **SMS (`message`)** по **дням**, **провайдеру** и **статусу**.

## Общее

- **Base path:** `/api/v1`
- **Аутентификация:** HTTP Basic (`Authorization: Basic …`, username = email). См. [users-basic-auth-api.md](./users-basic-auth-api.md)
- **OpenAPI tag:** `stats`
- **Endpoint:** `GET /api/v1/stats/messages-by-provider`

---

## Семантика данных

| Измерение | Источник |
|-----------|----------|
| Счётчик | одна строка `message` = +1 |
| Провайдер | `mailing.provider_code` (join по `message.mailing_id`) |
| День | календарный день по **`message.created_at`** в query-параметре `timezone` |
| Статус | `message.status` |

Период задаётся **календарными датами** в выбранной TZ; на бэкенде фильтр: от 00:00 `date_from` до 23:59:59.999… `date_to` inclusive (реализация: `[start_of_day(from), start_of_day(to+1))` в UTC).

Максимальная длина периода: **366 дней**. Иначе **400**.

---

## Query-параметры

| Параметр | Обязательный | Default | Описание |
|----------|--------------|---------|----------|
| `date_from` | да | — | `YYYY-MM-DD`, начало периода (inclusive) |
| `date_to` | да | — | `YYYY-MM-DD`, конец периода (inclusive) |
| `timezone` | нет | `UTC` | IANA, напр. `Europe/Minsk` — для границ периода и группировки по дням |
| `provider_code` | нет | все | Повторяемый параметр: `provider_code=fake&provider_code=beltelecom` |
| `status` | нет | все | Повторяемый: значения enum ниже |
| `fill_gaps` | нет | `false` | См. раздел ниже |

**Пример:**

```http
GET /api/v1/stats/messages-by-provider?date_from=2026-06-01&date_to=2026-06-30&timezone=Europe/Minsk&fill_gaps=true
Authorization: Basic ...
```

---

## Ответ 200

```json
{
  "date_from": "2026-06-01",
  "date_to": "2026-06-30",
  "timezone": "Europe/Minsk",
  "items": [
    {
      "date": "2026-06-01",
      "provider_code": "beltelecom",
      "provider_name": "Белтелеком",
      "status": "submitted",
      "count": 120
    },
    {
      "date": "2026-06-01",
      "provider_code": "fake",
      "provider_name": "Fake (dev)",
      "status": "created",
      "count": 5
    }
  ]
}
```

| Поле item | Описание |
|-----------|----------|
| `date` | Календарная дата в смысле `timezone` |
| `provider_code` | Код провайдера |
| `provider_name` | Имя из каталога (`GET /providers`), может быть `null` |
| `status` | Статус сообщения |
| `count` | ≥ 0 |

Формат **long**: одна строка = одна комбинация `(date, provider_code, status)`.

---

## `fill_gaps`

- **`false` (default):** в `items` только комбинации с `count > 0` (фактические группы из БД).
- **`true`:** для каждой пары `(provider_code, status)`, которая **хотя бы раз** встретилась в сырой выборке, добавляются все дни от `date_from` до `date_to`; в дни без данных `count: 0`.

Если за период нет данных, `items: []` даже при `fill_gaps=true`.

**Графики:** для stacked bar / line с непрерывной осью X удобнее `fill_gaps=true` или заполнение нулей на клиенте при pivot.

---

## Значения `status` (`MessageStatus`)

| Значение | |
|----------|---|
| `created` | |
| `queued` | |
| `submitted` | |
| `delivered` | |
| `undelivered` | |
| `failed` | |
| `unknown` | |

Фильтр `status=submitted&status=delivered` ограничивает агрегацию только этими статусами.

---

## Ошибки 400

| Типичный `detail` | Причина |
|-------------------|---------|
| `Unknown timezone: '...'` | Невалидный IANA в `timezone` |
| `date_to must be on or after date_from` | Перепутаны даты |
| `Period must not exceed 366 days` | Слишком длинный интервал |

---

## Построение графика на фронте (кратко)

1. Запросить `GET /providers/` для подписей (опционально — имена уже в `provider_name`).
2. Запросить stats с тем же `timezone`, что у пользователя в UI.
3. Pivot по `items`:
   - **Stacked bar по дням:** X = `date`, серии = `(provider_code, status)` или stack = provider, цвет = status.
   - **График одного провайдера:** `items.filter(i => i.provider_code === code)`, серии = `status`.

```typescript
// Пример группировки для ECharts/Recharts
const key = (i: Item) => `${i.provider_code}:${i.status}`;
const bySeries = Map.groupBy(items, key);
```

---

## Связь с коммитом `4d183d1`

Коды провайдеров и `provider_name` согласованы с [`GET /api/v1/providers/`](./4d183d1-provider-api.md). Для фильтра графика можно использовать те же `code`, что в селекте рассылки.

---

## Swagger

`/docs` → тег **stats** → `GET /stats/messages-by-provider`.
