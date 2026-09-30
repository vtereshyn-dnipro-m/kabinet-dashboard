# pages/10_Access.py — кто входит в Кабинет: роли, страны, срок, матрица прав, журналы
"""Админка доступа (ТЗ 010).

Своя проверка прав здесь обязательна и не дублирует сайдбар: пункт меню админам
показывает `app.py`, но на страницу можно прийти по прямой ссылке, и решает именно
эта проверка, а не отсутствие ссылки.

Удаления людей отсюда нет: доступ снимается флагом или сроком. Строка нужна журналам —
по удалённой почте потом не понять, кто и что делал.
"""
from datetime import date, datetime

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

# Раздел действия — по префиксу его кода. Отдельной колонки «страница» в журнале нет
# и заводить её незачем: префикс и есть раздел, а два источника одной истины
# разошлись бы в первый же день, когда кто-то добавит действие и забудет про колонку.
SECTION_OF = {"forecast": "forecast", "dict": "dictionaries", "ads": "ads",
              "reorder": "reorder", "incident": "incidents", "admin": "access"}


def section_of(action: str) -> str:
    return SECTION_OF.get(as_text(action).split(".")[0], "other")


def fmt_dt(v) -> str:
    """Дата текстом: пустая ячейка редактора рисуется словом «None» при любом типе."""
    if pd.isna(v):
        return "—"
    return pd.Timestamp(v).strftime("%d.%m.%Y %H:%M")


def fmt_date(v) -> str:
    if pd.isna(v):
        return ""
    return pd.Timestamp(v).strftime("%d.%m.%Y")


def parse_date(s):
    """Строка → дата. Возвращает (значение, ошибка). Пусто — это «без срока», а не ошибка."""
    s = as_text(s).strip()
    if not s:
        return None, None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).date(), None
        except ValueError:
            continue
    return None, s


