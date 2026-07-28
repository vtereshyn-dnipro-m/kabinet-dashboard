"""
6_Dictionaries.py — раздел «📚 Справочники» Кабинета Demand & Supply.

Табы:
  🏭 Склады             kabinet_data.warehouses
  🔗 Цепочки подпитки   kabinet_data.supply_chains
  🌍 Маркетплейсы       kabinet_data.marketplaces
  📦 Пулы               kabinet_data.pools + pool_members
  📏 Нормативы          kabinet_data.coverage_norms

Переводы страницы лежат в этом же файле (словарь TR + функция _tr),
чтобы не раздувать i18n.py сотней ключей dict.*. Текущий язык берётся
из i18n.get_lang() — то есть из того же st.session_state['lang'],
что и на остальных страницах Кабинета.
"""

from datetime import date

import pandas as pd
import streamlit as st

from i18n import init_lang, get_lang

# --- подключение к БД -------------------------------------------------------
# ⚠️ импорт должен совпадать с 4_Reorder.py / 5_Money.py — если там другой
#    путь модуля, поправить только эту строку
try:
    from db import get_connection
except Exception:  # pragma: no cover
    try:
        from utils.db import get_connection
    except Exception:
        from lib.db import get_connection


# ═══════════════════════════════════════════════════════════════════════════
# ПЕРЕВОДЫ
# ═══════════════════════════════════════════════════════════════════════════

