"""Справочники → «Amazon API»: кто и сколько ходит в Amazon, что кончилось 429 и что не записало данные (21.10.2026).

Один экран вместо пяти мест (решение владельца, пункт 4 плана «закрываем тему квоты»). Данные готовят джобы, здесь
только показываем — своих оценок нет:
- `Kabinet - Amazon API Journal` (раз в час) — отчёты SP-API и запросы Data Kiosk аккаунта по getReports / getQueries:
  `amazon_report_log`, `amazon_dk_query_log`;
- `Kabinet - Amazon Run Check` (раз в час) — прогоны джоб Amazon API: успех, запись в таблицы, 429: `amazon_run_checks`.

Чья джоба создала отчёт, Amazon не говорит. Экран сопоставляет по типу и времени: отчёт типа T, созданный в момент
t, приписан джобе, у которой тип T есть в коде (`amazon_report_types.jobs`) и прогон шёл в момент t. Прогоны в
`amazon_run_checks` — только завершённые и проверенные (Run Check в :50, 15+ мин после конца), поэтому отчёт идущего
прогона сопоставить ещё нечем: «ещё не сопоставлен», пока он новее «сейчас − (самый долгий проверенный прогон джобы
его типа за 10 дней + amazon_check_lag_min + час)» (21.10.2026 без этого всё утро отчёты Sales & Traffic for Tableau,
07:00–10:12, шли как «не опознан»). Джоба без проверенных прогонов за 10 дней (пауза) кандидатом не считается — иначе
её типы висели бы «ещё не сопоставлен» вечно. «Не опознан» — время ожидания вышло, а совпадения нет: ручной запуск,
проба, отчёт самого Amazon. Владелец — система, а не человек.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db.connection import get_connection
from i18n import t
from util import as_text, grid_height

KYIV = ZoneInfo("Europe/Kyiv")
# палитра Кабинета (schedule_view.py)
OWNER_COLOR = {"kabinet": "#1f77b4", "darina": "#f2b134", "listing_suite": "#26a69a", "pending": "#cfd6df",
               "unknown": "#9aa4b2"}
OWNERS = ["kabinet", "darina", "listing_suite", "pending", "unknown"]
WINDOW_H = 24
SLACK = timedelta(minutes=2)          # createdTime у Amazon и границы прогона Databricks — разные часы


def _table_exists(conn, name: str) -> bool:
    return bool(pd.read_sql("SELECT to_regclass(%(n)s) IS NOT NULL AS ok", conn, params={"n": name}).iloc[0, 0])


@st.cache_data(ttl=300)
def _load():
    """Всё за 48 ч. Журнала ещё нет (джоба не включена) — его части None, экран скажет словами."""
    conn = get_connection()
    try:
        jobs = pd.read_sql("""SELECT job_id, job_name, owner, check_write, quiet_days FROM kabinet_data.amazon_api_jobs
                              WHERE is_active""", conn)
        runs = pd.read_sql("""SELECT job_id, job_name, owner, started_at, ended_at, state, wrote, n429, kinds_429
                              FROM kabinet_data.amazon_run_checks WHERE started_at >= now() - interval '48 hours'""",
                           conn)
        # самый долгий проверенный прогон джобы за 10 дней — сколько отчёт может ждать проверки своего прогона
        dur = pd.read_sql("""SELECT job_id, max(extract(epoch FROM ended_at - started_at)) / 60 AS max_min
                             FROM kabinet_data.amazon_run_checks
                             WHERE started_at >= now() - interval '10 days' AND ended_at IS NOT NULL
                             GROUP BY 1""", conn)
        lag = pd.read_sql("SELECT value FROM kabinet_data.reorder_params WHERE key = 'amazon_check_lag_min'", conn)
        pulse = pd.read_sql("""SELECT job_name, last_success_at, note FROM kabinet_data.system_pulse
                               WHERE job_name IN ('Kabinet - Amazon API Journal', 'Kabinet - Amazon Run Check')""",
                            conn)
        rep = dk = types = None
        if _table_exists(conn, "kabinet_data.amazon_report_log"):
            rep = pd.read_sql("""SELECT report_id, report_type, processing_status, created_time, processing_start,
                                        processing_end FROM kabinet_data.amazon_report_log
                                 WHERE created_time >= now() - interval '48 hours'""", conn)
            dk = pd.read_sql("""SELECT query_id, processing_status, created_time, processing_start, processing_end,
                                       dataset FROM kabinet_data.amazon_dk_query_log
                                WHERE created_time >= now() - interval '48 hours'""", conn)
            types = pd.read_sql("SELECT report_type, jobs FROM kabinet_data.amazon_report_types", conn)
        return dict(jobs=jobs, runs=runs, pulse=pulse, rep=rep, dk=dk, types=types,
                    dur={int(r.job_id): float(r.max_min) for r in dur.itertuples() if not pd.isna(r.max_min)},
                    lag_min=float(lag.iloc[0, 0]) if len(lag) else 15.0)
    except Exception:
        return None
    finally:
        conn.close()


def _kyiv(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return pd.Timestamp(v).tz_convert(KYIV).strftime("%d.%m %H:%M")


def _attribute(rep: pd.DataFrame, runs: pd.DataFrame, types: pd.DataFrame, jobs: pd.DataFrame,
               dur=None, lag_min: float = 15.0, now=None) -> pd.DataFrame:
    """Отчёт → джоба по типу и времени (см. шапку модуля). Колонки job_name и owner; не нашлась — «не опознан»."""
    by_name = {as_text(r.job_name): (int(r.job_id), as_text(r.owner)) for r in jobs.itertuples()}
    type_jobs = {}
    for r in types.itertuples():
        names = [as_text(x).split(":", 1)[-1].strip() for x in as_text(r.jobs).split(";") if as_text(x).strip()]
        type_jobs[as_text(r.report_type)] = [by_name[n] for n in names if n in by_name]
    win = {}
    for r in runs.itertuples():
        if pd.isna(r.started_at):
            continue
        end = r.ended_at if not pd.isna(r.ended_at) else pd.Timestamp.now(tz=timezone.utc)
        win.setdefault(int(r.job_id), []).append((r.started_at - SLACK, end + SLACK))
    names = {int(r.job_id): as_text(r.job_name) for r in jobs.itertuples()}
    dur = dur or {}
    now = now if now is not None else pd.Timestamp.now(tz=timezone.utc)
    # до какого момента отчёт может ждать проверки своего прогона — по джобе: самый долгий её прогон + задержка + час
    wait_from = {jid: now - timedelta(minutes=m + lag_min + 60) for jid, m in dur.items()}
    out_job, out_owner = [], []
    for r in rep.itertuples():
        hit, cands = None, type_jobs.get(as_text(r.report_type), [])
        if not pd.isna(r.created_time):
            for jid, owner in cands:
                if any(a <= r.created_time <= b for a, b in win.get(jid, [])):
                    hit = (names.get(jid, ""), owner)
                    break
        if hit:
            out_job.append(hit[0])
            out_owner.append(hit[1])
            continue
        # прогон, который мог его создать, ещё мог не дойти до проверки; джоба без проверенных прогонов — не кандидат
        pending = (not pd.isna(r.created_time)
                   and any(jid in wait_from and r.created_time >= wait_from[jid] for jid, _o in cands))
        out_job.append("")
        out_owner.append("pending" if pending else "unknown")
    rep = rep.copy()
    rep["job_name"], rep["owner"] = out_job, out_owner
    return rep


def _minutes(df: pd.DataFrame) -> pd.Series:
    d = (pd.to_datetime(df["processing_end"], utc=True) - pd.to_datetime(df["processing_start"], utc=True))
    return d.dt.total_seconds() / 60


def render():
    data = _load()
    if data is None:
        st.warning(t("api.load_error"))
        return
    st.caption(t("api.intro"))
    now = pd.Timestamp.now(tz=timezone.utc)
    since = now - timedelta(hours=WINDOW_H)
    pulse = {as_text(r.job_name): r.last_success_at for r in data["pulse"].itertuples()}
    st.caption(t("api.fresh", journal=_kyiv(pulse.get("Kabinet - Amazon API Journal")),
                 check=_kyiv(pulse.get("Kabinet - Amazon Run Check"))))

    runs = data["runs"]
    runs24 = runs[pd.to_datetime(runs["started_at"], utc=True) >= since]
    rep, dk = data["rep"], data["dk"]
    if rep is None:
        st.info(t("api.no_journal"))
    else:
        rep = _attribute(rep, runs, data["types"], data["jobs"], data["dur"], data["lag_min"], now)
    rep24 = rep[pd.to_datetime(rep["created_time"], utc=True) >= since] if rep is not None else None
    dk24 = dk[pd.to_datetime(dk["created_time"], utc=True) >= since] if dk is not None else None

    # ── итог за сутки ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("api.m_reports"), "—" if rep24 is None else f"{len(rep24)}")
    c2.metric(t("api.m_failed"), "—" if rep24 is None else
              f"{int(rep24['processing_status'].isin(['FATAL', 'CANCELLED']).sum())}", help=t("api.m_failed_help"))
    c3.metric(t("api.m_429"), f"{int(pd.to_numeric(runs24['n429'], errors='coerce').fillna(0).sum())}",
              help=t("api.m_429_help"))
    c4.metric(t("api.m_dk"), "—" if dk24 is None else f"{len(dk24)}")

    # ── отчёты по часам и по системе + 429 ──
    if rep24 is not None and len(rep24):
        st.subheader(t("api.h_hours"))
        hours = pd.date_range(since.floor("h"), now.floor("h"), freq="h", tz=timezone.utc)
        rep24 = rep24.assign(h=pd.to_datetime(rep24["created_time"], utc=True).dt.floor("h"))
        fig = go.Figure()
        for ow in OWNERS:
            cnt = rep24[rep24["owner"] == ow].groupby("h").size().reindex(hours, fill_value=0)
            if cnt.sum():
                fig.add_bar(x=[h.tz_convert(KYIV) for h in hours], y=cnt.values, name=t(f"api.owner.{ow}"),
                            marker_color=OWNER_COLOR[ow])
        r429 = runs24.assign(h=pd.to_datetime(runs24["started_at"], utc=True).dt.floor("h"),
                             n=pd.to_numeric(runs24["n429"], errors="coerce").fillna(0))
        q = r429.groupby("h")["n"].sum().reindex(hours, fill_value=0)
        if q.sum():
            fig.add_scatter(x=[h.tz_convert(KYIV) for h in hours], y=q.values, name=t("api.series_429"),
                            mode="lines+markers", line=dict(color="#e8484d"), yaxis="y2")
        fig.update_layout(barmode="stack", height=320, margin=dict(l=10, r=10, t=10, b=10),
                          yaxis=dict(title=t("api.ax_reports")),
                          yaxis2=dict(title=t("api.ax_429"), overlaying="y", side="right", showgrid=False),
                          legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(t("api.hours_note"))

    # ── джобы ──
    st.subheader(t("api.h_jobs"))
    jobs = data["jobs"]
    rows = []
    for j in jobs.itertuples():
        jr = runs[runs["job_id"] == j.job_id].sort_values("started_at")
        last = jr.iloc[-1] if len(jr) else None
        if last is None:
            res = "—"
        elif as_text(last["state"]) != "SUCCESS":
            res = t("api.res_failed", s=as_text(last["state"]))
        elif pd.isna(last["wrote"]):
            res = t("api.res_ok_nocheck")
        elif bool(last["wrote"]):
            res = t("api.res_ok")
        elif not pd.isna(j.quiet_days):
            # законно пишет не каждый прогон (Settlements, SQP) — тревога только после quiet_days без записи
            res = t("api.res_quiet", n=int(j.quiet_days))
        else:
            res = t("api.res_nowrite")
        j24 = runs24[runs24["job_id"] == j.job_id]
        rows.append({t("api.c_job"): as_text(j.job_name), t("api.c_owner"): t(f"api.owner.{as_text(j.owner)}"),
                     t("api.c_last"): _kyiv(last["started_at"]) if last is not None else "—",
                     t("api.c_result"): res,
                     t("api.c_reports"): int((rep24["job_name"] == as_text(j.job_name)).sum()) if rep24 is not None else None,
                     t("api.c_429"): int(pd.to_numeric(j24["n429"], errors="coerce").fillna(0).sum())})
    jt = pd.DataFrame(rows).sort_values([t("api.c_429"), t("api.c_job")], ascending=[False, True])
    st.dataframe(jt, hide_index=True, use_container_width=True, height=grid_height(len(jt)))

    # ── отчёты по типу ──
    if rep24 is not None and len(rep24):
        st.subheader(t("api.h_types"))
        g = rep24.assign(mins=_minutes(rep24)).groupby("report_type").agg(
            n=("report_id", "size"),
            done=("processing_status", lambda s: int((s == "DONE").sum())),
            bad=("processing_status", lambda s: int(s.isin(["FATAL", "CANCELLED"]).sum())),
            med=("mins", "median")).reset_index().sort_values("n", ascending=False)
        g["med"] = g["med"].map(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
        g.columns = [t("api.c_type"), t("api.c_n"), t("api.c_done"), t("api.c_bad"), t("api.c_med")]
        st.dataframe(g, hide_index=True, use_container_width=True, height=grid_height(len(g)))
        st.caption(t("api.types_note"))

    # ── Data Kiosk ──
    if dk24 is not None and len(dk24):
        st.subheader(t("api.h_dk"))
        g = dk24.assign(mins=_minutes(dk24), dataset=dk24["dataset"].fillna("—")).groupby("dataset").agg(
            n=("query_id", "size"),
            bad=("processing_status", lambda s: int(s.isin(["FATAL", "CANCELLED"]).sum())),
            med=("mins", "median")).reset_index().sort_values("n", ascending=False)
        g["med"] = g["med"].map(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
        g.columns = [t("api.c_dataset"), t("api.c_n"), t("api.c_bad"), t("api.c_med")]
        st.dataframe(g, hide_index=True, use_container_width=True, height=grid_height(len(g)))
