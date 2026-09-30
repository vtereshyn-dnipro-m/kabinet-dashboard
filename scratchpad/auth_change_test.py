# -*- coding: utf-8 -*-
"""Та же логика, что в стороже, но в транзакции с откатом: в чат ничего не уходит,
а проверить надо именно сравнение «было → стало»."""
import json, re, psycopg2, warnings
warnings.filterwarnings("ignore")
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN); cur = c.cursor()   # без autocommit

def шаг(новое):
    """Повторяет блок сторожа и возвращает строку для Telegram (или None)."""
    cur.execute("UPDATE kabinet_data.reorder_params SET value = %s WHERE key = 'auth_enabled'", (новое,))
    cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'auth_enabled'")
    now = int(cur.fetchone()[0])
    cur.execute("""SELECT details FROM kabinet_data.app_action_log
                    WHERE action = 'auth_mode' ORDER BY ts DESC, id DESC LIMIT 1""")
    row = cur.fetchone()
    prev = None
    if row and row[0]:
        m = re.search(r"режим (\d+)", row[0])
        prev = int(m.group(1)) if m else None
    line = None
    if prev != now:
        cur.execute("""INSERT INTO kabinet_data.app_action_log (email, role, action, allowed, details)
                       VALUES (NULL, NULL, 'auth_mode', true, %s)""",
                    (f"режим {now}" + (f", было {prev}" if prev is not None else ", первая запись"),))
        if prev is not None:
            line = f"режим {prev} → {now}"
    return line

беда = 0
def ждём(что, ожидание, факт):
    global беда
    if ожидание != факт:
        print(f"  РАСХОЖДЕНИЕ: {что} — ждали {ожидание!r}, получили {факт!r}"); беда += 1

ждём("перевод 2 → 0 замечен", "режим 2 → 0", шаг(0))
ждём("повторный прогон на том же режиме молчит", None, шаг(0))
ждём("ещё один прогон тоже молчит", None, шаг(0))
ждём("возврат 0 → 1 замечен", "режим 0 → 1", шаг(1))
ждём("перевод 1 → 2 замечен", "режим 1 → 2", шаг(2))
c.rollback()
cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'auth_enabled'")
print(f"после отката режим в базе: {int(cur.fetchone()[0])} (должен быть 2)")
print(f"расхождений: {беда}")
c.close()
