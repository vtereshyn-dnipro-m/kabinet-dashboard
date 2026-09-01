# period.py — единый выбор периода для всех страниц Кабинета
"""Один набор вариантов и одна память на всё приложение.

До этого каждая страница объявляла свой набор: где-то 7/30, где-то
7/30/60/90, на отзывах 7/14/30/60/90 и без «этого месяца». Человек,
переходя со страницы на страницу, каждый раз выбирал период заново и
сравнивал числа за разные окна, не замечая этого. Набор здесь один, и
менять его надо здесь же, а не в семи файлах.

Выбор переживает переход между страницами: он лежит в session_state, а
не только в состоянии виджета — Streamlit чистит состояние виджетов,
которых нет на текущей странице, и без этой копии период сбрасывался бы
ровно при переходе. Дублируем ещё и в адрес, чтобы ссылкой можно было
поделиться вместе с периодом.
"""
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import streamlit as st

from i18n import t

P_7, P_30, P_90 = "7", "30", "90"
# Ключ памяти и ключ виджета обязаны быть РАЗНЫМИ. Streamlit запрещает
# присваивать session_state[k], если k — ключ уже отрисованного виджета,
# и на одном ключе страница падала с StreamlitAPIException ещё до того,
# как успевала что-нибудь показать
STATE = "kab_period"        # выбранный вариант, переживает смену страницы
WIDGET = "kab_period_pick"  # ключ самого переключателя
STATE_RANGE = "kab_range"   # границы своего периода
QP = "d"                    # тот же период в адресе страницы


def options() -> list:
    return [P_7, P_30, P_90, t("period.month"), t("period.custom")]


@dataclass
class Period:
    """Окно, за которое страница показывает данные.

    days нужен страницам, которые считают «за последние N дней», d_from и
    d_to — тем, кто умеет произвольный диапазон. Для своего периода days
    равен длине диапазона, но опираться на него там нельзя: диапазон
    может заканчиваться не сегодня."""
    choice: str
    days: int
    d_from: pd.Timestamp = None
    d_to: pd.Timestamp = None

    @property
    def is_range(self) -> bool:
        return self.d_from is not None

    @property
    def from_str(self) -> str:
        return self.d_from.strftime("%Y-%m-%d") if self.is_range else ""

    @property
    def to_str(self) -> str:
        return self.d_to.strftime("%Y-%m-%d") if self.is_range else ""

    @property
    def start(self) -> pd.Timestamp:
        """Первый день окна — для проверки, покрывают ли его данные.

        Отступ days-1, то есть ровно столько суток, сколько написано на
        кнопке. Запросы просят на день шире (>= CURRENT_DATE - INTERVAL
        'N days' — это N+1 суток), и брать за начало их границу нельзя:
        тогда честно покрытая неделя каждый раз рапортовала бы дырку в
        один день. Ложная тревога здесь дороже пропущенной: подпись,
        которая горит всегда, перестаёт читаться."""
        return self.d_from if self.is_range else (
            pd.Timestamp(datetime.now().date()) - pd.Timedelta(days=self.days - 1))

    @property
    def end(self) -> pd.Timestamp:
        return self.d_to if self.is_range else pd.Timestamp(datetime.now().date())

    @property
    def title(self) -> str:
        if self.is_range:
            return t("period.title_range", 
                a=self.d_from.strftime("%d.%m"), b=self.d_to.strftime("%d.%m.%Y"))
        return t("period.title_days", d=self.days)


def control(*, key: str = WIDGET, columns=None) -> Period:
    """Селектор периода. Возвращает окно, а не строку выбора."""
    opts = options()
    saved = st.query_params.get(QP) or st.session_state.get(STATE)
    default = saved if saved in opts else P_30

    c1, c2 = columns if columns is not None else st.columns([2, 2])
    with c1:
        choice = st.segmented_control(
            t("period.label"), options=opts, default=default, key=key) or default
    st.session_state[STATE] = choice
    if st.query_params.get(QP) != choice:
        st.query_params[QP] = choice

    today = pd.Timestamp(datetime.now().date())
    if choice == t("period.month"):
        d_from, d_to = today.replace(day=1), today
    elif choice == t("period.custom"):
        # границы своего периода тоже помним: иначе при возврате на
        # страницу диапазон молча схлопывается в последние 30 дней
        saved_r = st.session_state.get(STATE_RANGE) or (
            (today - pd.Timedelta(days=29)).date(), today.date())
        with c2:
            picked = st.date_input(t("period.range"), value=saved_r,
                                   max_value=today, format="DD.MM.YYYY",
                                   key=f"{key}_range")
        if isinstance(picked, (list, tuple)) and len(picked) == 2:
            d_from, d_to = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
            st.session_state[STATE_RANGE] = (d_from.date(), d_to.date())
        else:
            # пока кликнули только первую границу, держим прошлый диапазон.
            # Схлопывать окно в один день на середине выбора — значит
            # мигнуть пустой страницей и напугать без причины
            d_from, d_to = (pd.Timestamp(saved_r[0]), pd.Timestamp(saved_r[1]))
    else:
        return Period(choice=choice, days=int(choice))

    return Period(choice=choice, days=max((d_to - d_from).days + 1, 1),
                  d_from=d_from, d_to=d_to)


def note(p: Period, first, last) -> str:
    """Чем данные не дотягивают до выбранного окна.

    Молчаливый ноль за непокрытый период — худшее, что здесь можно
    показать: он неотличим от честного «продаж не было». Поэтому границы
    имеющихся данных сравниваем с запрошенными и говорим разницу словами."""
    first = pd.to_datetime(first, errors="coerce")
    last = pd.to_datetime(last, errors="coerce")
    if pd.isna(first) or pd.isna(last):
        return t("period.gap_none", p=p.title)
    parts = []
    if first.normalize() > p.start.normalize():
        parts.append(t("period.gap_start", 
            d=first.strftime("%d.%m.%Y"), p=p.start.strftime("%d.%m.%Y")))
    if last.normalize() < p.end.normalize():
        parts.append(t("period.gap_end", 
            d=last.strftime("%d.%m.%Y"), p=p.end.strftime("%d.%m.%Y")))
    return " ".join(parts)


def show_note(p: Period, first, last) -> None:
    msg = note(p, first, last)
    if msg:
        st.caption(msg)
