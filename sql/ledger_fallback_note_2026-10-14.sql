-- Примечание правила здоровья запасной джобы вечерней цепочки называло тревогу кодом (ledger_evening), и сторож
-- выводил его в тексте job_health — на «Площадках» это код вместо названия (ловит scratchpad/smoke_full.py).
UPDATE kabinet_data.job_health_rules
   SET note = 'Страховка вечерней цепочки: нет вечерней записи Ledger Summary — запасной Stock Loader и Coverage, '
              'тревога «Вечерние остатки FBA не обновились»'
 WHERE job_name = 'Kabinet - Запасной прогон после Ledger Summary';
