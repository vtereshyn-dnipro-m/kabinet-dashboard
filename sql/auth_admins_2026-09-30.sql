-- Доступ: рабочая почта Артёма вместо личной (указание владельца 30.09.2026).
--
-- Личный gmail заводился как единственное исключение из правила домена, пока рабочей
-- почты не было. Теперь она есть, и исключение больше не нужно: a.kolisnyk@dniprom.com
-- проходит по домену, как все остальные.
--
-- Строка с gmail НЕ удаляется, а отключается. Удаления людей в Кабинете нет вовсе:
-- журналы входов и действий ссылаются на почту, и по удалённой записи потом не понять,
-- кто и что делал. `is_active = false` — это «доступ снят», и вход по такой строке не
-- проходит даже у своего домена, не говоря о чужом.
--
-- Записи в журнал действий добавлены руками, потому что правка идёт прямым запросом, а
-- не через «Доступ»: иначе в истории доступа осталась бы дыра ровно там, где менялись
-- права администратора. Почта автора пустая намеренно — подписать это чьим-то именем
-- значило бы сказать, что человек нажал кнопку, а он не нажимал.

BEGIN;

-- 1. рабочая почта
INSERT INTO kabinet_data.app_users (email, role, note, created_by)
VALUES ('a.kolisnyk@dniprom.com', 'admin', 'рабочая почта вместо личной', 'owner:2026-09-30')
ON CONFLICT (email) DO UPDATE
   SET role = 'admin', is_active = true,
       note = COALESCE(kabinet_data.app_users.note, 'рабочая почта вместо личной');

-- 2. личная почта — доступ снят
UPDATE kabinet_data.app_users
   SET is_active = false,
       note = 'доступ снят 30.09.2026: перешёл на a.kolisnyk@dniprom.com'
 WHERE email = 'artem.kolesnik1@gmail.com';

-- 3. журнал
INSERT INTO kabinet_data.app_action_log (email, role, action, object_type, object_id, allowed, details)
VALUES (NULL, NULL, 'admin.set_access', 'user', 'a.kolisnyk@dniprom.com', true,
        'заведён администратором по указанию владельца, прямым запросом'),
       (NULL, NULL, 'admin.set_access', 'user', 'artem.kolesnik1@gmail.com', true,
        'доступ снят по указанию владельца: перешёл на рабочую почту');

COMMIT;

-- Проверка глазами после прогона: кто входит и с какой ролью.
SELECT email, role, is_active, COALESCE(note, '') AS note
  FROM kabinet_data.app_users ORDER BY is_active DESC, email;
