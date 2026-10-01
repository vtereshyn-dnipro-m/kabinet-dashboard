# Databricks notebook source
# DBTITLE 1,Курсы валют к евро (ЕЦБ через Frankfurter)
# ═════════════════════════════════════════════════════════════
# KABINET - FX RATES — курсы GBP, SEK, PLN к евро
# Источник: ЕЦБ через api.frankfurter.app (бесплатный, без ключа)
# Пишет: dnipro_m.dnipro_m.raw_ecb_fx_rates
# Самодостаточная ячейка: своё подключение, свои константы.
# ═════════════════════════════════════════════════════════════
import datetime
import requests
from pyspark.sql import Row

ТАБЛИЦА = "dnipro_m.dnipro_m.raw_ecb_fx_rates"
ВАЛЮТЫ = ["GBP", "SEK", "PLN"]
НАЧАЛО = datetime.date(2025, 1, 1)
JOB_NAME = "Kabinet - FX Rates"

# ЕЦБ публикует курс по рабочим дням около 16:00 CET, и в 9:00 по Киеву (8:00 CET)
# курса за сегодня ещё нет. Поэтому у строки ДВЕ даты: `date` — наш календарный день,
# `rate_date` — день, которым курс опубликован. На выходных и в праздники они
# расходятся на два-три дня, и это нормально; скрывать расхождение одной датой нельзя,
# иначе в отчёте «курс на субботу» будет выглядеть как субботняя публикация.
сегодня = datetime.date.today()
ответ = requests.get(
    f"https://api.frankfurter.app/{НАЧАЛО.isoformat()}..{сегодня.isoformat()}",
    params={"base": "EUR", "symbols": ",".join(ВАЛЮТЫ)},
    headers={"User-Agent": "kabinet-dashboard/1.0"},  # без него приходит 403
    timeout=120)
ответ.raise_for_status()
опубликовано = ответ.json().get("rates", {})
if not опубликовано:
    raise RuntimeError("Frankfurter вернул пустой список курсов — писать нечего")

# Разворачиваем публикации в КАЛЕНДАРЬ: строка на каждый день, курс — последний
# опубликованный на эту дату. Иначе join по дате продажи терял бы каждую субботу и
# воскресенье, а это треть дней.
даты_публикаций = sorted(datetime.date.fromisoformat(d) for d in опубликовано)
строки, i, текущая = [], 0, None
день = НАЧАЛО
while день <= сегодня:
    while i < len(даты_публикаций) and даты_публикаций[i] <= день:
        текущая = даты_публикаций[i]
        i += 1
    if текущая is not None:
        курсы = опубликовано[текущая.isoformat()]
        for валюта in ВАЛЮТЫ:
            к = курсы.get(валюта)
            if к:
                строки.append(Row(date=день, currency=валюта,
                                  units_per_eur=float(к),
                                  eur_per_unit=round(1.0 / float(к), 8),
                                  rate_date=текущая, source="ecb:frankfurter",
                                  loaded_at=datetime.datetime.now(datetime.timezone.utc)))
    день += datetime.timedelta(days=1)

df = spark.createDataFrame(строки)
df.createOrReplaceTempView("_fx_new")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {ТАБЛИЦА} (
        date          DATE      COMMENT 'Календарный день, на который действует курс',
        currency      STRING    COMMENT 'Код валюты ISO 4217',
        units_per_eur DOUBLE    COMMENT 'Сколько единиц валюты за 1 евро — конвенция ЕЦБ',
        eur_per_unit  DOUBLE    COMMENT 'Сколько евро за 1 единицу валюты — обратный курс',
        rate_date     DATE      COMMENT 'Каким днём курс опубликован ЕЦБ; в выходные отстаёт от date',
        source        STRING,
        loaded_at     TIMESTAMP
    ) USING DELTA
    COMMENT 'Курсы валют к евро от ЕЦБ (через Frankfurter). Строка на каждый календарный день: в выходные и праздники ЕЦБ курс не публикует, и берётся последний опубликованный.'
""")

# MERGE, а не перезапись: прогон идемпотентен, повторный запуск ничего не множит, а
# пропущенный день закрывается следующим прогоном сам
spark.sql(f"""
    MERGE INTO {ТАБЛИЦА} t
    USING _fx_new s ON t.date = s.date AND t.currency = s.currency
    WHEN MATCHED AND (t.units_per_eur <> s.units_per_eur OR t.rate_date <> s.rate_date)
        THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

итог = spark.sql(f"""
    SELECT count(*) AS n, count(DISTINCT date) AS days, min(date) AS d1, max(date) AS d2,
           max(rate_date) AS last_rate
      FROM {ТАБЛИЦА}
""").collect()[0]
summary = (f"строк {итог['n']}, дней {итог['days']} ({итог['d1']} … {итог['d2']}), "
           f"последняя публикация ЕЦБ {итог['last_rate']}, валют {len(ВАЛЮТЫ)}")
print("💱 " + summary)

# ── SYSTEM PULSE: безусловно, последним ──
# Метка — внешняя точка контроля: если прогон встанет, об этом скажет сторож.
import psycopg2
from databricks.sdk import WorkspaceClient

_w = WorkspaceClient()
_me = _w.current_user.me().user_name
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
_c = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
    port=5432, dbname="databricks_postgres", user=_me, password=_cred.token,
    sslmode="require")
_cur = _c.cursor()
_cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                VALUES (%s, now(), %s)
                ON CONFLICT (job_name) DO UPDATE
                   SET last_success_at = now(), note = EXCLUDED.note""",
             (JOB_NAME, summary[:900]))
_c.commit(); _c.close()
print(f"💓 {JOB_NAME}")
