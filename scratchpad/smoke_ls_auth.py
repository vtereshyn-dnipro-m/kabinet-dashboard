# -*- coding: utf-8 -*-
"""Сверка прав Listing Suite: КОД второго репозитория против таблицы в базе Кабинета.

Зачем отдельная проверка. Матрица прав одна и живёт в `kabinet_data.app_permissions`,
а список действий объявлен в коде Listing Suite (`auth._MATRIX` того репозитория).
Экран «Доступ» видит только базу, тесты Listing Suite — только свой код; разойтись
они могут молча, и обнаружилось бы это тем, что кнопка перестала работать у всех.

Проверка видит ОБЕ стороны, поэтому живёт здесь, где есть доступ к базе, и знает
путь к чужому репозиторию. Не найдётся — скажет об этом, а не притворится успешной.

Только чтение (с 21.10.2026): код Listing Suite берётся из `origin/main` того репозитория (`git show`), а не из
рабочей копии — там может быть чужая ветка окна Listing Suite; в базе — только SELECT и каталог. Защита от
самоблокировки проверяется по определению триггера, а не пробным UPDATE с откатом: пробы записи на живой базе
запрещены даже с откатом (AGENTS.md, «Автономия»).

Запуск: python scratchpad/smoke_ls_auth.py
"""
import json
import pathlib
import subprocess
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


if not (КОРЕНЬ_LS / ".git").exists():
    print(f"нет репозитория Listing Suite: {КОРЕНЬ_LS}")
    sys.exit(2)


def из_main(путь: str):
    """Файл Listing Suite из origin/main (без checkout и без fetch); нет — None."""
    r = subprocess.run(["git", "-C", str(КОРЕНЬ_LS), "show", f"origin/main:{путь}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


_main = subprocess.run(["git", "-C", str(КОРЕНЬ_LS), "log", "-1", "--format=%h %cd", "--date=format:%d.%m %H:%M",
                        "origin/main"], capture_output=True, text=True).stdout.strip()
print(f"Listing Suite: origin/main {_main} (последний fetch этой копии — сверка не моложе его)")
_auth = из_main("auth.py")
if _auth is None:
    print("в origin/main Listing Suite нет auth.py")
    sys.exit(2)

# auth.py Listing Suite читаем БЕЗ импорта: он тянет streamlit и своё подключение,
# а нам нужны только объявления. Разбор — по дереву, не регуляркой.
import ast
дерево = ast.parse(_auth.decode("utf-8"))

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
c.set_session(readonly=True)           # сверка только читает
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
# Роль пилота «Генератор текстов» (21.10.2026): видит одну страницу и ни одного действия, а сам генератор — только она
# и администратор. Пока SQL роли не применён, этих строк в базе нет — проверка скажет «не заведено», а не «запрещено»
if "textgen_pilot" in роли_кода:
    ждём("пилоту генератора разрешено только «Генератор текстов»",
         {a for (a, r) in разрешено if r == "textgen_pilot"} == {"ls.page.textgen"})
    ждём("«Генератор текстов» видят только пилот и администратор",
         {r for (a, r) in разрешено if a == "ls.page.textgen"} == {"admin", "textgen_pilot"})

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

# ── общий экран «Доступ»: одна версия на два репозитория ─────────────────────
# Копия обязана совпадать с источником байт в байт. Это и есть всё «общий код»: две
# версии одной админки разошлись бы молча, а таблицы у них общие.
_источник = pathlib.Path(__file__).resolve().parent.parent / "access_screen.py"
_копия = из_main("access_screen.py")
ждём("экран «Доступ» есть у источника", _источник.exists())
ждём("и выложен в Listing Suite (origin/main)", _копия is not None)
if _источник.exists() and _копия is not None:
    ждём("копия в Listing Suite совпадает с источником побайтно",
         _источник.read_bytes() == _копия)
_обёртка = из_main("pages/access.py")
ждём("страница Listing Suite зовёт общий модуль",
     _обёртка is not None and "access_screen.render(" in _обёртка.decode("utf-8"))

# ── право на админку второго продукта и защита от самоблокировки ─────────────
cur.execute("""SELECT role, allowed FROM kabinet_data.app_permissions
                WHERE action = 'ls.admin' ORDER BY role""")
_админка = dict(cur.fetchall())
ждём("право ls.admin заведено на все роли", set(_админка) == роли_кода)
ждём("и разрешено только администратору",
     _админка.get("admin") is True
     and not any(v for r, v in _админка.items() if r != "admin"))
# По определению триггера, не пробой: пробный UPDATE с откатом на живой таблице запрещён (с 19.10.2026)
cur.execute("""SELECT t.tgenabled, pg_get_functiondef(t.tgfoid)
                 FROM pg_trigger t
                WHERE t.tgrelid = 'kabinet_data.app_permissions'::regclass AND NOT t.tgisinternal
                  AND t.tgname = 'app_permissions_keep_admin'""")
_триггер = cur.fetchone()
ждём("триггер app_permissions_keep_admin есть и включён", bool(_триггер) and _триггер[0] != "D")
for _пара in (("admin", "admin"), ("ls.admin", "admin")):
    ждём(f"пару «{_пара[1]} × {_пара[0]}» снять нельзя (она в списке триггера)",
         bool(_триггер) and f"ARRAY['{_пара[0]}','{_пара[1]}']" in _триггер[1])
c.rollback()

print()
print("ИТОГ:", "всё сошлось" if not беда else f"{len(беда)} провалов")
sys.exit(1 if беда else 0)
