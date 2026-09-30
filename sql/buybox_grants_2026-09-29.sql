-- Гранты на buybox_status обоим принципалам.
--
-- Таблицу создала роль Кабинета, а джоба идёт под принципалом джоб (b1698364-…) — он получил
-- «permission denied for table buybox_status» на первом же прогоне. Приложению (583bf6d1-…)
-- нужен SELECT: без него страница покажет «не прочиталось» там, где данные есть.
-- Default privileges от rw стоят с 17.09, но на объект, созданный позже них, — проверяем явно.

GRANT SELECT, INSERT ON kabinet_data.buybox_status TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.buybox_status          TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_buybox_current       TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.v_buybox_current       TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

SELECT has_table_privilege('b1698364-6ec5-4240-8cd6-e06dd6e60856',
                           'kabinet_data.buybox_status', 'INSERT') AS джоба_пишет,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb',
                           'kabinet_data.buybox_status', 'SELECT') AS приложение_читает;
