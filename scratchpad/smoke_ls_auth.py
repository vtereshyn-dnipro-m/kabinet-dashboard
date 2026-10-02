# -*- coding: utf-8 -*-
"""Сверка прав Listing Suite: КОД второго репозитория против таблицы в базе Кабинета.

Зачем отдельная проверка. Матрица прав одна и живёт в `kabinet_data.app_permissions`,
а список действий объявлен в коде Listing Suite (`auth._MATRIX` того репозитория).
Экран «Доступ» видит только базу, тесты Listing Suite — только свой код; разойтись
они могут молча, и обнаружилось бы это тем, что кнопка перестала работать у всех.

Проверка видит ОБЕ стороны, поэтому живёт здесь, где есть доступ к базе, и знает
путь к чужому репозиторию. Не найдётся — скажет об этом, а не притворится успешной.

Запуск: python scratchpad/smoke_ls_auth.py
"""
import json
import pathlib
import sys

import psycopg2

КОРЕНЬ_LS = pathlib.Path("/Users/vitter/Documents/Code/listing-analyzer-dashboard")
DSN = json.load(open(pathlib.Path(__file__).resolve().parent.parent / ".mcp.json")
                )["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]

беда = []


def ждём(что, условие):
    print(("  ок     " if условие else "  ПРОВАЛ ") + что)
    if not условие:
        беда.append(что)


if not (КОРЕНЬ_LS / "auth.py").exists():
    print(f"нет репозитория Listing Suite: {КОРЕНЬ_LS}")
    sys.exit(2)

# auth.py Listing Suite читаем БЕЗ импорта: он тянет streamlit и своё подключение,
# а нам нужны только объявления. Разбор — по дереву, не регуляркой.
import ast
дерево = ast.parse((КОРЕНЬ_LS / "auth.py").read_text(encoding="utf-8"))

# Константы ролей там названы именами (`ROLES = [VIEWER, …]`), поэтому сначала
# собираем простые строковые присваивания, а потом подставляем их при разборе.
окружение = {}
for узел in дерево.body:
    if (isinstance(узел, ast.Assign) and len(узел.targets) == 1
            and isinstance(узел.value, ast.Constant)
            and isinstance(узел.value.value, str)):
        окружение[getattr(узел.targets[0], "id", "")] = узел.value.value


def разобрать(узел):
    if isinstance(узел, ast.Constant):
        return узел.value
    if isinstance(узел, ast.Name):
        if узел.id not in окружение:
            raise ValueError(f"неизвестное имя {узел.id}")
        return окружение[узел.id]
    if isinstance(узел, (ast.List, ast.Tuple)):
        return [разобрать(э) for э in узел.elts]
    if isinstance(узел, ast.Set):
        return {разобрать(э) for э in узел.elts}
    if isinstance(узел, ast.Dict):
        return {разобрать(k): разобрать(v) for k, v in zip(узел.keys, узел.values)}
    raise ValueError(f"не разбирается: {ast.dump(узел)[:60]}")


значения = {}
for узел in дерево.body:
    if isinstance(узел, ast.Assign) and len(узел.targets) == 1:
        имя = getattr(узел.targets[0], "id", "")
        if имя in ("_MATRIX", "PAGES", "ROLES", "PRODUCT"):
            значения[имя] = разобрать(узел.value)
# страницы добавляют в матрицу свои права циклом — повторяем его здесь
действия_кода = set(значения["_MATRIX"]) | {
    "ls.page." + ключ for ключ, *_ in значения["PAGES"]}
роли_кода = set(значения["ROLES"])

c = psycopg2.connect(DSN)
cur = c.cursor()
cur.execute("SELECT action, role, allowed FROM kabinet_data.app_permissions "
            "WHERE action LIKE 'ls.%'")
строки = cur.fetchall()
действия_базы = {a for a, _, _ in строки}
роли_базы = {r for _, r, _ in строки}

print(f"действий в коде {len(действия_кода)}, в базе {len(действия_базы)}")
нет_в_базе = sorted(действия_кода - действия_базы)
ждём("каждое действие кода заведено в базе"
     + (f" (не заведено: {', '.join(нет_в_базе)})" if нет_в_базе else ""),
     not нет_в_базе)
лишние = sorted(действия_базы - действия_кода)
ждём("в базе нет действий, которых нет в коде"
     + (f" (лишние: {', '.join(лишние)})" if лишние else ""),
     not лишние)
ждём("роли совпадают", роли_базы <= роли_кода)

# У каждого действия должна быть строка на КАЖДУЮ роль: отсутствующая пара читается
# как запрет, и на экране такой галочки просто нет — различить «запрещено» и
# «не заведено» стало бы невозможно.
пары = {(a, r) for a, r, _ in строки}
нет_пар = sorted(f"{a}×{r}" for a in действия_базы for r in роли_кода
                 if (a, r) not in пары)
ждём("у каждого действия есть строка на каждую роль"
     + (f" (нет: {', '.join(нет_пар[:5])}{'…' if len(нет_пар) > 5 else ''})"
        if нет_пар else ""),
     not нет_пар)

# Отправка в Amazon — та самая кнопка, которая меняет живой листинг: ни «Просмотру»,
# ни контент-менеджеру её быть не должно, чем бы ни кончились правки галочками.
разрешено = {(a, r) for a, r, ok in строки if ok}
ждём("отправка в Amazon закрыта «Просмотру»",
     ("ls.amazon.push", "viewer") not in разрешено)
ждём("отправка в Amazon закрыта контент-менеджеру",
     ("ls.amazon.push", "content_manager") not in разрешено)
ждём("правка настроек — только администратору",
     all(r == "admin" for (a, r) in разрешено if a == "ls.settings.edit"))

# Колонки, без которых вход не поднимется
cur.execute("""SELECT count(*) FROM information_schema.columns
                WHERE table_schema='kabinet_data' AND table_name='app_users'
                  AND column_name='ls_role'""")
ждём("колонка app_users.ls_role есть", cur.fetchone()[0] == 1)
for таблица in ("app_action_log", "app_login_log", "qa_tokens"):
    cur.execute("""SELECT count(*) FROM information_schema.columns
                    WHERE table_schema='kabinet_data' AND table_name=%s
                      AND column_name='product'""", (таблица,))
    ждём(f"колонка {таблица}.product есть", cur.fetchone()[0] == 1)
cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key='ls_auth_enabled'")
строка = cur.fetchone()
ждём("режим входа Listing Suite заведён", строка is not None)
if строка:
    print(f"  режим сейчас: {int(строка[0])} "
          f"({'раскатка' if int(строка[0]) == 2 else 'вход' if int(строка[0]) == 1 else 'авария'})")

# Права принципала приложения: без них вход не поднимется, и проверять это надо
# ПЕРВЫМ делом, а не по падению на проде
ПРИНЦИПАЛ = "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb"
for таблица, право in (("app_users", "SELECT"), ("app_users", "UPDATE"),
                       ("app_permissions", "SELECT"), ("reorder_params", "SELECT"),
                       ("app_login_log", "INSERT"), ("app_action_log", "INSERT"),
                       ("qa_tokens", "UPDATE")):
    cur.execute("SELECT has_table_privilege(%s, %s, %s)",
                (ПРИНЦИПАЛ, f"kabinet_data.{таблица}", право))
    ждём(f"принципалу можно {право} по {таблица}", bool(cur.fetchone()[0]))

print()
print("ИТОГ:", "всё сошлось" if not беда else f"{len(беда)} провалов")
sys.exit(1 if беда else 0)
