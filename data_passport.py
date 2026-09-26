"""Паспорт данных: откуда взята каждая цифра, по какую дату она свежая и когда устарела.

Зачем отдельный модуль, а не подписи по месту. Цифра на экране складывается из двух-трёх
таблиц, которые наполняют разные загрузчики в разное время, и без паспорта единственный
способ узнать, что стоит за числом, — прочитать код страницы. Именно так рождались вопросы
«почему на Обзоре одно, а в Деньгах другое»: данные были из разных срезов, и сказать это
было негде.

Три вещи, которые модуль даёт странице:
  • `banner(page)`  — предупреждение наверху, если данные под цифрами устарели;
  • `tip(page, key)` — текст для ⓘ у конкретной цифры: источник, дата содержимого, кто обновляет;
  • `footer(page)`   — блок «Откуда данные» внизу: таблица источников целиком.

Возраст считается по СОДЕРЖИМОМУ (последняя дата продаж, расчёта, снимка), а не по времени
работы загрузчика: пользователю важно, по какое число цифры, а не когда крутилась джоба.
Пороги берём из `kabinet_data.data_freshness_rules` — там они уже живут для сторожа, и второй
копии в коде быть не должно; если правила на таблицу нет, порог берётся из описания источника
здесь и это видно в паспорте словом «по умолчанию».
"""
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from db.connection import get_connection
from i18n import t


@dataclass(frozen=True)
class Source:
    key: str                  # ключ подсказки: passport.src.<key>
    table: str                # таблица или вью в kabinet_data
    anchor: str               # колонка с датой СОДЕРЖИМОГО
    loader: str               # имя джобы — как в system_pulse и в правиле сторожа
    default_max_age_h: int    # порог, если правила в data_freshness_rules нет
    feeds: tuple = field(default_factory=tuple)   # ключи цифр, которые кормит
    watch: bool = True        # False — дату показываем, но «устарело» не считаем


# Что стоит за цифрами каждой страницы. Порядок — как на экране сверху вниз.
PAGES = {
    "home": (
        Source("economics", "economics_summary", "sales_date", "Kabinet - Economics Loader", 96,
               ("revenue", "margin", "units", "channels")),
        Source("logistics", "economics_logistics", "sales_date", "Kabinet - Economics Loader", 96,
               ("margin",)),
        Source("ads", "ads_spend", "date", "Kabinet - Economics Loader", 96, ("margin",)),
        Source("traffic", "sales_traffic_daily", "snapshot_date", "Kabinet - Sales & Traffic Replica", 72,
               ("ordered", "plan")),
        # план месяца неделями не меняется по делу, а инциденты молчат, когда всё хорошо:
        # у обоих дату показываем, но в «устарело» не записываем — иначе предупреждение
        # висело бы там, где ничего не случилось, и его перестали бы читать
        Source("forecast", "forecast_register", "changed_at", "Kabinet - Forecast Plan Loader", 720,
               ("plan",), watch=False),
        Source("coverage", "coverage_summary", "calc_date", "Kabinet - Coverage Projection", 38, ("coverage",)),
        Source("transfers", "transfer_recommendations", "calc_date", "Kabinet - Stock Loader", 38, ("transfers",)),
        Source("incidents", "incidents", "created_at", "Kabinet - Watchdog", 48, ("incidents",), watch=False),
        Source("reviews", "asin_reviews_daily", "snapshot_date", "Listing Suite Sync Reviews Daily", 72, ("reviews",)),
    ),
    "reorder": (
        Source("reorder", "reorder_recommendations", "calc_date", "Kabinet - Stock Loader", 38,
               ("critical", "warning", "qty", "controlled")),
        Source("transfers", "transfer_recommendations", "calc_date", "Kabinet - Stock Loader", 38,
               ("tr_own", "tr_fba", "tr_qty")),
    ),
}


