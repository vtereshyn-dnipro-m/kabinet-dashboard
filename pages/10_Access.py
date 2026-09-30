# pages/10_Access.py — кто входит в Кабинет: роли, страны, журналы
"""Админка доступа (ТЗ 010).

Своя проверка прав здесь обязательна и не дублирует сайдбар: пункт меню админам
показывает `app.py`, но на страницу можно прийти по прямой ссылке, и решает именно
эта проверка, а не отсутствие ссылки.

Удаления людей нет намеренно — доступ снимается флагом. Строка нужна журналам: по
удалённой почте потом не понять, кто и что делал.
"""
import pandas as pd
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t
from util import as_text
import auth

init_lang()

st.title(t("auth.admin.title"))

if not auth.can("admin"):
    st.error(t("auth.denied"))
    auth.log_action("admin.open", False, "page", "access")
    st.stop()

st.caption(t("auth.admin.caption"))

_m = auth.mode()
st.info(t("auth.admin.mode", mode=t(f"auth.admin.mode_{_m}")) + "  \n" + t("auth.admin.mode_where"))

ROLES = [auth.VIEWER, auth.COUNTRY_MANAGER, auth.DEMAND_PLANNER, auth.ADMIN]
# В базе роль лежит английским кодом — её читают проверки прав; на экране слово.
# При сохранении подпись переводится обратно, иначе в базу уехало бы «Просмотр»
# и ни одна проверка её бы не узнала (тот же приём, что у типов маршрутов).
ROLE_LABEL = {r: t(f"auth.role.{r}") for r in ROLES}
LABEL_ROLE = {v: k for k, v in ROLE_LABEL.items()}


@st.cache_data(ttl=60)
def load_people():
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT u.email, u.role, u.is_active, COALESCE(u.note, '') AS note,
                   u.first_login_at, u.last_login_at,
                   COALESCE(string_agg(c.country, ', ' ORDER BY c.country), '') AS countries
              FROM kabinet_data.app_users u
              LEFT JOIN kabinet_data.app_user_countries c ON c.email = u.email
             GROUP BY u.email, u.role, u.is_active, u.note, u.first_login_at, u.last_login_at
             ORDER BY u.email
        """, conn)
    finally:
        conn.close()
    return df


@st.cache_data(ttl=600)
def known_countries() -> set:
    """Коды стран из справочника: проверяем ввод по нему, а не по длине строки."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT alpha2 FROM kabinet_data.countries")
            return {r[0].upper() for r in cur.fetchall()}
    except Exception:
        return set()
    finally:
        conn.close()


def fmt_dt(v) -> str:
    """Дата текстом: пустая ячейка в редакторе рисуется словом «None» при любом типе."""
    if pd.isna(v):
        return "—"
    return pd.Timestamp(v).strftime("%d.%m.%Y %H:%M")


people = load_people()

tab_people, tab_logins, tab_actions = st.tabs(
    [t("auth.admin.people"), t("auth.admin.logins"), t("auth.admin.actions")])

