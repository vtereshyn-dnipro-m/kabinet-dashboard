-- Снимки витрины по PL, IE и GB не собираем (решение владельца 29.09.2026).
-- ВЫПОЛНЯЕТ ВЛАДЕЛЕЦ: `marketplaces_new` принадлежит v.tereshyn@dniprom.com, и роль Кабинета
-- получает «permission denied for table marketplaces_new» — UPDATE строк ей не выдан
-- (карточка маркетплейса правит их под принципалом ПРИЛОЖЕНИЯ, а не под rw).
--
-- Причина отключения — не дефект сборщика. Проверка через SP-API Product Pricing показала:
-- блока покупки в снимке нет, потому что ПОКУПАТЬ НЕЧЕГО. По IE 137 наших ASIN из 138 не имеют
-- ни одного покупаемого оффера, по GB 28 из 32, по PL 1 из 1. Buy Box по этим рынкам теперь
-- закрыт загрузчиком `Kabinet - Buy Box`, и снимки по ним тратят запросы Scrapingdog впустую
-- (около 700 в месяц по текущему темпу: IE 283, GB 49, PL 5 за две недели).
--
-- Точка управления — наш справочник: `Listing Suite Auto Collector` берёт список рынков
-- запросом с условием `scrapingdog_country IS NOT NULL`, то есть пустое поле и есть выключатель.
--
-- Прежние значения, чтобы было чем вернуть:
--   AMZ-PL  'pl'   AMZ-IE  'ie'   AMZ-GB  'gb'
-- Выключается ТОЛЬКО сбор снимков: маркетплейсы остаются активными, листинги, заказы,
-- экономика и реклама по ним идут как шли.

BEGIN;

UPDATE kabinet_data.marketplaces_new
   SET scrapingdog_country = NULL
 WHERE code IN ('AMZ-PL', 'AMZ-IE', 'AMZ-GB');

-- Проверка глазами до COMMIT: собираться должны ровно ES, DE, IT, FR, BE, NL.
SELECT code, scrapingdog_country, scrapingdog_domain, is_active
  FROM kabinet_data.marketplaces_new
 WHERE platform_short = 'AMZ' ORDER BY code;

COMMIT;
