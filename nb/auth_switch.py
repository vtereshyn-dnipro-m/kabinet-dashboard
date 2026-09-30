# Databricks notebook source
# MAGIC %md
# MAGIC # Рубильник входа в Кабинет
# MAGIC
# MAGIC Этим ноутбуком включают и выключают вход через Google. Больше он ничего не делает
# MAGIC и ничего другого поменять не может.
# MAGIC
# MAGIC ## Когда ставить 0
# MAGIC
# MAGIC **0 — это авария: вход не спрашивается, Кабинет открыт всем на чтение, кнопки
# MAGIC действий скрыты.** Ставьте 0, если люди не могут войти:
# MAGIC
# MAGIC * на экране входа кнопка «Sign in with Google» ведёт в ошибку;
# MAGIC * вход проходит, но Кабинет пишет «Доступ закрыт» тем, у кого он должен быть;
# MAGIC * Кабинет вообще не открывается дальше экрана входа.
# MAGIC
# MAGIC Ноль **никого не выкидывает** и ничего не ломает: люди продолжают работать, просто
# MAGIC не могут нажимать кнопки, которые что-то меняют. Это безопасное состояние — лучше
# MAGIC оставить Кабинет открытым на чтение, чем закрытым совсем.
# MAGIC
# MAGIC ## Как вернуть 1
# MAGIC
# MAGIC **1 — обычное состояние: вход обязателен, роли работают.** Возвращайте 1, когда
# MAGIC вход починили и вы сами смогли войти.
# MAGIC
# MAGIC ## Про 2
# MAGIC
# MAGIC **2 — раскатка: входа нет, но кнопки у всех.** Так было до включения входа. Сейчас
# MAGIC ставить 2 не нужно: в этом состоянии любой, у кого есть ссылка, может менять данные.
# MAGIC Если кажется, что нужно именно 2, — сначала спросите.
# MAGIC
# MAGIC ## Порядок
# MAGIC
# MAGIC 1. Запустите ячейку **«Что сейчас»** — она только смотрит и ничего не меняет.
# MAGIC 2. В ячейке **«Переключить»** впишите нужное число вместо `None` и запустите её.
# MAGIC 3. Прочитайте вывод — он должен выглядеть так, как показано ниже.
# MAGIC 4. Откройте Кабинет и убедитесь своими глазами. Изменение действует в течение минуты.
# MAGIC
# MAGIC «Run All» ничего не переключает: пока в ячейке стоит `None`, она отказывается
# MAGIC работать. Это сделано нарочно, чтобы случайный запуск всего ноутбука не менял режим.
# MAGIC
# MAGIC ## Что должно быть в выводе
# MAGIC
# MAGIC Ячейка «Что сейчас» — одна строка:
# MAGIC
# MAGIC ```
# MAGIC Режим входа: 1 — вход обязателен, роли работают
# MAGIC ```
# MAGIC
# MAGIC Ячейка «Переключить» при настоящем переключении:
# MAGIC
# MAGIC ```
# MAGIC Было 1, стало 0 — АВАРИЯ: входа нет, у всех «Просмотр». Переключил: darina.korotkova@dniprom.com.
# MAGIC Подействует в течение минуты; сообщение уйдёт в Telegram.
# MAGIC ✅ Готово. Проверьте Кабинет через минуту.
# MAGIC ```
# MAGIC
# MAGIC Если режим уже стоит нужный:
# MAGIC
# MAGIC ```
# MAGIC Уже 0 — АВАРИЯ: входа нет, у всех «Просмотр». Ничего не менялось.
# MAGIC ```
# MAGIC
# MAGIC ## Если вместо этого ошибка
# MAGIC
# MAGIC * `permission denied for function set_auth_mode` — вам не выдали права. Напишите
# MAGIC   Владиславу, это одна строка в базе;
# MAGIC * `password authentication failed` или `role ... does not exist` — вашей учётной
# MAGIC   записи нет в базе Кабинета, это тоже к Владиславу;
# MAGIC * `Режим бывает только 0, 1 или 2` — опечатка в числе, исправьте и запустите снова;
# MAGIC * что-то другое — пришлите текст ошибки целиком, не пересказывая.
# MAGIC
# MAGIC Каждое переключение записывается в журнал Кабинета вместе с вашим именем и уходит
# MAGIC сообщением в Telegram. Это нормально и так задумано: рубильник не должен срабатывать
# MAGIC незаметно.

# COMMAND ----------

