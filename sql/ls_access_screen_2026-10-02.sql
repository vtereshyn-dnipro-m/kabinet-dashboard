-- Экран «Доступ» в Listing Suite: своё право и та же защита от самоблокировки.
-- 02.10.2026. Выполняется от роли Кабинета (она владеет app_permissions).
BEGIN;

-- ── право на админку второго продукта ────────────────────────────────────────
-- Отдельное от кабинетного `admin`: администратор Кабинета и администратор Listing
-- Suite — разные люди по смыслу, и одно право на оба продукта означало бы, что роль в
-- одном молча открывает чужую админку.
INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT 'ls.admin', r.role, r.role = 'admin', 'sql:ls_access_screen_2026-10-02'
  FROM (VALUES ('viewer'), ('content_manager'), ('approver'), ('admin')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;

-- ── самоблокировка запрещена у ОБОИХ продуктов ───────────────────────────────
-- Прежняя функция держала одну пару — «admin × admin». Снять «ls.admin × admin» она
-- позволяла, а это ровно та же дыра: в «Доступ» Listing Suite не вошёл бы никто, и
-- вернуть право можно было бы только запросом в базу, потому что экран, которым его
-- возвращают, закрыт этим же правом.
--
-- Пары перечислены списком, а не выведены из префикса: «действие, которым открывают
-- доступ» — это решение, а не свойство имени, и новое такое право должно попадать сюда
-- осознанно.
CREATE OR REPLACE FUNCTION kabinet_data.app_permissions_keep_admin()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    запертые text[][] := ARRAY[ARRAY['admin','admin'], ARRAY['ls.admin','admin']];
    пара text[];
BEGIN
    IF TG_OP = 'DELETE' THEN
        FOREACH пара SLICE 1 IN ARRAY запертые LOOP
            IF OLD.action = пара[1] AND OLD.role = пара[2] THEN
                RAISE EXCEPTION 'Право «% × %» снять нельзя: иначе в «Доступ» не войдёт никто, и вернуть его можно будет только запросом в базу', пара[2], пара[1];
            END IF;
        END LOOP;
        RETURN OLD;
    END IF;
    IF NOT NEW.allowed THEN
        FOREACH пара SLICE 1 IN ARRAY запертые LOOP
            IF NEW.action = пара[1] AND NEW.role = пара[2] THEN
                RAISE EXCEPTION 'Право «% × %» снять нельзя: иначе в «Доступ» не войдёт никто, и вернуть его можно будет только запросом в базу', пара[2], пара[1];
            END IF;
        END LOOP;
    END IF;
    RETURN NEW;
END $function$;

COMMIT;
