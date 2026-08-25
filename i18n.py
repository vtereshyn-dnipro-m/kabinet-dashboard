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
              "часть складского остатка). Это не дополнительный товар: он уже учтён в остатках складов выше.",
        "uk": "Квота, виставлена на канал зі складського залишку (наприклад, оффери Leroy Merlin — "
              "частина складського залишку). Це не додатковий товар: він уже врахований у залишках складів вище.",
        "en": "Quantity listed on a channel out of existing warehouse stock (e.g. Leroy Merlin offers are "
              "part of the local stock). This is not additional goods — it's already counted above.",
    },
    "stock.channels.col_channel": {"ru": "Канал", "uk": "Канал", "en": "Channel"},
    "stock.channels.col_qty": {"ru": "Выделено, шт", "uk": "Виділено, шт", "en": "Allocated, pcs"},
    "stock.channels.download": {
        "ru": "⬇️ Скачать квоты каналов CSV",
        "uk": "⬇️ Завантажити квоти каналів CSV",
        "en": "⬇️ Download channel quotas CSV",
    },
    "stock.only_channels": {
        "ru": "В последнем снапшоте только квоты каналов, физических остатков нет. Показаны квоты.",
        "uk": "В останньому знімку лише квоти каналів, фізичних залишків немає. Показані квоти.",
        "en": "The latest snapshot contains only channel quotas, no physical stock. Showing quotas.",
    },
    "stock.tab.coverage": {"ru": "📅 Покрытие", "uk": "📅 Покриття", "en": "📅 Coverage"},
    "stock.abc.no_data": {
        "ru": "Недостаточно данных для ABC-анализа по текущему фильтру.",
        "uk": "Недостатньо даних для ABC-аналізу за поточним фільтром.",
        "en": "Not enough data for ABC analysis with the current filter.",
    },
    "stock.cov.no_data": {
        "ru": "Расчёт покрытия ещё не выполнялся.",
        "uk": "Розрахунок покриття ще не виконувався.",
        "en": "The coverage calculation has not run yet.",
    },
    "stock.cov.as_of": {"ru": "Расчёт на {d}", "uk": "Розрахунок на {d}", "en": "Calculated on {d}"},
    "stock.cov.intro": {
        "ru": "Покрытие считается по неделям вперёд: из остатка вычитается прогноз продаж, "
              "добавляются поступления. Когда склад Amazon пустеет, продажи не встают — "
              "листинг переключается на отгрузку с местного склада. Но этот запас общий на "
              "несколько стран, поэтому реальный срок короче обещанного.",
        "uk": "Покриття рахується по тижнях уперед: із залишку віднімається прогноз продажів, "
              "додаються надходження. Коли склад Amazon порожніє, продажі не зупиняються — "
              "лістинг перемикається на відвантаження з місцевого складу. Але цей запас "
              "спільний на кілька країн, тому реальний строк коротший за обіцяний.",
        "en": "Coverage is projected week by week: the forecast is subtracted from stock and "
              "incoming shipments are added. When Amazon stock runs out, sales do not stop — "
              "the listing switches to shipping from the local warehouse. But that stock is "
              "shared across countries, so the real horizon is shorter than promised.",
    },
    "stock.cov.horizon_note": {
        "ru": "**Насколько можно верить горизонту.** В расчёте учтены только подтверждённые "
              "поставки — товар, который уже в пути. Это примерно неделя вперёд. Заказы "
              "поставщику и производственные планы в систему пока не заведены, поэтому "
              "дефицит после первой недели означает «поставок не запланировано в известных "
              "нам данных», а не «товара точно не будет».",
        "uk": "**Наскільки можна вірити горизонту.** У розрахунку враховані лише підтверджені "
              "поставки — товар, який уже в дорозі. Це приблизно тиждень уперед. Замовлення "
              "постачальнику й виробничі плани в систему поки не заведені, тому дефіцит після "
              "першого тижня означає «поставок не заплановано у відомих нам даних», а не "
              "«товару точно не буде».",
        "en": "**How far the horizon can be trusted.** The calculation only includes confirmed "
              "shipments — stock already in transit, roughly a week ahead. Purchase orders and "
              "production plans are not in the system yet, so a shortage beyond the first week "
              "means “no shipments planned in the data we have”, not “there will be no stock”.",
    },
    "stock.cov.col_odoo": {"ru": "Ожидается, шт", "uk": "Очікується, шт", "en": "Expected, units"},
    "stock.cov.col_odoo_help": {
        "ru": "Товар, который числится в системе как заказанный или в производстве. "
              "Дата прибытия неизвестна, поэтому в расчёт покрытия он не входит",
        "uk": "Товар, що числиться в системі як замовлений або у виробництві. "
              "Дата прибуття невідома, тому в розрахунок покриття він не входить",
        "en": "Stock recorded as ordered or in production. The arrival date is unknown, "
              "so it is not included in the coverage calculation",
    },
    "stock.cov.odoo_note": {
        "ru": "По этому товару ожидается ещё {qty} шт — заказано или в производстве. "
              "Дата прибытия в системе не зафиксирована, поэтому в расчёт выше он не вошёл.",
        "uk": "За цим товаром очікується ще {qty} шт — замовлено або у виробництві. "
              "Дата прибуття в системі не зафіксована, тому в розрахунок вище він не увійшов.",
        "en": "Another {qty} units are expected for this item — ordered or in production. "
              "No arrival date is recorded, so it is not part of the calculation above.",
    },
    "stock.cov.kpi_overstock": {"ru": "Излишек", "uk": "Надлишок", "en": "Overstock"},
    "stock.cov.kpi_overstock_help": {
        "ru": "Позиции, где товар остаётся даже после того, как весь прогноз на год исчерпан",
        "uk": "Позиції, де товар залишається навіть після того, як увесь прогноз на рік вичерпано",
        "en": "Items with stock left over after the entire year's forecast is consumed",
    },
    "stock.cov.col_gaps": {"ru": "Разрывов", "uk": "Розривів", "en": "Gaps"},
    "stock.cov.col_gaps_help": {
        "ru": "Сколько раз товар закончится на горизонте расчёта. Поставка закрывает один "
              "разрыв, после неё может открыться следующий",
        "uk": "Скільки разів товар закінчиться на горизонті розрахунку. Поставка закриває один "
              "розрив, після неї може відкритися наступний",
        "en": "How many times the item runs out over the horizon. A shipment closes one gap, "
              "another may open after it",
    },
    "stock.cov.col_gaps_qty": {"ru": "Не покроем, шт", "uk": "Не покриємо, шт", "en": "Unmet, units"},
    "stock.cov.col_gaps_qty_help": {
        "ru": "Сколько единиц спроса останется без товара за все разрывы вместе",
        "uk": "Скільки одиниць попиту залишиться без товару за всі розриви разом",
        "en": "Total demand left unserved across all gaps",
    },
    "stock.cov.col_overstock": {"ru": "Излишек, шт", "uk": "Надлишок, шт", "en": "Overstock, units"},
    "stock.cov.col_overstock_help": {
        "ru": "Товар, который остаётся после того, как весь годовой прогноз продан",
        "uk": "Товар, що залишається після того, як увесь річний прогноз продано",
        "en": "Stock remaining after the full year's forecast is sold",
    },
    "stock.cov.gaps_found": {"ru": "Разрывов на горизонте", "uk": "Розривів на горизонті", "en": "Gaps ahead"},
    "stock.cov.gaps_qty": {"ru": "Спроса без товара", "uk": "Попиту без товару", "en": "Demand unserved"},
    "stock.cov.gaps_qty_help": {
        "ru": "Суммарно по всем разрывам, единиц",
        "uk": "Сумарно за всіма розривами, одиниць",
        "en": "Total across all gaps, units",
    },
    "stock.cov.gap_from": {"ru": "Дефицит с", "uk": "Дефіцит з", "en": "Gap from"},
    "stock.cov.gap_to": {"ru": "по", "uk": "по", "en": "to"},
    "stock.cov.gap_qty": {"ru": "Не покроем, шт", "uk": "Не покриємо, шт", "en": "Unmet, units"},
    "stock.cov.overstock_note": {
        "ru": "Излишек: {qty} шт останется после того, как весь годовой прогноз будет продан — "
              "это примерно {weeks} недель продаж сверх горизонта.",
        "uk": "Надлишок: {qty} шт залишиться після того, як увесь річний прогноз буде продано — "
              "це приблизно {weeks} тижнів продажів понад горизонт.",
        "en": "Overstock: {qty} units remain after the entire year's forecast is sold — "
              "roughly {weeks} weeks of sales beyond the horizon.",
    },
    "stock.cov.header": {"ru": "Покрытие на {d}", "uk": "Покриття на {d}", "en": "Coverage as of {d}"},
    "stock.cov.how": {"ru": "Как читать", "uk": "Як читати", "en": "How to read"},
    "stock.cov.show": {"ru": "Показать", "uk": "Показати", "en": "Show"},
    "stock.cov.st_critical": {"ru": "Дефицит в ближайшие 4 недели",
                              "uk": "Дефіцит у найближчі 4 тижні",
                              "en": "Shortage within 4 weeks"},
    "stock.cov.st_warning": {"ru": "Дефицит через 5–13 недель",
                             "uk": "Дефіцит через 5–13 тижнів",
                             "en": "Shortage in 5–13 weeks"},
    "stock.cov.st_ok": {"ru": "Запас достаточен", "uk": "Запас достатній", "en": "Well covered"},
    "stock.cov.filter_mp": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "stock.cov.filter_status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "stock.cov.kpi_critical": {"ru": "Дефицит ≤ 4 недель", "uk": "Дефіцит ≤ 4 тижнів", "en": "Shortage ≤ 4 weeks"},
    "stock.cov.kpi_critical_help": {
        "ru": "Товаров, которых хватит меньше чем на 4 недели с учётом местного запаса",
        "uk": "Товарів, яких вистачить менш ніж на 4 тижні з урахуванням місцевого запасу",
        "en": "Products with less than 4 weeks of cover including the local stock",
    },
    "stock.cov.kpi_warning": {"ru": "Дефицит 5–13 недель", "uk": "Дефіцит 5–13 тижнів", "en": "Shortage 5–13 weeks"},
    "stock.cov.kpi_warning_help": {
        "ru": "Товаров, которых хватит на 5–13 недель — не критично, но стоит планировать поставку",
        "uk": "Товарів, яких вистачить на 5–13 тижнів — не критично, але варто планувати поставку",
        "en": "Products with 5–13 weeks of cover — not critical, but worth planning a shipment",
    },
    "stock.cov.kpi_switch": {"ru": "Перейдут на локальный склад",
                             "uk": "Перейдуть на локальний склад",
                             "en": "Switch to local warehouse"},
    "stock.cov.kpi_switch_help": {
        "ru": "Товары, по которым запас Amazon кончится и отгрузка переключится на местный склад",
        "uk": "Товари, за якими запас Amazon закінчиться і відвантаження перемкнеться на місцевий склад",
        "en": "Products where Amazon stock runs out and fulfilment switches to the local warehouse",
    },
    "stock.cov.kpi_pool": {"ru": "Прогноз завышен", "uk": "Прогноз завищений", "en": "Optimistic"},
    "stock.cov.kpi_pool_help": {
        "ru": "Товары, где местный запас делят несколько стран — общий спрос израсходует "
              "его раньше, чем показывает расчёт по каждой стране отдельно",
        "uk": "Товари, де місцевий запас ділять кілька країн — спільний попит витратить "
              "його раніше, ніж показує розрахунок по кожній країні окремо",
        "en": "Products where several countries share the local stock — combined demand "
              "drains it sooner than the per-country calculation suggests",
    },
    "stock.cov.col_mp": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "stock.cov.col_stock": {"ru": "Остаток FBA, шт", "uk": "Залишок FBA, шт", "en": "FBA stock, units"},
    "stock.cov.col_until_gap": {"ru": "До дефицита, недель", "uk": "До дефіциту, тижнів", "en": "Until shortage, weeks"},
    "stock.cov.col_until_gap_help": {
        "ru": "Сколько недель подряд товар обеспечен, начиная с сегодня. Ноль означает, "
              "что дефицит наступает уже на этой неделе. Это главное число: показывает, "
              "сколько времени осталось на решение",
        "uk": "Скільки тижнів поспіль товар забезпечений, починаючи з сьогодні. Нуль означає, "
              "що дефіцит настає вже цього тижня. Це головне число: показує, скільки часу "
              "лишилось на рішення",
        "en": "How many consecutive weeks the item is covered starting today. Zero means the "
              "shortage hits this week. This is the number that matters — how much time is "
              "left to act",
    },
    "stock.cov.col_weeks_fba": {"ru": "Обеспечено недель из 52",
                                "uk": "Забезпечено тижнів із 52",
                                "en": "Weeks covered of 52"},
    "stock.cov.col_weeks_fba_help": {
        "ru": "Сколько недель из года товар будет в наличии — с учётом всех известных "
              "поставок. Это не непрерывный срок: между покрытыми неделями могут быть "
              "разрывы, смотри колонку «До дефицита»",
        "uk": "Скільки тижнів із року товар буде в наявності — з урахуванням усіх відомих "
              "поставок. Це не безперервний строк: між покритими тижнями можуть бути "
              "розриви, дивись колонку «До дефіциту»",
        "en": "How many weeks of the year the item will be in stock, counting all known "
              "shipments. Not a continuous run — there may be gaps between covered weeks, "
              "see the “Until shortage” column",
    },
    "stock.cov.col_madrid": {"ru": "Остаток локального склада, шт",
                             "uk": "Залишок локального складу, шт",
                             "en": "Local warehouse stock, units"},
    "stock.cov.col_madrid_help": {
        "ru": "Остаток на складе внутри страны — резерв на случай, когда Amazon опустеет",
        "uk": "Залишок на складі всередині країни — резерв на випадок, коли Amazon спорожніє",
        "en": "Stock in the in-country warehouse — the fallback when Amazon runs out",
    },
    "stock.cov.col_weeks_total": {"ru": "Обеспеченность с локальным складом, недели",
                                  "uk": "Забезпеченість з локальним складом, тижні",
                                  "en": "Cover with local warehouse, weeks"},
    "stock.cov.col_weeks_total_help": {
        "ru": "Покрытие, если весь местный запас достанется этому маркетплейсу",
        "uk": "Покриття, якщо весь місцевий запас дістанеться цьому маркетплейсу",
        "en": "Cover if the entire local stock went to this marketplace",
    },
    "stock.cov.col_shared": {"ru": "Общий запас", "uk": "Спільний запас", "en": "Shared"},
    "stock.cov.col_shared_suffix": {"ru": "стран", "uk": "країн", "en": "countries"},
    "stock.cov.col_shared_help": {
        "ru": "Местный запас по этому товару делят несколько стран. Поэтому «Реально недель» "
              "меньше: общий спрос израсходует его быстрее.",
        "uk": "Місцевий запас за цим товаром ділять кілька країн. Тому «Реально тижнів» "
              "менше: спільний попит витратить його швидше.",
        "en": "Several countries share the local stock for this product. That is why "
              "“Realistic weeks” is lower.",
    },
    "stock.cov.col_weeks_real": {"ru": "Реально недель", "uk": "Реально тижнів", "en": "Realistic weeks"},
    "stock.cov.col_weeks_real_help": {
        "ru": "Меньшее из двух: покрытие этой страны и срок жизни общего местного запаса",
        "uk": "Менше з двох: покриття цієї країни і термін життя спільного місцевого запасу",
        "en": "The lower of two: this country's cover and the life of the shared local stock",
    },
    "stock.cov.col_first_deficit": {"ru": "Дефицит с", "uk": "Дефіцит з", "en": "Shortage from"},
    "stock.cov.col_status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "stock.cov.note": {
        "ru": "Прогноз продаж пока считается по скорости за 30 дней. Когда появится плановый "
              "прогноз, расчёт переключится на него — остальная логика не изменится.",
        "uk": "Прогноз продажів поки рахується за швидкістю за 30 днів. Коли зʼявиться плановий "
              "прогноз, розрахунок перемкнеться на нього — решта логіки не зміниться.",
        "en": "The sales forecast is currently based on 30-day velocity. Once a planned "
              "forecast is available the calculation switches to it — nothing else changes.",
    },
    "stock.cov.weekly_title": {"ru": "Проекция по неделям", "uk": "Проекція по тижнях", "en": "Week by week"},
    "stock.cov.pick": {"ru": "Товар и маркетплейс", "uk": "Товар і маркетплейс", "en": "Product and marketplace"},
    "stock.cov.no_projection": {
        "ru": "Проекция для этой пары не рассчитана.",
        "uk": "Проекція для цієї пари не розрахована.",
        "en": "No projection for this pair.",
    },
    "stock.cov.pool_warn": {
        "ru": "Местный запас ({qty} шт) делится между несколькими странами — их {n}, "
              "суммарный спрос {demand:.0f} шт в неделю. Общего запаса хватит примерно на "
              "{pool_weeks} нед., а расчёт по этой стране обещает {promised}.",
        "uk": "Місцевий запас ({qty} шт) ділиться між кількома країнами — їх {n}, "
              "сумарний попит {demand:.0f} шт на тиждень. Спільного запасу вистачить "
              "приблизно на {pool_weeks} тиж., а розрахунок по цій країні обіцяє {promised}.",
        "en": "The local stock ({qty} units) is shared across {n} countries with combined "
              "demand of {demand:.0f} units per week. It lasts about {pool_weeks} week(s), "
              "while this country's calculation promises {promised}.",
    },
    "stock.cov.p_week": {"ru": "Неделя", "uk": "Тиждень", "en": "Week"},
    "stock.cov.p_from": {"ru": "С даты", "uk": "З дати", "en": "From"},
    "stock.cov.p_begin": {"ru": "На начало", "uk": "На початок", "en": "Opening"},
    "stock.cov.p_incoming": {"ru": "Поступление", "uk": "Надходження", "en": "Incoming"},
    "stock.cov.p_forecast": {"ru": "Прогноз продаж", "uk": "Прогноз продажів", "en": "Forecast"},
    "stock.cov.p_end": {"ru": "На конец", "uk": "На кінець", "en": "Closing"},
    "stock.cov.p_unmet": {"ru": "Не покрыто", "uk": "Не покрито", "en": "Unmet"},
    "stock.cov.p_result": {"ru": "Итог", "uk": "Підсумок", "en": "Result"},
    "stock.cov.p_covered": {"ru": "Хватает", "uk": "Вистачає", "en": "Covered"},
    "stock.cov.p_deficit": {"ru": "Дефицит", "uk": "Дефіцит", "en": "Shortage"},
    "stock.cov.p_pool_line": {"ru": "Местный запас кончится",
                              "uk": "Місцевий запас закінчиться",
                              "en": "Local stock runs out"},
    "stock.cov.weekly_note": {
        "ru": "Поступление становится доступным со следующей недели после прибытия. "
              "Непокрытый спрос не переносится — потерянные продажи не возвращаются.",
        "uk": "Надходження стає доступним з наступного тижня після прибуття. "
              "Непокритий попит не переноситься — втрачені продажі не повертаються.",
        "en": "An incoming shipment becomes available the week after arrival. Unmet demand "
              "does not carry over — lost sales are gone.",
    },
    "stock.cov.download": {"ru": "Скачать покрытие CSV", "uk": "Завантажити покриття CSV", "en": "Download coverage CSV"},
    "stock.cov.go_reorder": {"ru": "Перейти к автозаказу", "uk": "Перейти до автозамовлення", "en": "Go to reorder"},
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
    "home.inc.low_stock": {"ru": "Мало остатка", "uk": "Мало залишку", "en": "Low stock"},
    "home.inc.out_of_stock": {"ru": "Нет в наличии", "uk": "Немає в наявності", "en": "Out of stock"},
    "home.inc.stale_data": {"ru": "Данные устарели", "uk": "Дані застаріли", "en": "Stale data"},
    "home.inc.negative_stock": {"ru": "Отрицательный остаток", "uk": "Відʼємний залишок", "en": "Negative stock"},
    "home.inc.lm_not_accepted": {"ru": "Заказ без акцепта", "uk": "Замовлення без акцепту", "en": "Order not accepted"},
    "home.inc.lm_offer_zero": {"ru": "Оффер обнулён", "uk": "Оффер обнулено", "en": "Offer out of stock"},
    "home.inc.lm_degraded": {"ru": "Показатели канала просели", "uk": "Показники каналу просіли", "en": "Channel health down"},
    "home.sales.n_countries": {
        "ru": "· продажи в {n} странах",
        "uk": "· продажі в {n} країнах",
        "en": "· sales in {n} countries"},
    "home.sales.lm_where": {
        "ru": "· Испания", "uk": "· Іспанія", "en": "· Spain"},
    "home.sales.lm_country": {
        "ru": "Leroy Merlin: Испания {v:,.0f} €",
        "uk": "Leroy Merlin: Іспанія {v:,.0f} €",
        "en": "Leroy Merlin: Spain {v:,.0f} €"},
    "home.sales.silent": {"ru": "нет продаж", "uk": "немає продажів", "en": "no sales"},
    "home.sales.silent_hint": {
        "ru": "За последние 90 дней в этой стране продажи были, а за выбранный период — нет",
        "uk": "За останні 90 днів у цій країні продажі були, а за обраний період — ні",
        "en": "This country had sales in the last 90 days but none in the selected period",
    },
    "home.sales.rest": {"ru": "ещё {n}", "uk": "ще {n}", "en": "{n} more"},
    "home.platform.lm_short": {"ru": "LM Испания", "uk": "LM Іспанія", "en": "LM Spain"},
    "home.sales.others": {
        "ru": "и ещё {n}: {v:,.0f} €", "uk": "і ще {n}: {v:,.0f} €", "en": "and {n} more: {v:,.0f} €"},
    "home.link.money": {"ru": "Деньги и маржа", "uk": "Гроші та маржа", "en": "Money and margin"},
    "home.sec.stock_note": {
        "ru": "Ниже — состояние на сейчас, период выше на него не влияет.",
        "uk": "Нижче — стан на зараз, період вище на нього не впливає.",
        "en": "Below is the current state — the period selector above does not affect it.",
    },
    "home.refresh": {
        "ru": "Обновить данные", "uk": "Оновити дані", "en": "Refresh data"},
    "home.refresh_help": {
        "ru": "Сбросить кеш и перечитать всё из базы. Пригодится, когда видно, "
              "что загрузчик уже отработал, а плашка ещё висит: сама она гаснет "
              "в течение минуты, кнопка делает это сразу.",
        "uk": "Скинути кеш і перечитати все з бази. Знадобиться, коли видно, що "
              "завантажувач уже відпрацював, а плашка ще висить: сама вона гасне "
              "протягом хвилини, кнопка робить це одразу.",
        "en": "Drop the cache and re-read everything from the database. Useful when "
              "the loader has clearly finished but the banner is still up: it clears "
              "on its own within a minute, this button does it now.",
    },
    "home.pulse.down": {
        "ru": "Система не обновляет данные {h:.0f} ч. Всё, что показано ниже, устарело — "
              "загрузчики не отрабатывают.",
        "uk": "Система не оновлює дані {h:.0f} год. Усе, що показано нижче, застаріло — "
              "завантажувачі не відпрацьовують.",
        "en": "The system has not updated data for {h:.0f}h. Everything below is stale — "
              "the loaders are not running.",
    },
    "home.pulse.partial": {
        "ru": "{n} процесс(ов) не обновлялись больше суток: {jobs}. Часть цифр может быть "
              "устаревшей.",
        "uk": "{n} процес(ів) не оновлювались понад добу: {jobs}. Частина цифр може бути "
              "застарілою.",
        "en": "{n} process(es) have not run for over a day: {jobs}. Some figures may be stale.",
    },
    "home.period.month": {"ru": "Этот месяц", "uk": "Цей місяць", "en": "This month"},
    "home.period.custom": {"ru": "Свой период", "uk": "Свій період", "en": "Custom"},
    "home.period.range": {"ru": "Даты с и по", "uk": "Дати з і по", "en": "Date range"},
    "home.sec.sales_range": {
        "ru": "Продажи: {f} — {to}", "uk": "Продажі: {f} — {to}", "en": "Sales: {f} — {to}"},
    "home.sales.lag_range": {
        "ru": "Данные есть по {d} включительно — Amazon отдаёт отчёты с задержкой, "
              "последние {n} дн. ещё не загружены. Конец выбранного периода пока пуст.",
        "uk": "Дані є по {d} включно — Amazon віддає звіти із затримкою, останні {n} дн. "
              "ще не завантажені. Кінець обраного періоду поки порожній.",
        "en": "Data is available up to {d} — Amazon delivers reports with a delay and the "
              "last {n} days are not loaded. The end of the selected range is still empty.",
    },
    "home.period": {"ru": "Период, дней", "uk": "Період, днів", "en": "Period, days"},
    "home.sec.sales": {"ru": "Продажи за {d} дней", "uk": "Продажі за {d} днів", "en": "Sales, last {d} days"},
    "home.sec.stock": {"ru": "Запасы и обеспеченность", "uk": "Запаси та забезпеченість", "en": "Stock and coverage"},
    "home.sec.reorder": {"ru": "Пополнение", "uk": "Поповнення", "en": "Replenishment"},
    "home.sec.incidents": {"ru": "Что требует внимания", "uk": "Що потребує уваги", "en": "Needs attention"},
    "home.sec.reviews": {"ru": "Отзывы", "uk": "Відгуки", "en": "Reviews"},
    "home.sales.no_data": {
        "ru": "Данные о продажах пока не подгружены.",
        "uk": "Дані про продажі поки не завантажені.",
        "en": "Sales data is not loaded yet.",
    },
    "home.platform.amazon": {"ru": "Amazon", "uk": "Amazon", "en": "Amazon"},
    "home.platform.lm": {"ru": "Leroy Merlin", "uk": "Leroy Merlin", "en": "Leroy Merlin"},
    "home.sales.by_country": {
        "ru": "Amazon по странам:", "uk": "Amazon за країнами:", "en": "Amazon by country:"},
    "home.sales.lag": {
        "ru": "Период: {f} — {d}. Amazon отдаёт отчёты с задержкой, последние {n} дн. "
              "ещё не загружены — поэтому окно отсчитывается от последнего дня с данными, "
              "а не от сегодня.",
        "uk": "Період: {f} — {d}. Amazon віддає звіти із затримкою, останні {n} дн. "
              "ще не завантажені — тому вікно відлічується від останнього дня з даними, "
              "а не від сьогодні.",
        "en": "Period: {f} — {d}. Amazon delivers reports with a delay, the last {n} days "
              "are not loaded yet — so the window is counted from the last day with data, "
              "not from today.",
    },
    "home.sales.no_plan": {
        "ru": "Сравнение с планом появится, когда будет подключён прогноз продаж. "
              "Пока сравниваем с предыдущим периодом.",
        "uk": "Порівняння з планом зʼявиться, коли буде підключено прогноз продажів. "
              "Поки порівнюємо з попереднім періодом.",
        "en": "Plan comparison will appear once the sales forecast is connected. "
              "For now we compare with the previous period.",
    },
    "home.kpi.ordered": {
        "ru": "Продажи по заказам", "uk": "Продажі за замовленнями", "en": "Ordered sales"},
    "home.kpi.ordered_help": {
        "ru": "То же число, что видно в кабинете Amazon: цена с НДС и доставкой, "
              "по дате заказа, отменённые не вычитаются. Это витрина, а не деньги на счёте",
        "uk": "Те саме число, що видно в кабінеті Amazon: ціна з ПДВ і доставкою, "
              "за датою замовлення, скасовані не віднімаються. Це вітрина, а не гроші на рахунку",
        "en": "The same figure you see in Seller Central: buyer price with VAT and shipping, "
              "by order date, cancellations not deducted. This is the storefront, not cash",
    },
    "home.sales.two_numbers": {
        "ru": "Разница между двумя числами — {gap:,.0f} € ({pct:.0f}%): НДС уходит "
              "государству, часть заказов отменяют и возвращают. Первое число сходится "
              "с кабинетом Amazon, второе — то, с чего считается маржа.",
        "uk": "Різниця між двома числами — {gap:,.0f} € ({pct:.0f}%): ПДВ іде державі, "
              "частину замовлень скасовують і повертають. Перше число збігається з "
              "кабінетом Amazon, друге — те, з чого рахується маржа.",
        "en": "The gap between the two figures is {gap:,.0f} € ({pct:.0f}%): VAT goes to "
              "the state, some orders are cancelled or returned. The first matches Seller "
              "Central, the second is what margin is calculated from.",
    },
    "home.kpi.revenue": {"ru": "Выручка", "uk": "Виручка", "en": "Revenue"},
    "home.kpi.revenue_help": {
        "ru": "Выручка за вычетом возвратов, без комиссий площадки. За последние {d} дней, "
              "изменение — к предыдущим {d} дням",
        "uk": "Виручка за вирахуванням повернень, без комісій майданчика. За останні {d} днів, "
              "зміна — до попередніх {d} днів",
        "en": "Revenue net of returns, before channel fees. Last {d} days, change compared "
              "with the previous {d} days",
    },
    "home.kpi.refunded": {"ru": "возврат", "uk": "повернення", "en": "returned"},
    "home.kpi.units_help": {
        "ru": "Заказано штук за период. Красным — сколько из них вернули",
        "uk": "Замовлено штук за період. Червоним — скільки з них повернули",
        "en": "Units ordered in the period. In red — how many were returned",
    },
    "home.kpi.margin": {"ru": "Маржа и её доля", "uk": "Маржа та її частка", "en": "Margin and its share"},
    "home.kpi.margin_help": {
        "ru": "Выручка минус комиссии площадки, себестоимость и реклама. Логистика "
              "внутренних перемещений сюда не входит — разбивка на странице «Деньги»",
        "uk": "Виручка мінус комісії майданчика, собівартість і реклама. Логістика "
              "внутрішніх переміщень сюди не входить — розбивка на сторінці «Гроші»",
        "en": "Revenue minus channel fees, COGS and ads. Internal logistics is not "
              "included — see the Money page for the breakdown",
    },
    "home.kpi.units": {"ru": "Продано штук", "uk": "Продано штук", "en": "Units sold"},
    "home.kpi.markets": {"ru": "Площадок", "uk": "Майданчиків", "en": "Channels"},
    "home.cov.no_data": {
        "ru": "Расчёт покрытия ещё не выполнялся.",
        "uk": "Розрахунок покриття ще не виконувався.",
        "en": "The coverage calculation has not run yet.",
    },
    "home.kpi.secured": {"ru": "Запас обеспечен", "uk": "Запас забезпечений", "en": "Well covered"},
    "home.kpi.secured_help": {
        "ru": "Доля позиций, по которым запаса хватит больше чем на 13 недель",
        "uk": "Частка позицій, за якими запасу вистачить більш ніж на 13 тижнів",
        "en": "Share of items with more than 13 weeks of stock",
    },
    "home.kpi.deficit_soon": {"ru": "Дефицит ≤ 4 недель", "uk": "Дефіцит ≤ 4 тижнів", "en": "Shortage ≤ 4 weeks"},
    "home.kpi.deficit_soon_help": {
        "ru": "Позиции, где товар закончится в ближайший месяц",
        "uk": "Позиції, де товар закінчиться найближчого місяця",
        "en": "Items running out within a month",
    },
    "home.kpi.deficit_later": {"ru": "Дефицит 5–13 недель", "uk": "Дефіцит 5–13 тижнів", "en": "Shortage 5–13 weeks"},
    "home.kpi.deficit_later_help": {
        "ru": "Не горит, но поставку стоит планировать",
        "uk": "Не горить, але поставку варто планувати",
        "en": "Not urgent, but a shipment is worth planning",
    },
    "home.cov.b_crit": {"ru": "До 4 недель", "uk": "До 4 тижнів", "en": "Under 4 weeks"},
    "home.cov.b_warn": {"ru": "5–13 недель", "uk": "5–13 тижнів", "en": "5–13 weeks"},
    "home.cov.b_ok": {"ru": "Больше 13 недель", "uk": "Більше 13 тижнів", "en": "Over 13 weeks"},
    "home.reorder.no_data": {
        "ru": "Рекомендаций по пополнению пока нет.",
        "uk": "Рекомендацій щодо поповнення поки немає.",
        "en": "No replenishment recommendations yet.",
    },
    "home.kpi.transfers": {"ru": "Перебросок", "uk": "Перекидань", "en": "Transfers"},
    "home.kpi.transfers_help": {
        "ru": "Рекомендации переместить товар между складами — своим товаром дешевле, "
              "чем закупать новый",
        "uk": "Рекомендації перемістити товар між складами — своїм товаром дешевше, "
              "ніж купувати новий",
        "en": "Recommendations to move stock between warehouses — cheaper than buying new",
    },
    "home.kpi.transfer_qty": {"ru": "Штук к переброске", "uk": "Штук до перекидання", "en": "Units to move"},
    "home.inc.no_data": {
        "ru": "Журнал инцидентов пуст.",
        "uk": "Журнал інцидентів порожній.",
        "en": "The incident log is empty.",
    },
    "home.inc.all_clear": {
        "ru": "Открытых инцидентов нет.",
        "uk": "Відкритих інцидентів немає.",
        "en": "No open incidents.",
    },
    "home.kpi.inc_supply": {"ru": "Снабжение", "uk": "Постачання", "en": "Supply"},
    "home.kpi.inc_supply_help": {
        "ru": "Проблемы с запасами, поставками и прогнозом",
        "uk": "Проблеми із запасами, поставками та прогнозом",
        "en": "Issues with stock, shipments and forecast",
    },
    "home.kpi.inc_sales": {"ru": "Продажи", "uk": "Продажі", "en": "Sales"},
    "home.kpi.inc_sales_help": {
        "ru": "Проблемы на площадках: заказы без акцепта, листинги",
        "uk": "Проблеми на майданчиках: замовлення без акцепту, лістинги",
        "en": "Marketplace issues: unaccepted orders, listings",
    },
    "home.kpi.inc_oldest": {"ru": "Дней у старейшего", "uk": "Днів у найстарішого", "en": "Oldest, days"},
    "home.kpi.inc_oldest_help": {
        "ru": "Сколько дней открыт самый давний инцидент",
        "uk": "Скільки днів відкритий найдавніший інцидент",
        "en": "How long the oldest incident has been open",
    },
    "home.rev.no_data": {
        "ru": "Рассылка запросов на отзыв ещё не запускалась.",
        "uk": "Розсилка запитів на відгук ще не запускалась.",
        "en": "Review requests have not started yet.",
    },
    "home.kpi.requests": {"ru": "Запросов за {d} дней", "uk": "Запитів за {d} днів", "en": "Requests, {d} days"},
    "home.kpi.requests_help": {
        "ru": "Автоматических запросов на отзыв отправлено за {d} дней",
        "uk": "Автоматичних запитів на відгук надіслано за {d} днів",
        "en": "Automated review requests sent over {d} days",
    },
    "home.kpi.new_reviews": {"ru": "Новых отзывов", "uk": "Нових відгуків", "en": "New reviews"},
    "home.kpi.new_reviews_help": {
        "ru": "Прирост за {d} дней по {n} позициям, которые отслеживаются всё это время. "
              "Товары, добавленные в наблюдение позже, в расчёт не идут",
        "uk": "Приріст за {d} днів по {n} позиціях, які відстежуються весь цей час. "
              "Товари, додані у спостереження пізніше, у розрахунок не йдуть",
        "en": "Growth over {d} days across {n} items tracked for the whole period. "
              "Items added to tracking later are excluded",
    },
    "home.rev.stopped": {
        "ru": "Рассылка не работает {h:.0f} ч — стоит проверить.",
        "uk": "Розсилка не працює {h:.0f} год — варто перевірити.",
        "en": "No requests sent for {h:.0f}h — worth checking.",
    },
    "home.link.coverage": {"ru": "Остатки и покрытие", "uk": "Залишки та покриття", "en": "Stock and coverage"},
    "home.link.reorder": {"ru": "Автозаказ", "uk": "Автозамовлення", "en": "Reorder"},
    "home.link.incidents": {"ru": "Журнал инцидентов", "uk": "Журнал інцидентів", "en": "Incident log"},
    "home.link.reviews": {"ru": "Отзывы", "uk": "Відгуки", "en": "Reviews"},
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
    "inc.stream.label": {"ru": "Кому смотреть", "uk": "Кому дивитись", "en": "Whose queue"},
    "inc.stream.all": {"ru": "Всё", "uk": "Все", "en": "All"},
    "inc.stream.supply": {"ru": "Снабжение", "uk": "Постачання", "en": "Supply"},
    "inc.stream.sales": {"ru": "Продажи", "uk": "Продажі", "en": "Sales"},
    "inc.type.low_stock": {"ru": "Мало остатка", "uk": "Мало залишку", "en": "Low stock"},
    "inc.type.out_of_stock": {"ru": "Нет в наличии", "uk": "Немає в наявності", "en": "Out of stock"},
    "inc.type.stale_data": {"ru": "Данные устарели", "uk": "Дані застаріли", "en": "Stale data"},
    "inc.type.negative_stock": {"ru": "Отрицательный остаток", "uk": "Відʼємний залишок", "en": "Negative stock"},
    "inc.type.job_health": {"ru": "Процесс не отработал", "uk": "Процес не відпрацював", "en": "Job did not run"},
    "inc.type.lm_order_not_accepted": {
        "ru": "Заказ без акцепта", "uk": "Замовлення без акцепту", "en": "Order not accepted"},
    "inc.type.lm_offer_out_of_stock": {
        "ru": "Оффер обнулён", "uk": "Оффер обнулено", "en": "Offer out of stock"},
    "inc.type.lm_health_degraded": {
        "ru": "Показатели канала просели", "uk": "Показники каналу просіли", "en": "Channel health down"},
    "inc.status.open": {"ru": "Открыт", "uk": "Відкрито", "en": "Open"},
    "inc.status.acknowledged": {"ru": "В работе", "uk": "В роботі", "en": "In progress"},
    "inc.status.resolved": {"ru": "Закрыт", "uk": "Закрито", "en": "Resolved"},
    "inc.sev.medium": {"ru": "Средний", "uk": "Середній", "en": "Medium"},
    "inc.sev_help.medium": {
        "ru": "Требует внимания, но не срочно.",
        "uk": "Потребує уваги, але не терміново.",
        "en": "Needs attention, but not urgent.",
    },
    "inc.tbl.col_warehouse": {"ru": "Склад", "uk": "Склад", "en": "Warehouse"},
    "inc.tbl.col_warehouse_help": {
        "ru": "Склад и страна, где возникла проблема",
        "uk": "Склад і країна, де виникла проблема",
        "en": "The warehouse and country where the problem occurred",
    },
    "inc.tbl.col_action": {"ru": "Что делать", "uk": "Що робити", "en": "What to do"},
    "inc.tbl.col_action_help": {
        "ru": "Подсказка по типу инцидента и данным покрытия: откуда взять товар "
              "или что проверить. Не заменяет решение человека",
        "uk": "Підказка за типом інциденту й даними покриття: звідки взяти товар "
              "або що перевірити. Не замінює рішення людини",
        "en": "A hint based on the incident type and coverage data: where to take stock "
              "from or what to check. Does not replace a human decision",
    },
    "inc.act.transfer": {
        "ru": "Есть {qty} шт на местном складе — перебросить",
        "uk": "Є {qty} шт на місцевому складі — перекинути",
        "en": "{qty} units in the local warehouse — transfer",
    },
    "inc.act.order_weeks": {
        "ru": "Своего товара нет, хватит на {w} нед. — заказывать",
        "uk": "Свого товару немає, вистачить на {w} тиж. — замовляти",
        "en": "No own stock, {w} weeks left — place an order",
    },
    "inc.act.order": {
        "ru": "Своего товара нет — заказывать",
        "uk": "Свого товару немає — замовляти",
        "en": "No own stock — place an order",
    },
    "inc.act.check_loader": {
        "ru": "Проверить загрузчик — данные не обновляются",
        "uk": "Перевірити завантажувач — дані не оновлюються",
        "en": "Check the loader — data is not updating",
    },
    "inc.act.accept_order": {
        "ru": "Принять заказ в кабинете Leroy Merlin, иначе отменится",
        "uk": "Прийняти замовлення в кабінеті Leroy Merlin, інакше скасується",
        "en": "Accept the order in Leroy Merlin, otherwise it will be cancelled",
    },
    "inc.act.refill_offer": {
        "ru": "Выставить количество на канал — продажи остановлены",
        "uk": "Виставити кількість на канал — продажі зупинені",
        "en": "List a quantity on the channel — sales are stopped",
    },
    "inc.act.check_channel": {
        "ru": "Разобрать просевшие показатели канала",
        "uk": "Розібрати просілі показники каналу",
        "en": "Review the channel's degraded metrics",
    },
    "inc.act.check_stock": {
        "ru": "Сверить остаток с фактом — в данных отрицательное число",
        "uk": "Звірити залишок з фактом — у даних відʼємне число",
        "en": "Reconcile stock with reality — the data shows a negative number",
    },
    "inc.act.check_job": {
        "ru": "Проверить, почему процесс перестал отрабатывать",
        "uk": "Перевірити, чому процес перестав відпрацьовувати",
        "en": "Check why the job stopped running",
    },
    "inc.title": {"ru": "Инциденты", "uk": "Інциденти", "en": "Incidents"},
    "inc.caption": {
        "ru": "Что требует действия прямо сейчас. Снабжение и продажи — два разных "
              "потока: их смотрят разные люди, переключатель ниже разводит их",
        "uk": "Що потребує дії прямо зараз. Постачання і продажі — два різні потоки: "
              "їх дивляться різні люди, перемикач нижче розводить їх",
        "en": "What needs action right now. Supply and sales are two separate streams "
              "handled by different people — the switch below separates them",
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
    "money.mismatch": {
        "ru": "Цифры на странице завышены: считается {mine:,.0f} €, в данных {real:,.0f} € "
              "(в {k:.1f} раза больше). Строк после соединений {rows} против {ctrl_rows} "
              "в таблице — значит строки размножились при JOIN. Скорее всего развёрнутая "
              "версия страницы отстала от репозитория.",
        "uk": "Цифри на сторінці завищені: рахується {mine:,.0f} €, у даних {real:,.0f} € "
              "(у {k:.1f} раза більше). Рядків після зʼєднань {rows} проти {ctrl_rows} "
              "у таблиці — отже рядки розмножились при JOIN. Найімовірніше розгорнута "
              "версія сторінки відстала від репозиторію.",
        "en": "Figures on this page are inflated: computed {mine:,.0f} €, actual {real:,.0f} € "
              "({k:.1f}× higher). {rows} rows after joins against {ctrl_rows} in the table — "
              "rows were multiplied by a JOIN. The deployed version is likely behind the repo.",
    },
    "money.empty": {
        "ru": "Данные экономики ещё не рассчитаны. Запусти агрегатор в пайплайне.",
        "uk": "Дані економіки ще не розраховані. Запусти агрегатор.",
        "en": "Economics not calculated yet. Run the aggregator.",
    },
    "money.filter.search": {"ru": "Поиск по SKU", "uk": "Пошук за SKU", "en": "Search SKU"},
    "money.filter.search_ph": {"ru": "напр. 41324000", "uk": "напр. 41324000", "en": "e.g. 41324000"},
    "money.kpi.ordered": {
        "ru": "Продажи по заказам", "uk": "Продажі за замовленнями", "en": "Ordered sales"},
    "money.kpi.ordered_help": {
        "ru": "ВСЕ заказы за период, включая ожидающие отгрузку и ещё не отгруженные. "
              "Как в кабинете Amazon: с НДС и доставкой, по дате заказа, отменённые не "
              "вычитаются. Только Amazon — на Mirakl такого отчёта нет, при фильтре «LM» "
              "показывается прочерк. Для сверки с Seller Central: маржа считается не отсюда",
        "uk": "УСІ замовлення за період, включно з тими, що чекають на відвантаження. "
              "Як у кабінеті Amazon: з ПДВ і доставкою, за датою замовлення, скасовані не "
              "віднімаються. Лише Amazon — на Mirakl такого звіту немає, за фільтром «LM» "
              "показується прочерк. Для звірки з Seller Central: маржа рахується не звідси",
        "en": "ALL orders in the period, including those still awaiting shipment. As in "
              "Seller Central: with VAT and shipping, by order date, cancellations not "
              "deducted. Amazon only — Mirakl has no such report, so the «LM» filter shows "
              "a dash. For reconciliation: margin is not based on this",
    },
    "money.kpi.revenue_help": {
        "ru": "Только ОТГРУЖЕННЫЕ заказы: чистая выручка после возвратов, без НДС. "
              "Поэтому она всегда меньше «Продаж по заказам» — там сидят и те заказы, "
              "которые ещё не уехали. С этой строки считается вся экономика ниже",
        "uk": "Лише ВІДВАНТАЖЕНІ замовлення: чиста виручка після повернень, без ПДВ. "
              "Тому вона завжди менша за «Продажі за замовленнями» — там є й ті "
              "замовлення, які ще не поїхали. З цього рядка рахується вся економіка нижче",
        "en": "SHIPPED orders only: net revenue after returns, excluding VAT. It is always "
              "lower than «Ordered sales», which also counts orders not yet shipped. "
              "All economics below are based on this line",
    },
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
    "money.col.markets": {"ru": "Где продаётся", "uk": "Де продається", "en": "Markets"},
    "money.col.markets_help": {
        "ru": "Маркетплейсы, на которых товар продавался за выбранный период. "
              "Цифры в строке — сумма по всем из них",
        "uk": "Маркетплейси, на яких товар продавався за обраний період. "
              "Цифри в рядку — сума за всіма з них",
        "en": "Marketplaces where the product sold in the selected period. "
              "Figures in the row are the total across all of them",
    },
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
        "ru": "Contribution Margin = выручка − комиссии − себестоимость − реклама. "
              "Комиссия площадки отдельно не вычитается: она уже внутри комиссий. "
              "Без логистики. Считается только по SKU с загруженной себестоимостью, "
              "доля выручки указана под карточками.",
        "uk": "Contribution Margin = виручка − комісії − собівартість − реклама. "
              "Комісія майданчика окремо не віднімається: вона вже всередині комісій. "
              "Без логістики. Рахується лише за SKU із завантаженою собівартістю, "
              "частка виручки вказана під картками.",
        "en": "Contribution Margin = revenue − fees − COGS − ads. The marketplace "
              "commission is not deducted separately: it is already inside the fees. "
              "Logistics not included. Computed only over SKUs that have COGS loaded; "
              "the share of revenue covered is shown under the cards.",
    },
    "money.kpi.cogs_missing": {
        "ru": "Себестоимость не загружена — показываем прочерк, а не ноль: ноль на этом "
              "месте дал бы прибыль, равную выручке",
        "uk": "Собівартість не завантажена — показуємо прочерк, а не нуль: нуль тут дав "
              "би прибуток, що дорівнює виручці",
        "en": "COGS not loaded — showing a dash rather than zero: a zero here would make "
              "profit equal to revenue",
    },
    "money.cogs_partial": {
        "ru": "Прибыль и процент маржи посчитаны по {n} SKU из {total} — это {pct}% "
              "выручки ({rev} €). По остальным {miss} себестоимость не загружена, в "
              "расчёт они не вошли. Выручка и «Чистыми» — по всем. Процент маржи "
              "относится к посчитанной части, а не ко всему обороту.",
        "uk": "Прибуток і відсоток маржі пораховано за {n} SKU з {total} — це {pct}% "
              "виручки ({rev} €). За рештою {miss} собівартість не завантажена, у "
              "розрахунок вони не увійшли. Виручка і «Чистими» — за всіма. Відсоток "
              "маржі стосується порахованої частини, а не всього обороту.",
        "en": "Profit and margin percentage are computed over {n} of {total} SKUs — that "
              "is {pct}% of revenue ({rev} €). The remaining {miss} have no COGS loaded "
              "and were excluded. Revenue and net proceeds cover all of them. The margin "
              "percentage refers to the computed part, not to the whole turnover.",
    },
    "money.struct.commission": {
        "ru": "Комиссия площадки", "uk": "Комісія майданчика",
        "en": "Marketplace commission"},
    "money.col.commission": {
        "ru": "Комиссия площадки", "uk": "Комісія майданчика", "en": "Commission"},
    "money.col.commission_help": {
        "ru": "Справочная колонка. Для Leroy Merlin комиссия площадки и есть все комиссии: "
              "commission_fee и total_fees — одно поле, а не два. У Amazon прочерк: там "
              "комиссия внутри общих комиссий и отдельно не выделяется, так устроен SP-API. "
              "Из прибыли отдельно НЕ вычитается — «Чистыми» уже за вычетом комиссий, "
              "второе вычитание посчитало бы те же деньги дважды.",
        "uk": "Довідкова колонка. Для Leroy Merlin комісія майданчика і є всі комісії: "
              "commission_fee і total_fees — одне поле, а не два. В Amazon прочерк: там "
              "комісія всередині загальних комісій і окремо не виділяється, так влаштовано "
              "SP-API. З прибутку окремо НЕ віднімається — «Чистими» вже за вирахуванням "
              "комісій, друге віднімання порахувало б ті самі гроші двічі.",
        "en": "Reference column. For Leroy Merlin the marketplace commission IS the whole "
              "fee: commission_fee and total_fees are one field, not two. Amazon shows a "
              "dash — there the commission sits inside total fees and is not broken out, "
              "by SP-API design. It is NOT deducted from profit separately: net proceeds "
              "are already after fees, so deducting again would count the same money twice.",
    },
    "money.struct.commission_note": {
        "ru": "Справочно: из них комиссия площадки — {v} €. Отдельным сегментом в круге "
              "её нет, это те же деньги, что и «Комиссии маркетплейса»: у Mirakl они "
              "приходят одним полем, у Amazon отдельно не выделяются.",
        "uk": "Довідково: з них комісія майданчика — {v} €. Окремим сегментом у колі її "
              "немає, це ті самі гроші, що й «Комісії маркетплейсу»: у Mirakl вони "
              "приходять одним полем, в Amazon окремо не виділяються.",
        "en": "For reference: {v} € of this is the marketplace commission. It has no "
              "separate slice in the chart — it is the same money as «Marketplace fees»: "
              "Mirakl reports it as a single field, Amazon does not break it out at all.",
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
    "money.col.asin_help": {
        "ru": "Нажми, чтобы открыть карточку товара на Amazon той страны, где он продаётся",
        "uk": "Натисни, щоб відкрити картку товару на Amazon тієї країни, де він продається",
        "en": "Click to open the product page on the Amazon marketplace where it sells",
    },
    "money.col.bsr": {"ru": "Место", "uk": "Місце", "en": "Rank"},
    "money.col.bsr_help": {
        "ru": "Best Sellers Rank: место товара в рейтинге продаж своей подкатегории "
              "Amazon. Чем меньше число, тем выше товар — первое место лучше сотого. "
              "Зависит не только от наших продаж: конкурент вырос — мы опустились при "
              "тех же продажах. Источник: asin_bsr_daily, поле rank.",
        "uk": "Best Sellers Rank: місце товару в рейтингу продажів своєї підкатегорії "
              "Amazon. Чим менше число, тим вище товар — перше місце краще за соте. "
              "Залежить не лише від наших продажів: конкурент зріс — ми опустилися за "
              "тих самих продажів. Джерело: asin_bsr_daily, поле rank.",
        "en": "Best Sellers Rank: the product's place in the sales ranking of its Amazon "
              "subcategory. The lower the number, the higher the product — rank 1 beats "
              "rank 100. It depends on competitors too: if someone else grows, we drop at "
              "the same sales. Source: asin_bsr_daily, field rank.",
    },
    "money.col.bsr_delta": {"ru": "Сдвиг", "uk": "Зсув", "en": "Shift"},
    "money.col.bsr_delta_help": {
        "ru": "На сколько позиций товар сместился в подкатегории за ВЫБРАННЫЙ период — "
              "от первого дня с данными до последнего. При периоде «7» это неделя, при "
              "«30» — месяц. Знак перевёрнут относительно самого места: подъём в "
              "рейтинге — это уменьшение номера, но в этой колонке он показан ПЛЮСОМ. "
              "Плюс — товар поднялся, минус — опустился. Падение при растущей рекламе "
              "значит, что деньги уходят, а позиция теряется.",
        "uk": "На скільки позицій товар змістився в підкатегорії за ОБРАНИЙ період — від "
              "першого дня з даними до останнього. За періоду «7» це тиждень, за «30» — "
              "місяць. Знак перевернуто відносно самого місця: підйом у рейтингу — це "
              "зменшення номера, але в цій колонці він показаний ПЛЮСОМ. Плюс — товар "
              "піднявся, мінус — опустився. Падіння за зростаючої реклами означає, що "
              "гроші йдуть, а позиція втрачається.",
        "en": "How many places the product moved within its subcategory over the SELECTED "
              "period — from the first day with data to the last. With period «7» that is "
              "a week, with «30» a month. The sign is inverted relative to the rank "
              "itself: moving up the ranking means a smaller number, but this column "
              "shows it as a PLUS. Plus means the product rose, minus means it fell. "
              "A drop while ad spend grows means money is going out and position is "
              "being lost.",
    },
    "rev.bsr.title": {
        "ru": "Движение в категории Amazon",
        "uk": "Рух у категорії Amazon",
        "en": "Movement in the Amazon category",
    },
    "rev.bsr.up": {"ru": "Поднялись", "uk": "Піднялися", "en": "Moved up"},
    "rev.bsr.down": {"ru": "Опустились", "uk": "Опустилися", "en": "Moved down"},
    "rev.bsr.tracked": {"ru": "Под наблюдением", "uk": "Під спостереженням", "en": "Tracked"},
    "rev.bsr.tracked_help": {
        "ru": "Товары, которым Amazon присваивает место в категории. Остальным он его "
              "не даёт — для этого нужен минимальный объём продаж",
        "uk": "Товари, яким Amazon присвоює місце в категорії. Іншим він його не дає — "
              "для цього потрібен мінімальний обсяг продажів",
        "en": "Products Amazon assigns a category rank to. It doesn't rank the rest — "
              "that requires a minimum sales volume",
    },
    "rev.bsr.rank": {"ru": "Место в категории", "uk": "Місце в категорії", "en": "Category rank"},
    "rev.bsr.axis": {"ru": "Товаров", "uk": "Товарів", "en": "Products"},
    "rev.bsr.note": {
        "ru": "По {n} товарам, которым Amazon присваивает место в категории. Вверх — "
              "поднялись, вниз — опустились. Позиция зависит и от конкурентов: товар "
              "может опуститься при тех же продажах, если кто-то другой вырос.",
        "uk": "По {n} товарах, яким Amazon присвоює місце в категорії. Вгору — "
              "піднялися, вниз — опустилися. Позиція залежить і від конкурентів: товар "
              "може опуститися за тих самих продажів, якщо хтось інший зріс.",
        "en": "Across {n} products Amazon ranks. Up means they moved up in the category, "
              "down means they dropped. Position also depends on competitors — a product "
              "can fall at the same sales if someone else grows.",
    },
    "rev.bsr.wait": {
        "ru": "Движение в категории считается сравнением с предыдущим днём, а сбор "
              "начался только что — сравнивать пока не с чем. Первые столбцы появятся "
              "завтра, читаемая картина через три-четыре дня.",
        "uk": "Рух у категорії рахується порівнянням із попереднім днем, а збір "
              "почався щойно — порівнювати поки нема з чим. Перші стовпці зʼявляться "
              "завтра, читабельна картина за три-чотири дні.",
        "en": "Category movement is measured against the previous day, and collection has "
              "only just started — there is nothing to compare yet. The first bars appear "
              "tomorrow, a readable picture in three or four days.",
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
    "money.alert.show_losers": {
        "ru": "Показать эти {n} в таблице", "uk": "Показати ці {n} у таблиці",
        "en": "Show these {n} in the table"},
    "money.alert.show_thin": {
        "ru": "Показать эти {n} в таблице", "uk": "Показати ці {n} у таблиці",
        "en": "Show these {n} in the table"},
    "money.alert.filtered_losers": {
        "ru": "Показаны только убыточные позиции — {n}. Нажми кнопку ещё раз, "
              "чтобы вернуть весь список.",
        "uk": "Показані лише збиткові позиції — {n}. Натисни кнопку ще раз, "
              "щоб повернути весь список.",
        "en": "Showing loss-making items only — {n}. Click the button again to "
              "restore the full list.",
    },
    "money.alert.filtered_thin": {
        "ru": "Показаны только позиции с маржой ниже 5% — {n}. Нажми кнопку ещё раз, "
              "чтобы вернуть весь список.",
        "uk": "Показані лише позиції з маржею нижче 5% — {n}. Натисни кнопку ще раз, "
              "щоб повернути весь список.",
        "en": "Showing items with margin under 5% only — {n}. Click the button again "
              "to restore the full list.",
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
    "money.alerts.window_note": {
        "ru": "Алерты считаются за 30 дней и не зависят от выбранного выше периода. "
              "Поэтому товар может числиться здесь, даже если сейчас снят с продажи — "
              "расход был раньше.",
        "uk": "Алерти рахуються за 30 днів і не залежать від обраного вище періоду. "
              "Тому товар може значитись тут, навіть якщо зараз знятий з продажу — "
              "витрата була раніше.",
        "en": "Alerts are calculated over 30 days and do not depend on the period selected "
              "above. So a product can appear here even if it is currently suppressed — "
              "the spend happened earlier.",
    },
    "money.alerts.note": {
        "ru": "Алерты пересчитываются ежедневно в 12:30 по данным рекламы (SP+SD) и P&L за 30 дней.",
        "uk": "Алерти перераховуються щодня о 12:30 за даними реклами та P&L за 30 днів.",
        "en": "Alerts recalculated daily at 12:30 from ads (SP+SD) and 30-day P&L.",
    },

    # --- 5_Money.py: выбор периода ---
    "money.period_days": {
        "ru": "Продажи за {d} дней", "uk": "Продажі за {d} днів", "en": "Sales, last {d} days"},
    "money.period_title": {
        "ru": "Период: {f} — {to}", "uk": "Період: {f} — {to}", "en": "Period: {f} — {to}"},
    "money.period_lag": {
        "ru": "Данные есть по {d} включительно — Amazon отдаёт отчёты с задержкой, "
              "последние {n} дн. ещё не загружены.",
        "uk": "Дані є по {d} включно — Amazon віддає звіти із затримкою, останні {n} дн. "
              "ще не завантажені.",
        "en": "Data is available up to {d} — Amazon delivers reports with a delay, "
              "the last {n} days are not loaded yet.",
    },
    "money.period.label": {"ru": "Период", "uk": "Період", "en": "Period"},
    "money.period.month": {"ru": "Этот месяц", "uk": "Цей місяць", "en": "This month"},
    "money.period.custom": {"ru": "Свой", "uk": "Свій", "en": "Custom"},
    "money.period.range": {"ru": "Даты от–до", "uk": "Дати від–до", "en": "Date range"},
    "money.period.pick": {"ru": "Выбери обе даты периода", "uk": "Обери обидві дати періоду", "en": "Pick both dates"},

    # --- 7_Reviews.py: монитор запросов на отзывы ---
    "nav.reviews": {"ru": "Отзывы", "uk": "Відгуки", "en": "Reviews"},
    "rev.title": {"ru": "Отзывы", "uk": "Відгуки", "en": "Reviews"},
    "rev.caption": {
        "ru": "Автоматические запросы на отзыв: сколько уходит, что покрыто, где теряем",
        "uk": "Автоматичні запити на відгук: скільки йде, що покрито, де втрачаємо",
        "en": "Automated review requests: how many go out, what is covered, where we lose",
    },
    "rev.no_table": {
        "ru": "Рассылка ещё не запускалась — таблица журнала не создана.",
        "uk": "Розсилка ще не запускалась — таблиця журналу не створена.",
        "en": "The mailing hasn't run yet — the log table does not exist.",
    },
    "rev.empty": {
        "ru": "Журнал пуст. Запусти отправитель в пайплайне.",
        "uk": "Журнал порожній. Запусти відправник у пайплайні.",
        "en": "The log is empty. Run the sender in the pipeline.",
    },
    "rev.health_ok": {
        "ru": "Рассылка работает. Последняя отправка: {when} по Мадриду",
        "uk": "Розсилка працює. Остання відправка: {when} за Мадридом",
        "en": "Mailing is running. Last send: {when} Madrid time",
    },
    "rev.health_stopped": {
        "ru": "Рассылка не работает {h:.0f} ч. Порог — 25 ч. Проверь расписание отправителя.",
        "uk": "Розсилка не працює {h:.0f} год. Поріг — 25 год. Перевір розклад відправника.",
        "en": "No sends for {h:.0f}h (threshold 25h). Check the sender schedule.",
    },
    "rev.health_never": {
        "ru": "Ни одного запроса ещё не отправлено.",
        "uk": "Жодного запиту ще не надіслано.",
        "en": "No requests have been sent yet.",
    },
    "rev.period": {"ru": "Период", "uk": "Період", "en": "Period"},
    "rev.kpi.today": {"ru": "Сегодня", "uk": "Сьогодні", "en": "Today"},
    "rev.kpi.week": {"ru": "За неделю", "uk": "За тиждень", "en": "This week"},
    "rev.kpi.today_help": {
        "ru": "Запросов отправлено с начала сегодняшнего дня по мадридскому времени",
        "uk": "Запитів надіслано з початку сьогоднішнього дня за мадридським часом",
        "en": "Requests sent since the start of today, Madrid time",
    },
    "rev.col.coverage_help": {
        "ru": "Доля заказов, по которым запрос реально ушёл: отправлено / заказов × 100",
        "uk": "Частка замовлень, за якими запит реально пішов: надіслано / замовлень × 100",
        "en": "Share of orders where the request actually went out: sent / orders × 100",
    },
    "rev.kpi.week_help": {
        "ru": "Запросов на отзыв отправлено за последнюю неделю",
        "uk": "Запитів на відгук надіслано за останній тиждень",
        "en": "Review requests sent over the last week",
    },
    "rev.kpi.pool": {"ru": "В очереди", "uk": "У черзі", "en": "In queue"},
    "rev.kpi.pool_help": {
        "ru": "Заказы в окне 8–33 дня, по которым запрос ещё не проверяли",
        "uk": "Замовлення у вікні 8–33 дні, по яких запит ще не перевіряли",
        "en": "Orders in the 8–33 day window not yet processed",
    },
    "rev.kpi.burning": {"ru": "Горит", "uk": "Горить", "en": "Urgent"},
    "rev.kpi.burning_help": {
        "ru": "Заказы старше 26 дней — окно отправки скоро закроется",
        "uk": "Замовлення старші 26 днів — вікно відправки скоро закриється",
        "en": "Orders older than 26 days — the send window is about to close",
    },
    "rev.kpi.skipped": {"ru": "Возвраты", "uk": "Повернення", "en": "Returns"},
    "rev.kpi.skipped_help": {
        "ru": "По этим заказам был возврат — запрос на отзыв не отправляем",
        "uk": "По цих замовленнях було повернення — запит на відгук не надсилаємо",
        "en": "These orders had a return — no review request is sent",
    },
    "rev.tab.coverage": {"ru": "Покрытие", "uk": "Покриття", "en": "Coverage"},
    "rev.tab.dynamics": {"ru": "Динамика отзывов", "uk": "Динаміка відгуків", "en": "Review growth"},
    "rev.dyn.no_data": {
        "ru": "Данных о количестве отзывов пока нет — сбор только запущен.",
        "uk": "Даних про кількість відгуків поки немає — збір щойно запущено.",
        "en": "No review count data yet — collection has just started.",
    },
    "rev.dyn.no_stable": {
        "ru": "Пока нет позиций со стабильными данными для сравнения.",
        "uk": "Поки немає позицій зі стабільними даними для порівняння.",
        "en": "No products with stable data to compare yet.",
    },
    "rev.dyn.total": {"ru": "Отзывов всего", "uk": "Відгуків всього", "en": "Reviews total"},
    "rev.dyn.total_help": {
        "ru": "Сумма отзывов по {n} позициям на последний снимок каждой — данные "
              "на {d}. Величина накопительная: от выбранного периода не зависит, "
              "период влияет на «Прибавилось» и на график. Состав позиций один и "
              "тот же для всех периодов, берётся по наблюдению за {w} дней; "
              "позиции со скачущим счётчиком в сумму не входят.",
        "uk": "Сума відгуків по {n} позиціях на останній знімок кожної — дані "
              "на {d}. Величина накопичувальна: від обраного періоду не залежить, "
              "період впливає на «Додалося» і на графік. Склад позицій той самий "
              "для всіх періодів, береться за спостереженням у {w} днів; позиції "
              "зі стрибучим лічильником у суму не входять.",
        "en": "Total reviews across {n} items at each item's latest snapshot — data "
              "as of {d}. This is a cumulative figure: it does not depend on the "
              "selected period, which affects «Added» and the chart instead. The set "
              "of items is the same for every period, derived from {w} days of "
              "tracking; items with a jumping counter are excluded.",
    },
    "rev.dyn.growth": {"ru": "Прибавилось", "uk": "Додалося", "en": "Added"},
    "rev.dyn.growth_help": {
        "ru": "Прирост за {d} дней наблюдения — по тем же позициям, что и «Отзывов "
              "всего». Зависит от периода и с его расширением только растёт: если "
              "за 30 дней прибавка меньше, чем за 14, это ошибка, а не данные.",
        "uk": "Приріст за {d} днів спостереження — по тих самих позиціях, що й "
              "«Відгуків всього». Залежить від періоду і з його розширенням лише "
              "зростає: якщо за 30 днів приріст менший, ніж за 14, це помилка.",
        "en": "Growth over {d} days of tracking, across the same items as «Reviews "
              "total». It depends on the period and can only increase as the period "
              "widens: if 30 days shows less growth than 14, that is a bug, not data.",
    },
    "rev.dyn.before": {"ru": "В день до", "uk": "На день до", "en": "Per day before"},
    "rev.dyn.before_help": {
        "ru": "Сколько отзывов прибавлялось в день до запуска рассылки",
        "uk": "Скільки відгуків додавалося на день до запуску розсилки",
        "en": "Reviews added per day before the mailing started",
    },
    "rev.dyn.after": {"ru": "В день после", "uk": "На день після", "en": "Per day after"},
    "rev.dyn.after_help": {
        "ru": "Сколько отзывов прибавляется в день после запуска рассылки",
        "uk": "Скільки відгуків додається на день після запуску розсилки",
        "en": "Reviews added per day since the mailing started",
    },
    "rev.dyn.chart": {
        "ru": "Отправленные запросы и новые отзывы по дням",
        "uk": "Надіслані запити та нові відгуки за днями",
        "en": "Requests sent and new reviews by day",
    },
    "rev.dyn.new_reviews": {"ru": "Новых отзывов", "uk": "Нових відгуків", "en": "New reviews"},
    "rev.dyn.launch": {"ru": "Старт рассылки", "uk": "Старт розсилки", "en": "Mailing started"},
    "rev.dyn.gap_note": {
        "ru": "Сборщик не отработал {n} дн. ({days}) — в эти дни данных нет, "
              "линия прироста разорвана. Это пропуск сбора, а не отсутствие отзывов.",
        "uk": "Збирач не відпрацював {n} дн. ({days}) — у ці дні даних немає, "
              "лінія приросту розірвана. Це пропуск збору, а не відсутність відгуків.",
        "en": "The collector did not run for {n} day(s) ({days}) — no data for those "
              "days, so the growth line is broken. A collection gap, not missing reviews.",
    },
    "rev.dyn.filtered_note": {
        "ru": "В таблице есть данные по {raw}, но свежие дни не прошли отбор "
              "стабильности и на графике показано по {shown}. Обычно это значит, "
              "что сборщик вернул другой набор товаров — стоит проверить его логи.",
        "uk": "У таблиці є дані по {raw}, але свіжі дні не пройшли відбір "
              "стабільності і на графіку показано по {shown}. Зазвичай це означає, "
              "що збирач повернув інший набір товарів — варто перевірити його логи.",
        "en": "The table has data through {raw}, but the most recent days did not pass "
              "the stability filter, so the chart shows data through {shown}. Usually "
              "this means the collector returned a different product set — check its logs.",
    },
    "rev.dyn.lag_note": {
        "ru": "Отзыв появляется не сразу: покупатель получает письмо, пишет отзыв, "
              "Amazon его публикует — обычно проходит 3–5 дней. Поэтому всплеск отзывов "
              "отстаёт от дня отправки примерно на четыре дня.",
        "uk": "Відгук зʼявляється не одразу: покупець отримує лист, пише відгук, "
              "Amazon його публікує — зазвичай минає 3–5 днів. Тому сплеск відгуків "
              "відстає від дня відправки приблизно на чотири дні.",
        "en": "A review does not appear immediately: the buyer receives the email, writes "
              "the review, Amazon publishes it — usually 3–5 days. So the spike in reviews "
              "lags the send date by roughly four days.",
    },
    "rev.dyn.grown": {"ru": "Товаров выросло", "uk": "Товарів зросло", "en": "Products grown"},
    "rev.dyn.grown_help": {
        "ru": "Сколько позиций из {n} получили новые отзывы за период",
        "uk": "Скільки позицій з {n} отримали нові відгуки за період",
        "en": "How many of {n} tracked items gained new reviews",
    },
    "rev.dyn.excluded": {"ru": "Исключено из счёта", "uk": "Виключено з підрахунку", "en": "Excluded"},
    "rev.dyn.excluded_help": {
        "ru": "Позиции, где число отзывов скачет: Amazon показывает то отзывы страны, "
              "то все европейские. Такие данные для сравнения не годятся.",
        "uk": "Позиції, де число відгуків стрибає: Amazon показує то відгуки країни, "
              "то всі європейські. Такі дані для порівняння не годяться.",
        "en": "Items where the review count jumps: Amazon sometimes shows country reviews, "
              "sometimes all European ones. Such data is not usable for comparison.",
    },
    "rev.dyn.top": {"ru": "Где отзывов прибавилось больше всего", "uk": "Де відгуків додалося найбільше", "en": "Biggest review gains"},
    "rev.dyn.was": {"ru": "Было", "uk": "Було", "en": "Was"},
    "rev.dyn.now": {"ru": "Стало", "uk": "Стало", "en": "Now"},
    "rev.dyn.plus": {"ru": "Прирост", "uk": "Приріст", "en": "Gain"},
    "rev.dyn.rating": {"ru": "Оценка", "uk": "Оцінка", "en": "Rating"},
    "rev.dyn.note": {
        "ru": "Часть отзывов появилась бы и без рассылки — покупатели пишут их сами. "
              "Поэтому сравниваем не общий прирост, а скорость: сколько отзывов "
              "прибавлялось в день до запуска и сколько после.",
        "uk": "Частина відгуків зʼявилася б і без розсилки — покупці пишуть їх самі. "
              "Тому порівнюємо не загальний приріст, а швидкість: скільки відгуків "
              "додавалося на день до запуску і скільки після.",
        "en": "Some reviews would have appeared anyway — buyers write them on their own. "
              "That is why we compare the rate, not the total: how many reviews were added "
              "per day before the launch and how many after.",
    },
    "rev.tab.marketplace": {"ru": "По маркетплейсам", "uk": "За маркетплейсами", "en": "By marketplace"},
    "rev.tab.age": {"ru": "Возраст заказа", "uk": "Вік замовлення", "en": "Order age"},
    "rev.tab.asin": {"ru": "По товарам", "uk": "За товарами", "en": "By product"},
    "rev.sum.orders": {"ru": "Заказов", "uk": "Замовлень", "en": "Orders"},
    "rev.sum.matured_only": {
        "ru": "Только дозревшие даты — свежие заказы ещё не в окне отправки",
        "uk": "Лише дозрілі дати — свіжі замовлення ще не у вікні відправки",
        "en": "Matured dates only — fresh orders are not in the send window yet",
    },
    "rev.sum.processed": {"ru": "Обработано", "uk": "Оброблено", "en": "Processed"},
    "rev.sum.coverage": {"ru": "Покрытие", "uk": "Покриття", "en": "Coverage"},
    "rev.sum.missed": {"ru": "Упущено", "uk": "Втрачено", "en": "Missed"},
    "rev.sum.missed_help": {
        "ru": "Окно отправки закрылось, а запрос так и не ушёл — отзывы потеряны",
        "uk": "Вікно відправки закрилось, а запит так і не пішов — відгуки втрачені",
        "en": "The send window closed with no request sent — reviews lost",
    },
    "rev.chart.orders_vs_processed": {
        "ru": "Заказы и обработка по датам",
        "uk": "Замовлення та обробка за датами",
        "en": "Orders and processing by date",
    },
    "rev.chart.by_marketplace": {
        "ru": "Результат обработки по маркетплейсам",
        "uk": "Результат обробки за маркетплейсами",
        "en": "Processing outcome by marketplace",
    },
    "rev.table.by_date": {"ru": "Покрытие по датам заказа", "uk": "Покриття за датами замовлення", "en": "Coverage by order date"},
    "rev.col.date": {"ru": "Дата заказа", "uk": "Дата замовлення", "en": "Order date"},
    "rev.col.orders": {"ru": "Заказов", "uk": "Замовлень", "en": "Orders"},
    "rev.col.processed": {"ru": "Обработано", "uk": "Оброблено", "en": "Processed"},
    "rev.col.sent": {"ru": "Отправлено", "uk": "Надіслано", "en": "Sent"},
    "rev.col.no_action": {"ru": "Amazon отказал", "uk": "Amazon відмовив", "en": "Declined"},
    "rev.col.no_action_help": {
        "ru": "Amazon не разрешил запрос: заказ не доставлен, запрос уже был или покупатель отказался от писем",
        "uk": "Amazon не дозволив запит: замовлення не доставлене, запит уже був або покупець відмовився від листів",
        "en": "Amazon did not allow the request: not delivered, already requested, or buyer opted out",
    },
    "rev.col.skipped": {"ru": "Возврат", "uk": "Повернення", "en": "Return"},
    "rev.col.skipped_help": {
        "ru": "По заказу был возврат — запрос не отправляли намеренно",
        "uk": "По замовленню було повернення — запит не надсилали навмисно",
        "en": "The order had a return — request deliberately not sent",
    },
    "rev.col.coverage": {"ru": "Покрытие", "uk": "Покриття", "en": "Coverage"},
    "rev.col.pending": {"ru": "Не обработано", "uk": "Не оброблено", "en": "Pending"},
    "rev.col.status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "rev.col.marketplace": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "rev.col.product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "rev.col.hit_rate": {"ru": "Доля разрешённых", "uk": "Частка дозволених", "en": "Allowed rate"},
    "rev.col.hit_rate_help": {
        "ru": "Какую долю проверенных заказов Amazon разрешил запросить",
        "uk": "Яку частку перевірених замовлень Amazon дозволив запитати",
        "en": "Share of checked orders Amazon allowed to request",
    },
    "rev.st.ok": {"ru": "В норме", "uk": "В нормі", "en": "On target"},
    "rev.st.catching": {"ru": "Догоняем", "uk": "Доганяємо", "en": "Catching up"},
    "rev.st.missed": {"ru": "Упущено", "uk": "Втрачено", "en": "Missed"},
    "rev.st.maturing": {"ru": "Зреет", "uk": "Зріє", "en": "Maturing"},
    "rev.legend": {
        "ru": "В норме — покрытие 90% и выше. Догоняем — ниже цели, но окно ещё открыто, "
              "запросы дошлются. Упущено — окно закрылось, отзывы потеряны. "
              "Зреет — заказ моложе 8 дней, отправка пока невозможна.",
        "uk": "В нормі — покриття 90% і вище. Доганяємо — нижче цілі, але вікно ще відкрите, "
              "запити дошлються. Втрачено — вікно закрилось, відгуки втрачені. "
              "Зріє — замовлення молодше 8 днів, відправка поки неможлива.",
        "en": "On target — coverage 90% or above. Catching up — below target but the window "
              "is still open. Missed — the window closed, reviews are lost. "
              "Maturing — order younger than 8 days, sending not possible yet.",
    },
    "rev.chart.no_action_note": {
        "ru": "Синим — всего заказов за дату. Столбец рядом показывает, что с ними "
              "сделано: зелёным — запрос отправлен, серым — Amazon отклонил (заказ не "
              "доставлен, запрос уже был или покупатель отписался от писем), жёлтым — "
              "заказ с возвратом, такие пропускаем намеренно. Три части в сумме дают "
              "общее число заказов. Красная линия — доля отправленных.",
        "uk": "Синім — усього замовлень за дату. Стовпець поруч показує, що з ними "
              "зроблено: зеленим — запит надіслано, сірим — Amazon відхилив (замовлення "
              "не доставлено, запит уже був або покупець відписався), жовтим — замовлення "
              "з поверненням, такі пропускаємо навмисно. Три частини в сумі дають "
              "загальне число замовлень. Червона лінія — частка надісланих.",
        "en": "Blue — total orders for the date. The bar next to it shows what happened "
              "to them: green — request sent, grey — Amazon declined (not delivered, "
              "already requested, or the buyer opted out), amber — order with a return, "
              "deliberately skipped. The three parts add up to the total. The red line "
              "is the share sent.",
    },
    "rev.table.by_date_marketplace": {
        "ru": "Покрытие по датам и маркетплейсам",
        "uk": "Покриття за датами та маркетплейсами",
        "en": "Coverage by date and marketplace",
    },
    "rev.table.marketplace_filter": {
        "ru": "Маркетплейсы в таблице",
        "uk": "Маркетплейси в таблиці",
        "en": "Marketplaces in the table",
    },
    "rev.intro.title": {
        "ru": "Как читать дашборд",
        "uk": "Як читати дашборд",
        "en": "How to read this dashboard",
    },
    "rev.intro.body": {
        "ru": "Запрос можно отправить только когда заказу {min}–{max} дней. "
              "Свежие даты — «{maturing}», отправка ещё невозможна. "
              "«{catching}» — окно открыто, система ещё успеет. "
              "«{missed}» — окно закрылось, отзыв уже не запросить.",
        "uk": "Запит можна надіслати лише коли замовленню {min}–{max} днів. "
              "Свіжі дати — «{maturing}», відправка ще неможлива. "
              "«{catching}» — вікно відкрите, система ще встигне. "
              "«{missed}» — вікно закрилось, відгук уже не запросити.",
        "en": "A request can only be sent when the order is {min}\u2013{max} days old. "
              "Recent dates show \u201c{maturing}\u201d \u2014 sending is not possible yet. "
              "\u201c{catching}\u201d \u2014 the window is open, the system will catch up. "
              "\u201c{missed}\u201d \u2014 the window closed, the review can no longer be requested.",
    },
    "rev.st.ok_desc": {
        "ru": "Покрытие 90% и выше — запросы ушли, делать ничего не нужно.",
        "uk": "Покриття 90% і вище — запити пішли, робити нічого не треба.",
        "en": "Coverage 90% or above — requests went out, no action needed.",
    },
    "rev.st.catching_desc": {
        "ru": "Ниже цели, но окно ещё открыто — запросы дошлют автоматически.",
        "uk": "Нижче цілі, але вікно ще відкрите — запити дошлють автоматично.",
        "en": "Below target, but the window is still open — requests will be sent automatically.",
    },
    "rev.st.missed_desc": {
        "ru": "Окно {min}–{max} дней закрылось, а покрытие осталось низким — "
              "эти отзывы потеряны навсегда.",
        "uk": "Вікно {min}–{max} днів закрилось, а покриття залишилось низьким — "
              "ці відгуки втрачені назавжди.",
        "en": "The {min}–{max} day window closed with coverage still low — "
              "these reviews are lost for good.",
    },
    "rev.st.maturing_desc": {
        "ru": "Заказ младше {min} дней — отправка пока невозможна, это норма.",
        "uk": "Замовлення молодше {min} днів — відправка поки неможлива, це норма.",
        "en": "The order is younger than {min} days — sending is not possible yet, this is normal.",
    },
    "rev.formula.title": {"ru": "Формула", "uk": "Формула", "en": "Formula"},
    "rev.funnel.title": {
        "ru": "Где теряются запросы",
        "uk": "Де губляться запити",
        "en": "Where requests are lost",
    },
    "rev.funnel.orders": {"ru": "Заказов", "uk": "Замовлень", "en": "Orders"},
    "rev.funnel.checked": {"ru": "Проверено", "uk": "Перевірено", "en": "Checked"},
    "rev.funnel.allowed": {"ru": "Amazon разрешил", "uk": "Amazon дозволив", "en": "Amazon allowed"},
    "rev.funnel.sent": {"ru": "Отправлено", "uk": "Надіслано", "en": "Sent"},
    "rev.funnel.note": {
        "ru": "Основная потеря — между «Проверено» и «Amazon разрешил»: это решение Amazon, "
              "а не сбой системы. Разрыв между «Заказов» и «Проверено» — наша зона ответственности.",
        "uk": "Основна втрата — між «Перевірено» і «Amazon дозволив»: це рішення Amazon, "
              "а не збій системи. Розрив між «Замовлень» і «Перевірено» — наша зона відповідальності.",
        "en": "The main drop is between \u201cChecked\u201d and \u201cAmazon allowed\u201d — that is Amazon's "
              "decision, not a system failure. The gap between \u201cOrders\u201d and \u201cChecked\u201d is ours.",
    },
    "rev.table.sort_hint": {
        "ru": "Нажми на заголовок колонки, чтобы отсортировать. Повторный клик меняет порядок.",
        "uk": "Натисни на заголовок колонки, щоб відсортувати. Повторний клік змінює порядок.",
        "en": "Click a column header to sort. Click again to reverse the order.",
    },
    "rev.table.split_by_marketplace": {
        "ru": "Разбить по маркетплейсам",
        "uk": "Розбити за маркетплейсами",
        "en": "Split by marketplace",
    },
    "rev.table.all_marketplaces": {"ru": "Все", "uk": "Всі", "en": "All"},
    "rev.legend.ok_short": {
        "ru": "покрытие 90% и выше",
        "uk": "покриття 90% і вище",
        "en": "coverage 90% or above",
    },
    "rev.legend.catching_short": {
        "ru": "окно открыто, запросы дошлются",
        "uk": "вікно відкрите, запити дошлються",
        "en": "window open, requests will follow",
    },
    "rev.legend.missed_short": {
        "ru": "окно закрылось, отзывы потеряны",
        "uk": "вікно закрилось, відгуки втрачені",
        "en": "window closed, reviews lost",
    },
    "rev.legend.maturing_short": {
        "ru": "заказ младше {min} дней",
        "uk": "замовлення молодше {min} днів",
        "en": "order younger than {min} days",
    },
    "rev.download": {"ru": "Скачать покрытие CSV", "uk": "Завантажити покриття CSV", "en": "Download coverage CSV"},
    "rev.mp.metric_help": {
        "ru": "Отправлено запросов и общее покрытие по маркетплейсу",
        "uk": "Надіслано запитів і загальне покриття за маркетплейсом",
        "en": "Requests sent and overall coverage for this marketplace",
    },
    "rev.age.title": {
        "ru": "Когда Amazon чаще разрешает запрос",
        "uk": "Коли Amazon частіше дозволяє запит",
        "en": "When Amazon is most likely to allow a request",
    },
    "rev.age.caption": {
        "ru": "По оси — возраст заказа в днях. Столбцы — сколько заказов проверено, "
              "линия — какую долю Amazon разрешил. По этим данным будем настраивать окно отправки.",
        "uk": "По осі — вік замовлення в днях. Стовпці — скільки замовлень перевірено, "
              "лінія — яку частку Amazon дозволив. За цими даними налаштуємо вікно відправки.",
        "en": "X axis — order age in days. Bars show orders checked, the line shows the share "
              "Amazon allowed. We will tune the send window from this data.",
    },
    "rev.age.axis": {"ru": "Дней с даты заказа", "uk": "Днів з дати замовлення", "en": "Days since order"},
    "rev.age.checked": {"ru": "Проверено", "uk": "Перевірено", "en": "Checked"},
    "rev.slot.title": {
        "ru": "Утро против вечера: сравнение расписаний",
        "uk": "Ранок проти вечора: порівняння розкладів",
        "en": "Morning vs evening: schedule comparison",
    },
    "rev.slot.caption": {
        "ru": "С 19 августа Испания отправляет в 19:00 по Мадриду, остальные страны — "
              "в 09:00 по Киеву. Сравниваем долю запросов, которые Amazon разрешил: "
              "это видно сразу, в отличие от прироста отзывов.",
        "uk": "З 19 серпня Іспанія надсилає о 19:00 за Мадридом, решта країн — "
              "о 09:00 за Києвом. Порівнюємо частку запитів, які Amazon дозволив: "
              "це видно одразу, на відміну від приросту відгуків.",
        "en": "Since 19 August Spain sends at 19:00 Madrid time, other countries at "
              "09:00 Kyiv time. We compare the share of requests Amazon allowed — that "
              "is visible immediately, unlike review growth.",
    },
    "rev.slot.evening": {"ru": "Вечер · Испания", "uk": "Вечір · Іспанія", "en": "Evening · Spain"},
    "rev.slot.morning": {"ru": "Утро · остальные", "uk": "Ранок · решта", "en": "Morning · others"},
    "rev.slot.checked": {"ru": "{n} проверено", "uk": "{n} перевірено", "en": "{n} checked"},
    "rev.slot.metric_help": {
        "ru": "Доля заказов, по которым Amazon разрешил отправить запрос. Зависит от "
              "того, доставлен ли заказ и не просили ли отзыв раньше — время отправки "
              "на это влиять не должно, поэтому большая разница была бы неожиданной",
        "uk": "Частка замовлень, за якими Amazon дозволив надіслати запит. Залежить від "
              "того, чи доставлено замовлення і чи не просили відгук раніше — час "
              "відправки на це впливати не має, тому велика різниця була б несподіваною",
        "en": "Share of orders Amazon allowed a request for. It depends on whether the "
              "order was delivered and whether a request was already made — send time "
              "should not affect this, so a large gap would be surprising",
    },
    "rev.slot.axis": {"ru": "Разрешено, %", "uk": "Дозволено, %", "en": "Allowed, %"},
    "rev.slot.small": {
        "ru": "Всего {n} наблюдений, в меньшей группе {mn}. Для выводов мало: пока "
              "группы отличаются по размеру в разы, разница между ними говорит о "
              "разном составе заказов, а не о времени отправки. Нужно хотя бы по "
              "300 в каждой.",
        "uk": "Всього {n} спостережень, у меншій групі {mn}. Для висновків замало: поки "
              "групи відрізняються за розміром у рази, різниця між ними говорить про "
              "різний склад замовлень, а не про час відправки. Потрібно хоча б по "
              "300 у кожній.",
        "en": "{n} observations in total, {mn} in the smaller group. Too few to conclude: "
              "while the groups differ in size by several times over, any gap reflects a "
              "different mix of orders rather than send time. At least 300 in each is needed.",
    },
    "rev.slot.enough": {
        "ru": "Наблюдений: {n}. Если линии идут рядом — время отправки на решение "
              "Amazon не влияет, и это ожидаемо: письмо он ставит в очередь и "
              "рассылает по своему расписанию.",
        "uk": "Спостережень: {n}. Якщо лінії йдуть поруч — час відправки на рішення "
              "Amazon не впливає, і це очікувано: лист він ставить у чергу і "
              "розсилає за своїм розкладом.",
        "en": "Observations: {n}. If the lines run together, send time does not affect "
              "Amazon's decision — which is expected: it queues the email and delivers "
              "on its own schedule.",
    },
    "rev.slot.wait": {
        "ru": "Разделение расписаний запущено — сравнение появится, когда пройдут "
              "первые прогоны по обоим.",
        "uk": "Розділення розкладів запущено — порівняння зʼявиться, коли пройдуть "
              "перші прогони по обох.",
        "en": "Split schedules have started — the comparison will appear once both have run.",
    },
    "rev.hour.title": {
        "ru": "Во сколько уходят запросы", "uk": "О котрій ідуть запити", "en": "When requests go out"},
    "rev.hour.caption": {
        "ru": "По местному времени маркетплейсов, с разбивкой по странам. С 19 августа "
              "Испания отправляет вечером, остальные утром — сравнение результата "
              "ниже, под этим графиком.",
        "uk": "За місцевим часом маркетплейсів, з розбивкою за країнами. З 19 серпня "
              "Іспанія надсилає ввечері, решта вранці — порівняння результату "
              "нижче, під цим графіком.",
        "en": "In marketplace local time, split by country. Since 19 August Spain sends "
              "in the evening and the others in the morning — the outcome comparison "
              "is below this chart.",
    },
    "rev.hour.split": {
        "ru": "Кто когда отправляет: {s}",
        "uk": "Хто коли надсилає: {s}",
        "en": "Who sends when: {s}",
    },
    "rev.hour.single": {
        "ru": "Пока все запросы уходят в {h}:00 — сравнивать не с чем. Разброс появится, "
              "только если разнести отправку по времени.",
        "uk": "Поки всі запити йдуть о {h}:00 — порівнювати нема з чим. Розкид зʼявиться, "
              "лише якщо рознести відправку за часом.",
        "en": "All requests currently go out at {h}:00 — nothing to compare yet. A spread "
              "will only appear if sending is split across times.",
    },
    "rev.age.no_data": {
        "ru": "Данных о возрасте пока нет — появятся после первых прогонов.",
        "uk": "Даних про вік поки немає — зʼявляться після перших прогонів.",
        "en": "No age data yet — it will appear after the first runs.",
    },
    "rev.age.small_sample": {
        "ru": "Наблюдений пока {n} — мало для выводов. Окно отправки не меняем, "
              "пока не наберётся хотя бы 200.",
        "uk": "Спостережень поки {n} — замало для висновків. Вікно відправки не змінюємо, "
              "поки не набереться щонайменше 200.",
        "en": "Only {n} observations so far — too few to conclude. The send window stays "
              "unchanged until at least 200 accumulate.",
    },
    "rev.age.enough_sample": {
        "ru": "Наблюдений: {n}. Выборки достаточно, чтобы обсуждать границы окна отправки.",
        "uk": "Спостережень: {n}. Вибірки достатньо, щоб обговорювати межі вікна відправки.",
        "en": "Observations: {n}. Enough data to discuss the send window boundaries.",
    },
    "rev.asin.top": {"ru": "Топ товаров по отправкам", "uk": "Топ товарів за відправками", "en": "Top products by requests sent"},
    "rev.asin.table": {"ru": "Все товары", "uk": "Всі товари", "en": "All products"},
    "rev.asin.no_data": {
        "ru": "По товарам данных пока нет.",
        "uk": "За товарами даних поки немає.",
        "en": "No product data yet.",
    },
    "rev.how.title": {"ru": "Как это работает", "uk": "Як це працює", "en": "How this works"},
    "rev.how.body": {
        "ru": (
            "Раз в сутки система берёт доставленные заказы возрастом 8–33 дня и спрашивает "
            "у Amazon, можно ли запросить отзыв. Где Amazon разрешает — запрос уходит "
            "автоматически, письмо покупателю отправляет сам Amazon по своему шаблону.\n\n"
            "**Заказы с возвратом пропускаются** — просить отзыв у того, кто вернул товар, "
            "значит собирать негатив.\n\n"
            "**Почему Amazon отказывает.** Заказ ещё не доставлен, запрос по нему уже "
            "отправляли раньше, или покупатель отказался от таких писем. Причину Amazon "
            "не сообщает, поэтому колонка называется просто «Amazon отказал».\n\n"
            "---\n\n"
            "### Что показали данные\n\n"
            "**Значение имеет день после заказа, а не время суток.**\n\n"
            "| День с даты заказа | Amazon разрешает |\n|---|---|\n"
            "| 8–16 | 77–100% |\n| 17 | 32% |\n| 18–33 | 0–10% |\n\n"
            "После 16-го дня окно фактически закрыто.\n\n"
            "**Повторно спрашивать бесполезно.** Заказ, по которому Amazon отказал в "
            "открытом окне, при повторной проверке позже не конвертируется: за неделю "
            "наблюдений ноль отправок из 394 попыток. Поэтому повторы прекращаются "
            "после 16-го дня — раньше они съедали 87% всех обращений к Amazon, не давая "
            "ни одной отправки.\n\n"
            "**Время суток мы не контролируем.** Наш вызов ставит запрос в очередь "
            "Amazon, а когда он разошлёт письмо — не сообщает. Поэтому час отправки "
            "определяет, когда уйдёт команда, а не когда покупатель увидит письмо. "
            "С 19 августа Испания отправляет вечером, остальные утром — сравнение "
            "результата на вкладке «Возраст заказа».\n\n"
            "**Что изменилось после отключения Helium 10** (10 августа): доля "
            "разрешённых запросов по свежим заказам выросла с 18% до 68%. Два "
            "инструмента конкурировали за одни и те же заказы, и выигрывал тот, "
            "кто успевал первым.\n\n"
            "**Штатный режим с 1 августа.** До этого система разбирала накопленное — "
            "заказы, которым уже было под месяц, и Amazon по ним отказывал: уходило "
            "3–21 запрос из 30–50 заказов. Сейчас обрабатываем на 8–10 день, уходит "
            "35–45 из 45."
        ),
        "uk": (
            "Раз на добу система бере доставлені замовлення віком 8–33 дні й питає в Amazon, "
            "чи можна запросити відгук. Де Amazon дозволяє — запит іде автоматично, лист "
            "покупцеві надсилає сам Amazon за своїм шаблоном.\n\n"
            "**Замовлення з поверненням пропускаються** — просити відгук у того, хто повернув "
            "товар, означає збирати негатив.\n\n"
            "**Чому Amazon відмовляє.** Замовлення ще не доставлене, запит уже надсилали "
            "раніше, або покупець відмовився від таких листів. Причину Amazon не повідомляє.\n\n"
            "---\n\n"
            "### Що показали дані\n\n"
            "**Значення має день після замовлення, а не час доби.**\n\n"
            "| День з дати замовлення | Amazon дозволяє |\n|---|---|\n"
            "| 8–16 | 77–100% |\n| 17 | 32% |\n| 18–33 | 0–10% |\n\n"
            "Після 16-го дня вікно фактично закрите.\n\n"
            "**Повторно питати марно.** Замовлення, за яким Amazon відмовив у відкритому "
            "вікні, при повторній перевірці пізніше не конвертується: за тиждень "
            "спостережень нуль відправок із 394 спроб. Тому повтори припиняються після "
            "16-го дня — раніше вони зʼїдали 87% усіх звернень до Amazon, не даючи "
            "жодної відправки.\n\n"
            "**Час доби ми не контролюємо.** Наш виклик ставить запит у чергу Amazon, "
            "а коли він розішле лист — не повідомляє. Тому година відправки визначає, "
            "коли піде команда, а не коли покупець побачить лист. З 19 серпня Іспанія "
            "надсилає ввечері, решта вранці — порівняння на вкладці «Вік замовлення».\n\n"
            "**Що змінилось після відключення Helium 10** (10 серпня): частка дозволених "
            "запитів за свіжими замовленнями зросла з 18% до 68%.\n\n"
            "**Штатний режим з 1 серпня.** До цього система розбирала накопичене — "
            "замовлення, яким уже було під місяць: йшло 3–21 запит із 30–50. Зараз "
            "обробляємо на 8–10 день, іде 35–45 із 45."
        ),
        "en": (
            "Once a day the system takes delivered orders aged 8–33 days and asks Amazon "
            "whether a review can be requested. Where Amazon allows it, the request is sent "
            "automatically — Amazon emails the buyer using its own template.\n\n"
            "**Orders with returns are skipped** — asking for a review from someone who "
            "returned the item means collecting negative feedback.\n\n"
            "**Why Amazon declines.** The order is not delivered yet, a request was already "
            "sent, or the buyer opted out. Amazon does not disclose the reason.\n\n"
            "---\n\n"
            "### What the data showed\n\n"
            "**What matters is the day after the order, not the time of day.**\n\n"
            "| Days since order | Amazon allows |\n|---|---|\n"
            "| 8–16 | 77–100% |\n| 17 | 32% |\n| 18–33 | 0–10% |\n\n"
            "After day 16 the window is effectively closed.\n\n"
            "**Asking again is pointless.** An order Amazon declined inside the open window "
            "does not convert on a later retry: zero sends out of 394 attempts over a week. "
            "Retries therefore stop after day 16 — previously they consumed 87% of all calls "
            "to Amazon without producing a single send.\n\n"
            "**We do not control the time of day.** Our call queues the request with Amazon, "
            "and it does not disclose when the email goes out. So the send hour determines "
            "when the command leaves, not when the buyer sees the email. Since 19 August "
            "Spain sends in the evening and the others in the morning — see the comparison "
            "on the Order age tab.\n\n"
            "**After Helium 10 was switched off** (10 August): the share of allowed requests "
            "on fresh orders rose from 18% to 68%.\n\n"
            "**Steady state since 1 August.** Before that the system was clearing a backlog "
            "of orders already a month old: 3–21 requests went out of 30–50 orders. Now we "
            "process on day 8–10 and send 35–45 out of 45."
        ),
    },
    # --- 8_CM_Dashboard.py: сводка по площадкам и здоровье каналов ---
    "nav.cm": {"ru": "Площадки", "uk": "Майданчики", "en": "Channels"},
    "cm.title": {"ru": "Площадки", "uk": "Майданчики", "en": "Channels"},
    "cm.caption": {
        "ru": "Amazon и Leroy Merlin в одной картине: продажи, цены, остатки, здоровье каналов",
        "uk": "Amazon і Leroy Merlin в одній картині: продажі, ціни, залишки, здоров'я каналів",
        "en": "Amazon and Leroy Merlin side by side: sales, prices, stock, channel health",
    },
    "cm.intro.title": {
        "ru": "Зачем эта страница",
        "uk": "Навіщо ця сторінка",
        "en": "What this page is for",
    },
    "cm.intro.body": {
        "ru": "Amazon и Leroy Merlin продают один и тот же товар, но данные по ним лежат "
              "в разных местах — сопоставить цены и остатки было негде. Здесь один товар "
              "занимает одну строку, обе площадки рядом. Смотреть в первую очередь на две "
              "колонки: разница цен (где на площадках расходится больше чем на 10%) и "
              "возвраты (где возвращают больше 15% проданного). Остаток Leroy Merlin — это "
              "не отдельный товар, а квота, выставленная на канал из местного склада: "
              "складывать её с амазоновским остатком нельзя.",
        "uk": "Amazon і Leroy Merlin продають один і той самий товар, але дані по них лежать "
              "у різних місцях — зіставити ціни й залишки не було де. Тут один товар займає "
              "один рядок, обидва майданчики поруч. Дивитись насамперед на дві колонки: "
              "різниця цін (де на майданчиках розходиться більш ніж на 10%) і повернення "
              "(де повертають понад 15% проданого). Залишок Leroy Merlin — це не окремий "
              "товар, а квота, виставлена на канал з місцевого складу: складати її з "
              "амазонівським залишком не можна.",
        "en": "Amazon and Leroy Merlin sell the same products, but their data lives in "
              "separate places — there was nowhere to compare prices and stock. Here one "
              "product is one row with both channels side by side. Watch two columns first: "
              "the price gap (where channels differ by more than 10%) and returns (where more "
              "than 15% of units sold come back). Leroy Merlin stock is not separate "
              "inventory — it is a quota listed on the channel out of the local warehouse, "
              "so it must not be added to the Amazon figure.",
    },
    "cm.filter.country": {"ru": "Страна", "uk": "Країна", "en": "Country"},
    "cm.filter.all_countries": {"ru": "Все страны", "uk": "Всі країни", "en": "All countries"},
    "cm.period.month": {"ru": "Этот месяц", "uk": "Цей місяць", "en": "This month"},
    "cm.period.custom": {"ru": "Свой период", "uk": "Свій період", "en": "Custom"},
    "cm.period.range": {"ru": "Даты с и по", "uk": "Дати з і по", "en": "Date range"},
    "cm.amz.returns_range": {
        "ru": "Единиц возвращено за период {f} — {to}",
        "uk": "Одиниць повернено за період {f} — {to}",
        "en": "Units returned between {f} and {to}",
    },
    "cm.filter.period": {"ru": "Период", "uk": "Період", "en": "Period"},
    "cm.tab.summary": {"ru": "Свод по товарам", "uk": "Зведення за товарами", "en": "By product"},
    "cm.tab.lm_health": {"ru": "Leroy Merlin", "uk": "Leroy Merlin", "en": "Leroy Merlin"},
    "cm.tab.amazon_health": {"ru": "Amazon", "uk": "Amazon", "en": "Amazon"},
    "cm.tab.all_countries": {"ru": "Все страны", "uk": "Всі країни", "en": "All countries"},
    "cm.kpi.skus": {"ru": "Товаров", "uk": "Товарів", "en": "Products"},
    "cm.kpi.revenue_amazon": {"ru": "Выручка Amazon", "uk": "Виручка Amazon", "en": "Amazon revenue"},
    "cm.kpi.revenue_lm": {"ru": "Выручка LM", "uk": "Виручка LM", "en": "LM revenue"},
    "cm.kpi.price_alerts": {"ru": "Расхождения цен", "uk": "Розбіжності цін", "en": "Price gaps"},
    "cm.kpi.price_alerts_help": {
        "ru": "Товары, где средняя цена на площадках отличается больше чем на 10%",
        "uk": "Товари, де середня ціна на майданчиках відрізняється більш ніж на 10%",
        "en": "Products where the average price differs by more than 10% between channels",
    },
    "cm.summary.only_alerts": {
        "ru": "Только расхождения цен",
        "uk": "Лише розбіжності цін",
        "en": "Price gaps only",
    },
    "cm.summary.no_alerts": {
        "ru": "Расхождений цен больше 10% не найдено.",
        "uk": "Розбіжностей цін понад 10% не знайдено.",
        "en": "No price gaps above 10% found.",
    },
    "cm.summary.note": {
        "ru": "Остаток Amazon — физический товар на складах FBA. Остаток LM — квота, "
              "выставленная на канал из местного склада, это не отдельный запас.",
        "uk": "Залишок Amazon — фізичний товар на складах FBA. Залишок LM — квота, "
              "виставлена на канал з місцевого складу, це не окремий запас.",
        "en": "Amazon stock is physical inventory in FBA. LM stock is a quota listed on the "
              "channel out of the local warehouse — not separate inventory.",
    },
    "cm.download": {"ru": "Скачать свод CSV", "uk": "Завантажити зведення CSV", "en": "Download summary CSV"},
    "cm.col.product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "cm.col.units_amazon": {"ru": "Продано AMZ", "uk": "Продано AMZ", "en": "Units AMZ"},
    "cm.col.revenue_amazon": {"ru": "Выручка AMZ", "uk": "Виручка AMZ", "en": "Revenue AMZ"},
    "cm.col.price_amazon": {"ru": "Цена AMZ", "uk": "Ціна AMZ", "en": "Price AMZ"},
    "cm.col.stock_amazon": {"ru": "Остаток AMZ", "uk": "Залишок AMZ", "en": "Stock AMZ"},
    "cm.col.stock_amazon_help": {
        "ru": "Физический остаток на складах FBA",
        "uk": "Фізичний залишок на складах FBA",
        "en": "Physical stock in FBA warehouses",
    },
    "cm.col.units_lm": {"ru": "Продано LM", "uk": "Продано LM", "en": "Units LM"},
    "cm.col.revenue_lm": {"ru": "Выручка LM", "uk": "Виручка LM", "en": "Revenue LM"},
    "cm.col.price_lm": {"ru": "Цена LM", "uk": "Ціна LM", "en": "Price LM"},
    "cm.col.stock_lm": {"ru": "Квота LM", "uk": "Квота LM", "en": "LM quota"},
    "cm.col.stock_lm_help": {
        "ru": "Количество, выставленное на канал из местного склада",
        "uk": "Кількість, виставлена на канал з місцевого складу",
        "en": "Quantity listed on the channel out of the local warehouse",
    },
    "cm.col.price_gap": {"ru": "Разница цен", "uk": "Різниця цін", "en": "Price gap"},
    "cm.col.price_gap_help": {
        "ru": "Насколько цена на LM выше или ниже цены на Amazon",
        "uk": "Наскільки ціна на LM вища або нижча за ціну на Amazon",
        "en": "How much the LM price is above or below the Amazon price",
    },
    "cm.lm.no_table": {
        "ru": "Мониторинг Leroy Merlin ещё не запущен — таблица показателей не создана.",
        "uk": "Моніторинг Leroy Merlin ще не запущено — таблиця показників не створена.",
        "en": "Leroy Merlin monitoring is not running yet — the metrics table does not exist.",
    },
    "cm.lm.as_of": {"ru": "Данные на {d}", "uk": "Дані на {d}", "en": "Data as of {d}"},
    "cm.lm.acceptance": {"ru": "Акцепт заказов", "uk": "Акцепт замовлень", "en": "Acceptance rate"},
    "cm.lm.avg_time": {"ru": "Среднее время", "uk": "Середній час", "en": "Average time"},
    "cm.lm.p90_time": {"ru": "Худшие 10%", "uk": "Найгірші 10%", "en": "Worst 10%"},
    "cm.lm.tracking": {"ru": "С трек-номером", "uk": "З трек-номером", "en": "With tracking"},
    "cm.lm.incidents": {"ru": "Инциденты", "uk": "Інциденти", "en": "Incidents"},
    "cm.lm.waiting": {"ru": "Ждут акцепта", "uk": "Чекають акцепту", "en": "Awaiting acceptance"},
    "cm.lm.orders": {"ru": "Заказов", "uk": "Замовлень", "en": "Orders"},
    "cm.lm.on_time": {"ru": "Отгружено в срок", "uk": "Відвантажено вчасно", "en": "Shipped on time"},
    "cm.lm.open_incidents": {"ru": "Открытых инцидентов", "uk": "Відкритих інцидентів", "en": "Open incidents"},
    "cm.lm.trend": {"ru": "Динамика по дням", "uk": "Динаміка за днями", "en": "Daily trend"},
    "cm.lm.waiting_title": {
        "ru": "Заказы, ожидающие акцепта",
        "uk": "Замовлення, що чекають акцепту",
        "en": "Orders awaiting acceptance",
    },
    "cm.lm.waiting_none": {
        "ru": "Все заказы приняты — ожидающих нет.",
        "uk": "Усі замовлення прийняті — очікуючих немає.",
        "en": "All orders accepted — none waiting.",
    },
    "cm.lm.waiting_warn": {
        "ru": "{n} заказ(ов) ждут акцепта. Mirakl отменяет непринятые заказы автоматически — "
              "их нужно принять в кабинете Leroy Merlin.",
        "uk": "{n} замовлень чекають акцепту. Mirakl скасовує неприйняті замовлення автоматично — "
              "їх потрібно прийняти в кабінеті Leroy Merlin.",
        "en": "{n} order(s) awaiting acceptance. Mirakl cancels unaccepted orders automatically — "
              "they need to be accepted in the Leroy Merlin back office.",
    },
    "cm.amz.open_incidents": {"ru": "Открытых инцидентов", "uk": "Відкритих інцидентів", "en": "Open incidents"},
    "cm.amz.critical": {"ru": "Критических", "uk": "Критичних", "en": "Critical"},
    "cm.amz.high": {"ru": "Высокого уровня", "uk": "Високого рівня", "en": "High severity"},
    "cm.amz.oldest": {"ru": "Самый старый", "uk": "Найстаріший", "en": "Oldest"},
    "cm.amz.oldest_help": {
        "ru": "Сколько дней открыт самый давний инцидент",
        "uk": "Скільки днів відкритий найдавніший інцидент",
        "en": "How many days the oldest incident has been open",
    },
    "cm.amz.by_type": {
        "ru": "Открытые инциденты по типу",
        "uk": "Відкриті інциденти за типом",
        "en": "Open incidents by type",
    },
    "cm.amz.incidents_note": {
        "ru": "Инциденты Leroy Merlin показаны на своей вкладке. Полный журнал со всеми "
              "статусами и историей — на странице «Инциденты».",
        "uk": "Інциденти Leroy Merlin показані на своїй вкладці. Повний журнал з усіма "
              "статусами та історією — на сторінці «Інциденти».",
        "en": "Leroy Merlin incidents are on their own tab. The full log with statuses and "
              "history is on the Incidents page.",
    },
    "cm.amz.returns": {"ru": "Возвратов", "uk": "Повернень", "en": "Returns"},
    "cm.amz.returns_help": {
        "ru": "Единиц возвращено за последние {d} дней",
        "uk": "Одиниць повернено за останні {d} днів",
        "en": "Units returned over the last {d} days",
    },
    "cm.amz.refunded": {"ru": "Возвращено денег", "uk": "Повернуто грошей", "en": "Refunded"},
    "cm.amz.return_skus": {"ru": "Товаров с возвратами", "uk": "Товарів з поверненнями", "en": "Products returned"},
    "cm.amz.returns_title": {"ru": "Возвраты", "uk": "Повернення", "en": "Returns"},
    "cm.amz.no_returns": {
        "ru": "Возвратов за выбранный период нет.",
        "uk": "Повернень за обраний період немає.",
        "en": "No returns in the selected period.",
    },
    "cm.amz.top_returns": {
        "ru": "Больше всего возвращают",
        "uk": "Найбільше повертають",
        "en": "Most returned products",
    },
    "cm.amz.by_reason": {"ru": "Причины возврата", "uk": "Причини повернення", "en": "Return reasons"},
    "cm.amz.reason_note": {
        "ru": "Причину Amazon передаёт только по возвратам со своих складов. По отгрузкам "
              "со своего склада причина не приходит — вместо неё бывает комментарий покупателя.",
        "uk": "Причину Amazon передає лише за поверненнями зі своїх складів. За відвантаженнями "
              "з власного складу причина не приходить — замість неї буває коментар покупця.",
        "en": "Amazon only provides a reason for returns from its own warehouses. For "
              "merchant-fulfilled orders there is no reason, sometimes a buyer comment instead.",
    },
    "cm.kpi.return_alerts": {"ru": "Много возвратов", "uk": "Багато повернень", "en": "High returns"},
    "cm.kpi.return_alerts_help": {
        "ru": "Товары, где возвращают больше 15% проданного",
        "uk": "Товари, де повертають понад 15% проданого",
        "en": "Products where more than 15% of units sold are returned",
    },
    "cm.summary.only_returns": {
        "ru": "Только много возвратов",
        "uk": "Лише багато повернень",
        "en": "High returns only",
    },
    "cm.col.returns_pct": {"ru": "Возвраты", "uk": "Повернення", "en": "Returns"},
    "cm.col.returns_pct_help": {
        "ru": "Доля возвратов от проданного за период. Больше 15% — повод посмотреть "
              "на товар: описание, качество или ожидания покупателя.",
        "uk": "Частка повернень від проданого за період. Понад 15% — привід подивитись "
              "на товар: опис, якість або очікування покупця.",
        "en": "Share of units returned out of units sold. Above 15% is worth a look — "
              "listing, quality, or buyer expectations.",
    },
    "cm.col.days_open": {"ru": "Дней", "uk": "Днів", "en": "Days"},
    "cm.col.days_open_help": {
        "ru": "Сколько дней инцидент остаётся открытым",
        "uk": "Скільки днів інцидент залишається відкритим",
        "en": "How many days the incident has been open",
    },
    "cm.col.warehouse": {"ru": "Склад", "uk": "Склад", "en": "Warehouse"},
    "cm.amz.incidents_title": {"ru": "Открытые инциденты", "uk": "Відкриті інциденти", "en": "Open incidents"},
    "cm.amz.no_incidents": {
        "ru": "Открытых инцидентов нет.",
        "uk": "Відкритих інцидентів немає.",
        "en": "No open incidents.",
    },
    "cm.state.waiting_acceptance": {
        "ru": "Ждёт акцепта", "uk": "Чекає акцепту", "en": "Awaiting acceptance"},
    "cm.state.waiting_debit": {
        "ru": "Ждёт оплаты", "uk": "Чекає оплати", "en": "Awaiting payment"},
    "cm.inc.low_stock": {"ru": "Мало остатка", "uk": "Мало залишку", "en": "Low stock"},
    "cm.inc.out_of_stock": {"ru": "Нет в наличии", "uk": "Немає в наявності", "en": "Out of stock"},
    "cm.inc.stale_data": {"ru": "Данные устарели", "uk": "Дані застаріли", "en": "Stale data"},
    "cm.inc.negative_stock": {"ru": "Отрицательный остаток", "uk": "Відʼємний залишок", "en": "Negative stock"},
    "cm.inc.lm_not_accepted": {
        "ru": "Заказ без акцепта", "uk": "Замовлення без акцепту", "en": "Order not accepted"},
    "cm.inc.lm_offer_zero": {
        "ru": "Оффер обнулён", "uk": "Оффер обнулено", "en": "Offer out of stock"},
    "cm.inc.lm_degraded": {
        "ru": "Показатели канала просели", "uk": "Показники каналу просіли", "en": "Channel health down"},
    "cm.sev.critical": {"ru": "Критично", "uk": "Критично", "en": "Critical"},
    "cm.sev.high": {"ru": "Высокий", "uk": "Високий", "en": "High"},
    "cm.sev.warning": {"ru": "Средний", "uk": "Середній", "en": "Medium"},
    "cm.sev.low": {"ru": "Низкий", "uk": "Низький", "en": "Low"},
    "cm.sev.info": {"ru": "Инфо", "uk": "Інфо", "en": "Info"},
    "cm.col.order": {"ru": "Заказ", "uk": "Замовлення", "en": "Order"},
    "cm.col.created": {"ru": "Создан", "uk": "Створено", "en": "Created"},
    "cm.col.state": {"ru": "Состояние", "uk": "Стан", "en": "State"},
    "cm.col.amount": {"ru": "Сумма", "uk": "Сума", "en": "Amount"},
    "cm.col.hours_open": {"ru": "Ждёт", "uk": "Чекає", "en": "Waiting"},
    "cm.col.severity": {"ru": "Уровень", "uk": "Рівень", "en": "Severity"},
    "cm.col.type": {"ru": "Тип", "uk": "Тип", "en": "Type"},
    "cm.col.description": {"ru": "Описание", "uk": "Опис", "en": "Description"},
    "cm.platform.amazon": {"ru": "Amazon", "uk": "Amazon", "en": "Amazon"},
    "cm.platform.lm": {"ru": "Leroy Merlin", "uk": "Leroy Merlin", "en": "Leroy Merlin"},
    "cm.all.metric_help": {
        "ru": "Выручка и маржа за выбранный период",
        "uk": "Виручка і маржа за обраний період",
        "en": "Revenue and margin for the selected period",
    },
    "cm.all.chart": {
        "ru": "Выручка по площадкам",
        "uk": "Виручка за майданчиками",
        "en": "Revenue by channel",
    },
    "cm.all.note": {
        "ru": "Маржа считается как выручка минус комиссии площадки и себестоимость. "
              "Реклама и логистика в этот расчёт не входят — они на странице «Деньги».",
        "uk": "Маржа рахується як виручка мінус комісії майданчика і собівартість. "
              "Реклама і логістика в цей розрахунок не входять — вони на сторінці «Гроші».",
        "en": "Margin is revenue minus channel fees and COGS. Ads and logistics are not "
              "included here — see the Money page.",
    },
    "cm.col.marketplace": {"ru": "Площадка", "uk": "Майданчик", "en": "Channel"},
    "cm.col.platform": {"ru": "Тип", "uk": "Тип", "en": "Type"},
    "cm.col.skus": {"ru": "Товаров", "uk": "Товарів", "en": "Products"},
    "cm.col.units": {"ru": "Продано", "uk": "Продано", "en": "Units"},
    "cm.col.revenue": {"ru": "Выручка", "uk": "Виручка", "en": "Revenue"},
    "cm.col.fees": {"ru": "Комиссии", "uk": "Комісії", "en": "Fees"},
    "cm.col.fees_pct": {"ru": "Доля комиссий", "uk": "Частка комісій", "en": "Fees share"},
    "cm.col.cm": {"ru": "Маржа", "uk": "Маржа", "en": "Margin"},
    "cm.col.cm_pct": {"ru": "Маржа %", "uk": "Маржа %", "en": "Margin %"},
    # --- 9_Coverage.py: покрытие по неделям ---
    "nav.coverage": {"ru": "Покрытие", "uk": "Покриття", "en": "Coverage"},
    "cov.title": {"ru": "Покрытие", "uk": "Покриття", "en": "Coverage"},
    "cov.caption": {
        "ru": "На сколько недель хватит товара и когда начнётся дефицит",
        "uk": "На скільки тижнів вистачить товару і коли почнеться дефіцит",
        "en": "How many weeks of stock are left and when the shortage begins",
    },
    "cov.no_table": {
        "ru": "Расчёт покрытия ещё не запускался — таблица не создана.",
        "uk": "Розрахунок покриття ще не запускався — таблиця не створена.",
        "en": "The coverage calculation has not run yet — the table does not exist.",
    },
    "cov.empty": {
        "ru": "Данных пока нет. Запусти расчёт покрытия в пайплайне.",
        "uk": "Даних поки немає. Запусти розрахунок покриття в пайплайні.",
        "en": "No data yet. Run the coverage calculation in the pipeline.",
    },
    "cov.as_of": {"ru": "Расчёт на {d}", "uk": "Розрахунок на {d}", "en": "Calculated on {d}"},
    "cov.intro.title": {
        "ru": "Как читать",
        "uk": "Як читати",
        "en": "How to read this",
    },
    "cov.intro.body": {
        "ru": "Покрытие считается по неделям вперёд: из остатка вычитается прогноз продаж, "
              "добавляются поступления. Когда остаток на складе Amazon кончается, продажи "
              "не встают — листинг переключается на отгрузку из Мадрида. Но мадридский "
              "запас общий на несколько стран, поэтому реальный срок короче обещанного.",
        "uk": "Покриття рахується по тижнях уперед: із залишку віднімається прогноз продажів, "
              "додаються надходження. Коли залишок на складі Amazon закінчується, продажі "
              "не зупиняються — лістинг перемикається на відвантаження з Мадрида. Але "
              "місцевий запас спільний на кілька країн, тому реальний строк коротший.",
        "en": "Coverage is projected week by week: the forecast is subtracted from stock and "
              "incoming shipments are added. When Amazon stock runs out, sales do not stop — "
              "the listing switches to shipping from Madrid. But the local stock is shared "
              "across several countries, so the real horizon is shorter than promised.",
    },
    "cov.filter.marketplace": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "cov.filter.status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "cov.filter.search": {"ru": "Поиск по SKU или товару", "uk": "Пошук за SKU або товаром", "en": "Search SKU or product"},
    "cov.filter.search_ph": {"ru": "напр. 41324000", "uk": "напр. 41324000", "en": "e.g. 41324000"},
    "cov.st.critical": {"ru": "Критично", "uk": "Критично", "en": "Critical"},
    "cov.st.warning": {"ru": "Под вопросом", "uk": "Під питанням", "en": "At risk"},
    "cov.st.ok": {"ru": "В норме", "uk": "В нормі", "en": "OK"},
    "cov.kpi.critical": {"ru": "Критично", "uk": "Критично", "en": "Critical"},
    "cov.kpi.critical_help": {
        "ru": "Товаров, которых хватит меньше чем на 4 недели с учётом местного запаса",
        "uk": "Товарів, яких вистачить менш ніж на 4 тижні з урахуванням місцевого запасу",
        "en": "Products with less than 4 weeks of cover including the local stock",
    },
    "cov.kpi.warning": {"ru": "Под вопросом", "uk": "Під питанням", "en": "At risk"},
    "cov.kpi.deficit_13": {"ru": "Дефицит в 13 недель", "uk": "Дефіцит у 13 тижнів", "en": "Shortage within 13 weeks"},
    "cov.kpi.deficit_13_help": {
        "ru": "Товаров, у которых запас кончится в горизонте 13 недель",
        "uk": "Товарів, у яких запас закінчиться в горизонті 13 тижнів",
        "en": "Products running out within a 13-week horizon",
    },
    "cov.kpi.switch": {"ru": "Перейдут на местный склад", "uk": "Перейдуть на місцевий склад", "en": "Switching to the local warehouse"},
    "cov.kpi.switch_help": {
        "ru": "Товары, по которым запас Amazon кончится и отгрузка переключится на склад в Мадриде",
        "uk": "Товари, за якими запас Amazon закінчиться і відвантаження перемкнеться на склад у Мадриді",
        "en": "Products where Amazon stock runs out and fulfilment switches to the local warehouse",
    },
    "cov.kpi.pool_risk": {"ru": "Прогноз завышен", "uk": "Прогноз завищений", "en": "Optimistic forecast"},
    "cov.kpi.pool_risk_help": {
        "ru": "Товары, где местный запас делят несколько стран — общий спрос съест его "
              "раньше, чем показывает расчёт по каждой стране отдельно",
        "uk": "Товари, де місцевий запас ділять кілька країн — спільний попит вичерпає його "
              "раніше, ніж показує розрахунок по кожній країні окремо",
        "en": "Products where several countries share the local stock — combined demand will "
              "consume it sooner than the per-country calculation suggests",
    },
    "cov.tab.list": {"ru": "Список товаров", "uk": "Список товарів", "en": "Products"},
    "cov.tab.detail": {"ru": "По неделям", "uk": "По тижнях", "en": "Week by week"},
    "cov.tab.distribution": {"ru": "Распределение", "uk": "Розподіл", "en": "Distribution"},
    "cov.col.product": {"ru": "Товар", "uk": "Товар", "en": "Product"},
    "cov.col.marketplace": {"ru": "Маркетплейс", "uk": "Маркетплейс", "en": "Marketplace"},
    "cov.col.stock": {"ru": "Остаток", "uk": "Залишок", "en": "Stock"},
    "cov.col.stock_help": {
        "ru": "Доступный остаток на складе Amazon",
        "uk": "Доступний залишок на складі Amazon",
        "en": "Available stock in the Amazon warehouse",
    },
    "cov.col.weeks_fba": {"ru": "Недель Amazon", "uk": "Тижнів Amazon", "en": "Weeks Amazon"},
    "cov.col.weeks_fba_help": {
        "ru": "На сколько недель хватит только складского остатка Amazon",
        "uk": "На скільки тижнів вистачить лише складського залишку Amazon",
        "en": "Weeks of cover from Amazon stock alone",
    },
    "cov.col.madrid": {"ru": "Мадрид", "uk": "Мадрид", "en": "Madrid"},
    "cov.col.madrid_help": {
        "ru": "Остаток на складе внутри страны — резерв на случай, когда Amazon опустеет",
        "uk": "Залишок на складі всередині країни — резерв на випадок, коли Amazon спорожніє",
        "en": "Stock in the in-country warehouse — the fallback when Amazon runs out",
    },
    "cov.col.weeks_total": {"ru": "С Мадридом", "uk": "З Мадридом", "en": "With Madrid"},
    "cov.col.weeks_total_help": {
        "ru": "Покрытие, если весь местный запас достанется этому маркетплейсу",
        "uk": "Покриття, якщо весь місцевий запас дістанеться цьому маркетплейсу",
        "en": "Cover if the entire local stock went to this marketplace",
    },
    "cov.col.pool_weeks": {"ru": "Хватит пула", "uk": "Вистачить пулу", "en": "Pool lasts"},
    "cov.col.pool_weeks_help": {
        "ru": "На сколько недель хватит местного запаса при суммарном спросе всех стран, "
              "которые его делят",
        "uk": "На скільки тижнів вистачить місцевого запасу за сумарного попиту всіх країн, "
              "які його ділять",
        "en": "How long the local stock lasts against the combined demand of all countries "
              "sharing it",
    },
    "cov.col.weeks_real": {"ru": "Реально недель", "uk": "Реально тижнів", "en": "Realistic weeks"},
    "cov.col.weeks_real_help": {
        "ru": "Меньшее из двух: покрытие этой страны и срок жизни общего местного запаса",
        "uk": "Менше з двох: покриття цієї країни і термін життя спільного місцевого запасу",
        "en": "The lower of two: this country's cover and the life of the shared local stock",
    },
    "cov.col.first_deficit": {"ru": "Дефицит с", "uk": "Дефіцит з", "en": "Shortage from"},
    "cov.col.switch": {"ru": "Переход на местный склад", "uk": "Перехід на місцевий склад", "en": "Switch to the local warehouse"},
    "cov.col.switch_help": {
        "ru": "Неделя, когда склад Amazon опустеет и отгрузка пойдёт из Мадрида",
        "uk": "Тиждень, коли склад Amazon спорожніє і відвантаження піде з Мадрида",
        "en": "The week when Amazon stock runs out and fulfilment moves to the local warehouse",
    },
    "cov.col.status": {"ru": "Статус", "uk": "Статус", "en": "Status"},
    "cov.list.pool_warn": {
        "ru": "У {n} позиций прогноз завышен: местный запас делят несколько стран, "
              "и общий спрос съест его раньше срока, показанного в колонке «С Мадридом».",
        "uk": "У {n} позицій прогноз завищений: місцевий запас ділять кілька країн, "
              "і спільний попит вичерпає його раніше строку в колонці «З Мадридом».",
        "en": "{n} items have an optimistic forecast: the local stock is shared across "
              "countries, and combined demand will consume it before the date shown in "
              "the “With Madrid” column.",
    },
    "cov.list.note": {
        "ru": "Прогноз продаж пока считается по скорости за 30 дней. Когда появится "
              "плановый прогноз, расчёт переключится на него — остальная логика не изменится.",
        "uk": "Прогноз продажів поки рахується за швидкістю за 30 днів. Коли зʼявиться "
              "плановий прогноз, розрахунок перемкнеться на нього — решта логіки не зміниться.",
        "en": "The sales forecast is currently based on the last 30 days of velocity. Once a "
              "planned forecast is available the calculation will switch to it — nothing else changes.",
    },
    "cov.kpi.warning_help": {
        "ru": "Товаров, которых хватит на 5–13 недель — не критично, но стоит планировать поставку",
        "uk": "Товарів, яких вистачить на 5–13 тижнів — не критично, але варто планувати поставку",
        "en": "Products with 5–13 weeks of cover — not critical, but worth planning a shipment",
    },
    "cov.col.shared": {"ru": "Общий запас", "uk": "Спільний запас", "en": "Shared stock"},
    "cov.col.shared_suffix": {"ru": "стран", "uk": "країн", "en": "countries"},
    "cov.col.shared_help": {
        "ru": "Местный запас по этому товару делят несколько стран. Поэтому «Реально "
              "недель» меньше, чем «С Мадридом»: общий спрос израсходует запас быстрее.",
        "uk": "Місцевий запас за цим товаром ділять кілька країн. Тому «Реально тижнів» "
              "менше: спільний попит витратить запас швидше.",
        "en": "Several countries share the local stock for this product. That is why "
              "“Realistic weeks” is lower than “With Madrid” — combined demand drains it faster.",
    },
    "cov.proj.pool_line": {
        "ru": "Мадрид кончится",
        "uk": "Мадрид закінчиться",
        "en": "Madrid runs out",
    },
    "cov.detail.chart_note": {
        "ru": "График показывает только склад Amazon этой страны. Пунктирная линия — неделя, "
              "когда закончится общий местный запас: после неё переключаться будет уже не на что.",
        "uk": "Графік показує лише склад Amazon цієї країни. Пунктирна лінія — тиждень, коли "
              "закінчиться спільний місцевий запас: після нього перемикатися буде вже нема на що.",
        "en": "The chart shows only this country's Amazon stock. The dashed line marks the week "
              "the shared local stock runs out — after that there is nothing to switch to.",
    },
    "cov.go_reorder": {
        "ru": "Перейти к автозаказу",
        "uk": "Перейти до автозамовлення",
        "en": "Go to reorder",
    },
    "cov.download": {"ru": "Скачать CSV", "uk": "Завантажити CSV", "en": "Download CSV"},
    "cov.detail.pick": {"ru": "Товар и маркетплейс", "uk": "Товар і маркетплейс", "en": "Product and marketplace"},
    "cov.detail.no_projection": {
        "ru": "Проекция по неделям для этой пары не рассчитана.",
        "uk": "Проекція по тижнях для цієї пари не розрахована.",
        "en": "No week-by-week projection for this pair.",
    },
    "cov.detail.pool_warn": {
        "ru": "Местный запас ({qty} шт) делят {n} стран, их суммарный спрос — "
              "{demand:.0f} шт в неделю. Общего запаса хватит примерно на {pool_weeks} нед., "
              "а расчёт по этой стране обещает {promised}.",
        "uk": "Місцевий запас ({qty} шт) ділять {n} країн, їхній сумарний попит — "
              "{demand:.0f} шт на тиждень. Спільного запасу вистачить приблизно на "
              "{pool_weeks} тиж., а розрахунок по цій країні обіцяє {promised}.",
        "en": "The local stock ({qty} units) is shared by {n} countries with a combined "
              "demand of {demand:.0f} units per week. It will last roughly {pool_weeks} "
              "week(s), while this country's own calculation promises {promised}.",
    },
    "cov.detail.note": {
        "ru": "Поступление становится доступным со следующей недели после прибытия. "
              "Непокрытый спрос не переносится на следующую неделю — потерянные продажи "
              "не возвращаются.",
        "uk": "Надходження стає доступним з наступного тижня після прибуття. "
              "Непокритий попит не переноситься на наступний тиждень — втрачені продажі "
              "не повертаються.",
        "en": "An incoming shipment becomes available from the week after it arrives. "
              "Unmet demand does not carry over — lost sales are gone.",
    },
    "cov.proj.week_num": {"ru": "Неделя", "uk": "Тиждень", "en": "Week"},
    "cov.proj.week_start": {"ru": "С даты", "uk": "З дати", "en": "From"},
    "cov.proj.stock_begin": {"ru": "На начало", "uk": "На початок", "en": "Opening"},
    "cov.proj.incoming": {"ru": "Поступление", "uk": "Надходження", "en": "Incoming"},
    "cov.proj.forecast": {"ru": "Прогноз продаж", "uk": "Прогноз продажів", "en": "Forecast"},
    "cov.proj.stock_end": {"ru": "На конец", "uk": "На кінець", "en": "Closing"},
    "cov.proj.unmet": {"ru": "Не покрыто", "uk": "Не покрито", "en": "Unmet"},
    "cov.proj.status": {"ru": "Итог", "uk": "Підсумок", "en": "Result"},
    "cov.proj.covered": {"ru": "Хватает", "uk": "Вистачає", "en": "Covered"},
    "cov.proj.deficit": {"ru": "Дефицит", "uk": "Дефіцит", "en": "Shortage"},
    "cov.bucket.0_4": {"ru": "до 4 недель", "uk": "до 4 тижнів", "en": "under 4 weeks"},
    "cov.bucket.5_13": {"ru": "5–13 недель", "uk": "5–13 тижнів", "en": "5–13 weeks"},
    "cov.bucket.14_26": {"ru": "14–26 недель", "uk": "14–26 тижнів", "en": "14–26 weeks"},
    "cov.bucket.26plus": {"ru": "больше 26", "uk": "більше 26", "en": "over 26"},
    "cov.dist.title": {
        "ru": "Сколько товаров в каждой зоне покрытия",
        "uk": "Скільки товарів у кожній зоні покриття",
        "en": "Products by coverage band",
    },
    "cov.dist.pairs": {"ru": "Позиций", "uk": "Позицій", "en": "Items"},
    "cov.dist.by_marketplace": {
        "ru": "По маркетплейсам",
        "uk": "За маркетплейсами",
        "en": "By marketplace",
    },
    "cov.dist.critical_share": {"ru": "Доля критичных", "uk": "Частка критичних", "en": "Critical share"},
    "cov.dist.median_weeks": {"ru": "Медиана недель", "uk": "Медіана тижнів", "en": "Median weeks"},
    "cov.dist.note": {
        "ru": "Позиция — это товар на одном маркетплейсе. Один товар может быть критичным "
              "в одной стране и в норме в другой.",
        "uk": "Позиція — це товар на одному маркетплейсі. Один товар може бути критичним "
              "в одній країні і в нормі в іншій.",
        "en": "An item is one product on one marketplace. The same product can be critical "
              "in one country and fine in another.",
    },
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