# DBTITLE 1,Что сейчас
# Ячейка только смотрит. Запускать можно сколько угодно раз.
#
# Самодостаточна нарочно: своё подключение и свои константы. Ячейку запускают в
# одиночку, с середины, после падения — и ничего из соседних ячеек в этот момент
# может не существовать.
import subprocess, sys
try:
    import psycopg2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2
import requests


def подключиться():
    """Соединение с базой Кабинета ПОД ТЕМ, КТО ЗАПУСТИЛ ноутбук.

    Ходим в REST напрямую, а не через databricks-sdk, и это не каприз: на serverless
    стоит SDK постарше, где нужного вызова нет вовсе — первый прогон упал
    «'WorkspaceClient' object has no attribute 'postgres'». Лечить это установкой
    пакета с перезапуском интерпретатора нельзя: при заданном окружении задачи
    перезапуск роняет прогон. REST же есть всегда и от версий не зависит.
    """
    _ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    _хост = _ctx.apiUrl().get()
    _мой_токен = _ctx.apiToken().get()
    # имя берём у самого Databricks, а не вписываем строкой: с чужим именем
    # в ответ приходит «OAuth: User is not authorized»
    try:
        _я = _ctx.userName().get()
    except Exception:
        _я = spark.sql("SELECT current_user()").first()[0]
    _ответ = requests.post(
        f"{_хост}/api/2.0/postgres/credentials",
        headers={"Authorization": f"Bearer {_мой_токен}"},
        json={"endpoint": "projects/kabinet-dashboard/branches/production/endpoints/primary"},
        timeout=60)
    _ответ.raise_for_status()
    return _я, psycopg2.connect(
        host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
        port=5432, dbname="databricks_postgres",
        user=_я, password=_ответ.json()["token"], sslmode="require")


_я, _соединение = подключиться()
print(f"вы: {_я}")
try:
    with _соединение.cursor() as _к:
        _к.execute("SELECT kabinet_data.get_auth_mode()")
        print(_к.fetchone()[0])
finally:
    _соединение.close()

# COMMAND ----------

# DBTITLE 1,Переключить
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  Впишите число вместо None и запустите ячейку.                           │
# │                                                                          │
# │      0 — авария: входа нет, Кабинет открыт на чтение, кнопок нет         │
# │      1 — обычное состояние: вход обязателен, роли работают               │
# │      2 — раскатка: входа нет, кнопки у всех (сейчас не нужно)            │
# └──────────────────────────────────────────────────────────────────────────┘

РЕЖИМ = None

# ──────────────────────────────────────────────────────────────────────────────
# Ниже менять нечего.
#
# None здесь не забывчивость, а защита: «Run All» не должен переключать режим.
# Ячейка отказывается работать, пока число не вписали руками.
import subprocess, sys
try:
    import psycopg2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2
import requests


def подключиться():
    """То же, что в ячейке выше. Повторено нарочно: ячейку запускают в одиночку,
    и она не должна зависеть от того, запускали ли соседнюю."""
    _ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    _хост = _ctx.apiUrl().get()
    _мой_токен = _ctx.apiToken().get()
    try:
        _я = _ctx.userName().get()
    except Exception:
        _я = spark.sql("SELECT current_user()").first()[0]
    _ответ = requests.post(
        f"{_хост}/api/2.0/postgres/credentials",
        headers={"Authorization": f"Bearer {_мой_токен}"},
        json={"endpoint": "projects/kabinet-dashboard/branches/production/endpoints/primary"},
        timeout=60)
    _ответ.raise_for_status()
    return _я, psycopg2.connect(
        host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
        port=5432, dbname="databricks_postgres",
        user=_я, password=_ответ.json()["token"], sslmode="require")


if РЕЖИМ is None:
    print("Режим не выбран — ничего не менялось.\n"
          "Впишите 0, 1 или 2 в строку «РЕЖИМ =» выше и запустите ячейку снова.")
else:
    _я, _соединение = подключиться()
    _соединение.autocommit = True
    try:
        with _соединение.cursor() as _к:
            # Проверку значения и запись в журнал делает сама функция в базе, а не эта
            # ячейка: правило должно быть одно на всех, кто переключает, а не своё в
            # каждом ноутбуке.
            _к.execute("SELECT kabinet_data.set_auth_mode(%s)", (int(РЕЖИМ),))
            print(_к.fetchone()[0])
        print("✅ Готово. Проверьте Кабинет через минуту.")
    finally:
        _соединение.close()
