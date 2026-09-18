"""
6_Dictionaries.py — раздел «📚 Справочники» Кабинета Sales, Demand & Supply.

Табы:
  🏭 Склады            kabinet_data.warehouses
  🔗 Подпитка          kabinet_data.supply_chains
  🌍 Маркетплейсы      kabinet_data.marketplaces
  📦 Пулы              kabinet_data.pools + pool_members
  📏 Нормативы         kabinet_data.coverage_norms

Переводы страницы лежат в этом файле (TR + _tr), чтобы не раздувать i18n.py.
Язык берётся из i18n.get_lang() — общий с остальными страницами.
"""

import json
from datetime import date

import pandas as pd
import streamlit as st

from i18n import init_lang, get_lang
from db.connection import get_connection


# ═══════════════════════════════════════════════════════════════════════════
# ПЕРЕВОДЫ
# ═══════════════════════════════════════════════════════════════════════════

TR = {
    "ru": {
        "title": "📚 Справочники",
        "sub": "Настройки, на которых считаются остатки, покрытие и автозаказ",
        "tab_wh": "🏭 Склады", "tab_ch": "🔗 Подпитка", "tab_mp": "🌍 Маркетплейсы",
        "tab_pool": "📦 Пулы", "tab_norm": "📏 Нормативы",
        "tab_assort": "🧭 Ассортимент",
        "tab_alerts": "🔔 Алерты",
        "tab_sku": "🧱 SKU",
        "tab_peid": "🏷 PeID",
        "tab_vg": "🧬 Вариации",
        "tab_matrix": "🗂 Матрица",
        "am_hint": "Ассортиментная матрица по ТЗ 007: допуск SKU на площадку (рамочный) или на marketplace (операционный), признаки «в листинге» "
                   "и «комплиментарный», история неизменяемыми записями с датами. Стартовый срез собран из действующих листингов (source seed); "
                   "решения людей — source manual, загрузчик их не меняет. Исключение — дата в «Исключён»; повторный запуск — новая запись.",
        "am_level": "Уровень", "am_level_marketplace": "marketplace", "am_level_platform": "площадка",
        "am_platform": "Площадка", "am_mp": "Маркетплейс", "am_search": "SKU", "am_show_history": "Показать историю",
        "am_only_issues": "Только с проблемами",
        "am_summary": "Действующих допусков: {n} · в листинге {listing} · комплиментарных {comp} · с ошибками контроля {err}",
        "am_col_level": "Уровень", "am_col_platform": "Площадка", "am_col_mp": "Маркетплейс", "am_col_sku": "SKU", "am_col_name": "Название",
        "am_col_type": "Тип", "am_col_added": "Добавлен", "am_col_removed": "Исключён", "am_col_listing": "В листинге",
        "am_col_comp": "Комплиментарный", "am_col_reason": "Причина", "am_col_source": "Источник", "am_col_issues": "Контроль",
        "am_add_title": "Добавить SKU в матрицу", "am_add_sku": "SKU", "am_add_date": "Дата добавления", "am_add_btn": "➕ Добавить",
        "am_add_ok": "Допуск создан", "am_add_dup": "Действующая запись уже есть", "am_add_no_intro": "У SKU нет даты ввода (ТЗ 007 §8)",
        "am_add_exited": "У SKU есть дата вывода — новый допуск не создаётся", "am_add_restricted": "SKU ограничен для этой площадки/страны (ТЗ 005 §6)",
        "am_add_no_platform": "Нет рамочного допуска площадки для этого SKU — сначала добавь на уровень площадки",
        "am_add_comp_composite": "Составной SKU не может быть комплиментарным (ТЗ 007 §9)",
        "am_saved": "Сохранено: допусков {a}, представлений {r}",
        "am_repr_title": "Представления SKU на маркетплейсе", "am_repr_pick_mp": "Маркетплейс для представлений",
        "am_repr_col_peid": "PeID", "am_repr_col_group": "Группа вариаций", "am_repr_col_role": "Коммерческая роль",
        "am_repr_col_from": "С", "am_repr_col_to": "По", "am_repr_none": "Представлений нет",
        "am_role_help": "Hero / Traffic / Margin / Support — только для PeID в группе вариаций (ТЗ 009). Без группы поле пустое.",
        "am_role_no_group": "Роль не сохранена для {peid}: у PeID нет группы вариаций",
        "vg_hint": "Группы вариаций по ТЗ 006: у Amazon — Parent ASIN и его дети. Группа живёт в одном marketplace, вариант входит в одну группу; "
                   "связь назначается на уровне PeID (вкладка PeID, при выбранном одном маркетплейсе). Имя — как на площадке; "
                   "исправленное здесь имя помечается manual. Группа — уровень консолидации рекламы и ACOS.",
        "vg_summary": "Групп: {total}, активных {active}, вариантов в группах {members}, с замечаниями {issues}",
        "vg_col_mp": "Маркетплейс", "vg_col_name": "Название на площадке", "vg_col_peid": "Групповой PeID", "vg_col_members": "Вариантов",
        "vg_col_family": "Семья площадки", "vg_col_active": "Активна", "vg_col_issues": "Контроль", "vg_col_comment": "Комментарий",
        "vg_col_src": "Источник",
        "vg_members_pick": "Состав группы", "vg_members_none": "Вариантов нет",
        "vg_saved": "Сохранено: {n} групп",
        "pe_group_edit_hint": "Группу можно менять, когда выбран один маркетплейс: список — группы этого маркетплейса.",
        "pe_hint": "Товарные сущности площадок по ТЗ 008: ASIN у Amazon, model id у ManoMano, product_sku у Leroy Merlin и Carrefour. "
                   "Собираются из листингов и офферов ежедневно. Связь с SKU по ТЗ живёт в матрице; здесь показано, под каким SKU сущность "
                   "выставлена сейчас. Группа вариаций назначается на уровне PeID (ТЗ 006).",
        "pe_mp": "Маркетплейс", "pe_search": "PeID, название или SKU", "pe_only_issues": "Только с проблемами",
        "pe_hide_parents": "Скрыть Parent ASIN", "pe_hide_inactive": "Скрыть неактивные",
        "pe_summary": "Сущностей: {total}, активных {active}, Parent ASIN {parents}, с ошибками контроля {err}",
        "pe_col_mp": "Маркетплейс", "pe_col_peid": "PeID", "pe_col_title": "Название на площадке", "pe_col_skus": "SKU в листингах",
        "pe_col_status": "Статусы листингов", "pe_col_parent": "Parent", "pe_col_group": "Группа вариаций", "pe_col_active": "Активен",
        "pe_col_seen": "Источники", "pe_col_last": "Последний раз", "pe_col_issues": "Контроль", "pe_col_comment": "Комментарий",
        "pe_saved": "Сохранено: {n} записей",
        "sku_hint": "Справочник SKU по ТЗ 005: базовые и составные товары компании. Тип и имя — из Odoo, вес брутто — из ERP, "
                    "габариты упаковки и EAN — из Amazon, дата ввода — оценка по первому остатку/листингу/продаже. "
                    "Поле, поправленное здесь, помечается «manual» и загрузчиком больше не трогается.",
        "sku_search": "Код или название", "sku_type_f": "Тип", "sku_check_f": "Проблема",
        "sku_only_issues": "Только с проблемами",
        "sku_t_base": "базовый", "sku_t_composite": "составной", "sku_t_none": "не определён",
        "sku_summary": "SKU: {total} (базовых {base}, составных {comp}, без типа {none}) · с ошибками контроля {err}",
        "sku_col_sku": "SKU", "sku_col_type": "Тип", "sku_col_name": "Название", "sku_col_ean": "EAN",
        "sku_col_supplier": "Код поставщика", "sku_col_intro": "Дата ввода", "sku_col_exit": "Дата вывода",
        "sku_col_h": "В, мм", "sku_col_w": "Ш, мм", "sku_col_l": "Д, мм", "sku_col_vol": "Объём, м³",
        "sku_col_weight": "Брутто, кг", "sku_col_restr": "Ограничения", "sku_col_passport": "Паспорт",
        "sku_col_issues": "Контроль", "sku_col_scope": "Где", "sku_col_src": "Источники",
        "sku_restr_help": "Коды marketplace или стран через запятую, где применение запрещено (ТЗ 005 §6)",
        "sku_comp_pick": "Состав набора", "sku_comp_none": "Состав не найден",
        "sku_comp_col_base": "Базовый SKU", "sku_comp_col_qty": "Кол-во", "sku_comp_col_name": "Название",
        "sku_comp_note": "Состав неизменяем (ТЗ 005 §7): другой набор — это новый SKU. Источник — Odoo.",
        "sku_intro_estimate": "оценка",
        "sku_saved_manual": "Сохранено: {n} полей помечены как введённые вручную",
        "al_hint": "Справочник типов алертов Кабинета. Указан список ClickUp — задачи уходят туда; "
                   "список пуст — тип живёт только в «Инцидентах». Других включателей нет. "
                   "Исполнитель — роль ClickUp, не человек; роли заведёт Владислав. "
                   "«Контроль закрытия»: Кабинет сам закрывает задачу, когда причина ушла из данных, и "
                   "переоткрывает, если её закрыли руками при живой причине; без контроля — задачу создали и отдали.",
        "al_hint2": "Идентификатор алерта обязателен в задаче: в списке ClickUp должно быть текстовое поле "
                    "«Alert ID». Пока его нет, джоба задачи не создаёт — причина в колонке «Проверка списка».",
        "al_only_routed": "Только со списком", "al_search": "Тип",
        "al_col_type": "Тип", "al_col_title": "Название", "al_col_descr": "Что означает",
        "al_col_list": "Список ClickUp (id)", "al_col_list_name": "Путь списка",
        "al_col_mode": "Режим", "al_col_watch": "Контроль закрытия", "al_col_risk": "Risk",
        "al_col_due": "Срок, дн", "al_col_role": "Роль ClickUp", "al_col_role_id": "id роли",
        "al_col_since": "Задачи с даты", "al_col_open": "Открыто", "al_col_tasks": "Задач в ClickUp",
        "al_col_check": "Проверка списка", "al_col_checked": "Проверено",
        "al_mode_task": "задача на инцидент", "al_mode_digest": "дайджест",
        "al_summary": "Типов: {total}, со списком ClickUp: {routed}, открытых инцидентов: {open}",
        "al_sync_hint": "Джоба «Kabinet - ClickUp Sync» ходит раз в час; изменения здесь подхватываются следующим прогоном.",
        "as_hint": "Слева факт — статус по продажам, его считает загрузчик и руками он не правится. "
                   "Справа намерение — что с этим SKU на этом рынке решено. Прогноз читает намерение: "
                   "«выводим» и «не продаём» из прогноза исключаются, «запускаем» — попадает без истории.",
        "as_mp": "Рынок", "as_fact": "Факт", "as_search": "SKU",
        "as_only_gap": "Только где намерение не задано",
        "as_col_fact": "Факт (продажи)", "as_col_target": "Намерение", "as_col_note": "Примечание",
        "as_col_upd": "Изменено",
        "as_t_": "—", "as_t_keep": "держим", "as_t_launch": "запускаем", "as_t_phase_out": "выводим",
        "as_t_seasonal": "сезонный", "as_t_stop": "не продаём",
        "as_f_active": "продаётся", "as_f_not_launched": "не продавался", "as_f_phasing_out": "затухает",
        "as_f_seasonal_pause": "сезонная пауза", "as_f_discontinued": "снят",
        "as_summary": "Намерение задано у {n} из {total} пар на этом рынке",
        "save": "💾 Сохранить изменения", "saved": "Сохранено: {n} запис(ей)",
        "nochange": "Изменений нет", "err": "Ошибка: {e}", "no_data": "Нет данных",
        "del_col": "Удалить", "delete_sel": "🗑 Удалить отмеченные", "deleted": "Удалено: {n}",
        "wh_hint": "Два поля заполняются руками — площадки склада и приоритет "
                   "обеспечения. Остальное приезжает из ERP и меняется там.",
        "wh_pick": "Склад", "wh_show_sales": "Показать точки продаж и FBA",
        "wh_show_sales_hint": "По умолчанию видны только склады хранения — "
                              "решения принимаются по ним. У FBA площадка "
                              "определена страной и проставлена сама.",
        "wh_inactive": "выключен", "wh_active": "активен",
        "wh_mp_h": "Какие площадки обеспечивает",
        "wh_mp_hint": "Отметь витрины, товар на которые уезжает с этого склада. "
                      "Можно несколько — склад обычно кормит не одну.",
        "wh_mp_missing": "Таблица связей ещё не создана: выполните "
                         "sql/warehouse_marketplaces.sql. Приоритет пока "
                         "сохраняется, площадки — нет.",
        "wh_mp_count": "Отмечено: {n} из {total}",
        "wh_prio_h": "Приоритет обеспечения",
        "wh_prio_hint": "Один номер на склад, общий для всех площадок. "
                        "1 — забираем отсюда в первую очередь. "
                        "0 — склад в обеспечении не участвует.",
        "wh_src_h": "Откуда пополняется",
        "wh_src_none": "Маршрутов подпитки на этот склад пока нет.",
        "wh_src_hint": "Считается по накладным, менять на вкладке «Подпитка».",
        "wh_sum_h": "Что уже заполнено",
        "wh_all": "Все склады одной таблицей",
        "col_mps": "Площадки", "col_src": "Склад-источник", "col_basis": "Основание",
        "basis_ttn": "накладных: {n}", "basis_expert": "оценка вручную",
        "t_sales": "точка продаж", "t_storage": "хранение",
        "t_transit": "транзит", "t_manufacturer": "производитель",
        "ch_hint": "Кто кого пополняет и за сколько дней. Срок из накладных "
                   "(ttn_planned) надёжнее экспертного (expert).",
        "ch_add": "➕ Добавить связь подпитки",
        "ch_from": "Склад-источник", "ch_to": "Склад-получатель",
        "ch_same": "Источник и получатель не могут совпадать",
        "ch_exists": "Такая связь уже есть",
        "mp_hint": "Справочник маркетплейсов. Код и Amazon ID менять нельзя.",
        "pool_hint": "Пул — группа маркетплейсов с общим совокупным прогнозом. "
                     "Маркетплейс не может одновременно быть в двух активных пулах.",
        "pool_list": "Пулы", "pool_new": "Новый пул", "pool_name": "Название",
        "pool_comment": "Комментарий", "pool_create": "➕ Создать пул",
        "pool_save_cmt": "✏️ Сохранить комментарий", "pool_delete": "🗑 Удалить пул",
        "pool_members": "Состав пула", "pool_select": "Маркетплейсы",
        "pool_from": "Действует с", "pool_to": "Действует по (пусто — бессрочно)",
        "pool_save": "💾 Сохранить состав", "pool_none": "Пулов пока нет — создай первый",
        "pool_conflict": "Уже в другом пуле: {mp}", "pool_created": "Пул создан",
        "pool_deleted": "Пул удалён", "pool_empty_name": "Укажи название пула",
        "norm_hint": "Норматив покрытия в днях по SKU для маркетплейса или пула. "
                     "Минимум ≤ цель ≤ максимум.",
        "norm_add": "➕ Добавить норматив", "norm_sku": "SKU",
        "norm_target": "Привязка", "norm_target_mp": "Маркетплейс", "norm_target_pool": "Пул",
        "norm_target_val": "Значение", "norm_added": "Норматив добавлен",
        "norm_manual": "SKU нет в списке — ввести вручную",
        "norm_no_pools": "Пулов ещё нет, поэтому доступна только привязка к маркетплейсу.",
        "norm_now": "Сейчас покрытие {w} нед., статус «{st}»",
        "norm_now_none": "Покрытие по этой паре ещё не считалось",
        "norm_unused": "Норматив пока только хранится: расчёт покрытия его не читает, "
                       "статусы на «Остатках» загрузчик считает по своим порогам. "
                       "Заполнять имеет смысл — цифры понадобятся, когда расчёт переведут на справочник.",
        "col_product": "Товар",
        "norm_exists": "Норматив для этой связки уже есть — отредактируй в таблице ниже",
        "norm_order": "Должно быть: минимум ≤ цель ≤ максимум",
        "norm_empty": "Укажи SKU", "norm_list": "Действующие нормативы",
        "norm_none": "Нормативы ещё не заданы", "norm_no_target": "Сначала заведи пул",
        "col_id": "ID", "col_name": "Название", "col_code": "Код", "col_type": "Тип",
        "col_mp": "Маркетплейс", "col_country": "Страна", "col_currency": "Валюта",
        "col_amazon_id": "Amazon ID", "col_active": "Активен", "col_canon": "Дубль от",
        "col_note": "Примечание", "col_ship_prio": "Приоритет отгрузки",
        "col_route": "Тип маршрута", "col_median": "Срок, дн",
        "col_shipments": "Отгрузок", "col_lead_src": "Источник срока",
        "col_sample": "Накладных", "col_min": "Мин, дн", "col_target": "Цель, дн",
        "col_max": "Макс, дн", "col_pool": "Пул", "col_from": "С", "col_to": "По",
    },
    "uk": {
        "title": "📚 Довідники",
        "sub": "Налаштування, на яких рахуються залишки, покриття та автозамовлення",
        "tab_wh": "🏭 Склади", "tab_ch": "🔗 Підживлення", "tab_mp": "🌍 Маркетплейси",
        "tab_pool": "📦 Пули", "tab_norm": "📏 Нормативи",
        "tab_assort": "🧭 Асортимент",
        "tab_alerts": "🔔 Алерти",
        "tab_sku": "🧱 SKU",
        "tab_peid": "🏷 PeID",
        "tab_vg": "🧬 Варіації",
        "tab_matrix": "🗂 Матриця",
        "am_hint": "Асортиментна матриця за ТЗ 007: допуск SKU на майданчик (рамковий) або на marketplace (операційний), ознаки «в лістингу» "
                   "та «компліментарний», історія незмінними записами з датами. Стартовий зріз зібрано з чинних лістингів (source seed); "
                   "рішення людей — source manual, завантажувач їх не змінює. Виключення — дата у «Виключено»; повторний запуск — новий запис.",
        "am_level": "Рівень", "am_level_marketplace": "marketplace", "am_level_platform": "майданчик",
        "am_platform": "Майданчик", "am_mp": "Маркетплейс", "am_search": "SKU", "am_show_history": "Показати історію",
        "am_only_issues": "Лише з проблемами",
        "am_summary": "Чинних допусків: {n} · в лістингу {listing} · компліментарних {comp} · з помилками контролю {err}",
        "am_col_level": "Рівень", "am_col_platform": "Майданчик", "am_col_mp": "Маркетплейс", "am_col_sku": "SKU", "am_col_name": "Назва",
        "am_col_type": "Тип", "am_col_added": "Додано", "am_col_removed": "Виключено", "am_col_listing": "В лістингу",
        "am_col_comp": "Компліментарний", "am_col_reason": "Причина", "am_col_source": "Джерело", "am_col_issues": "Контроль",
        "am_add_title": "Додати SKU до матриці", "am_add_sku": "SKU", "am_add_date": "Дата додавання", "am_add_btn": "➕ Додати",
        "am_add_ok": "Допуск створено", "am_add_dup": "Чинний запис уже є", "am_add_no_intro": "У SKU немає дати введення (ТЗ 007 §8)",
        "am_add_exited": "У SKU є дата виведення — новий допуск не створюється", "am_add_restricted": "SKU обмежений для цього майданчика/країни (ТЗ 005 §6)",
        "am_add_no_platform": "Немає рамкового допуску майданчика для цього SKU — спершу додай на рівень майданчика",
        "am_add_comp_composite": "Складений SKU не може бути компліментарним (ТЗ 007 §9)",
        "am_saved": "Збережено: допусків {a}, представлень {r}",
        "am_repr_title": "Представлення SKU на маркетплейсі", "am_repr_pick_mp": "Маркетплейс для представлень",
        "am_repr_col_peid": "PeID", "am_repr_col_group": "Група варіацій", "am_repr_col_role": "Комерційна роль",
        "am_repr_col_from": "З", "am_repr_col_to": "По", "am_repr_none": "Представлень немає",
        "am_role_help": "Hero / Traffic / Margin / Support — лише для PeID у групі варіацій (ТЗ 009). Без групи поле порожнє.",
        "am_role_no_group": "Роль не збережено для {peid}: у PeID немає групи варіацій",
        "vg_hint": "Групи варіацій за ТЗ 006: в Amazon — Parent ASIN і його діти. Група живе в одному marketplace, варіант входить в одну групу; "
                   "звʼязок призначається на рівні PeID (вкладка PeID, при обраному одному маркетплейсі). Назва — як на майданчику; "
                   "виправлена тут назва позначається manual. Група — рівень консолідації реклами та ACOS.",
        "vg_summary": "Груп: {total}, активних {active}, варіантів у групах {members}, із зауваженнями {issues}",
        "vg_col_mp": "Маркетплейс", "vg_col_name": "Назва на майданчику", "vg_col_peid": "Груповий PeID", "vg_col_members": "Варіантів",
        "vg_col_family": "Сімʼя майданчика", "vg_col_active": "Активна", "vg_col_issues": "Контроль", "vg_col_comment": "Коментар",
        "vg_col_src": "Джерело",
        "vg_members_pick": "Склад групи", "vg_members_none": "Варіантів немає",
        "vg_saved": "Збережено: {n} груп",
        "pe_group_edit_hint": "Групу можна змінювати, коли обрано один маркетплейс: список — групи цього маркетплейсу.",
        "pe_hint": "Товарні сутності майданчиків за ТЗ 008: ASIN в Amazon, model id у ManoMano, product_sku у Leroy Merlin і Carrefour. "
                   "Збираються з лістингів та офферів щодня. Звʼязок із SKU за ТЗ живе в матриці; тут показано, під яким SKU сутність "
                   "виставлена зараз. Група варіацій призначається на рівні PeID (ТЗ 006).",
        "pe_mp": "Маркетплейс", "pe_search": "PeID, назва або SKU", "pe_only_issues": "Лише з проблемами",
        "pe_hide_parents": "Сховати Parent ASIN", "pe_hide_inactive": "Сховати неактивні",
        "pe_summary": "Сутностей: {total}, активних {active}, Parent ASIN {parents}, з помилками контролю {err}",
        "pe_col_mp": "Маркетплейс", "pe_col_peid": "PeID", "pe_col_title": "Назва на майданчику", "pe_col_skus": "SKU в лістингах",
        "pe_col_status": "Статуси лістингів", "pe_col_parent": "Parent", "pe_col_group": "Група варіацій", "pe_col_active": "Активний",
        "pe_col_seen": "Джерела", "pe_col_last": "Востаннє", "pe_col_issues": "Контроль", "pe_col_comment": "Коментар",
        "pe_saved": "Збережено: {n} записів",
        "sku_hint": "Довідник SKU за ТЗ 005: базові та складені товари компанії. Тип і назва — з Odoo, вага брутто — з ERP, "
                    "габарити упаковки та EAN — з Amazon, дата введення — оцінка за першим залишком/лістингом/продажем. "
                    "Поле, виправлене тут, позначається «manual» і завантажувачем більше не чіпається.",
        "sku_search": "Код або назва", "sku_type_f": "Тип", "sku_check_f": "Проблема",
        "sku_only_issues": "Лише з проблемами",
        "sku_t_base": "базовий", "sku_t_composite": "складений", "sku_t_none": "не визначено",
        "sku_summary": "SKU: {total} (базових {base}, складених {comp}, без типу {none}) · з помилками контролю {err}",
        "sku_col_sku": "SKU", "sku_col_type": "Тип", "sku_col_name": "Назва", "sku_col_ean": "EAN",
        "sku_col_supplier": "Код постачальника", "sku_col_intro": "Дата введення", "sku_col_exit": "Дата виведення",
        "sku_col_h": "В, мм", "sku_col_w": "Ш, мм", "sku_col_l": "Д, мм", "sku_col_vol": "Обʼєм, м³",
        "sku_col_weight": "Брутто, кг", "sku_col_restr": "Обмеження", "sku_col_passport": "Паспорт",
        "sku_col_issues": "Контроль", "sku_col_scope": "Де", "sku_col_src": "Джерела",
        "sku_restr_help": "Коди marketplace або країн через кому, де застосування заборонене (ТЗ 005 §6)",
        "sku_comp_pick": "Склад набору", "sku_comp_none": "Склад не знайдено",
        "sku_comp_col_base": "Базовий SKU", "sku_comp_col_qty": "К-сть", "sku_comp_col_name": "Назва",
        "sku_comp_note": "Склад незмінний (ТЗ 005 §7): інший набір — це новий SKU. Джерело — Odoo.",
        "sku_intro_estimate": "оцінка",
        "sku_saved_manual": "Збережено: {n} полів позначено як введені вручну",
        "al_hint": "Довідник типів алертів Кабінету. Вказано список ClickUp — задачі йдуть туди; "
                   "список порожній — тип живе лише в «Інцидентах». Інших вмикачів немає. "
                   "Виконавець — роль ClickUp, не людина; ролі заведе Владислав. "
                   "«Контроль закриття»: Кабінет сам закриває задачу, коли причина зникла з даних, і "
                   "перевідкриває, якщо її закрили руками при живій причині; без контролю — задачу створили й віддали.",
        "al_hint2": "Ідентифікатор алерту обов'язковий у задачі: у списку ClickUp має бути текстове поле "
                    "«Alert ID». Поки його немає, джоба задач не створює — причина в колонці «Перевірка списку».",
        "al_only_routed": "Лише зі списком", "al_search": "Тип",
        "al_col_type": "Тип", "al_col_title": "Назва", "al_col_descr": "Що означає",
        "al_col_list": "Список ClickUp (id)", "al_col_list_name": "Шлях списку",
        "al_col_mode": "Режим", "al_col_watch": "Контроль закриття", "al_col_risk": "Risk",
        "al_col_due": "Термін, дн", "al_col_role": "Роль ClickUp", "al_col_role_id": "id ролі",
        "al_col_since": "Задачі з дати", "al_col_open": "Відкрито", "al_col_tasks": "Задач у ClickUp",
        "al_col_check": "Перевірка списку", "al_col_checked": "Перевірено",
        "al_mode_task": "задача на інцидент", "al_mode_digest": "дайджест",
        "al_summary": "Типів: {total}, зі списком ClickUp: {routed}, відкритих інцидентів: {open}",
        "al_sync_hint": "Джоба «Kabinet - ClickUp Sync» ходить раз на годину; зміни тут підхоплюються наступним прогоном.",
        "as_hint": "Ліворуч факт — статус за продажами, його рахує завантажувач і руками він не правиться. "
                   "Праворуч намір — що з цим SKU на цьому ринку вирішено. Прогноз читає намір: "
                   "«виводимо» і «не продаємо» з прогнозу виключаються, «запускаємо» — потрапляє без історії.",
        "as_mp": "Ринок", "as_fact": "Факт", "as_search": "SKU",
        "as_only_gap": "Лише де намір не задано",
        "as_col_fact": "Факт (продажі)", "as_col_target": "Намір", "as_col_note": "Примітка",
        "as_col_upd": "Змінено",
        "as_t_": "—", "as_t_keep": "тримаємо", "as_t_launch": "запускаємо", "as_t_phase_out": "виводимо",
        "as_t_seasonal": "сезонний", "as_t_stop": "не продаємо",
        "as_f_active": "продається", "as_f_not_launched": "не продавався", "as_f_phasing_out": "згасає",
        "as_f_seasonal_pause": "сезонна пауза", "as_f_discontinued": "знятий",
        "as_summary": "Намір задано у {n} з {total} пар на цьому ринку",
        "save": "💾 Зберегти зміни", "saved": "Збережено: {n} запис(ів)",
        "nochange": "Змін немає", "err": "Помилка: {e}", "no_data": "Немає даних",
        "del_col": "Видалити", "delete_sel": "🗑 Видалити відмічені", "deleted": "Видалено: {n}",
        "wh_hint": "Два поля заповнюються руками — майданчики складу та пріоритет "
                   "забезпечення. Решта приїздить із ERP і змінюється там.",
        "wh_pick": "Склад", "wh_show_sales": "Показати точки продажу та FBA",
        "wh_show_sales_hint": "За замовчуванням видно лише склади зберігання — "
                              "рішення ухвалюються по них. У FBA майданчик "
                              "визначений країною і проставлений сам.",
        "wh_inactive": "вимкнений", "wh_active": "активний",
        "wh_mp_h": "Які майданчики забезпечує",
        "wh_mp_hint": "Відміть вітрини, товар на які їде з цього складу. "
                      "Можна кілька — склад зазвичай годує не одну.",
        "wh_mp_missing": "Таблиця звʼязків ще не створена: виконайте "
                         "sql/warehouse_marketplaces.sql. Пріоритет поки "
                         "зберігається, майданчики — ні.",
        "wh_mp_count": "Відмічено: {n} з {total}",
        "wh_prio_h": "Пріоритет забезпечення",
        "wh_prio_hint": "Один номер на склад, спільний для всіх майданчиків. "
                        "1 — беремо звідси в першу чергу. "
                        "0 — склад у забезпеченні не бере участі.",
        "wh_src_h": "Звідки поповнюється",
        "wh_src_none": "Маршрутів підживлення на цей склад поки немає.",
        "wh_src_hint": "Рахується по накладних, змінювати на вкладці «Підживлення».",
        "wh_sum_h": "Що вже заповнено",
        "wh_all": "Усі склади однією таблицею",
        "col_mps": "Майданчики", "col_src": "Склад-джерело", "col_basis": "Підстава",
        "basis_ttn": "накладних: {n}", "basis_expert": "оцінка вручну",
        "t_sales": "точка продажу", "t_storage": "зберігання",
        "t_transit": "транзит", "t_manufacturer": "виробник",
        "ch_hint": "Хто кого поповнює і за скільки днів. Термін із накладних "
                   "(ttn_planned) надійніший за експертний (expert).",
        "ch_add": "➕ Додати звʼязок підживлення",
        "ch_from": "Склад-джерело", "ch_to": "Склад-отримувач",
        "ch_same": "Джерело та отримувач не можуть збігатися",
        "ch_exists": "Такий звʼязок уже є",
        "mp_hint": "Довідник маркетплейсів. Код та Amazon ID змінювати не можна.",
        "pool_hint": "Пул — група маркетплейсів зі спільним сукупним прогнозом. "
                     "Маркетплейс не може одночасно бути у двох активних пулах.",
        "pool_list": "Пули", "pool_new": "Новий пул", "pool_name": "Назва",
        "pool_comment": "Коментар", "pool_create": "➕ Створити пул",
        "pool_save_cmt": "✏️ Зберегти коментар", "pool_delete": "🗑 Видалити пул",
        "pool_members": "Склад пулу", "pool_select": "Маркетплейси",
        "pool_from": "Діє з", "pool_to": "Діє по (порожньо — безстроково)",
        "pool_save": "💾 Зберегти склад", "pool_none": "Пулів поки немає — створи перший",
        "pool_conflict": "Уже в іншому пулі: {mp}", "pool_created": "Пул створено",
        "pool_deleted": "Пул видалено", "pool_empty_name": "Вкажи назву пулу",
        "norm_hint": "Норматив покриття в днях по SKU для маркетплейсу або пулу. "
                     "Мінімум ≤ ціль ≤ максимум.",
        "norm_add": "➕ Додати норматив", "norm_sku": "SKU",
        "norm_target": "Привʼязка", "norm_target_mp": "Маркетплейс", "norm_target_pool": "Пул",
        "norm_target_val": "Значення", "norm_added": "Норматив додано",
        "norm_manual": "SKU немає в списку — ввести вручну",
        "norm_no_pools": "Пулів ще немає, тому доступна лише прив'язка до маркетплейсу.",
        "norm_now": "Зараз покриття {w} тижн., статус «{st}»",
        "norm_now_none": "Покриття по цій парі ще не рахувалося",
        "norm_unused": "Норматив поки лише зберігається: розрахунок покриття його не читає, "
                       "статуси на «Залишках» завантажувач рахує за своїми порогами. "
                       "Заповнювати має сенс — цифри знадобляться, коли розрахунок переведуть на довідник.",
        "col_product": "Товар",
        "norm_exists": "Норматив для цієї звʼязки вже є — відредагуй у таблиці нижче",
        "norm_order": "Має бути: мінімум ≤ ціль ≤ максимум",
        "norm_empty": "Вкажи SKU", "norm_list": "Чинні нормативи",
        "norm_none": "Нормативи ще не задані", "norm_no_target": "Спершу створи пул",
        "col_id": "ID", "col_name": "Назва", "col_code": "Код", "col_type": "Тип",
        "col_mp": "Маркетплейс", "col_country": "Країна", "col_currency": "Валюта",
        "col_amazon_id": "Amazon ID", "col_active": "Активний", "col_canon": "Дубль від",
        "col_note": "Примітка", "col_ship_prio": "Пріоритет відвантаження",
        "col_route": "Тип маршруту", "col_median": "Термін, дн",
        "col_shipments": "Відвантажень", "col_lead_src": "Джерело терміну",
        "col_sample": "Накладних", "col_min": "Мін, дн", "col_target": "Ціль, дн",
        "col_max": "Макс, дн", "col_pool": "Пул", "col_from": "З", "col_to": "По",
    },
    "en": {
        "title": "📚 Dictionaries",
        "sub": "Settings behind stock, coverage and replenishment calculations",
        "tab_wh": "🏭 Warehouses", "tab_ch": "🔗 Supply chains", "tab_mp": "🌍 Marketplaces",
        "tab_pool": "📦 Pools", "tab_norm": "📏 Coverage norms",
        "tab_assort": "🧭 Assortment",
        "tab_alerts": "🔔 Alerts",
        "tab_sku": "🧱 SKU",
        "tab_peid": "🏷 PeID",
        "tab_vg": "🧬 Variations",
        "tab_matrix": "🗂 Matrix",
        "am_hint": "Assortment matrix per spec 007: SKU admission to a platform (framework) or a marketplace (operational), the «in listing» and "
                   "«complementary» flags, history as immutable dated records. The initial snapshot comes from live listings (source seed); "
                   "human decisions are source manual and the loader never changes them. Exclusion — a date in «Removed»; relaunch — a new record.",
        "am_level": "Level", "am_level_marketplace": "marketplace", "am_level_platform": "platform",
        "am_platform": "Platform", "am_mp": "Marketplace", "am_search": "SKU", "am_show_history": "Show history",
        "am_only_issues": "Only with issues",
        "am_summary": "Active admissions: {n} · in listing {listing} · complementary {comp} · with control errors {err}",
        "am_col_level": "Level", "am_col_platform": "Platform", "am_col_mp": "Marketplace", "am_col_sku": "SKU", "am_col_name": "Name",
        "am_col_type": "Type", "am_col_added": "Added", "am_col_removed": "Removed", "am_col_listing": "In listing",
        "am_col_comp": "Complementary", "am_col_reason": "Reason", "am_col_source": "Source", "am_col_issues": "Control",
        "am_add_title": "Add SKU to the matrix", "am_add_sku": "SKU", "am_add_date": "Added on", "am_add_btn": "➕ Add",
        "am_add_ok": "Admission created", "am_add_dup": "An active record already exists", "am_add_no_intro": "SKU has no intro date (spec 007 §8)",
        "am_add_exited": "SKU has an exit date — no new admission", "am_add_restricted": "SKU is restricted for this platform/country (spec 005 §6)",
        "am_add_no_platform": "No framework platform admission for this SKU — add it at platform level first",
        "am_add_comp_composite": "A composite SKU cannot be complementary (spec 007 §9)",
        "am_saved": "Saved: admissions {a}, representations {r}",
        "am_repr_title": "SKU representations on the marketplace", "am_repr_pick_mp": "Marketplace for representations",
        "am_repr_col_peid": "PeID", "am_repr_col_group": "Variation group", "am_repr_col_role": "Commercial role",
        "am_repr_col_from": "From", "am_repr_col_to": "To", "am_repr_none": "No representations",
        "am_role_help": "Hero / Traffic / Margin / Support — only for a PeID within a variation group (spec 009). Empty without a group.",
        "am_role_no_group": "Role not saved for {peid}: the PeID has no variation group",
        "vg_hint": "Variation groups per spec 006: on Amazon — a Parent ASIN and its children. A group lives in one marketplace, a variant belongs to one group; "
                   "the link is assigned at PeID level (PeID tab, with a single marketplace selected). Name — as on the marketplace; "
                   "a name corrected here is marked manual. The group is the consolidation level for ads and ACOS.",
        "vg_summary": "Groups: {total}, active {active}, variants in groups {members}, with remarks {issues}",
        "vg_col_mp": "Marketplace", "vg_col_name": "Name on marketplace", "vg_col_peid": "Group PeID", "vg_col_members": "Variants",
        "vg_col_family": "Marketplace family", "vg_col_active": "Active", "vg_col_issues": "Control", "vg_col_comment": "Comment",
        "vg_col_src": "Source",
        "vg_members_pick": "Group members", "vg_members_none": "No variants",
        "vg_saved": "Saved: {n} groups",
        "pe_group_edit_hint": "The group can be changed when a single marketplace is selected: the list holds that marketplace's groups.",
        "pe_hint": "Marketplace product entities per spec 008: ASIN on Amazon, model id on ManoMano, product_sku on Leroy Merlin and Carrefour. "
                   "Collected daily from listings and offers. The SKU link per spec lives in the matrix; here you see which SKU the entity "
                   "is currently listed under. The variation group is assigned at PeID level (spec 006).",
        "pe_mp": "Marketplace", "pe_search": "PeID, title or SKU", "pe_only_issues": "Only with issues",
        "pe_hide_parents": "Hide Parent ASINs", "pe_hide_inactive": "Hide inactive",
        "pe_summary": "Entities: {total}, active {active}, Parent ASINs {parents}, with control errors {err}",
        "pe_col_mp": "Marketplace", "pe_col_peid": "PeID", "pe_col_title": "Title on marketplace", "pe_col_skus": "SKUs in listings",
        "pe_col_status": "Listing statuses", "pe_col_parent": "Parent", "pe_col_group": "Variation group", "pe_col_active": "Active",
        "pe_col_seen": "Sources", "pe_col_last": "Last seen", "pe_col_issues": "Control", "pe_col_comment": "Comment",
        "pe_saved": "Saved: {n} records",
        "sku_hint": "SKU directory per spec 005: base and composite company products. Type and name from Odoo, gross weight from ERP, "
                    "package dimensions and EAN from Amazon, intro date estimated from first stock/listing/sale. "
                    "A field edited here is marked «manual» and the loader never overwrites it again.",
        "sku_search": "Code or name", "sku_type_f": "Type", "sku_check_f": "Issue",
        "sku_only_issues": "Only with issues",
        "sku_t_base": "base", "sku_t_composite": "composite", "sku_t_none": "undefined",
        "sku_summary": "SKUs: {total} (base {base}, composite {comp}, untyped {none}) · with control errors {err}",
        "sku_col_sku": "SKU", "sku_col_type": "Type", "sku_col_name": "Name", "sku_col_ean": "EAN",
        "sku_col_supplier": "Supplier code", "sku_col_intro": "Intro date", "sku_col_exit": "Exit date",
        "sku_col_h": "H, mm", "sku_col_w": "W, mm", "sku_col_l": "L, mm", "sku_col_vol": "Volume, m³",
        "sku_col_weight": "Gross, kg", "sku_col_restr": "Restrictions", "sku_col_passport": "Passport",
        "sku_col_issues": "Control", "sku_col_scope": "Where", "sku_col_src": "Sources",
        "sku_restr_help": "Comma-separated marketplace or country codes where use is prohibited (spec 005 §6)",
        "sku_comp_pick": "Kit composition", "sku_comp_none": "No composition found",
        "sku_comp_col_base": "Base SKU", "sku_comp_col_qty": "Qty", "sku_comp_col_name": "Name",
        "sku_comp_note": "Composition is immutable (spec 005 §7): a different kit is a new SKU. Source — Odoo.",
        "sku_intro_estimate": "estimate",
        "sku_saved_manual": "Saved: {n} fields marked as manually entered",
        "al_hint": "Dictionary of Kabinet alert types. A ClickUp list set — tasks go there; "
                   "list empty — the type lives only in «Incidents». There is no other switch. "
                   "Assignee is a ClickUp role, not a person; roles will be created by Vladyslav. "
                   "«Watch close»: Kabinet closes the task itself once the cause is gone from data and "
                   "reopens it if closed by hand while the cause persists; unwatched — created and handed over.",
        "al_hint2": "The alert identifier is mandatory on the task: the ClickUp list must have a text field "
                    "«Alert ID». Until it exists the job creates no tasks — see the «List check» column.",
        "al_only_routed": "Only with a list", "al_search": "Type",
        "al_col_type": "Type", "al_col_title": "Title", "al_col_descr": "Meaning",
        "al_col_list": "ClickUp list (id)", "al_col_list_name": "List path",
        "al_col_mode": "Mode", "al_col_watch": "Watch close", "al_col_risk": "Risk",
        "al_col_due": "Due, days", "al_col_role": "ClickUp role", "al_col_role_id": "role id",
        "al_col_since": "Tasks since", "al_col_open": "Open", "al_col_tasks": "Tasks in ClickUp",
        "al_col_check": "List check", "al_col_checked": "Checked",
        "al_mode_task": "task per incident", "al_mode_digest": "digest",
        "al_summary": "Types: {total}, with a ClickUp list: {routed}, open incidents: {open}",
        "al_sync_hint": "The «Kabinet - ClickUp Sync» job runs hourly; changes here are picked up on the next run.",
        "as_hint": "Left is fact — the sales-derived status, computed by the loader, not editable. "
                   "Right is intent — what has been decided for this SKU on this market. The forecast reads intent: "
                   "«phase out» and «stop» are excluded, «launch» enters without history.",
        "as_mp": "Market", "as_fact": "Fact", "as_search": "SKU",
        "as_only_gap": "Only where intent is not set",
        "as_col_fact": "Fact (sales)", "as_col_target": "Intent", "as_col_note": "Note",
        "as_col_upd": "Updated",
        "as_t_": "—", "as_t_keep": "keep", "as_t_launch": "launch", "as_t_phase_out": "phase out",
        "as_t_seasonal": "seasonal", "as_t_stop": "stop",
        "as_f_active": "selling", "as_f_not_launched": "never sold", "as_f_phasing_out": "fading",
        "as_f_seasonal_pause": "seasonal pause", "as_f_discontinued": "discontinued",
        "as_summary": "Intent set for {n} of {total} pairs on this market",
        "save": "💾 Save changes", "saved": "Saved: {n} row(s)",
        "nochange": "No changes", "err": "Error: {e}", "no_data": "No data",
        "del_col": "Delete", "delete_sel": "🗑 Delete selected", "deleted": "Deleted: {n}",
        "wh_hint": "Two fields are filled by hand — the warehouse marketplaces and "
                   "the supply priority. The rest comes from ERP and changes there.",
        "wh_pick": "Warehouse", "wh_show_sales": "Show sales points and FBA",
        "wh_show_sales_hint": "Storage warehouses only by default — that is where "
                              "the decisions are made. FBA marketplaces follow "
                              "from the country and are filled in automatically.",
        "wh_inactive": "disabled", "wh_active": "active",
        "wh_mp_h": "Marketplaces served",
        "wh_mp_hint": "Tick the storefronts supplied from this warehouse. "
                      "More than one is normal.",
        "wh_mp_missing": "The link table does not exist yet: run "
                         "sql/warehouse_marketplaces.sql. Priority still saves, "
                         "marketplaces do not.",
        "wh_mp_count": "Ticked: {n} of {total}",
        "wh_prio_h": "Supply priority",
        "wh_prio_hint": "One number per warehouse, the same for every marketplace. "
                        "1 — take from here first. 0 — the warehouse takes no part "
                        "in supply.",
        "wh_src_h": "Replenished from",
        "wh_src_none": "No supply routes into this warehouse yet.",
        "wh_src_hint": "Computed from invoices, edited on the Supply chains tab.",
        "wh_sum_h": "Filled in so far",
        "wh_all": "All warehouses in one table",
        "col_mps": "Marketplaces", "col_src": "Source warehouse", "col_basis": "Basis",
        "basis_ttn": "invoices: {n}", "basis_expert": "manual estimate",
        "t_sales": "sales point", "t_storage": "storage",
        "t_transit": "transit", "t_manufacturer": "manufacturer",
        "ch_hint": "Who replenishes whom and in how many days. Lead time from invoices "
                   "(ttn_planned) is more reliable than expert estimate.",
        "ch_add": "➕ Add supply link",
        "ch_from": "Source warehouse", "ch_to": "Receiver warehouse",
        "ch_same": "Source and receiver must differ",
        "ch_exists": "This link already exists",
        "mp_hint": "Marketplace registry. Code and Amazon ID are read-only.",
        "pool_hint": "A pool is a group of marketplaces sharing one aggregate forecast. "
                     "A marketplace cannot belong to two active pools.",
        "pool_list": "Pools", "pool_new": "New pool", "pool_name": "Name",
        "pool_comment": "Comment", "pool_create": "➕ Create pool",
        "pool_save_cmt": "✏️ Save comment", "pool_delete": "🗑 Delete pool",
        "pool_members": "Pool members", "pool_select": "Marketplaces",
        "pool_from": "Valid from", "pool_to": "Valid to (empty — open-ended)",
        "pool_save": "💾 Save members", "pool_none": "No pools yet — create the first one",
        "pool_conflict": "Already in another pool: {mp}", "pool_created": "Pool created",
        "pool_deleted": "Pool deleted", "pool_empty_name": "Enter a pool name",
        "norm_hint": "Coverage norm in days per SKU for a marketplace or pool. "
                     "Min ≤ target ≤ max.",
        "norm_add": "➕ Add norm", "norm_sku": "SKU",
        "norm_target": "Target", "norm_target_mp": "Marketplace", "norm_target_pool": "Pool",
        "norm_target_val": "Value", "norm_added": "Norm added",
        "norm_manual": "SKU not in the list — type it in",
        "norm_no_pools": "No pools yet, so only a marketplace can be targeted.",
        "norm_now": "Coverage now {w} weeks, status \u00ab{st}\u00bb",
        "norm_now_none": "Coverage for this pair has not been computed yet",
        "norm_unused": "The norm is stored only: the coverage calculation does not read it, "
                       "and the statuses on Stock come from the loader's own thresholds. "
                       "Filling it in is still worth it — the numbers are needed once the "
                       "calculation moves to the dictionary.",
        "col_product": "Product",
        "norm_exists": "A norm for this combination exists — edit it in the table below",
        "norm_order": "Required: min ≤ target ≤ max",
        "norm_empty": "Enter a SKU", "norm_list": "Active norms",
        "norm_none": "No norms defined yet", "norm_no_target": "Create a pool first",
        "col_id": "ID", "col_name": "Name", "col_code": "Code", "col_type": "Type",
        "col_mp": "Marketplace", "col_country": "Country", "col_currency": "Currency",
        "col_amazon_id": "Amazon ID", "col_active": "Active", "col_canon": "Alias of",
        "col_note": "Note", "col_ship_prio": "Shipping priority",
        "col_route": "Route type", "col_median": "Lead, days",
        "col_shipments": "Shipments", "col_lead_src": "Lead source",
        "col_sample": "Invoices", "col_min": "Min, days", "col_target": "Target, days",
        "col_max": "Max, days", "col_pool": "Pool", "col_from": "From", "col_to": "To",
    },
}


