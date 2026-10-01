-- Журнал действий под человека (задание владельца 01.10.2026).
--
-- «Кто» должен быть почтой, а не ролью исполнителя. Прежняя подпись
-- «claude-code по указанию v.tereshyn» верно описывала механику, но читателю журнала
-- нужен ответ на вопрос «чьё это решение», а не «чьими руками выполнено». Решение
-- владельца: в «кто» стоит почта владельца, а то, что правка шла мимо экрана,
-- показывается ПОМЕТКОЙ рядом.
--
-- Пометка — отдельная колонка, а не текст внутри подписи: «правка через экран» и
-- «правка прямым запросом» это разные уровни доверия к записи, и различать их надо
-- полем, по которому можно отобрать, а не подстрокой в имени.

BEGIN;

ALTER TABLE kabinet_data.app_action_log
    ADD COLUMN IF NOT EXISTS via text;

COMMENT ON COLUMN kabinet_data.app_action_log.via IS
    'ui — действие через экран, db — правка прямым запросом в базу, system — запись кода (приложение или сторож)';

-- прямые правки: имя исполнителя меняем на почту владельца, механику — в пометку
UPDATE kabinet_data.app_action_log
   SET email = 'v.tereshyn@dniprom.com', via = 'db'
 WHERE email = 'claude-code по указанию v.tereshyn';

-- записи кода: это не человек, и пометка должна это говорить
UPDATE kabinet_data.app_action_log
   SET via = 'system'
 WHERE via IS NULL AND (email IN ('система', 'kabinet-app', 'watchdog') OR email IS NULL);

-- всё остальное сделано через экран
UPDATE kabinet_data.app_action_log SET via = 'ui' WHERE via IS NULL;

ALTER TABLE kabinet_data.app_action_log ALTER COLUMN via SET DEFAULT 'ui';

COMMIT;

SELECT COALESCE(via, '—') AS via, COALESCE(email, '—') AS kto, count(*) AS n
  FROM kabinet_data.app_action_log GROUP BY 1, 2 ORDER BY n DESC;
