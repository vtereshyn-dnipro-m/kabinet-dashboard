# pages/3_Forecast.py — документ «Прогноз продаж marketplace / пула» по ТЗ 010 v0.2
"""Экран поверх реестра прогноза (`forecast_documents`, `forecast_register`, `forecast_change_log`).

Документ в Кабинете — источник истины (Ярослав, 20.09.2026); файлы и лист Google — только способ
загрузить: загрузчик листа с 20.09 создаёт черновики, утверждает и проводит человек здесь.

Что реализовано из ТЗ: список документов (§10), карточка с шапкой (§5) и строками SKU × месяц (§6),
состояния значений «Не утверждено / Утверждено / Заменено» (§9), утверждение и снятие утверждения
по выбранным SKU и месяцам (сценарии 6, 19), проведение с проверками заполнения, утверждения,
прошедших месяцев и полноты (§4, §9, §12, сценарии 8, 17), замена действующих записей с двусторонними
ссылками (сценарий 20), добавление SKU с проверкой допуска по матрице (§3, §7, сценарий 4), заполнение
по матрице (сценарий 16), пустоты → нули (сценарий 5), удаление строк черновика (сценарий 18), журнал
изменений (§10, сценарий 13). Не реализовано: роли COUNTRY_MANAGER / DEMAND_PLANNER (у приложения нет
входа по пользователям), загрузка из файла в черновик (§11 — лист Google грузит загрузчик),
пересоздание после изменения пула (сценарии 12, 21), зависимая потребность (ТЗ 011 — отдельный расчёт).
"""
import calendar
import json
from datetime import date

import pandas as pd
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, get_lang

init_lang()

