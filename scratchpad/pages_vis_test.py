# -*- coding: utf-8 -*-
"""Видимость страниц: закрывает ли снятая галочка и видит ли всё QA-агент."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
import auth

беда = 0
def ждём(что, ожидание, факт):
    global беда
    if bool(ожидание) != bool(факт):
        print(f"  ПРОВАЛ {что}: ждали {ожидание}, вышло {факт}"); беда += 1
    else:
        print(f"  ок     {что}")

def роль(r, qa=False):
    auth.current = lambda: auth.User(email="x@dniprom.com", role=r, countries={"ES"},
                                     logged_in=True, is_qa=qa)

auth.mode = lambda: auth.MODE_ON

print("=== по умолчанию видно всё ===")
auth._matrix = lambda: None          # таблица не прочиталась — работает запасная из кода
for r in (auth.VIEWER, auth.COUNTRY_MANAGER, auth.DEMAND_PLANNER, auth.ADMIN):
    роль(r)
    ждём(f"{r}: видит все десять страниц", True,
         all(auth.can(a) for a in auth.PAGE_ACTIONS))

print("=== снятая галочка закрывает ===")
открыто = {a: {auth.VIEWER, auth.COUNTRY_MANAGER, auth.DEMAND_PLANNER, auth.ADMIN}
           for a in auth.PAGE_ACTIONS}
закрыто = dict(открыто); закрыто["page.money"] = {auth.ADMIN}
auth._matrix = lambda: закрыто
роль(auth.VIEWER)
ждём("«Деньги» закрыты просмотру", False, auth.can("page.money"))
ждём("остальные девять открыты", True,
     all(auth.can(a) for a in auth.PAGE_ACTIONS if a != "page.money"))
роль(auth.ADMIN)
ждём("админу «Деньги» открыты", True, auth.can("page.money"))

print("=== QA-агент: видит всё, не может ничего ===")
роль(auth.VIEWER, qa=True)
ждём("робот видит все страницы", True, all(auth.can(a) for a in auth.PAGE_ACTIONS))
ждём("робот видит даже закрытые просмотру", True, auth.can("page.money"))
ждём("роботу нельзя ни одно действие", True,
     not any(auth.can(d, "ES") for d in
             ("forecast.edit", "forecast.post", "ads.act", "dict.edit",
              "reorder.act", "incident.act", "admin")))

print("=== «Доступ» отдельным правом, а не страницей ===")
ждём("page.access среди прав страниц нет", True, "page.access" not in auth.PAGE_ACTIONS)
роль(auth.ADMIN)
auth._matrix = lambda: None
ждём("админка у админа открыта", True, auth.can("admin"))
роль(auth.DEMAND_PLANNER)
ждём("админка планировщику закрыта", False, auth.can("admin"))

print(f"\nрасхождений: {беда}")
