# -*- coding: utf-8 -*-
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
import auth
беда = 0
def ждём(что, ожидание, факт):
    global беда
    if bool(ожидание) != bool(факт):
        print(f"  РАСХОЖДЕНИЕ: {что} — ждали {ожидание}, получили {факт}"); беда += 1

АКТИВЕН   = {"role": "viewer", "is_active": True,  "countries": []}
ОТКЛЮЧЁН  = {"role": "admin",  "is_active": False, "countries": []}

ждём("рабочая почта, строки нет — пускаем", True,
     auth._allowed_to_enter("kto@dniprom.com", None))
ждём("рабочая почта, строка активна", True,
     auth._allowed_to_enter("kto@dniprom.com", АКТИВЕН))
ждём("рабочая почта, доступ СНЯТ — не пускаем даже своего", False,
     auth._allowed_to_enter("kto@dniprom.com", ОТКЛЮЧЁН))
ждём("чужой домен без строки — отказ", False,
     auth._allowed_to_enter("artem.kolesnik1@gmail.com", None))
ждём("чужой домен со строкой — исключение работает", True,
     auth._allowed_to_enter("artem.kolesnik1@gmail.com", АКТИВЕН))
ждём("чужой домен, строка отключена", False,
     auth._allowed_to_enter("artem.kolesnik1@gmail.com", ОТКЛЮЧЁН))
ждём("похожий домен не проходит", False,
     auth._allowed_to_enter("kto@notdniprom.com", None))
ждём("поддомен не проходит", False,
     auth._allowed_to_enter("kto@mail.dniprom.com.evil.ru", None))

from datetime import date, timedelta
ВЧЕРА   = {"role": "admin", "is_active": True, "expired": True,
           "access_until": date.today() - timedelta(days=1)}
СЕГОДНЯ = {"role": "admin", "is_active": True, "expired": False,
           "access_until": date.today()}
ЗАВТРА  = {"role": "admin", "is_active": True, "expired": False,
           "access_until": date.today() + timedelta(days=1)}
БЕЗ_СРОКА = {"role": "admin", "is_active": True, "expired": False, "access_until": None}

ждём("срок истёк вчера — не пускаем", False, auth._allowed_to_enter("kto@dniprom.com", ВЧЕРА))
ждём("последний день включительно — пускаем", True, auth._allowed_to_enter("kto@dniprom.com", СЕГОДНЯ))
ждём("срок завтра — пускаем", True, auth._allowed_to_enter("kto@dniprom.com", ЗАВТРА))
ждём("без срока — пускаем", True, auth._allowed_to_enter("kto@dniprom.com", БЕЗ_СРОКА))
ждём("истёкший срок у исключения вне домена — не пускаем", False,
     auth._allowed_to_enter("kto@gmail.com", ВЧЕРА))
ждём("снятый доступ важнее живого срока", False,
     auth._allowed_to_enter("kto@dniprom.com", dict(ЗАВТРА, is_active=False)))
print(f"расхождений: {беда}")
