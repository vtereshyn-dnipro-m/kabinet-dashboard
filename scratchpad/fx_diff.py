# -*- coding: utf-8 -*-
"""Разница на экранах: что показывалось и что покажется."""
import json, psycopg2, warnings
warnings.filterwarnings("ignore")
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN); cur = c.cursor()

def пара(подпись, запрос_табл, запрос_вью):
    cur.execute(запрос_табл); было = float(cur.fetchone()[0] or 0)
    cur.execute(запрос_вью);  стало = float(cur.fetchone()[0] or 0)
    d = стало - было
    доля = f"{d / было * 100:+.2f} %" if было else "—"
    print(f"  {подпись:46} {было:11,.2f} → {стало:11,.2f}   {d:+9.2f} €  {доля}")

print("=== ОБЗОР и ДЕНЬГИ: окно 30 дней от последней даты экономики ===")
cur.execute("SELECT max(sales_date) FROM kabinet_data.economics_summary")
последняя = cur.fetchone()[0]
окно = f"sales_date > DATE '{последняя}' - 30 AND sales_date <= DATE '{последняя}'"
пара("Выручка без НДС",
     f"SELECT sum(net_product_sales) FROM kabinet_data.economics_summary WHERE {окно}",
     f"SELECT sum(net_product_sales) FROM kabinet_data.v_economics_summary_eur WHERE {окно}")
пара("Чистыми (после комиссий и возвратов)",
     f"SELECT sum(net_proceeds_total) FROM kabinet_data.economics_summary WHERE {окно}",
     f"SELECT sum(net_proceeds_total) FROM kabinet_data.v_economics_summary_eur WHERE {окно}")
пара("Комиссии площадок",
     f"SELECT sum(total_fees) FROM kabinet_data.economics_summary WHERE {окно}",
     f"SELECT sum(total_fees) FROM kabinet_data.v_economics_summary_eur WHERE {окно}")
пара("Маржа: чистыми минус себестоимость",
     f"""SELECT sum(net_proceeds_total) - sum(cogs * net_units_sold)
           FROM kabinet_data.economics_summary WHERE {окно} AND cogs IS NOT NULL""",
     f"""SELECT sum(net_proceeds_total) - sum(cogs * net_units_sold)
           FROM kabinet_data.v_economics_summary_eur WHERE {окно} AND cogs IS NOT NULL""")

print("\n=== ОБЗОР: карточка «Продажи по заказам» (с НДС), 30 дней ===")
cur.execute("SELECT max(snapshot_date) FROM kabinet_data.sales_traffic_daily")
посл2 = cur.fetchone()[0]
окно2 = f"snapshot_date > DATE '{посл2}' - 30 AND snapshot_date <= DATE '{посл2}'"
пара("Продажи по заказам",
     f"SELECT sum(ordered_sales) FROM kabinet_data.sales_traffic_daily WHERE {окно2}",
     f"SELECT sum(ordered_sales) FROM kabinet_data.v_sales_traffic_daily_eur WHERE {окно2}")

print("\n=== ПЛАН-ФАКТ: цена отгруженных строк заказа, весь период ===")
пара("Сумма строк заказов (с НДС)",
     "SELECT sum(item_price) FROM kabinet_data.orders_history WHERE order_status <> 'Canceled'",
     "SELECT sum(item_price) FROM kabinet_data.v_orders_history_eur WHERE order_status <> 'Canceled'")

print("\n=== За всю историю, по рынкам с чужой валютой ===")
cur.execute("""SELECT e.marketplace, e.currency_code,
                      sum(e.net_product_sales), sum(v.net_product_sales)
                 FROM kabinet_data.economics_summary e
                 JOIN kabinet_data.v_economics_summary_eur v
                   ON v.sales_date=e.sales_date AND v.marketplace=e.marketplace AND v.norm_sku=e.norm_sku
                WHERE e.currency_code <> 'EUR' GROUP BY 1,2 ORDER BY 1""")
вб = вс = 0
for рынок, валюта, было, стало in cur.fetchall():
    print(f"  {рынок} ({валюта}): {float(было):8.2f} → {float(стало):8.2f} € "
          f"({float(стало)-float(было):+8.2f})")
    вб += float(было); вс += float(стало)
print(f"  итого по трём: {вб:.2f} → {вс:.2f} € ({вс-вб:+.2f})")