def _lang() -> str:
    try:
        lg = str(get_lang() or "ru").lower()[:2]
    except Exception:
        lg = str(st.session_state.get("lang", "ru")).lower()[:2]
    return lg if lg in TR else "ru"


def _tr(key: str) -> str:
    return TR[_lang()].get(key, TR["ru"].get(key, key))


def _trf(key: str, **kw) -> str:
    """Подстановка, которая не роняет страницу.

    Фраза и вызов живут в разных местах файла и расходятся набором
    плейсхолдеров легко. Обычный .format() на таком расхождении бросает
    KeyError и уносит с собой всю вкладку — лучше показать строку как есть.
    """
    try:
        return _tr(key).format(**kw)
    except (KeyError, IndexError, ValueError):
        return _tr(key)


# ═══════════════════════════════════════════════════════════════════════════
# БАЗА
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120)
def q(sql: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


# Связка «склад ↔ площадки» появилась позже остальной схемы: пока
# sql/warehouse_marketplaces.sql не выполнен, таблицы в базе нет, и вкладка
# должна открываться без неё, а не падать на «relation does not exist».
WH_MP = "kabinet_data.warehouse_marketplaces"


@st.cache_data(ttl=300)
def has_table(qualified: str) -> bool:
    return bool(pd.notna(q(f"SELECT to_regclass('{qualified}') AS t").iloc[0]["t"]))


def _int0(v) -> int:
    """Число или ноль. NULL из базы доезжает то None, то NaN, и `v or 0`
    на NaN не спасает: NaN истинен, а int(NaN) бросает ValueError."""
    return 0 if pd.isna(v) else int(v)


def q1(sql: str, params: tuple) -> pd.DataFrame:
    """Разовый запрос с параметрами.

    Не через q(): та кэшируется по тексту запроса, а параметры в текст не
    попадают — на второй SKU кэш вернул бы ответ по первому. И не через
    склейку строки: апостроф в артикуле роняет запрос.
    """
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def _py(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.date()
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return v
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def exec_sql(statements):
    conn = get_connection()
    try:
        cur = conn.cursor()
        for sql, params in statements:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _same(a, b) -> bool:
    a, b = _py(a), _py(b)
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except Exception:
            return str(a) == str(b)
    return str(a) == str(b)


def build_updates(orig, edited, table, pk, cols):
    o, e = orig.set_index(pk), edited.set_index(pk)
    out = []
    for idx in e.index:
        if pd.isna(idx) or idx not in o.index:
            continue
        changed = {c: _py(e.at[idx, c]) for c in cols
                   if not _same(e.at[idx, c], o.at[idx, c])}
        if changed:
            sets = ", ".join(f"{c} = %s" for c in changed)
            out.append((f"UPDATE {table} SET {sets} WHERE {pk} = %s",
                        list(changed.values()) + [_py(idx)]))
    return out


def save_block(orig, edited, table, pk, cols):
    ups = build_updates(orig, edited, table, pk, cols)
    if not ups:
        st.info(_tr("nochange"))
        return
    try:
        exec_sql(ups)
        st.cache_data.clear()
        st.success(_tr("saved").format(n=len(ups)))
        st.rerun()
    except Exception as e:
        st.error(_tr("err").format(e=e))


# ═══════════════════════════════════════════════════════════════════════════
# СТРАНИЦА
# ═══════════════════════════════════════════════════════════════════════════

init_lang()

st.title(_tr("title"))
st.caption(_tr("sub"))

# «Ассортимент» (факт + намерение по SKU × рынок) снят 18.09.2026: это не матрица по ТЗ 007,
# sku_target_status никто не заполнял. Его место — «Матрица»; таблицы остались.
tab_wh, tab_ch, tab_mp, tab_pool, tab_norm, tab_alerts, tab_sku, tab_peid, tab_vg, tab_matrix = st.tabs(
    [_tr("tab_wh"), _tr("tab_ch"), _tr("tab_mp"), _tr("tab_pool"), _tr("tab_norm"),
     _tr("tab_alerts"), _tr("tab_sku"), _tr("tab_peid"), _tr("tab_vg"), _tr("tab_matrix")]
)

# ---------------------------------------------------------------- склады ---
with tab_wh:
    st.caption(_tr("wh_hint"))

    wh = q("""
        SELECT id, name, code, type, marketplace, country,
               shipping_priority, is_active, canonical_id, note
        FROM kabinet_data.warehouses
        ORDER BY type, country, name
    """)

    if wh.empty:
        st.info(_tr("no_data"))
    else:
        mp = q("""
            SELECT id, code, name, country, channel
            FROM kabinet_data.marketplaces
            WHERE is_active IS NOT FALSE
            ORDER BY channel, name
        """)
        links_ok = has_table(WH_MP)
        links = (q(f"SELECT warehouse_id, marketplace_id FROM {WH_MP}")
                 if links_ok else
                 pd.DataFrame(columns=["warehouse_id", "marketplace_id"]))
        by_wh = {int(k): {int(x) for x in v}
                 for k, v in links.groupby("warehouse_id")["marketplace_id"]}
        mp_name = {int(r["id"]): r["name"] for _, r in mp.iterrows()}

        show_all = st.toggle(_tr("wh_show_sales"), value=False, key="wh_show_all")
        st.caption(_tr("wh_show_sales_hint"))
        pool = wh if show_all else wh[wh["type"] == "storage"]

        if pool.empty:
            st.info(_tr("no_data"))
        else:
            titles = {int(r["id"]): f'{r["name"]} ({r["code"]})' if r["code"]
                      else str(r["name"]) for _, r in pool.iterrows()}
            sel = st.selectbox(_tr("wh_pick"), list(titles),
                               format_func=lambda i: titles[i], key="wh_pick")
            row = wh.set_index("id").loc[sel]

            facts = [_tr(f't_{row["type"]}') if row["type"] else "—",
                     str(row["country"] or "—"),
                     _tr("wh_inactive") if row["is_active"] is False
                     else _tr("wh_active")]
            st.markdown(f'#### {row["name"]}')
            st.caption(" · ".join(facts))

            # ── площадки ──────────────────────────────────────────────────
            st.markdown("##### " + _tr("wh_mp_h"))
            picked, было = set(), by_wh.get(int(sel), set())
            if not links_ok:
                st.warning(_tr("wh_mp_missing"))
            else:
                st.caption(_tr("wh_mp_hint"))
                # Amazon отдельной колонкой: десять витрин против четырёх
                # у всех остальных каналов вместе
                amz, rest = st.columns(2)
                with amz:
                    st.markdown("**Amazon**")
                    for _, m in mp[mp["channel"] == "Amazon"].iterrows():
                        if st.checkbox(m["name"], value=int(m["id"]) in было,
                                       key=f'wm_{sel}_{m["id"]}'):
                            picked.add(int(m["id"]))
                with rest:
                    for ch_name in [c for c in dict.fromkeys(mp["channel"])
                                    if c != "Amazon"]:
                        st.markdown(f"**{ch_name}**")
                        for _, m in mp[mp["channel"] == ch_name].iterrows():
                            if st.checkbox(m["name"], value=int(m["id"]) in было,
                                           key=f'wm_{sel}_{m["id"]}'):
                                picked.add(int(m["id"]))
                st.caption(_trf("wh_mp_count", n=len(picked), total=len(mp)))

            # ── приоритет ─────────────────────────────────────────────────
            st.markdown("##### " + _tr("wh_prio_h"))
            st.caption(_tr("wh_prio_hint"))
            prio_было = _int0(row["shipping_priority"])
            prio = st.number_input(_tr("col_ship_prio"), min_value=0, max_value=99,
                                   step=1, value=prio_было, key=f"wp_{sel}")

            # ── откуда пополняется, только чтение ─────────────────────────
            st.markdown("##### " + _tr("wh_src_h"))
            src = q(f"""
                SELECT f.name AS src_name, c.median_days, c.lead_source, c.sample_size
                FROM kabinet_data.supply_chains c
                JOIN kabinet_data.warehouses f ON f.id = c.from_warehouse_id
                WHERE c.to_warehouse_id = {int(sel)} AND c.is_active IS NOT FALSE
                ORDER BY c.median_days, f.name
            """)
            if src.empty:
                st.caption(_tr("wh_src_none"))
            else:
                st.caption(_tr("wh_src_hint"))
                st.dataframe(
                    pd.DataFrame({
                        _tr("col_src"): src["src_name"],
                        _tr("col_median"): src["median_days"],
                        _tr("col_basis"): [
                            _trf("basis_ttn", n=int(n)) if s == "ttn_planned" and pd.notna(n)
                            else _tr("basis_expert")
                            for s, n in zip(src["lead_source"], src["sample_size"])],
                    }),
                    use_container_width=True, hide_index=True,
                )

            # ── сохранение ────────────────────────────────────────────────
            if st.button(_tr("save"), key="save_wh_card", type="primary"):
                stmts = []
                if prio != prio_было:
                    stmts.append((
                        "UPDATE kabinet_data.warehouses SET shipping_priority = %s "
                        "WHERE id = %s", (int(prio), int(sel))))
                if links_ok:
                    for m_id in sorted(picked - было):
                        stmts.append((
                            f"INSERT INTO {WH_MP} (warehouse_id, marketplace_id, "
                            "updated_by) VALUES (%s, %s, 'kabinet') "
                            "ON CONFLICT DO NOTHING", (int(sel), int(m_id))))
                    if было - picked:
                        stmts.append((
                            f"DELETE FROM {WH_MP} WHERE warehouse_id = %s "
                            "AND marketplace_id = ANY(%s)",
                            (int(sel), sorted(int(x) for x in было - picked))))
                if not stmts:
                    st.info(_tr("nochange"))
                else:
                    try:
                        exec_sql(stmts)
                        st.cache_data.clear()
                        st.success(_trf("saved", n=len(stmts)))
                        st.rerun()
                    except Exception as e:
                        st.error(_trf("err", e=e))

            # ── что уже заполнено ─────────────────────────────────────────
            st.markdown("##### " + _tr("wh_sum_h"))
            st.dataframe(
                pd.DataFrame({
                    _tr("col_name"): [titles[int(i)] for i in pool["id"]],
                    _tr("col_mps"): [
                        ", ".join(mp_name[m] for m in sorted(by_wh.get(int(i), ())))
                        or "—" for i in pool["id"]],
                    _tr("col_ship_prio"): [_int0(p) for p in pool["shipping_priority"]],
                    _tr("col_active"): list(pool["is_active"]),
                }),
                use_container_width=True, hide_index=True,
                column_config={_tr("col_active"): st.column_config.CheckboxColumn()},
            )

        # ── таблица целиком, для тех, кто правит пачкой ───────────────────
        with st.expander(_tr("wh_all")):
            ed = st.data_editor(
                wh, key="ed_wh", use_container_width=True, height=520,
                hide_index=True, num_rows="fixed",
                disabled=["id", "name", "code", "canonical_id"],
                column_config={
                    "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                    "name": st.column_config.TextColumn(_tr("col_name"), width="large"),
                    "code": st.column_config.TextColumn(_tr("col_code"), width="small"),
                    "type": st.column_config.SelectboxColumn(
                        _tr("col_type"),
                        options=["sales", "storage", "transit", "manufacturer"]),
                    "marketplace": st.column_config.TextColumn(_tr("col_mp"), width="small"),
                    "country": st.column_config.TextColumn(_tr("col_country"), width="small"),
                    "shipping_priority": st.column_config.NumberColumn(
                        _tr("col_ship_prio"), min_value=0, max_value=99, step=1),
                    "is_active": st.column_config.CheckboxColumn(_tr("col_active")),
                    "canonical_id": st.column_config.NumberColumn(_tr("col_canon"), width="small"),
                    "note": st.column_config.TextColumn(_tr("col_note"), width="large"),
                },
            )
            if st.button(_tr("save"), key="save_wh", type="primary"):
                save_block(wh, ed, "kabinet_data.warehouses", "id",
                           ["type", "marketplace", "country", "shipping_priority",
                            "is_active", "note"])

# ------------------------------------------------------------- подпитка ---
with tab_ch:
    st.caption(_tr("ch_hint"))
    ch = q("""
        SELECT c.id,
               f.name  AS from_name,
               tw.name AS to_name,
               c.route_type, c.median_days, c.shipment_count,
               c.lead_source, c.sample_size, c.is_active, c.note
        FROM kabinet_data.supply_chains c
        LEFT JOIN kabinet_data.warehouses f  ON f.id  = c.from_warehouse_id
        LEFT JOIN kabinet_data.warehouses tw ON tw.id = c.to_warehouse_id
        ORDER BY tw.name, c.median_days
    """)
    wh_all = q("""
        SELECT id, name, COALESCE(code, '') AS code
        FROM kabinet_data.warehouses
        WHERE is_active IS NOT FALSE
        ORDER BY name
    """)
    wh_label = {int(r.id): (f"{r['name']} ({r.code})" if r.code else r["name"])
                for _, r in wh_all.iterrows()}
    label_wh = {v: k for k, v in wh_label.items()}
    ROUTES = ["internal", "last_mile", "fba_inbound"]

    if ch.empty:
        st.info(_tr("no_data"))
    else:
        ed_ch = st.data_editor(
            ch, key="ed_ch", use_container_width=True, height=460,
            hide_index=True, num_rows="fixed",
            disabled=["id", "from_name", "to_name", "shipment_count",
                      "lead_source", "sample_size"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "from_name": st.column_config.TextColumn(_tr("ch_from"), width="medium"),
                "to_name": st.column_config.TextColumn(_tr("ch_to"), width="medium"),
                "route_type": st.column_config.SelectboxColumn(
                    _tr("col_route"), options=ROUTES),
                "median_days": st.column_config.NumberColumn(
                    _tr("col_median"), min_value=0, max_value=365, step=1),
                "shipment_count": st.column_config.NumberColumn(
                    _tr("col_shipments"), width="small"),
                "lead_source": st.column_config.TextColumn(_tr("col_lead_src"), width="small"),
                "sample_size": st.column_config.NumberColumn(_tr("col_sample"), width="small"),
                "is_active": st.column_config.CheckboxColumn(_tr("col_active")),
                "note": st.column_config.TextColumn(_tr("col_note"), width="large"),
            },
        )
        if st.button(_tr("save"), key="save_ch", type="primary"):
            save_block(ch, ed_ch, "kabinet_data.supply_chains", "id",
                       ["route_type", "median_days", "is_active", "note"])

    with st.expander(_tr("ch_add")):
        c1, c2 = st.columns(2)
        src = c1.selectbox(_tr("ch_from"), list(label_wh.keys()), key="new_ch_src")
        rec = c2.selectbox(_tr("ch_to"), list(label_wh.keys()), key="new_ch_rec")
        c3, c4, c5 = st.columns([1, 1, 2])
        rtype = c3.selectbox(_tr("col_route"), ROUTES, key="new_ch_type")
        lead = c4.number_input(_tr("col_median"), 0, 365, 14, key="new_ch_lead")
        note = c5.text_input(_tr("col_note"), key="new_ch_note")
        if st.button(_tr("ch_add"), key="add_ch", type="primary"):
            sid, rid = label_wh[src], label_wh[rec]
            exists = q(f"""
                SELECT 1 FROM kabinet_data.supply_chains
                WHERE from_warehouse_id = {sid} AND to_warehouse_id = {rid}
                LIMIT 1
            """)
            if sid == rid:
                st.error(_tr("ch_same"))
            elif not exists.empty:
                st.warning(_tr("ch_exists"))
            else:
                try:
                    exec_sql([("""
                        INSERT INTO kabinet_data.supply_chains
                            (from_warehouse_id, to_warehouse_id, route_type,
                             median_days, lead_source, is_active, note)
                        VALUES (%s, %s, %s, %s, 'expert', TRUE, %s)
                    """, [sid, rid, rtype, int(lead), note or None])])
                    st.cache_data.clear()
                    st.success(_tr("saved").format(n=1))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))

