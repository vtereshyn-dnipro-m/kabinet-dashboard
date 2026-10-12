"""Паспорт данных → «Расписание»: когда идут джобы, кто кого ждёт и что менялось (12.10.2026).

Данные готовит джоба `Kabinet - Job Schedule Snapshot` (раз в час, nb/job_schedule_snapshot.py): расписание всех джоб
воркспейса, длительность по каждому запуску дня, какие таблицы джоба пишет и читает (по коду ноутбука и вьюхам) и
история расписаний из журнала аудита. Здесь только показываем: своих вычислений порядка нет, иначе вкладка и сторож
разошлись бы в оценке одного и того же запаса.

Время — по Киеву. Владелец джобы — система (Кабинет, витрина Power BI, Tableau, Listing Suite), а не человек.
Статусы — метками палитры Кабинета, не эмодзи: эмодзи остаются в Telegram.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db.connection import get_connection
from i18n import t
from util import as_text, grid_height

KYIV = ZoneInfo("Europe/Kyiv")
# палитра Кабинета (home.py, 8_CM_Dashboard.py)
RED, AMBER, GREEN, GREY, BLUE = "#e8484d", "#f2b134", "#2e9e5b", "#9aa4b2", "#1f77b4"
SYSTEM_COLOR = {"kabinet": BLUE, "powerbi": AMBER, "tableau": "#7e57c2", "listing_suite": "#26a69a", "other": GREY}
STATUS_COLOR = {"ok": GREEN, "warn": AMBER, "broken": RED, "prev_day": GREY, "event": GREY, "source_event": GREY,
                "success": GREEN, "failed": RED, "running": AMBER, "canceled": GREY, "skipped": GREY}
STATUS_RANK = {"broken": 0, "warn": 1, "ok": 2, "source_event": 3, "event": 4, "prev_day": 5}


@st.cache_data(ttl=300)
def _load():
    """Три таблицы снимка. Нет таблиц или не прочиталось — None: вкладка скажет об этом словами."""
    conn = get_connection()
    try:
        snap = pd.read_sql("SELECT * FROM kabinet_data.job_schedule_snapshot", conn)
        deps = pd.read_sql("SELECT * FROM kabinet_data.job_dependencies", conn)
        changes = pd.read_sql("SELECT * FROM kabinet_data.job_schedule_changes ORDER BY event_time DESC", conn)
        warn = pd.read_sql("SELECT value FROM kabinet_data.reorder_params WHERE key = 'schedule_margin_warn_min'", conn)
        return dict(snap=snap, deps=deps, changes=changes,
                    warn_min=int(float(warn.iloc[0, 0])) if len(warn) else 10)
    except Exception:
        return None
    finally:
        conn.close()


def _js(v):
    """jsonb из psycopg2 приходит уже разобранным, из JSON-файла пробы — тоже; строку разбираем."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def _kyiv(v):
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return None
    ts = pd.Timestamp(v)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    return ts.tz_convert(KYIV)


def _days_text(dows) -> str:
    dows = sorted(set(dows or []))
    if not dows or len(dows) == 7:
        return t("sched.daily")
    return ", ".join(t(f"sched.dow.{d}") for d in dows)


def when_text(kind, slots, paused, cron=None) -> str:
    """«ежедневно 10:40, 16:40», «пн 07:30», «по событию», «вручную»; пауза — словом в конце."""
    slots = _js(slots) or []
    if kind == "event":
        txt = t("sched.kind.event")
    elif kind == "continuous":
        txt = t("sched.kind.continuous")
    elif kind == "manual" or (kind == "cron" and not slots and not cron):
        txt = t("sched.kind.manual")
    elif not slots:
        txt = as_text(cron)
    else:
        by_days = {}
        for s in slots:
            by_days.setdefault(tuple(sorted(s.get("dows") or [])), []).append(s["t"])
        txt = "; ".join(f"{_days_text(d)} {', '.join(sorted(ts))}" for d, ts in by_days.items())
        if any(s.get("monthly") for s in slots):
            txt += " · " + t("sched.monthly")
    return txt + (" · " + t("sched.paused") if bool(paused) else "")


