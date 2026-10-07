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
from util import as_text


@dataclass(frozen=True)
class Source:
    key: str                  # ключ подсказки: passport.src.<key>
    table: str                # таблица или вью в kabinet_data
    anchor: str               # колонка с датой СОДЕРЖИМОГО
    loader: str               # имя джобы — как в system_pulse и в правиле сторожа
    default_max_age_h: int    # порог, если правила в data_freshness_rules нет
    feeds: tuple = field(default_factory=tuple)   # ключи цифр, которые кормит
    watch: bool = True        # False — дату показываем, но «устарело» не считаем
    # Условие на строки таблицы. Нужно там, где таблицу пишут несколько загрузчиков с разным
    # смыслом даты: `MAX` по всей таблице тогда показывает самого быстрого писателя, а цифру
    # на экране кормит другой. Ровно так остаток FBA выпал из покрытия (см. AGENTS.md).
    where: str = ""
    # Ключ порога в `reorder_params`, если правило свежести на таблицу описывает НЕ то же самое.
    # У `stock_local` правило про всю таблицу (её каждый день пишет Mirakl), а нас интересует
    # возраст одних строк FBA — порог у них свой, и он тот же, что читает сторож.
    param_key: str = ""


# Что стоит за цифрами каждой страницы. Порядок — как на экране сверху вниз.
PAGES = {
    "home": (
        Source("economics", "economics_summary", "sales_date", "Kabinet - Economics Loader", 96,
               ("revenue", "margin", "units", "channels")),
        Source("logistics", "economics_logistics", "sales_date", "Kabinet - Economics Loader", 96,
               ("margin",)),
        Source("ads", "ads_spend", "date", "Kabinet - Economics Loader", 96, ("margin",)),
        # ACOS и TACOS по формулам Power BI Дарины: день × рынок, SB с продажами по купленным ASIN
        Source("ads_market", "ads_market_daily", "date", "Kabinet - Economics Loader", 96, ("acos", "tacos")),
        # возвраты, вернувшие себестоимость в маржу: FBA — по оценке Amazon, Мадрид — по приёмке Odoo в годный запас.
        # Годные возвраты редки, и дни без них — норма, поэтому «устарело» по этой дате не считаем
        Source("returns", "v_returns_cogs_credit", "return_date", "Kabinet - Returns Loader", 96, ("margin",),
               watch=False),
        Source("traffic", "sales_traffic_daily", "snapshot_date", "Kabinet - Sales & Traffic Replica", 72,
               ("ordered", "ordered_all", "plan", "tacos")),
        # план месяца неделями не меняется по делу, а инциденты молчат, когда всё хорошо:
        # у обоих дату показываем, но в «устарело» не записываем — иначе предупреждение
        # висело бы там, где ничего не случилось, и его перестали бы читать
        Source("forecast", "forecast_register", "changed_at", "Kabinet - Forecast Plan Loader", 720,
               ("plan",), watch=False),
        # Остаток FBA — отдельной строкой, хотя лежит в той же `stock_local`, что офферы Mirakl:
        # у них разный смысл `snapshot_date` (у FBA это дата отчёта Amazon, у Mirakl — сегодня),
        # и без фильтра по источнику возраст считался бы по Mirakl. Порог — `stock_fba_max_age_hours`,
        # тот же, что у проверки сторожа `[STOCK_FBA]`: одно число, два читателя.
        Source("fba_stock", "stock_local", "snapshot_date", "Kabinet - Stock Loader", 72,
               ("coverage", "stock"), where="source = 'ledger-summary'",
               param_key="stock_fba_max_age_hours"),
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
    # ── Остатки ──────────────────────────────────────────────────────────
    # Остаток FBA — снова отдельной строкой с фильтром по источнику: `stock_local` пишут
    # несколько загрузчиков, и у них разный смысл `snapshot_date` (см. Source.where).
    "stock": (
        Source("fba_stock", "stock_local", "snapshot_date", "Kabinet - Stock Loader", 72,
               ("stock", "countries"), where="source = 'ledger-summary'",
               param_key="stock_fba_max_age_hours"),
        Source("mirakl_stock", "stock_local", "snapshot_date", "Kabinet - LM Orders Loader", 48,
               ("stock",), where="source <> 'ledger-summary'"),
        Source("coverage", "coverage_summary", "calc_date", "Kabinet - Coverage Projection", 38,
               ("deficit_soon", "deficit_later", "overstock", "secured")),
        Source("projection", "coverage_projection", "calc_date", "Kabinet - Coverage Projection", 38,
               ("deficit_soon",)),
        Source("ledger", "fba_ledger_detail", "event_date", "FBA Ledger Detail Loader", 72, ("moves",)),
        # Резерв к отгрузке приезжает из Odoo своим путём — через остатки своих складов,
        # а не из отчётов Amazon, поэтому у него отдельная строка паспорта: если встанет
        # именно эта выгрузка, колонка «Резерв / к отгрузке» молча застынет.
        Source("reserve", "warehouse_stock", "snapshot_date", "Kabinet - Stock Loader", 38, ("reserve",)),
    ),
    # ── Деньги ───────────────────────────────────────────────────────────
    "money": (
        Source("economics", "economics_summary", "sales_date", "Kabinet - Economics Loader", 96,
               ("ordered", "revenue", "net", "cogs", "cm")),
        Source("logistics", "economics_logistics", "sales_date", "Kabinet - Economics Loader", 96,
               ("logistics", "cm")),
        Source("ads", "ads_spend", "date", "Kabinet - Economics Loader", 96, ("ads", "cm")),
        Source("traffic", "sales_traffic_daily", "snapshot_date", "Kabinet - Sales & Traffic Replica", 72,
               ("ordered", "plan")),
        Source("shipments", "shipment_facts", "shipped_date", "Kabinet - Shipment Facts", 48, ("plan",)),
        Source("settlements", "raw_amazon_settlements", "posted_date", "Kabinet - Settlements Loader", 240,
               ("cm_settle",), watch=False),
        Source("forecast", "forecast_register", "changed_at", "Kabinet - Forecast Plan Loader", 720,
               ("plan",), watch=False),
    ),
    # ── Прогноз ──────────────────────────────────────────────────────────
    # Реестр меняется от руки: человек проводит документ тогда, когда решил, и «устарело»
    # тут не про данные, а про решение — поэтому watch=False у всех строк.
    "forecast": (
        Source("forecast", "forecast_register", "changed_at", "Kabinet - Forecast Plan Loader", 720,
               ("docs", "cells"), watch=False),
        Source("fc_docs", "forecast_documents", "created_at", "Kabinet - Forecast Plan Loader", 720,
               ("docs",), watch=False),
        Source("sku", "sku_master", "updated_at", "Kabinet - SKU Master Loader", 48, ("sku",)),
        Source("admissions", "assortment_admissions", "updated_at", "Kabinet - Assortment Matrix Loader", 48,
               ("admissions",)),
    ),
    # ── Инциденты ────────────────────────────────────────────────────────
    "incidents": (
        Source("incidents", "incidents", "created_at", "Kabinet - Watchdog", 48,
               ("open", "critical", "oldest"), watch=False),
        Source("fba_stock", "stock_local", "snapshot_date", "Kabinet - Stock Loader", 72, ("stock",),
               where="source = 'ledger-summary'", param_key="stock_fba_max_age_hours"),
        Source("reorder", "reorder_recommendations", "calc_date", "Kabinet - Stock Loader", 38, ("reorder",)),
        Source("reserve", "warehouse_stock", "snapshot_date", "Kabinet - Stock Loader", 38, ("reserve",)),
    ),
    # ── Отзывы ───────────────────────────────────────────────────────────
    "reviews": (
        Source("reviews", "asin_reviews_daily", "snapshot_date", "Listing Suite Sync Reviews Daily", 72,
               ("rating", "count", "new")),
        Source("requests", "review_request_log", "checked_at", "Kabinet - Review Requests (Morning)", 48,
               ("requests", "sent")),
        Source("orders", "orders_history", "purchase_date", "Kabinet - Orders Loader", 48, ("eligible",)),
    ),
    # ── Реклама ──────────────────────────────────────────────────────────
    "ads": (
        Source("amc", "v_amc_attribution", "report_date", "AMC Collect", 72,
               ("campaigns", "no_sales")),
        # карточки ACOS, TACOS, расход и продажи с рекламы — по формулам Power BI Дарины (ad_ratios.py)
        Source("ads_market", "ads_market_daily", "date", "Kabinet - Economics Loader", 96,
               ("acos", "tacos", "spend", "ad_sales")),
        Source("traffic", "sales_traffic_daily", "snapshot_date", "Kabinet - Sales & Traffic Replica", 72,
               ("tacos",)),
        # ads_spend страница «Реклама» не читает вовсе (строка = SKU, продаж SB в ней нет) — в паспорте её нет
        Source("ads_alerts", "ads_alerts", "calc_date", "Kabinet - Ads Alerts", 48, ("alerts",)),
        # журнал кнопок: пишется только когда человек нажал, «устарел» он по делу не бывает
        Source("ads_actions", "ads_actions", "created_at", "—", 720, ("actions",), watch=False),
    ),
    # ── Справочники ──────────────────────────────────────────────────────
    # Справочники правятся руками, и «давно не менялся» здесь — норма, а не тревога.
    # Следим только за теми, что наполняет загрузчик: если он встал, справочник тихо отстанет.
    "dictionaries": (
        Source("sku", "sku_master", "updated_at", "Kabinet - SKU Master Loader", 48, ("sku",)),
        Source("peid", "product_entities", "updated_at", "Kabinet - Product Entities Loader", 48, ("peid",)),
        Source("admissions", "assortment_admissions", "updated_at", "Kabinet - Assortment Matrix Loader", 48,
               ("matrix",)),
        # Перевод ERP: им подписаны категории в английском интерфейсе. Следим, потому что
        # реплику наполняет загрузчик — встанет он, и английские названия тихо отстанут.
        Source("translation", "raw_erp_translation_en", "loaded_at", "Kabinet - SKU Master Loader", 48,
               ("categories",)),
        Source("warehouses", "warehouses", "created_at", "—", 720, ("wh",), watch=False),
        Source("chains", "supply_chains", "updated_at", "—", 720, ("chains",), watch=False),
        Source("marketplaces", "marketplaces_new", "created_at", "—", 720, ("mp",), watch=False),
    ),
    # ── Площадки (CM Dashboard) ──────────────────────────────────────────
    "cm": (
        Source("economics", "economics_summary", "sales_date", "Kabinet - Economics Loader", 96,
               ("revenue", "cm")),
        Source("mirakl_stock", "stock_local", "snapshot_date", "Kabinet - LM Orders Loader", 48, ("stock",),
               where="source <> 'ledger-summary'"),
        Source("parity", "price_parity", "updated_at", "Kabinet - Price Parity", 48, ("parity",)),
        Source("incidents", "incidents", "created_at", "Kabinet - Watchdog", 48, ("health",), watch=False),
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
                f"FROM kabinet_data.{s.table}" + (f" WHERE {s.where}" if s.where else ""))
        df = pd.read_sql(" UNION ALL ".join(parts), conn) if parts else pd.DataFrame(columns=["key", "as_of", "age_h"])
        rules = pd.read_sql(
            """SELECT replace(table_name, 'kabinet_data.', '') AS tbl,
                      COALESCE(max_content_age_hours, max_age_hours) AS max_age_h
               FROM kabinet_data.data_freshness_rules WHERE is_active""", conn)
        params = pd.read_sql("SELECT key, value::numeric AS v FROM kabinet_data.reorder_params", conn)
        # последнее звено: откуда загрузчик берёт данные у площадки и как часто она их обновляет.
        # Живёт в своей таблице, потому что data_freshness_rules принадлежит владельцу базы —
        # колонок туда роль Кабинета не добавит
        origins = pd.read_sql(
            """SELECT replace(table_name, 'kabinet_data.', '') AS tbl,
                      platform_source, platform_refresh, our_refresh, verdict, note,
                      reconcile_with, reconciled_at, reconcile_result,
                      darina_method, darina_verdict, darina_reason
               FROM kabinet_data.data_source_origins""", conn)
    except Exception as e:                      # паспорт не имеет права ронять страницу
        return pd.DataFrame({"key": [s.key for s in srcs], "error": str(e)[:200]})
    finally:
        conn.close()

    thr = {r.tbl: r.max_age_h for r in rules.itertuples() if r.max_age_h}
    prm = {r.key: float(r.v) for r in params.itertuples() if r.v is not None}
    org = {r.tbl: r for r in origins.itertuples()}
    rows = []
    for s in srcs:
        r = df[df["key"] == s.key]
        # порог: сначала свой ключ настройки, если объявлен, потом правило на таблицу
        limit = prm.get(s.param_key) if s.param_key else thr.get(s.table)
        limit_src = "param" if (s.param_key and limit is not None) else ("db" if limit is not None else "code")
        o = org.get(s.table)
        rows.append({
            "key": s.key, "table": s.table, "anchor": s.anchor, "loader": s.loader,
            "platform_source": (o.platform_source if o else None),
            "platform_refresh": (o.platform_refresh if o else None),
            "our_refresh": (o.our_refresh if o else None),
            "verdict": (o.verdict if o else None),
            "origin_note": (o.note if o else None),
            "reconcile_with": (o.reconcile_with if o else None),
            "reconciled_at": (o.reconciled_at if o else None),
            "reconcile_result": (o.reconcile_result if o else None),
            "darina_method": (o.darina_method if o else None),
            "darina_verdict": (o.darina_verdict if o else None),
            "darina_reason": (o.darina_reason if o else None),
            "as_of": (r["as_of"].iloc[0] if len(r) and r["as_of"].iloc[0] else None),
            "age_h": (float(r["age_h"].iloc[0]) if len(r) and pd.notna(r["age_h"].iloc[0]) else None),
            "limit_h": limit or s.default_max_age_h,
            "limit_from_db": limit is not None,
            "limit_src": limit_src,
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
    # ПУСТАЯ таблица — не то же самое, что отсутствующая. Отсутствующую паспорт уже умел
    # показывать строкой «нет данных», а у пустой `MAX(дата)` возвращает NULL, возраст
    # приходит NaN, и `int(NaN)` роняет страницу целиком: так «Реклама» упала на журнале
    # нажатий, где записей ещё нет и не должно быть (28.09.2026). Проверять только на None
    # мало — `pd.isna` ловит оба случая.
    if age_h is None or pd.isna(age_h):
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
    lines = []
    for r in used:
        line = t("passport.tip_line", src=t(f"passport.src.{r.key}"), date=_fmt_date(r.as_of),
                 loader=r.loader)
        # техническое имя таблицы живёт здесь, а не в таблице паспорта: в строке оно занимает
        # половину ширины и ничего не говорит тому, кто смотрит на цифру, — но нужно тому,
        # кто пойдёт проверять её запросом
        line += " " + t("passport.tip_table", table=f"kabinet_data.{r.table}")
        # у площадки данные обновляются со своей частотой, и подпись должна называть её:
        # «данные по 25.09» без этого читается как «в источнике больше ничего нет»
        if as_text(r.platform_source):
            line += " " + t("passport.tip_origin", origin=as_text(r.platform_source),
                            refresh=as_text(r.platform_refresh, "—"))
        lines.append(line)
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

        def _feeds(key: str) -> str:
            """Первая колонка — что это за цифра на экране. Берём из объявления источника:
            там уже написано, какие метрики он кормит, и второй список заводить незачем."""
            keys = dict((x.key, x.feeds) for x in PAGES[page]).get(key, ())
            names = [t(f"passport.feeds.{k}") for k in keys]
            return " · ".join(names) if names else "—"

        def _reconcile(r) -> str:
            """С чем сверяется, когда и чем кончилось. Пусто — «не сверяется»: пустая ячейка
            читается как «сверка была, результата нет», а это разные вещи."""
            with_ = as_text(r.reconcile_with)
            if not with_:
                return t("passport.rec_none")
            when = _fmt_date(r.reconciled_at) if r.reconciled_at is not None else None
            res = as_text(r.reconcile_result)
            if not when:
                return t("passport.rec_planned", with_=with_)
            return t("passport.rec_done", with_=with_, date=when, result=res or t("passport.rec_no_result"))

        def _darina(r) -> str:
            """Как тот же показатель считает витрина Дарины: итог одним словом, почему — одной фразой,
            и как у неё — из SQL-определения её витрины. Пусто = показателя в её витрине нет."""
            v = as_text(getattr(r, "darina_verdict", None))
            if not v:
                return "—"
            out = t(f"passport.darina.{v}")
            why = as_text(getattr(r, "darina_reason", None))
            how = as_text(getattr(r, "darina_method", None))
            if why:
                out += " — " + why
            if how:
                out += ". " + t("passport.darina.how", how=how)
            return out

        view = pd.DataFrame({
            t("passport.col_shows"): [_feeds(r.key) for r in st_.itertuples()],
            t("passport.col_origin"): [as_text(r.platform_source, "—") for r in st_.itertuples()],
            t("passport.col_loader"): [as_text(r.our_refresh) or as_text(r.loader, "—")
                                       for r in st_.itertuples()],
            t("passport.col_table"): [t(f"passport.src.{r.key}") for r in st_.itertuples()],
            t("passport.col_as_of"): [
                t("passport.absent_short") if r.absent else
                (_fmt_date(r.as_of) + " · " + _age_text(r.age_h)) for r in st_.itertuples()],
            t("passport.col_verdict"): [
                {"we_pull_more": "⚠️", "we_pull_less": "⏳", "ok": "✓"}.get(as_text(r.verdict), "—")
                for r in st_.itertuples()],
            t("passport.col_reconcile"): [_reconcile(r) for r in st_.itertuples()],
            t("passport.col_darina"): [_darina(r) for r in st_.itertuples()],
            t("passport.col_state"): [
                ("🔴 " + t("passport.state_absent")) if r.absent
                else ("🔴 " + t("passport.state_stale")) if r.stale
                else ("— " if not r.watch else "🟢 " + t("passport.state_fresh"))
                for r in st_.itertuples()],
        })
        st.dataframe(view, hide_index=True, use_container_width=True,
                     height=min(420, 38 + 35 * len(view)),
                     column_config={
                         t("passport.col_shows"): st.column_config.TextColumn(
                             t("passport.col_shows"), width="medium"),
                         t("passport.col_origin"): st.column_config.TextColumn(
                             t("passport.col_origin"), width="medium"),
                         t("passport.col_loader"): st.column_config.TextColumn(
                             t("passport.col_loader"), width="medium"),
                         t("passport.col_table"): st.column_config.TextColumn(
                             t("passport.col_table"), width="small",
                             help=t("passport.col_table_help")),
                         t("passport.col_as_of"): st.column_config.TextColumn(
                             t("passport.col_as_of"), width="small",
                             help=t("passport.col_as_of_help")),
                         t("passport.col_verdict"): st.column_config.TextColumn(
                             t("passport.col_verdict"), width="small",
                             help=t("passport.verdict_help")),
                         t("passport.col_reconcile"): st.column_config.TextColumn(
                             t("passport.col_reconcile"), width="medium",
                             help=t("passport.col_reconcile_help")),
                         t("passport.col_darina"): st.column_config.TextColumn(
                             t("passport.col_darina"), width="large",
                             help=t("passport.col_darina_help")),
                     })
        st.caption(t("passport.verdict_hint"))
        # Пороги ушли из таблицы: строка «96 из справочника» занимала колонку и читалась как
        # часть данных, хотя это настройка проверки. Здесь же видно, у кого порог откуда.
        _lim = [f"{t(f'passport.src.{r.key}')}: {int(r.limit_h)} "
                + {"param": t("passport.limit_param"), "db": t("passport.limit_db")}.get(
                    r.limit_src, t("passport.limit_code"))
                for r in st_.itertuples() if r.watch]
        if _lim:
            st.caption(t("passport.limits_hint", items=" · ".join(_lim)))
        notes = [(t(f"passport.src.{r.key}"), as_text(r.origin_note))
                 for r in st_.itertuples() if as_text(r.origin_note)]
        if notes:
            st.markdown("\n".join(f"- **{n}** — {x}" for n, x in notes))