# -------------------------------------------------------- маркетплейсы ---
with tab_mp:
    st.caption(_tr("mp_hint"))
    mp = q("""
        SELECT id, code, name, country, currency, amazon_id, is_active
        FROM kabinet_data.marketplaces
        ORDER BY code
    """)
    if mp.empty:
        st.info(_tr("no_data"))
    else:
        ed_mp = st.data_editor(
            mp, key="ed_mp", use_container_width=True, height=420,
            hide_index=True, num_rows="fixed",
            disabled=["id", "code", "amazon_id"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "code": st.column_config.TextColumn(_tr("col_code"), width="small"),
                "name": st.column_config.TextColumn(_tr("col_name"), width="medium"),
                "country": st.column_config.TextColumn(_tr("col_country"), width="small"),
                "currency": st.column_config.TextColumn(_tr("col_currency"), width="small"),
                "amazon_id": st.column_config.TextColumn(_tr("col_amazon_id"), width="medium"),
                "is_active": st.column_config.CheckboxColumn(_tr("col_active")),
            },
        )
        if st.button(_tr("save"), key="save_mp", type="primary"):
            save_block(mp, ed_mp, "kabinet_data.marketplaces", "id",
                       ["name", "country", "currency", "is_active"])

# ------------------------------------------------------------------ пулы ---
with tab_pool:
    st.caption(_tr("pool_hint"))
    pools = q("SELECT id, name, comment FROM kabinet_data.pools ORDER BY name")
    mps = q("""
        SELECT id, code, country FROM kabinet_data.marketplaces
        WHERE is_active IS NOT FALSE ORDER BY code
    """)
    mp_label = {int(r.id): f"{r.code} ({r.country})" for _, r in mps.iterrows()}
    label_mp = {v: k for k, v in mp_label.items()}

    left, right = st.columns([1, 2])

    with left:
        st.markdown(f"**{_tr('pool_list')}**")
        sel_pool = None
        if pools.empty:
            st.info(_tr("pool_none"))
        else:
            sel_name = st.radio(" ", pools["name"].tolist(), key="pool_pick",
                                label_visibility="collapsed")
            sel_pool = int(pools.loc[pools["name"] == sel_name, "id"].iloc[0])

        with st.form("new_pool", clear_on_submit=True):
            st.markdown(f"**{_tr('pool_new')}**")
            nname = st.text_input(_tr("pool_name"))
            ncomment = st.text_input(_tr("pool_comment"))
            if st.form_submit_button(_tr("pool_create")):
                if not nname.strip():
                    st.error(_tr("pool_empty_name"))
                else:
                    try:
                        exec_sql([("""
                            INSERT INTO kabinet_data.pools (name, comment)
                            VALUES (%s, %s) ON CONFLICT (name) DO NOTHING
                        """, [nname.strip(), ncomment or None])])
                        st.cache_data.clear()
                        st.success(_tr("pool_created"))
                        st.rerun()
                    except Exception as e:
                        st.error(_tr("err").format(e=e))

    with right:
        if sel_pool:
            cur_cmt = pools.loc[pools["id"] == sel_pool, "comment"].iloc[0]
            c1, c2 = st.columns([3, 1])
            new_cmt = c1.text_input(_tr("pool_comment"), value=cur_cmt or "",
                                    key=f"pc_{sel_pool}")
            if c2.button(_tr("pool_save_cmt"), key=f"pr_{sel_pool}"):
                try:
                    exec_sql([("UPDATE kabinet_data.pools SET comment = %s WHERE id = %s",
                               [new_cmt or None, sel_pool])])
                    st.cache_data.clear()
                    st.success(_tr("saved").format(n=1))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))

            st.markdown(f"**{_tr('pool_members')}**")
            members = q(f"""
                SELECT marketplace_id FROM kabinet_data.pool_members
                WHERE pool_id = {sel_pool}
            """)
            cur_ids = set(members["marketplace_id"].astype(int)) if not members.empty else set()
            picked = st.multiselect(
                _tr("pool_select"), list(label_mp.keys()),
                default=[mp_label[i] for i in cur_ids if i in mp_label],
                key=f"pm_{sel_pool}")
            d1, d2 = st.columns(2)
            v_from = d1.date_input(_tr("pool_from"), value=date.today(), key=f"pf_{sel_pool}")
            v_to = d2.date_input(_tr("pool_to"), value=None, key=f"pt_{sel_pool}")

            if st.button(_tr("pool_save"), key=f"ps_{sel_pool}", type="primary"):
                picked_ids = [label_mp[p] for p in picked]
                busy = q(f"""
                    SELECT pm.marketplace_id
                    FROM kabinet_data.pool_members pm
                    WHERE pm.pool_id <> {sel_pool}
                      AND (pm.valid_to IS NULL OR pm.valid_to >= CURRENT_DATE)
                """)
                clash = [mp_label.get(int(r.marketplace_id), str(r.marketplace_id))
                         for _, r in busy.iterrows()
                         if int(r.marketplace_id) in picked_ids]
                if clash:
                    st.error(_tr("pool_conflict").format(mp=", ".join(sorted(set(clash)))))
                else:
                    try:
                        stmts = [("DELETE FROM kabinet_data.pool_members WHERE pool_id = %s",
                                  [sel_pool])]
                        for mid in picked_ids:
                            stmts.append((
                                "INSERT INTO kabinet_data.pool_members "
                                "(pool_id, marketplace_id, valid_from, valid_to) "
                                "VALUES (%s, %s, %s, %s)",
                                [sel_pool, mid, v_from, v_to or None]))
                        exec_sql(stmts)
                        st.cache_data.clear()
                        st.success(_tr("saved").format(n=len(picked_ids)))
                        st.rerun()
                    except Exception as e:
                        st.error(_tr("err").format(e=e))

            if st.button(_tr("pool_delete"), key=f"pd_{sel_pool}"):
                try:
                    exec_sql([
                        ("DELETE FROM kabinet_data.pool_members WHERE pool_id = %s", [sel_pool]),
                        ("DELETE FROM kabinet_data.pools WHERE id = %s", [sel_pool]),
                    ])
                    st.cache_data.clear()
                    st.success(_tr("pool_deleted"))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))

