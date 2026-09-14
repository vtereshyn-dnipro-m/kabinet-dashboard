-- Целевой статус SKU × рынок — намерение рядом с фактом. Lakebase, kabinet_data.
--
-- Факт — sku_lifecycle: active / not_launched / phasing_out / seasonal_pause /
-- discontinued, считается загрузчиком из продаж и трогать его руками нельзя.
-- Намерение — «запускаем», «выводим», «сезонный, после августа не заказывать» —
-- в данных не существует, его заполняет человек. Отдельная таблица, а не
-- колонка в sku_lifecycle: загрузчик переписывает ту таблицу целиком, и
-- ручное поле в ней жило бы до первого прогона.

CREATE TABLE IF NOT EXISTS kabinet_data.sku_target_status (
    sku           text NOT NULL,
    marketplace   text NOT NULL,
    target_status text NOT NULL CHECK (target_status IN ('keep', 'launch', 'phase_out', 'seasonal', 'stop')),
    note          text,
    updated_by    text,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sku, marketplace)
);
COMMENT ON TABLE kabinet_data.sku_target_status IS
    'Целевой статус SKU на рынке, заполняется на экране «Справочники → Ассортимент». '
    'keep — держим; launch — запускаем; phase_out — выводим; seasonal — сезонный; stop — не продаём. '
    'Факт живёт в sku_lifecycle и сюда не копируется.';

GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sku_target_status TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.sku_target_status TO claude_code_ro;
