"""
6_Dictionaries.py — раздел «📚 Справочники» Кабинета Demand & Supply.

Табы:
  🏭 Склады            kabinet_data.warehouses
  🔗 Подпитка          kabinet_data.supply_chains
  🌍 Маркетплейсы      kabinet_data.marketplaces
  📦 Пулы              kabinet_data.pools + pool_members
  📏 Нормативы         kabinet_data.coverage_norms

Переводы страницы лежат в этом файле (TR + _tr), чтобы не раздувать i18n.py.
Язык берётся из i18n.get_lang() — общий с остальными страницами.
"""

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
        "save": "💾 Сохранить изменения", "saved": "Сохранено: {n} запис(ей)",
        "nochange": "Изменений нет", "err": "Ошибка: {e}", "no_data": "Нет данных",
        "del_col": "Удалить", "delete_sel": "🗑 Удалить отмеченные", "deleted": "Удалено: {n}",
        "wh_hint": "Тип склада и приоритет отгрузки участвуют в расчёте обеспечения. "
                   "Название, код и связка дублей — только для чтения.",
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
        "save": "💾 Зберегти зміни", "saved": "Збережено: {n} запис(ів)",
        "nochange": "Змін немає", "err": "Помилка: {e}", "no_data": "Немає даних",
        "del_col": "Видалити", "delete_sel": "🗑 Видалити відмічені", "deleted": "Видалено: {n}",
        "wh_hint": "Тип складу та пріоритет відвантаження беруть участь у розрахунку. "
                   "Назва, код і звʼязка дублів — лише для читання.",
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
        "save": "💾 Save changes", "saved": "Saved: {n} row(s)",
        "nochange": "No changes", "err": "Error: {e}", "no_data": "No data",
        "del_col": "Delete", "delete_sel": "🗑 Delete selected", "deleted": "Deleted: {n}",
        "wh_hint": "Warehouse type and shipping priority drive supply calculations. "
                   "Name, code and duplicate link are read-only.",
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
                    _tr("col_type"),
                    options=["sales", "storage", "transit", "manufacturer"]),
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

    mps_n = q("SELECT id, code, country FROM kabinet_data.marketplaces ORDER BY code")
    pools_n = q("SELECT id, name FROM kabinet_data.pools ORDER BY name")
    mp_opts = {f"{r.code} ({r.country})": int(r.id) for _, r in mps_n.iterrows()}
    pool_opts = {r["name"]: int(r.id) for _, r in pools_n.iterrows()}

    with st.expander(_tr("norm_add"), expanded=True):
        with st.form("add_norm", clear_on_submit=True):
            a1, a2, a3 = st.columns([2, 1, 2])
            sku_val = a1.text_input(_tr("norm_sku"))
            tgt_type = a2.selectbox(_tr("norm_target"),
                                    [_tr("norm_target_mp"), _tr("norm_target_pool")])
            is_mp = tgt_type == _tr("norm_target_mp")
            opts = mp_opts if is_mp else pool_opts
            tgt_val = a3.selectbox(_tr("norm_target_val"),
                                   list(opts.keys()) or ["—"])

            b1, b2, b3 = st.columns(3)
            mn = b1.number_input(_tr("col_min"), 0, 999, 30, step=5)
            tg = b2.number_input(_tr("col_target"), 0, 999, 60, step=5)
            mx = b3.number_input(_tr("col_max"), 0, 999, 90, step=5)

            if st.form_submit_button(_tr("norm_add"), type="primary"):
                if not sku_val.strip():
                    st.error(_tr("norm_empty"))
                elif not opts:
                    st.error(_tr("norm_no_target"))
                elif not (mn <= tg <= mx):
                    st.error(_tr("norm_order"))
                else:
                    tid = opts[tgt_val]
                    col = "marketplace_id" if is_mp else "pool_id"
                    dup = q(f"""
                        SELECT 1 FROM kabinet_data.coverage_norms
                        WHERE sku = '{sku_val.strip()}' AND {col} = {tid} LIMIT 1
                    """)
                    if not dup.empty:
                        st.warning(_tr("norm_exists"))
                    else:
                        try:
                            exec_sql([(f"""
                                INSERT INTO kabinet_data.coverage_norms
                                    (sku, {col}, min_days, target_days, max_days)
                                VALUES (%s, %s, %s, %s, %s)
                            """, [sku_val.strip(), tid, int(mn), int(tg), int(mx)])])
                            st.cache_data.clear()
                            st.success(_tr("norm_added"))
                            st.rerun()
                        except Exception as e:
                            st.error(_tr("err").format(e=e))

    st.markdown(f"**{_tr('norm_list')}**")
    norms = q("""
        SELECT n.id, n.sku,
               m.code AS marketplace,
               p.name AS pool,
               n.min_days, n.target_days, n.max_days
        FROM kabinet_data.coverage_norms n
        LEFT JOIN kabinet_data.marketplaces m ON m.id = n.marketplace_id
        LEFT JOIN kabinet_data.pools p        ON p.id = n.pool_id
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
            disabled=["id", "sku", "marketplace", "pool"],
            column_config={
                "id": st.column_config.NumberColumn(_tr("col_id"), width="small"),
                "sku": st.column_config.TextColumn(_tr("norm_sku"), width="medium"),
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
                save_block(norms, ed_n.drop(columns=["__del"]),
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
                    st.success(_tr("deleted").format(n=len(ids)))
                    st.rerun()
                except Exception as e:
                    st.error(_tr("err").format(e=e))
