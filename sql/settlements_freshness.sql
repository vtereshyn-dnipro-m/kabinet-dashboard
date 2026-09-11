-- Правило свежести на реплику Settlement. Lakebase, kabinet_data.
--
-- Запись: загрузчик ежедневный, порог 30 ч — как у остальных суточных.
-- Содержимое: расчёты закрываются раз в две недели, значит возраст
-- последней проводки в норме качается от 2 до 16 дней. Порог 21 день
-- (504 ч) ловит один пропущенный цикл и молчит на здоровом.

BEGIN;

INSERT INTO kabinet_data.data_freshness_rules
       (table_name, date_column, max_age_hours,
        content_date_column, max_content_age_hours,
        source_type, owner_role, is_active, comment, updated_at)
VALUES ('kabinet_data.raw_amazon_settlements', 'loaded_at', 30, 'posted_date', 504,
        'lakebase', 'finance', true,
        'Settlement V2 по всем рынкам, загрузчик Kabinet - Settlements Loader, ежедневно. '
        'Расчёты закрываются раз в две недели: возраст последней проводки в норме 2–16 дней, '
        'порог 21 день ловит пропущенный цикл.', now())
ON CONFLICT (table_name) DO UPDATE
   SET date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
       content_date_column = EXCLUDED.content_date_column,
       max_content_age_hours = EXCLUDED.max_content_age_hours,
       comment = EXCLUDED.comment, updated_at = now();

COMMIT;

SELECT table_name, max_age_hours, content_date_column, max_content_age_hours, is_active
  FROM kabinet_data.data_freshness_rules WHERE table_name = 'kabinet_data.raw_amazon_settlements';
