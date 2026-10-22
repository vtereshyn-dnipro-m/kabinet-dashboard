# Databricks notebook source
# DBTITLE 1,Kabinet - TikTok Auth Exchange: одноразовый код авторизации → токены в скоуп tiktok-shop
# Kabinet - TikTok Auth Exchange (22.10.2026, решение владельца: «TikTok Shop — подключаем, только чтение»).
#
# Запускает ВЛАДЕЛЕЦ руками, сразу после того как открыл ссылку авторизации приложения «Dnipro-M» и получил code:
# код одноразовый и живёт недолго. Не джоба и не по расписанию — пульса нет.
#
# Что делает: обмен через https://auth.tiktok-shops.com/api/v2/token/get (grant_type=authorized_code), запись в скоуп
# tiktok-shop — refresh-token, access-token, refresh-expires, access-expires (unix) — и сразу проверочный запрос
# Get Authorized Shops (подписанный: если он прошёл, подпись и app-secret верны). В вывод — только продавец, регион,
# сроки токенов и список магазинов (id, имя, регион, тип продавца). Сами токены, app-secret и cipher не выводятся.
# Если TikTok отказал из-за app-key / app-secret — вывод говорит прямо «СЕКРЕТ НЕВЕРНЫЙ».
#
# Лежит в одной папке с tiktok_client.py (файл рабочей области) — модуль импортируется из папки ноутбука.
# Источник кода — nb/tiktok_auth_exchange.py в kabinet-dashboard.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.118.0" requests -q
dbutils.library.restartPython()

# COMMAND ----------

import os
import sys

_nb_dir = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
sys.path.insert(0, "/Workspace" + _nb_dir)
import tiktok_client as tt

dbutils.widgets.text("auth_code", "")
auth_code = dbutils.widgets.get("auth_code").strip()
if not auth_code:
    raise ValueError("нет auth_code: открыть ссылку авторизации приложения и вставить code из адреса возврата в виджет")

client = tt.TikTokClient.from_databricks(dbutils)
try:
    info = client.exchange_auth_code(auth_code)
except tt.TikTokError as e:
    print("ОБМЕН НЕ ПРОШЁЛ:", e.message, f"(HTTP {e.http}, code={e.code}, request_id={e.request_id})")
    raise
print("обмен прошёл, токены записаны в скоуп", tt.SCOPE)
print("  продавец:", info.get("seller_name"), "| регион:", info.get("seller_base_region"), "| тип:", info.get("user_type"))
print("  access до:", tt.fmt_ts(info["access_expires"]), "| refresh до:", tt.fmt_ts(info["refresh_expires"]))
print("  права приложения:", ", ".join(info.get("granted_scopes") or []) or "—")

try:
    shops = client.get_authorized_shops()
except tt.TikTokError as e:
    print("ПРОВЕРОЧНЫЙ ЗАПРОС НЕ ПРОШЁЛ (токены уже записаны):", e)
    raise
print(f"магазинов доступно: {len(shops)}")
for s in shops:
    print(f"  id={s.get('id')} | {s.get('name')} | регион {s.get('region')} | {s.get('seller_type')} | "
          f"cipher {'получен' if s.get('cipher') else 'НЕТ'}")
if not shops:
    raise RuntimeError("обмен прошёл, но Get Authorized Shops вернул пустой список — магазин не авторизовал приложение")
