-- Журнал «доехал ли мерж без ребута» (T-11, 19.10.2026): строка на старт процесса приложения и на каждое
-- перечитывание модулей после мержа (deploy_log.py). Пишут оба приложения под принципалом приложения.
-- Применяет роль Кабинета claude_code_rw.
CREATE TABLE IF NOT EXISTS kabinet_data.app_deploy_log (
    id                 bigserial PRIMARY KEY,
    at                 timestamptz NOT NULL DEFAULT now(),
    app                text NOT NULL,              -- kabinet / listing_suite
    kind               text NOT NULL CHECK (kind IN ('start', 'reload', 'unknown')),
    commit_sha         text,                       -- коммит на диске в момент события
    imported_at        timestamptz,                -- когда модуль импортирован (то есть когда случилось событие)
    process_started_at timestamptz,                -- время старта процесса (/proc/self/stat); пусто — не узнали
    pid                int
);
CREATE INDEX IF NOT EXISTS app_deploy_log_at_idx ON kabinet_data.app_deploy_log (at DESC);
COMMENT ON TABLE kabinet_data.app_deploy_log IS
  'Старты процесса приложения (start) и перечитывания модулей после мержа (reload) — проверка «без ребута».';

GRANT SELECT, INSERT ON kabinet_data.app_deploy_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE ON SEQUENCE kabinet_data.app_deploy_log_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