# ------------------------------------------------------------- нормативы ---
with tab_norm:
    st.caption(_tr("norm_hint"))
    st.info(_tr("norm_unused"))

    # SKU берём из coverage_summary: это ровно тот набор, к которому норматив
    # и применяется. Девяносто с небольшим штук — выбором из списка опечатку
    # не сделаешь, а свободным вводом норматив легко повесить на SKU, которого
    # нет, и он молча не сработает никогда.
    skus = q("""
        SELECT sku, max(product_name) AS product_name
        FROM kabinet_data.coverage_summary
        GROUP BY sku ORDER BY sku
    """)
    mps_n = q("""
        SELECT id, code, country FROM kabinet_data.marketplaces
        WHERE is_active IS NOT FALSE ORDER BY code
    """)
    pools_n = q("SELECT id, name FROM kabinet_data.pools ORDER BY name")

    mp_opts = {f"{r.code} ({r.country})": int(r.id) for _, r in mps_n.iterrows()}
    pool_opts = {r["name"]: int(r.id) for _, r in pools_n.iterrows()}
    sku_title = {r["sku"]: (f'{r["sku"]} — {r["product_name"]}'
                            if r["product_name"] else r["sku"])
                 for _, r in skus.iterrows()}

    with st.expander(_tr("norm_add"), expanded=True):
        # Без st.form намеренно: подсказка про текущее покрытие должна
        # обновляться сразу после выбора SKU и рынка, а форма перерисовку
        # придерживает до отправки.
        a1, a2, a3 = st.columns([2, 1, 2])

        manual = a1.checkbox(_tr("norm_manual"), key="norm_manual")
        if manual or skus.empty:
            sku_val = a1.text_input(_tr("norm_sku"), key="norm_sku_txt").strip()
        else:
            sku_val = a1.selectbox(_tr("norm_sku"), list(sku_title),
                                   format_func=lambda s: sku_title[s],
                                   key="norm_sku_sel")

        if not pool_opts:
            a2.caption(_tr("norm_no_pools"))
            is_mp = True
        else:
            is_mp = a2.selectbox(_tr("norm_target"),
                                 [_tr("norm_target_mp"), _tr("norm_target_pool")],
                                 key="norm_tgt") == _tr("norm_target_mp")

        opts = mp_opts if is_mp else pool_opts
        tgt_val = a3.selectbox(_tr("norm_target_val"), list(opts) or ["—"],
                               key="norm_tgt_val")

        # Чем норматив обосновать: что у этой пары с покрытием прямо сейчас
        if sku_val and is_mp and opts:
            _mp_code = tgt_val.split(" ")[0]
            cov = q1("""
                SELECT round(coverage_weeks::numeric, 1) AS ned, coverage_status
                FROM kabinet_data.coverage_summary
                WHERE sku = %s AND marketplace = %s
                ORDER BY calc_date DESC LIMIT 1
            """, (sku_val, _mp_code))
            if cov.empty or pd.isna(cov.iloc[0]["ned"]):
                st.caption(_tr("norm_now_none"))
            else:
                st.caption(_trf("norm_now", w=cov.iloc[0]["ned"],
                                st=cov.iloc[0]["coverage_status"]))

        b1, b2, b3 = st.columns(3)
        mn = b1.number_input(_tr("col_min"), 0, 999, 30, step=5, key="norm_mn")
        tg = b2.number_input(_tr("col_target"), 0, 999, 60, step=5, key="norm_tg")
        mx = b3.number_input(_tr("col_max"), 0, 999, 90, step=5, key="norm_mx")

        if st.button(_tr("norm_add"), type="primary", key="norm_add_btn"):
            if not sku_val:
                st.error(_tr("norm_empty"))
            elif not opts:
                st.error(_tr("norm_no_target"))
            elif not (mn <= tg <= mx):
                st.error(_tr("norm_order"))
            else:
                tid = opts[tgt_val]
                col = "marketplace_id" if is_mp else "pool_id"
                # Уникальность в БД — по тройке (marketplace_id, pool_id, sku),
                # а NULL в Postgres друг другу не равны: вторая строка с тем же
                # рынком и SKU при пустом пуле ограничение НЕ нарушит. Значит
                # дубли ловим здесь, и параметром, а не склейкой строки —
                # апостроф в артикуле иначе роняет запрос.
                dup = q1(f"SELECT 1 FROM kabinet_data.coverage_norms "
                         f"WHERE sku = %s AND {col} = %s LIMIT 1",
                         (sku_val, tid))
                if not dup.empty:
                    st.warning(_tr("norm_exists"))
                else:
                    try:
                        exec_sql([(f"""
                            INSERT INTO kabinet_data.coverage_norms
                                (sku, {col}, min_days, target_days, max_days)
                            VALUES (%s, %s, %s, %s, %s)
                        """, [sku_val, tid, int(mn), int(tg), int(mx)])])
                        st.cache_data.clear()
                        st.success(_tr("norm_added"))
                        st.rerun()
                    except Exception as e:
                        st.error(_trf("err", e=e))

    st.markdown(f"**{_tr('norm_list')}**")
    norms = q("""
        SELECT n.id, n.sku, c.product_name,
               m.code AS marketplace,
               p.name AS pool,
               n.min_days, n.target_days, n.max_days
        FROM kabinet_data.coverage_norms n
        LEFT JOIN kabinet_data.marketplaces m ON m.id = n.marketplace_id
        LEFT JOIN kabinet_data.pools p        ON p.id = n.pool_id
        LEFT JOIN LATERAL (
            SELECT max(product_name) AS product_name
            FROM kabinet_data.coverage_summary s WHERE s.sku = n.sku
        ) c ON true
        ORDER BY n.sku, m.code NULLS LAST, p.name NULLS LAST
    """)
    if norms.empty:
        st.info(_tr("norm_none"))
    else:
        view_n = norms.copy()
        view_n["__del"] = False
        ed_n = st.data_editor(
            view_n, key="ed_norm", use_container_width=True, height=420,
            hide_index=True, num_rows="fixed",
            disabled=["id", "sku", "product_name", "marketplace", "pool"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "sku": st.column_config.TextColumn(_tr("norm_sku"), width="small"),
                "product_name": st.column_config.TextColumn(_tr("col_product"), width="large"),
                "marketplace": st.column_config.TextColumn(_tr("col_mp"), width="small"),
                "pool": st.column_config.TextColumn(_tr("col_pool"), width="small"),
                "min_days": st.column_config.NumberColumn(_tr("col_min"), step=5),
                "target_days": st.column_config.NumberColumn(_tr("col_target"), step=5),
                "max_days": st.column_config.NumberColumn(_tr("col_max"), step=5),
                "__del": st.column_config.CheckboxColumn(_tr("del_col"), width="small"),
            },
        )
        s1, s2 = st.columns(2)
        if s1.button(_tr("save"), key="save_norm", type="primary"):
            bad = ed_n[~((ed_n["min_days"] <= ed_n["target_days"]) &
                         (ed_n["target_days"] <= ed_n["max_days"]))]
            if not bad.empty:
                st.error(_tr("norm_order"))
            else:
                save_block(norms.drop(columns=["product_name"]),
                           ed_n.drop(columns=["__del", "product_name"]),
                           "kabinet_data.coverage_norms", "id",
                           ["min_days", "target_days", "max_days"])
        if s2.button(_tr("delete_sel"), key="del_norm"):
            ids = [int(i) for i in ed_n.loc[ed_n["__del"], "id"].tolist()]
            if not ids:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql([("DELETE FROM kabinet_data.coverage_norms WHERE id = ANY(%s)",
                               [ids])])
                    st.cache_data.clear()
                    st.success(_trf("deleted", n=len(ids)))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err", e=e))

