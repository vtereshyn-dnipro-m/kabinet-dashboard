# -*- coding: utf-8 -*-
"""Каждая объявленная строка паспорта обязана читаться на живой базе.

Иначе паспорт покажет «нет данных» там, где данные есть, — и это заметят не сразу.
"""
import sys, json, psycopg2, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
import data_passport as dp
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN); cur = c.cursor()
плохо = 0
for page, srcs in dp.PAGES.items():
    for s in srcs:
        where = f" WHERE {s.where}" if s.where else ""
        try:
            cur.execute(f"SELECT MAX({s.anchor}) FROM kabinet_data.{s.table}{where}")
            v = cur.fetchone()[0]
            if v is None:
                плохо += 1
                print(f"  ПУСТО   {page:<12} {s.table}.{s.anchor}{where}")
        except Exception as e:
            c.rollback(); плохо += 1
            print(f"  ОШИБКА  {page:<12} {s.table}.{s.anchor}: {str(e).strip().splitlines()[0][:90]}")
print(f"\nстрок паспорта: {sum(len(v) for v in dp.PAGES.values())}, с бедой: {плохо}")
c.close()
