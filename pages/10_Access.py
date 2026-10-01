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


# Действия, которые журнал пишет сам о себе: открытие экрана, уведомления, досылы.
# Они не рассказывают, что человек СДЕЛАЛ, и по умолчанию прячутся — иначе настоящие
# решения тонут в шуме. Прячутся, а не выбрасываются: переключатель рядом.
СЛУЖЕБНЫЕ = {"admin.open", "notify_new_user", "notify_new_user_wd", "auth_mode_notify"}


def имя_объекта(тип, ид) -> str:
    """«С чем» — человеческим именем, а не кодом.

    У каждого вида объекта своё представление: право — это пара «действие и роль», а
    не строка `forecast.post/admin`; режим входа — слово, а не цифра. Там, где имя
    вывести неоткуда, оставляем как есть: выдумывать красивое имя хуже, чем показать
    то, что записано."""
    тип, ид = as_text(тип), as_text(ид)
    if not тип and not ид:
        return "—"
    if тип == "permission" and "/" in ид:
        действие, роль = ид.split("/", 1)
        return f'{t("auth.action." + действие)} — {ROLE_LABEL.get(роль, роль)}'
    if тип == "mode":
        return t(f"auth.admin.mode_{ид}") if ид in ("0", "1", "2") else ид
    if тип == "user":
        return ид or t("auth.admin.col_email")
    if тип == "page":
        return t("auth.admin.title") if ид == "access" else ид
    if тип == "qa":
        return t("auth.admin.qa")
    if тип == "log":
        return t("auth.admin.actions")
    return ид or тип


# Технические имена писателей — словами. «kabinet-app» в колонке «Кто» не говорит
# ничего тому, кто читает журнал, а «система» рядом с пометкой «запись кода» — это
# ещё и масло масляное.
СИСТЕМНЫЕ = {"система", "kabinet-app", "watchdog", "qa-агент"}


def кто_словом(почта, откуда) -> str:
    почта = as_text(почта, "—")
    if почта in СИСТЕМНЫЕ:
        # у этих имя само и есть объяснение: пометку не добавляем
        return t(f"auth.log.who.{почта}")
    if откуда == "db":
        return f'{почта} · {t("auth.log.via_db")}'
    return почта


def итог_словом(разрешено) -> str:
    return "✓" if bool(разрешено) else t("auth.log.denied")


people = load_people()

tab_people, tab_matrix, tab_qa, tab_idle, tab_logins, tab_actions = st.tabs(
    [t("auth.admin.people"), t("auth.admin.matrix"), t("auth.admin.qa"),
     t("auth.admin.idle"), t("auth.admin.logins"), t("auth.admin.actions")])

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


