-- Маркетплейс не может состоять в двух действующих пулах (ТЗ 004).
--
-- До 28.09.2026 это держалось только проверкой на карточке пула в «Справочниках»
-- (`pool_conflict`). Любой другой путь записи — вкладка «Замена после изменения пула»,
-- прямой SQL, будущий загрузчик — второе членство добавлял молча, а дальше оно ломается тихо:
-- и загрузчик покрытия, и `plan_fact.py` идут ОТ прогноза пула К участникам
-- (`JOIN pool_members ON pm.pool_id = f.object_id`) и складывают `own UNION ALL viapool`,
-- то есть участник двух пулов с планами на обоих получает спрос дважды.
--
-- Период членства — ПОЛУОТКРЫТЫЙ [valid_from, valid_to): `valid_to` это первый день, когда
-- маркетплейс в пуле уже НЕ состоит. Иначе снятие (`valid_to = CURRENT_DATE`) и добавление
-- в новый пул тем же днём считались бы пересечением, и «сначала закрыть, потом завести новый
-- пул» не прошло бы до следующего дня.
--
-- Триггер, а не `EXCLUDE USING gist`: `btree_gist` роль Кабинета создать не может
-- («Must have CREATE privilege on current database»), а без расширения equality по int
-- в gist-индекс не влезает. Тот же приём, что у `coverage_norm_no_overlap()`.

CREATE OR REPLACE FUNCTION kabinet_data.pool_member_single_pool() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    _other_pool int;
    _from date;
    _to   date;
    _mp   text;
BEGIN
    -- перевёрнутые даты проверяем ЗДЕСЬ: BEFORE-триггер срабатывает раньше CHECK, и
    -- daterange() упал бы сообщением про диапазон, а не про членство в пуле
    IF NEW.valid_to IS NOT NULL AND NEW.valid_to < NEW.valid_from THEN
        RAISE EXCEPTION 'Дата окончания участия (%) раньше даты начала (%)', NEW.valid_to, NEW.valid_from;
    END IF;

    SELECT p.pool_id, p.valid_from, p.valid_to INTO _other_pool, _from, _to
    FROM kabinet_data.pool_members p
    WHERE p.marketplace_id = NEW.marketplace_id
      AND p.pool_id <> NEW.pool_id
      AND p.id IS DISTINCT FROM NEW.id
      AND daterange(p.valid_from, p.valid_to, '[)')
       && daterange(NEW.valid_from, NEW.valid_to, '[)')
    LIMIT 1;

    IF FOUND THEN
        SELECT code INTO _mp FROM kabinet_data.marketplaces_new WHERE id = NEW.marketplace_id;
        RAISE EXCEPTION
            'Маркетплейс % уже состоит в пуле % с % по %. По ТЗ 004 маркетплейс не может состоять в двух действующих пулах: сначала закройте прежнее участие датой.',
            COALESCE(_mp, NEW.marketplace_id::text), _other_pool, _from, COALESCE(_to::text, 'без срока');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS pool_member_single_pool ON kabinet_data.pool_members;
CREATE TRIGGER pool_member_single_pool
    BEFORE INSERT OR UPDATE OF pool_id, marketplace_id, valid_from, valid_to
    ON kabinet_data.pool_members
    FOR EACH ROW EXECUTE FUNCTION kabinet_data.pool_member_single_pool();