# ---------------------------------------------------------- ассортимент ---
# ------------------------------------------------------------------ алерты ---
with tab_alerts:
    st.caption(_tr("al_hint"))
    st.caption(_tr("al_hint2"))

    # Справочник заполняет джоба синка (новые типы из журнала — пустой строкой) и этот
    # экран. Список ClickUp — единственный включатель: пусто значит «не отправляем».
    IT = "kabinet_data.incident_types"
    if not has_table(IT):
        st.info(_tr("no_data"))
    else:
        types = q(f"""
            SELECT t.incident_type, t.title, t.description, t.clickup_list_id, t.clickup_list_name,
                   t.mode, t.watch_close, t.risk, t.due_days, t.assignee_group_name, t.assignee_group_id,
                   t.enabled_since, t.last_check_note, t.last_check_at, t.note,
                   COALESCE(o.n_open, 0)  AS n_open,
                   COALESCE(c.n_tasks, 0) AS n_tasks
            FROM {IT} t
            LEFT JOIN (SELECT incident_type, count(*) AS n_open FROM kabinet_data.incidents
                       WHERE status IN ('open', 'acknowledged') GROUP BY 1) o USING (incident_type)
            LEFT JOIN (SELECT incident_type, count(*) AS n_tasks FROM kabinet_data.clickup_tasks
                       WHERE closed_at IS NULL GROUP BY 1) c USING (incident_type)
            ORDER BY (t.clickup_list_id IS NULL), t.incident_type
        """)
        c1, c2 = st.columns([1.2, 2])
        only_routed = c1.toggle(_tr("al_only_routed"), value=False, key="al_routed")
        search = c2.text_input(_tr("al_search"), key="al_search").strip()
        view = types.copy()
        if only_routed:
            view = view[view["clickup_list_id"].notna()]
        if search:
            view = view[view["incident_type"].str.contains(search, case=False, na=False)
                        | view["title"].fillna("").str.contains(search, case=False, na=False)]
        st.caption(_trf("al_summary", total=len(types), routed=int(types["clickup_list_id"].notna().sum()),
                        open=int(types["n_open"].sum())))

        _mode_lbl = {"task": _tr("al_mode_task"), "digest": _tr("al_mode_digest")}
        _mode_code = {v: k for k, v in _mode_lbl.items()}
        RISKS = ["", "Low", "Medium", "High", "Critical"]
        view["mode"] = view["mode"].map(_mode_lbl)
        view["risk"] = view["risk"].fillna("")
        # id списка — целое, а не float: иначе 901222107497 в редакторе превратится в 9.01e11
        view["clickup_list_id"] = view["clickup_list_id"].astype("Int64")
        view["enabled_since"] = pd.to_datetime(view["enabled_since"])
        for c in ("title", "description", "clickup_list_name", "assignee_group_name", "assignee_group_id",
                  "last_check_note", "note"):
            view[c] = view[c].fillna("")

        cols = ["incident_type", "title", "n_open", "clickup_list_id", "mode", "watch_close", "risk",
                "due_days", "assignee_group_name", "assignee_group_id", "enabled_since", "n_tasks",
                "clickup_list_name", "last_check_note", "last_check_at", "description", "note"]
        ed = st.data_editor(
            view[cols], key="ed_alerts", use_container_width=True, height=560, hide_index=True,
            num_rows="fixed",
            disabled=["incident_type", "n_open", "n_tasks", "clickup_list_name", "last_check_note", "last_check_at"],
            column_config={
                "incident_type": st.column_config.TextColumn(_tr("al_col_type"), width="medium"),
                "title": st.column_config.TextColumn(_tr("al_col_title"), width="medium"),
                "n_open": st.column_config.NumberColumn(_tr("al_col_open"), width="small"),
                "clickup_list_id": st.column_config.NumberColumn(_tr("al_col_list"), width="medium",
                                                                 format="%d", step=1),
                "mode": st.column_config.SelectboxColumn(_tr("al_col_mode"), options=list(_mode_lbl.values()),
                                                         width="small"),
                "watch_close": st.column_config.CheckboxColumn(_tr("al_col_watch"), width="small"),
                "risk": st.column_config.SelectboxColumn(_tr("al_col_risk"), options=RISKS, width="small"),
                "due_days": st.column_config.NumberColumn(_tr("al_col_due"), width="small", min_value=0, step=1),
                "assignee_group_name": st.column_config.TextColumn(_tr("al_col_role"), width="small"),
                "assignee_group_id": st.column_config.TextColumn(_tr("al_col_role_id"), width="small"),
                "enabled_since": st.column_config.DateColumn(_tr("al_col_since"), width="small",
                                                             format="DD.MM.YYYY"),
                "n_tasks": st.column_config.NumberColumn(_tr("al_col_tasks"), width="small"),
                "clickup_list_name": st.column_config.TextColumn(_tr("al_col_list_name"), width="medium"),
                "last_check_note": st.column_config.TextColumn(_tr("al_col_check"), width="large"),
                "last_check_at": st.column_config.DatetimeColumn(_tr("al_col_checked"), width="small",
                                                                 format="DD.MM HH:mm"),
                "description": st.column_config.TextColumn(_tr("al_col_descr"), width="large"),
                "note": st.column_config.TextColumn(_tr("col_note"), width="medium"),
            },
        )
        st.caption(_tr("al_sync_hint"))
        if st.button(_tr("save"), key="save_alerts", type="primary"):
            before = view.set_index("incident_type")
            stmts = []
            for _, r in ed.iterrows():
                it = r["incident_type"]
                new = {
                    "title": _py(r["title"]), "description": _py(r["description"]),
                    "clickup_list_id": None if pd.isna(r["clickup_list_id"]) else int(r["clickup_list_id"]),
                    "mode": _mode_code.get(r["mode"], "task"),
                    "watch_close": bool(r["watch_close"]),
                    "risk": _py(r["risk"]), "due_days": _int0(r["due_days"]),
                    "assignee_group_name": _py(r["assignee_group_name"]),
                    "assignee_group_id": _py(r["assignee_group_id"]),
                    "enabled_since": _py(r["enabled_since"]), "note": _py(r["note"]),
                }
                old = {
                    "title": _py(before.at[it, "title"]), "description": _py(before.at[it, "description"]),
                    "clickup_list_id": None if pd.isna(before.at[it, "clickup_list_id"]) else int(before.at[it, "clickup_list_id"]),
                    "mode": _mode_code.get(before.at[it, "mode"], "task"),
                    "watch_close": bool(before.at[it, "watch_close"]),
                    "risk": _py(before.at[it, "risk"]), "due_days": _int0(before.at[it, "due_days"]),
                    "assignee_group_name": _py(before.at[it, "assignee_group_name"]),
                    "assignee_group_id": _py(before.at[it, "assignee_group_id"]),
                    "enabled_since": _py(before.at[it, "enabled_since"]), "note": _py(before.at[it, "note"]),
                }
                changed = {k: v for k, v in new.items() if not _same(v, old[k])}
                if not changed:
                    continue
                # список появился впервые — задачи только с сегодняшнего дня, висящее не переносим
                if changed.get("clickup_list_id") and old["clickup_list_id"] is None and not new["enabled_since"]:
                    changed["enabled_since"] = date.today()
                # список сняли — путь и результат проверки больше не про этот тип
                if "clickup_list_id" in changed and changed["clickup_list_id"] is None:
                    changed["clickup_list_name"] = None; changed["last_check_note"] = None
                sets = ", ".join(f"{k} = %s" for k in changed)
                stmts.append((f"UPDATE {IT} SET {sets}, updated_by = 'kabinet', updated_at = now() "
                              f"WHERE incident_type = %s", list(changed.values()) + [it]))
            if not stmts:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql(stmts)
                    st.cache_data.clear()
                    st.success(_trf("saved", n=len(stmts)))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err", e=e))


