-- Членство в пуле имеет ПЕРИОДЫ: одна и та же пара «пул + маркетплейс» может повторяться
-- с непересекающимися периодами (ТЗ 004 §11, решение владельца 28.09.2026).
--
-- Сейчас этому мешает `UNIQUE (pool_id, marketplace_id)` — без даты, одна строка на пару
-- навсегда. Из-за неё маркетплейс, у которого закрыли участие, вернуться в ТОТ ЖЕ пул не мог
-- никогда: повторная вставка падала «duplicate key value violates unique constraint»
-- (проверено на живой таблице 28.09.2026). Для роспуска Spain это означало бы, что вернуть
-- туда LM/MM/CF потом нельзя.
--
-- ВАЖЕН ПОРЯДОК, и поэтому всё одной транзакцией. Уникальность сегодня — единственное, что
-- не даёт завести ДВА ПЕРЕСЕКАЮЩИХСЯ членства в ОДНОМ пуле: триггер `pool_member_single_pool`
-- от 28.09 смотрел только на ЧУЖИЕ пулы (`p.pool_id <> NEW.pool_id`). Снять ограничение, не
-- расширив триггер, — значит закрыть одну дыру и открыть другую. Поэтому сначала триггер
-- начинает проверять пересечения в любом пуле, включая свой, и лишь затем снимается UNIQUE.
--
-- После этой правки правило одно и покрывает оба случая: у маркетплейса не может быть двух
-- членств с пересекающимися периодами — ни в разных пулах, ни в одном. Период полуоткрытый
-- [valid_from, valid_to): `valid_to` — первый день БЕЗ пула.

BEGIN;

CREATE OR REPLACE FUNCTION kabinet_data.pool_member_single_pool() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    _other_pool int;
    _from date;
    _to   date;
    _mp   text;
    _same boolean;
BEGIN
    -- перевёрнутые даты проверяем ЗДЕСЬ: BEFORE-триггер срабатывает раньше CHECK, и
    -- daterange() упал бы сообщением про диапазон, а не про членство в пуле
    IF NEW.valid_to IS NOT NULL AND NEW.valid_to < NEW.valid_from THEN
        RAISE EXCEPTION 'Дата окончания участия (%) раньше даты начала (%)', NEW.valid_to, NEW.valid_from;
    END IF;

    -- условия «другой пул» больше нет: пересечение запрещено в любом пуле, в том числе в своём
    SELECT p.pool_id, p.valid_from, p.valid_to INTO _other_pool, _from, _to
    FROM kabinet_data.pool_members p
    WHERE p.marketplace_id = NEW.marketplace_id
      AND p.id IS DISTINCT FROM NEW.id
      AND daterange(p.valid_from, p.valid_to, '[)')
       && daterange(NEW.valid_from, NEW.valid_to, '[)')
    LIMIT 1;

    IF FOUND THEN
        SELECT code INTO _mp FROM kabinet_data.marketplaces_new WHERE id = NEW.marketplace_id;
        _same := (_other_pool = NEW.pool_id);
        RAISE EXCEPTION
            'Маркетплейс % уже состоит в пуле % с % по %. Периоды членства пересекаются: %',
            COALESCE(_mp, NEW.marketplace_id::text), _other_pool, _from, COALESCE(_to::text, 'без срока'),
            CASE WHEN _same
                 THEN 'повторное участие в том же пуле возможно только с даты после закрытия прежнего.'
                 ELSE 'по ТЗ 004 маркетплейс не может состоять в двух действующих пулах — сначала закройте прежнее участие датой.'
            END;
    END IF;
    RETURN NEW;
END;
$$;

-- Снимаем уникальность по паре: периоды теперь держит триггер, и он строже —
-- пара без пересечения допустима, пара с пересечением запрещена в любом пуле.
ALTER TABLE kabinet_data.pool_members
    DROP CONSTRAINT IF EXISTS pool_members_pool_id_marketplace_id_key;

-- Проверка глазами до COMMIT: ограничения остались только нужные (PK и два внешних ключа),
-- триггер на месте и включён.
SELECT conname, pg_get_constraintdef(oid) AS определение
  FROM pg_constraint WHERE conrelid = 'kabinet_data.pool_members'::regclass ORDER BY conname;
SELECT tgname, tgenabled FROM pg_trigger
 WHERE tgrelid = 'kabinet_data.pool_members'::regclass AND NOT tgisinternal;

COMMIT;