@st.cache_data(ttl=300, show_spinner=False)
def _state(page: str) -> pd.DataFrame:
    """Свежесть источников страницы: одна дата и один возраст на источник.

    Один запрос на страницу, а не по запросу на таблицу: страниц много, соединение стоит
    дорого, а MAX() по индексированной колонке — копейки. Отсутствующая таблица не роняет
    паспорт: её строка приходит пустой, и в паспорте так и написано.
    """
    srcs = PAGES.get(page, ())
    if not srcs:
        return pd.DataFrame()
    conn = get_connection()
    try:
        have = pd.read_sql(
            """SELECT table_name, column_name FROM information_schema.columns
               WHERE table_schema = 'kabinet_data'""", conn)
        pairs = {(r.table_name, r.column_name) for r in have.itertuples()}
        parts, missing = [], []
        for s in srcs:
            if (s.table, s.anchor) not in pairs:
                missing.append(s.key)
                continue
            parts.append(
                f"SELECT '{s.key}' AS key, MAX({s.anchor})::text AS as_of, "
                f"EXTRACT(EPOCH FROM (now() - MAX({s.anchor})::timestamptz)) / 3600 AS age_h "
                f"FROM kabinet_data.{s.table}")
        df = pd.read_sql(" UNION ALL ".join(parts), conn) if parts else pd.DataFrame(columns=["key", "as_of", "age_h"])
        rules = pd.read_sql(
            """SELECT replace(table_name, 'kabinet_data.', '') AS tbl,
                      COALESCE(max_content_age_hours, max_age_hours) AS max_age_h
               FROM kabinet_data.data_freshness_rules WHERE is_active""", conn)
    except Exception as e:                      # паспорт не имеет права ронять страницу
        return pd.DataFrame({"key": [s.key for s in srcs], "error": str(e)[:200]})
    finally:
        conn.close()

    thr = {r.tbl: r.max_age_h for r in rules.itertuples() if r.max_age_h}
    rows = []
    for s in srcs:
        r = df[df["key"] == s.key]
        limit = thr.get(s.table)
        rows.append({
            "key": s.key, "table": s.table, "anchor": s.anchor, "loader": s.loader,
            "as_of": (r["as_of"].iloc[0] if len(r) and r["as_of"].iloc[0] else None),
            "age_h": (float(r["age_h"].iloc[0]) if len(r) and pd.notna(r["age_h"].iloc[0]) else None),
            "limit_h": limit or s.default_max_age_h,
            "limit_from_db": limit is not None,
            "watch": s.watch,
            "absent": s.key in missing,
        })
    out = pd.DataFrame(rows)
    out["stale"] = [
        bool(w and a is not None and a > l)
        for w, a, l in zip(out["watch"], out["age_h"], out["limit_h"])]
    return out


def _fmt_date(v) -> str:
    if not v:
        return "—"
    try:
        return pd.Timestamp(v).strftime("%d.%m.%Y")
    except Exception:
        return str(v)[:10]


def _age_text(age_h) -> str:
    if age_h is None:
        return "—"
    if age_h < 36:
        return t("passport.age_hours", n=int(age_h))
    return t("passport.age_days", n=int(age_h // 24))


def tip(page: str, metric_key: str, base: str = "") -> str:
    """Текст для ⓘ у цифры: к пояснению самой метрики добавляем, откуда она и по какую дату."""
    st_ = _state(page)
    if st_.empty or "error" in st_.columns:
        return base
    used = [r for r in st_.itertuples() if metric_key in dict(
        (s.key, s.feeds) for s in PAGES[page]).get(r.key, ())]
    if not used:
        return base
    lines = [t("passport.tip_line", src=t(f"passport.src.{r.key}"), date=_fmt_date(r.as_of),
               loader=r.loader) for r in used]
    tail = t("passport.tip_head") + "\n" + "\n".join(f"- {x}" for x in lines)
    return (base + "\n\n" + tail) if base else tail


def banner(page: str) -> None:
    """Предупреждение наверху страницы, когда цифры опираются на устаревшие данные.

    Показываем возраст СОДЕРЖИМОГО и порог, по которому решили, что это «устарело», —
    иначе предупреждение выглядит как «что-то не так», и с ним ничего нельзя сделать.
    """
    st_ = _state(page)
    if st_.empty:
        return
    if "error" in st_.columns:
        st.caption(t("passport.unavailable"))
        return
    bad = [r for r in st_.itertuples() if r.stale or r.absent]
    if not bad:
        return
    items = []
    for r in bad:
        name = t(f"passport.src.{r.key}")
        items.append(t("passport.absent_item", src=name) if r.absent else
                     t("passport.stale_item", src=name, date=_fmt_date(r.as_of),
                       age=_age_text(r.age_h), limit=int(r.limit_h)))
    st.warning(t("passport.stale_head") + "\n\n" + "\n".join(f"- {x}" for x in items))


def footer(page: str) -> None:
    """Блок «Откуда данные» внизу страницы: полный список источников с датами."""
    st_ = _state(page)
    if st_.empty:
        return
    with st.expander(t("passport.title")):
        if "error" in st_.columns:
            st.caption(t("passport.unavailable"))
            return
        st.caption(t("passport.hint"))
        view = pd.DataFrame({
            t("passport.col_src"): [t(f"passport.src.{r.key}") for r in st_.itertuples()],
            t("passport.col_table"): [f"kabinet_data.{r.table}" for r in st_.itertuples()],
            t("passport.col_as_of"): [t("passport.absent_short") if r.absent else _fmt_date(r.as_of)
                                      for r in st_.itertuples()],
            t("passport.col_age"): [_age_text(r.age_h) for r in st_.itertuples()],
            t("passport.col_limit"): [
                (f"{int(r.limit_h)} " + (t("passport.limit_db") if r.limit_from_db else t("passport.limit_code")))
                if r.watch else t("passport.limit_none")
                for r in st_.itertuples()],
            t("passport.col_loader"): [r.loader for r in st_.itertuples()],
            t("passport.col_state"): [
                ("🔴 " + t("passport.state_absent")) if r.absent
                else ("🔴 " + t("passport.state_stale")) if r.stale
                else ("— " if not r.watch else "🟢 " + t("passport.state_fresh"))
                for r in st_.itertuples()],
        })
        st.dataframe(view, hide_index=True, use_container_width=True,
                     height=min(420, 38 + 35 * len(view)))
