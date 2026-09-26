-- ТЗ 002: справочник «Страны». Сама таблица `countries` принадлежит владельцу базы: строки править
-- можно (у приложения есть INSERT и UPDATE), колонок добавить нельзя. Поэтому журнал изменений —
-- отдельной таблицей рядом, как и у остальных справочников.
--
-- Про Internal ID. ТЗ §2 требует системный неизменяемый ключ, а §6 — строить связи по нему. В нашей
-- базе эту роль исполняет `alpha2`: он первичный ключ, неизменяем по смыслу (ISO 3166-1 не
-- переиспользует коды) и на него уже построены все ссылки, включая внешний ключ маркетплейсов.
-- Отдельный surrogate id завести нельзя — ALTER чужой таблицы роль Кабинета не может, — и заводить
-- его было бы вредно: пришлось бы переписать ссылки во всех кабинетах ради второго ключа к тому же.
CREATE TABLE IF NOT EXISTS kabinet_data.country_change_log (
    id         bigserial PRIMARY KEY,
    alpha2     char(2) NOT NULL,
    field      text    NOT NULL,
    old_value  text,
    new_value  text,
    actor      text    NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS country_change_log_alpha2_idx
    ON kabinet_data.country_change_log (alpha2, changed_at DESC);
COMMENT ON TABLE kabinet_data.country_change_log IS
    'ТЗ 002 §7: история справочника стран — кто, когда и что изменил.';

GRANT SELECT ON kabinet_data.country_change_log TO claude_code_ro,
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT INSERT ON kabinet_data.country_change_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.country_change_log_id_seq
   TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Нормализованное название для контроля дублей (ТЗ §4): регистр не важен, пробелы по краям срезаны,
-- несколько пробелов внутри сведены к одному, дефисы и прочие знаки сохранены. Отображаемое название
-- при этом хранится как ввёл человек — нормализация нужна только для проверки.
CREATE OR REPLACE FUNCTION kabinet_data.country_name_key(p_name text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT lower(regexp_replace(btrim(coalesce(p_name, '')), '\s+', ' ', 'g'))
$$;
GRANT EXECUTE ON FUNCTION kabinet_data.country_name_key(text) TO
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