# --------------------------------------------------------------------- SKU ---
with tab_sku:
    st.caption(_tr("sku_hint"))
    SM = "kabinet_data.sku_master"
    if not has_table(SM):
        st.info(_tr("no_data"))
    else:
        sm = q(f"""
            SELECT m.sku, m.sku_type, m.name, m.ean, m.supplier_code, m.intro_date, m.intro_source, m.exit_date,
                   m.height_mm, m.width_mm, m.length_mm, m.volume_m3, m.gross_weight_kg, m.weight_source,
                   m.dims_source, m.ean_source, m.type_source,
                   array_to_string(ARRAY(SELECT jsonb_array_elements_text(m.restrictions)), ', ') AS restrictions,
                   m.passport_ref, array_to_string(m.in_scope, ', ') AS in_scope,
                   c.issues, c.n_err
            FROM {SM} m
            LEFT JOIN (SELECT sku, string_agg(check_code || CASE severity WHEN 'error' THEN ' ⛔' WHEN 'warning' THEN ' ⚠' ELSE '' END,
                                              ', ' ORDER BY severity, check_code) AS issues,
                              count(*) FILTER (WHERE severity = 'error') AS n_err
                       FROM kabinet_data.sku_checks GROUP BY sku) c USING (sku)
            ORDER BY (c.n_err IS NULL), c.n_err DESC, m.sku
        """)
        _types = {"base": _tr("sku_t_base"), "composite": _tr("sku_t_composite")}
        f1, f2, f3, f4 = st.columns([1.6, 1, 1.4, 1])
        search = f1.text_input(_tr("sku_search"), key="sku_search").strip()
        type_sel = f2.multiselect(_tr("sku_type_f"), ["base", "composite", "none"],
                                  format_func=lambda x: _types.get(x, _tr("sku_t_none")), key="sku_type_f")
        _codes = sorted({c.split(" ")[0] for v in sm["issues"].dropna() for c in v.split(", ")})
        check_sel = f3.multiselect(_tr("sku_check_f"), _codes, key="sku_check_f")
        only_issues = f4.toggle(_tr("sku_only_issues"), value=False, key="sku_only_issues")

        view = sm.copy()
        if search:
            view = view[view["sku"].str.contains(search, case=False, na=False)
                        | view["name"].fillna("").str.contains(search, case=False, na=False)]
        if type_sel:
            view = view[view["sku_type"].fillna("none").isin(type_sel)]
        if check_sel:
            view = view[view["issues"].fillna("").apply(lambda v: any(c in v for c in check_sel))]
        if only_issues:
            view = view[view["issues"].notna()]
        st.caption(_trf("sku_summary", total=len(sm), base=int((sm["sku_type"] == "base").sum()),
                        comp=int((sm["sku_type"] == "composite").sum()), none=int(sm["sku_type"].isna().sum()),
                        err=int((sm["n_err"].fillna(0) > 0).sum())))

        # тип показываем подписью; дату ввода-оценку помечаем в отдельной колонке источников
        view["sku_type"] = view["sku_type"].map(_types).fillna(_tr("sku_t_none"))
        view["sources"] = [", ".join(x for x in (
            f"{_tr('sku_col_intro').lower()}: {_tr('sku_intro_estimate')}" if str(r.intro_source or "").startswith("estimate") else "",
            f"{_tr('sku_col_weight').split(',')[0].lower()}: {r.weight_source}" if r.weight_source else "",
            f"{_tr('sku_col_h').split(',')[0].lower()}: {r.dims_source}" if r.dims_source else "") if x)
            for r in view.itertuples()]
        for c in ("ean", "supplier_code", "restrictions", "passport_ref", "issues", "in_scope", "name"):
            view[c] = view[c].fillna("")
        view["intro_date"] = pd.to_datetime(view["intro_date"]); view["exit_date"] = pd.to_datetime(view["exit_date"])
        cols = ["sku", "sku_type", "name", "issues", "ean", "intro_date", "exit_date", "height_mm", "width_mm", "length_mm",
                "volume_m3", "gross_weight_kg", "supplier_code", "restrictions", "passport_ref", "in_scope", "sources"]
        ed = st.data_editor(
            view[cols], key="ed_sku", use_container_width=True, height=560, hide_index=True, num_rows="fixed",
            disabled=["sku", "name", "issues", "volume_m3", "in_scope", "sources"],
            column_config={
                "sku": st.column_config.TextColumn(_tr("sku_col_sku"), width="small"),
                "sku_type": st.column_config.SelectboxColumn(_tr("sku_col_type"), options=list(_types.values()), width="small"),
                "name": st.column_config.TextColumn(_tr("sku_col_name"), width="large"),
                "issues": st.column_config.TextColumn(_tr("sku_col_issues"), width="medium"),
                "ean": st.column_config.TextColumn(_tr("sku_col_ean"), width="small"),
                "intro_date": st.column_config.DateColumn(_tr("sku_col_intro"), format="DD.MM.YYYY", width="small"),
                "exit_date": st.column_config.DateColumn(_tr("sku_col_exit"), format="DD.MM.YYYY", width="small"),
                "height_mm": st.column_config.NumberColumn(_tr("sku_col_h"), format="%d", step=1, width="small"),
                "width_mm": st.column_config.NumberColumn(_tr("sku_col_w"), format="%d", step=1, width="small"),
                "length_mm": st.column_config.NumberColumn(_tr("sku_col_l"), format="%d", step=1, width="small"),
                "volume_m3": st.column_config.NumberColumn(_tr("sku_col_vol"), format="%.4f", width="small"),
                "gross_weight_kg": st.column_config.NumberColumn(_tr("sku_col_weight"), format="%.3f", step=0.001, width="small"),
                "supplier_code": st.column_config.TextColumn(_tr("sku_col_supplier"), width="small"),
                "restrictions": st.column_config.TextColumn(_tr("sku_col_restr"), width="small", help=_tr("sku_restr_help")),
                "passport_ref": st.column_config.TextColumn(_tr("sku_col_passport"), width="small"),
                "in_scope": st.column_config.TextColumn(_tr("sku_col_scope"), width="small"),
                "sources": st.column_config.TextColumn(_tr("sku_col_src"), width="medium"),
            },
        )
        if st.button(_tr("save"), key="save_sku", type="primary"):
            _code_of = {v: k for k, v in _types.items()}
            before = view.set_index("sku")
            stmts, n_fields = [], 0
            MANUAL = {"sku_type": "type_source", "ean": "ean_source", "intro_date": "intro_source",
                      "exit_date": "exit_source", "gross_weight_kg": "weight_source"}
            for _, r in ed.iterrows():
                sku = r["sku"]; sets, params = [], []
                for f in ("sku_type", "ean", "intro_date", "exit_date", "gross_weight_kg", "supplier_code", "passport_ref"):
                    new_v, old_v = _py(r[f]), _py(before.at[sku, f])
                    if f == "sku_type":
                        new_v, old_v = _code_of.get(new_v), _code_of.get(old_v)
                    if _same(new_v, old_v):
                        continue
                    sets.append(f"{f} = %s"); params.append(new_v)
                    if f in MANUAL:
                        sets.append(f"{MANUAL[f]} = 'manual'")
                    stmts.append(("INSERT INTO kabinet_data.sku_change_log (sku, field, old_value, new_value, source, actor) "
                                  "VALUES (%s, %s, %s, %s, 'manual', 'kabinet')", (sku, f, str(old_v), str(new_v))))
                    n_fields += 1
                dims_new = tuple(_py(r[c]) for c in ("height_mm", "width_mm", "length_mm"))
                dims_old = tuple(_py(before.at[sku, c]) for c in ("height_mm", "width_mm", "length_mm"))
                if dims_new != dims_old:
                    sets += ["height_mm = %s", "width_mm = %s", "length_mm = %s", "dims_source = 'manual'"]
                    params += [None if v is None else int(v) for v in dims_new]
                    if all(dims_new):
                        sets.append("volume_m3 = %s"); params.append(round(dims_new[0] * dims_new[1] * dims_new[2] / 1e9, 6))
                    n_fields += 1
                restr_new = [x.strip() for x in str(r["restrictions"] or "").split(",") if x.strip()]
                restr_old = [x.strip() for x in str(before.at[sku, "restrictions"] or "").split(",") if x.strip()]
                if restr_new != restr_old:
                    sets.append("restrictions = %s::jsonb"); params.append(json.dumps(restr_new)); n_fields += 1
                if sets:
                    stmts.append((f"UPDATE {SM} SET {', '.join(sets)}, updated_at = now(), updated_by = 'kabinet' WHERE sku = %s",
                                  params + [sku]))
            if not stmts:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql(stmts)
                    st.cache_data.clear()
                    st.success(_trf("sku_saved_manual", n=n_fields))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err", e=e))

        # состав выбранного набора
        _kits = sm.loc[sm["sku_type"] == "composite", "sku"].tolist()
        if _kits:
            kit = st.selectbox(_tr("sku_comp_pick"), _kits, key="sku_kit")
            comp = q1("""SELECT c.base_sku, c.quantity, m.name, m.gross_weight_kg, m.volume_m3
                         FROM kabinet_data.sku_composition c LEFT JOIN kabinet_data.sku_master m ON m.sku = c.base_sku
                         WHERE c.composite_sku = %s ORDER BY c.base_sku""", (kit,))
            if comp.empty:
                st.caption(_tr("sku_comp_none"))
            else:
                st.dataframe(comp, hide_index=True, use_container_width=True, column_config={
                    "base_sku": st.column_config.TextColumn(_tr("sku_comp_col_base")),
                    "quantity": st.column_config.NumberColumn(_tr("sku_comp_col_qty"), format="%d"),
                    "name": st.column_config.TextColumn(_tr("sku_comp_col_name"), width="large"),
                    "gross_weight_kg": st.column_config.NumberColumn(_tr("sku_col_weight"), format="%.3f"),
                    "volume_m3": st.column_config.NumberColumn(_tr("sku_col_vol"), format="%.4f"),
                })
                st.caption(_tr("sku_comp_note"))


