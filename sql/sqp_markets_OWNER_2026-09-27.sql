-- Очередь SQP: снимаем с учёта отчёты по Ирландии и Бельгии.
-- ВЫПОЛНЯЕТ ВЛАДЕЛЕЦ: база listing-suite у роли Кабинета только на чтение
-- (permission denied for table sqp_report_queue). Правка косметическая — загрузчик
-- эти рынки больше не запрашивает, потому что очередь фильтруется по MARKETPLACES;
-- строки нужны лишь для того, чтобы следующий читатель видел диагноз, а не «failed».
--
-- SQP этому аккаунту по ирландскому и бельгийскому магазинам недоступен: Amazon отвечает FATAL
-- «Invalid marketplaceId» с внутренним номером магазина (753556201 и 679831071), хотя коды в
-- загрузчике верные. За восемь недель по IE упали 115 отчётов из 115, по BE 106 из 109, данных
-- ноль за всю историю. Рынки убраны из MARKETPLACES загрузчика 27.09.2026.
--
-- Строки очереди не удаляем: это история попыток, по ней и виден диагноз. Помечаем причину в
-- error_detail, чтобы следующий читатель не начинал разбор с нуля, и в статус unsupported —
-- тогда загрузчик не подберёт их заново, а done/empty/failed сохранят прежний смысл.
UPDATE listing_data.sqp_report_queue
   SET status = 'unsupported',
       error_detail = 'SQP недоступен для этого магазина: Amazon отвечает FATAL Invalid marketplaceId. Рынок снят с загрузки 27.09.2026. ' || coalesce(left(error_detail, 200), '')
 WHERE marketplace IN ('be', 'ie') AND status IN ('failed', 'submitted');

SELECT marketplace, status, count(*) FROM listing_data.sqp_report_queue
 WHERE marketplace IN ('be', 'ie') GROUP BY 1, 2 ORDER BY 1, 3 DESC;
