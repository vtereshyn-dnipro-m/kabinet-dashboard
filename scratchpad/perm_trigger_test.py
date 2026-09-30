# -*- coding: utf-8 -*-
import json, psycopg2, warnings
warnings.filterwarnings("ignore")
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN)      # без autocommit: всё откатим
беда = 0
def случай(что, sql, должно_упасть):
    global беда
    cur = c.cursor()
    try:
        cur.execute(sql); упало = None
    except Exception as e:
        упало = str(e).strip().splitlines()[0]
    c.rollback()
    ок = bool(упало) == должно_упасть
    if not ок: беда += 1
    метка = "ок    " if ок else "ПРОВАЛ"
    print(f"  {метка} {что}" + (f" → {упало[:80]}" if упало else ""))

случай("снять «админ × админка» нельзя",
       "UPDATE kabinet_data.app_permissions SET allowed = false WHERE action='admin' AND role='admin'", True)
случай("удалить «админ × админка» нельзя",
       "DELETE FROM kabinet_data.app_permissions WHERE action='admin' AND role='admin'", True)
случай("снять «админ × реклама» можно",
       "UPDATE kabinet_data.app_permissions SET allowed = false WHERE action='ads.act' AND role='admin'", False)
случай("дать «просмотру» рекламу можно (это решение администратора)",
       "UPDATE kabinet_data.app_permissions SET allowed = true WHERE action='ads.act' AND role='viewer'", False)
случай("снять админку у планировщика можно",
       "UPDATE kabinet_data.app_permissions SET allowed = false WHERE action='admin' AND role='demand_planner'", False)
print(f"\nрасхождений: {беда}")
c.close()