with tab_people:
    view = pd.DataFrame({
        "email": people["email"],
        "role": [ROLE_LABEL.get(r, r) for r in people["role"]],
        "countries": [as_text(c) for c in people["countries"]],
        "is_active": [bool(v) for v in people["is_active"]],
        "note": [as_text(n) for n in people["note"]],
        "first": [fmt_dt(v) for v in people["first_login_at"]],
        "last": [fmt_dt(v) for v in people["last_login_at"]],
    })
    edited = st.data_editor(
        view, width="stretch", hide_index=True, key="people_editor",
        column_config={
            "email": st.column_config.TextColumn(t("auth.admin.col_email"), disabled=True),
            "role": st.column_config.SelectboxColumn(
                t("auth.admin.col_role"), options=list(LABEL_ROLE.keys()), required=True),
            "countries": st.column_config.TextColumn(
                t("auth.admin.col_countries"), help=t("auth.admin.countries_help")),
            "is_active": st.column_config.CheckboxColumn(t("auth.admin.col_active")),
            "note": st.column_config.TextColumn(t("auth.admin.col_note")),
            "first": st.column_config.TextColumn(t("auth.admin.col_first"), disabled=True),
            "last": st.column_config.TextColumn(t("auth.admin.col_last"), disabled=True),
        })

    if st.button(t("auth.admin.save"), type="primary"):
        # Право проверяется ЗДЕСЬ, в обработчике, а не только тем, что страница
        # открылась: между отрисовкой и нажатием доступ мог быть снят.
        if auth.require("admin", object_type="page", object_id="access"):
            good = set(known_countries())
            errors, changes = [], []
            for i in range(len(view)):
                email = view.at[i, "email"]
                was = (view.at[i, "role"], view.at[i, "countries"],
                       bool(view.at[i, "is_active"]), view.at[i, "note"])
                now = (edited.at[i, "role"], as_text(edited.at[i, "countries"]),
                       bool(edited.at[i, "is_active"]), as_text(edited.at[i, "note"]))
                if was == now:
                    continue
                role = LABEL_ROLE.get(now[0], auth.VIEWER)
                codes = [c.strip().upper() for c in now[1].split(",") if c.strip()]
                for c in codes:
                    if good and c not in good:
                        errors.append(t("auth.admin.bad_country", v=c, email=email))
                if role == auth.COUNTRY_MANAGER and not codes:
                    errors.append(t("auth.admin.cm_no_countries", email=email))
                changes.append((email, role, codes, now[2], now[3]))
            if errors:
                # одна плохая строка отменяет всё сохранение: половина применённых
                # правок доступа хуже, чем ни одной, — потом не понять, что уже в силе
                for e in errors:
                    st.error(e)
            elif not changes:
                st.info(t("auth.admin.nochange"))
            else:
                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        for email, role, codes, active, note in changes:
                            cur.execute("""
                                UPDATE kabinet_data.app_users
                                   SET role = %s, is_active = %s, note = NULLIF(%s, '')
                                 WHERE email = %s
                            """, (role, active, note, email))
                            cur.execute("DELETE FROM kabinet_data.app_user_countries WHERE email = %s",
                                        (email,))
                            for c in codes:
                                cur.execute("""
                                    INSERT INTO kabinet_data.app_user_countries (email, country)
                                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                                """, (email, c))
                    conn.commit()
                finally:
                    conn.close()
                for email, role, codes, active, note in changes:
                    auth.log_action("admin.set_access", True, "user", email,
                                    f"роль {role}, страны {','.join(codes) or '—'}, "
                                    f"доступ {'есть' if active else 'снят'}")
                load_people.clear()
                auth._load_user.clear()
                st.success(t("auth.admin.saved", n=len(changes)))
                st.rerun()

with tab_logins:
    conn = get_connection()
    try:
        logins = pd.read_sql("""
            SELECT ts, email, result, COALESCE(reason, '') AS reason
              FROM kabinet_data.app_login_log ORDER BY ts DESC LIMIT 500
        """, conn)
    finally:
        conn.close()
    if logins.empty:
        st.caption(t("auth.admin.nochange"))
    else:
        logins["ts"] = [fmt_dt(v) for v in logins["ts"]]
        st.dataframe(logins, width="stretch", hide_index=True, column_config={
            "ts": st.column_config.TextColumn(t("auth.admin.col_ts")),
            "email": st.column_config.TextColumn(t("auth.admin.col_email")),
            "result": st.column_config.TextColumn(t("auth.admin.col_result")),
            "reason": st.column_config.TextColumn(t("auth.admin.col_reason")),
        })

with tab_actions:
    conn = get_connection()
    try:
        acts = pd.read_sql("""
            SELECT ts, email, role, action,
                   COALESCE(object_type, '') || COALESCE(' ' || object_id, '') AS object,
                   allowed, COALESCE(details, '') AS details
              FROM kabinet_data.app_action_log ORDER BY ts DESC LIMIT 500
        """, conn)
    finally:
        conn.close()
    if acts.empty:
        st.caption(t("auth.admin.nochange"))
    else:
        acts["ts"] = [fmt_dt(v) for v in acts["ts"]]
        acts["role"] = [ROLE_LABEL.get(r, as_text(r)) for r in acts["role"]]
        acts["allowed"] = [bool(v) for v in acts["allowed"]]
        st.dataframe(acts, width="stretch", hide_index=True, column_config={
            "ts": st.column_config.TextColumn(t("auth.admin.col_ts")),
            "email": st.column_config.TextColumn(t("auth.admin.col_email")),
            "role": st.column_config.TextColumn(t("auth.admin.col_role")),
            "action": st.column_config.TextColumn(t("auth.admin.col_action")),
            "object": st.column_config.TextColumn(t("auth.admin.col_object")),
            "allowed": st.column_config.CheckboxColumn(t("auth.admin.col_allowed")),
            "details": st.column_config.TextColumn(t("auth.admin.col_details"), width="large"),
        })
