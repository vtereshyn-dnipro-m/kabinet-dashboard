-- Риски входа (14.10.2026, решение владельца). Применять ПОСЛЕ мержа, ДО выкладки кода Кабинета и Listing Suite:
-- код зовёт функцию и читает колонку.
--
-- 1) Карточка привязывается к Google ID (sub), а не только к почте. Адрес в Workspace могут удалить и завести заново
--    на другого человека — без привязки он вошёл бы в действующую карточку прежнего, с его ролями в обоих продуктах.
-- 2) Возраст входа: Streamlit держит cookie входа 30 дней и Google не перепроверяет; удалённый в Workspace сотрудник
--    с открытым браузером входил бы до 30 дней. Теперь вход старше auth_max_login_hours отправляет на повторный вход
--    через Google — а его удалённый аккаунт уже не пройдёт.

ALTER TABLE kabinet_data.app_users ADD COLUMN IF NOT EXISTS google_sub text;
COMMENT ON COLUMN kabinet_data.app_users.google_sub IS
  'Google ID (claim sub) человека, которому принадлежит карточка. Пусто — ещё не входил после 14.10.2026; первый вход привязывает.';
CREATE UNIQUE INDEX IF NOT EXISTS app_users_google_sub_uq ON kabinet_data.app_users (google_sub)
  WHERE google_sub IS NOT NULL;

INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('auth_max_login_hours', 168,
        'Сколько часов действует вход через Google в Кабинет и Listing Suite (168 = 7 дней). Старше — повторный вход: '
        'удалённый в Workspace аккаунт его не пройдёт. 24 — перепроверка раз в сутки.')
ON CONFLICT (key) DO NOTHING;

-- Одно правило на оба продукта. Возвращает:
--   'none'      — карточки нет (дальше обычный первый вход по домену);
--   'bound'     — карточка без Google ID, привязали к этому человеку;
--   'ok'        — карточка этого человека;
--   'archived:<адрес>' — карточка принадлежала ДРУГОМУ Google-аккаунту: она уходит в архив под адресом
--                 «почта~ГГГГММДД-ЧЧММ» (выключена, роли и страны при ней — история видна на «Доступе»),
--                 а по самой почте карточки больше нет — дальше обычный первый вход: «Просмотр» в обоих продуктах
--                 для рабочей почты, отказ для адреса вне домена.
-- SECURITY DEFINER: у принципала приложения нет UPDATE на app_user_countries, а перенос стран в архив нужен.
CREATE OR REPLACE FUNCTION kabinet_data.app_user_bind_sub(p_email text, p_sub text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = kabinet_data, pg_temp AS $$
DECLARE
  v_email text := lower(trim(p_email));
  v_sub   text;
  v_arch  text;
BEGIN
  IF coalesce(p_sub, '') = '' OR coalesce(v_email, '') = '' THEN
    RETURN 'no_sub';
  END IF;
  SELECT google_sub INTO v_sub FROM app_users WHERE email = v_email FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'none';
  END IF;
  IF v_sub IS NULL THEN
    UPDATE app_users SET google_sub = p_sub WHERE email = v_email;
    RETURN 'bound';
  END IF;
  IF v_sub = p_sub THEN
    RETURN 'ok';
  END IF;
  v_arch := v_email || '~' || to_char(now() AT TIME ZONE 'Europe/Kyiv', 'YYYYMMDD-HH24MI');
  -- снять Google ID с исходной строки до копии: уникальный индекс не пустил бы две строки с одним sub
  UPDATE app_users SET google_sub = NULL WHERE email = v_email;
  INSERT INTO app_users
  SELECT (jsonb_populate_record(NULL::app_users, to_jsonb(u) || jsonb_build_object(
            'email', v_arch, 'is_active', false, 'google_sub', v_sub,
            'note', coalesce(u.note || ' · ', '') || 'архив ' || to_char(now() AT TIME ZONE 'Europe/Kyiv', 'DD.MM.YYYY')
                    || ': адрес ' || v_email || ' перешёл к другому Google-аккаунту'))).*
    FROM app_users u WHERE u.email = v_email;
  INSERT INTO app_user_countries
  SELECT (jsonb_populate_record(NULL::app_user_countries, to_jsonb(c) || jsonb_build_object('email', v_arch))).*
    FROM app_user_countries c WHERE c.email = v_email;
  DELETE FROM app_user_countries WHERE email = v_email;
  DELETE FROM app_users WHERE email = v_email;
  RETURN 'archived:' || v_arch;
END $$;

REVOKE ALL ON FUNCTION kabinet_data.app_user_bind_sub(text, text) FROM PUBLIC;
-- принципал приложения: им ходят и Кабинет, и Listing Suite
GRANT EXECUTE ON FUNCTION kabinet_data.app_user_bind_sub(text, text) TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.reorder_params TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- журнал входов: две новые причины — «вход устарел, повторный вход» и «адрес у другого Google-аккаунта»
ALTER TABLE kabinet_data.app_login_log DROP CONSTRAINT IF EXISTS app_login_log_result_check;
ALTER TABLE kabinet_data.app_login_log ADD CONSTRAINT app_login_log_result_check
  CHECK (result = ANY (ARRAY['ok', 'first_login', 'denied_domain', 'denied_disabled', 'logout', 'relogin', 'reassigned']));
