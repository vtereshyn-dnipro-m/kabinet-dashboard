-- Вход через Google в Listing Suite: роли, права, режим, журналы.
-- 02.10.2026. Выполняется от роли Кабинета (claude_code_rw/ro — она владеет app_*).
--
-- Устройство: один список людей и одна матрица прав на два продукта. Разделяет их
-- не таблица, а ЗНАЧЕНИЕ: у человека две роли в двух колонках, у действия префикс
-- `ls.`, у записи журнала колонка `product`. Второй список людей расходился бы с
-- первым молча — и обнаружилось бы это в день, когда кого-то уволили, а доступ
-- остался.
BEGIN;

-- ── роль в Listing Suite: вторая колонка, а не вторая строка ──────────────────
-- Пустая `ls_role` означает «доступа в Listing Suite нет» и это НЕ «Просмотр»:
-- иначе каждый, кого завели в Кабинет, автоматически получал бы чужой продукт.
ALTER TABLE kabinet_data.app_users ADD COLUMN IF NOT EXISTS ls_role text;

ALTER TABLE kabinet_data.app_users DROP CONSTRAINT IF EXISTS app_users_ls_role_check;
ALTER TABLE kabinet_data.app_users ADD CONSTRAINT app_users_ls_role_check
    CHECK (ls_role IS NULL
           OR ls_role = ANY (ARRAY['viewer','content_manager','approver','admin']));

-- ── какому продукту принадлежит запись ───────────────────────────────────────
-- Значение по умолчанию — 'kabinet': все записи, сделанные до этой правки, его и
-- касаются, и дописывать их задним числом нечем.
ALTER TABLE kabinet_data.app_action_log
    ADD COLUMN IF NOT EXISTS product text NOT NULL DEFAULT 'kabinet';
ALTER TABLE kabinet_data.app_login_log
    ADD COLUMN IF NOT EXISTS product text NOT NULL DEFAULT 'kabinet';
ALTER TABLE kabinet_data.qa_tokens
    ADD COLUMN IF NOT EXISTS product text NOT NULL DEFAULT 'kabinet';

ALTER TABLE kabinet_data.app_action_log DROP CONSTRAINT IF EXISTS app_action_log_product_check;
ALTER TABLE kabinet_data.app_action_log ADD CONSTRAINT app_action_log_product_check
    CHECK (product = ANY (ARRAY['kabinet','ls']));
ALTER TABLE kabinet_data.app_login_log DROP CONSTRAINT IF EXISTS app_login_log_product_check;
ALTER TABLE kabinet_data.app_login_log ADD CONSTRAINT app_login_log_product_check
    CHECK (product = ANY (ARRAY['kabinet','ls']));
ALTER TABLE kabinet_data.qa_tokens DROP CONSTRAINT IF EXISTS qa_tokens_product_check;
ALTER TABLE kabinet_data.qa_tokens ADD CONSTRAINT qa_tokens_product_check
    CHECK (product = ANY (ARRAY['kabinet','ls']));

-- ── роли в матрице: набор зависит от продукта ────────────────────────────────
-- Прежний CHECK знал только четыре роли Кабинета, и строка `ls.amazon.push ×
-- approver` в него не влезала. Новый не просто расширяет список, а СВЯЗЫВАЕТ
-- префикс действия с набором ролей: иначе в таблице появились бы бессмысленные
-- пары вида «проведение прогноза × утверждающий», и выглядели бы они законно.
ALTER TABLE kabinet_data.app_permissions DROP CONSTRAINT IF EXISTS app_permissions_role_check;
ALTER TABLE kabinet_data.app_permissions ADD CONSTRAINT app_permissions_role_check
    CHECK (CASE WHEN action LIKE 'ls.%'
                THEN role = ANY (ARRAY['viewer','content_manager','approver','admin'])
                ELSE role = ANY (ARRAY['viewer','country_manager','demand_planner','admin'])
           END);

-- ── матрица прав Listing Suite ───────────────────────────────────────────────
-- Видимость страниц открыта всем ролям: включение правил не должно отнимать то,
-- что люди видели вчера. Действия закрыты по смыслу:
--   ls.content.edit  — синтез, фото, контент, матрица (работа контент-менеджера);
--   ls.amazon.push   — отправка в Amazon: меняет живой листинг, поэтому с утверждающего;
--   ls.method.edit   — методика: версия навыка и пороги меняют ВСЁ, что генерится потом;
--   ls.settings.edit — ключи, шаблоны флэтфайлов, расписание сбора: только администратор.
INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT a.action, r.role,
       CASE
           WHEN a.action LIKE 'ls.page.%' THEN true
           WHEN a.action = 'ls.content.edit'
                THEN r.role IN ('content_manager','approver','admin')
           WHEN a.action IN ('ls.amazon.push','ls.method.edit')
                THEN r.role IN ('approver','admin')
           WHEN a.action = 'ls.settings.edit' THEN r.role = 'admin'
           ELSE false
       END,
       'sql:ls_login_2026-10-02'
  FROM (VALUES ('ls.content.edit'), ('ls.amazon.push'), ('ls.method.edit'),
               ('ls.settings.edit'),
               ('ls.page.guide'), ('ls.page.dashboard'), ('ls.page.catalog'),
               ('ls.page.synthesis'), ('ls.page.photo'), ('ls.page.content'),
               ('ls.page.matrix'), ('ls.page.methodology'), ('ls.page.settings')
       ) AS a(action),
       (VALUES ('viewer'), ('content_manager'), ('approver'), ('admin')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;   -- уже выставленные руками галочки не трогаем

-- ── режим входа Listing Suite — свой ─────────────────────────────────────────
-- Общий на два продукта означал бы, что авария в одном гасит кнопки в другом.
-- 2 — раскатка: входа нет, кнопки у всех, как было.
INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('ls_auth_enabled', 2,
        'Вход в Listing Suite: 2 раскатка (входа нет, кнопки у всех), 1 вход обязателен, 0 авария (у всех «Просмотр»)')
ON CONFLICT (key) DO NOTHING;

-- ── администраторы Кабинета — администраторы и в Listing Suite ───────────────
UPDATE kabinet_data.app_users SET ls_role = 'admin'
 WHERE role = 'admin' AND ls_role IS NULL;

COMMIT;
