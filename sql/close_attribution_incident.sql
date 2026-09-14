-- 14.09.2026. Инцидент [ATTRIBUTION] висел с 23.08: проверка ждала review_received_at
-- в review_request_log, а атрибуция там сломана дважды (регистр рынка в джойне и
-- скачущий review_count по семейству вариантов) — чинить в текущем виде нечего,
-- проверка из Watchdog убрана. Закрываем с пометкой, чтобы не висел вечно.
UPDATE kabinet_data.incidents
   SET status = 'resolved', resolved_at = now(), resolved_by = 'manual',
       message = message || ' | закрыт 14.09.2026: проверка убрана из Watchdog — атрибуция отзыв→запрос в текущем виде не считается (регистр рынка в джойне + review_count общий на варианты), см. комментарий в ноутбуке'
 WHERE message LIKE '[ATTRIBUTION]%' AND resolved_at IS NULL;
