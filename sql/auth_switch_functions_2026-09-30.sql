-- Рубильник входа: две функции вместо права писать в reorder_params.
--
-- Почему не GRANT UPDATE на таблицу, как просили буквально. В `reorder_params` лежат
-- ВСЕ пороги Кабинета — горизонт автозаказа, пол ставки по рекламе, окна свежести,
-- пороги сторожа. Право писать в таблицу ради одного переключателя дало бы заодно
-- право менять их все, причём молча: у большинства порогов нет ни журнала, ни экрана,
-- и расхождение «в базе новое значение, поведение старое» ищется только чтением кода.
-- Резервному у рубильника нужна ровно одна возможность, и она здесь одна.
--
-- Вторая причина, не менее важная. Прямой UPDATE оставил бы в журнале доступа автором
-- «систему»: смену замечают приложение и сторож, а кто её сделал — не знает никто.
-- Функция пишет, КТО переключил, и пишет это отдельным действием `auth_mode_set`, а не
-- `auth_mode`. Разные коды здесь принципиальны: приложение и сторож сравнивают себя с
-- последней записью `auth_mode`, и если функция писала бы её же, они сочли бы, что
-- смену уже заметили, — и Telegram о переключении НЕ ушёл бы. То есть аккуратная
-- запись в журнал выключила бы оповещение.

-- Показать текущий режим. Отдельная функция, чтобы резервному не пришлось давать
-- SELECT на таблицу целиком: тогда он видит и все остальные пороги.
CREATE OR REPLACE FUNCTION kabinet_data.get_auth_mode()
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = kabinet_data, pg_temp
AS $$
    SELECT 'Режим входа: ' || value::int || ' — ' ||
           CASE value::int
               WHEN 2 THEN 'раскатка: входа нет, кнопки у всех'
               WHEN 1 THEN 'вход обязателен, роли работают'
               WHEN 0 THEN 'АВАРИЯ: входа нет, у всех «Просмотр»'
               ELSE 'неизвестное значение'
           END
      FROM kabinet_data.reorder_params WHERE key = 'auth_enabled';
$$;

-- Переключить режим.
CREATE OR REPLACE FUNCTION kabinet_data.set_auth_mode(новый int)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
-- search_path задан явно: без него вызывающий может подставить свою схему и увести
-- запросы функции в чужие таблицы — обычная дыра SECURITY DEFINER
SET search_path = kabinet_data, pg_temp
AS $$
DECLARE
    было int;
    кто  text := session_user;   -- именно session_user: current_user внутри SECURITY
                                 -- DEFINER это владелец функции, а не тот, кто вызвал
    слово text;
BEGIN
    IF новый NOT IN (0, 1, 2) THEN
        RAISE EXCEPTION 'Режим бывает только 0, 1 или 2, а не %. 2 — раскатка, 1 — вход обязателен, 0 — авария', новый;
    END IF;

    SELECT value::int INTO было FROM kabinet_data.reorder_params WHERE key = 'auth_enabled';
    IF было IS NULL THEN
        RAISE EXCEPTION 'Настройки auth_enabled нет в reorder_params — переключать нечего, позовите разработчика';
    END IF;

    слово := CASE новый
                WHEN 2 THEN 'раскатка: входа нет, кнопки у всех'
                WHEN 1 THEN 'вход обязателен, роли работают'
                WHEN 0 THEN 'АВАРИЯ: входа нет, у всех «Просмотр»'
             END;

    IF было = новый THEN
        RETURN 'Уже ' || новый || ' — ' || слово || '. Ничего не менялось.';
    END IF;

    UPDATE kabinet_data.reorder_params
       SET value = новый, updated_at = now()
     WHERE key = 'auth_enabled';

    INSERT INTO kabinet_data.app_action_log
        (email, role, action, object_type, object_id, allowed, details)
    VALUES (кто, NULL, 'auth_mode_set', 'mode', новый::text, true,
            'переключено вручную: было ' || было || ', стало ' || новый);

    RETURN 'Было ' || было || ', стало ' || новый || ' — ' || слово ||
           '. Переключил: ' || кто ||
           '. Подействует в течение минуты; сообщение уйдёт в Telegram.';
END $$;

COMMENT ON FUNCTION kabinet_data.set_auth_mode(int) IS
    'Рубильник входа. 2 раскатка, 1 вход обязателен, 0 авария. Пишет в журнал, кто переключил.';

-- Проверка глазами.
SELECT kabinet_data.get_auth_mode() AS сейчас;