TR = {
    "ru": {
        "title": "Прогноз продаж", "caption": "Документы прогноза по ТЗ 010: черновик → утверждение значений → проведение. "
                 "Действующий прогноз — только из проведённых документов; проведённый документ не правится, изменение — новым документом.",
        "tab_docs": "Документы", "tab_log": "Журнал изменений", "tab_new": "Новый документ",
        "f_object": "Объект", "f_status": "Статус", "f_month": "Месяц в периоде", "all": "все",
        "st_draft": "Черновик", "st_posted": "Проведён", "full": "Полный", "partial": "Частичный",
        "col_number": "Номер", "col_date": "Дата", "col_object": "Объект", "col_period": "Период", "col_compl": "Полнота",
        "col_status": "Статус", "col_rows": "SKU", "col_filled": "Заполнено", "col_approved": "Утверждено", "col_source": "Источник",
        "col_created_by": "Создал", "col_posted_at": "Проведён", "col_comment": "Комментарий",
        "no_docs": "Документов по фильтру нет.", "open_doc": "Открыть документ",
        "new_object_type": "Тип объекта", "mp": "Marketplace", "pool": "Пул", "new_first": "Первый месяц", "new_last": "Последний месяц",
        "new_compl": "Полнота прогноза", "new_comment": "Комментарий", "btn_create": "Создать черновик",
        "err_period": "Последний месяц не раньше первого и не дальше 13 месяцев (§4).",
        "err_past": "Первый месяц — текущий или будущий: прошедшие месяцы заблокированы (§4).",
        "created": "Создан черновик {n}.",
        "hdr_object": "Объект", "hdr_period": "Период", "hdr_snapshot": "Состав пула на {d}", "hdr_created": "Создан {by} {at}",
        "hdr_posted": "Проведён {by} {at}", "hdr_source": "Источник",
        "m_rows": "SKU в документе", "m_cells": "Заполнено ячеек", "m_approved": "Утверждено ячеек", "m_matrix": "SKU матрицы в документе",
        "m_matrix_help": "Для полного прогноза: уникальные продажные SKU действующей матрицы объекта, включённые в документ / все продажные SKU матрицы (§12).",
        "m_sum": "Итого за период, шт", "m_rev": "Прогноз выручки, €",
        "grid_help": "Пусто — прогноз не заполнен, 0 — продаж не планируем. Прошедшие месяцы и проведённый документ не редактируются; "
                     "утверждённые ячейки меняются только после снятия утверждения.",
        "col_sku": "SKU", "col_type": "Тип", "col_state": "Состояние", "col_total": "Итого", "col_name": "Название",
        "type_base": "базовый", "type_composite": "составной", "type_unknown": "—",
        "state_all_appr": "утверждено", "state_none": "не утверждено", "state_part": "утв. {a}/{n}", "state_empty": "пусто: {e}",
        "btn_save": "Сохранить значения", "saved": "Сохранено изменений: {n}.", "nothing_changed": "Изменений нет.",
        "rej_approved": "{sku} · {m}: значение утверждено — сначала снимите утверждение.",
        "rej_past": "{sku} · {m}: прошедший месяц заблокирован.",
        "rej_value": "{sku} · {m}: допускаются целые числа не меньше нуля.",
        "rejected": "Не записано {n} значений:", "grid_posted": "Документ проведён — значения только для чтения.",
        "sec_add": "Добавить SKU", "add_pick": "SKU из справочника", "btn_add": "Добавить выбранные",
        "btn_matrix": "Заполнить по матрице", "matrix_added": "Добавлено по матрице: {n} SKU.", "matrix_none": "Все продажные SKU матрицы уже в документе.",
        "add_done": "Добавлено: {n}. Отклонено: {r}.", "add_no_admission": "{sku}: нет допуска к самостоятельной продаже на объекте (§3).",
        "add_liquidation": "{sku}: допуск закрыт — добавлен как распродажа по прежнему допуску (§7).", "add_dup": "{sku}: уже в документе.",
        "add_unknown": "{sku}: нет в справочнике SKU.",
        "sec_actions": "Действия", "pick_skus": "SKU", "pick_months": "Месяцы", "all_skus": "все SKU", "all_months": "все месяцы",
        "btn_approve": "Утвердить", "btn_unapprove": "Снять утверждение", "btn_zeros": "Пустоты → 0", "btn_delete": "Удалить строки",
        "approved_n": "Утверждено ячеек: {n}.", "approve_empty": "Не утверждено — пустые ячейки: {cells}",
        "unapproved_n": "Снято утверждение: {n}.", "zeros_n": "Заполнено нулями: {n}.",
        "del_has_approved": "Строки с утверждёнными значениями не удаляются: {skus}.",
        "del_confirm": "Удалить {n} строк? В них есть введённые значения. Нажмите ещё раз для подтверждения.",
        "deleted_n": "Удалено строк: {n}.",
        "sec_post": "Проведение", "btn_post": "Провести документ", "post_ok": "Документ {n} проведён: действующих записей {k}, заменено {r}.",
        "post_block": "Проведение заблокировано:", "post_no_rows": "в документе нет ни одного SKU;",
        "post_empty": "не заполнено ячеек: {n} ({cells});", "post_unapproved": "не утверждено ячеек: {n} ({cells});",
        "post_past": "в периоде прошедшие месяцы: {months} — проведение их не меняет и не создаёт (§4);",
        "post_missing": "полный прогноз: в матрице есть продажные SKU, которых нет в документе ({n}): {skus} — добавьте их или переключите на «Частичный» (сценарий 17);",
        "hdr_edit": "Шапка", "hdr_locked": "Объект и период заблокированы: в документе есть утверждённые значения (§9).",
        "btn_hdr_save": "Сохранить шапку", "hdr_saved": "Шапка сохранена.",
        "sec_prices": "Целевая цена по месяцам, €", "prices_help": "Цена не утверждается вместе с количеством и меняется в черновике без снятия утверждения (§9). Прогноз выручки = штуки × цена.",
        "btn_prices_save": "Сохранить цены", "prices_saved": "Сохранено цен: {n}.",
        "sec_states": "Состояние по месяцам", "states_help": "○ не утверждено · ✓ утверждено · ⟲ заменено новой версией · пусто — значения нет",
        "sec_doclog": "Журнал документа",
        "log_from": "Проведено / изменено с", "log_to": "по", "log_sku": "SKU", "log_month": "Месяц прогноза",
        "log_col_at": "Когда", "log_col_actor": "Кто", "log_col_doc": "Документ", "log_col_field": "Поле", "log_col_old": "Было", "log_col_new": "Стало", "log_col_src": "Источник",
        "log_empty": "Записей нет.",
        "err_read": "Не прочиталось: {e}", "err_write": "Не записалось: {e}",
        "actor_unknown": "kabinet-app",
    },
    "uk": {
        "title": "Прогноз продажів", "caption": "Документи прогнозу за ТЗ 010: чернетка → затвердження значень → проведення. "
                 "Чинний прогноз — лише з проведених документів; проведений документ не правиться, зміна — новим документом.",
        "tab_docs": "Документи", "tab_log": "Журнал змін", "tab_new": "Новий документ",
        "f_object": "Обʼєкт", "f_status": "Статус", "f_month": "Місяць у періоді", "all": "усі",
        "st_draft": "Чернетка", "st_posted": "Проведено", "full": "Повний", "partial": "Частковий",
        "col_number": "Номер", "col_date": "Дата", "col_object": "Обʼєкт", "col_period": "Період", "col_compl": "Повнота",
        "col_status": "Статус", "col_rows": "SKU", "col_filled": "Заповнено", "col_approved": "Затверджено", "col_source": "Джерело",
        "col_created_by": "Створив", "col_posted_at": "Проведено", "col_comment": "Коментар",
        "no_docs": "Документів за фільтром немає.", "open_doc": "Відкрити документ",
        "new_object_type": "Тип обʼєкта", "mp": "Marketplace", "pool": "Пул", "new_first": "Перший місяць", "new_last": "Останній місяць",
        "new_compl": "Повнота прогнозу", "new_comment": "Коментар", "btn_create": "Створити чернетку",
        "err_period": "Останній місяць не раніше першого і не далі 13 місяців (§4).",
        "err_past": "Перший місяць — поточний або майбутній: минулі місяці заблоковано (§4).",
        "created": "Створено чернетку {n}.",
        "hdr_object": "Обʼєкт", "hdr_period": "Період", "hdr_snapshot": "Склад пулу на {d}", "hdr_created": "Створено {by} {at}",
        "hdr_posted": "Проведено {by} {at}", "hdr_source": "Джерело",
        "m_rows": "SKU у документі", "m_cells": "Заповнено клітинок", "m_approved": "Затверджено клітинок", "m_matrix": "SKU матриці в документі",
        "m_matrix_help": "Для повного прогнозу: унікальні продажні SKU чинної матриці обʼєкта, включені в документ / усі продажні SKU матриці (§12).",
        "m_sum": "Разом за період, шт", "m_rev": "Прогноз виручки, €",
        "grid_help": "Порожньо — прогноз не заповнено, 0 — продажів не плануємо. Минулі місяці та проведений документ не редагуються; "
                     "затверджені клітинки змінюються лише після зняття затвердження.",
        "col_sku": "SKU", "col_type": "Тип", "col_state": "Стан", "col_total": "Разом", "col_name": "Назва",
        "type_base": "базовий", "type_composite": "складений", "type_unknown": "—",
        "state_all_appr": "затверджено", "state_none": "не затверджено", "state_part": "затв. {a}/{n}", "state_empty": "порожньо: {e}",
        "btn_save": "Зберегти значення", "saved": "Збережено змін: {n}.", "nothing_changed": "Змін немає.",
        "rej_approved": "{sku} · {m}: значення затверджено — спершу зніміть затвердження.",
        "rej_past": "{sku} · {m}: минулий місяць заблоковано.",
        "rej_value": "{sku} · {m}: допускаються цілі числа не менше нуля.",
        "rejected": "Не записано {n} значень:", "grid_posted": "Документ проведено — значення лише для читання.",
        "sec_add": "Додати SKU", "add_pick": "SKU з довідника", "btn_add": "Додати вибрані",
        "btn_matrix": "Заповнити за матрицею", "matrix_added": "Додано за матрицею: {n} SKU.", "matrix_none": "Усі продажні SKU матриці вже в документі.",
        "add_done": "Додано: {n}. Відхилено: {r}.", "add_no_admission": "{sku}: немає допуску до самостійного продажу на обʼєкті (§3).",
        "add_liquidation": "{sku}: допуск закрито — додано як розпродаж за попереднім допуском (§7).", "add_dup": "{sku}: вже в документі.",
        "add_unknown": "{sku}: немає в довіднику SKU.",
        "sec_actions": "Дії", "pick_skus": "SKU", "pick_months": "Місяці", "all_skus": "усі SKU", "all_months": "усі місяці",
        "btn_approve": "Затвердити", "btn_unapprove": "Зняти затвердження", "btn_zeros": "Порожні → 0", "btn_delete": "Видалити рядки",
        "approved_n": "Затверджено клітинок: {n}.", "approve_empty": "Не затверджено — порожні клітинки: {cells}",
        "unapproved_n": "Знято затвердження: {n}.", "zeros_n": "Заповнено нулями: {n}.",
        "del_has_approved": "Рядки із затвердженими значеннями не видаляються: {skus}.",
        "del_confirm": "Видалити {n} рядків? У них є введені значення. Натисніть ще раз для підтвердження.",
        "deleted_n": "Видалено рядків: {n}.",
        "sec_post": "Проведення", "btn_post": "Провести документ", "post_ok": "Документ {n} проведено: чинних записів {k}, замінено {r}.",
        "post_block": "Проведення заблоковано:", "post_no_rows": "у документі немає жодного SKU;",
        "post_empty": "не заповнено клітинок: {n} ({cells});", "post_unapproved": "не затверджено клітинок: {n} ({cells});",
        "post_past": "у періоді минулі місяці: {months} — проведення їх не змінює і не створює (§4);",
        "post_missing": "повний прогноз: у матриці є продажні SKU, яких немає в документі ({n}): {skus} — додайте їх або перемкніть на «Частковий» (сценарій 17);",
        "hdr_edit": "Шапка", "hdr_locked": "Обʼєкт і період заблоковано: у документі є затверджені значення (§9).",
        "btn_hdr_save": "Зберегти шапку", "hdr_saved": "Шапку збережено.",
        "sec_prices": "Цільова ціна за місяцями, €", "prices_help": "Ціна не затверджується разом із кількістю і змінюється в чернетці без зняття затвердження (§9). Прогноз виручки = штуки × ціна.",
        "btn_prices_save": "Зберегти ціни", "prices_saved": "Збережено цін: {n}.",
        "sec_states": "Стан за місяцями", "states_help": "○ не затверджено · ✓ затверджено · ⟲ замінено новою версією · порожньо — значення немає",
        "sec_doclog": "Журнал документа",
        "log_from": "Проведено / змінено з", "log_to": "по", "log_sku": "SKU", "log_month": "Місяць прогнозу",
        "log_col_at": "Коли", "log_col_actor": "Хто", "log_col_doc": "Документ", "log_col_field": "Поле", "log_col_old": "Було", "log_col_new": "Стало", "log_col_src": "Джерело",
        "log_empty": "Записів немає.",
        "err_read": "Не прочиталося: {e}", "err_write": "Не записалося: {e}",
        "actor_unknown": "kabinet-app",
    },
    "en": {
        "title": "Sales forecast", "caption": "Forecast documents per spec 010: draft → approve values → post. "
                 "The effective forecast comes only from posted documents; a posted document is immutable, changes go through a new one.",
        "tab_docs": "Documents", "tab_log": "Change log", "tab_new": "New document",
        "f_object": "Object", "f_status": "Status", "f_month": "Month within period", "all": "all",
        "st_draft": "Draft", "st_posted": "Posted", "full": "Full", "partial": "Partial",
        "col_number": "Number", "col_date": "Date", "col_object": "Object", "col_period": "Period", "col_compl": "Completeness",
        "col_status": "Status", "col_rows": "SKUs", "col_filled": "Filled", "col_approved": "Approved", "col_source": "Source",
        "col_created_by": "Created by", "col_posted_at": "Posted", "col_comment": "Comment",
        "no_docs": "No documents match the filter.", "open_doc": "Open document",
        "new_object_type": "Object type", "mp": "Marketplace", "pool": "Pool", "new_first": "First month", "new_last": "Last month",
        "new_compl": "Completeness", "new_comment": "Comment", "btn_create": "Create draft",
        "err_period": "Last month must not precede the first one and the period is at most 13 months (§4).",
        "err_past": "First month must be the current or a future month: past months are locked (§4).",
        "created": "Draft {n} created.",
        "hdr_object": "Object", "hdr_period": "Period", "hdr_snapshot": "Pool members as of {d}", "hdr_created": "Created by {by} {at}",
        "hdr_posted": "Posted by {by} {at}", "hdr_source": "Source",
        "m_rows": "SKUs in document", "m_cells": "Cells filled", "m_approved": "Cells approved", "m_matrix": "Matrix SKUs in document",
        "m_matrix_help": "Full forecast: unique sellable SKUs of the object's active matrix included in the document / all sellable matrix SKUs (§12).",
        "m_sum": "Period total, units", "m_rev": "Forecast revenue, €",
        "grid_help": "Empty — not filled, 0 — no sales planned. Past months and posted documents are read-only; "
                     "approved cells change only after unapproval.",
        "col_sku": "SKU", "col_type": "Type", "col_state": "State", "col_total": "Total", "col_name": "Name",
        "type_base": "base", "type_composite": "composite", "type_unknown": "—",
        "state_all_appr": "approved", "state_none": "not approved", "state_part": "appr. {a}/{n}", "state_empty": "empty: {e}",
        "btn_save": "Save values", "saved": "Saved changes: {n}.", "nothing_changed": "No changes.",
        "rej_approved": "{sku} · {m}: value is approved — unapprove first.",
        "rej_past": "{sku} · {m}: past month is locked.",
        "rej_value": "{sku} · {m}: only non-negative integers are allowed.",
        "rejected": "Not written: {n} values:", "grid_posted": "Document is posted — values are read-only.",
        "sec_add": "Add SKUs", "add_pick": "SKUs from the directory", "btn_add": "Add selected",
        "btn_matrix": "Fill from matrix", "matrix_added": "Added from matrix: {n} SKUs.", "matrix_none": "All sellable matrix SKUs are already in the document.",
        "add_done": "Added: {n}. Rejected: {r}.", "add_no_admission": "{sku}: no admission for standalone sale on this object (§3).",
        "add_liquidation": "{sku}: admission closed — added as sell-off under the former admission (§7).", "add_dup": "{sku}: already in the document.",
        "add_unknown": "{sku}: not in the SKU directory.",
        "sec_actions": "Actions", "pick_skus": "SKUs", "pick_months": "Months", "all_skus": "all SKUs", "all_months": "all months",
        "btn_approve": "Approve", "btn_unapprove": "Unapprove", "btn_zeros": "Empty → 0", "btn_delete": "Delete rows",
        "approved_n": "Approved cells: {n}.", "approve_empty": "Not approved — empty cells: {cells}",
        "unapproved_n": "Unapproved: {n}.", "zeros_n": "Filled with zeros: {n}.",
        "del_has_approved": "Rows with approved values cannot be deleted: {skus}.",
        "del_confirm": "Delete {n} rows? They contain values. Click again to confirm.",
        "deleted_n": "Rows deleted: {n}.",
        "sec_post": "Posting", "btn_post": "Post document", "post_ok": "Document {n} posted: {k} effective records, {r} superseded.",
        "post_block": "Posting is blocked:", "post_no_rows": "the document has no SKUs;",
        "post_empty": "empty cells: {n} ({cells});", "post_unapproved": "unapproved cells: {n} ({cells});",
        "post_past": "the period contains past months: {months} — posting neither changes nor creates them (§4);",
        "post_missing": "full forecast: the matrix has sellable SKUs missing from the document ({n}): {skus} — add them or switch to «Partial» (scenario 17);",
        "hdr_edit": "Header", "hdr_locked": "Object and period are locked: the document has approved values (§9).",
        "btn_hdr_save": "Save header", "hdr_saved": "Header saved.",
        "sec_prices": "Target price by month, €", "prices_help": "Price is not approved together with quantity and can change in a draft without unapproval (§9). Revenue = units × price.",
        "btn_prices_save": "Save prices", "prices_saved": "Prices saved: {n}.",
        "sec_states": "State by month", "states_help": "○ not approved · ✓ approved · ⟲ superseded · blank — no value",
        "sec_doclog": "Document log",
        "log_from": "Posted / changed from", "log_to": "to", "log_sku": "SKU", "log_month": "Forecast month",
        "log_col_at": "When", "log_col_actor": "Who", "log_col_doc": "Document", "log_col_field": "Field", "log_col_old": "Old", "log_col_new": "New", "log_col_src": "Source",
        "log_empty": "No records.",
        "err_read": "Read failed: {e}", "err_write": "Write failed: {e}",
        "actor_unknown": "kabinet-app",
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
    try:
        return _tr(key).format(**kw)
    except (KeyError, IndexError, ValueError):
        return _tr(key)


def _actor() -> str:
    """Кто действует. У приложения нет входа по пользователям (роли ТЗ §9 не реализованы);
    на Streamlit Cloud с закрытым доступом есть st.user.email — берём его, иначе имя приложения."""
    try:
        u = getattr(st, "user", None)
        email = getattr(u, "email", None) if u is not None else None
        if email:
            return str(email)
    except Exception:
        pass
    return _tr("actor_unknown")


# ═══════════════════════════════════════════════════════════════════════════
# БАЗА
# ═══════════════════════════════════════════════════════════════════════════

def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def tx(fn):
    """Одна транзакция на действие: либо всё записалось, либо ничего (проведение — десятки записей)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        out = fn(cur)
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def month_label(m) -> str:
    m = pd.Timestamp(m)
    return f"{m.month:02d}.{m.year}"


def months_between(a: date, b: date) -> list:
    out, cur = [], date(a.year, a.month, 1)
    while cur <= b:
        out.append(cur)
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return out


def add_months(d: date, n: int) -> date:
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


TODAY = date.today()
CUR_MONTH = date(TODAY.year, TODAY.month, 1)


def load_objects() -> pd.DataFrame:
    mp = q("""SELECT 'marketplace' AS object_type, id AS object_id, code AS name, country_alpha2 AS country, platform_short AS platform
              FROM kabinet_data.marketplaces_new WHERE is_active ORDER BY code""")
    pl = q("""SELECT 'pool' AS object_type, p.id AS object_id, p.name, MIN(m.country_alpha2) AS country, NULL::text AS platform
              FROM kabinet_data.pools p LEFT JOIN kabinet_data.pool_members pm ON pm.pool_id = p.id
                   AND pm.valid_from <= current_date AND (pm.valid_to IS NULL OR pm.valid_to >= current_date)
              LEFT JOIN kabinet_data.marketplaces_new m ON m.id = pm.marketplace_id GROUP BY p.id, p.name ORDER BY p.name""")
    return pd.concat([mp, pl], ignore_index=True)


def object_label(row) -> str:
    return f"{row['name']} ({_tr('pool')})" if row["object_type"] == "pool" else str(row["name"])


def pool_snapshot(pool_id: int) -> list:
    d = q("""SELECT marketplace_id FROM kabinet_data.pool_members WHERE pool_id = %s
             AND valid_from <= current_date AND (valid_to IS NULL OR valid_to >= current_date) ORDER BY 1""", (int(pool_id),))
    return [int(x) for x in d["marketplace_id"]]


def load_docs() -> pd.DataFrame:
    return q("""
        SELECT d.id, d.number, d.doc_date, d.object_type, d.object_id,
               COALESCE(m.code, p.name) AS object_name, d.first_month, d.last_month, d.completeness, d.status, d.comment,
               d.source, d.created_by, d.created_at, d.posted_by, d.posted_at, d.pool_snapshot, d.pool_snapshot_date,
               COUNT(DISTINCT r.sku) AS n_sku, COUNT(r.id) AS n_cells,
               COUNT(r.id) FILTER (WHERE r.quantity IS NOT NULL) AS n_filled,
               COUNT(r.id) FILTER (WHERE r.status = 'approved' OR (d.status = 'posted' AND r.status <> 'unapproved')) AS n_approved
        FROM kabinet_data.forecast_documents d
        LEFT JOIN kabinet_data.marketplaces_new m ON d.object_type = 'marketplace' AND m.id = d.object_id
        LEFT JOIN kabinet_data.pools p ON d.object_type = 'pool' AND p.id = d.object_id
        LEFT JOIN kabinet_data.forecast_register r ON r.document_id = d.id AND r.record_type = 'sales'
        GROUP BY d.id, m.code, p.name
        ORDER BY d.status = 'draft' DESC, d.created_at DESC""")


def load_rows(doc_id: int) -> pd.DataFrame:
    return q("""
        SELECT r.id, r.sku, r.month, r.quantity, r.status, r.target_price, r.line_comment, r.version, r.is_current,
               r.approved_by, r.approved_at, s.sku_type, s.name AS sku_name
        FROM kabinet_data.forecast_register r
        LEFT JOIN kabinet_data.sku_master s ON s.sku = r.sku
        WHERE r.document_id = %s AND r.record_type = 'sales'
        ORDER BY r.sku, r.month""", (int(doc_id),))


def admitted_skus(object_type: str, object_id: int, snapshot) -> tuple:
    """Продажные SKU действующей матрицы объекта (§12) и SKU с закрытым допуском (распродажа, §7).
    Marketplace — записи уровня marketplace; пул — хотя бы на одном marketplace сохранённого состава."""
    if object_type == "marketplace":
        ids = [int(object_id)]
    else:
        ids = [int(x) for x in (snapshot or [])] or pool_snapshot(object_id)
    if not ids:
        return set(), set()
    d = q("""SELECT sku, bool_or(removed_on IS NULL OR removed_on > current_date) AS active
             FROM kabinet_data.assortment_admissions
             WHERE level = 'marketplace' AND marketplace_id = ANY(%s) AND in_listing AND added_on <= current_date
             GROUP BY sku""", (ids,))
    active = set(d.loc[d["active"], "sku"])
    former = set(d.loc[~d["active"], "sku"]) - active
    return active, former


def log(cur, doc_id, sku, month, field, old, new, source, actor):
    cur.execute("""INSERT INTO kabinet_data.forecast_change_log (document_id, sku, month, field, old_value, new_value, source, actor)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (int(doc_id), sku, month, field, None if old is None else str(old), None if new is None else str(new), source, actor))


def next_number(cur, object_name: str) -> str:
    base = f"FC-{TODAY:%Y%m%d}-{object_name.upper()}"
    cur.execute("SELECT count(*) FROM kabinet_data.forecast_documents WHERE number = %s OR number LIKE %s", (base, base + "-%"))
    n = cur.fetchone()[0]
    return base if n == 0 else f"{base}-{n + 1}"


# ═══════════════════════════════════════════════════════════════════════════
# ДЕЙСТВИЯ
# ═══════════════════════════════════════════════════════════════════════════

def create_document(obj, first: date, last: date, completeness: str, comment: str) -> str:
    actor = _actor()
    snap = pool_snapshot(obj["object_id"]) if obj["object_type"] == "pool" else None

    def _do(cur):
        no = next_number(cur, str(obj["name"]))
        cur.execute("""INSERT INTO kabinet_data.forecast_documents
                          (number, object_type, object_id, pool_snapshot, pool_snapshot_date, first_month, last_month,
                           completeness, status, comment, source, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s, 'manual', %s) RETURNING id""",
                    (no, obj["object_type"], int(obj["object_id"]), json.dumps(snap) if snap else None,
                     TODAY if snap else None, first, last, completeness, comment or None, actor))
        doc_id = cur.fetchone()[0]
        log(cur, doc_id, None, None, "document", None, f"created {no}", "manual", actor)
        return no
    return tx(_do)


def add_skus(doc, rows: pd.DataFrame, skus: list, active: set, former: set, known: set) -> tuple:
    """Сценарий 4: SKU есть в справочнике, есть допуск (действующий или прежний — распродажа), нет дубля."""
    actor = _actor()
    months = months_between(doc["first_month"], doc["last_month"])
    present = set(rows["sku"]) if not rows.empty else set()
    ok, rejected = [], []
    for s in skus:
        if s not in known:
            rejected.append(_trf("add_unknown", sku=s))
        elif s in present:
            rejected.append(_trf("add_dup", sku=s))
        elif s in active:
            ok.append((s, None))
        elif s in former:
            ok.append((s, "liquidation"))
            rejected.append(_trf("add_liquidation", sku=s))
        else:
            rejected.append(_trf("add_no_admission", sku=s))
    if ok:
        def _do(cur):
            for s, note in ok:
                for m in months:
                    cur.execute("""INSERT INTO kabinet_data.forecast_register
                                      (record_type, object_type, object_id, sku, month, quantity, version, status, is_current, document_id, line_comment, created_by)
                                   VALUES ('sales', %s, %s, %s, %s, NULL, 1, 'unapproved', FALSE, %s, %s, %s)""",
                                (doc["object_type"], int(doc["object_id"]), s, m, int(doc["id"]),
                                 "распродажа по прежнему допуску (§7)" if note else None, actor))
                log(cur, doc["id"], s, None, "row", None, "added" + (" (liquidation)" if note else ""), "manual", actor)
        tx(_do)
    return len(ok), rejected


def save_grid(doc, rows: pd.DataFrame, edited: pd.DataFrame, months: list) -> tuple:
    """Ручной ввод (§6, §11): пусто → NULL, 0 → 0; утверждённые и прошедшие месяцы не трогаем, ошибку показываем."""
    actor = _actor()
    by_key = {(r.sku, pd.Timestamp(r.month).date()): r for r in rows.itertuples()}
    changes, rejected = [], []
    for _, er in edited.iterrows():
        sku = er["sku"]
        for m in months:
            col = month_label(m)
            if col not in edited.columns:
                continue
            v = er.get(col)
            new = None if (v is None or (isinstance(v, float) and pd.isna(v)) or v == "") else v
            old_r = by_key.get((sku, m))
            if old_r is None:
                continue
            old = None if pd.isna(old_r.quantity) else int(old_r.quantity)
            if new is not None:
                try:
                    fv = float(new)
                    if fv < 0 or fv != int(fv):
                        raise ValueError
                    new = int(fv)
                except (TypeError, ValueError):
                    rejected.append(_trf("rej_value", sku=sku, m=col))
                    continue
            if new == old:
                continue
            if m < CUR_MONTH:
                rejected.append(_trf("rej_past", sku=sku, m=col))
                continue
            if old_r.status == "approved":
                rejected.append(_trf("rej_approved", sku=sku, m=col))
                continue
            changes.append((old_r.id, sku, m, old, new))
    if changes:
        def _do(cur):
            for rid, sku, m, old, new in changes:
                cur.execute("UPDATE kabinet_data.forecast_register SET quantity = %s WHERE id = %s AND status = 'unapproved'", (new, int(rid)))
                log(cur, doc["id"], sku, m, "quantity", old, new, "manual", actor)
        tx(_do)
    return len(changes), rejected


def save_prices(doc, rows: pd.DataFrame, edited: pd.DataFrame, months: list) -> int:
    actor = _actor()
    by_key = {(r.sku, pd.Timestamp(r.month).date()): r for r in rows.itertuples()}
    changes = []
    for _, er in edited.iterrows():
        for m in months:
            if m < CUR_MONTH or month_label(m) not in edited.columns:
                continue
            v = er.get(month_label(m))
            new = None if (v is None or (isinstance(v, float) and pd.isna(v))) else round(float(v), 4)
            r = by_key.get((er["sku"], m))
            if r is None:
                continue
            old = None if pd.isna(r.target_price) else round(float(r.target_price), 4)
            if new != old:
                changes.append((r.id, er["sku"], m, old, new))
    if changes:
        def _do(cur):
            for rid, sku, m, old, new in changes:
                cur.execute("UPDATE kabinet_data.forecast_register SET target_price = %s WHERE id = %s", (new, int(rid)))
                log(cur, doc["id"], sku, m, "target_price", old, new, "manual", actor)
        tx(_do)
    return len(changes)


def _cells(rows: pd.DataFrame, skus, months) -> pd.DataFrame:
    sel = rows[rows["month"].apply(lambda x: pd.Timestamp(x).date()).isin(months)]
    if skus:
        sel = sel[sel["sku"].isin(skus)]
    return sel


def approve(doc, rows, skus, months) -> tuple:
    """Сценарий 6: утверждаем только заполненные ячейки выбранных SKU × месяцев; пустые показываем и не утверждаем."""
    actor = _actor()
    sel = _cells(rows, skus, [m for m in months if m >= CUR_MONTH])
    sel = sel[sel["status"] == "unapproved"]
    empty = sel[sel["quantity"].isna()]
    if len(empty):
        return 0, [f"{r.sku} · {month_label(r.month)}" for r in empty.itertuples()]
    if sel.empty:
        return 0, []
    def _do(cur):
        for r in sel.itertuples():
            cur.execute("""UPDATE kabinet_data.forecast_register SET status = 'approved', approved_by = %s, approved_at = now()
                           WHERE id = %s AND status = 'unapproved' AND quantity IS NOT NULL""", (actor, int(r.id)))
            log(cur, doc["id"], r.sku, pd.Timestamp(r.month).date(), "approval", "unapproved", "approved", "approve", actor)
    tx(_do)
    return len(sel), []


def unapprove(doc, rows, skus, months) -> int:
    """Сценарий 19: только черновик, только текущие и будущие месяцы; пользователь и дата — в записи и в журнале."""
    actor = _actor()
    sel = _cells(rows, skus, [m for m in months if m >= CUR_MONTH])
    sel = sel[sel["status"] == "approved"]
    if sel.empty:
        return 0
    def _do(cur):
        for r in sel.itertuples():
            cur.execute("""UPDATE kabinet_data.forecast_register SET status = 'unapproved', unapproved_by = %s, unapproved_at = now()
                           WHERE id = %s AND status = 'approved'""", (actor, int(r.id)))
            log(cur, doc["id"], r.sku, pd.Timestamp(r.month).date(), "approval", "approved", "unapproved", "unapprove", actor)
    tx(_do)
    return len(sel)


def fill_zeros(doc, rows) -> int:
    actor = _actor()
    sel = rows[(rows["quantity"].isna()) & (rows["status"] == "unapproved")
               & (rows["month"].apply(lambda x: pd.Timestamp(x).date()) >= CUR_MONTH)]
    if sel.empty:
        return 0
    def _do(cur):
        for r in sel.itertuples():
            cur.execute("UPDATE kabinet_data.forecast_register SET quantity = 0 WHERE id = %s AND quantity IS NULL", (int(r.id),))
            log(cur, doc["id"], r.sku, pd.Timestamp(r.month).date(), "quantity", None, 0, "manual:fill_zeros", actor)
    tx(_do)
    return len(sel)


def delete_rows(doc, rows, skus) -> int:
    """Сценарий 18: физически удаляем только строки черновика без утверждённых значений — они ещё не история."""
    actor = _actor()
    sel = rows[rows["sku"].isin(skus)]
    if sel.empty:
        return 0
    def _do(cur):
        cur.execute("""DELETE FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales'
                       AND sku = ANY(%s) AND status = 'unapproved' AND NOT is_current""", (int(doc["id"]), list(skus)))
        for s in skus:
            log(cur, doc["id"], s, None, "row", "present", "deleted", "manual", actor)
    tx(_do)
    return len(set(sel["sku"]))


def save_header(doc, first, last, completeness, comment, locked: bool) -> None:
    actor = _actor()
    def _do(cur):
        if locked:
            cur.execute("UPDATE kabinet_data.forecast_documents SET completeness = %s, comment = %s WHERE id = %s AND status = 'draft'",
                        (completeness, comment or None, int(doc["id"])))
        else:
            cur.execute("""UPDATE kabinet_data.forecast_documents SET first_month = %s, last_month = %s, completeness = %s, comment = %s
                           WHERE id = %s AND status = 'draft'""", (first, last, completeness, comment or None, int(doc["id"])))
            # период изменился — строки документа приводим к новому набору месяцев (пустые ячейки добавляем, лишние неутверждённые убираем)
            months = months_between(first, last)
            cur.execute("SELECT DISTINCT sku FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales'", (int(doc["id"]),))
            skus = [r[0] for r in cur.fetchall()]
            cur.execute("""DELETE FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales'
                           AND status = 'unapproved' AND NOT is_current AND NOT (month = ANY(%s))""", (int(doc["id"]), months))
            for s in skus:
                for m in months:
                    cur.execute("""INSERT INTO kabinet_data.forecast_register (record_type, object_type, object_id, sku, month, quantity, version, status, is_current, document_id, created_by)
                                   SELECT 'sales', %s, %s, %s, %s, NULL, 1, 'unapproved', FALSE, %s, %s
                                   WHERE NOT EXISTS (SELECT 1 FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales' AND sku = %s AND month = %s)""",
                                (doc["object_type"], int(doc["object_id"]), s, m, int(doc["id"]), actor, int(doc["id"]), s, m))
        log(cur, doc["id"], None, None, "header", None, f"{first:%Y-%m}..{last:%Y-%m} {completeness}", "manual", actor)
    tx(_do)


def post_checks(doc, rows: pd.DataFrame, active_matrix: set) -> list:
    """Сценарий 8 + 17: всё заполнено и утверждено, прошедших месяцев нет, для полного — состав матрицы."""
    problems = []
    if rows.empty:
        problems.append(_tr("post_no_rows"))
        return problems
    empty = rows[rows["quantity"].isna()]
    if len(empty):
        cells = ", ".join(f"{r.sku} · {month_label(r.month)}" for r in empty.head(8).itertuples()) + ("…" if len(empty) > 8 else "")
        problems.append(_trf("post_empty", n=len(empty), cells=cells))
    un = rows[(rows["status"] != "approved")]
    if len(un):
        cells = ", ".join(f"{r.sku} · {month_label(r.month)}" for r in un.head(8).itertuples()) + ("…" if len(un) > 8 else "")
        problems.append(_trf("post_unapproved", n=len(un), cells=cells))
    past = sorted({pd.Timestamp(m).date() for m in rows["month"] if pd.Timestamp(m).date() < CUR_MONTH})
    if past:
        problems.append(_trf("post_past", months=", ".join(month_label(m) for m in past)))
    if doc["completeness"] == "full":
        missing = sorted(active_matrix - set(rows["sku"]))
        if missing:
            problems.append(_trf("post_missing", n=len(missing), skus=", ".join(missing[:12]) + ("…" if len(missing) > 12 else "")))
    return problems


def post_document(doc, rows: pd.DataFrame) -> tuple:
    """Сценарий 20: заменяем записи, действующие на момент проведения; ссылки в обе стороны; дата проведения — дата изменения."""
    actor = _actor()
    def _do(cur):
        cur.execute("SELECT status FROM kabinet_data.forecast_documents WHERE id = %s FOR UPDATE", (int(doc["id"]),))
        if cur.fetchone()[0] != "draft":
            raise RuntimeError("document is not a draft")
        n_cur = n_rep = 0
        for r in rows.itertuples():
            m = pd.Timestamp(r.month).date()
            cur.execute("""SELECT id, version FROM kabinet_data.forecast_register
                           WHERE record_type = 'sales' AND object_type = %s AND object_id = %s AND sku = %s AND month = %s AND is_current
                           FOR UPDATE""", (doc["object_type"], int(doc["object_id"]), r.sku, m))
            old = cur.fetchone()
            if old:
                cur.execute("""UPDATE kabinet_data.forecast_register SET is_current = FALSE, status = 'superseded', superseded_at = now(),
                               replaced_by = array_append(replaced_by, %s) WHERE id = %s""", (int(r.id), int(old[0])))
                n_rep += 1
            cur.execute("""UPDATE kabinet_data.forecast_register SET is_current = TRUE, version = %s, replaces = %s, changed_at = now()
                           WHERE id = %s AND status = 'approved' AND quantity IS NOT NULL""",
                        ((old[1] + 1) if old else 1, [int(old[0])] if old else [], int(r.id)))
            n_cur += 1
        cur.execute("""UPDATE kabinet_data.forecast_documents SET status = 'posted', posted_by = %s, posted_at = now() WHERE id = %s""",
                    (actor, int(doc["id"])))
        log(cur, doc["id"], None, None, "document", "draft", "posted", "post", actor)
        return n_cur, n_rep
    return tx(_do)


# ═══════════════════════════════════════════════════════════════════════════
# ЭКРАН
# ═══════════════════════════════════════════════════════════════════════════

st.title(_tr("title"))
st.caption(_tr("caption"))

try:
    objects = load_objects()
    docs = load_docs()
except Exception as e:
    st.error(_trf("err_read", e=e))
    st.stop()

obj_labels = {f"{r['object_type']}:{r['object_id']}": object_label(r) for _, r in objects.iterrows()}
tab_docs, tab_new, tab_log = st.tabs([_tr("tab_docs"), _tr("tab_new"), _tr("tab_log")])

# ───────────────────────────── новый документ ─────────────────────────────
with tab_new:
    c1, c2 = st.columns(2)
    otype = c1.radio(_tr("new_object_type"), ["marketplace", "pool"], format_func=lambda x: _tr("mp") if x == "marketplace" else _tr("pool"),
                     horizontal=True, key="fc_new_type")
    cands = objects[objects["object_type"] == otype]
    pick = c2.selectbox(_tr("f_object"), list(cands["object_id"]), format_func=lambda i: object_label(cands[cands["object_id"] == i].iloc[0]),
                        key="fc_new_obj") if len(cands) else None
    month_opts = [add_months(CUR_MONTH, i) for i in range(0, 25)]
    c3, c4, c5 = st.columns(3)
    first = c3.selectbox(_tr("new_first"), month_opts, format_func=month_label, key="fc_new_first")
    last = c4.selectbox(_tr("new_last"), month_opts, index=min(5, len(month_opts) - 1), format_func=month_label, key="fc_new_last")
    compl = c5.radio(_tr("new_compl"), ["partial", "full"], format_func=lambda x: _tr(x), horizontal=True, key="fc_new_compl")
    comment = st.text_input(_tr("new_comment"), key="fc_new_comment")
    if st.button(_tr("btn_create"), type="primary", disabled=pick is None, key="fc_create"):
        if last < first or add_months(first, 12) < last:
            st.error(_tr("err_period"))
        elif first < CUR_MONTH:
            st.error(_tr("err_past"))
        else:
            try:
                no = create_document(cands[cands["object_id"] == pick].iloc[0], first, last, compl, comment)
                st.success(_trf("created", n=no))
                st.session_state["fc_open_number"] = no
                st.rerun()
            except Exception as e:
                st.error(_trf("err_write", e=e))

# ───────────────────────────── список ─────────────────────────────
with tab_docs:
    f1, f2, f3 = st.columns(3)
    f_obj = f1.selectbox(_tr("f_object"), [None] + list(obj_labels.keys()), format_func=lambda k: _tr("all") if k is None else obj_labels[k], key="fc_f_obj")
    f_st = f2.selectbox(_tr("f_status"), [None, "draft", "posted"], format_func=lambda s: _tr("all") if s is None else _tr("st_" + s), key="fc_f_st")
    f_m = f3.selectbox(_tr("f_month"), [None] + [add_months(CUR_MONTH, i) for i in range(-3, 13)],
                       format_func=lambda m: _tr("all") if m is None else month_label(m), key="fc_f_m")
    view = docs.copy()
    if f_obj:
        ot, oid = f_obj.split(":")
        view = view[(view["object_type"] == ot) & (view["object_id"] == int(oid))]
    if f_st:
        view = view[view["status"] == f_st]
    if f_m:
        view = view[(pd.to_datetime(view["first_month"]).dt.date <= f_m) & (pd.to_datetime(view["last_month"]).dt.date >= f_m)]

    if view.empty:
        st.info(_tr("no_docs"))
    else:
        show = pd.DataFrame({
            _tr("col_number"): view["number"], _tr("col_date"): pd.to_datetime(view["doc_date"]).dt.strftime("%d.%m.%Y"),
            _tr("col_object"): view["object_name"] + view["object_type"].map({"pool": f" ({_tr('pool')})", "marketplace": ""}),
            _tr("col_period"): view["first_month"].map(month_label) + " – " + view["last_month"].map(month_label),
            _tr("col_compl"): view["completeness"].map(lambda x: _tr(x)), _tr("col_status"): view["status"].map(lambda s: _tr("st_" + s)),
            _tr("col_rows"): view["n_sku"], _tr("col_filled"): view["n_filled"].astype(str) + " / " + view["n_cells"].astype(str),
            _tr("col_approved"): view["n_approved"], _tr("col_source"): view["source"], _tr("col_created_by"): view["created_by"],
            _tr("col_posted_at"): pd.to_datetime(view["posted_at"]).dt.strftime("%d.%m.%Y %H:%M").fillna("—"), _tr("col_comment"): view["comment"].fillna(""),
        })
        st.dataframe(show, hide_index=True, use_container_width=True, height=min(420, 38 + 35 * len(show)))

    numbers = list(view["number"])
    default = st.session_state.get("fc_open_number")
    idx = numbers.index(default) if default in numbers else 0
    sel_no = st.selectbox(_tr("open_doc"), numbers, index=idx, key="fc_sel") if numbers else None

    if sel_no:
        doc = docs[docs["number"] == sel_no].iloc[0].to_dict()
        doc["first_month"] = pd.Timestamp(doc["first_month"]).date()
        doc["last_month"] = pd.Timestamp(doc["last_month"]).date()
        is_draft = doc["status"] == "draft"
        months = months_between(doc["first_month"], doc["last_month"])
        try:
            rows = load_rows(doc["id"])
            snap = doc.get("pool_snapshot")
            if isinstance(snap, str):
                snap = json.loads(snap)
            active_matrix, former_matrix = admitted_skus(doc["object_type"], doc["object_id"], snap)
            known = set(q("SELECT sku FROM kabinet_data.sku_master")["sku"])
        except Exception as e:
            st.error(_trf("err_read", e=e))
            st.stop()
        rows["month"] = pd.to_datetime(rows["month"]).dt.date

        # ── шапка ──
        st.divider()
        st.subheader(f"{doc['number']} · {doc['object_name']}" + (f" ({_tr('pool')})" if doc["object_type"] == "pool" else ""))
        h1, h2, h3, h4 = st.columns(4)
        h1.markdown(f"**{_tr('hdr_period')}**: {month_label(doc['first_month'])} – {month_label(doc['last_month'])}")
        h2.markdown(f"**{_tr('col_status')}**: {_tr('st_' + doc['status'])} · {_tr(doc['completeness'])}")
        h3.markdown(_trf("hdr_created", by=doc["created_by"], at=pd.Timestamp(doc["created_at"]).strftime("%d.%m.%Y %H:%M")))
        if doc["posted_at"] is not None and not pd.isna(doc["posted_at"]):
            h4.markdown(_trf("hdr_posted", by=doc["posted_by"], at=pd.Timestamp(doc["posted_at"]).strftime("%d.%m.%Y %H:%M")))
        else:
            h4.markdown(f"**{_tr('hdr_source')}**: {doc['source']}")
        if snap:
            names = objects[(objects["object_type"] == "marketplace") & (objects["object_id"].isin(snap))]["name"]
            st.caption(_trf("hdr_snapshot", d=pd.Timestamp(doc["pool_snapshot_date"]).strftime("%d.%m.%Y") if doc.get("pool_snapshot_date") else "—")
                       + ": " + ", ".join(names))
        if doc.get("comment"):
            st.caption(f"{_tr('col_comment')}: {doc['comment']}")

        n_appr = int((rows["status"] == "approved").sum()) if is_draft else int((rows["status"] != "unapproved").sum())
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric(_tr("m_rows"), rows["sku"].nunique())
        k2.metric(_tr("m_cells"), f"{int(rows['quantity'].notna().sum())} / {len(rows)}")
        k3.metric(_tr("m_approved"), f"{n_appr} / {len(rows)}")
        if doc["completeness"] == "full":
            k4.metric(_tr("m_matrix"), f"{len(active_matrix & set(rows['sku']))} / {len(active_matrix)}", help=_tr("m_matrix_help"))
        k4_total = int(rows["quantity"].fillna(0).sum())
        k5.metric(_tr("m_sum"), f"{k4_total:,}")
        rev = (rows["quantity"].fillna(0) * rows["target_price"].fillna(0)).sum()
        if rev:
            st.caption(f"{_tr('m_rev')}: {rev:,.0f}")

        # ── редактируемая шапка (черновик) ──
        has_approved = bool((rows["status"] == "approved").any())
        if is_draft:
            with st.expander(_tr("hdr_edit")):
                if has_approved:
                    st.info(_tr("hdr_locked"))
                e1, e2, e3 = st.columns(3)
                opts = sorted(set([add_months(CUR_MONTH, i) for i in range(0, 25)] + [doc["first_month"], doc["last_month"]]))
                ef = e1.selectbox(_tr("new_first"), opts, index=opts.index(doc["first_month"]), format_func=month_label, key=f"fc_hf_{doc['id']}", disabled=has_approved)
                el = e2.selectbox(_tr("new_last"), opts, index=opts.index(doc["last_month"]), format_func=month_label, key=f"fc_hl_{doc['id']}", disabled=has_approved)
                ec = e3.radio(_tr("new_compl"), ["partial", "full"], index=0 if doc["completeness"] == "partial" else 1,
                              format_func=lambda x: _tr(x), horizontal=True, key=f"fc_hc_{doc['id']}")
                ecm = st.text_input(_tr("new_comment"), value=doc.get("comment") or "", key=f"fc_hcm_{doc['id']}")
                if st.button(_tr("btn_hdr_save"), key=f"fc_hsave_{doc['id']}"):
                    if el < ef or add_months(ef, 12) < el:
                        st.error(_tr("err_period"))
                    elif ef < CUR_MONTH and not has_approved and ef != doc["first_month"]:
                        st.error(_tr("err_past"))
                    else:
                        try:
                            save_header(doc, ef, el, ec, ecm, has_approved)
                            st.success(_tr("hdr_saved"))
                            st.rerun()
                        except Exception as e:
                            st.error(_trf("err_write", e=e))

        # ── таблица SKU × месяц ──
        st.caption(_tr("grid_help") if is_draft else _tr("grid_posted"))
        sku_meta = rows.groupby("sku").agg(sku_type=("sku_type", "first"), sku_name=("sku_name", "first")).reset_index()
        grid = rows.pivot_table(index="sku", columns="month", values="quantity", aggfunc="first", dropna=False)
        grid = grid.reindex(columns=months)
        grid.columns = [month_label(m) for m in months]
        grid = grid.reset_index().merge(sku_meta, on="sku", how="left")
        stat = rows.groupby("sku").agg(n=("status", "size"), a=("status", lambda s: int((s == "approved").sum())),
                                       e=("quantity", lambda s: int(s.isna().sum())),
                                       sup=("status", lambda s: int((s == "superseded").sum()))).reset_index()

        def _state(r):
            if not is_draft:
                return "⟲" if r.sup else _tr("state_all_appr")
            base = _tr("state_all_appr") if r.a == r.n else (_tr("state_none") if r.a == 0 else _trf("state_part", a=r.a, n=r.n))
            return base + (" · " + _trf("state_empty", e=r.e) if r.e else "")
        stat["state"] = [_state(r) for r in stat.itertuples()]
        grid = grid.merge(stat[["sku", "state"]], on="sku", how="left")
        grid["type"] = grid["sku_type"].map({"base": _tr("type_base"), "composite": _tr("type_composite")}).fillna(_tr("type_unknown"))
        mcols = [month_label(m) for m in months]
        grid[_tr("col_total")] = grid[mcols].fillna(0).sum(axis=1).astype(int)
        show_cols = ["sku", "type", "state"] + mcols + [_tr("col_total"), "sku_name"]
        cfg = {"sku": st.column_config.TextColumn(_tr("col_sku"), disabled=True, width="small"),
               "type": st.column_config.TextColumn(_tr("col_type"), disabled=True, width="small"),
               "state": st.column_config.TextColumn(_tr("col_state"), disabled=True, width="small"),
               "sku_name": st.column_config.TextColumn(_tr("col_name"), disabled=True, width="medium"),
               _tr("col_total"): st.column_config.NumberColumn(_tr("col_total"), disabled=True, format="%d")}
        for m in months:
            cfg[month_label(m)] = st.column_config.NumberColumn(month_label(m), min_value=0, step=1, format="%d",
                                                                disabled=(not is_draft) or m < CUR_MONTH)
        edited = st.data_editor(grid[show_cols], column_config=cfg, hide_index=True, use_container_width=True,
                                disabled=not is_draft, key=f"fc_grid_{doc['id']}_{len(rows)}",
                                height=min(560, 38 + 35 * max(1, len(grid))))
        if is_draft and st.button(_tr("btn_save"), type="primary", key=f"fc_save_{doc['id']}"):
            try:
                n, rej = save_grid(doc, rows, edited, months)
                if n:
                    st.success(_trf("saved", n=n))
                elif not rej:
                    st.info(_tr("nothing_changed"))
                if rej:
                    st.warning(_trf("rejected", n=len(rej)) + "\n\n" + "\n".join(f"- {x}" for x in rej[:20]))
                if n:
                    st.rerun()
            except Exception as e:
                st.error(_trf("err_write", e=e))

        with st.expander(_tr("sec_states")):
            st.caption(_tr("states_help"))
            sym = {"unapproved": "○", "approved": "✓", "superseded": "⟲"}
            sm = rows.assign(s=[("" if pd.isna(r.quantity) and r.status == "unapproved" else sym.get(r.status, "?")) for r in rows.itertuples()])
            sm = sm.pivot_table(index="sku", columns="month", values="s", aggfunc="first").reindex(columns=months).fillna("")
            sm.columns = mcols
            st.dataframe(sm, use_container_width=True, height=min(400, 38 + 35 * max(1, len(sm))))

        with st.expander(_tr("sec_prices")):
            st.caption(_tr("prices_help"))
            pg_ = rows.pivot_table(index="sku", columns="month", values="target_price", aggfunc="first", dropna=False).reindex(columns=months)
            pg_.columns = mcols
            pg_ = pg_.reset_index()
            pcfg = {"sku": st.column_config.TextColumn(_tr("col_sku"), disabled=True)}
            for m in months:
                pcfg[month_label(m)] = st.column_config.NumberColumn(month_label(m), min_value=0.0, format="%.2f", disabled=(not is_draft) or m < CUR_MONTH)
            pe = st.data_editor(pg_, column_config=pcfg, hide_index=True, use_container_width=True, disabled=not is_draft,
                                key=f"fc_prices_{doc['id']}_{len(rows)}", height=min(400, 38 + 35 * max(1, len(pg_))))
            if is_draft and st.button(_tr("btn_prices_save"), key=f"fc_psave_{doc['id']}"):
                try:
                    n = save_prices(doc, rows, pe, months)
                    st.success(_trf("prices_saved", n=n)) if n else st.info(_tr("nothing_changed"))
                    if n:
                        st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))

        # ── добавление SKU и действия (черновик) ──
        if is_draft:
            st.markdown(f"##### {_tr('sec_add')}")
            a1, a2, a3 = st.columns([3, 1, 1])
            present = set(rows["sku"])
            cand = sorted((active_matrix | former_matrix | known) - present)
            picked = a1.multiselect(_tr("add_pick"), cand, key=f"fc_add_{doc['id']}",
                                    format_func=lambda s: s if s in active_matrix else (f"{s} · распродажа" if s in former_matrix else f"{s} · нет допуска"))
            if a2.button(_tr("btn_add"), disabled=not picked, key=f"fc_addbtn_{doc['id']}"):
                try:
                    n, rej = add_skus(doc, rows, picked, active_matrix, former_matrix, known)
                    st.success(_trf("add_done", n=n, r=len(rej)))
                    if rej:
                        st.warning("\n".join(f"- {x}" for x in rej[:20]))
                    if n:
                        st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if a3.button(_tr("btn_matrix"), key=f"fc_matrix_{doc['id']}", help="Сценарий 16: добавляются только продажные SKU матрицы, которых ещё нет; существующие строки и значения не трогаются"):
                todo = sorted(active_matrix - present)
                if not todo:
                    st.info(_tr("matrix_none"))
                else:
                    try:
                        n, _ = add_skus(doc, rows, todo, active_matrix, former_matrix, known | active_matrix)
                        st.success(_trf("matrix_added", n=n))
                        st.rerun()
                    except Exception as e:
                        st.error(_trf("err_write", e=e))
            lost = sorted(present - active_matrix - former_matrix) if present else []
            if lost:
                st.warning("SKU без допуска на объекте (строки не удаляются автоматически, сценарий 16): " + ", ".join(lost[:20]))

            st.markdown(f"##### {_tr('sec_actions')}")
            b1, b2 = st.columns(2)
            sel_skus = b1.multiselect(_tr("pick_skus"), sorted(present), key=f"fc_sel_skus_{doc['id']}", placeholder=_tr("all_skus"))
            sel_months = b2.multiselect(_tr("pick_months"), months, format_func=month_label, key=f"fc_sel_months_{doc['id']}", placeholder=_tr("all_months"))
            eff_months = sel_months or months
            c1, c2, c3, c4 = st.columns(4)
            if c1.button(_tr("btn_approve"), type="primary", key=f"fc_appr_{doc['id']}"):
                try:
                    n, empty = approve(doc, rows, sel_skus, eff_months)
                    if empty:
                        st.warning(_trf("approve_empty", cells=", ".join(empty[:15]) + ("…" if len(empty) > 15 else "")))
                    else:
                        st.success(_trf("approved_n", n=n))
                        st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if c2.button(_tr("btn_unapprove"), key=f"fc_unappr_{doc['id']}"):
                try:
                    n = unapprove(doc, rows, sel_skus, eff_months)
                    st.success(_trf("unapproved_n", n=n))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if c3.button(_tr("btn_zeros"), key=f"fc_zeros_{doc['id']}"):
                try:
                    n = fill_zeros(doc, rows)
                    st.success(_trf("zeros_n", n=n))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if c4.button(_tr("btn_delete"), disabled=not sel_skus, key=f"fc_del_{doc['id']}"):
                with_appr = sorted(set(rows[(rows["sku"].isin(sel_skus)) & (rows["status"] == "approved")]["sku"]))
                if with_appr:
                    st.error(_trf("del_has_approved", skus=", ".join(with_appr)))
                else:
                    has_vals = bool(rows[(rows["sku"].isin(sel_skus)) & rows["quantity"].notna()].shape[0])
                    ck = f"fc_del_confirm_{doc['id']}"
                    if has_vals and st.session_state.get(ck) != tuple(sorted(sel_skus)):
                        st.session_state[ck] = tuple(sorted(sel_skus))
                        st.warning(_trf("del_confirm", n=len(sel_skus)))
                    else:
                        try:
                            n = delete_rows(doc, rows, sel_skus)
                            st.session_state.pop(ck, None)
                            st.success(_trf("deleted_n", n=n))
                            st.rerun()
                        except Exception as e:
                            st.error(_trf("err_write", e=e))

            st.markdown(f"##### {_tr('sec_post')}")
            problems = post_checks(doc, rows, active_matrix)
            if problems:
                st.warning(_tr("post_block") + "\n\n" + "\n".join(f"- {p}" for p in problems))
            if st.button(_tr("btn_post"), type="primary", disabled=bool(problems), key=f"fc_post_{doc['id']}"):
                try:
                    k, r = post_document(doc, rows)
                    st.success(_trf("post_ok", n=doc["number"], k=k, r=r))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))

        # ── журнал документа ──
        with st.expander(_tr("sec_doclog")):
            try:
                lg = q("""SELECT changed_at, actor, sku, month, field, old_value, new_value, source
                          FROM kabinet_data.forecast_change_log WHERE document_id = %s ORDER BY changed_at DESC LIMIT 500""", (int(doc["id"]),))
            except Exception as e:
                lg = pd.DataFrame()
                st.error(_trf("err_read", e=e))
            if lg.empty:
                st.caption(_tr("log_empty"))
            else:
                lg["month"] = lg["month"].map(lambda m: month_label(m) if pd.notna(m) else "")
                lg["changed_at"] = pd.to_datetime(lg["changed_at"]).dt.strftime("%d.%m.%Y %H:%M:%S")
                lg.columns = [_tr("log_col_at"), _tr("log_col_actor"), _tr("col_sku"), _tr("log_month"), _tr("log_col_field"), _tr("log_col_old"), _tr("log_col_new"), _tr("log_col_src")]
                st.dataframe(lg, hide_index=True, use_container_width=True, height=min(400, 38 + 35 * len(lg)))