TR = {
    "ru": {
        "title": "📚 Справочники",
        "sub": "Настройки, на которых считаются остатки, покрытие и автозаказ",
        "tab_wh": "🏭 Склады", "tab_ch": "🔗 Подпитка", "tab_mp": "🌍 Маркетплейсы",
        "tab_pool": "📦 Пулы", "tab_norm": "📏 Нормативы",
        "save": "💾 Сохранить изменения", "saved": "Сохранено: {n} запис(ей)",
        "nochange": "Изменений нет", "err": "Ошибка сохранения: {e}",
        "wh_hint": "Тип склада и приоритет отгрузки участвуют в расчёте обеспечения. "
                   "Имя, код и связка дублей (canonical) — только для чтения.",
        "ch_hint": "Цепочка подпитки: кто кого пополняет, каким эшелоном и за сколько дней. "
                   "Срок из накладных (ttn_planned) надёжнее экспертного (expert).",
        "ch_add": "➕ Добавить связь подпитки", "ch_receiver": "Склад-получатель",
        "ch_source": "Склад-источник", "ch_exists": "Такая связь уже есть",
        "ch_same": "Получатель и источник не могут совпадать",
        "mp_hint": "Приоритет покрытия: 1 — покрывается первым при распределении запаса.",
        "pool_hint": "Пул — группа маркетплейсов с общим совокупным прогнозом. "
                     "Маркетплейс не может одновременно быть в двух активных пулах.",
        "pool_list": "Пулы", "pool_new": "Новый пул", "pool_name": "Название",
        "pool_comment": "Комментарий", "pool_create": "➕ Создать пул",
        "pool_rename": "✏️ Переименовать", "pool_delete": "🗑 Удалить пул",
        "pool_members": "Состав пула", "pool_select": "Маркетплейсы",
        "pool_from": "Действует с", "pool_to": "Действует по (пусто — бессрочно)",
        "pool_save": "💾 Сохранить состав", "pool_none": "Пулов пока нет — создай первый",
        "pool_conflict": "Уже в другом пуле: {mp}", "pool_created": "Пул создан",
        "pool_deleted": "Пул удалён", "pool_empty_name": "Укажи название пула",
        "norm_hint": "Норматив покрытия в месяцах. Приоритет: сначала норматив SKU, "
                     "потом категории. Периоды одной связки не должны пересекаться.",
        "norm_add": "➕ Добавить норматив", "norm_scope": "Уровень",
        "norm_scope_sku": "SKU", "norm_scope_cat": "Категория",
        "norm_value": "SKU / категория", "norm_country": "Страна",
        "norm_target": "Привязка", "norm_target_mp": "Маркетплейс", "norm_target_pool": "Пул",
        "norm_target_val": "Значение", "norm_min": "Мин, мес", "norm_max": "Макс, мес",
        "norm_from": "С даты", "norm_to": "По дату (пусто — бессрочно)",
        "norm_author": "Автор", "norm_comment": "Комментарий",
        "norm_minmax": "Минимум не может быть больше максимума",
        "norm_overlap": "Период пересекается с существующим нормативом этой связки",
        "norm_added": "Норматив добавлен", "norm_empty": "Заполни значение уровня",
        "norm_list": "Действующие нормативы", "norm_none": "Нормативы ещё не заданы",
        "delete_sel": "🗑 Удалить отмеченные", "del_col": "Удалить",
        "deleted": "Удалено: {n}", "no_data": "Нет данных",
        "col_id": "ID", "col_name": "Название", "col_code": "Код", "col_type": "Тип",
        "col_mp": "Маркетплейс", "col_country": "Страна", "col_prio": "Приоритет",
        "col_ship_prio": "Приоритет отгрузки", "col_active": "Активен",
        "col_canon": "Дубль от", "col_note": "Примечание", "col_comment": "Комментарий",
        "col_echelon": "Эшелон", "col_lead": "Срок, дн", "col_lead_src": "Источник срока",
        "col_sample": "Накладных", "col_wh_sales": "Склад продаж",
        "col_from": "С", "col_to": "По",
    },
    "uk": {
        "title": "📚 Довідники",
        "sub": "Налаштування, на яких рахуються залишки, покриття та автозамовлення",
        "tab_wh": "🏭 Склади", "tab_ch": "🔗 Підживлення", "tab_mp": "🌍 Маркетплейси",
        "tab_pool": "📦 Пули", "tab_norm": "📏 Нормативи",
        "save": "💾 Зберегти зміни", "saved": "Збережено: {n} запис(ів)",
        "nochange": "Змін немає", "err": "Помилка збереження: {e}",
        "wh_hint": "Тип складу та пріоритет відвантаження беруть участь у розрахунку забезпечення. "
                   "Назва, код і звʼязка дублів (canonical) — лише для читання.",
        "ch_hint": "Ланцюг підживлення: хто кого поповнює, яким ешелоном і за скільки днів. "
                   "Термін із накладних (ttn_planned) надійніший за експертний (expert).",
        "ch_add": "➕ Додати звʼязок підживлення", "ch_receiver": "Склад-отримувач",
        "ch_source": "Склад-джерело", "ch_exists": "Такий звʼязок уже є",
        "ch_same": "Отримувач і джерело не можуть збігатися",
        "mp_hint": "Пріоритет покриття: 1 — покривається першим при розподілі запасу.",
        "pool_hint": "Пул — група маркетплейсів зі спільним сукупним прогнозом. "
                     "Маркетплейс не може одночасно бути у двох активних пулах.",
        "pool_list": "Пули", "pool_new": "Новий пул", "pool_name": "Назва",
        "pool_comment": "Коментар", "pool_create": "➕ Створити пул",
        "pool_rename": "✏️ Перейменувати", "pool_delete": "🗑 Видалити пул",
        "pool_members": "Склад пулу", "pool_select": "Маркетплейси",
        "pool_from": "Діє з", "pool_to": "Діє по (порожньо — безстроково)",
        "pool_save": "💾 Зберегти склад", "pool_none": "Пулів поки немає — створи перший",
        "pool_conflict": "Уже в іншому пулі: {mp}", "pool_created": "Пул створено",
        "pool_deleted": "Пул видалено", "pool_empty_name": "Вкажи назву пулу",
        "norm_hint": "Норматив покриття в місяцях. Пріоритет: спершу норматив SKU, "
                     "потім категорії. Періоди однієї звʼязки не мають перетинатися.",
        "norm_add": "➕ Додати норматив", "norm_scope": "Рівень",
        "norm_scope_sku": "SKU", "norm_scope_cat": "Категорія",
        "norm_value": "SKU / категорія", "norm_country": "Країна",
        "norm_target": "Привʼязка", "norm_target_mp": "Маркетплейс", "norm_target_pool": "Пул",
        "norm_target_val": "Значення", "norm_min": "Мін, міс", "norm_max": "Макс, міс",
        "norm_from": "З дати", "norm_to": "По дату (порожньо — безстроково)",
        "norm_author": "Автор", "norm_comment": "Коментар",
        "norm_minmax": "Мінімум не може бути більшим за максимум",
        "norm_overlap": "Період перетинається з наявним нормативом цієї звʼязки",
        "norm_added": "Норматив додано", "norm_empty": "Заповни значення рівня",
        "norm_list": "Чинні нормативи", "norm_none": "Нормативи ще не задані",
        "delete_sel": "🗑 Видалити відмічені", "del_col": "Видалити",
        "deleted": "Видалено: {n}", "no_data": "Немає даних",
        "col_id": "ID", "col_name": "Назва", "col_code": "Код", "col_type": "Тип",
        "col_mp": "Маркетплейс", "col_country": "Країна", "col_prio": "Пріоритет",
        "col_ship_prio": "Пріоритет відвантаження", "col_active": "Активний",
        "col_canon": "Дубль від", "col_note": "Примітка", "col_comment": "Коментар",
        "col_echelon": "Ешелон", "col_lead": "Термін, дн", "col_lead_src": "Джерело терміну",
        "col_sample": "Накладних", "col_wh_sales": "Склад продажів",
        "col_from": "З", "col_to": "По",
    },
    "en": {
        "title": "📚 Dictionaries",
        "sub": "Settings behind stock, coverage and replenishment calculations",
        "tab_wh": "🏭 Warehouses", "tab_ch": "🔗 Supply chains", "tab_mp": "🌍 Marketplaces",
        "tab_pool": "📦 Pools", "tab_norm": "📏 Coverage norms",
        "save": "💾 Save changes", "saved": "Saved: {n} row(s)",
        "nochange": "No changes", "err": "Save failed: {e}",
        "wh_hint": "Warehouse type and shipping priority drive the supply calculation. "
                   "Name, code and duplicate link (canonical) are read-only.",
        "ch_hint": "Supply chain: who replenishes whom, at which echelon and lead time. "
                   "Lead time from invoices (ttn_planned) is more reliable than expert.",
        "ch_add": "➕ Add supply link", "ch_receiver": "Receiver warehouse",
        "ch_source": "Source warehouse", "ch_exists": "This link already exists",
        "ch_same": "Receiver and source must differ",
        "mp_hint": "Coverage priority: 1 is covered first during stock allocation.",
        "pool_hint": "A pool is a group of marketplaces sharing one aggregate forecast. "
                     "A marketplace cannot belong to two active pools.",
        "pool_list": "Pools", "pool_new": "New pool", "pool_name": "Name",
        "pool_comment": "Comment", "pool_create": "➕ Create pool",
        "pool_rename": "✏️ Rename", "pool_delete": "🗑 Delete pool",
        "pool_members": "Pool members", "pool_select": "Marketplaces",
        "pool_from": "Valid from", "pool_to": "Valid to (empty — open-ended)",
        "pool_save": "💾 Save members", "pool_none": "No pools yet — create the first one",
        "pool_conflict": "Already in another pool: {mp}", "pool_created": "Pool created",
        "pool_deleted": "Pool deleted", "pool_empty_name": "Enter a pool name",
        "norm_hint": "Coverage norm in months. Priority: SKU norm first, then category. "
                     "Periods of the same combination must not overlap.",
        "norm_add": "➕ Add norm", "norm_scope": "Scope",
        "norm_scope_sku": "SKU", "norm_scope_cat": "Category",
        "norm_value": "SKU / category", "norm_country": "Country",
        "norm_target": "Target", "norm_target_mp": "Marketplace", "norm_target_pool": "Pool",
        "norm_target_val": "Value", "norm_min": "Min, months", "norm_max": "Max, months",
        "norm_from": "Valid from", "norm_to": "Valid to (empty — open-ended)",
        "norm_author": "Author", "norm_comment": "Comment",
        "norm_minmax": "Min cannot exceed max",
        "norm_overlap": "Period overlaps an existing norm for this combination",
        "norm_added": "Norm added", "norm_empty": "Fill in the scope value",
        "norm_list": "Active norms", "norm_none": "No norms defined yet",
        "delete_sel": "🗑 Delete selected", "del_col": "Delete",
        "deleted": "Deleted: {n}", "no_data": "No data",
        "col_id": "ID", "col_name": "Name", "col_code": "Code", "col_type": "Type",
        "col_mp": "Marketplace", "col_country": "Country", "col_prio": "Priority",
        "col_ship_prio": "Shipping priority", "col_active": "Active",
        "col_canon": "Alias of", "col_note": "Note", "col_comment": "Comment",
        "col_echelon": "Echelon", "col_lead": "Lead, days", "col_lead_src": "Lead source",
        "col_sample": "Invoices", "col_wh_sales": "Sales warehouse",
        "col_from": "From", "col_to": "To",
    },
}


