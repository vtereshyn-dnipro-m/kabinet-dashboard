-- Реплика Power BI: запуск по записи в витрину и защита от неполной сборки (14.10.2026, решение владельца).
-- Применять ПОСЛЕ мержа и ДО выкладки ноутбука `Kabinet - Power BI Replica`: ноутбук пишет в pbi_replica_meta.
-- :launcher_job_id — id джобы `Kabinet - Power BI Replica (16:45)`, его выдаст `databricks jobs create`.

-- Каждый прогон реплики: заменил ли он реплику или оставил прежнюю (витрина неполная), и время сборки витрины Amazon.
-- Страницы берут отсюда строку «Данные на … В Power BI цифры обновятся до ~…» и плашку «Источник неполный»; паспорт — время сборки в ⓘ.
CREATE TABLE IF NOT EXISTS kabinet_data.pbi_replica_meta (
    id              bigserial PRIMARY KEY,
    loaded_at       timestamptz NOT NULL DEFAULT now(),   -- когда отработал прогон
    status          text NOT NULL CHECK (status IN ('replaced', 'kept')),
    source_built_at timestamptz,          -- последняя запись в dnipro_m.dnipro_m.raw_amazon_spiderweb_report (DESCRIBE HISTORY)
    shown_as_of     timestamptz,          -- на какой момент данные на страницах: replaced — сейчас, kept — прошлая замена
    detail          text,                 -- kept: какие рынки упали или пропали, было → стало
    window_days     int,
    pbi_refresh_until text                -- до скольки (Киев, ЧЧ:ММ) экран Power BI обычно подтягивает витрину — оценка по журналу доступа
);
CREATE INDEX IF NOT EXISTS pbi_replica_meta_loaded_idx ON kabinet_data.pbi_replica_meta (loaded_at DESC);
COMMENT ON TABLE kabinet_data.pbi_replica_meta IS
  'Прогоны реплики витрины Power BI: заменена или оставлена прежней (витрина неполная) и время сборки витрины Amazon.';

-- реплика идёт под владельцем; приложению — читать; принципалу джоб — на случай запуска из-под него
GRANT SELECT, INSERT ON kabinet_data.pbi_replica_meta TO "v.tereshyn@dniprom.com";
GRANT USAGE ON SEQUENCE kabinet_data.pbi_replica_meta_id_seq TO "v.tereshyn@dniprom.com";
GRANT SELECT, INSERT ON kabinet_data.pbi_replica_meta TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE ON SEQUENCE kabinet_data.pbi_replica_meta_id_seq TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.pbi_replica_meta TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- пороги защиты — в базе, не в коде
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('pbi_guard_drop_pct', 30, 'Реплика Power BI: рынок упал больше чем на столько процентов против прежней реплики по тем же дням — реплику не заменяем'),
  ('pbi_guard_min_eur', 50, 'Реплика Power BI: рынки с прежней суммой меньше этой (€ с НДС за окно) в защите не участвуют — шум'),
  ('pbi_guard_days', 14, 'Реплика Power BI: окно сравнения новой витрины с прежней репликой, дней. 14, а не 28: 13.10 сборке не хватало последней недели, и в окне 28 дней Испания упала лишь на 29 % — полные сентябрьские дни разбавляли провал; в окне 14 дней −62 %')
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest)
VALUES ('pbi_source_incomplete', 'task', 'High', 'Витрина Power BI неполная',
        'Витрина Power BI собралась неполной: продажи рынка упали больше порога против прежней реплики по тем же дням или '
        'рынок пропал. Реплику Кабинета не заменяли — на страницах цифры прошлой полной сборки. Закрывается сама, когда '
        'витрина снова полная.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

-- запускалка 16:45 — без своего пульса (запускает основную реплику), поэтому правило по job_id
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:launcher_job_id, 'Kabinet - Power BI Replica (16:45)', 26, 'ежедневно 16:45 Kyiv', true,
        'Запускает Kabinet - Power BI Replica, чтобы подхватить дневные заказы Leroy Merlin, ManoMano и Carrefour')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
