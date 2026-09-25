-- ТЗ 001 §5: фактический срок поставки по маршруту и уведомление при отклонении от планового LT.
--
-- Плановый LT — это `supply_chains.median_days`: его правят в карточке склада-получателя, и именно он
-- идёт в расчёты обеспечения и автозаказа. Факт хранится отдельно и НИКОГДА не переписывает план —
-- «LT не изменяется автоматически» сказано в ТЗ прямым текстом. В одном поле их держать нельзя было
-- ещё и технически: `supply_chains` принадлежит владельцу базы, роль Кабинета колонок туда не добавит.
CREATE TABLE IF NOT EXISTS kabinet_data.supply_lead_time_facts (
    route_id            int  PRIMARY KEY,   -- supply_chains.id; FK нет — таблица маршрутов чужая, REFERENCES на неё роли не выдан
    from_warehouse_id   int  NOT NULL,
    to_warehouse_id     int  NOT NULL,
    actual_days         numeric(5,1),       -- медиана календарных дней «отгрузка → приёмка» по закрытым ТТН
    shipments           int  NOT NULL DEFAULT 0,   -- число ТТН, а не строк: одна поставка на 229 позиций — это одна поставка
    lines               int  NOT NULL DEFAULT 0,
    window_days         int  NOT NULL,
    first_delivery      date,
    last_delivery       date,
    promise_days        numeric(5,1),       -- медиана обещания перевозчика в ТТН: не факт, но показывает, чем план подкреплён
    promise_shipments   int  NOT NULL DEFAULT 0,
    source              text NOT NULL DEFAULT 'erp:ttn',
    calculated_at       timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.supply_lead_time_facts IS
    'ТЗ 001 §5: фактический срок поставки по маршруту из закрытых ТТН ERP. Плановый LT живёт в supply_chains.median_days и автоматически не меняется.';

-- Пороги — в БД, а не в коде: их пересматривают без правки загрузчика.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('lead_time_deviation_pct', 15, 'ТЗ 001 §5: отклонение факта срока поставки от планового LT, с которого Кабинет заводит информационный алерт, %'),
  ('lead_time_min_shipments', 5, 'Сколько закрытых ТТН должно быть в окне, чтобы факт считался основанием для пересмотра LT'),
  ('lead_time_window_days', 180, 'Окно, за которое считается фактический срок поставки, календарных дней')
ON CONFLICT (key) DO UPDATE SET note = EXCLUDED.note;

GRANT SELECT ON kabinet_data.supply_lead_time_facts TO claude_code_ro,
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT INSERT, UPDATE, DELETE ON kabinet_data.supply_lead_time_facts TO
      "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Тип алерта: информационный, канал общий (Кабинет → Telegram → ClickUp), отдельного не заводим.
INSERT INTO kabinet_data.incident_types (incident_type, mode, clickup_list_id, clickup_list_name, risk, due_days,
                                         enabled_since, title, description, watch_close, assignee_group_id, assignee_group_name, updated_by)
SELECT 'lead_time_deviation', 'task', t.clickup_list_id, t.clickup_list_name, 'Low', 7, CURRENT_DATE,
       'Срок поставки расходится с планом',
       'ТЗ 001 §5: фактический срок поставки по маршруту отличается от планового LT больше порога. '
       'Уведомление информационное — LT Кабинет не меняет, его пересматривает человек в карточке склада-получателя.',
       true, t.assignee_group_id, t.assignee_group_name, 'kabinet'
FROM kabinet_data.incident_types t WHERE t.incident_type = 'forecast_pace'
ON CONFLICT (incident_type) DO NOTHING;