def _lang() -> str:
    """Текущий язык Кабинета (ru/uk/en) из общей i18n-системы."""
    try:
        lg = str(get_lang() or "ru").lower()[:2]
    except Exception:
        lg = str(st.session_state.get("lang", "ru")).lower()[:2]
    return lg if lg in TR else "ru"


def _tr(key: str) -> str:
    """Перевод строки этой страницы (ключи живут в TR, не в i18n.py)."""
    return TR[_lang()].get(key, TR["ru"].get(key, key))


# ═══════════════════════════════════════════════════════════════════════════
# БАЗА: чтение / запись
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120)
def q(sql: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


def _py(v):
    """numpy/pandas → python-типы для psycopg2."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (pd.Timestamp,)):
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
    """statements: список (sql, params). Всё в одной транзакции."""
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


def build_updates(orig: pd.DataFrame, edited: pd.DataFrame, table: str,
                  pk: str, cols) -> list:
    """Собирает UPDATE-ы по изменённым ячейкам."""
    o = orig.set_index(pk)
    e = edited.set_index(pk)
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

tab_wh, tab_ch, tab_mp, tab_pool, tab_norm = st.tabs(
    [_tr("tab_wh"), _tr("tab_ch"), _tr("tab_mp"), _tr("tab_pool"), _tr("tab_norm")]
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
        ed = st.data_editor(
            wh, key="ed_wh", use_container_width=True, height=520,
            hide_index=True, num_rows="fixed",
            disabled=["id", "name", "code", "canonical_id"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "name": st.column_config.TextColumn(_tr("col_name"), width="large"),
                "code": st.column_config.TextColumn(_tr("col_code"), width="small"),
                "type": st.column_config.SelectboxColumn(
                    _tr("col_type"), options=["sales", "storage", "transit", "manufacturer"]),
                "marketplace": st.column_config.TextColumn(_tr("col_mp"), width="small"),
                "country": st.column_config.TextColumn(_tr("col_country"), width="small"),
                "shipping_priority": st.column_config.NumberColumn(
                    _tr("col_ship_prio"), min_value=1, max_value=99, step=1),
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
               r.name AS receiver_name,
               s.name AS source_name,
               c.echelon, c.priority, c.guaranteed_lead_days,
               c.lead_source, c.sample_size, c.is_active, c.comment
        FROM kabinet_data.supply_chains c
        LEFT JOIN kabinet_data.warehouses r ON r.id = c.receiver_warehouse_id
        LEFT JOIN kabinet_data.warehouses s ON s.id = c.source_warehouse_id
        ORDER BY r.name, c.echelon, c.priority
    """)
    wh_all = q("""
        SELECT id, name, COALESCE(code,'') AS code
        FROM kabinet_data.warehouses
        WHERE is_active IS NOT FALSE
        ORDER BY name
    """)
    wh_label = {int(r.id): f"{r['name']} ({r.code})" if r.code else r["name"]
                for _, r in wh_all.iterrows()}
    label_wh = {v: k for k, v in wh_label.items()}

    if ch.empty:
        st.info(_tr("no_data"))
    else:
        ed_ch = st.data_editor(
            ch, key="ed_ch", use_container_width=True, height=460,
            hide_index=True, num_rows="fixed",
            disabled=["id", "receiver_name", "source_name", "lead_source", "sample_size"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "receiver_name": st.column_config.TextColumn(_tr("ch_receiver"), width="medium"),
                "source_name": st.column_config.TextColumn(_tr("ch_source"), width="medium"),
                "echelon": st.column_config.NumberColumn(_tr("col_echelon"), min_value=1, step=1),
                "priority": st.column_config.NumberColumn(_tr("col_prio"), min_value=1, step=1),
                "guaranteed_lead_days": st.column_config.NumberColumn(
                    _tr("col_lead"), min_value=0, step=1),
                "lead_source": st.column_config.TextColumn(_tr("col_lead_src"), width="small"),
                "sample_size": st.column_config.NumberColumn(_tr("col_sample"), width="small"),
                "is_active": st.column_config.CheckboxColumn(_tr("col_active")),
                "comment": st.column_config.TextColumn(_tr("col_comment"), width="large"),
            },
        )
        if st.button(_tr("save"), key="save_ch", type="primary"):
            save_block(ch, ed_ch, "kabinet_data.supply_chains", "id",
                       ["echelon", "priority", "guaranteed_lead_days",
                        "is_active", "comment"])

    with st.expander(_tr("ch_add")):
        c1, c2, c3 = st.columns([2, 2, 1])
        rec = c1.selectbox(_tr("ch_receiver"), list(label_wh.keys()), key="new_ch_rec")
        src = c2.selectbox(_tr("ch_source"), list(label_wh.keys()), key="new_ch_src")
        ech = c3.number_input(_tr("col_echelon"), 1, 9, 1, key="new_ch_ech")
        c4, c5 = st.columns([1, 3])
        lead = c4.number_input(_tr("col_lead"), 0, 180, 14, key="new_ch_lead")
        cmt = c5.text_input(_tr("col_comment"), key="new_ch_cmt")
        if st.button(_tr("ch_add"), key="add_ch"):
            rid, sid = label_wh[rec], label_wh[src]
            if rid == sid:
                st.error(_tr("ch_same"))
            elif not ch.empty and ((ch["receiver_name"] == rec.split(" (")[0]) &
                                   (ch["source_name"] == src.split(" (")[0])).any():
                st.warning(_tr("ch_exists"))
            else:
                try:
                    exec_sql([("""
                        INSERT INTO kabinet_data.supply_chains
                            (receiver_warehouse_id, source_warehouse_id, echelon,
                             priority, guaranteed_lead_days, lead_source, is_active, comment)
                        VALUES (%s,%s,%s,%s,%s,'expert',TRUE,%s)
                        ON CONFLICT (receiver_warehouse_id, source_warehouse_id) DO NOTHING
                    """, [rid, sid, int(ech), 1, int(lead), cmt or None])])
                    st.cache_data.clear()
                    st.success(_tr("saved").format(n=1))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))

