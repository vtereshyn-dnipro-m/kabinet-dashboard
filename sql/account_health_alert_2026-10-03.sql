-- Account Health в стороже (Kabinet - Watchdog, блок «ACCOUNT HEALTH»), 03.10.2026.
-- Порогов в reorder_params нет намеренно: статусы метрикам и аккаунту ставит сам Amazon
-- (GOOD / FAIR / BAD, NORMAL / AT_RISK), сторож переводит их в важность. ClickUp не включён:
-- clickup_list_id пуст — тип живёт в Кабинете и Telegram; включается одним полем на «Алертах».
INSERT INTO kabinet_data.incident_types (incident_type, mode, title, description, watch_close, due_days)
VALUES ('account_health', 'task', 'Здоровье аккаунта Amazon',
        'Amazon пометил метрику аккаунта или сам аккаунт на рынке как не «хорошо»: статус аккаунта, Account Health Rating, ODR, опоздания, отмены, доставка, трекинг, счета, нарушения политик, запросы документов. Одна тревога на рынок, важность по худшей проблеме; закрывается сама, когда всё в норме.',
        true, 1)
ON CONFLICT (incident_type) DO UPDATE SET title = EXCLUDED.title, description = EXCLUDED.description;
