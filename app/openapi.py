OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "auth",
        "description": "Аутентификация по заголовку `X-API-Key`.",
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
]
