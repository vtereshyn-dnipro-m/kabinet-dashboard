-- Локализованные названия стран. Сам справочник kabinet_data.countries принадлежит владельцу базы
-- (у роли Кабинета на него только SELECT), поэтому названия на трёх языках лежат рядом.
-- Источник — iso-codes (пакет pycountry), а не ручной перевод: 196 стран руками не выверить.
CREATE TABLE IF NOT EXISTS kabinet_data.country_names (
    alpha2     TEXT PRIMARY KEY,
    name_en    TEXT NOT NULL,
    name_ru    TEXT,
    name_uk    TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.country_names IS 'Названия стран на языках интерфейса; ключ — alpha2 из kabinet_data.countries.';
GRANT SELECT ON kabinet_data.country_names TO claude_code_ro, "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
SELECT count(*) FROM kabinet_data.country_names;
