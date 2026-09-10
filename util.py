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
    behind: list          # источники, которые её и задают
    ahead: object         # pd.Series: источник -> его дата, у кого данных больше


def data_boundary(df: pd.DataFrame, date_col: str, group_col: str) -> Boundary:
    """Граница данных по самому отстающему источнику.

    Считаем максимум по каждому источнику и берём из них минимальный.
    Максимум по всей выборке обещал бы данные до самой свежей страны,
    хотя по остальным их нет: страницы называли дату, которой по части
    рынков не существует, и две соседние страницы расходились в цифрах.

    Ровно то же правило — и та же функция — должно работать на всех
    страницах. Логика, размноженная по вызовам, однажды разойдётся:
    так уже было с именами джоб и с расчётом комиссии.

    Плата за это — обрезка по худшему: один заказ в Бельгии двигает
    границу для всей страницы. Поэтому подпись обязана назвать, кто
    именно отстал, иначе цифра выглядит необъяснимо низкой.
    """
    if df.empty or date_col not in df.columns or group_col not in df.columns:
        return Boundary(pd.NaT, [], pd.Series(dtype="datetime64[ns]"))
    per = (df.assign(_d=pd.to_datetime(df[date_col], errors="coerce"))
             .groupby(group_col)["_d"].max().dropna())
    if per.empty:
        return Boundary(pd.NaT, [], pd.Series(dtype="datetime64[ns]"))
    last = per.min()
    return Boundary(last, sorted(per[per == last].index), per[per > last])