def _dur_text(slots, median) -> str:
    slots = _js(slots) or []
    vals = [s.get("median_min") for s in slots if s.get("median_min") is not None]
    if not vals:
        return "—" if median is None or pd.isna(median) else t("sched.min", n=_fmt_min(median))
    if max(vals) - min(vals) < 1.5:
        return t("sched.min", n=_fmt_min(sum(vals) / len(vals)))
    return t("sched.min", n=" / ".join(_fmt_min(v) for v in vals))


def _fmt_min(v) -> str:
    v = float(v)
    return f"{v:.0f}" if v >= 10 else f"{v:.1f}".replace(".", ",").replace(",0", "")


def _badge(text: str, color: str) -> str:
    """Метка в цветах палитры — как плашка счётчика в меню (app.py): тон фона и цвет текста одного оттенка."""
    return (f"<span style='background:{color}26;color:{color};border:1px solid {color}66;border-radius:10px;"
            f"padding:2px 10px;font-weight:600;font-size:0.9rem;white-space:nowrap'>{text}</span>")


def _color_cells(styler_df, col, kinds):
    """Цвет текста ячейки по статусу — через Styler: в этих таблицах нет фото и ссылок, с которыми он не уживается."""
    def _style(_):
        return [f"color:{STATUS_COLOR.get(k, GREY)};font-weight:600" for k in kinds]
    return styler_df.apply(_style, subset=[col])


