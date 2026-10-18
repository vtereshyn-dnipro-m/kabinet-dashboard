-- Сводка цикла автономной работы в бот (19.10.2026, предложение; применять после мержа владельцем).
-- Агент кладёт сводку строкой (scratchpad/cycle_report.py, роль claude_code_rw), джоба `Kabinet - Agent Cycle Report`
-- (под владельцем) отправляет неотправленные в основной чат и ставит sent_at. Секрет бота агент не трогает — им
-- пользуется только джоба. :cycle_job_id — id джобы, его выдаст `databricks jobs create`.

CREATE TABLE IF NOT EXISTS kabinet_data.agent_cycle_reports (
    id          bigserial PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    title       text NOT NULL,             -- «Цикл 19.10 14:00» — короткая шапка
    done        text,                      -- что сделано (строки через перевод строки)
    merged      text,                      -- что смержено САМ (уровень «сам») — номера PR и одна фраза
    waiting     text,                      -- что ждёт владельца: «мержи #N», ответ, секрет
    problems    text,                      -- что не получилось / красные проверки
    sent_at     timestamptz,               -- когда ушло в бот; NULL — ещё не отправлено
    send_error  text                       -- последняя ошибка отправки
);
CREATE INDEX IF NOT EXISTS agent_cycle_reports_unsent_idx ON kabinet_data.agent_cycle_reports (id) WHERE sent_at IS NULL;
COMMENT ON TABLE kabinet_data.agent_cycle_reports IS
  'Сводки циклов автономной работы агента; отправляет в бот джоба Kabinet - Agent Cycle Report.';

GRANT SELECT, UPDATE ON kabinet_data.agent_cycle_reports TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.agent_cycle_reports TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, UPDATE ON kabinet_data.agent_cycle_reports TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- ── вторая часть: после `databricks jobs create` ──
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:cycle_job_id, 'Kabinet - Agent Cycle Report', 26, 'каждые 15 мин 08:00–22:45 Kyiv', true,
        'Отправляет в бот сводки циклов автономной работы агента')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
