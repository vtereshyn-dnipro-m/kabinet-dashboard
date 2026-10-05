-- Наборы S…_ у Amazon (решение владельца 05.10.2026): подготовка.
-- 1) Копии таблиц экономики ДО правки — чтобы любую цифру можно было сравнить и при нужде вернуть.
CREATE TABLE IF NOT EXISTS kabinet_data.economics_summary_before_kits_20261005 AS TABLE kabinet_data.economics_summary;
CREATE TABLE IF NOT EXISTS kabinet_data.economics_logistics_before_kits_20261005 AS TABLE kabinet_data.economics_logistics;
CREATE TABLE IF NOT EXISTS kabinet_data.ads_spend_before_kits_20261005 AS TABLE kabinet_data.ads_spend;
-- 2) Теневые таблицы той же формы: в них пробный прогон исправленного загрузчика пишет «после»,
--    рабочие таблицы до решения владельца не трогаются.
CREATE TABLE IF NOT EXISTS kabinet_data.economics_summary_kits  (LIKE kabinet_data.economics_summary  INCLUDING ALL);
CREATE TABLE IF NOT EXISTS kabinet_data.economics_logistics_kits (LIKE kabinet_data.economics_logistics INCLUDING ALL);
CREATE TABLE IF NOT EXISTS kabinet_data.ads_spend_kits          (LIKE kabinet_data.ads_spend          INCLUDING ALL);
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.economics_summary_kits, kabinet_data.economics_logistics_kits,
      kabinet_data.ads_spend_kits TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.economics_summary_before_kits_20261005, kabinet_data.economics_logistics_before_kits_20261005,
      kabinet_data.ads_spend_before_kits_20261005 TO "v.tereshyn@dniprom.com";