def render() -> None:
    data = _load()
    if not data or data["snap"].empty:
        st.info(t("sched.unavailable"))
        return
    snap, deps, changes, warn_min = data["snap"], data["deps"], data["changes"], data["warn_min"]
    now = datetime.now(timezone.utc)
    observed = _kyiv(snap["observed_at"].max())
    sched = snap[snap["schedule_kind"] != "manual"]
    broken = deps[deps["status"] == "broken"]
    ch = changes.copy()
    if not ch.empty:
        ch["when_k"] = ch["event_time"].map(_kyiv)
        ch = ch.sort_values("when_k", ascending=False)
    ch_day = ch[ch["when_k"] >= pd.Timestamp(now).tz_convert(KYIV) - pd.Timedelta(hours=24)] if not ch.empty else ch

    # ── 1. шапка ──
    st.caption(t("sched.hint", warn=warn_min))
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**{t('sched.head.date')}**  \n{datetime.now(KYIV):%d.%m.%Y}  \n"
                f"<span style='color:{GREY}'>{t('sched.head.observed', t=observed.strftime('%H:%M') if observed else '—')}</span>",
                unsafe_allow_html=True)
    c2.markdown(f"**{t('sched.head.jobs')}**  \n{len(sched)} " + t("sched.head.jobs_of", n=len(snap)))
    order = (_badge(t("sched.head.order_ok"), GREEN) if broken.empty
             else _badge(t("sched.head.order_bad", n=len(broken)), RED))
    c3.markdown(f"**{t('sched.head.order')}**  \n{order}", unsafe_allow_html=True)
    c4.markdown(f"**{t('sched.head.changes')}**  \n" +
                (_badge(str(len(ch_day)), AMBER) if len(ch_day) else _badge("0", GREY)), unsafe_allow_html=True)

    # ── 2. джобы ──
    st.markdown(f"#### {t('sched.jobs.title')}")
    changed_recent = {}
    if not ch.empty:
        recent = ch[ch["when_k"] >= pd.Timestamp(now).tz_convert(KYIV) - pd.Timedelta(days=7)]
        for r in recent.itertuples():
            changed_recent.setdefault(int(r.job_id), r.when_k)
    f1, f2 = st.columns([3, 1])
    sys_all = ["kabinet", "powerbi", "tableau", "listing_suite", "other"]
    pick = f1.multiselect(t("sched.f.system"), sys_all, default=[], format_func=lambda s: t(f"sched.sys.{s}"),
                          placeholder=t("sched.f.all"), key="sched_sys")
    only_sched = f2.toggle(t("sched.f.only_sched"), value=True, key="sched_only")
    view = snap.copy()
    if pick:
        view = view[view["system"].isin(pick)]
    if only_sched:
        view = view[view["schedule_kind"] != "manual"]

    def _first(slots):
        sl = _js(slots) or []
        return min((s["t"] for s in sl), default="99:99")
    view = view.assign(_first=view["slots"].map(_first)).sort_values(["_first", "job_name"])
    states = view["last_run_state"].fillna("").tolist()
    tbl = pd.DataFrame({
        t("sched.col.job"): view["job_name"],
        t("sched.col.system"): view["system"].map(lambda s: t(f"sched.sys.{s}")),
        t("sched.col.when"): [when_text(r.schedule_kind, r.slots, r.paused, r.cron) for r in view.itertuples()],
        t("sched.col.duration"): [_dur_text(r.slots, r.median_min) for r in view.itertuples()],
        t("sched.col.last"): [
            (t(f"sched.run.{as_text(r.last_run_state)}") + " · " + _kyiv(r.last_run_start).strftime("%d.%m %H:%M"))
            if _kyiv(r.last_run_start) is not None else "—" for r in view.itertuples()],
        t("sched.col.changed"): [t("sched.changed_on", d=changed_recent[int(r.job_id)].strftime("%d.%m"))
                                 if int(r.job_id) in changed_recent else "" for r in view.itertuples()],
        t("sched.col.writes"): [", ".join(x.split(".", 1)[-1] for x in (r.writes or [])) or "—"
                                for r in view.itertuples()],
    })
    sty = _color_cells(tbl.style, t("sched.col.last"), states)
    sty = sty.apply(lambda col: [f"color:{AMBER};font-weight:600" if v else "" for v in col],
                    subset=[t("sched.col.changed")])
    st.dataframe(sty, hide_index=True, use_container_width=True, height=grid_height(len(tbl), 14),
                 column_config={t("sched.col.writes"): st.column_config.TextColumn(width="large"),
                                t("sched.col.job"): st.column_config.TextColumn(width="medium")})

    # ── 3. зависимости ──
    st.markdown(f"#### {t('sched.deps.title')}")
    st.caption(t("sched.deps.hint", warn=warn_min))
    show_all = st.toggle(t("sched.deps.show_all"), value=False, key="sched_deps_all")
    d = deps.copy()
    if not show_all:
        d = d[d["status"].isin(["broken", "warn", "ok"])]
    d = d.assign(_r=d["status"].map(STATUS_RANK), _m=d["margin_min"].fillna(10 ** 6)).sort_values(
        ["_r", "_m", "our_job", "our_time"])
    if d.empty:
        st.info(t("sched.deps.none"))
    else:
        kinds = d["status"].tolist()
        dt_ = pd.DataFrame({
            t("sched.col.our"): d["our_job"],
            t("sched.col.waits"): [f"{r.source_job} · {t(f'sched.sys.{r.source_system}')}" for r in d.itertuples()],
            t("sched.col.tables"): [", ".join(x.split(".", 1)[-1] for x in (r.tables or [])) for r in d.itertuples()],
            t("sched.col.src_end"): [as_text(r.source_end, "—") for r in d.itertuples()],
            t("sched.col.we_start"): [t("sched.kind.event") if r.our_time == "event" else r.our_time
                                      for r in d.itertuples()],
            t("sched.col.margin"): [("—" if pd.isna(r.margin_min) else t("sched.min", n=int(r.margin_min)))
                                    for r in d.itertuples()],
            t("sched.col.status"): [t(f"sched.st.{r.status}") + (
                (" · " + _days_text([int(x) for x in str(r.days).split(",")])) if as_text(r.days) else "")
                for r in d.itertuples()],
        })
        sty = _color_cells(dt_.style, t("sched.col.status"), kinds)
        sty = _color_cells(sty, t("sched.col.margin"), kinds)
        st.dataframe(sty, hide_index=True, use_container_width=True, height=grid_height(len(dt_), 12),
                     column_config={t("sched.col.tables"): st.column_config.TextColumn(width="medium")})

    # ── 4. шкала дня ──
    st.markdown(f"#### {t('sched.gantt.title')}")
    st.caption(t("sched.gantt.hint"))
    _gantt(view)

    # ── 5. изменения расписания ──
    st.markdown(f"#### {t('sched.changes.title')}")
    if ch.empty:
        st.info(t("sched.changes.none"))
    else:
        def _sch(v):
            v = _js(v)
            if not v:
                return t("sched.changes.unknown")
            return when_text(v.get("kind"), v.get("slots"), v.get("paused"), v.get("cron"))
        ct = pd.DataFrame({
            t("sched.col.when_changed"): ch["when_k"].map(lambda x: x.strftime("%d.%m %H:%M")),
            t("sched.col.job"): ch["job_name"],
            t("sched.col.system"): ch["system"].map(lambda s: t(f"sched.sys.{s}")),
            t("sched.col.before"): ch["before"].map(_sch),
            t("sched.col.after"): ch["after"].map(_sch),
            t("sched.col.affects"): [", ".join(r.affected_jobs) if bool(r.affects_ours) and r.affected_jobs is not None
                                     and len(r.affected_jobs) else t("sched.changes.no")
                                     for r in ch.itertuples()],
        })
        aff = ["warn" if bool(x) else "prev_day" for x in ch["affects_ours"]]
        sty = _color_cells(ct.style, t("sched.col.affects"), aff)
        st.dataframe(sty, hide_index=True, use_container_width=True, height=grid_height(len(ct), 10),
                     column_config={t("sched.col.affects"): st.column_config.TextColumn(width="large")})

    # ── 6. all-purpose кластер ──
    st.markdown(f"#### {t('sched.cluster.title')}")
    ap = snap[snap["cluster_kind"] == "all_purpose"].copy()
    if ap.empty:
        st.info(t("sched.cluster.none"))
    else:
        ap = ap.assign(_first=ap["slots"].map(_first)).sort_values(["cluster_name", "_first"])
        st.caption(t("sched.cluster.hint", n=len(ap)))
        at = pd.DataFrame({
            t("sched.col.cluster"): ap["cluster_name"].fillna("—"),
            t("sched.col.job"): ap["job_name"],
            t("sched.col.system"): ap["system"].map(lambda s: t(f"sched.sys.{s}")),
            t("sched.col.when"): [when_text(r.schedule_kind, r.slots, r.paused, r.cron) for r in ap.itertuples()],
            t("sched.col.duration"): [_dur_text(r.slots, r.median_min) for r in ap.itertuples()],
        })
        st.dataframe(at, hide_index=True, use_container_width=True, height=grid_height(len(at), 12))


