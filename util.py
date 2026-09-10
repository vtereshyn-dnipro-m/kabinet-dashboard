# util.py — мелочи, нужные больше чем одной странице
"""Приведение к тексту, устойчивое к пропускам.

Выражение `x or ""` для этого не годится, и ломается оно двумя разными
способами. NaN в Python истинен, поэтому выражение возвращает сам NaN и
следующий же .lower() падает с AttributeError. А pd.NA на проверке
истинности бросает TypeError ещё раньше. Обёртка str() спасает от падения,
но подсовывает строку «nan», и та уезжает в таблицу как артикул товара.

Правильная проверка одна — pd.isna, и она должна быть в одном месте, а не
переписываться на каждой странице.
"""
from typing import NamedTuple

import pandas as pd


def as_text(v, default: str = "") -> str:
    """Строка или default, если значения нет."""
    try:
        if v is None or pd.isna(v):
            return default
    except (TypeError, ValueError):
        # pd.isna на списках и массивах возвращает массив, а не флаг —
        # такие значения текстом и так не притворяются
        pass
    return str(v)


def day_axis(df: pd.DataFrame, day_col: str, start, end) -> pd.DataFrame:
    """Растягивает суточный ряд на все дни периода.

    Дни, которых в данных нет, появляются строками с NaN. Что из них
    считать нулём, а что пропуском, решает вызывающий: из самого факта
    отсутствия строки это не выводится.

    Пример, на котором это видно. 17.08.2026 в `sales_traffic_daily` — 57
    штук на 2 848 €, а в `economics_summary` за тот день нет ни одной
    строки. Продажи были, финансовый отчёт не приехал. Нарисуй мы там
    ноль — график объявил бы провал, которого не случилось. Поэтому ноль
    ставится только тогда, когда есть чем подтвердить, что продаж не было.

    Ряд должен быть уже свёрнут по дню: две строки на одну дату сюда не
    поместятся, reindex на них падает.
    """
    axis = pd.date_range(start, end, freq="D")
    if df.empty:
        out = pd.DataFrame({day_col: axis})
        for c in df.columns:
            if c != day_col:
                out[c] = pd.NA
        return out
    out = df.copy()
    out[day_col] = pd.to_datetime(out[day_col])
    return (out.set_index(day_col).reindex(axis)
               .rename_axis(day_col).reset_index())


class Boundary(NamedTuple):
    """Где кончаются данные, если сравнивать источники между собой."""
    last: object          # pd.Timestamp или pd.NaT — общая граница
    ahead: object         # pd.Series: источник -> его дата, у кого данных больше
    anchored: bool        # границу задал якорный канал, а не общий максимум


def data_boundary(df: pd.DataFrame, date_col: str, group_col: str,
                  anchor=None) -> Boundary:
    """Последний день, за который картина полная.

    Границу задаёт якорный канал: если Amazon отдал отчёт за дату хоть по
    одной стране, день закрыт целиком. Страна без строк за этот день не
    «не отчиталась» — она не продавала, и это разные вещи.

    Раньше здесь стоял минимум из максимумов по каждому рынку, то есть
    обрезка по самому отстающему. Правило выглядело осторожным, а на деле
    врало: Бельгия и Британия торгуют редко, последние их заказы были
    03.09, и вся страница схлопывалась на эту дату, хотя по Amazon данные
    шли до 07.09. Подпись при этом объясняла обрезку тем, что «по BE, GB
    отчёты приходят позже», — а отчёты пришли, просто продаж не было.
    Четыре дня цифр пропадали из-за двух рынков без заказов.

    Обратная крайность — максимум по всем рынкам — тоже неверна. Каналы
    Mirakl приходят почти сразу, Amazon отстаёт на два-три дня: за свежие
    дни в витрине остаются только Mirakl, и показать их значит нарисовать
    обвал, которого не было. Поэтому якорь, а не максимум.

    Без якоря (или если якорных строк в выборке нет — фильтр по одному
    Leroy Merlin) остаётся общий максимум: это лучше пустого экрана.
    """
    empty = pd.Series(dtype="datetime64[ns]")
    if df.empty or date_col not in df.columns or group_col not in df.columns:
        return Boundary(pd.NaT, empty, False)

    d = df.assign(_d=pd.to_datetime(df[date_col], errors="coerce")).dropna(subset=["_d"])
    if d.empty:
        return Boundary(pd.NaT, empty, False)

    per = d.groupby(group_col)["_d"].max()
    last, anchored = pd.NaT, False

    if anchor:
        codes = {str(a).strip().upper() for a in anchor}
        rows = d[d[group_col].astype(str).str.strip().str.upper().isin(codes)]
        if not rows.empty:
            last, anchored = rows["_d"].max(), True

    if pd.isna(last):
        last = per.max()

    return Boundary(last, per[per > last], anchored)
