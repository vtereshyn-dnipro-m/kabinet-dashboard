# -*- coding: utf-8 -*-
"""Как журнал выглядит человеку: прогоняем ту же логику показа против живой базы."""
import sys, json, psycopg2, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
from i18n import TRANSLATIONS
from util import as_text
import auth

def t(key, **kw):
    v = TRANSLATIONS.get(key, {}).get("ru", key)
    for k, val in kw.items():
        v = v.replace("{" + k + "}", str(val))
    return v

ROLE_LABEL = {r: t(f"auth.role.{r}") for r in
              ("viewer", "country_manager", "demand_planner", "admin")}
СИСТЕМНЫЕ = {"система", "kabinet-app", "watchdog", "qa-агент"}
СЛУЖЕБНЫЕ = {"admin.open", "notify_new_user", "notify_new_user_wd", "auth_mode_notify"}

def кто_словом(почта, откуда):
    почта = as_text(почта, "—")
    if почта in СИСТЕМНЫЕ:
        return t(f"auth.log.who.{почта}")
    return f'{почта} · {t("auth.log.via_db")}' if откуда == "db" else почта

def имя_объекта(тип, ид):
    тип, ид = as_text(тип), as_text(ид)
    if not тип and not ид: return "—"
    if тип == "permission" and "/" in ид:
        д, р = ид.split("/", 1)
        return f'{t("auth.action." + д)} — {ROLE_LABEL.get(р, р)}'
    if тип == "mode":  return t(f"auth.admin.mode_{ид}") if ид in ("0","1","2") else ид
    if тип == "user":  return ид or "—"
    if тип == "page":  return t("auth.admin.title") if ид == "access" else ид
    if тип == "qa":    return t("auth.admin.qa")
    if тип == "log":   return t("auth.admin.actions")
    return ид or тип

DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
c = psycopg2.connect(DSN); cur = c.cursor()
cur.execute("""SELECT ts, email, action, COALESCE(object_type,''), COALESCE(object_id,''),
                      allowed, COALESCE(via,'ui')
                 FROM kabinet_data.app_action_log ORDER BY ts DESC, id DESC""")
строки = cur.fetchall()
видно = [r for r in строки if r[2] not in СЛУЖЕБНЫЕ]
print(f"всего записей {len(строки)}, служебных {len(строки)-len(видно)}, показано {len(видно)}\n")
print(f"{'Когда':<12} {'Кто':<44} {'Что сделал':<34} {'С чем':<28} Итог")
print("-" * 128)
for ts, email, action, тип, ид, ok, via in видно:
    print(f"{ts:%d.%m %H:%M}  {кто_словом(email, via):<44} "
          f"{t('auth.log.act.' + action):<34} {имя_объекта(тип, ид)[:27]:<28} "
          f"{'✓' if ok else t('auth.log.denied')}")
print("\n— служебные (скрыты по умолчанию) —")
for ts, email, action, тип, ид, ok, via in строки:
    if action in СЛУЖЕБНЫЕ:
        print(f"{ts:%d.%m %H:%M}  {кто_словом(email, via):<44} {t('auth.log.act.' + action)}")
