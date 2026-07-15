# i18n.py — переводы RU/UK/EN + переключатель языка
import streamlit as st

DEFAULT_LANG = "ru"
LANG_LABELS = {"ru": "РУ", "uk": "УКР", "en": "EN"}

# Ключ: {"ru": "...", "uk": "...", "en": "..."}
TRANSLATIONS = {
    # --- навигация / app.py ---
    "app.page_title": {
        "ru": "Кабинет Demand & Supply — Dnipro-M",
        "uk": "Кабінет Demand & Supply — Dnipro-M",
        "en": "Demand & Supply Cabinet — Dnipro-M",
    },
    "nav.section": {
        "ru": "Кабинет Demand & Supply",
        "uk": "Кабінет Demand & Supply",
        "en": "Demand & Supply Cabinet",
    },
    "nav.home": {"ru": "Обзор", "uk": "Огляд", "en": "Overview"},
    "nav.stock": {"ru": "Остатки", "uk": "Залишки", "en": "Stock"},
    "nav.incidents": {"ru": "Инциденты", "uk": "Інциденти", "en": "Incidents"},
    "nav.reorder": {"ru": "Автозаказ", "uk": "Автозамовлення", "en": "Reorder"},
    "nav.forecast": {"ru": "Прогноз", "uk": "Прогноз", "en": "Forecast"},

    # --- общие элементы ---
    "common.loading": {"ru": "Загрузка данных...", "uk": "Завантаження даних...", "en": "Loading data..."},
    "common.no_data": {"ru": "Нет данных", "uk": "Немає даних", "en": "No data"},
    "common.refresh": {"ru": "Обновить", "uk": "Оновити", "en": "Refresh"},
    "common.filter": {"ru": "Фильтр", "uk": "Фільтр", "en": "Filter"},
    "common.all": {"ru": "Все", "uk": "Всі", "en": "All"},
    "common.country": {"ru": "Страна", "uk": "Країна", "en": "Country"},
    "common.warehouse": {"ru": "Склад", "uk": "Склад", "en": "Warehouse"},
    "common.sku": {"ru": "Артикул", "uk": "Артикул", "en": "SKU"},
    "common.quantity": {"ru": "Количество", "uk": "Кількість", "en": "Quantity"},
    "common.date": {"ru": "Дата", "uk": "Дата", "en": "Date"},
    "common.status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "common.confirm": {"ru": "Подтвердить", "uk": "Підтвердити", "en": "Confirm"},
    "common.cancel": {"ru": "Отмена", "uk": "Скасувати", "en": "Cancel"},
    "common.language_label": {"ru": "Смена языка", "uk": "Зміна мови", "en": "Change language"},

    # --- 1_Stock.py ---
    "stock.title": {"ru": "Остатки", "uk": "Залишки", "en": "Stock"},
    "stock.caption": {
        "ru": "Консолидация по складам: Amazon FBA (по странам) + собственные/3PL",
        "uk": "Консолідація по складах: Amazon FBA (по країнах) + власні/3PL",
        "en": "Consolidated by warehouse: Amazon FBA (by country) + own/3PL",
    },

    "stock.other": {"ru": "Прочее", "uk": "Інше", "en": "Other"},
    "stock.cat.amoladora": {"ru": "Amoladoras (болгарки)", "uk": "Amoladoras (кутові шліфмашини)", "en": "Amoladoras (angle grinders)"},
    "stock.cat.martillo": {"ru": "Martillos (перфораторы)", "uk": "Martillos (перфоратори)", "en": "Martillos (rotary hammers)"},
    "stock.cat.taladro": {"ru": "Taladros (дрели/шуруповёрты)", "uk": "Taladros (дрилі/шуруповерти)", "en": "Taladros (drills/drivers)"},
    "stock.cat.destornillador": {"ru": "Destornilladores (отвёртки)", "uk": "Destornilladores (викрутки)", "en": "Destornilladores (screwdrivers)"},
    "stock.cat.motosierra": {"ru": "Motosierras (пилы)", "uk": "Motosierras (пили)", "en": "Motosierras (chainsaws)"},
    "stock.cat.sierra": {"ru": "Sierras (пилы)", "uk": "Sierras (пили)", "en": "Sierras (saws)"},
    "stock.cat.soldador": {"ru": "Soldadores (сварка)", "uk": "Soldadores (зварювання)", "en": "Soldadores (welders)"},
    "stock.cat.compresor": {"ru": "Compresores", "uk": "Compresores", "en": "Compresores (compressors)"},
    "stock.cat.bateria": {"ru": "Baterías / зарядки", "uk": "Baterías / зарядні", "en": "Baterías / chargers"},

    "stock.filter.warehouse": {"ru": "Склад (часть названия)", "uk": "Склад (частина назви)", "en": "Warehouse (partial name)"},
    "stock.filter.sku": {"ru": "SKU / артикул", "uk": "SKU / артикул", "en": "SKU"},
    "stock.filter.avail_status": {"ru": "Статус доступности", "uk": "Статус доступності", "en": "Availability status"},
    "stock.filter.all": {"ru": "Все", "uk": "Всі", "en": "All"},
    "stock.filter.country": {"ru": "Страна (FBA)", "uk": "Країна (FBA)", "en": "Country (FBA)"},
    "stock.filter.country_placeholder": {"ru": "Все страны", "uk": "Всі країни", "en": "All countries"},

    "stock.kpi.total_sku": {"ru": "Всего SKU", "uk": "Всього SKU", "en": "Total SKUs"},
    "stock.kpi.countries": {"ru": "Стран (FBA)", "uk": "Країн (FBA)", "en": "Countries (FBA)"},
    "stock.kpi.countries_help": {"ru": "Количество стран, где лежит товар на Amazon FBA", "uk": "Кількість країн, де лежить товар на Amazon FBA", "en": "Number of countries where the product sits in Amazon FBA"},
    "stock.kpi.total_qty": {"ru": "Суммарный остаток", "uk": "Сумарний залишок", "en": "Total stock"},
    "stock.kpi.median": {"ru": "Медиана на SKU", "uk": "Медіана на SKU", "en": "Median per SKU"},
    "stock.kpi.low_stock": {"ru": "SKU с остатком ≤ 3", "uk": "SKU із залишком ≤ 3", "en": "SKUs with stock ≤ 3"},
    "stock.kpi.low_stock_help": {"ru": "Кандидаты на пополнение (сумма по всем странам)", "uk": "Кандидати на поповнення (сума по всіх країнах)", "en": "Replenishment candidates (summed across all countries)"},

    "stock.burn_title": {"ru": "🔥 Минимальные остатки — кандидаты на пополнение", "uk": "🔥 Мінімальні залишки — кандидати на поповнення", "en": "🔥 Minimum stock — replenishment candidates"},
    "stock.burn_none": {"ru": "нет в наличии", "uk": "немає в наявності", "en": "out of stock"},

    "stock.tab.overview": {"ru": "📊 Обзор", "uk": "📊 Огляд", "en": "📊 Overview"},
    "stock.tab.abc": {"ru": "🅰️ ABC-анализ", "uk": "🅰️ ABC-аналіз", "en": "🅰️ ABC analysis"},
    "stock.tab.categories": {"ru": "🧰 Категории", "uk": "🧰 Категорії", "en": "🧰 Categories"},
    "stock.tab.countries": {"ru": "🌍 По странам", "uk": "🌍 По країнах", "en": "🌍 By country"},
    "stock.tab.table": {"ru": "📋 Таблица", "uk": "📋 Таблиця", "en": "📋 Table"},

    "stock.ov.top15_title": {"ru": "Топ-15 SKU по остатку (сумма по всем странам)", "uk": "Топ-15 SKU за залишком (сума по всіх країнах)", "en": "Top 15 SKUs by stock (summed across all countries)"},
    "stock.ov.unit_short": {"ru": "шт", "uk": "шт", "en": "pcs"},
    "stock.ov.by_status_title": {"ru": "Остаток по статусу доступности", "uk": "Залишок за статусом доступності", "en": "Stock by availability status"},
    "stock.ov.dist_title": {"ru": "Распределение остатка по SKU", "uk": "Розподіл залишку за SKU", "en": "Stock distribution by SKU"},
    "stock.ov.dist_xaxis": {"ru": "шт на SKU", "uk": "шт на SKU", "en": "pcs per SKU"},

    "stock.abc.class_label": {"ru": "Класс {cls}", "uk": "Клас {cls}", "en": "Class {cls}"},
    "stock.abc.sku_count": {"ru": "{n} SKU", "uk": "{n} SKU", "en": "{n} SKUs"},
    "stock.abc.pct_of_stock": {"ru": "{pct:.0f}% остатка", "uk": "{pct:.0f}% залишку", "en": "{pct:.0f}% of stock"},
    "stock.abc.pareto_title": {"ru": "Парето: вклад SKU в суммарный остаток", "uk": "Парето: внесок SKU у сумарний залишок", "en": "Pareto: SKU contribution to total stock"},
    "stock.abc.qty_legend": {"ru": "Остаток, шт", "uk": "Залишок, шт", "en": "Stock, pcs"},
    "stock.abc.cum_pct_legend": {"ru": "Накопленный %", "uk": "Накопичений %", "en": "Cumulative %"},
    "stock.abc.hover_click_hint": {"ru": "Кликни — карточка товара со ссылкой", "uk": "Клікни — картка товару з посиланням", "en": "Click — product card with link"},
    "stock.abc.stock_word": {"ru": "Остаток", "uk": "Залишок", "en": "Stock"},
    "stock.abc.yaxis_pct": {"ru": "накопленный %", "uk": "накопичений %", "en": "cumulative %"},
    "stock.abc.xaxis": {"ru": "SKU (по убыванию остатка)", "uk": "SKU (за спаданням залишку)", "en": "SKU (descending stock)"},
    "stock.abc.total_stock": {"ru": "Остаток (всего)", "uk": "Залишок (всього)", "en": "Stock (total)"},
    "stock.abc.class_word": {"ru": "Класс", "uk": "Клас", "en": "Class"},
    "stock.abc.open_amazon": {"ru": "Открыть на Amazon ↗", "uk": "Відкрити на Amazon ↗", "en": "Open on Amazon ↗"},
    "stock.abc.by_country_prefix": {"ru": "По странам:", "uk": "По країнах:", "en": "By country:"},
    "stock.abc.click_hint": {"ru": "💡 Кликни по столбику — появится карточка товара со ссылкой на листинг", "uk": "💡 Клікни по стовпчику — з'явиться картка товару з посиланням на лістинг", "en": "💡 Click a bar — a product card with a listing link will appear"},
    "stock.abc.footer_note": {
        "ru": "A — SKU, дающие 80% остатка; B — следующие 15%; C — хвост. Когда подключим продажи, пересчитаем ABC по velocity — это будет честнее.",
        "uk": "A — SKU, що дають 80% залишку; B — наступні 15%; C — хвіст. Коли підключимо продажі, перерахуємо ABC за velocity — це буде чесніше.",
        "en": "A — SKUs contributing 80% of stock; B — next 15%; C — the tail. Once sales data is connected, we'll recompute ABC by velocity for a fairer split.",
    },

    "stock.cat.treemap_title": {"ru": "Остаток по категориям инструмента", "uk": "Залишок за категоріями інструменту", "en": "Stock by tool category"},
    "stock.cat.sku_word": {"ru": "SKU", "uk": "SKU", "en": "SKU"},
    "stock.cat.power_scatter_title": {"ru": "Мощность (W) vs остаток — где сидит сток", "uk": "Потужність (W) vs залишок — де сидить сток", "en": "Power (W) vs stock — where stock sits"},
    "stock.cat.power_xaxis": {"ru": "Мощность, W", "uk": "Потужність, W", "en": "Power, W"},
    "stock.cat.qty_yaxis": {"ru": "Остаток, шт", "uk": "Залишок, шт", "en": "Stock, pcs"},

    "stock.ctr.by_country_title": {"ru": "Остаток по странам FBA", "uk": "Залишок по країнах FBA", "en": "Stock by FBA country"},
    "stock.ctr.metric_help": {"ru": "{n} SKU", "uk": "{n} SKU", "en": "{n} SKUs"},
    "stock.ctr.bar_title": {"ru": "Остаток по странам", "uk": "Залишок по країнах", "en": "Stock by country"},
    "stock.ctr.country_axis": {"ru": "Страна", "uk": "Країна", "en": "Country"},
    "stock.ctr.matrix_title": {"ru": "Матрица SKU × страна (топ-20 по остатку)", "uk": "Матриця SKU × країна (топ-20 за залишком)", "en": "SKU × country matrix (top 20 by stock)"},
    "stock.ctr.click_hint": {"ru": "💡 Кликни по ячейке — увидишь товар целиком и остаток по всем странам", "uk": "💡 Клікни по комірці — побачиш товар цілком і залишок по всіх країнах", "en": "💡 Click a cell — see the full product and stock across all countries"},
    "stock.ctr.map_note": {
        "ru": "Пусто/светлое = товара нет или мало в этой стране. Топ-20 — для наглядности карты. Полная таблица со всеми SKU — ниже.",
        "uk": "Порожньо/світле = товару немає або мало в цій країні. Топ-20 — для наочності карти. Повна таблиця з усіма SKU — нижче.",
        "en": "Empty/light = no or little stock in that country. Top 20 is for map clarity. The full table with all SKUs is below.",
    },
    "stock.ctr.full_table_title": {"ru": "Полная таблица: все SKU × страны", "uk": "Повна таблиця: всі SKU × країни", "en": "Full table: all SKUs × countries"},
    "stock.ctr.col_sku": {"ru": "SKU", "uk": "SKU", "en": "SKU"},
    "stock.ctr.col_product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "stock.ctr.col_total": {"ru": "Всего", "uk": "Всього", "en": "Total"},
    "stock.ctr.total_row": {"ru": "ИТОГО", "uk": "РАЗОМ", "en": "TOTAL"},
    "stock.ctr.download_matrix": {"ru": "⬇️ Скачать полную матрицу CSV", "uk": "⬇️ Завантажити повну матрицю CSV", "en": "⬇️ Download full matrix CSV"},

    "stock.tbl.view_mode": {"ru": "Вид таблицы", "uk": "Вигляд таблиці", "en": "Table view"},
    "stock.tbl.view_by_product": {"ru": "По товару (сумма по странам)", "uk": "За товаром (сума по країнах)", "en": "By product (summed across countries)"},
    "stock.tbl.view_by_product_country": {"ru": "По товару и стране (детально)", "uk": "За товаром і країною (детально)", "en": "By product and country (detailed)"},
    "stock.tbl.col_total_stock": {"ru": "Остаток (всего)", "uk": "Залишок (всього)", "en": "Stock (total)"},
    "stock.tbl.col_countries": {"ru": "Стран", "uk": "Країн", "en": "Countries"},
    "stock.tbl.col_countries_help": {"ru": "В скольких странах FBA лежит товар", "uk": "У скількох країнах FBA лежить товар", "en": "In how many FBA countries the product sits"},
    "stock.tbl.col_listing": {"ru": "Листинг", "uk": "Лістинг", "en": "Listing"},
    "stock.tbl.col_listing_text": {"ru": "Открыть ↗", "uk": "Відкрити ↗", "en": "Open ↗"},
    "stock.tbl.col_category": {"ru": "Категория", "uk": "Категорія", "en": "Category"},
    "stock.tbl.col_stock": {"ru": "Остаток", "uk": "Залишок", "en": "Stock"},
    "stock.tbl.col_country": {"ru": "Страна", "uk": "Країна", "en": "Country"},
    "stock.tbl.col_status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "stock.tbl.col_snapshot": {"ru": "Снапшот", "uk": "Знімок", "en": "Snapshot"},
    "stock.tbl.download_detail": {"ru": "⬇️ Скачать CSV (детально, по странам)", "uk": "⬇️ Завантажити CSV (детально, по країнах)", "en": "⬇️ Download CSV (detailed, by country)"},

    "stock.no_data_warning": {"ru": "Нет данных в kabinet_data.stock_local", "uk": "Немає даних у kabinet_data.stock_local", "en": "No data in kabinet_data.stock_local"},

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
}