@st.cache_data(ttl=60)
def load_people():
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT u.email, u.role, u.is_active, COALESCE(u.note, '') AS note,
                   u.access_until, u.first_login_at, u.last_login_at,
                   (u.access_until IS NOT NULL AND u.access_until < current_date) AS expired,
                   COALESCE(string_agg(c.country, ', ' ORDER BY c.country), '') AS countries
              FROM kabinet_data.app_users u
              LEFT JOIN kabinet_data.app_user_countries c ON c.email = u.email
             GROUP BY u.email, u.role, u.is_active, u.note, u.access_until,
                      u.first_login_at, u.last_login_at
             ORDER BY u.email
        """, conn)
    finally:
        conn.close()


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


@st.cache_data(ttl=60)
def load_matrix() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT action, role, allowed FROM kabinet_data.app_permissions
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=60)
def idle_threshold() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'auth_idle_days'")
            row = cur.fetchone()
        return int(row[0]) if row else 30
    except Exception:
        return 30
    finally:
        conn.close()


people = load_people()

tab_people, tab_matrix, tab_idle, tab_logins, tab_actions = st.tabs(
    [t("auth.admin.people"), t("auth.admin.matrix"), t("auth.admin.idle"),
     t("auth.admin.logins"), t("auth.admin.actions")])

# ─────────────────────────────── Люди ───────────────────────────────
with tab_people:
    view = pd.DataFrame({
        "email": people["email"],
        "role": [ROLE_LABEL.get(r, r) for r in people["role"]],
        "countries": [as_text(c) for c in people["countries"]],
        "is_active": [bool(v) for v in people["is_active"]],
        "access_until": [fmt_date(v) for v in people["access_until"]],
        "note": [as_text(n) for n in people["note"]],
        "last": [fmt_dt(v) for v in people["last_login_at"]],
    })
    if bool(people["expired"].any()):
        st.warning(t("auth.admin.some_expired",
                     n=int(people["expired"].sum()),
                     who=", ".join(people.loc[people["expired"], "email"])))
    edited = st.data_editor(
        view, width="stretch", hide_index=True, key="people_editor",
        column_config={
            "email": st.column_config.TextColumn(t("auth.admin.col_email"), disabled=True),
            "role": st.column_config.SelectboxColumn(
                t("auth.admin.col_role"), options=list(LABEL_ROLE.keys()), required=True),
            "countries": st.column_config.TextColumn(
                t("auth.admin.col_countries"), help=t("auth.admin.countries_help")),
            "is_active": st.column_config.CheckboxColumn(t("auth.admin.col_active")),
            "access_until": st.column_config.TextColumn(
                t("auth.admin.col_until"), help=t("auth.admin.until_help")),
            "note": st.column_config.TextColumn(t("auth.admin.col_note")),
            "last": st.column_config.TextColumn(t("auth.admin.col_last"), disabled=True),
        })

    if st.button(t("auth.admin.save"), type="primary", key="save_people"):
        # Право проверяется ЗДЕСЬ, в обработчике, а не только тем, что страница
        # открылась: между отрисовкой и нажатием доступ мог быть снят.
        if auth.require("admin", object_type="page", object_id="access"):
            good = set(known_countries())
            errors, changes = [], []
            for i in range(len(view)):
                email = view.at[i, "email"]
                was = tuple(view.loc[i, ["role", "countries", "is_active", "access_until", "note"]])
                now = (edited.at[i, "role"], as_text(edited.at[i, "countries"]),
                       bool(edited.at[i, "is_active"]), as_text(edited.at[i, "access_until"]),
                       as_text(edited.at[i, "note"]))
                if tuple(was) == now:
                    continue
                role = LABEL_ROLE.get(now[0], auth.VIEWER)
                codes = [c.strip().upper() for c in now[1].split(",") if c.strip()]
                for c in codes:
                    if good and c not in good:
                        errors.append(t("auth.admin.bad_country", v=c, email=email))
                if role == auth.COUNTRY_MANAGER and not codes:
                    errors.append(t("auth.admin.cm_no_countries", email=email))
                until, bad = parse_date(now[3])
                if bad:
                    errors.append(t("auth.admin.bad_date", v=bad, email=email))
                changes.append((email, role, codes, now[2], until, now[4]))
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
                        for email, role, codes, active, until, note in changes:
                            cur.execute("""
                                UPDATE kabinet_data.app_users
                                   SET role = %s, is_active = %s, access_until = %s,
                                       note = NULLIF(%s, '')
                                 WHERE email = %s
                            """, (role, active, until, note, email))
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
                for email, role, codes, active, until, note in changes:
                    auth.log_action("admin.set_access", True, "user", email,
                                    f"роль {role}, страны {','.join(codes) or '—'}, "
                                    f"доступ {'есть' if active else 'снят'}, "
                                    f"срок {until or 'без срока'}")
                load_people.clear()
                auth._load_user.clear()
                st.success(t("auth.admin.saved", n=len(changes)))
                st.rerun()

# ────────────────────────────── Матрица ─────────────────────────────
with tab_matrix:
    st.caption(t("auth.admin.matrix_caption"))
    mx = load_matrix()
    в_базе = sorted(set(mx["action"])) if not mx.empty else []
    в_коде = sorted(auth._MATRIX)
    # Действие, которого в таблице нет, запрещено всем: новая кнопка не должна начать
    # работать раньше, чем кто-то решил, кому она доступна. Молчать об этом нельзя —
    # иначе оно выглядит сломанным, а не незаполненным.
    нет_в_базе = [a for a in в_коде if a not in в_базе]
    if нет_в_базе:
        st.warning(t("auth.admin.missing_actions", n=len(нет_в_базе),
                     what=", ".join(нет_в_базе)))
    лишние = [a for a in в_базе if a not in в_коде]
    if лишние:
        st.caption(t("auth.admin.extra_actions", what=", ".join(лишние)))

    if mx.empty:
        st.warning(t("auth.admin.matrix_empty"))
    else:
        wide = mx.pivot(index="action", columns="role", values="allowed").reindex(columns=ROLES)
        wide = wide.fillna(False).astype(bool).reset_index()
        grid = pd.DataFrame({"action": [t(f"auth.action.{a}") for a in wide["action"]]})
        for r in ROLES:
            grid[r] = [bool(v) for v in wide[r]]
        edited_mx = st.data_editor(
            grid, width="stretch", hide_index=True, key="matrix_editor",
            column_config=dict(
                {"action": st.column_config.TextColumn(t("auth.admin.col_action"), disabled=True)},
                **{r: st.column_config.CheckboxColumn(ROLE_LABEL[r]) for r in ROLES}))
        st.caption(t("auth.admin.matrix_locked"))

        if st.button(t("auth.admin.save"), type="primary", key="save_matrix"):
            if auth.require("admin", object_type="page", object_id="matrix"):
                правки, отказ = [], []
                for i, действие in enumerate(wide["action"]):
                    for r in ROLES:
                        было, стало = bool(wide.at[i, r]), bool(edited_mx.at[i, r])
                        if было == стало:
                            continue
                        if (действие, r) == auth.LOCKED and not стало:
                            отказ.append(t("auth.admin.locked_pair"))
                            continue
                        правки.append((действие, r, стало))
                for e in dict.fromkeys(отказ):
                    st.error(e)
                if not правки and not отказ:
                    st.info(t("auth.admin.nochange"))
                elif правки:
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            for действие, r, стало in правки:
                                cur.execute("""
                                    INSERT INTO kabinet_data.app_permissions
                                        (action, role, allowed, updated_at, updated_by)
                                    VALUES (%s, %s, %s, now(), %s)
                                    ON CONFLICT (action, role) DO UPDATE
                                       SET allowed = EXCLUDED.allowed, updated_at = now(),
                                           updated_by = EXCLUDED.updated_by
                                """, (действие, r, стало, auth.actor()))
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        st.error(t("auth.admin.matrix_failed", e=str(e).splitlines()[0][:200]))
                        правки = []
                    finally:
                        conn.close()
                    if правки:
                        for действие, r, стало in правки:
                            auth.log_action("admin.set_permission", True, "permission",
                                            f"{действие}/{r}",
                                            "разрешено" if стало else "запрещено")
                        load_matrix.clear()
                        auth._matrix.clear()
                        st.success(t("auth.admin.saved", n=len(правки)))
                        st.rerun()

# ───────────────────────── Давно не заходил ─────────────────────────
with tab_idle:
    порог = idle_threshold()
    st.caption(t("auth.admin.idle_caption", n=порог))
    df = people.copy()
    дней = []
    for v in df["last_login_at"]:
        дней.append(None if pd.isna(v) else (pd.Timestamp.now(tz="UTC") - pd.Timestamp(v).tz_convert("UTC")).days)
    df["дней"] = дней
    # «Ни разу не входил» и «давно не заходил» — разные вещи, и первое не «бесконечно
    # давно»: человека могли завести вчера. Показываем обоих, но подписываем по-разному.
    молчат = df[[(d is None) or (d >= порог) for d in df["дней"]]]
    if молчат.empty:
        st.success(t("auth.admin.idle_none", n=порог))
    else:
        show = pd.DataFrame({
            "email": молчат["email"],
            "role": [ROLE_LABEL.get(r, r) for r in молчат["role"]],
            "last": [t("auth.admin.never") if pd.isna(v) else fmt_dt(v)
                     for v in молчат["last_login_at"]],
            "days": [t("auth.admin.never_short") if d is None else str(int(d))
                     for d in молчат["дней"]],
            "active": [bool(v) for v in молчат["is_active"]],
        })
        st.dataframe(show, width="stretch", hide_index=True, column_config={
            "email": st.column_config.TextColumn(t("auth.admin.col_email")),
            "role": st.column_config.TextColumn(t("auth.admin.col_role")),
            "last": st.column_config.TextColumn(t("auth.admin.col_last")),
            "days": st.column_config.TextColumn(t("auth.admin.col_days")),
            "active": st.column_config.CheckboxColumn(t("auth.admin.col_active")),
        })

# ─────────────────────────── Журнал входов ──────────────────────────
with tab_logins:
    conn = get_connection()
    try:
        logins = pd.read_sql("""
            SELECT ts, email, result, COALESCE(reason, '') AS reason
              FROM kabinet_data.app_login_log ORDER BY ts DESC, id DESC LIMIT 500
        """, conn)
    finally:
        conn.close()
    if logins.empty:
        st.caption(t("auth.admin.log_empty"))
    else:
        logins["ts"] = [fmt_dt(v) for v in logins["ts"]]
        logins["result"] = [t(f"auth.admin.res.{as_text(r)}") for r in logins["result"]]
        st.dataframe(logins, width="stretch", hide_index=True, column_config={
            "ts": st.column_config.TextColumn(t("auth.admin.col_ts")),
            "email": st.column_config.TextColumn(t("auth.admin.col_email")),
            "result": st.column_config.TextColumn(t("auth.admin.col_result")),
            "reason": st.column_config.TextColumn(t("auth.admin.col_reason"), width="large"),
        })

# ────────────────────────── Журнал действий ─────────────────────────
with tab_actions:
    conn = get_connection()
    try:
        acts = pd.read_sql("""
            SELECT ts, email, role, action,
                   COALESCE(object_type, '') || COALESCE(' ' || object_id, '') AS object,
                   allowed, COALESCE(details, '') AS details
              FROM kabinet_data.app_action_log ORDER BY ts DESC, id DESC LIMIT 5000
        """, conn)
    finally:
        conn.close()
    if acts.empty:
        st.caption(t("auth.admin.log_empty"))
    else:
        acts["section"] = [section_of(a) for a in acts["action"]]
        acts["ts"] = pd.to_datetime(acts["ts"])
        f1, f2, f3, f4 = st.columns([1.4, 1.2, 1.4, 1.6])
        # Пустой выбор означает «все», а не «ничего»: человек снимает галочки, чтобы
        # перестать фильтровать, а не чтобы получить пустую таблицу.
        люди = f1.multiselect(t("auth.admin.f_who"),
                              sorted({as_text(e) for e in acts["email"] if as_text(e)}),
                              default=[], placeholder=t("auth.admin.f_all"))
        разделы = f2.multiselect(t("auth.admin.f_section"),
                                 sorted(set(acts["section"])), default=[],
                                 format_func=lambda s: t(f"auth.admin.sec.{s}"),
                                 placeholder=t("auth.admin.f_all"))
        действия = f3.multiselect(t("auth.admin.f_action"), sorted(set(acts["action"])),
                                  default=[], format_func=lambda a: t(f"auth.action.{a}"),
                                  placeholder=t("auth.admin.f_all"))
        период = f4.date_input(t("auth.admin.f_period"),
                               value=(acts["ts"].min().date(), acts["ts"].max().date()),
                               key="acts_period")
        сито = acts
        if люди:
            сито = сито[сито["email"].isin(люди)]
        if разделы:
            сито = сито[сито["section"].isin(разделы)]
        if действия:
            сито = сито[сито["action"].isin(действия)]
        if isinstance(период, (tuple, list)) and len(период) == 2:
            с, по = период
            сито = сито[(сито["ts"].dt.date >= с) & (сито["ts"].dt.date <= по)]
        st.caption(t("auth.admin.shown", n=len(сито), all=len(acts)))
        show = pd.DataFrame({
            "ts": [fmt_dt(v) for v in сито["ts"]],
            "email": [as_text(e, "—") for e in сито["email"]],
            "role": [ROLE_LABEL.get(as_text(r), as_text(r, "—")) for r in сито["role"]],
            "section": [t(f"auth.admin.sec.{s}") for s in сито["section"]],
            "action": [t(f"auth.action.{a}") for a in сито["action"]],
            "object": [as_text(o, "—") for o in сито["object"]],
            "allowed": [bool(v) for v in сито["allowed"]],
            "details": [as_text(d) for d in сито["details"]],
        })
        if show.empty:
            st.caption(t("auth.admin.filtered_empty"))
        else:
            st.dataframe(show, width="stretch", hide_index=True, column_config={
                "ts": st.column_config.TextColumn(t("auth.admin.col_ts")),
                "email": st.column_config.TextColumn(t("auth.admin.col_email")),
                "role": st.column_config.TextColumn(t("auth.admin.col_role")),
                "section": st.column_config.TextColumn(t("auth.admin.col_section")),
                "action": st.column_config.TextColumn(t("auth.admin.col_action")),
                "object": st.column_config.TextColumn(t("auth.admin.col_object")),
                "allowed": st.column_config.CheckboxColumn(t("auth.admin.col_allowed")),
                "details": st.column_config.TextColumn(t("auth.admin.col_details"), width="large"),
            })
