# Пользователи и Basic Auth (API)

Документ для UI: вход по HTTP Basic, профиль текущего пользователя, админский CRUD.

## Общее

- **Base path:** `/api/v1`
- **Аутентификация:** HTTP Basic — `Authorization: Basic base64(email:password)`
- **Username:** email
- **OpenAPI tag:** `users`
- **Роли:** `user` | `admin`

При 401 сервер отдаёт заголовок `WWW-Authenticate: Basic`.

---

## Модель `UserRead`

```json
{
  "id": "uuid",
  "is_active": true,
  "name": "Имя",
  "email": "user@example.com",
  "role": "user"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | uuid | |
| `is_active` | bool | `false` — логин → 401 |
| `name` | string | |
| `email` | string | логин |
| `role` | `user` \| `admin` | |

Пароль / `password_hash` в ответах **никогда** нет.

---

## `GET /api/v1/users/me/`

Профиль текущего пользователя (любая активная роль).

```http
GET /api/v1/users/me/
Authorization: Basic ...
```

**200:** `UserRead`  
**401:** нет/неверный Basic Auth или пользователь неактивен

> Breaking: раньше было `GET /api/v1/auth/me/` + `X-API-Key`.

**UI:** после логина дергать `/users/me/` — отрисовать имя/email и спрятать admin-only пункты, если `role !== "admin"`.

---

## Admin: управление пользователями

Все методы ниже — **только `admin`**. Иначе **403** `Forbidden`.

### `GET /api/v1/users/`

Список с пагинацией.

| Query | Default | Описание |
|-------|---------|----------|
| `limit` | 50 | 1–500 |
| `offset` | 0 | |

**200:** `Page[UserRead]` — `{ total, limit, offset, items }`

### `POST /api/v1/users/`

```json
{
  "email": "new@example.com",
  "password": "password123",
  "name": "New",
  "role": "user",
  "is_active": true
}
```

| Поле | Обязательное | Default | Ограничения |
|------|--------------|---------|-------------|
| `email` | да | | |
| `password` | да | | 8–128 символов |
| `name` | нет | `""` | max 255 |
| `role` | нет | `user` | `user` \| `admin` |
| `is_active` | нет | `true` | |

**201:** `UserRead`  
**409:** `Email already exists`

### `GET /api/v1/users/{user_id}/`

**200:** `UserRead`  
**404:** `User not found`

### `PATCH /api/v1/users/{user_id}/`

Частичное обновление — хотя бы одно поле.

```json
{ "name": "...", "email": "...", "password": "...", "role": "admin", "is_active": false }
```

**200:** `UserRead`  
**404:** `User not found`  
**409:** `Email already exists`  
**409:** `Cannot demote or deactivate the last active admin`  
**422:** `At least one field must be set`

DELETE нет (FK на рассылки). Деактивация — `is_active: false`.

---

## RBAC (кратко для UI)

| Действие | `user` | `admin` |
|----------|--------|--------|
| `GET /users/me/` | да | да |
| CRUD `/users/` (кроме me) | нет | да |
| `PATCH /providers/{code}` | нет | да |
| mailings / templates / stats / GET providers | да | да |

Данные рассылок/шаблонов/статистики **общие** (без фильтра по владельцу).

---

## Ошибки auth

| HTTP | `detail` | Когда |
|------|----------|--------|
| 401 | `Unauthorized` | Нет/неверный Basic Auth, неактивный user |
| 403 | `Forbidden` | Нужен admin |
| 409 | `Email already exists` | Конфликт email |
| 409 | `Cannot demote or deactivate the last active admin` | Защита последнего admin |
| 422 | `At least one field must be set` | Пустой PATCH |

Swagger: `/docs` → тег **users**.
