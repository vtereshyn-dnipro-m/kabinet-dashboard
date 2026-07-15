# --- home.py ---
    "home.title": {"ru": "Кабинет Demand & Supply", "uk": "Кабінет Demand & Supply", "en": "Demand & Supply Cabinet"},
    "home.subtitle": {
        "ru": "Система сама находит проблемы и приносит их вам",
        "uk": "Система сама знаходить проблеми і приносить їх вам",
        "en": "The system finds problems and brings them to you",
    },
    "home.db_error": {"ru": "Нет подключения к базе", "uk": "Немає підключення до бази", "en": "No database connection"},

    "home.metric.health": {"ru": "💚 Здоровье каталога", "uk": "💚 Здоров'я каталогу", "en": "💚 Catalog health"},
    "home.metric.health_help": {
        "ru": "Доля SKU с достаточным запасом (остаток > 3). Данные на {snap}",
        "uk": "Частка SKU з достатнім запасом (залишок > 3). Дані на {snap}",
        "en": "Share of SKUs with sufficient stock (qty > 3). Data as of {snap}",
    },
    "home.metric.sku_controlled": {"ru": "SKU под контролем", "uk": "SKU під контролем", "en": "SKUs monitored"},
    "home.metric.total_stock": {"ru": "Суммарный остаток", "uk": "Сумарний залишок", "en": "Total stock"},
    "home.metric.open_incidents": {"ru": "Открытых инцидентов", "uk": "Відкритих інцидентів", "en": "Open incidents"},
    "home.metric.resolved_auto": {"ru": "Решено автоматически", "uk": "Вирішено автоматично", "en": "Auto-resolved"},
    "home.metric.resolved_auto_help": {
        "ru": "Система сама закрыла после пополнения стока",
        "uk": "Система сама закрила після поповнення стоку",
        "en": "Auto-closed by the system after stock replenishment",
    },
    "home.critical_suffix": {"ru": "critical", "uk": "critical", "en": "critical"},

    "home.attention_title": {"ru": "🔥 Требуют внимания первыми", "uk": "🔥 Потребують уваги першими", "en": "🔥 Needs attention first"},
    "home.unit_pcs": {"ru": "шт", "uk": "шт", "en": "pcs"},
    "home.link.full_journal": {"ru": "Весь журнал →", "uk": "Весь журнал →", "en": "Full log →"},

    "home.dist_title": {"ru": "Распределение запаса", "uk": "Розподіл запасу", "en": "Stock distribution"},
    "home.dist.critical": {"ru": "критично (≤3)", "uk": "критично (≤3)", "en": "critical (≤3)"},
    "home.dist.low": {"ru": "мало (4–10)", "uk": "мало (4–10)", "en": "low (4–10)"},
    "home.dist.normal": {"ru": "норма (>10)", "uk": "норма (>10)", "en": "normal (>10)"},

    "home.top_title": {"ru": "Топ запаса (куда вложены деньги)", "uk": "Топ запасу (куди вкладено гроші)", "en": "Top stock (where money is tied up)"},
    "home.link.full_analytics": {"ru": "Полная аналитика →", "uk": "Повна аналітика →", "en": "Full analytics →"},

    "home.how_title": {"ru": "⚙️ Как устроена система", "uk": "⚙️ Як влаштована система", "en": "⚙️ How the system works"},
    "home.how_body": {
        "ru": (
            "```\nDatabricks (данные)  →  Loader (правила)  →  Lakebase (состояние)  →  этот дашборд\n```\n"
            "Каждый день система автоматически: обновляет остатки → проверяет правила "
            "(остаток = 0, остаток ≤ 3) → открывает инциденты по новым проблемам → "
            "закрывает инциденты по решённым. Человек нужен там, где нужно решение, "
            "а не там, где нужно смотреть в таблицы."
        ),
        "uk": (
            "```\nDatabricks (дані)  →  Loader (правила)  →  Lakebase (стан)  →  цей дашборд\n```\n"
            "Щодня система автоматично: оновлює залишки → перевіряє правила "
            "(залишок = 0, залишок ≤ 3) → відкриває інциденти за новими проблемами → "
            "закриває інциденти за вирішеними. Людина потрібна там, де потрібне рішення, "
            "а не там, де потрібно дивитись у таблиці."
        ),
        "en": (
            "```\nDatabricks (data)  →  Loader (rules)  →  Lakebase (state)  →  this dashboard\n```\n"
            "Every day the system automatically: updates stock → checks rules "
            "(qty = 0, qty ≤ 3) → opens incidents for new problems → "
            "closes incidents for resolved ones. A human is only needed where a decision "
            "is required, not to stare at tables."
        ),
    },

    "home.roadmap_title": {"ru": "🗺️ Что дальше (roadmap)", "uk": "🗺️ Що далі (roadmap)", "en": "🗺️ What's next (roadmap)"},
    "home.roadmap_table": {
        "ru": (
            "| Этап | Что даёт | Статус |\n|---|---|---|\n"
            "| Правила по остаткам | инциденты low stock / out of stock | ✅ в проде |\n"
            "| История снапшотов | тренды остатков, динамика инцидентов | 🔄 копится |\n"
            "| Данные продаж | умные пороги (days of cover), прогноз спроса | 🔜 следующий шаг |\n"
            "| Поставки в пути | инциденты «зависшая поставка», точный дозаказ | 🔜 |\n"
            "| Новые каналы | Shopify, Leroy Merlin (Mirakl) в тот же контур | 🔜 |\n"
            "| ИИ-агент | триаж инцидентов, черновики заказов, алерты в Telegram | 🔜 |"
        ),
        "uk": (
            "| Етап | Що дає | Статус |\n|---|---|---|\n"
            "| Правила по залишках | інциденти low stock / out of stock | ✅ в проді |\n"
            "| Історія знімків | тренди залишків, динаміка інцидентів | 🔄 накопичується |\n"
            "| Дані продажів | розумні пороги (days of cover), прогноз попиту | 🔜 наступний крок |\n"
            "| Поставки в дорозі | інциденти «зависла поставка», точне дозамовлення | 🔜 |\n"
            "| Нові канали | Shopify, Leroy Merlin (Mirakl) у тому ж контурі | 🔜 |\n"
            "| ШІ-агент | тріаж інцидентів, чернетки замовлень, алерти в Telegram | 🔜 |"
        ),
        "en": (
            "| Stage | What it gives | Status |\n|---|---|---|\n"
            "| Stock rules | low stock / out of stock incidents | ✅ in prod |\n"
            "| Snapshot history | stock trends, incident dynamics | 🔄 accumulating |\n"
            "| Sales data | smart thresholds (days of cover), demand forecast | 🔜 next step |\n"
            "| Shipments in transit | \"stuck shipment\" incidents, precise reorder | 🔜 |\n"
            "| New channels | Shopify, Leroy Merlin (Mirakl) in the same pipeline | 🔜 |\n"
            "| AI agent | incident triage, order drafts, Telegram alerts | 🔜 |"
        ),
    },

    "home.diag_title": {"ru": "🔧 Диагностика", "uk": "🔧 Діагностика", "en": "🔧 Diagnostics"},
    "home.diag_ok": {"ru": "✅ Lakebase доступен", "uk": "✅ Lakebase доступний", "en": "✅ Lakebase reachable"},
    "home.diag_error": {"ru": "❌ Ошибка подключения", "uk": "❌ Помилка підключення", "en": "❌ Connection error"},
    "home.diag_stock_line": {
        "ru": "stock_local: {rows} строк, последний снапшот {date}",
        "uk": "stock_local: {rows} рядків, останній знімок {date}",
        "en": "stock_local: {rows} rows, latest snapshot {date}",
    },
    "home.diag_incidents_line": {
        "ru": "incidents: последняя запись {date}",
        "uk": "incidents: останній запис {date}",
        "en": "incidents: latest record {date}",
    },
