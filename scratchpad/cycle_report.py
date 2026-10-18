"""Положить сводку цикла автономной работы в kabinet_data.agent_cycle_reports — в бот её отправит джоба
`Kabinet - Agent Cycle Report` (секрет бота агент не трогает). Схема — docs/autonomy.md.

    python3 scratchpad/cycle_report.py --title "Цикл 19.10 14:00" \
        --done "T-1: PR #330 открыт, проверка ок" --merged "#331 docs: факты по остаткам" \
        --waiting "мержи #330" --problems ""

Пустые поля в сообщение не попадают. Пишет под ролью из .mcp.json (lakebase-kabinet), ничего кроме этой строки.
"""
import argparse, json, os
import psycopg2

ap = argparse.ArgumentParser()
ap.add_argument("--title", required=True)
for k in ("done", "merged", "waiting", "problems"):
    ap.add_argument(f"--{k}", default="")
a = ap.parse_args()
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dsn = json.load(open(os.path.join(root, ".mcp.json")))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
with psycopg2.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.agent_cycle_reports (title, done, merged, waiting, problems)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (a.title, a.done or None, a.merged or None, a.waiting or None, a.problems or None))
    print("сводка записана, id", cur.fetchone()[0], "— уйдёт в бот в течение 15 минут")