def _gantt(view: pd.DataFrame) -> None:
    """Полоса на каждый запуск 06:00–20:00, длина = обычная длительность этого запуска (минимум 3 минуты, чтобы
    короткие джобы были видны). Цвет — система-владелец."""
    day = datetime.now(KYIV).date()
    base = datetime(day.year, day.month, day.day, tzinfo=KYIV)
    lo, hi = base + timedelta(hours=6), base + timedelta(hours=20)
    rows = []
    for r in view.itertuples():
        for s in _js(r.slots) or []:
            h, m = map(int, s["t"].split(":"))
            start = base + timedelta(hours=h, minutes=m)
            dur = s.get("median_min") or r.median_min or 1
            dur = 1 if pd.isna(dur) else float(dur)
            end = start + timedelta(minutes=max(dur, 3))
            if end < lo or start > hi:
                continue
            rows.append(dict(job=r.job_name, system=r.system, start=start, end=end, t=s["t"], dur=dur))
    if not rows:
        st.info(t("sched.gantt.none"))
        return
    g = pd.DataFrame(rows)
    order = g.groupby("job")["start"].min().sort_values().index.tolist()
    fig = go.Figure()
    for sysk, part in g.groupby("system"):
        fig.add_trace(go.Bar(
            base=part["start"], x=(part["end"] - part["start"]).dt.total_seconds() * 1000, y=part["job"],
            orientation="h", name=t(f"sched.sys.{sysk}"), marker_color=SYSTEM_COLOR.get(sysk, GREY),
            customdata=list(zip(part["t"], part["dur"].map(_fmt_min))),
            hovertemplate="%{y}<br>%{customdata[0]} · %{customdata[1]} " + t("sched.min_short") + "<extra></extra>"))
    now_k = datetime.now(KYIV)
    fig.update_layout(
        barmode="overlay", height=max(320, 22 * len(order) + 90), margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(type="date", range=[lo, hi], tickformat="%H:%M", dtick=3600000, showgrid=True),
        yaxis=dict(categoryorder="array", categoryarray=order[::-1], automargin=True, tickfont=dict(size=11)),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))
    if lo <= now_k <= hi:
        fig.add_vline(x=now_k, line_width=1, line_dash="dot", line_color=GREY)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