# -------------------------------------------------------------------- PeID ---
with tab_peid:
    st.caption(_tr("pe_hint"))
    PE = "kabinet_data.product_entities"
    if not has_table(PE):
        st.info(_tr("no_data"))
    else:
        pe = q(f"""
            SELECT e.id, m.code AS mp, e.peid, e.title, e.url, e.is_parent, e.is_active, e.active_source,
                   e.variation_group_id, g.name AS group_name,
                   array_to_string(e.seen_in, ', ') AS seen, e.last_seen, e.comment,
                   l.skus, l.statuses, c.issues, c.n_err
            FROM {PE} e
            JOIN kabinet_data.marketplaces_new m ON m.id = e.marketplace_id
            LEFT JOIN kabinet_data.variation_groups g ON g.id = e.variation_group_id
            LEFT JOIN (SELECT marketplace_id, peid, string_agg(DISTINCT sku, ', ') AS skus,
                              string_agg(DISTINCT listing_status, ', ') AS statuses
                       FROM kabinet_data.product_entity_listings GROUP BY 1, 2) l USING (marketplace_id, peid)
            LEFT JOIN (SELECT marketplace_id, peid,
                              string_agg(check_code || CASE severity WHEN 'error' THEN ' ⛔' WHEN 'warning' THEN ' ⚠' ELSE '' END,
                                         ', ' ORDER BY severity, check_code) AS issues,
                              count(*) FILTER (WHERE severity = 'error') AS n_err
                       FROM kabinet_data.product_entity_checks GROUP BY 1, 2) c USING (marketplace_id, peid)
            ORDER BY m.code, (c.n_err IS NULL), c.n_err DESC, e.peid
        """) if has_table("kabinet_data.variation_groups") else q(f"""
            SELECT e.id, m.code AS mp, e.peid, e.title, e.url, e.is_parent, e.is_active, e.active_source,
                   e.variation_group_id, NULL::text AS group_name,
                   array_to_string(e.seen_in, ', ') AS seen, e.last_seen, e.comment,
                   l.skus, l.statuses, c.issues, c.n_err
            FROM {PE} e
            JOIN kabinet_data.marketplaces_new m ON m.id = e.marketplace_id
            LEFT JOIN (SELECT marketplace_id, peid, string_agg(DISTINCT sku, ', ') AS skus,
                              string_agg(DISTINCT listing_status, ', ') AS statuses
                       FROM kabinet_data.product_entity_listings GROUP BY 1, 2) l USING (marketplace_id, peid)
            LEFT JOIN (SELECT marketplace_id, peid,
                              string_agg(check_code || CASE severity WHEN 'error' THEN ' ⛔' WHEN 'warning' THEN ' ⚠' ELSE '' END,
                                         ', ' ORDER BY severity, check_code) AS issues,
                              count(*) FILTER (WHERE severity = 'error') AS n_err
                       FROM kabinet_data.product_entity_checks GROUP BY 1, 2) c USING (marketplace_id, peid)
            ORDER BY m.code, (c.n_err IS NULL), c.n_err DESC, e.peid
        """)
        f1, f2, f3, f4, f5 = st.columns([1.2, 1.8, 1, 1, 1])
        _mps = sorted(pe["mp"].unique())
        mp_sel = f1.multiselect(_tr("pe_mp"), _mps, default=[m for m in ("AMZ-ES",) if m in _mps], key="pe_mp")
        search = f2.text_input(_tr("pe_search"), key="pe_search").strip()
        only_issues = f3.toggle(_tr("pe_only_issues"), value=False, key="pe_issues")
        hide_parents = f4.toggle(_tr("pe_hide_parents"), value=False, key="pe_parents")
        hide_inactive = f5.toggle(_tr("pe_hide_inactive"), value=True, key="pe_inactive")
        view = pe.copy()
        if mp_sel:
            view = view[view["mp"].isin(mp_sel)]
        if search:
            m = (view["peid"].str.contains(search, case=False, na=False)
                 | view["title"].fillna("").str.contains(search, case=False, na=False)
                 | view["skus"].fillna("").str.contains(search, case=False, na=False))
            view = view[m]
        if only_issues:
            view = view[view["issues"].notna()]
        if hide_parents:
            view = view[~view["is_parent"]]
        if hide_inactive:
            view = view[view["is_active"]]
        st.caption(_trf("pe_summary", total=len(pe), active=int(pe["is_active"].sum()), parents=int(pe["is_parent"].sum()),
                        err=int((pe["n_err"].fillna(0) > 0).sum())))
        for c in ("title", "skus", "statuses", "group_name", "issues", "comment", "seen"):
            view[c] = view[c].fillna("")
        view["last_seen"] = pd.to_datetime(view["last_seen"])
        cols = ["mp", "peid", "title", "skus", "statuses", "is_parent", "group_name", "is_active", "issues", "last_seen", "seen", "comment", "url"]
        # группа правится только при одном выбранном маркетплейсе: варианты списка — группы этого рынка (ТЗ 006 §8)
        _one_mp = mp_sel[0] if len(mp_sel) == 1 else None
        _grp_opts = []
        if _one_mp and has_table("kabinet_data.variation_groups"):
            _g = q1("""SELECT g.id, g.name FROM kabinet_data.variation_groups g JOIN kabinet_data.marketplaces_new m ON m.id = g.marketplace_id
                       WHERE m.code = %s AND g.is_active ORDER BY g.name""", (_one_mp,))
            _grp_opts = _g["name"].tolist(); _grp_id = dict(zip(_g["name"], _g["id"]))
            st.caption(_tr("pe_group_edit_hint"))
        _group_col = (st.column_config.SelectboxColumn(_tr("pe_col_group"), options=[""] + _grp_opts, width="medium") if _one_mp
                      else st.column_config.TextColumn(_tr("pe_col_group"), width="medium"))
        ed = st.data_editor(
            view[cols], key="ed_peid", use_container_width=True, height=560, hide_index=True, num_rows="fixed",
            disabled=["mp", "peid", "title", "skus", "statuses", "is_parent", "issues", "last_seen", "seen", "url"] + ([] if _one_mp else ["group_name"]),
            column_config={
                "mp": st.column_config.TextColumn(_tr("pe_col_mp"), width="small"),
                "peid": st.column_config.TextColumn(_tr("pe_col_peid"), width="small"),
                "title": st.column_config.TextColumn(_tr("pe_col_title"), width="large"),
                "skus": st.column_config.TextColumn(_tr("pe_col_skus"), width="small"),
                "statuses": st.column_config.TextColumn(_tr("pe_col_status"), width="small"),
                "is_parent": st.column_config.CheckboxColumn(_tr("pe_col_parent"), width="small"),
                "group_name": _group_col,
                "is_active": st.column_config.CheckboxColumn(_tr("pe_col_active"), width="small"),
                "issues": st.column_config.TextColumn(_tr("pe_col_issues"), width="medium"),
                "last_seen": st.column_config.DateColumn(_tr("pe_col_last"), format="DD.MM.YYYY", width="small"),
                "seen": st.column_config.TextColumn(_tr("pe_col_seen"), width="small"),
                "comment": st.column_config.TextColumn(_tr("pe_col_comment"), width="medium"),
                "url": st.column_config.LinkColumn("URL", width="small", display_text="↗"),
            },
        )
        if st.button(_tr("save"), key="save_peid", type="primary"):
            before = view.set_index(["mp", "peid"])
            ids = view.set_index(["mp", "peid"])["id"]
            stmts = []
            for _, r in ed.iterrows():
                key = (r["mp"], r["peid"]); sets, params = [], []
                if bool(r["is_active"]) != bool(before.at[key, "is_active"]):
                    sets += ["is_active = %s", "active_source = 'manual'"]; params.append(bool(r["is_active"]))
                if (r["comment"] or "") != (before.at[key, "comment"] or ""):
                    sets.append("comment = %s"); params.append(r["comment"] or None)
                if _one_mp and (r["group_name"] or "") != (before.at[key, "group_name"] or ""):
                    new_gid = _grp_id.get(r["group_name"]) if r["group_name"] else None
                    sets += ["variation_group_id = %s", "group_source = 'manual'"]; params.append(new_gid)
                    stmts.append(("INSERT INTO kabinet_data.product_entity_change_log (marketplace_id, peid, field, old_value, new_value, source, actor) "
                                  "SELECT marketplace_id, peid, 'variation_group_id', %s, %s, 'manual', 'kabinet' FROM kabinet_data.product_entities WHERE id = %s",
                                  (before.at[key, "group_name"] or None, r["group_name"] or None, int(ids.at[key]))))
                if sets:
                    stmts.append((f"UPDATE {PE} SET {', '.join(sets)}, updated_at = now(), updated_by = 'kabinet' WHERE id = %s",
                                  params + [int(ids.at[key])]))
            if not stmts:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql(stmts)
                    st.cache_data.clear()
                    st.success(_trf("pe_saved", n=len(stmts)))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err", e=e))


# ---------------------------------------------------------------- вариации ---
with tab_vg:
    st.caption(_tr("vg_hint"))
    VG = "kabinet_data.variation_groups"
    if not has_table(VG):
        st.info(_tr("no_data"))
    else:
        vg = q(f"""
            SELECT g.id, m.code AS mp, g.name, g.name_source, g.group_peid, g.url, g.is_family, g.is_active, g.source, g.comment,
                   COALESCE(e.members, 0) AS members, c.issues
            FROM {VG} g
            JOIN kabinet_data.marketplaces_new m ON m.id = g.marketplace_id
            LEFT JOIN (SELECT variation_group_id, count(*) AS members FROM kabinet_data.product_entities
                       WHERE variation_group_id IS NOT NULL GROUP BY 1) e ON e.variation_group_id = g.id
            LEFT JOIN (SELECT group_id, string_agg(check_code || CASE severity WHEN 'error' THEN ' ⛔' WHEN 'warning' THEN ' ⚠' ELSE '' END,
                                                    ', ' ORDER BY severity, check_code) AS issues
                       FROM kabinet_data.variation_group_checks GROUP BY 1) c ON c.group_id = g.id
            ORDER BY m.code, g.name
        """)
        g1, g2, g3 = st.columns([1.2, 2, 1])
        _mps = sorted(vg["mp"].unique())
        mp_sel = g1.multiselect(_tr("vg_col_mp"), _mps, default=[m for m in ("AMZ-ES",) if m in _mps], key="vg_mp")
        search = g2.text_input(_tr("pe_search"), key="vg_search").strip()
        only_issues = g3.toggle(_tr("pe_only_issues"), value=False, key="vg_issues")
        view = vg.copy()
        if mp_sel:
            view = view[view["mp"].isin(mp_sel)]
        if search:
            view = view[view["name"].str.contains(search, case=False, na=False) | view["group_peid"].fillna("").str.contains(search, case=False, na=False)]
        if only_issues:
            view = view[view["issues"].notna()]
        st.caption(_trf("vg_summary", total=len(vg), active=int(vg["is_active"].sum()), members=int(vg["members"].sum()),
                        issues=int(vg["issues"].notna().sum())))
        for c in ("group_peid", "comment", "issues", "url"):
            view[c] = view[c].fillna("")
        cols = ["mp", "name", "group_peid", "members", "is_family", "is_active", "issues", "source", "comment", "url"]
        ed = st.data_editor(
            view[cols], key="ed_vg", use_container_width=True, height=480, hide_index=True, num_rows="fixed",
            disabled=["mp", "group_peid", "members", "issues", "source", "url"],
            column_config={
                "mp": st.column_config.TextColumn(_tr("vg_col_mp"), width="small"),
                "name": st.column_config.TextColumn(_tr("vg_col_name"), width="large"),
                "group_peid": st.column_config.TextColumn(_tr("vg_col_peid"), width="small"),
                "members": st.column_config.NumberColumn(_tr("vg_col_members"), format="%d", width="small"),
                "is_family": st.column_config.CheckboxColumn(_tr("vg_col_family"), width="small"),
                "is_active": st.column_config.CheckboxColumn(_tr("vg_col_active"), width="small"),
                "issues": st.column_config.TextColumn(_tr("vg_col_issues"), width="medium"),
                "source": st.column_config.TextColumn(_tr("vg_col_src"), width="small"),
                "comment": st.column_config.TextColumn(_tr("vg_col_comment"), width="medium"),
                "url": st.column_config.LinkColumn("URL", width="small", display_text="↗"),
            },
        )
        if st.button(_tr("save"), key="save_vg", type="primary"):
            before = view.set_index(["mp", "group_peid"]); ids = before["id"]
            stmts = []
            for _, r in ed.iterrows():
                key = (r["mp"], r["group_peid"]); sets, params = [], []
                if (r["name"] or "") != (before.at[key, "name"] or ""):
                    sets += ["name = %s", "name_source = 'manual'"]; params.append(r["name"])
                if bool(r["is_family"]) != bool(before.at[key, "is_family"]):
                    sets.append("is_family = %s"); params.append(bool(r["is_family"]))
                if bool(r["is_active"]) != bool(before.at[key, "is_active"]):
                    sets += ["is_active = %s", "active_source = 'manual'"]; params.append(bool(r["is_active"]))
                if (r["comment"] or "") != (before.at[key, "comment"] or ""):
                    sets.append("comment = %s"); params.append(r["comment"] or None)
                if sets:
                    stmts.append((f"UPDATE {VG} SET {', '.join(sets)}, updated_at = now(), updated_by = 'kabinet' WHERE id = %s",
                                  params + [int(ids.at[key])]))
            if not stmts:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql(stmts)
                    st.cache_data.clear()
                    st.success(_trf("vg_saved", n=len(stmts)))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err", e=e))
        if not view.empty:
            pick = st.selectbox(_tr("vg_members_pick"), view["name"].tolist(), key="vg_pick")
            gid = int(view.loc[view["name"] == pick, "id"].iloc[0])
            mem = q1("""SELECT e.peid, e.title, l.skus, e.is_active, e.group_source
                        FROM kabinet_data.product_entities e
                        LEFT JOIN (SELECT marketplace_id, peid, string_agg(DISTINCT sku, ', ') AS skus
                                   FROM kabinet_data.product_entity_listings GROUP BY 1, 2) l USING (marketplace_id, peid)
                        WHERE e.variation_group_id = %s ORDER BY e.peid""", (gid,))
            if mem.empty:
                st.caption(_tr("vg_members_none"))
            else:
                st.dataframe(mem, hide_index=True, use_container_width=True, column_config={
                    "peid": st.column_config.TextColumn(_tr("pe_col_peid")), "title": st.column_config.TextColumn(_tr("pe_col_title"), width="large"),
                    "skus": st.column_config.TextColumn(_tr("pe_col_skus")), "is_active": st.column_config.CheckboxColumn(_tr("pe_col_active")),
                    "group_source": st.column_config.TextColumn(_tr("vg_col_src"))})


