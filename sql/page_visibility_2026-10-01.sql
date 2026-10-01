-- Видимость страниц в матрице прав (задание владельца 01.10.2026).
--
-- По строке на каждую из десяти страниц. ВСЁ ОТКРЫТО по умолчанию: включение этих
-- правил не должно ничего отнять у людей, которые вчера это видели. Закрывают потом,
-- галочками, осознанно.
--
-- «Доступа» среди строк нет намеренно: его видимость — это уже существующее право
-- «Доступ: управление» (`admin`), и оно защищено от самоблокировки триггером. Завести
-- вторую галочку про то же самое значило бы завести два правила, которые когда-нибудь
-- разойдутся — и разойдутся молча.

BEGIN;

INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT 'page.' || p.key, r.role, true, 'seed:pages-2026-10-01'
  FROM (VALUES ('home'), ('stock'), ('incidents'), ('reorder'), ('money'),
               ('ads'), ('forecast'), ('reviews'), ('cm'), ('dictionaries')) AS p(key)
  CROSS JOIN (VALUES ('viewer'), ('country_manager'), ('demand_planner'), ('admin')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;

COMMIT;

SELECT action,
       bool_or(allowed) FILTER (WHERE role = 'viewer')          AS prosmotr,
       bool_or(allowed) FILTER (WHERE role = 'country_manager') AS stranovoy,
       bool_or(allowed) FILTER (WHERE role = 'demand_planner')  AS planner,
       bool_or(allowed) FILTER (WHERE role = 'admin')           AS admin
  FROM kabinet_data.app_permissions
 WHERE action LIKE 'page.%'
 GROUP BY action ORDER BY action;
