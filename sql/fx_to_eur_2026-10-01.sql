-- Пересчёт в евро одним правилом (найдено 01.10.2026).
--
-- Что обнаружилось: `economics_summary.currency_code` в коде Кабинета НЕ ЧИТАЛСЯ НИГДЕ.
-- Суммы по GB, SE и PL лежат в своей валюте, и всюду, где Кабинет складывал выручку по
-- рынкам, фунты, кроны и злотые прибавлялись к евро один к одному.
--
-- Ошибка разнонаправленная, и это важнее её размера: фунт дороже евро, поэтому GB
-- ЗАНИЖАЛСЯ, а злотый и крона дешевле — PL и SE ЗАВЫШАЛИСЬ. Итог по трём рынкам за всю
-- историю: 1 996 € вместо 1 266 €, то есть завышение на 730 €. На общем фоне в 250 тыс.
-- это немного, но «немного» тут — следствие того, что на этих рынках почти нет продаж;
-- правило неверно независимо от суммы.
--
-- Функция, а не выражение по месту: пересчёт нужен на четырёх страницах и в сверке, и
-- второе написание разошлось бы молча — ровно как уже было с границей периода у пулов.

CREATE OR REPLACE FUNCTION kabinet_data.to_eur(
    amount double precision, currency text, on_date date)
RETURNS double precision
LANGUAGE sql STABLE
AS $$
    SELECT CASE
        WHEN amount IS NULL THEN NULL
        -- пустая валюта у строки в евро — обычное дело: заполняют не везде
        WHEN currency IS NULL OR currency = '' OR upper(currency) = 'EUR' THEN amount
        ELSE (SELECT amount / f.units_per_eur
                FROM kabinet_data.raw_ecb_fx_rates f
               WHERE f.currency = upper(to_eur.currency) AND f.date = to_eur.on_date)
    END
$$;

COMMENT ON FUNCTION kabinet_data.to_eur(double precision, text, date) IS
    'Сумма в евро по курсу ЕЦБ на дату. EUR отдаётся как есть; нет курса на дату — NULL, а не исходная сумма.';

-- Нет курса на дату — NULL, а НЕ исходная сумма. Вернуть сумму как есть значило бы
-- тихо вернуть ту самую ошибку, ради которой всё и делается: на экране снова
-- появились бы злотые, сложенные с евро, и заметить это было бы неоткуда.

GRANT SELECT ON kabinet_data.raw_ecb_fx_rates
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Проверка: три валюты пересчитываются, евро проходит насквозь, выдуманная — NULL.
SELECT 'GBP 100 на 30.09' AS case_, round(kabinet_data.to_eur(100, 'GBP', DATE '2026-09-30')::numeric, 2) AS eur
UNION ALL SELECT 'SEK 100 на 30.09', round(kabinet_data.to_eur(100, 'SEK', DATE '2026-09-30')::numeric, 2)
UNION ALL SELECT 'PLN 100 на 30.09', round(kabinet_data.to_eur(100, 'PLN', DATE '2026-09-30')::numeric, 2)
UNION ALL SELECT 'EUR 100 — как есть', round(kabinet_data.to_eur(100, 'EUR', DATE '2026-09-30')::numeric, 2)
UNION ALL SELECT 'пустая валюта — как есть', round(kabinet_data.to_eur(100, NULL, DATE '2026-09-30')::numeric, 2)
UNION ALL SELECT 'XXX — курса нет, NULL', round(kabinet_data.to_eur(100, 'XXX', DATE '2026-09-30')::numeric, 2)
UNION ALL SELECT 'GBP до начала истории — NULL', round(kabinet_data.to_eur(100, 'GBP', DATE '2024-01-01')::numeric, 2);
