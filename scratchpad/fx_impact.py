# -*- coding: utf-8 -*-
"""Сколько стоит то, что Кабинет складывает фунты и кроны с евро как есть."""
import json, psycopg2, warnings, datetime
warnings.filterwarnings("ignore")
import uc
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN); cur = c.cursor()

# курс на дату: units_per_eur (единиц валюты за 1 евро)
курс = {}
for д, в, к in uc.q("""SELECT CAST(date AS STRING), currency, units_per_eur
                         FROM dnipro_m.dnipro_m.raw_ecb_fx_rates"""):
    курс[(д, в)] = float(к)

def в_евро(сумма, валюта, дата):
    if валюта == "EUR":
        return сумма, None
    k = курс.get((str(дата), валюта))
    return (сумма / k, k) if k else (None, None)

print("=== 1. economics_summary — выручка без НДС ===")
cur.execute("""SELECT marketplace, currency_code, sales_date, sum(net_product_sales)
                 FROM kabinet_data.economics_summary
                WHERE currency_code <> 'EUR'
                GROUP BY 1,2,3 ORDER BY 1,3""")
итоги = {}
нет_курса = 0
for рынок, валюта, дата, сумма in cur.fetchall():
    евро, k = в_евро(float(сумма), валюта, дата)
    if евро is None:
        нет_курса += 1; continue
    а, б = итоги.get(рынок, (0.0, 0.0))
    итоги[рынок] = (а + float(сумма), б + евро)
всего_как_есть = всего_верно = 0.0
for рынок, (как_есть, верно) in sorted(итоги.items()):
    валюта = {"GB": "GBP", "SE": "SEK", "PL": "PLN"}[рынок]
    print(f"  {рынок}: {как_есть:9.2f} {валюта} — сейчас считается как {как_есть:9.2f} € , "
          f"на деле {верно:8.2f} € · разница {верно - как_есть:+9.2f} €")
    всего_как_есть += как_есть; всего_верно += верно
print(f"  ИТОГО: завышено на {всего_как_есть - всего_верно:+.2f} € "
      f"({всего_как_есть:.2f} вместо {всего_верно:.2f})")
if нет_курса:
    print(f"  дней без курса: {нет_курса}")

print("\n=== 2. sales_traffic_daily — продажи по заказам (с НДС) ===")
cur.execute("""SELECT marketplace, currency, snapshot_date, sum(ordered_sales)
                 FROM kabinet_data.sales_traffic_daily
                WHERE currency IS NOT NULL AND currency <> 'EUR'
                GROUP BY 1,2,3""")
строки = cur.fetchall()
if not строки:
    cur.execute("SELECT DISTINCT currency FROM kabinet_data.sales_traffic_daily")
    print("  валюты в таблице:", [r[0] for r in cur.fetchall()])
else:
    агр = {}
    for рынок, валюта, дата, сумма in строки:
        евро, _ = в_евро(float(сумма), валюта, дата)
        if евро is None: continue
        а, б = агр.get((рынок, валюта), (0.0, 0.0))
        агр[(рынок, валюта)] = (а + float(сумма), б + евро)
    for (рынок, валюта), (как_есть, верно) in sorted(агр.items()):
        print(f"  {рынок} ({валюта}): {как_есть:10.2f} вместо {верно:9.2f} € · "
              f"разница {верно - как_есть:+9.2f} €")

print("\n=== 3. orders_history — цена строки заказа ===")
cur.execute("""SELECT marketplace_code, currency, count(*), sum(item_price)
                 FROM kabinet_data.orders_history
                WHERE currency IS NOT NULL AND currency <> 'EUR'
                GROUP BY 1,2 ORDER BY 4 DESC NULLS LAST""")
for рынок, валюта, n, сумма in cur.fetchall():
    print(f"  {рынок} ({валюта}): строк {n}, сумма {float(сумма or 0):.2f} {валюта}")
