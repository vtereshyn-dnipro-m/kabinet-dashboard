# TikTok Shop (с 22.10.2026)

Решение владельца 22.10.2026: подключаем, **только чтение**. Custom app «Dnipro-M», рынок Spain · Local. Магазин
берётся из Get Authorized Shops (на 22.10 — один, регион ES, LOCAL); `shop_cipher` берётся из ответа API на каждом
прогоне и нигде не хранится. Код — сразу под несколько магазинов: позже добавятся страны.

## Что есть

- `nb/tiktok_client.py` — модуль: подпись (HMAC-SHA256), белый список путей, обновление токенов, ошибки без секретов.
  Его импортируют ноутбуки TikTok и тесты (`tests/test_tiktok_client.py`).
- `nb/tiktok_auth_exchange.py` — ноутбук `Kabinet - TikTok Auth Exchange`: одноразовый код → токены в скоуп и
  проверочный Get Authorized Shops. Запускает владелец руками.
- Загрузчик в сырьё (`dnipro_m.tiktok`) — следующим PR.

## Только чтение: белый список

Клиент отказывает до запроса во всём, чего нет в `ALLOWED`. POST — ровно два поиска, у TikTok они есть только как POST
и данных не меняют (решение владельца 22.10.2026): `POST /order/202309/orders/search` и
`POST /product/202502/products/search`. Остальное — GET: `/authorization/202309/shops`, `/order/202507/orders`,
`/order/202407/orders/{id}/price_detail`, `/product/202309/products/{id}`, `/finance/202309/statements`,
`/finance/202501/statements/{id}/statement_transactions`, `/finance/202501/orders/{id}/statement_transactions`.
Новый путь — правкой `ALLOWED` по «мержи», и только на чтение. IP allowlist приложения не используем.

## Секреты — скоуп `tiktok-shop`

Ключи с дефисом, как во всех наших скоупах (решение владельца 22.10.2026).
- `app-key`, `app-secret` — вносит владелец (перезаписаны 22.10.2026 12:17 и 12:23); `app-id` — с 17.09, коду не нужен.
- `refresh-token`, `access-token`, `refresh-expires`, `access-expires` (unix, секунды) — пишет ноутбук обмена и сам
  клиент при обновлении. TikTok выдаёт новый refresh-токен при каждом обновлении — клиент записывает его первым и с
  повторами; не записался — `TokenSaveError` и падение: старый refresh уже может не действовать → повторная авторизация.
- Значения агент не читает и не выводит. Ошибки клиента секретов не содержат: у запросов авторизации app_secret и
  auth_code — в query, а исключения requests печатают URL, поэтому сетевые ошибки поднимаются без URL.

## Принципал и права (решение владельца 22.10.2026)

Джоба загрузчика — только под `kabinet-jobs-sp`; `claude-uc-ro` не расширяем и для TikTok не используем. Пока #364 не
смержен и его SQL не применён — загрузчик без расписания, прогоны владелец запускает руками.

Права `kabinet-jobs-sp` (применяет владелец, `<sp>` — Application ID):
```
databricks secrets put-acl tiktok-shop <sp> WRITE
```
и в Unity Catalog — `USE SCHEMA, CREATE TABLE, MODIFY, SELECT` только на `dnipro_m.tiktok` (SQL — с загрузчиком), плюс
Can Read на папку ноутбуков TikTok.

Снять MANAGE у `claude-uc-ro` на скоупе — когда `kabinet-jobs-sp` заработает (применяет владелец):
```
databricks secrets delete-acl tiktok-shop b1698364-6ec5-4240-8cd6-e06dd6e60856
```
На 22.10.2026 у скоупа: MANAGE у владельца и у `claude-uc-ro` (выдан 17.09 для пробы).

## Порядок

1. PR1 (клиент и обмен) → «мержи» владельца → выкладка в `/Users/v.tereshyn@dniprom.com/Kabinet - TikTok Shop/`:
   ноутбук `Kabinet - TikTok Auth Exchange` и рядом `tiktok_client.py` файлом рабочей области (не ноутбуком), сверка
   побайтно с репозиторием.
2. Владелец открывает ссылку авторизации и сразу запускает обмен с `auth_code`. Успех — «обмен прошёл» и список
   магазинов; «СЕКРЕТ НЕВЕРНЫЙ» — перезаписать `app-key` / `app-secret`.
3. После первого успешного обмена — удалить старый `Kabinet - TikTok Shop Probe` (17.09; решение владельца).
4. Загрузчик (PR2): 90 дней истории, дальше раз в сутки; проверка на 3–5 заказах с Seller Center — владельцу, до
   показа коллегам.
5. Сроки токенов — в утреннюю сводку (блок «Техника», решение владельца 22.10.2026): до конца refresh меньше 14 дней —
   WARN; access истёк, а джобы нет — WARN «запустить загрузчик руками». Отдельным PR.

Статус TTS-ES в «Справочниках» («загрузчика нет», `marketplace_attributes.no_loader_since`) загрузка в сырьё не меняет:
он смотрит на данные Кабинета, а их этот этап не трогает.
