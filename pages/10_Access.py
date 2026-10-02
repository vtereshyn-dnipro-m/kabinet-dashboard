# pages/10_Access.py — экран «Доступ» Кабинета: тонкая обёртка над общим модулем.
"""Сам экран живёт в `access_screen.py` — один на два приложения.

Здесь остаётся только то, что принадлежит ХОЗЯИНУ: язык интерфейса, своё соединение,
свой модуль прав и код продукта. Код страницы был разъят на модуль и обёртку 02.10.2026,
когда такой же экран понадобился в Listing Suite: держать две версии одной админки
значило бы однажды их разойтись, причём молча — таблицы-то общие.
"""
import streamlit as st  # noqa: F401  (нужен Streamlit-контексту страницы)

import access_screen
import auth
from db.connection import get_connection
from i18n import init_lang, t, get_lang

init_lang()

access_screen.render(product="kabinet", auth=auth, get_connection=get_connection,
                     t=t, lang=get_lang())
