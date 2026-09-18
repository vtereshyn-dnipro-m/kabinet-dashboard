-- 19.09.2026: роли ClickUp созданы через API (группы пустые, наполнит Владислав), привязаны к типам,
-- включены группы «Площадки» и «Снабжение». Задачи уйдут на роль — без правок в Кабинете, когда в ней появятся люди.
UPDATE kabinet_data.incident_types SET assignee_group_id = '5e544aa4-050d-46cf-bc28-f952cdb839aa', assignee_group_name = 'Kabinet · Данные', updated_by = 'kabinet', updated_at = now()
 WHERE incident_type IN ('stale_data', 'job_health', 'listing_pair_unreachable');
UPDATE kabinet_data.incident_types SET assignee_group_id = 'e22d4135-cd54-4077-a763-19c1c4767f50', assignee_group_name = 'Kabinet · Площадки', updated_by = 'kabinet', updated_at = now()
 WHERE incident_type IN ('listing_pair_blocked', 'listing_pair_missing', 'listing_suppressed', 'manomano_health_degraded', 'carrefour_health_degraded',
                         'lm_order_not_accepted', 'leroy_merlin_order_not_accepted', 'carrefour_order_not_accepted');
UPDATE kabinet_data.incident_types SET assignee_group_id = '3339e28d-d15f-42ec-8585-ec3831eac0ce', assignee_group_name = 'Kabinet · Снабжение', updated_by = 'kabinet', updated_at = now()
 WHERE incident_type IN ('out_of_stock', 'low_stock', 'forecast_pace', 'missing_forecast', 'partial_forecast');

-- «Площадки»: только новые с даты включения (висящие 53 blocked / 20 suppressed — старые, не переносим).
UPDATE kabinet_data.incident_types SET clickup_list_id = 901222107924, clickup_list_name = '5.6 Listing Publication', enabled_since = '2026-09-19'
 WHERE incident_type IN ('listing_pair_blocked', 'listing_pair_missing', 'listing_suppressed');
UPDATE kabinet_data.incident_types SET clickup_list_id = 901222107986, clickup_list_name = '5.9 Marketplace Performance', enabled_since = '2026-09-19'
 WHERE incident_type IN ('manomano_health_degraded', 'carrefour_health_degraded');
UPDATE kabinet_data.incident_types SET clickup_list_id = 901222107945, clickup_list_name = '5.7 Marketplace Logistics', enabled_since = '2026-09-19'
 WHERE incident_type IN ('lm_order_not_accepted', 'leroy_merlin_order_not_accepted', 'carrefour_order_not_accepted');
-- «Снабжение»: с 17.09 — даты, когда автозакрытие вычистило журнал; всё открытое после неё проверено данными.
UPDATE kabinet_data.incident_types SET clickup_list_id = 901222107434, clickup_list_name = '3.3 Replenishment', enabled_since = '2026-09-17'
 WHERE incident_type IN ('out_of_stock', 'low_stock', 'forecast_pace');
UPDATE kabinet_data.incident_types SET clickup_list_id = 901222107410, clickup_list_name = '3.1 Demand Planning', enabled_since = '2026-09-17'
 WHERE incident_type IN ('missing_forecast', 'partial_forecast');
SELECT incident_type, assignee_group_name, clickup_list_name, mode, enabled_since FROM kabinet_data.incident_types WHERE clickup_list_id IS NOT NULL ORDER BY assignee_group_name, incident_type;
