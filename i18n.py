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
    "nav.money": {"ru": "Деньги", "uk": "Гроші", "en": "Money"},
    "nav.dictionaries": {"ru": "Справочники", "uk": "Довідники", "en": "Dictionaries"},

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
    "stock.ctr.click_hint": {"ru": "💡 Кликни по ячейке — увидишь товар целиком и остаток по всем странам", "uk": "💡 Клікні по комірці — побачиш товар цілком і залишок по всіх країнах", "en": "💡 Click a cell — see the full product and stock across all countries"},
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

    # --- дефекты / возвраты ---
    "stock.ctr.defects_title": {"ru": "⚠️ Дефекты / возвраты", "uk": "⚠️ Дефекти / повернення", "en": "⚠️ Defects / returns"},
    "stock.ctr.defects_caption": {
        "ru": "Позиции с браком или возвратом (Amazon removal/grade). Не в остатках и не в автозаказе.",
        "uk": "Позиції з браком або поверненням (Amazon removal/grade). Не в залишках і не в автозамовленні.",
        "en": "Damaged or returned items (Amazon removal/grade). Excluded from stock and reorder.",
    },
    "stock.ctr.defects_download": {"ru": "⬇️ Скачать дефекты CSV", "uk": "⬇️ Завантажити дефекти CSV", "en": "⬇️ Download defects CSV"},
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
    # --- 1_Stock.py: квоты, выделенные на каналы продаж ---
    "stock.kpi.total_qty_help": {
        "ru": "Физический остаток на складах. Квоты, выделенные на каналы продаж, не входят.",
        "uk": "Фізичний залишок на складах. Квоти, виділені на канали продажів, не входять.",
        "en": "Physical stock in warehouses. Quotas allocated to sales channels are excluded.",
    },
    "stock.channels.title": {
        "ru": "📤 Выделено на каналы продаж ({n} шт)",
        "uk": "📤 Виділено на канали продажів ({n} шт)",
        "en": "📤 Allocated to sales channels ({n} pcs)",
    },
    "stock.channels.caption": {
        "ru": "Квота, выставленная на канал из складского остатка (например, офферы Leroy Merlin — "
              "часть мадридского стока). Это не дополнительный товар: он уже учтён в остатках складов выше.",
        "uk": "Квота, виставлена на канал зі складського залишку (наприклад, оффери Leroy Merlin — "
              "частина мадридського стоку). Це не додатковий товар: він уже врахований у залишках складів вище.",
        "en": "Quantity listed on a channel out of existing warehouse stock (e.g. Leroy Merlin offers are "
              "part of the Madrid stock). This is not additional goods — it's already counted above.",
    },
    "stock.channels.col_channel": {"ru": "Канал", "uk": "Канал", "en": "Channel"},
    "stock.channels.col_qty": {"ru": "Выделено, шт", "uk": "Виділено, шт", "en": "Allocated, pcs"},
    "stock.channels.download": {
        "ru": "⬇️ Скачать квоты каналов CSV",
        "uk": "⬇️ Завантажити квоти каналів CSV",
        "en": "⬇️ Download channel quotas CSV",
    },
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

    # --- 2_Incidents.py ---
    "inc.title": {"ru": "Инциденты", "uk": "Інциденти", "en": "Incidents"},
    "inc.caption": {
        "ru": "Единый журнал проблем со всех разделов системы: что требует действия прямо сейчас. Источники: остатки (активно) · поставки и продажи (скоро)",
        "uk": "Єдиний журнал проблем з усіх розділів системи: що потребує дії прямо зараз. Джерела: залишки (активно) · поставки та продажі (скоро)",
        "en": "A unified log of problems from all sections of the system: what needs action right now. Sources: stock (active) · shipments and sales (soon)",
    },
    "inc.how_title": {"ru": "ℹ️ Как это работает", "uk": "ℹ️ Як це працює", "en": "ℹ️ How this works"},
    "inc.how_body": {
        "ru": (
            "Инциденты создаются **автоматически** при каждом обновлении данных:\n\n"
            "| Тип | Правило | Источник | Статус |\n|---|---|---|---|\n"
            "| 🔴 out_of_stock | остаток = 0 | Остатки | ✅ активно |\n"
            "| 🟡 low_stock | остаток ≤ 3 шт | Остатки | ✅ активно |\n"
            "| 🟠 stuck_shipment | поставка без движения | Поставки | 🔜 скоро |\n"
            "| 🟣 sales_anomaly | резкий рост/падение продаж | Продажи | 🔜 скоро |\n\n"
            "Когда проблема исчезает (например, сток пополнен) — инцидент закрывается сам."
        ),
        "uk": (
            "Інциденти створюються **автоматично** під час кожного оновлення даних:\n\n"
            "| Тип | Правило | Джерело | Статус |\n|---|---|---|---|\n"
            "| 🔴 out_of_stock | залишок = 0 | Залишки | ✅ активно |\n"
            "| 🟡 low_stock | залишок ≤ 3 шт | Залишки | ✅ активно |\n"
            "| 🟠 stuck_shipment | поставка без руху | Поставки | 🔜 скоро |\n"
            "| 🟣 sales_anomaly | різке зростання/падіння продажів | Продажі | 🔜 скоро |\n\n"
            "Коли проблема зникає (наприклад, сток поповнено) — інцидент закривається сам."
        ),
        "en": (
            "Incidents are created **automatically** on every data update:\n\n"
            "| Type | Rule | Source | Status |\n|---|---|---|---|\n"
            "| 🔴 out_of_stock | qty = 0 | Stock | ✅ active |\n"
            "| 🟡 low_stock | qty ≤ 3 pcs | Stock | ✅ active |\n"
            "| 🟠 stuck_shipment | shipment not moving | Shipments | 🔜 soon |\n"
            "| 🟣 sales_anomaly | sharp sales rise/drop | Sales | 🔜 soon |\n\n"
            "When the problem disappears (e.g. stock replenished) — the incident closes itself."
        ),
    },
    "inc.empty": {
        "ru": "Инцидентов пока нет. Либо всё хорошо, либо генератор ещё не запускался 🙂",
        "uk": "Інцидентів поки немає. Або все добре, або генератор ще не запускався 🙂",
        "en": "No incidents yet. Either everything's fine, or the generator hasn't run yet 🙂",
    },
    "inc.filter.severity": {"ru": "Уровень серьёзности", "uk": "Рівень серйозності", "en": "Severity level"},
    "inc.filter.status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "inc.filter.type": {"ru": "Тип", "uk": "Тип", "en": "Type"},
    "inc.filter.search": {"ru": "Поиск (SKU / текст)", "uk": "Пошук (SKU / текст)", "en": "Search (SKU / text)"},
    "inc.filter.search_placeholder": {"ru": "например 22635000", "uk": "наприклад 22635000", "en": "e.g. 22635000"},
    "inc.sev.critical": {"ru": "Critical", "uk": "Critical", "en": "Critical"},
    "inc.sev.high": {"ru": "High", "uk": "High", "en": "High"},
    "inc.sev.warning": {"ru": "Warning", "uk": "Warning", "en": "Warning"},
    "inc.sev.low": {"ru": "Low", "uk": "Low", "en": "Low"},
    "inc.sev.info": {"ru": "Info", "uk": "Info", "en": "Info"},
    "inc.sev_help.critical": {
        "ru": "Продажи уже остановлены: остаток = 0. Реагировать немедленно.",
        "uk": "Продажі вже зупинені: залишок = 0. Реагувати негайно.",
        "en": "Sales already stopped: stock = 0. React immediately.",
    },
    "inc.sev_help.high": {
        "ru": "Высокий риск, требует реакции в ближайшие дни.",
        "uk": "Високий ризик, потребує реакції найближчими днями.",
        "en": "High risk, needs a response within the next few days.",
    },
    "inc.sev_help.warning": {
        "ru": "Запас на исходе: остаток ≤ 3 шт. Спланировать пополнение.",
        "uk": "Запас на завершенні: залишок ≤ 3 шт. Спланувати поповнення.",
        "en": "Stock running low: qty ≤ 3 pcs. Plan a replenishment.",
    },
    "inc.sev_help.low": {
        "ru": "Запас на исходе: остаток ≤ 3 шт. Спланировать пополнение.",
        "uk": "Запас на завершенні: залишок ≤ 3 шт. Спланувати поповнення.",
        "en": "Stock running low: qty ≤ 3 pcs. Plan a replenishment.",
    },
    "inc.sev_help.info": {
        "ru": "Информационное уведомление, действия по ситуации.",
        "uk": "Інформаційне повідомлення, дії за ситуацією.",
        "en": "Informational notice, act as needed.",
    },
    "inc.kpi.open": {"ru": "Открытых", "uk": "Відкритих", "en": "Open"},
    "inc.kpi.open_help": {
        "ru": "Инциденты со статусом open — требуют действия. Закрываются автоматически, когда проблема исчезает из данных.",
        "uk": "Інциденти зі статусом open — потребують дії. Закриваються автоматично, коли проблема зникає з даних.",
        "en": "Incidents with status open — need action. Auto-close when the problem disappears from the data.",
    },
    "inc.kpi.none_help": {
        "ru": "Инцидентов других уровней сейчас нет.",
        "uk": "Інцидентів інших рівнів зараз немає.",
        "en": "No incidents of other levels right now.",
    },
    "inc.kpi.resolved": {"ru": "Закрыто (всего)", "uk": "Закрито (всього)", "en": "Resolved (total)"},
    "inc.kpi.resolved_help": {
        "ru": "Автозакрытые: сток пополнился — система сама перевела инцидент в resolved. Показатель того, что проблемы реально решаются.",
        "uk": "Автозакриті: сток поповнився — система сама перевела інцидент у resolved. Показник того, що проблеми реально вирішуються.",
        "en": "Auto-resolved: stock was replenished — the system moved the incident to resolved itself. A sign problems are actually getting fixed.",
    },
    "inc.burning_title": {"ru": "🔥 Требуют внимания первыми", "uk": "🔥 Потребують уваги першими", "en": "🔥 Needs attention first"},
    "inc.age_delta_open": {"ru": "-{n} дн. открыт", "uk": "-{n} дн. відкрито", "en": "-{n}d open"},
    "inc.age_new": {"ru": "новый", "uk": "новий", "en": "new"},
    "inc.status_word": {"ru": "статус", "uk": "статус", "en": "status"},
    "inc.chart.by_type_title": {"ru": "Открытые по типу", "uk": "Відкриті за типом", "en": "Open by type"},
    "inc.age.today": {"ru": "сегодня", "uk": "сьогодні", "en": "today"},
    "inc.age.1_2d": {"ru": "1–2 дня", "uk": "1–2 дні", "en": "1–2 days"},
    "inc.age.3_6d": {"ru": "3–6 дней", "uk": "3–6 днів", "en": "3–6 days"},
    "inc.age.1_2w": {"ru": "1–2 недели", "uk": "1–2 тижні", "en": "1–2 weeks"},
    "inc.age.gt2w": {"ru": "> 2 недель", "uk": "> 2 тижнів", "en": "> 2 weeks"},
    "inc.chart.age_title": {"ru": "Возраст открытых (дней без реакции)", "uk": "Вік відкритих (днів без реакції)", "en": "Age of open incidents (days without response)"},
    "inc.chart.daily_title": {"ru": "Новые инциденты по дням", "uk": "Нові інциденти за днями", "en": "New incidents by day"},
    "inc.chart.dynamics_title": {"ru": "Динамика по дням", "uk": "Динаміка за днями", "en": "Daily dynamics"},
    "inc.chart.dynamics_caption": {
        "ru": "📈 Появится, когда накопится история за несколько дней. Включи расписание лоадера — и через неделю здесь будет тренд.",
        "uk": "📈 З'явиться, коли накопичиться історія за декілька днів. Увімкни розклад лоадера — і за тиждень тут буде тренд.",
        "en": "📈 Will appear once a few days of history accumulate. Turn on the loader schedule and there'll be a trend here within a week.",
    },
    "inc.tbl.col_created": {"ru": "Создан", "uk": "Створено", "en": "Created"},
    "inc.tbl.col_level": {"ru": "Уровень", "uk": "Рівень", "en": "Level"},
    "inc.tbl.col_type": {"ru": "Тип", "uk": "Тип", "en": "Type"},
    "inc.tbl.col_qty": {"ru": "Остаток", "uk": "Залишок", "en": "Stock"},
    "inc.tbl.col_qty_help": {"ru": "Актуальный остаток по последнему снапшоту", "uk": "Актуальний залишок за останнім знімком", "en": "Current stock as of the latest snapshot"},
    "inc.tbl.col_desc": {"ru": "Описание", "uk": "Опис", "en": "Description"},
    "inc.tbl.col_age": {"ru": "Дней", "uk": "Днів", "en": "Days"},
    "inc.tbl.col_age_help": {"ru": "Сколько дней инцидент открыт", "uk": "Скільки днів інцидент відкрито", "en": "How many days the incident has been open"},
    "inc.tbl.col_status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "inc.btn.acknowledge": {"ru": "🎯 Взять в работу ({n})", "uk": "🎯 Взяти в роботу ({n})", "en": "🎯 Acknowledge ({n})"},
    "inc.btn.resolve": {"ru": "✅ Закрыть вручную ({n})", "uk": "✅ Закрити вручну ({n})", "en": "✅ Resolve manually ({n})"},
    "inc.hint.select_rows": {
        "ru": "Выбери строки галочками слева → «Взять в работу» пометит их как acknowledged, чтобы команда видела: кто-то уже занимается.",
        "uk": "Вибери рядки галочками зліва → «Взяти в роботу» позначить їх як acknowledged, щоб команда бачила: хтось вже займається.",
        "en": "Select rows with the checkboxes on the left → \"Acknowledge\" marks them as acknowledged, so the team can see someone's already on it.",
    },
    "inc.btn.download": {"ru": "⬇️ Скачать CSV", "uk": "⬇️ Завантажити CSV", "en": "⬇️ Download CSV"},

    # --- 3_Forecast.py ---
    "fc.title": {"ru": "Прогноз", "uk": "Прогноз", "en": "Forecast"},
    "fc.caption": {
        "ru": "Прогноз спроса и рекомендации по дозаказу",
        "uk": "Прогноз попиту та рекомендації щодо дозамовлення",
        "en": "Demand forecast and reorder recommendations",
    },
    "fc.kpi.at_risk": {"ru": "Товаров в зоне риска", "uk": "Товарів у зоні ризику", "en": "Products at risk"},
    "fc.kpi.at_risk_help": {
        "ru": "Запаса меньше, чем время поставки — успеть дозаказать",
        "uk": "Запасу менше, ніж час поставки — встигнути дозамовити",
        "en": "Less stock than lead time — reorder in time",
    },
    "fc.empty_title": {"ru": "🔜 Раздел готовится: ждёт подключения данных продаж.", "uk": "🔜 Розділ готується: чекає підключення даних продажів.", "en": "🔜 Section in progress: waiting for sales data connection."},
    "fc.empty_body": {
        "ru": (
            "**Как это будет работать:**\n\n"
            "| Что | Откуда |\n|---|---|\n"
            "| Скорость продаж (шт/день) | продажи Amazon из `dnipro_m` |\n"
            "| Days of cover | остаток ÷ скорость продаж |\n"
            "| Зона риска | запаса меньше, чем срок поставки |\n"
            "| Рекомендация дозаказа | суммой на N дней вперёд с учётом поставок в пути |\n\n"
            "Остатки уже собираются ежедневно — как только подключим продажи, "
            "прогноз включится автоматически."
        ),
        "uk": (
            "**Як це працюватиме:**\n\n"
            "| Що | Звідки |\n|---|---|\n"
            "| Швидкість продажів (шт/день) | продажі Amazon з `dnipro_m` |\n"
            "| Days of cover | залишок ÷ швидкість продажів |\n"
            "| Зона ризику | запасу менше, ніж термін поставки |\n"
            "| Рекомендація дозамовлення | сумою на N днів наперед з урахуванням поставок у дорозі |\n\n"
            "Залишки вже збираються щодня — щойно підключимо продажі, "
            "прогноз увімкнеться автоматично."
        ),
        "en": (
            "**How this will work:**\n\n"
            "| What | Source |\n|---|---|\n"
            "| Sales velocity (units/day) | Amazon sales from `dnipro_m` |\n"
            "| Days of cover | stock ÷ sales velocity |\n"
            "| Risk zone | less stock than lead time |\n"
            "| Reorder recommendation | a quantity for N days ahead, accounting for shipments in transit |\n\n"
            "Stock is already collected daily — once sales data is connected, "
            "the forecast will turn on automatically."
        ),
    },
    "fc.load_error": {"ru": "Не удалось загрузить прогноз: {e}", "uk": "Не вдалося завантажити прогноз: {e}", "en": "Failed to load forecast: {e}"},

    # --- 4_Reorder.py ---
    "ro.title": {"ru": "Автозаказ", "uk": "Автозамовлення", "en": "Reorder"},
    "ro.caption": {
        "ru": "Что и сколько заказать: скорость продаж × остаток × срок поставки. Система считает точку заказа сама.",
        "uk": "Що і скільки замовити: швидкість продажів × залишок × термін поставки. Система рахує точку замовлення сама.",
        "en": "What and how much to order: sales velocity × stock × lead time. The system calculates the reorder point itself.",
    },
    "ro.empty": {
        "ru": "Рекомендации ещё не рассчитаны. Запусти ячейку автозаказа в пайплайне.",
        "uk": "Рекомендації ще не розраховані. Запусти комірку автозамовлення в пайплайні.",
        "en": "Recommendations haven't been calculated yet. Run the reorder cell in the pipeline.",
    },
    "ro.urg.critical": {"ru": "Заказать срочно", "uk": "Замовити терміново", "en": "Order urgently"},
    "ro.urg.warning": {"ru": "Пора заказывать", "uk": "Час замовляти", "en": "Time to order"},
    "ro.urg.ok": {"ru": "В норме", "uk": "В нормі", "en": "OK"},
    "ro.kpi.critical": {"ru": "🔴 Заказать срочно", "uk": "🔴 Замовити терміново", "en": "🔴 Order urgently"},
    "ro.kpi.critical_help": {
        "ru": "Кончатся раньше, чем приедет поставка",
        "uk": "Закінчаться раніше, ніж приїде поставка",
        "en": "Will run out before the shipment arrives",
    },
    "ro.kpi.warning": {"ru": "🟡 Пора заказывать", "uk": "🟡 Час замовляти", "en": "🟡 Time to order"},
    "ro.kpi.total_qty": {"ru": "Всего к заказу, шт", "uk": "Всього до замовлення, шт", "en": "Total to order, pcs"},
    "ro.kpi.sku_controlled": {"ru": "SKU под контролем", "uk": "SKU під контролем", "en": "SKUs monitored"},
    "ro.priority_title": {"ru": "🔴 Требуют заказа в первую очередь", "uk": "🔴 Потребують замовлення в першу чергу", "en": "🔴 Needs ordering first"},
    "ro.priority.value": {"ru": "заказать {n}", "uk": "замовити {n}", "en": "order {n}"},
    "ro.priority.delta": {"ru": "хватит на {n:.0f} дн", "uk": "вистачить на {n:.0f} дн", "en": "lasts {n:.0f}d"},
    "ro.priority.help": {"ru": "{name} · продаётся {v:.1f}/день", "uk": "{name} · продається {v:.1f}/день", "en": "{name} · sells {v:.1f}/day"},
    "ro.filter.urgency": {"ru": "Срочность", "uk": "Терміновість", "en": "Urgency"},
    "ro.filter.search": {"ru": "Поиск SKU / товар", "uk": "Пошук SKU / товар", "en": "Search SKU / product"},
    "ro.filter.search_ph": {"ru": "напр. Amoladora", "uk": "напр. Amoladora", "en": "e.g. Amoladora"},
    "ro.filter.search_placeholder": {"ru": "напр. Amoladora", "uk": "напр. Amoladora", "en": "e.g. Amoladora"},
    "ro.tbl.col_urgency": {"ru": "Срочность", "uk": "Терміновість", "en": "Urgency"},
    "ro.tbl.col_sku": {"ru": "SKU", "uk": "SKU", "en": "SKU"},
    "ro.tbl.col_product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "ro.tbl.col_stock": {"ru": "Остаток", "uk": "Залишок", "en": "Stock"},
    "ro.tbl.col_velocity": {"ru": "Продаётся/день", "uk": "Продається/день", "en": "Sold/day"},
    "ro.tbl.col_days_left": {"ru": "Хватит, дней", "uk": "Вистачить, днів", "en": "Lasts, days"},
    "ro.tbl.col_days_left_help": {
        "ru": "На сколько дней хватит при текущей скорости продаж",
        "uk": "На скільки днів вистачить за поточної швидкості продажів",
        "en": "How many days it will last at the current sales velocity",
    },
    "ro.tbl.col_suggested": {"ru": "Заказать, шт", "uk": "Замовити, шт", "en": "Order, pcs"},
    "ro.tbl.col_suggested_help": {
        "ru": "Рекомендуемое количество к заказу",
        "uk": "Рекомендована кількість до замовлення",
        "en": "Recommended order quantity",
    },
    "ro.download_btn": {"ru": "⬇️ Скачать заказ ({n} SKU, {qty} шт)", "uk": "⬇️ Завантажити замовлення ({n} SKU, {qty} шт)", "en": "⬇️ Download order ({n} SKUs, {qty} pcs)"},
    "ro.how_title": {"ru": "ℹ️ Как считается автозаказ", "uk": "ℹ️ Як рахується автозамовлення", "en": "ℹ️ How the reorder is calculated"},
    "ro.how_body": {
        "ru": (
            "- **Скорость продаж** — среднее за последние 30 дней (из истории заказов)\n"
            "- **Хватит дней** = остаток / скорость продаж\n"
            "- **🔴 Заказать срочно** — хватит меньше, чем срок поставки (не успеваем)\n"
            "- **🟡 Пора заказывать** — остаток ниже точки заказа (срок поставки + страховой запас)\n"
            "- **Заказать, шт** — сколько нужно, чтобы покрыть спрос на 60 дней вперёд\n\n"
            "Параметры (срок поставки, страховой запас) пока общие — скоро вынесем в настройки, "
            "и посчитаем реальный срок поставки по каждому складу из истории поставок."
        ),
        "uk": (
            "- **Швидкість продажів** — середнє за останні 30 днів (з історії замовлень)\n"
            "- **Вистачить днів** = залишок / швидкість продажів\n"
            "- **🔴 Замовити терміново** — вистачить менше, ніж термін поставки (не встигаємо)\n"
            "- **🟡 Час замовляти** — залишок нижче точки замовлення (термін поставки + страховий запас)\n"
            "- **Замовити, шт** — скільки потрібно, щоб покрити попит на 60 днів наперед\n\n"
            "Параметри (термін поставки, страховий запас) поки загальні — скоро винесемо в налаштування, "
            "і порахуємо реальний термін поставки по кожному складу з історії поставок."
        ),
        "en": (
            "- **Sales velocity** — average over the last 30 days (from order history)\n"
            "- **Days left** = stock / sales velocity\n"
            "- **🔴 Order urgently** — will last less than the lead time (won't make it in time)\n"
            "- **🟡 Time to order** — stock below the reorder point (lead time + safety stock)\n"
            "- **Order, pcs** — how much is needed to cover demand for the next 60 days\n\n"
            "Parameters (lead time, safety stock) are still shared across all — soon they'll move into settings, "
            "and we'll compute the real lead time per warehouse from shipment history."
        ),
    },

    # --- 4_Reorder.py: переброска ---
    "ro.tr.title": {"ru": "🔄 Сначала — переброска", "uk": "🔄 Спочатку — переброс", "en": "🔄 First — transfer"},
    "ro.tr.caption": {
        "ru": "Товар горит на Amazon, но есть на своих складах или в других странах — перебросить дешевле, чем заказывать.",
        "uk": "Товар горить на Amazon, але є на власних складах або в інших країнах — перекинути дешевше, ніж замовляти.",
        "en": "Stock is critical on Amazon, but it's available in own warehouses or other countries — transferring is cheaper than ordering.",
    },
    "ro.tr.from_own": {"ru": "📦 Со своих складов", "uk": "📦 З власних складів", "en": "📦 From own warehouses"},
    "ro.tr.from_own_help": {"ru": "Переброска со складов Польши (ERP)", "uk": "Переброс зі складів Польщі (ERP)", "en": "Transfer from Poland warehouses (ERP)"},
    "ro.tr.from_fba": {"ru": "✈️ Между странами FBA", "uk": "✈️ Між країнами FBA", "en": "✈️ Between FBA countries"},
    "ro.tr.total_qty": {"ru": "Всего к переброске, шт", "uk": "Всього до перебросу, шт", "en": "Total to transfer, pcs"},
    "ro.tr.col_do": {"ru": "Перебросить?", "uk": "Перекинути?", "en": "Transfer?"},
    "ro.tr.col_product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "ro.tr.col_source": {"ru": "Откуда (источник)", "uk": "Звідки (джерело)", "en": "From (source)"},
    "ro.tr.col_to": {"ru": "Куда", "uk": "Куди", "en": "To"},
    "ro.tr.col_eta": {"ru": "Срок", "uk": "Термін", "en": "ETA"},
    "ro.tr.col_eta_help": {
        "ru": "Ожидаемый срок доставки до FBA по маршруту",
        "uk": "Очікуваний термін доставки до FBA за маршрутом",
        "en": "Expected delivery time to FBA for this route",
    },
    "ro.tr.col_qty": {"ru": "Шт", "uk": "Шт", "en": "Pcs"},
    "ro.tr.col_cover": {"ru": "Хватит, дн", "uk": "Вистачить, дн", "en": "Cover, days"},
    "ro.tr.col_incoming": {
        "ru": "🚚 Едет в Мадрид",
        "uk": "🚚 Їде до Мадрида",
        "en": "🚚 En route to Madrid",
    },
    "ro.tr.col_incoming_help": {
        "ru": "Товар уже в пути на склад Мадрид по данным снабжения. "
              "Из рекомендации не вычитается — приедет на другой склад, но учитывай при решении.",
        "uk": "Товар уже в дорозі на склад Мадрид за даними постачання. "
              "З рекомендації не віднімається — приїде на інший склад, але враховуй при рішенні.",
        "en": "Already in transit to the Madrid warehouse per supply data. "
              "Not deducted from the recommendation — it arrives at a different warehouse, "
              "but take it into account when deciding.",
    },
    "ro.tr.confirm": {"ru": "🔄 Подтвердить переброску ({n})", "uk": "🔄 Підтвердити переброс ({n})", "en": "🔄 Confirm transfer ({n})"},
    "ro.tr.confirmed": {
        "ru": "Переброска подтверждена: {n} позиций. Дальше — оформление перемещения на вашей стороне.",
        "uk": "Переброс підтверджено: {n} позицій. Далі — оформлення переміщення на вашій стороні.",
        "en": "Transfer confirmed: {n} items. Next — arrange the movement on your side.",
    },
    "ro.tr.export": {"ru": "⬇️ Экспорт CSV ({n})", "uk": "⬇️ Експорт CSV ({n})", "en": "⬇️ Export CSV ({n})"},
    "ro.tr.order_created": {
        "ru": "Заявка {no} сформирована: {n} позиций. Скачай и отправь исполнителю.",
        "uk": "Заявку {no} сформовано: {n} позицій. Завантаж і відправ виконавцю.",
        "en": "Order {no} created: {n} lines. Download and send to the executor.",
    },
    "ro.tr.order_download": {"ru": "⬇️ Скачать заявку {no}", "uk": "⬇️ Завантажити заявку {no}", "en": "⬇️ Download {no}"},

    # --- 4_Reorder.py: заказ у поставщика ---
    "ro.order.title": {"ru": "🛒 Заказ у поставщика", "uk": "🛒 Замовлення у постачальника", "en": "🛒 Supplier order"},
    "ro.order.col_do": {"ru": "Заказать?", "uk": "Замовити?", "en": "Order?"},
    "ro.order.col_urgency": {"ru": "Срочность", "uk": "Терміновість", "en": "Urgency"},
    "ro.order.col_stock": {"ru": "Остаток", "uk": "Залишок", "en": "Stock"},
    "ro.order.col_velocity": {"ru": "Прод./день", "uk": "Прод./день", "en": "Sold/day"},
    "ro.order.col_cover": {"ru": "Хватит, дней", "uk": "Вистачить, днів", "en": "Lasts, days"},
    "ro.order.col_qty": {"ru": "Заказать, шт", "uk": "Замовити, шт", "en": "Order, pcs"},
    "ro.order.chosen": {"ru": "Выбрано SKU", "uk": "Вибрано SKU", "en": "SKUs selected"},
    "ro.order.total": {"ru": "Итого к заказу, шт", "uk": "Разом до замовлення, шт", "en": "Total to order, pcs"},
    "ro.order.avg_velocity": {"ru": "Средняя скорость", "uk": "Середня швидкість", "en": "Average velocity"},
    "ro.order.form": {"ru": "✅ Сформировать заказ ({n})", "uk": "✅ Сформувати замовлення ({n})", "en": "✅ Create order ({n})"},
    "ro.order.formed": {"ru": "Заказ сформирован: {n} SKU, {qty} шт.", "uk": "Замовлення сформовано: {n} SKU, {qty} шт.", "en": "Order created: {n} SKUs, {qty} pcs."},
    "ro.order.export": {"ru": "⬇️ Экспорт CSV ({n})", "uk": "⬇️ Експорт CSV ({n})", "en": "⬇️ Export CSV ({n})"},
    "ro.ordered.title": {"ru": "✅ Уже заказано ({n} SKU, {qty} шт)", "uk": "✅ Вже замовлено ({n} SKU, {qty} шт)", "en": "✅ Already ordered ({n} SKUs, {qty} pcs)"},
    "ro.ordered.col_qty": {"ru": "Заказано, шт", "uk": "Замовлено, шт", "en": "Ordered, pcs"},
    "ro.how.title": {"ru": "ℹ️ Как считается", "uk": "ℹ️ Як рахується", "en": "ℹ️ How it's calculated"},
    "ro.how.body": {
        "ru": (
            "- **Скорость продаж** — среднее за 30 дней\n"
            "- **Хватит дней** = остаток / скорость\n"
            "- **🔴 Срочно** — хватит меньше срока поставки\n"
            "- **Заказать** — покрыть спрос на 60 дней\n\n"
            "Сначала система предлагает переброску (свои склады → FBA), "
            "потом заказ у поставщика на то, что переброской не закрыть."
        ),
        "uk": (
            "- **Швидкість продажів** — середнє за 30 днів\n"
            "- **Вистачить днів** = залишок / швидкість\n"
            "- **🔴 Терміново** — вистачить менше терміну поставки\n"
            "- **Замовити** — покрити попит на 60 днів\n\n"
            "Спочатку система пропонує переброс (власні склади → FBA), "
            "потім замовлення у постачальника на те, що перебросом не закрити."
        ),
        "en": (
            "- **Sales velocity** — 30-day average\n"
            "- **Days left** = stock / velocity\n"
            "- **🔴 Urgent** — will last less than the lead time\n"
            "- **Order** — cover 60 days of demand\n\n"
            "First the system suggests transfers (own warehouses → FBA), "
            "then a supplier order for what transfers can't cover."
        ),
    },

    # --- 5_Money.py: юнит-экономика ---
    "money.title": {"ru": "Деньги", "uk": "Гроші", "en": "Money"},
    "money.caption": {
        "ru": "Юнит-экономика: сколько зарабатываем, что съедают комиссии",
        "uk": "Юніт-економіка: скільки заробляємо, що з'їдають комісії",
        "en": "Unit economics: what we earn and what fees eat",
    },
    "money.empty": {
        "ru": "Данные экономики ещё не рассчитаны. Запусти агрегатор в пайплайне.",
        "uk": "Дані економіки ще не розраховані. Запусти агрегатор.",
        "en": "Economics not calculated yet. Run the aggregator.",
    },
    "money.filter.search": {"ru": "Поиск по SKU", "uk": "Пошук за SKU", "en": "Search SKU"},
    "money.filter.search_ph": {"ru": "напр. 41324000", "uk": "напр. 41324000", "en": "e.g. 41324000"},
    "money.kpi.revenue": {"ru": "Выручка ({d} дн)", "uk": "Виручка ({d} дн)", "en": "Revenue ({d}d)"},
    "money.kpi.net": {"ru": "Чистыми", "uk": "Чистими", "en": "Net proceeds"},
    "money.kpi.net_help": {
        "ru": "После вычета всех комиссий маркетплейса",
        "uk": "Після вирахування всіх комісій маркетплейсу",
        "en": "After all marketplace fees",
    },
    "money.kpi.margin": {"ru": "Маржа", "uk": "Маржа", "en": "Margin"},
    "money.kpi.fees": {"ru": "Комиссии", "uk": "Комісії", "en": "Fees"},
    "money.kpi.fees_help": {
        "ru": "Сколько всего забрал маркетплейс",
        "uk": "Скільки всього забрав маркетплейс",
        "en": "Total marketplace fees",
    },
    "money.tab.by_sku": {"ru": "📦 По товарам", "uk": "📦 За товарами", "en": "📦 By product"},
    "money.tab.fees": {"ru": "💸 Комиссии", "uk": "💸 Комісії", "en": "💸 Fees"},
    "money.top_profit": {
        "ru": "Топ прибыльных (чистыми, €)",
        "uk": "Топ прибуткових (чистими, €)",
        "en": "Top profitable (net, €)",
    },
    "money.low_margin": {"ru": "Низкая маржа (%)", "uk": "Низька маржа (%)", "en": "Low margin (%)"},
    "money.table_title": {"ru": "Все товары", "uk": "Всі товари", "en": "All products"},
    "money.col.units": {"ru": "Продано, шт", "uk": "Продано, шт", "en": "Units"},
    "money.col.product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "money.col.revenue": {"ru": "Выручка", "uk": "Виручка", "en": "Revenue"},
    "money.col.fees": {"ru": "Комиссии", "uk": "Комісії", "en": "Fees"},
    "money.col.net": {"ru": "Чистыми", "uk": "Чистими", "en": "Net"},
    "money.col.ppu": {"ru": "Прибыль/шт", "uk": "Прибуток/шт", "en": "Profit/unit"},
    "money.col.margin": {"ru": "Маржа", "uk": "Маржа", "en": "Margin"},
    "money.download": {"ru": "⬇️ Скачать CSV", "uk": "⬇️ Завантажити CSV", "en": "⬇️ Download CSV"},
    "money.fees_axis": {"ru": "% от выручки", "uk": "% від виручки", "en": "% of revenue"},
    "money.struct_title": {"ru": "Куда уходит выручка", "uk": "Куди йде виручка", "en": "Where revenue goes"},
    "money.struct.net": {"ru": "Чистыми нам", "uk": "Чистими нам", "en": "Net to us"},
    "money.struct.fees": {"ru": "Комиссии маркетплейса", "uk": "Комісії маркетплейсу", "en": "Marketplace fees"},
    "money.struct.other": {"ru": "Прочее", "uk": "Інше", "en": "Other"},

    # --- 5_Money.py: мультиканальность (Amazon + Leroy Merlin и далее) ---
    "money.filter.marketplace": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "money.filter.marketplace_ph": {"ru": "Все каналы", "uk": "Всі канали", "en": "All channels"},
    "money.tab.by_marketplace": {
        "ru": "🌍 По маркетплейсам", "uk": "🌍 За маркетплейсами", "en": "🌍 By marketplace",
    },
    "money.col.marketplace": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "money.marketplace_chart": {
        "ru": "Прибыль и расходы по маркетплейсам",
        "uk": "Прибуток і витрати за маркетплейсами",
        "en": "Profit & costs by marketplace",
    },
    "money.fees_by_marketplace": {
        "ru": "Доля комиссий от выручки по маркетплейсам (%)",
        "uk": "Частка комісій від виручки за маркетплейсами (%)",
        "en": "Fees as % of revenue by marketplace",
    },

    # --- 5_Money.py: P&L (COGS + реклама + CM) ---
    "money.kpi.cogs": {"ru": "Себестоимость", "uk": "Собівартість", "en": "COGS"},
    "money.kpi.cogs_help": {
        "ru": "Закупочная стоимость проданного (COGS × шт)",
        "uk": "Закупівельна вартість проданого",
        "en": "Cost of goods sold",
    },
    "money.kpi.ads": {"ru": "Реклама", "uk": "Реклама", "en": "Ads"},
    "money.kpi.ads_help": {
        "ru": "Расходы Amazon Ads (SP + SD)",
        "uk": "Витрати Amazon Ads (SP + SD)",
        "en": "Amazon Ads spend (SP + SD)",
    },
    "money.kpi.cm": {"ru": "Прибыль (CM)", "uk": "Прибуток (CM)", "en": "Profit (CM)"},
    "money.kpi.cm_help": {
        "ru": "Contribution Margin = выручка − комиссии − себестоимость − реклама. Без логистики.",
        "uk": "Contribution Margin = виручка − комісії − собівартість − реклама. Без логістики.",
        "en": "Contribution Margin = revenue − fees − COGS − ads. Logistics not included.",
    },
    "money.tab.pnl": {"ru": "💰 P&L по товарам", "uk": "💰 P&L за товарами", "en": "💰 P&L by product"},
    "money.top_cm": {"ru": "Топ по прибыли (CM, €)", "uk": "Топ за прибутком (CM, €)", "en": "Top by profit (CM, €)"},
    "money.worst_cm": {"ru": "Худшие по прибыли (€)", "uk": "Найгірші за прибутком (€)", "en": "Worst by profit (€)"},
    "money.pnl_table": {"ru": "Полный P&L по товарам", "uk": "Повний P&L за товарами", "en": "Full P&L by product"},
    "money.col.ads": {"ru": "Реклама", "uk": "Реклама", "en": "Ads"},
    "money.col.ads_help": {"ru": "Рекламные расходы, отнесённые на SKU", "uk": "Рекламні витрати, віднесені на SKU", "en": "Ad spend attributed to the SKU"},
    "money.col.cm": {"ru": "Прибыль", "uk": "Прибуток", "en": "Profit"},
    "money.col.cm_pct": {"ru": "Маржа", "uk": "Маржа", "en": "Margin"},
    "money.col.cm_pct_help": {"ru": "Прибыль ÷ выручка, %", "uk": "Прибуток ÷ виторг, %", "en": "Profit ÷ revenue, %"},
    "money.col.cm_help": {"ru": "Чистыми − COGS − реклама", "uk": "Чистими − COGS − реклама", "en": "Net − COGS − ads"},
    "money.col.net_help": {
        "ru": "Выручка минус все комиссии маркетплейса",
        "uk": "Виручка мінус всі комісії маркетплейсу",
        "en": "Revenue minus all marketplace fees",
    },
    "money.col.cogs_help": {
        "ru": "Себестоимость проданного за период",
        "uk": "Собівартість проданого за період",
        "en": "COGS for period",
    },
    "money.col.acos_help": {"ru": "Реклама / выручка", "uk": "Реклама / виручка", "en": "Ads / revenue"},
    "money.col.ann_help": {
        "ru": "Пометка: у цифр этого товара есть контекст (Vine, промо и т.п.)",
        "uk": "Позначка: у цифр цього товару є контекст (Vine, промо тощо)",
        "en": "Note: this product's numbers have context (Vine, promo, etc.)",
    },
    "money.col.flag": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "money.col.flag_help": {
        "ru": "Прибыльность товара за период",
        "uk": "Прибутковість товару за період",
        "en": "Product profitability for the period",
    },
    "money.col.ann": {"ru": "Контекст", "uk": "Контекст", "en": "Context"},
    "money.legend": {
        "ru": "Статус: 🟢 маржа >15% · 🟡 5–15% · 🟠 <5% · 🔴 убыток. "
              "Контекст: 🌿 Vine-кампания · 🏷️ промо · 💱 репрайсинг — цифры объясняются событием, это не проблема.",
        "uk": "Статус: 🟢 маржа >15% · 🟡 5–15% · 🟠 <5% · 🔴 збиток. "
              "Контекст: 🌿 Vine-кампанія · 🏷️ промо · 💱 репрайсинг — цифри пояснюються подією, це не проблема.",
        "en": "Status: 🟢 margin >15% · 🟡 5–15% · 🟠 <5% · 🔴 loss. "
              "Context: 🌿 Vine campaign · 🏷️ promo · 💱 repricing — numbers explained by an event, not a problem.",
    },
    "money.alert.losers": {
        "ru": "🔴 В убытке: {n} SKU ({skus}) — реклама/себестоимость съедают всё",
        "uk": "🔴 У збитку: {n} SKU ({skus})",
        "en": "🔴 Loss-making: {n} SKU ({skus})",
    },
    "money.alert.thin": {
        "ru": "🟠 Маржа <5%: {n} SKU ({skus}) — продаются почти в ноль",
        "uk": "🟠 Маржа <5%: {n} SKU ({skus})",
        "en": "🟠 Margin <5%: {n} SKU ({skus})",
    },
    "money.pnl_note": {
        "ru": "P&L = выручка − комиссии маркетплейса − себестоимость (ERP) − реклама. "
              "Логистика не учтена — добавим, когда появится стоимость доставки.",
        "uk": "P&L = виручка − комісії маркетплейсу − собівартість − реклама. Логістика не врахована.",
        "en": "P&L = revenue − marketplace fees − COGS − ads. Logistics not included yet.",
    },
    "money.struct_pie_title": {
        "ru": "Куда уходит выручка (после комиссий)",
        "uk": "Куди йде виручка",
        "en": "Where revenue goes",
    },
    "money.country_metric_help": {
        "ru": "Прибыль (CM) и маржа за период",
        "uk": "Прибуток (CM) і маржа",
        "en": "Profit (CM) and margin",
    },

    # --- 5_Money.py: водопад выручка → прибыль ---
    "money.waterfall_title": {
        "ru": "Как выручка превращается в прибыль",
        "uk": "Як виручка перетворюється на прибуток",
        "en": "How revenue turns into profit",
    },
    "money.wf.revenue": {"ru": "Выручка", "uk": "Виручка", "en": "Revenue"},
    "money.wf.fees": {"ru": "Комиссии маркетплейса", "uk": "Комісії маркетплейсу", "en": "Marketplace fees"},
    "money.wf.cogs": {"ru": "Себестоимость", "uk": "Собівартість", "en": "COGS"},
    "money.wf.ads": {"ru": "Реклама", "uk": "Реклама", "en": "Ads"},
    "money.wf.cm": {"ru": "Прибыль (CM)", "uk": "Прибуток (CM)", "en": "Profit (CM)"},
    "money.waterfall_caption": {
        "ru": "Водопад за период: из выручки по шагам вычитаются комиссии, себестоимость и реклама.",
        "uk": "Водоспад за період: з виручки по кроках віднімаються комісії, собівартість і реклама.",
        "en": "Waterfall for the period: fees, COGS and ads are deducted from revenue step by step.",
    },

    # --- 5_Money.py: алерты по рекламе ---
    "money.tab.alerts": {"ru": "⚠️ Реклама: проблемы", "uk": "⚠️ Реклама: проблеми", "en": "⚠️ Ads issues"},
    "money.alerts.none": {
        "ru": "Рекламных проблем не найдено 🎉",
        "uk": "Рекламних проблем не знайдено 🎉",
        "en": "No ads issues found 🎉",
    },
    "money.alerts.none_help": {"ru": "Ни одного SKU с рекламными проблемами за период", "uk": "Жодного SKU з рекламними проблемами за період", "en": "No SKU with ad problems in the period"},
    "money.alerts.zero": {"ru": "🔴 Реклама без продаж", "uk": "🔴 Реклама без продажів", "en": "🔴 Ads, no sales"},
    "money.alerts.zero_help": {
        "ru": "Кампании крутятся, продаж 0 — бюджет впустую",
        "uk": "Кампанії крутяться, продажів 0 — бюджет марно",
        "en": "Campaigns running, 0 sales — wasted budget",
    },
    "money.alerts.negcm": {"ru": "🔴 Убыточные (CM<0)", "uk": "🔴 Збиткові (CM<0)", "en": "🔴 Loss-making (CM<0)"},
    "money.alerts.negcm_help": {"ru": "CM<0 — себестоимость и реклама больше выручки", "uk": "CM<0 — собівартість і реклама більші за виторг", "en": "CM<0 — COGS + ads exceed revenue"},
    "money.alerts.wasted": {"ru": "🟡 Холостые дни", "uk": "🟡 Холості дні", "en": "🟡 Wasted days"},
    "money.alerts.wasted_help": {"ru": "Дни с рекламой, но без заказов", "uk": "Дні з рекламою, але без замовлень", "en": "Days with ad spend but no orders"},
    "money.alerts.col_type": {"ru": "Тип", "uk": "Тип", "en": "Type"},
    "money.alerts.col_details": {"ru": "Детали", "uk": "Деталі", "en": "Details"},
    "money.alerts.note": {
        "ru": "Алерты пересчитываются ежедневно в 12:30 по данным рекламы (SP+SD) и P&L за 30 дней.",
        "uk": "Алерти перераховуються щодня о 12:30 за даними реклами та P&L за 30 днів.",
        "en": "Alerts recalculated daily at 12:30 from ads (SP+SD) and 30-day P&L.",
    },

    # --- 5_Money.py: выбор периода ---
    "money.period.label": {"ru": "Период", "uk": "Період", "en": "Period"},
    "money.period.custom": {"ru": "Свой", "uk": "Свій", "en": "Custom"},
    "money.period.range": {"ru": "Даты от–до", "uk": "Дати від–до", "en": "Date range"},
    "money.period.pick": {"ru": "Выбери обе даты периода", "uk": "Обери обидві дати періоду", "en": "Pick both dates"},

    # --- 6_Dictionaries.py ---
    "nav.dictionaries_hint": {
        "ru": "Справочники складов, цепочек подпитки, маркетплейсов, пулов и нормативов",
        "uk": "Довідники складів, ланцюгів підживлення, маркетплейсів, пулів і нормативів",
        "en": "Warehouses, supply chains, marketplaces, pools and coverage norms",
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
    if current not in LANG_LABELS:  # защита от мусора в session_state
        current = DEFAULT_LANG
        st.session_state.lang = current

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
