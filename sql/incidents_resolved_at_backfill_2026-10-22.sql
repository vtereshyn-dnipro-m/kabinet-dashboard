-- Старые тревоги со статусом resolved без даты закрытия (22.10.2026, решение владельца: «закрыть старые тревоги без
-- resolved_at»). Применяет ВЛАДЕЛЕЦ после мержа.
--
-- Что это: 274 строки kabinet_data.incidents — low_stock 250 и out_of_stock 24, заведены 09.07–12.09.2026, status =
-- 'resolved', а resolved_at и resolved_by пустые. Так закрывал прежний Stock Loader (до 17.09.2026: с того дня он
-- пишет resolved_at = NOW() и причину). По одному «resolved_at IS NULL» они выглядят открытыми — 20.10 на этом
-- споткнулась ручная проверка тревог; сводка и страницы фильтруют по обоим полям и их не показывают.
--
-- Настоящего времени закрытия нет нигде, поэтому НЕ выдумываем его: resolved_at — момент применения, а resolved_by
-- прямо говорит, что дата проставлена задним числом, — по нему такие строки отсекаются в расчётах «как быстро
-- закрыли». Удаления нет, статус не меняется.
BEGIN;
UPDATE kabinet_data.incidents
   SET resolved_at = now(),
       resolved_by = 'sql 22.10.2026: закрыта до 17.09.2026, дата закрытия не записана — проставлена задним числом'
 WHERE status = 'resolved'
   AND resolved_at IS NULL
   AND resolved_by IS NULL
   AND incident_type IN ('low_stock', 'out_of_stock')
   AND created_at < '2026-09-17';
-- ожидаемо: UPDATE 274 (проверено чтением 21.10.2026: low_stock 250, out_of_stock 24)
COMMIT;