# ───────────────────────────── журнал ─────────────────────────────
with tab_log:
    l1, l2, l3, l4, l5 = st.columns(5)
    d_from = l1.date_input(_tr("log_from"), value=TODAY.replace(day=1), key="fc_log_from")
    d_to = l2.date_input(_tr("log_to"), value=TODAY, key="fc_log_to")
    lo = l3.selectbox(_tr("f_object"), [None] + list(obj_labels.keys()), format_func=lambda k: _tr("all") if k is None else obj_labels[k], key="fc_log_obj")
    lsku = l4.text_input(_tr("log_sku"), key="fc_log_sku")
    lm = l5.selectbox(_tr("log_month"), [None] + [add_months(CUR_MONTH, i) for i in range(-6, 13)],
                      format_func=lambda m: _tr("all") if m is None else month_label(m), key="fc_log_month")
    where, params = ["l.changed_at >= %s", "l.changed_at < %s + INTERVAL '1 day'"], [d_from, d_to]
    if lo:
        ot, oid = lo.split(":")
        where.append("d.object_type = %s AND d.object_id = %s"); params += [ot, int(oid)]
    if lsku.strip():
        where.append("l.sku ILIKE %s"); params.append(f"%{lsku.strip()}%")
    if lm:
        where.append("l.month = %s"); params.append(lm)
    try:
        lg = q(f"""SELECT l.changed_at, l.actor, d.number, COALESCE(m.code, p.name) AS object_name, d.status, l.sku, l.month, l.field,
                          l.old_value, l.new_value, l.source
                   FROM kabinet_data.forecast_change_log l JOIN kabinet_data.forecast_documents d ON d.id = l.document_id
                   LEFT JOIN kabinet_data.marketplaces_new m ON d.object_type = 'marketplace' AND m.id = d.object_id
                   LEFT JOIN kabinet_data.pools p ON d.object_type = 'pool' AND p.id = d.object_id
                   WHERE {' AND '.join(where)} ORDER BY l.changed_at DESC LIMIT 2000""", tuple(params))
    except Exception as e:
        lg = pd.DataFrame()
        st.error(_trf("err_read", e=e))
    if lg.empty:
        st.info(_tr("log_empty"))
    else:
        lg["month"] = lg["month"].map(lambda m: month_label(m) if pd.notna(m) else "")
        lg["changed_at"] = pd.to_datetime(lg["changed_at"]).dt.strftime("%d.%m.%Y %H:%M:%S")
        lg["status"] = lg["status"].map(lambda s: _tr("st_" + s))
        lg.columns = [_tr("log_col_at"), _tr("log_col_actor"), _tr("log_col_doc"), _tr("col_object"), _tr("col_status"), _tr("col_sku"),
                      _tr("log_month"), _tr("log_col_field"), _tr("log_col_old"), _tr("log_col_new"), _tr("log_col_src")]
        st.dataframe(lg, hide_index=True, use_container_width=True, height=min(600, 38 + 35 * len(lg)))
