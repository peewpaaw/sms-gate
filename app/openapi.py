OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "users",
        "description": "Профиль текущего пользователя и управление пользователями (CRUD — только admin).",
    },
    {
        "name": "mailings",
        "description": "Создание и отправка SMS-рассылок.",
    },
    {
        "name": "templates",
        "description": "Шаблоны текста сообщений для рассылок.",
    },
    {
        "name": "providers",
        "description": "Доступные SMS-провайдеры.",
    },
    {
        "name": "stats",
        "description": "Агрегированная статистика для дашбордов.",
    },
]