# -------------------------------------------------------- маркетплейсы ---
with tab_mp:
    st.caption(_tr("mp_hint"))
    mp = q("""
        SELECT m.id, m.marketplace, m.country, m.coverage_priority,
               m.sales_warehouse_id, w.name AS warehouse_name,
               m.is_active, m.comment
        FROM kabinet_data.marketplaces m
        LEFT JOIN kabinet_data.warehouses w ON w.id = m.sales_warehouse_id
        ORDER BY m.coverage_priority NULLS LAST, m.marketplace
    """)
    if mp.empty:
        st.info(_tr("no_data"))
    else:
        wh_sales = q("""
            SELECT id, name FROM kabinet_data.warehouses
            WHERE type = 'sales' AND is_active IS NOT FALSE ORDER BY name
        """)
        opts = {int(r.id): r["name"] for _, r in wh_sales.iterrows()}
        rev = {v: k for k, v in opts.items()}

        view = mp.copy()
        view["warehouse_name"] = view["sales_warehouse_id"].map(opts)
        ed_mp = st.data_editor(
            view.drop(columns=["sales_warehouse_id"]),
            key="ed_mp", use_container_width=True, height=420,
            hide_index=True, num_rows="fixed",
            disabled=["id", "marketplace", "country"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "marketplace": st.column_config.TextColumn(_tr("col_mp"), width="small"),
                "country": st.column_config.TextColumn(_tr("col_country"), width="small"),
                "coverage_priority": st.column_config.NumberColumn(
                    _tr("col_prio"), min_value=1, max_value=99, step=1),
                "warehouse_name": st.column_config.SelectboxColumn(
                    _tr("col_wh_sales"), options=list(opts.values())),
                "is_active": st.column_config.CheckboxColumn(_tr("col_active")),
                "comment": st.column_config.TextColumn(_tr("col_comment"), width="large"),
            },
        )
        if st.button(_tr("save"), key="save_mp", type="primary"):
            e2 = ed_mp.copy()
            e2["sales_warehouse_id"] = e2["warehouse_name"].map(rev)
            o2 = view.copy()
            save_block(o2, e2, "kabinet_data.marketplaces", "id",
                       ["coverage_priority", "sales_warehouse_id", "is_active", "comment"])

