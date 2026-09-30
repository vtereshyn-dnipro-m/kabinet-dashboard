# -*- coding: utf-8 -*-
"""Вход через Google живёт на зависимостях, которых не видно из нашего кода.

Запускать В ЧИСТОМ окружении, собранном по requirements.txt, — иначе проверка
ничего не значит: нужные библиотеки почти наверняка уже стоят от чего-то другого.

    python3 -m venv /tmp/reqtest
    /tmp/reqtest/bin/pip install -r requirements.txt
    /tmp/reqtest/bin/python scratchpad/check_login_deps.py

Почему проверка вообще нужна. `st.login()` без Authlib отвечает
StreamlitMissingAuthlibError — это первая ошибка, и на ней легко остановиться.
Но Streamlit 1.64 работает на Starlette, маршруты входа лежат в
streamlit/web/server/starlette/starlette_auth_routes.py, и тот импортирует
authlib.integrations.starlette_client, а он — httpx. httpx не ставит ни Streamlit,
ни Authlib. Объявить один Authlib значит починить первую ошибку и получить вторую
на том же нажатии — и ещё один цикл «деплой, ребут, не работает».
"""
import warnings
warnings.filterwarnings("ignore")

ШАГИ = [
    ("streamlit нужной версии",
     "import streamlit as st; assert st.__version__ == '1.64.0', st.__version__"),
    ("st.login / st.logout / st.user",
     "import streamlit as st; assert hasattr(st,'login') and hasattr(st,'logout') and hasattr(st,'user')"),
    ("Streamlit считает Authlib установленным",
     "from streamlit.auth_util import is_authlib_installed as f; assert f(), 'версия старше 1.3.2?'"),
    ("маршруты входа импортируются целиком",
     "import streamlit.web.server.starlette.starlette_auth_routes"),
    ("токен провайдера кодируется и разбирается",
     "import streamlit.auth_util as au; au.get_signing_secret = lambda: 'x'*32; "
     "t = au.encode_provider_token('google'); assert au.decode_provider_token(t)['provider'] == 'google'"),
]

плохо = 0
for имя, код in ШАГИ:
    try:
        exec(код, {})
        print(f"  ок      {имя}")
    except Exception as e:
        плохо += 1
        print(f"  ПРОВАЛ  {имя}: {type(e).__name__}: {str(e)[:120]}")
print(f"\nнеудач: {плохо}")
raise SystemExit(1 if плохо else 0)
