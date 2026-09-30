-- Журнал доступа: у каждой записи должен быть автор (указание владельца 30.09.2026).
--
-- Пустое «кто» было у трёх РАЗНЫХ групп записей, и подписать их одинаково значило бы
-- соврать. Поэтому разбор по группам, а не одно обновление на всё:
--
-- 1. правки прямым запросом — их делал я по указанию владельца. Подписываем именно так,
--    с обеих сторон: и кто выполнил, и по чьему указанию;
-- 2. наблюдения за сменой режима входа — их пишет не человек, а код: приложение при
--    первом открытии страницы или сторож на прогоне. Кто именно из двоих, в старых
--    строках не записано, и выдумывать нельзя — ставим «система». У новых записей автор
--    есть: приложение подписывается `kabinet-app`, сторож `watchdog`;
-- 3. отказы на открытии «Доступа» — там человека НЕТ по существу: в Кабинет никто не
--    вошёл, почты не существует. Автор тут приложение, и это то же значение, которое
--    теперь подставляет `auth.actor()`.
--
-- Примечание Артёма: «владелец» поставлено по ошибке, правильное — «админ».

BEGIN;

-- 1. прямые правки
UPDATE kabinet_data.app_action_log
   SET email = 'claude-code по указанию v.tereshyn'
 WHERE email IS NULL
   AND action IN ('admin.set_access', 'admin.delete_user')
   AND details LIKE '%по указанию владельца%';

-- 2. наблюдения за режимом: автор — код, но который именно, в старых строках не сохранён
UPDATE kabinet_data.app_action_log
   SET email = 'система'
 WHERE email IS NULL AND action = 'auth_mode';

-- 3. отказы невошедшим
UPDATE kabinet_data.app_action_log
   SET email = 'kabinet-app'
 WHERE email IS NULL AND action = 'admin.open';

-- примечание вместо ошибочного «владелец»
UPDATE kabinet_data.app_users SET note = 'админ'
 WHERE email = 'a.kolisnyk@dniprom.com' AND note = 'владелец';

INSERT INTO kabinet_data.app_action_log (email, role, action, object_type, object_id, allowed, details)
VALUES ('claude-code по указанию v.tereshyn', NULL, 'admin.set_access', 'user',
        'a.kolisnyk@dniprom.com', true, 'примечание «владелец» исправлено на «админ»'),
       ('claude-code по указанию v.tereshyn', NULL, 'admin.set_access', 'log', NULL, true,
        'проставлен автор у записей без «кто»: прямые правки, наблюдения системы, отказы невошедшим');

COMMIT;

-- Проверка глазами: пустых «кто» остаться не должно.
SELECT COALESCE(email, '— ПУСТО —') AS кто, count(*) AS записей
  FROM kabinet_data.app_action_log GROUP BY 1 ORDER BY 2 DESC;