# ------------------------------------------------------------------ пулы ---
with tab_pool:
    st.caption(_tr("pool_hint"))
    pools = q("SELECT id, name, comment FROM kabinet_data.pools ORDER BY name")
    mps = q("""
        SELECT id, marketplace, country FROM kabinet_data.marketplaces
        WHERE is_active IS NOT FALSE ORDER BY marketplace
    """)
    mp_label = {int(r.id): f"{r.marketplace} ({r.country})" for _, r in mps.iterrows()}
    label_mp = {v: k for k, v in mp_label.items()}

    left, right = st.columns([1, 2])

    with left:
        st.markdown(f"**{_tr('pool_list')}**")
        if pools.empty:
            st.info(_tr("pool_none"))
            sel_pool = None
        else:
            names = pools["name"].tolist()
            sel_name = st.radio(" ", names, key="pool_pick", label_visibility="collapsed")
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
                        exec_sql([("INSERT INTO kabinet_data.pools (name, comment) "
                                   "VALUES (%s,%s) ON CONFLICT (name) DO NOTHING",
                                   [nname.strip(), ncomment or None])])
                        st.cache_data.clear()
                        st.success(_tr("pool_created"))
                        st.rerun()
                    except Exception as e:
                        st.error(_tr("err").format(e=e))

    with right:
        if not pools.empty and sel_pool:
            cur_comment = pools.loc[pools["id"] == sel_pool, "comment"].iloc[0]
            c1, c2 = st.columns([3, 1])
            new_cmt = c1.text_input(_tr("pool_comment"), value=cur_comment or "",
                                    key=f"pc_{sel_pool}")
            if c2.button(_tr("pool_rename"), key=f"pr_{sel_pool}"):
                try:
                    exec_sql([("UPDATE kabinet_data.pools SET comment=%s WHERE id=%s",
                               [new_cmt or None, sel_pool])])
                    st.cache_data.clear()
                    st.success(_tr("saved").format(n=1))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))

            st.markdown(f"**{_tr('pool_members')}**")
            members = q(f"""
                SELECT marketplace_id, valid_from, valid_to
                FROM kabinet_data.pool_members WHERE pool_id = {sel_pool}
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
                    SELECT pm.marketplace_id, p.name
                    FROM kabinet_data.pool_members pm
                    JOIN kabinet_data.pools p ON p.id = pm.pool_id
                    WHERE pm.pool_id <> {sel_pool}
                      AND (pm.valid_to IS NULL OR pm.valid_to >= CURRENT_DATE)
                """)
                clash = [mp_label.get(int(r.marketplace_id), str(r.marketplace_id))
                         for _, r in busy.iterrows()
                         if int(r.marketplace_id) in picked_ids]
                if clash:
                    st.error(_tr("pool_conflict").format(mp=", ".join(clash)))
                else:
                    try:
                        stmts = [(f"DELETE FROM kabinet_data.pool_members "
                                  f"WHERE pool_id = %s", [sel_pool])]
                        for mid in picked_ids:
                            stmts.append((
                                "INSERT INTO kabinet_data.pool_members "
                                "(pool_id, marketplace_id, valid_from, valid_to) "
                                "VALUES (%s,%s,%s,%s)",
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
                        ("DELETE FROM kabinet_data.pool_members WHERE pool_id=%s", [sel_pool]),
                        ("DELETE FROM kabinet_data.pools WHERE id=%s", [sel_pool]),
                    ])
                    st.cache_data.clear()
                    st.success(_tr("pool_deleted"))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))

