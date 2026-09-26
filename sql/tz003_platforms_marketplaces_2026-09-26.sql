-- ТЗ 003: площадки и маркетплейсы. Реквизиты, которых не было, лежат рядом с чужими таблицами:
-- `platforms` и `marketplaces_new` принадлежат владельцу базы, и роль Кабинета колонок в них не добавит
-- (тот же случай, что со складами). Строки в них править можно — этим и пользуемся для названий,
-- страны, валюты и активности маркетплейса.

-- ── площадка: активность, комментарий и три обозначения ассортиментной структуры ──
-- По ТЗ §3 и §5 обозначения задаются НА ПЛОЩАДКЕ и используются её маркетплейсами без копий.
-- Сейчас они лежат в трёх колонках `marketplaces_new` — по факту одинаковые внутри площадки
-- (проверено: у каждой площадки ровно одно значение), так что перенос наверх ничего не теряет.
CREATE TABLE IF NOT EXISTS kabinet_data.platform_attributes (
    platform_id           int  PRIMARY KEY,   -- platforms.id; FK нет: таблица владельца, REFERENCES роли не выдан
    is_active             boolean NOT NULL DEFAULT true,
    comment               text,
    variation_group_label text,               -- «Parent ASIN» у Amazon; пусто — площадка без вариационных семей
    variation_label       text,               -- «Child ASIN»
    product_entity_label  text,               -- «ASIN», «MMID»
    peid_format_hint      text,               -- правило формата PeID словами (ТЗ §3)
    updated_at            timestamptz NOT NULL DEFAULT now(),
    updated_by            text NOT NULL DEFAULT 'kabinet'
);
COMMENT ON TABLE kabinet_data.platform_attributes IS
    'ТЗ 003: реквизиты площадки, которых нет в kabinet_data.platforms (таблица владельца): активность, комментарий, обозначения ассортиментной структуры.';

INSERT INTO kabinet_data.platform_attributes
    (platform_id, is_active, variation_group_label, variation_label, product_entity_label, updated_by)
SELECT p.id, true,
       max(m.variation_group_label), max(m.variation_label), max(m.product_entity_label), 'migration:tz003'
FROM kabinet_data.platforms p
LEFT JOIN kabinet_data.marketplaces_new m ON m.platform_short = p.short_name
GROUP BY p.id
ON CONFLICT (platform_id) DO NOTHING;

-- ── маркетплейс: внешние идентификаторы и ссылка на сайт ──
CREATE TABLE IF NOT EXISTS kabinet_data.marketplace_attributes (
    marketplace_id  int  PRIMARY KEY,         -- marketplaces_new.id
    external_system text,                     -- заполняется в паре с external_id (ТЗ §4)
    external_id     text,
    website_url     text,                     -- только https, проверяется на экране
    updated_at      timestamptz NOT NULL DEFAULT now(),
    updated_by      text NOT NULL DEFAULT 'kabinet',
    CONSTRAINT marketplace_attributes_pair CHECK (
        (external_system IS NULL AND external_id IS NULL) OR
        (external_system IS NOT NULL AND external_id IS NOT NULL))
);
-- уникальность в пределах пары «внешняя система + внешний ид»: один и тот же ид в разных системах допустим
CREATE UNIQUE INDEX IF NOT EXISTS marketplace_attributes_ext_uq
    ON kabinet_data.marketplace_attributes (external_system, external_id)
    WHERE external_system IS NOT NULL;

-- ── валюты: перечень ISO 4217, чтобы валюта выбиралась, а не вводилась текстом (ТЗ §4) ──
CREATE TABLE IF NOT EXISTS kabinet_data.currencies (
    code      char(3) PRIMARY KEY,
    name      text NOT NULL,
    is_active boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE kabinet_data.currencies IS 'ISO 4217: перечень для выбора валюты маркетплейса (ТЗ 003 §4). Наполняется scratchpad/currencies.py из pycountry.';

-- ── журнал справочника: смена площадки и страны пишутся по ТЗ §5 ──
CREATE TABLE IF NOT EXISTS kabinet_data.marketplace_change_log (
    id          bigserial PRIMARY KEY,
    object_type text NOT NULL CHECK (object_type IN ('platform', 'marketplace')),
    object_id   int  NOT NULL,
    field       text NOT NULL,
    old_value   text,
    new_value   text,
    actor       text NOT NULL,
    changed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS marketplace_change_log_obj_idx
    ON kabinet_data.marketplace_change_log (object_type, object_id, changed_at DESC);

GRANT SELECT ON kabinet_data.platform_attributes, kabinet_data.marketplace_attributes,
      kabinet_data.currencies, kabinet_data.marketplace_change_log
   TO claude_code_ro, "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT INSERT, UPDATE, DELETE ON kabinet_data.platform_attributes, kabinet_data.marketplace_attributes,
      kabinet_data.marketplace_change_log
   TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.marketplace_change_log_id_seq
   TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- ── что можно выбирать в новых операциях (ТЗ 003 §7) ──
-- Неактивная площадка закрывает свои маркетплейсы для новых допусков, пулов, прогнозов и PeID,
-- даже если сам маркетплейс активен. Держим это одним вью, чтобы условие не расползлось по экранам
-- в пяти написаниях: сегодня все площадки активны, и поведение не меняется, но правило уже работает.
CREATE OR REPLACE VIEW kabinet_data.v_marketplaces_selectable AS
SELECT m.id, m.code, m.name, m.platform_short, m.country_alpha2, m.currency, m.legacy_code, m.amazon_id,
       COALESCE(a.variation_group_label, m.variation_group_label) AS variation_group_label,
       COALESCE(a.variation_label,       m.variation_label)       AS variation_label,
       COALESCE(a.product_entity_label,  m.product_entity_label)  AS product_entity_label
FROM kabinet_data.marketplaces_new m
JOIN kabinet_data.platforms p ON p.short_name = m.platform_short
LEFT JOIN kabinet_data.platform_attributes a ON a.platform_id = p.id
WHERE m.is_active AND COALESCE(a.is_active, true);
COMMENT ON VIEW kabinet_data.v_marketplaces_selectable IS
    'ТЗ 003 §7: маркетплейсы, доступные для новых операций — активные и у активной площадки. Обозначения ассортиментной структуры берутся с площадки (ТЗ §3), колонки маркетплейса остались фолбэком на время перехода.';

GRANT SELECT ON kabinet_data.v_marketplaces_selectable TO claude_code_ro,
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
