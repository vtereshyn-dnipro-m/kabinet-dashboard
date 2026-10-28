-- Паритет цен: вариант 3 (T-37, решение владельца 28.10.2026) — цена LM и CF по сроку скидки, пауза между акциями не
-- выброс, сборка после каждой загрузки офферов отдельной джобой `Kabinet - Price Parity` (nb/price_parity.py).
-- Применяет владелец или агент по прямому «применяй», под учёткой владельца. Только добавляет: новая колонка, четыре
-- настройки; ничего не удаляет и ни у кого не отнимает. Порядок: часть A → выкладка ноутбука и модуля → создание джобы
-- → часть B с её job_id → патч Economics Loader (ячейка 6 перестаёт писать паритет).

-- ── Часть A ──
BEGIN;

ALTER TABLE kabinet_data.price_parity ADD COLUMN IF NOT EXISTS promo_pause_channels text;
COMMENT ON COLUMN kabinet_data.price_parity.promo_pause_channels IS
  'Каналы в паузе между акциями (скидки нет, но была недавно): цена показана как есть, выбросом строку из-за них не считаем. Пишет Kabinet - Price Parity.';

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('parity_promo_pause_days', 7, 'Паритет цен: пауза между акциями LM и CF — скидки нет, но была за столько суток (срок кончился или скидка в истории снимков LM)', now()),
 ('parity_shrink_guard_pct', 70, 'Паритет цен: сборка меньше этой доли (%) прежней — пропавшие SKU не удаляются, сбой в пульс (источник ответил не весь)', now()),
 ('parity_outlier_pct', 20, 'Паритет цен: канал — выброс, если дороже минимума страны больше чем на столько % (как в прежней ячейке 6 Economics Loader)', now()),
 ('parity_offer_run_window_min', 60, 'Паритет цен: оффер LM/CF берётся, только если обновлён последней загрузкой (loaded_at не раньше максимума минус столько минут) — пропавшие из API офферы остаются в реплике «активными»', now())
ON CONFLICT (key) DO NOTHING;

COMMIT;

-- ── Часть B. Правило сторожа — ПОСЛЕ создания джобы, с её job_id ──
-- Имя = метка пульса = имя джобы (AGENTS.md, «Одно имя джоба в трёх местах»). Три прогона в сутки — порог 26 ч (один
-- пропущенный день виден, один упавший прогон из трёх — нет: его видно по красному прогону и тексту ошибки).
-- INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
-- VALUES (:parity_job_id, 'Kabinet - Price Parity', 26, 'ежедневно 08:20, 10:20, 16:20 Kyiv', true,
--         'Паритет цен: Amazon (Listing Suite), MM, LM, CF; цена LM/CF по сроку скидки; T-37')
-- ON CONFLICT (job_id) DO NOTHING;