# ------------------------------------------------------------- нормативы ---
with tab_norm:
    st.caption(_tr("norm_hint"))

    mps_n = q("SELECT marketplace, country FROM kabinet_data.marketplaces ORDER BY marketplace")
    pools_n = q("SELECT name FROM kabinet_data.pools ORDER BY name")
    countries = sorted(mps_n["country"].dropna().unique().tolist()) or ["ES"]

    with st.expander(_tr("norm_add"), expanded=True):
        with st.form("add_norm", clear_on_submit=True):
            a1, a2, a3 = st.columns([1, 2, 1])
            scope = a1.selectbox(_tr("norm_scope"), [_tr("norm_scope_sku"), _tr("norm_scope_cat")])
            scope_val = a2.text_input(_tr("norm_value"))
            country = a3.selectbox(_tr("norm_country"), countries)

            b1, b2 = st.columns([1, 2])
            tgt_type = b1.selectbox(_tr("norm_target"),
                                    [_tr("norm_target_mp"), _tr("norm_target_pool")])
            if tgt_type == _tr("norm_target_mp"):
                tgt_opts = mps_n["marketplace"].dropna().unique().tolist()
            else:
                tgt_opts = pools_n["name"].tolist() or ["—"]
            tgt_val = b2.selectbox(_tr("norm_target_val"), tgt_opts)

            c1, c2, c3, c4 = st.columns(4)
            mn = c1.number_input(_tr("norm_min"), 0.0, 24.0, 1.0, step=0.5)
            mx = c2.number_input(_tr("norm_max"), 0.0, 24.0, 3.0, step=0.5)
            vf = c3.date_input(_tr("norm_from"), value=date.today())
            vt = c4.date_input(_tr("norm_to"), value=None)

            d1, d2 = st.columns(2)
            author = d1.text_input(_tr("norm_author"))
            comment = d2.text_input(_tr("norm_comment"))

            if st.form_submit_button(_tr("norm_add"), type="primary"):
                st_scope = "sku" if scope == _tr("norm_scope_sku") else "category"
                st_tgt = "marketplace" if tgt_type == _tr("norm_target_mp") else "pool"
                if not scope_val.strip():
                    st.error(_tr("norm_empty"))
                elif mn > mx:
                    st.error(_tr("norm_minmax"))
                else:
                    ov = q(f"""
                        SELECT 1 FROM kabinet_data.coverage_norms
                        WHERE scope_type = '{st_scope}'
                          AND scope_value = '{scope_val.strip()}'
                          AND country = '{country}'
                          AND target_type = '{st_tgt}'
                          AND target_value = '{tgt_val}'
                          AND daterange(valid_from, COALESCE(valid_to, DATE '9999-12-31'), '[]')
                              && daterange(DATE '{vf}',
                                           DATE '{vt or "9999-12-31"}', '[]')
                        LIMIT 1
                    """)
                    if not ov.empty:
                        st.error(_tr("norm_overlap"))
                    else:
                        try:
                            exec_sql([("""
                                INSERT INTO kabinet_data.coverage_norms
                                    (scope_type, scope_value, country, target_type,
                                     target_value, min_months, max_months,
                                     valid_from, valid_to, comment, author)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """, [st_scope, scope_val.strip(), country, st_tgt, tgt_val,
                                  float(mn), float(mx), vf, vt or None,
                                  comment or None, author or None])])
                            st.cache_data.clear()
                            st.success(_tr("norm_added"))
                            st.rerun()
                        except Exception as e:
                            st.error(_tr("err").format(e=e))

    st.markdown(f"**{_tr('norm_list')}**")
    norms = q("""
        SELECT id, scope_type, scope_value, country, target_type, target_value,
               min_months, max_months, valid_from, valid_to, author, comment
        FROM kabinet_data.coverage_norms
        ORDER BY country, target_value, scope_value, valid_from DESC
    """)
    if norms.empty:
        st.info(_tr("norm_none"))
    else:
        view_n = norms.copy()
        view_n["__del"] = False
        ed_n = st.data_editor(
            view_n, key="ed_norm", use_container_width=True, height=420,
            hide_index=True, num_rows="fixed",
            disabled=["id", "scope_type", "scope_value", "country",
                      "target_type", "target_value", "valid_from"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "scope_type": st.column_config.TextColumn(_tr("norm_scope"), width="small"),
                "scope_value": st.column_config.TextColumn(_tr("norm_value"), width="medium"),
                "country": st.column_config.TextColumn(_tr("col_country"), width="small"),
                "target_type": st.column_config.TextColumn(_tr("norm_target"), width="small"),
                "target_value": st.column_config.TextColumn(_tr("norm_target_val"), width="small"),
                "min_months": st.column_config.NumberColumn(_tr("norm_min"), step=0.5),
                "max_months": st.column_config.NumberColumn(_tr("norm_max"), step=0.5),
                "valid_from": st.column_config.DateColumn(_tr("col_from")),
                "valid_to": st.column_config.DateColumn(_tr("col_to")),
                "author": st.column_config.TextColumn(_tr("norm_author"), width="small"),
                "comment": st.column_config.TextColumn(_tr("col_comment"), width="large"),
                "__del": st.column_config.CheckboxColumn(_tr("del_col"), width="small"),
            },
        )
        s1, s2 = st.columns([1, 1])
        if s1.button(_tr("save"), key="save_norm", type="primary"):
            bad = ed_n[ed_n["min_months"] > ed_n["max_months"]]
            if not bad.empty:
                st.error(_tr("norm_minmax"))
            else:
                save_block(norms, ed_n.drop(columns=["__del"]),
                           "kabinet_data.coverage_norms", "id",
                           ["min_months", "max_months", "valid_to", "author", "comment"])
        if s2.button(_tr("delete_sel"), key="del_norm"):
            ids = [int(i) for i in ed_n.loc[ed_n["__del"], "id"].tolist()]
            if not ids:
                st.info(_tr("nochange"))
            else:
                try:
                    exec_sql([("DELETE FROM kabinet_data.coverage_norms WHERE id = ANY(%s)",
                               [ids])])
                    st.cache_data.clear()
                    st.success(_tr("deleted").format(n=len(ids)))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))