def init_lang():
    """Инициализация языка в session_state (вызывать в начале каждой страницы)."""
    if "lang" not in st.session_state:
        st.session_state.lang = DEFAULT_LANG


def get_lang() -> str:
    init_lang()
    return st.session_state.lang


def t(key: str) -> str:
    """Возвращает перевод по ключу для текущего языка. Если ключа нет — возвращает сам key."""
    init_lang()
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(st.session_state.lang, entry.get(DEFAULT_LANG, key))


def language_toggle(location=None):
    """Переключатель РУ/УКР/EN, рендерится в сайдбаре по умолчанию."""
    init_lang()
    loc = location or st.sidebar
    order = ["ru", "uk", "en"]
    current = st.session_state.lang

    loc.caption(t("common.language_label"))

    if hasattr(loc, "segmented_control"):
        choice = loc.segmented_control(
            "Язык",
            options=[LANG_LABELS[l] for l in order],
            default=LANG_LABELS[current],
            label_visibility="collapsed",
            key="lang_toggle_widget",
        )
        choice = choice or LANG_LABELS[current]
    else:
        choice = loc.radio(
            "Язык",
            options=[LANG_LABELS[l] for l in order],
            index=order.index(current),
            horizontal=True,
            label_visibility="collapsed",
            key="lang_toggle_widget",
        )

    new_lang = order[[LANG_LABELS[l] for l in order].index(choice)]
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