# ----------------------------------------------------------------- матрица ---
with tab_matrix:
    st.caption(_tr("am_hint"))
    AA, AR = "kabinet_data.assortment_admissions", "kabinet_data.assortment_representations"
    if not has_table(AA):
        st.info(_tr("no_data"))
    else:
        am = q(f"""
            SELECT a.id, a.level, a.platform, m.code AS mp, a.marketplace_id, a.sku, s.name, s.sku_type, a.added_on, a.removed_on,
                   a.in_listing, a.complementary, a.reason, a.source, c.issues, c.n_err
            FROM {AA} a
            LEFT JOIN kabinet_data.marketplaces_new m ON m.id = a.marketplace_id
            LEFT JOIN kabinet_data.sku_master s ON s.sku = a.sku
            LEFT JOIN (SELECT record_id, string_agg(check_code || CASE severity WHEN 'error' THEN ' ⛔' WHEN 'warning' THEN ' ⚠' ELSE '' END,
                                                      ', ' ORDER BY severity, check_code) AS issues,
                              count(*) FILTER (WHERE severity = 'error') AS n_err
                       FROM kabinet_data.assortment_checks WHERE register = 'admission' GROUP BY 1) c ON c.record_id = a.id
            ORDER BY a.platform, m.code NULLS FIRST, a.sku, a.added_on DESC
        """)
        mps_all = q("SELECT id, code, platform_short FROM kabinet_data.marketplaces_new WHERE is_active IS NOT FALSE ORDER BY code")
        skus_all = q("SELECT sku, sku_type, intro_date, exit_date, restrictions FROM kabinet_data.sku_master ORDER BY sku")

        f1, f2, f3, f4, f5, f6 = st.columns([1, 1, 1.2, 1.4, 1, 1])
        _lvl = {"marketplace": _tr("am_level_marketplace"), "platform": _tr("am_level_platform")}
        lvl_sel = f1.selectbox(_tr("am_level"), list(_lvl), format_func=_lvl.get, key="am_level")
        pl_sel = f2.multiselect(_tr("am_platform"), sorted(am["platform"].unique()), key="am_platform")
        mp_sel = f3.multiselect(_tr("am_mp"), sorted(am["mp"].dropna().unique()), key="am_mp")
        search = f4.text_input(_tr("am_search"), key="am_search").strip()
        show_hist = f5.toggle(_tr("am_show_history"), value=False, key="am_hist")
        only_issues = f6.toggle(_tr("am_only_issues"), value=False, key="am_issues")

        view = am[am["level"] == lvl_sel].copy()
        if pl_sel: view = view[view["platform"].isin(pl_sel)]
        if mp_sel: view = view[view["mp"].isin(mp_sel)]
        if search: view = view[view["sku"].str.contains(search, case=False, na=False) | view["name"].fillna("").str.contains(search, case=False, na=False)]
        if not show_hist: view = view[view["removed_on"].isna()]
        if only_issues: view = view[view["issues"].notna()]
        act = am[am["removed_on"].isna() & (am["level"] == "marketplace")]
        st.caption(_trf("am_summary", n=len(act), listing=int(act["in_listing"].sum()), comp=int(act["complementary"].sum()),
                        err=int((act["n_err"].fillna(0) > 0).sum())))
        for c in ("mp", "name", "reason", "issues", "sku_type"): view[c] = view[c].fillna("")
        view["added_on"] = pd.to_datetime(view["added_on"]); view["removed_on"] = pd.to_datetime(view["removed_on"])
        cols = ["platform", "mp", "sku", "name", "sku_type", "added_on", "removed_on", "in_listing", "complementary", "reason", "source", "issues"]
        ed = st.data_editor(
            view[cols], key=f"ed_am_{lvl_sel}", use_container_width=True, height=440, hide_index=True, num_rows="fixed",
            disabled=["platform", "mp", "sku", "name", "sku_type", "added_on", "source", "issues"],
            column_config={
                "platform": st.column_config.TextColumn(_tr("am_col_platform"), width="small"),
                "mp": st.column_config.TextColumn(_tr("am_col_mp"), width="small"),
                "sku": st.column_config.TextColumn(_tr("am_col_sku"), width="small"),
                "name": st.column_config.TextColumn(_tr("am_col_name"), width="large"),
                "sku_type": st.column_config.TextColumn(_tr("am_col_type"), width="small"),
                "added_on": st.column_config.DateColumn(_tr("am_col_added"), format="DD.MM.YYYY", width="small"),
                "removed_on": st.column_config.DateColumn(_tr("am_col_removed"), format="DD.MM.YYYY", width="small"),
                "in_listing": st.column_config.CheckboxColumn(_tr("am_col_listing"), width="small"),
                "complementary": st.column_config.CheckboxColumn(_tr("am_col_comp"), width="small"),
                "reason": st.column_config.TextColumn(_tr("am_col_reason"), width="medium"),
                "source": st.column_config.TextColumn(_tr("am_col_source"), width="small"),
                "issues": st.column_config.TextColumn(_tr("am_col_issues"), width="medium"),
            },
        )

        # ── представления по выбранному маркетплейсу ──
        st.markdown(f"**{_tr('am_repr_title')}**")
        _mp_codes = sorted(am.loc[am["level"] == "marketplace", "mp"].dropna().unique())
        rp_mp = st.selectbox(_tr("am_repr_pick_mp"), _mp_codes, index=(_mp_codes.index("AMZ-ES") if "AMZ-ES" in _mp_codes else 0) if _mp_codes else None, key="am_repr_mp")
        roles = q("SELECT code, name FROM kabinet_data.commercial_roles WHERE is_active ORDER BY sort_order")
        _role_opts = [""] + roles["code"].tolist()
        rp = q1(f"""
            SELECT r.id, r.peid, a.sku, g.name AS group_name, e.variation_group_id, r.commercial_role, r.valid_from, r.valid_to, r.source, c.issues
            FROM {AR} r
            JOIN {AA} a ON a.id = r.admission_id
            JOIN kabinet_data.marketplaces_new m ON m.id = r.marketplace_id
            LEFT JOIN kabinet_data.product_entities e ON e.marketplace_id = r.marketplace_id AND e.peid = r.peid
            LEFT JOIN kabinet_data.variation_groups g ON g.id = e.variation_group_id
            LEFT JOIN (SELECT record_id, string_agg(check_code || CASE severity WHEN 'error' THEN ' ⛔' ELSE ' ⚠' END, ', ') AS issues
                       FROM kabinet_data.assortment_checks WHERE register = 'representation' GROUP BY 1) c ON c.record_id = r.id
            WHERE m.code = %s AND (r.valid_to IS NULL OR %s) ORDER BY a.sku, r.peid""", (rp_mp, bool(show_hist))) if rp_mp else pd.DataFrame()
        if rp.empty:
            st.caption(_tr("am_repr_none")); ed_r = rp
        else:
            for c in ("group_name", "commercial_role", "issues"): rp[c] = rp[c].fillna("")
            rp["valid_from"] = pd.to_datetime(rp["valid_from"]); rp["valid_to"] = pd.to_datetime(rp["valid_to"])
            st.caption(_tr("am_role_help"))
            ed_r = st.data_editor(
                rp[["sku", "peid", "group_name", "commercial_role", "valid_from", "valid_to", "source", "issues"]],
                key=f"ed_am_repr_{rp_mp}", use_container_width=True, height=360, hide_index=True, num_rows="fixed",
                disabled=["sku", "peid", "group_name", "valid_from", "source", "issues"],
                column_config={
                    "sku": st.column_config.TextColumn(_tr("am_col_sku"), width="small"),
                    "peid": st.column_config.TextColumn(_tr("am_repr_col_peid"), width="small"),
                    "group_name": st.column_config.TextColumn(_tr("am_repr_col_group"), width="medium"),
                    "commercial_role": st.column_config.SelectboxColumn(_tr("am_repr_col_role"), options=_role_opts, width="small"),
                    "valid_from": st.column_config.DateColumn(_tr("am_repr_col_from"), format="DD.MM.YYYY", width="small"),
                    "valid_to": st.column_config.DateColumn(_tr("am_repr_col_to"), format="DD.MM.YYYY", width="small"),
                    "source": st.column_config.TextColumn(_tr("am_col_source"), width="small"),
                    "issues": st.column_config.TextColumn(_tr("am_col_issues"), width="medium"),
                })

        if st.button(_tr("save"), key="save_am", type="primary"):
            stmts, n_a, n_r = [], 0, 0
            before = view.set_index("id"); ed_i = ed.copy(); ed_i.index = view.index
            for idx, r in ed_i.iterrows():
                rid = int(view.at[idx, "id"]); sets, params = [], []
                for f in ("in_listing", "complementary"):
                    if bool(r[f]) != bool(before.at[rid, f]):
                        sets.append(f"{f} = %s"); params.append(bool(r[f]))
                        stmts.append(("INSERT INTO kabinet_data.assortment_change_log (register, record_id, field, old_value, new_value, source, actor) VALUES ('admission', %s, %s, %s, %s, 'manual', 'kabinet')",
                                      (rid, f, str(bool(before.at[rid, f])), str(bool(r[f])))))
                if (r["reason"] or "") != (before.at[rid, "reason"] or ""):
                    sets.append("reason = %s"); params.append(r["reason"] or None)
                new_rm, old_rm = _py(r["removed_on"]), _py(before.at[rid, "removed_on"])
                if not _same(new_rm, old_rm):
                    sets.append("removed_on = %s"); params.append(new_rm)
                    stmts.append(("INSERT INTO kabinet_data.assortment_change_log (register, record_id, field, old_value, new_value, source, actor) VALUES ('admission', %s, 'removed_on', %s, %s, 'manual', 'kabinet')",
                                  (rid, str(old_rm), str(new_rm))))
                    if new_rm is not None:
                        # исключение SKU закрывает его действующие представления той же датой (ТЗ 007 §5)
                        stmts.append((f"UPDATE {AR} SET valid_to = %s, updated_at = now() WHERE admission_id = %s AND valid_to IS NULL", (new_rm, rid)))
                if sets:
                    sets.append("source = CASE WHEN source LIKE 'seed%%' THEN 'manual' ELSE source END")
                    stmts.append((f"UPDATE {AA} SET {', '.join(sets)}, updated_at = now() WHERE id = %s", params + [rid])); n_a += 1
            if not rp.empty:
                rb = rp.set_index("id"); ed_ri = ed_r.copy(); ed_ri.index = rp.index
                for idx, r in ed_ri.iterrows():
                    rid = int(rp.at[idx, "id"]); sets, params = [], []
                    new_role, old_role = (r["commercial_role"] or None), (rb.at[rid, "commercial_role"] or None)
                    if new_role != old_role:
                        if new_role and pd.isna(rb.at[rid, "variation_group_id"]):
                            st.warning(_trf("am_role_no_group", peid=r["peid"]))
                        else:
                            sets += ["commercial_role = %s", "role_since = %s"]; params += [new_role, date.today()]
                            stmts.append(("INSERT INTO kabinet_data.assortment_change_log (register, record_id, field, old_value, new_value, source, actor) VALUES ('representation', %s, 'commercial_role', %s, %s, 'manual', 'kabinet')",
                                          (rid, old_role, new_role)))
                    new_to, old_to = _py(r["valid_to"]), _py(rb.at[rid, "valid_to"])
                    if not _same(new_to, old_to):
                        sets.append("valid_to = %s"); params.append(new_to)
                    if sets:
                        stmts.append((f"UPDATE {AR} SET {', '.join(sets)}, source = CASE WHEN source LIKE 'seed%%' THEN 'manual' ELSE source END, updated_at = now() WHERE id = %s", params + [rid])); n_r += 1
            if not stmts:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql(stmts); st.cache_data.clear(); st.success(_trf("am_saved", a=n_a, r=n_r)); st.rerun()
                except Exception as e:
                    st.error(_trf("err", e=e))

        # ── добавить SKU в матрицу — с проверками ТЗ 007 §8 ──
        with st.form("am_add", clear_on_submit=True):
            st.markdown(f"**{_tr('am_add_title')}**")
            c1, c2, c3, c4 = st.columns([1, 1.2, 1.4, 1])
            a_level = c1.selectbox(_tr("am_level"), list(_lvl), format_func=_lvl.get)
            a_mp = c2.selectbox(_tr("am_mp"), mps_all["code"].tolist())
            a_sku = c3.selectbox(_tr("am_add_sku"), skus_all["sku"].tolist())
            a_date = c4.date_input(_tr("am_add_date"), value=date.today())
            c5, c6, c7 = st.columns([1, 1, 3])
            a_listing = c5.checkbox(_tr("am_col_listing"), value=True)
            a_comp = c6.checkbox(_tr("am_col_comp"), value=False)
            a_reason = c7.text_input(_tr("am_col_reason"))
            if st.form_submit_button(_tr("am_add_btn")):
                mrow = mps_all[mps_all["code"] == a_mp].iloc[0]; srow = skus_all[skus_all["sku"] == a_sku].iloc[0]
                a_platform = mrow["platform_short"]; a_mid = int(mrow["id"]) if a_level == "marketplace" else None
                errs = []
                if pd.isna(srow["intro_date"]): errs.append(_tr("am_add_no_intro"))
                if pd.notna(srow["exit_date"]): errs.append(_tr("am_add_exited"))
                restr = set(srow["restrictions"] or [])
                if a_mp in restr or a_mp.split("-")[-1] in restr: errs.append(_tr("am_add_restricted"))
                if a_comp and srow["sku_type"] == "composite": errs.append(_tr("am_add_comp_composite"))
                if a_level == "marketplace" and am[(am["level"] == "platform") & (am["platform"] == a_platform) & (am["sku"] == a_sku) & am["removed_on"].isna()].empty:
                    errs.append(_tr("am_add_no_platform"))
                dup = am[(am["level"] == a_level) & (am["platform"] == a_platform) & (am["sku"] == a_sku) & am["removed_on"].isna()
                         & ((am["marketplace_id"] == a_mid) if a_mid else am["marketplace_id"].isna())]
                if not dup.empty: errs.append(_tr("am_add_dup"))
                if errs:
                    for e in errs: st.error(e)
                else:
                    try:
                        exec_sql([(f"""INSERT INTO {AA} (level, platform, marketplace_id, sku, added_on, in_listing, complementary, reason, source, created_by)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'manual', 'kabinet')""",
                                   (a_level, a_platform, a_mid, a_sku, a_date, bool(a_listing), bool(a_comp), a_reason or None))])
                        st.cache_data.clear(); st.success(_tr("am_add_ok")); st.rerun()
                    except Exception as e:
                        st.error(_trf("err", e=e))