# ──────────────────────── тестовый вход QA ──────────────────────────
with tab_qa:
    st.caption(t("auth.qa.caption"))
    _вкл = False
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT value FROM kabinet_data.reorder_params
                            WHERE key = 'qa_access_enabled'""")
            _r = cur.fetchone()
            _вкл = bool(_r) and int(_r[0]) == 1
            cur.execute("""SELECT value FROM kabinet_data.reorder_params
                            WHERE key = 'qa_token_days'""")
            _r2 = cur.fetchone()
            _дней = int(_r2[0]) if _r2 else 7
        токены = pd.read_sql("""
            SELECT id, COALESCE(label, '') AS label, created_at, created_by,
                   expires_at, revoked_at, last_used_at, uses
              FROM kabinet_data.qa_tokens ORDER BY id DESC LIMIT 50
        """, conn)
    finally:
        conn.close()

    # Состояние выключателя — первым и словом: «ссылка не работает» и «токен просрочен»
    # это разные причины, и человек должен видеть, которая из них
    (st.success if _вкл else st.warning)(
        t("auth.qa.on") if _вкл else t("auth.qa.off"))
    if not auth.qa_pepper_set():
        # Молча работать без «перца» нельзя: защита ослаблена, и об этом надо сказать
        st.info(t("auth.qa.no_pepper"))

    живых = 0
    if not токены.empty:
        живых = int(sum(1 for r in токены.itertuples()
                        if pd.isna(r.revoked_at) and pd.Timestamp(r.expires_at) > pd.Timestamp.now(tz="UTC")))
    c1, c2 = st.columns([1, 2])
    if c1.button(t("auth.qa.new"), type="primary", key="qa_new"):
        if auth.require("admin", object_type="qa", object_id="token"):
            import secrets as _secrets
            новый = _secrets.token_urlsafe(32)
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    # прежние гасим: два живых токена — это две утечки вместо одной
                    cur.execute("""UPDATE kabinet_data.qa_tokens SET revoked_at = now()
                                    WHERE revoked_at IS NULL""")
                    cur.execute("""INSERT INTO kabinet_data.qa_tokens
                                       (token_hash, label, created_by, expires_at)
                                   VALUES (%s, %s, %s, now() + make_interval(days => %s))""",
                                (auth.qa_hash(новый), "QA", auth.actor(), _дней))
                conn.commit()
            finally:
                conn.close()
            auth.log_action("qa.new_token", True, "qa", "token", f"срок {_дней} дн.")
            # Показываем ОДИН раз: открытый токен не хранится даже у нас
            st.session_state["qa_fresh"] = новый
            st.rerun()
    c2.caption(t("auth.qa.live", n=живых))

    _свежий = st.session_state.pop("qa_fresh", None)
    if _свежий:
        st.success(t("auth.qa.once"))
        st.code(f"?qa={_свежий}", language="text")

    if токены.empty:
        st.caption(t("auth.qa.none"))
    else:
        показ = pd.DataFrame({
            "выдан": [fmt_dt(v) for v in токены["created_at"]],
            "кем": [as_text(v, "—") for v in токены["created_by"]],
            "до": [fmt_dt(v) for v in токены["expires_at"]],
            "состояние": [
                t("auth.qa.st_revoked") if not pd.isna(r.revoked_at)
                else (t("auth.qa.st_expired")
                      if pd.Timestamp(r.expires_at) <= pd.Timestamp.now(tz="UTC")
                      else t("auth.qa.st_live"))
                for r in токены.itertuples()],
            "заходов": [str(int(v)) for v in токены["uses"]],
            "последний": [fmt_dt(v) for v in токены["last_used_at"]],
        })
        st.dataframe(показ, width="stretch", hide_index=True)
        if живых and st.button(t("auth.qa.revoke"), key="qa_revoke"):
            if auth.require("admin", object_type="qa", object_id="revoke"):
                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE kabinet_data.qa_tokens SET revoked_at = now()
                                        WHERE revoked_at IS NULL""")
                    conn.commit()
                finally:
                    conn.close()
                auth.log_action("qa.revoke", True, "qa", "token", "все живые токены погашены")
                st.success(t("auth.qa.revoked"))
                st.rerun()
    st.caption(t("auth.qa.note"))

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
            SELECT ts, email, role, action, COALESCE(object_type, '') AS object_type,
                   COALESCE(object_id, '') AS object_id,
                   allowed, COALESCE(details, '') AS details, COALESCE(via, 'ui') AS via
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
        служебных = int(acts["action"].isin(СЛУЖЕБНЫЕ).sum())
        показать_служебные = st.checkbox(
            t("auth.log.show_service", n=служебных), value=False, key="acts_service")
        сито = acts if показать_служебные else acts[~acts["action"].isin(СЛУЖЕБНЫЕ)]
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
            # «Кто» — почта. Прямая правка в базе помечается рядом: через экран и
            # мимо экрана — разные уровни доверия к записи
            "email": [кто_словом(e, v) for e, v in zip(сито["email"], сито["via"])],
            "section": [t(f"auth.admin.sec.{s}") for s in сито["section"]],
            "action": [t(f"auth.log.act.{a}") for a in сито["action"]],
            "object": [имя_объекта(тип, ид)
                       for тип, ид in zip(сито["object_type"], сито["object_id"])],
            "result": [итог_словом(v) for v in сито["allowed"]],
            "details": [as_text(d) for d in сито["details"]],
        })
        if show.empty:
            st.caption(t("auth.admin.filtered_empty"))
        else:
            st.dataframe(show, width="stretch", hide_index=True, column_config={
                "ts": st.column_config.TextColumn(t("auth.admin.col_ts"), width="small"),
                # широкая намеренно: рядом с почтой стоит пометка «напрямую в базе»,
                # и обрезанная до «напр…» она не значит ничего
                "email": st.column_config.TextColumn(t("auth.log.col_who"), width="large"),
                "section": st.column_config.TextColumn(t("auth.admin.col_section"), width="small"),
                "action": st.column_config.TextColumn(t("auth.log.col_what"), width="large"),
                "object": st.column_config.TextColumn(t("auth.log.col_with"), width="large"),
                # «✓» и «отказано» словом, а не галочкой: галочка в колонке «итог»
                # читается как «отметить», а не как «получилось»
                "result": st.column_config.TextColumn(t("auth.log.col_result"), width="small"),
                "details": st.column_config.TextColumn(t("auth.admin.col_details"), width="medium"),
            })
