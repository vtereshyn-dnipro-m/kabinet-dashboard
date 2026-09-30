# -*- coding: utf-8 -*-
"""Рубильник проверяем В ТРАНЗАКЦИИ С ОТКАТОМ: режим сейчас боевой, и настоящее
переключение выкинуло бы людей из Кабинета ради теста."""
import json, psycopg2, warnings
warnings.filterwarnings("ignore")
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN); cur = c.cursor()
беда = 0
def ждём(что, условие, текст=""):
    global беда
    if not условие:
        беда += 1; print(f"  ПРОВАЛ {что}: {текст}")
    else:
        print(f"  ок     {что}" + (f" → {текст}" if текст else ""))

cur.execute("SELECT kabinet_data.get_auth_mode()")
сейчас = cur.fetchone()[0]
ждём("показ текущего режима", "Режим входа:" in сейчас, сейчас)

cur.execute("SELECT value::int FROM kabinet_data.reorder_params WHERE key='auth_enabled'")
было = cur.fetchone()[0]

cur.execute("SELECT kabinet_data.set_auth_mode(0)")
r = cur.fetchone()[0]
ждём("переключение в аварию", "АВАРИЯ" in r and f"Было {было}" in r, r)

cur.execute("SELECT value::int FROM kabinet_data.reorder_params WHERE key='auth_enabled'")
ждём("значение в базе поменялось", cur.fetchone()[0] == 0)

cur.execute("""SELECT email, action, details FROM kabinet_data.app_action_log
               ORDER BY id DESC LIMIT 1""")
кто, действие, подробности = cur.fetchone()
ждём("в журнале записан автор", bool(кто), f"{кто} · {действие} · {подробности}")
ждём("код действия отдельный, чтобы не заглушить оповещение", действие == "auth_mode_set", действие)

cur.execute("SELECT kabinet_data.set_auth_mode(0)")
ждём("повторное то же значение — ничего не меняет", "Ничего не менялось" in cur.fetchone()[0])

for плохое in (3, -1, 42):
    try:
        cur.execute("SELECT kabinet_data.set_auth_mode(%s)", (плохое,))
        ждём(f"значение {плохое} отклонено", False, "прошло, а не должно")
    except Exception as e:
        c.rollback(); cur = c.cursor()
        cur.execute("SELECT kabinet_data.set_auth_mode(0)")   # восстановим состояние опыта
        ждём(f"значение {плохое} отклонено", True, str(e).splitlines()[0][:70])

c.rollback()
cur = c.cursor()
cur.execute("SELECT value::int FROM kabinet_data.reorder_params WHERE key='auth_enabled'")
после = cur.fetchone()[0]
ждём("после отката режим прежний", после == было, f"{после} (был {было})")
print(f"\nрасхождений: {беда}")
c.close()
