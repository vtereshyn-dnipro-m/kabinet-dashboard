# Finances, промо и добор экономики

> Перенесено из AGENTS.md дословно 19.10.2026 (сжатие файла правил). Правила работы и указатель — в AGENTS.md; дополнять этот файл, а не AGENTS.md.

## Finances, промо и добор экономики из Data Kiosk (с 18.10.2026, решения владельца)

Три загрузчика, ни один не создаёт отчётов через createReport. Источники кода — `nb/finances_loader.py`,
`nb/promotions_loader.py`, `nb/economics_dk_backfill.py`; SQL — `sql/pr2_finances_promo_backfill_2026-10-18.sql`.

- **Транзакции Amazon** — `Kabinet - Amazon Finances Loader` (08:40), Finances v2024-06-19 `listTransactions` по каждому
  рынку Amazon → `dnipro_m.raw_amazon_finances_transactions` (тип, статус, дата проводки, рынок, сумма, номера заказа,
  отгрузки, settlement, отложенность) и `raw_amazon_finances_breakdowns` (разбивка суммы построчно, путь
  «Sales/ProductCharges/OurPricePrincipal», уровень транзакции и позиции с SKU, ASIN и штуками). **Данных покупателя не
  храним** — решение владельца: только разрешённые поля, `AddressContext` отбрасывается целиком, сырого ответа в
  таблицах нет. Amazon отдаёт не старше двух лет. Окно — `reorder_params.finances_reread_days` (30): статус транзакции
  меняется (`DEFERRED` → `DEFERRED_RELEASED` / `RELEASED`). Блок 30 дней заменяется целиком или не пишется. Номер
  settlement в транзакции есть — сверка с settlement-отчётом идёт по нему напрямую. Проба 18.10: 101 транзакция за два
  дня по всем рынкам; виды разбивки — `Commission`, `FBAPerUnitFulfillmentFee`, `DigitalServicesFee`, `PromoRebates`,
  `VineEnrollmentFee`, `ShippingChargeback` и др.
  **Одна продажа лежит в таблице ДВАЖДЫ** — отложенной транзакцией (`DEFERRED_RELEASED`) и выплатой (`RELEASED`) с той
  же разбивкой, и сумма «всего подряд» удваивается (digital-сбор ES за август 2026 выходил 506 € вместо 241 €). Читать
  только вью `dnipro_m.v_amazon_finances_transactions_current` / `v_amazon_finances_breakdowns_current`
  (`sql/v_amazon_finances_current_2026-10-18.sql`): выплаты + ещё не выплаченные (`DEFERRED`) + отложенные, на которые
  выплаты нет — 423 продажи ноября 2024 — марта 2025 Amazon отдаёт только отложенной транзакцией. ES август 2026 по вью
  — 811 заказов и 40 334,16 €, как в settlement до цента. И второе: внутри разбивки суммы вложены (путь `X` и `X/Y`
  повторяют одни деньги, уровень транзакции повторяет позиции) — складывать один уровень: листья (`is_leaf = 'Y'`) или
  конкретный путь у позиций (`item_no IS NOT NULL`).
- **Бэклог (решение владельца 18.10.2026, не чинить сейчас): digital-сбор в `economics_fees` недосчитан.** Data Kiosk
  отдаёт `DigitalServicesFeeSOA` почти пустым — ES август 2026 14 €, сентябрь 5 €, — а Amazon удерживает 241 € и 256 €
  (с НДС; settlement и Finances сходятся до цента). Наша методика маржи недосчитывает по ES ~200–250 € в месяц; экраны
  это не трогает — там цифры Power BI, у которого модель «3 % от реферальной» близка к факту. Чинить — брать сбор из
  Finances (вью `v_amazon_finances_breakdowns_current`, путь `…DigitalServicesFee/DigitalServicesFee` у позиций).
- **Промо по товару** — `Kabinet - Amazon Promotions Loader` (08:50), Data Kiosk `analytics_sellerAnalytics_2025_03_31`,
  блок `promotion` → `dnipro_m.raw_amazon_seller_analytics_promotions`: ASIN × рынок × день, только дни с акцией. Один
  запрос на все рынки, суммы в евро (пересчёт GB/SE/PL делает Amazon). `msku` Amazon для промо не отдаёт, идентификатора
  акции в группировке нет — акцию называют `deal_id` / `deal_title`. ES за сентябрь 2026: 34 ASIN, 8 акций, скидка
  353 € (`Sales Discount` 52 строки, `Price Discount` 12). Окно `promotions_reread_days` (35).
- **Добор экономики за два года** — `Kabinet - Economics DK Backfill`, ночью 00:30, новых запросов после
  `econ_backfill_deadline_hhmm` (04:30) не создаёт. Тот же запрос и те же таблицы, что у Economics Loader
  (`dnipro_m.kabinet.economics_daily` / `economics_fees`), **только дни раньше первого загруженного дня рынка и только те,
  которых ещё нет** — уже загруженное не перезаписывается. Граница у каждого рынка своя (у большинства 15.05.2026, у GB
  и IE 01.06.2026) и фиксируется первым прогоном строкой `BACKFILL_BOUNDARY` в журнале — до любой записи: иначе после
  первой ночи «первым днём» стал бы добранный октябрь 2024 и остальная история выпала бы. Сетка кусков привязана к
  границе, а не к «сегодня минус два года» — край истории сдвигается каждый день. Куски по 31 дню, журнал — `economics_load_runs` со статусами
  `BACKFILL_DONE` / `BACKFILL_EMPTY` / `BACKFILL_ERROR`; закрытый кусок второй раз не запрашивается. ~190 кусков на десять
  рынков. На 429 не повторяет: остаток следующей ночью. Когда в пульсе «история полная» — джобу на паузу и правило
  сторожа удалить. Второй задачей той же ночи идёт промо — его первый прогон добирает историю промо.
- **`economics_summary` назад не продлеваем** (решение владельца): ячейка 2 Economics Loader читает `economics_daily` и
  `economics_fees` с 15.05.2026 (`ECON_SUMMARY_SINCE`, патч `nb/patches/2026-10-18_economics_summary_since_Economics_Loader.diff`).
  До этой правки она читала таблицы ЦЕЛИКОМ, без фильтра по дате, и добранная история ушла бы в сводку на первом же
  прогоне — поэтому патч выкладывается ДО первой ночи добора. Остальные читатели этих таблиц смотрят окном: сверка 30
  дней, вью `kabinet_data.sku_margin_threshold` 90, Brand Analytics 365 (там добор лишь расширит «наши ASIN» на ASIN,
  продававшиеся с октября 2025). Витрина Power BI их не читает.
- У GB и IE экономика начиналась 01.06.2026: дни 15–31.05 по ним закрывает добор, и в `economics_summary` они попадают (граница сводки — 15.05).
