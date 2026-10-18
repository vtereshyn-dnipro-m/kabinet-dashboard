# Удаление в справочниках

> Перенесено из AGENTS.md дословно 19.10.2026 (сжатие файла правил). Правила работы и указатель — в AGENTS.md; дополнять этот файл, а не AGENTS.md.

## Удаление в справочниках

Физического удаления одним действием в «Справочниках» нет намеренно: 18.09.2026 пулы
Spain и France с их связями исчезли одним нажатием кнопки «Удалить пул» (кто — не
установлено, восстановлены по `sql/pools_restore_2026-09-18.sql`). Правила:

- удаление — только по одной записи и через `confirm_delete()`: первое нажатие
  показывает вопрос «Удалить пул «Spain» и 4 его связей?», второе — удаляет;
- объект со ссылками не удаляется, а закрывается датой или деактивируется: у пула
  проверяются `pool_members` (вся история), `forecast_documents`/`forecast_register`,
  `forecast_alert_rules`, `coverage_norms` (`pool_references()`); участники пула при
  снятии получают `valid_to = CURRENT_DATE`, а не `DELETE` (ТЗ 004 §11);
- массовых «удалить отмеченные» с чекбоксом нет; матрица (ТЗ 007) исключает датой,
  SKU/PeID/группы — флагом активности.

На уровне базы с 18.09.2026 стоят внешние ключи (`sql/foreign_keys_2026-09-18*.sql`): наши таблицы
→ `marketplaces_new` / `warehouses` / `sku_master` / `product_entities` / `variation_groups`, у владельца —
`warehouses.canonical_id` → `warehouses`, `coverage_norms.sku` → `sku_master`; роли Кабинета выдан
`REFERENCES` на `marketplaces_new`, `warehouses`, `pools`. `pool_members → pools` был и до этого — пулы
удалились, потому что кнопка сначала сносила участников: ключ не защищает от кода, который его обходит.
Без ключа намеренно: `sku_lifecycle.sku`, `reorder_recommendations.sku` (шире периметра справочника),
`forecast_register.sku` (82 SKU листа планов нигде не выставлены), полиморфные `(object_type, object_id)`.
