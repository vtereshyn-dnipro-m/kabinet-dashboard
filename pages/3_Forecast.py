# pages/3_Forecast.py — документ «Прогноз продаж marketplace / пула» по ТЗ 010 v0.2
"""Экран поверх реестра прогноза (`forecast_documents`, `forecast_register`, `forecast_change_log`).

Документ в Кабинете — источник истины (Ярослав, 20.09.2026); файлы и лист Google — только способ
загрузить: загрузчик листа с 20.09 создаёт черновики, утверждает и проводит человек здесь.

Что реализовано из ТЗ: список документов (§10), карточка с шапкой (§5) и строками SKU × месяц (§6),
состояния значений «Не утверждено / Утверждено / Заменено» (§9), утверждение и снятие утверждения
по выбранным SKU и месяцам (сценарии 6, 19), проведение с проверками заполнения, утверждения,
прошедших месяцев и полноты (§4, §9, §12, сценарии 8, 17), замена действующих записей с двусторонними
ссылками (сценарий 20), добавление SKU с проверкой допуска по матрице (§3, §7, сценарий 4), заполнение
по матрице (сценарий 16), пустоты → нули (сценарий 5), удаление строк черновика (сценарий 18), журнал
изменений (§10, сценарий 13), загрузка значений в черновик из файла Excel/CSV и из Google Таблицы
(§11, сценарий 15). Не реализовано: роли COUNTRY_MANAGER / DEMAND_PLANNER (у приложения нет входа
по пользователям), пересоздание после изменения пула (сценарии 12, 21).

Зависимая потребность (ТЗ 011) считается в базе и показывается отдельным блоком карточки.
"""
import base64
import calendar
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from db.connection import get_connection, get_workspace_client
from i18n import init_lang, get_lang

init_lang()

TR = {
    "ru": {
        "title": "Прогноз продаж", "caption": "Документы прогноза: черновик → утверждение значений → проведение. "
                 "Действующий прогноз — только из проведённых документов; проведённый документ не правится, изменение — новым документом.",
        "tab_docs": "Документы", "tab_log": "Журнал изменений", "tab_new": "Новый документ",
        "f_object": "Объект", "f_status": "Статус", "f_month": "Месяц в периоде", "all": "все",
        "st_draft": "Черновик", "st_posted": "Проведён", "full": "весь ассортимент матрицы", "partial": "часть ассортимента",
        "col_number": "Номер", "col_date": "Дата", "col_object": "Объект", "col_period": "Период", "col_compl": "Охват матрицы",
        "col_status": "Статус", "col_rows": "SKU", "col_filled": "Заполнено", "col_approved": "Утверждено", "col_source": "Источник",
        "col_created_by": "Создал", "col_posted_at": "Проведён", "col_comment": "Комментарий",
        "no_docs": "Документов по фильтру нет.", "open_doc": "Открыть документ",
        "new_object_type": "Тип объекта", "mp": "Marketplace", "pool": "Пул", "new_first": "Первый месяц", "new_last": "Последний месяц",
        "new_compl": "Охват матрицы", "new_comment": "Комментарий", "btn_create": "Создать черновик",
        "ph_pick_sku": "выберите SKU", "lbl_liquidation": "распродажа", "lbl_no_admission": "нет допуска",
        "btn_matrix_help": "Сценарий 16: добавляются только продажные SKU матрицы, которых ещё нет; существующие строки и значения не трогаются",
        "lost_admission": "SKU без допуска на объекте (строки не удаляются автоматически, сценарий 16): ",
        "src_sheet": "загрузка из листа", "btn_post_confirm": "Да, провести",
        "post_confirm": "Проведение необратимо: {n} станет действующим прогнозом по {k} значениям, проведённый документ не правится — изменение только новым документом. Нажмите «Да, провести».",
        "err_period": "Последний месяц не раньше первого и не дальше 13 месяцев (§4).",
        "err_past": "Первый месяц — текущий или будущий: прошедшие месяцы заблокированы (§4).",
        "created": "Создан черновик {n}.",
        "hdr_object": "Объект", "hdr_period": "Период", "hdr_snapshot": "Состав пула на {d}", "hdr_created": "Создан {by} {at}",
        "hdr_posted": "Проведён {by} {at}", "hdr_source": "Источник",
        "m_rows": "SKU в документе", "m_cells": "Заполнено ячеек", "m_approved": "Утверждено ячеек", "m_matrix": "SKU матрицы в документе",
        "m_matrix_help": "Для полного прогноза: уникальные продажные SKU действующей матрицы объекта, включённые в документ / все продажные SKU матрицы (§12).",
        "m_sum": "Итого за период, шт", "m_rev": "Прогноз выручки, €",
        "grid_help": "Пусто — прогноз не заполнен, 0 — продаж не планируем. Прошедшие месяцы и проведённый документ не редактируются; "
                     "утверждённые ячейки меняются только после снятия утверждения.",
        "col_sku": "SKU", "col_type": "Тип", "col_state": "Состояние", "col_total": "Итого", "col_name": "Название",
        "type_base": "базовый", "type_composite": "составной", "type_unknown": "—",
        "state_all_appr": "утверждено", "state_none": "не утверждено", "state_part": "утв. {a}/{n}", "state_empty": "пусто: {e}",
        "btn_save": "Сохранить значения", "saved": "Сохранено изменений: {n}.", "nothing_changed": "Изменений нет.",
        "rej_approved": "{sku} · {m}: значение утверждено — сначала снимите утверждение.",
        "rej_past": "{sku} · {m}: прошедший месяц заблокирован.",
        "rej_value": "{sku} · {m}: допускаются целые числа не меньше нуля.",
        "rejected": "Не записано {n} значений:", "grid_posted": "Документ проведён — значения только для чтения.",
        "sec_add": "Добавить SKU", "add_pick": "SKU из справочника (допущенных на объекте: {a}, всего: {n})", "btn_add": "Добавить выбранные",
        "btn_matrix": "Заполнить по матрице", "matrix_added": "Добавлено по матрице: {n} SKU.", "matrix_none": "Все продажные SKU матрицы уже в документе.",
        "add_done": "Добавлено: {n}. Отклонено: {r}.", "add_no_admission": "{sku}: нет допуска к самостоятельной продаже на объекте (§3).",
        "add_liquidation": "{sku}: допуск закрыт — добавлен как распродажа по прежнему допуску (§7).", "add_dup": "{sku}: уже в документе.",
        "add_unknown": "{sku}: нет в справочнике SKU.",
        "ro_all_past": "Документ только для просмотра: все его месяцы уже прошли. Непроведённый черновик не удаляется и в расчётах не участвует, но изменить, утвердить или провести его нельзя — прошедшие месяцы прогнозом не переписываются.",
        "rej_restricted": "{sku} · {m}: продажа SKU сейчас запрещена ({why}) — значение сохранено в черновике, утверждение не выполнено.",
        "why_inactive": "SKU деактивирован в справочнике", "why_restricted": "ограничение применения для этой площадки или страны",
        "why_unknown": "нет в справочнике SKU",
        "post_restricted": "продажа запрещена у SKU: {skus} — снимите их из документа или устраните запрет;",
        # ── загрузка из файла и из Google Таблицы ──
        "sec_upload": "Загрузка из файла", "up_help": "Строка источника — один SKU, значения прогноза — колонками по месяцам. "
                 "Объект берётся из документа, в файле его указывать не нужно. Загрузка кладёт значения в черновик и ничего не утверждает: "
                 "пустая ячейка ничего не меняет, 0 означает «продаж не планируем». Ошибка хотя бы в одной ячейке останавливает всю загрузку.",
        "up_src": "Источник", "up_src_file": "Файл Excel или CSV", "up_src_gs": "Google Таблица",
        "up_file": "Файл", "up_sheet": "Лист", "up_header": "Строка заголовков", "up_gs_url": "Ссылка на Google Таблицу",
        "up_sku_col": "Колонка с артикулом SKU", "up_map": "Какой месяц документа берёт каждая колонка источника",
        "up_skip": "пропустить", "up_col_nameless": "колонка", "up_col_month": "Месяц", "up_col_old": "Было", "up_col_new": "Станет",
        "up_map_dup": "Один месяц документа выбран у двух колонок — оставьте одну.",
        "up_no_months": "Сопоставьте хотя бы одну колонку с месяцем документа.",
        "up_preview": "К загрузке: SKU {s}, значений {v}; новых SKU {a}, замен заполненного {r}.",
        "up_errors": "Загрузка заблокирована, ошибок {n}. Документ не изменён — исправьте источник и проверьте снова.",
        "up_err_unknown": "{sku} — нет в справочнике SKU, загрузка новые артикулы не создаёт",
        "up_err_admission": "{sku} — нет допуска на объекте прогноза, добавить его загрузкой нельзя",
        "up_err_value": "{sku} · {m}: «{v}» — нужно целое число не меньше нуля",
        "up_err_dup": "{sku} · {m} — сочетание артикула и месяца в источнике повторяется",
        "up_err_approved": "{sku} · {m} — значение утверждено; сначала снимите утверждение",
        "up_err_past": "{sku} · {m} — прошедший месяц не меняется",
        "up_replace": "Заполненных значений будет заменено: {n}. Проверьте столбцы «Было» и «Станет» и нажмите «Да, заменить и загрузить».",
        "up_btn_apply": "Загрузить", "up_btn_apply_confirm": "Да, заменить и загрузить",
        "up_done": "Загружено значений: {n}, добавлено SKU: {k}.",
        "up_nothing": "Загружать нечего: значения источника совпадают с документом.",
        "up_read_fail": "Источник не прочитан: {e}", "up_gs_fail": "Google Таблица недоступна: {e}",
        "liq_note": "распродажа по прежнему допуску", "src_file": "загрузка из файла", "src_gsheet": "загрузка из Google Таблицы",
        # ── изменение состава пула: пересоздание и общая замена ──
        "tab_repl": "Замена после изменения пула",
        "col_recreate": "Пересоздание", "recreate_needed": "требуется",
        "recreate_banner": "Состав пула изменился: {what}. Прежний прогноз продолжает действовать, "
                 "но поодиночке этот документ больше не проводится — замена выполняется целиком на вкладке «{tab}».",
        "repl_help": "Изменение состава пула само по себе прогнозы не переключает: до общей замены отчёты и обеспечение "
                 "живут на прежних прогнозах и сохранённом в них составе. Вышедший маркетплейс продолжает считаться в прогнозе пула, "
                 "добавленный прежним прогнозом пула не покрывается. Переключение происходит одним действием: либо все новые документы "
                 "проводятся сразу, либо не проводится ни один.",
        "repl_none": "Составы пулов совпадают с действующими прогнозами — пересоздавать нечего.",
        "repl_hdr": "Пул «{pool}»", "repl_what": "{what}. Документ {n}: состав в прогнозе — {was}; состав пула сейчас — {now}.",
        "repl_scope": "Заменяются {rows} действующих записей с {m}; прошедшие месяцы не меняются.",
        "repl_pick_pool": "Новый прогноз пула «{pool}»", "repl_pick_mp": "Новый прогноз {mp}",
        "repl_none_pick": "— не выбран —",
        "repl_role_removed": "вышел из пула", "repl_role_added": "добавлен в пул",
        "repl_mp_active": "работает", "repl_mp_inactive": "деактивирован",
        "repl_reason_mp": "Причина прекращения прогноза {mp}", "repl_reason_ph": "почему прогноз прекращает действие",
        "repl_added_hint": "покрывается новым прогнозом пула; его собственный прогноз этой же операцией перестанет действовать",
        "repl_disbanded_hint": "В пуле не осталось участников: новый прогноз пула не нужен — нужны прогнозы продолжающих работу маркетплейсов или причины прекращения.",
        "repl_reason": "Причина изменения состава (попадёт в историю)",
        "repl_m_docs": "Документов", "repl_m_sup": "Записей к замене", "repl_m_term": "Записей к прекращению",
        "repl_blocked": "Замена не выполняется, причин {n}:",
        "repl_ready": "Проверки пройдены: можно выполнять замену.",
        "repl_need_op_reason": "Укажите причину изменения состава.",
        "repl_confirm": "Замена необратима: документов {d}, записей к замене {s}, к прекращению {t}. Нажмите «Да, заменить».",
        "repl_btn": "Заменить прогнозы после изменения пула", "repl_btn_confirm": "Да, заменить",
        "repl_done": "Замена {op} выполнена: проведено документов {d}, заменено записей {s}, прекращено {t}.",
        "repl_dd_err": "Зависимая потребность пересчитана не полностью: {e}",
        "repl_hist": "Выполненные замены", "repl_hist_empty": "Замен пока не было.",
        "repl_c_at": "Когда", "repl_c_what": "Что изменилось", "repl_c_reason": "Причина",
        "repl_no_doc": "Документ {d} не найден.", "repl_not_draft": "{n}: документ уже не черновик.",
        "repl_no_comment": "{n}: в комментарии документа нужна причина пересоздания.",
        "repl_stale_snapshot": "{n}: документ создан с прежним составом ({was}), а в пуле сейчас {now} — создайте новый документ.",
        "repl_doc_empty": "{n}: в документе нет строк.",
        "repl_need_doc": "{mp} продолжает работу — нужен новый прогноз: свой или в составе актуального пула.",
        "repl_need_reason": "{mp} деактивирован — вместо нового прогноза укажите причину прекращения.",
        "repl_double": "{mp} попадёт разом в свой прогноз и в прогноз пула {n} — оставьте один источник.",
        "repl_uncovered": "Не покрыто новыми прогнозами записей: {n} ({cells}). Либо добавьте их в новые документы, либо укажите причину прекращения.",
        "repl_race": "Состав пула изменился, пока готовилась замена — проверьте заново.",
        "drift_disbanded": "пул расформирован", "drift_removed": "из пула вышли: {mps}", "drift_added": "в пул добавлены: {mps}",
        "drift_block_pool": "Состав пула «{pool}» изменился: документ проводится только общей заменой на вкладке «Замена после изменения пула».",
        "drift_block_mp": "Маркетплейс затронут изменением состава пула ({pools}): документ проводится только общей заменой.",
        "drift_block_member": "Маркетплейс входит в пул ({pools}), состав которого изменился: документ проводится только общей заменой.",
        "sec_actions": "Действия", "pick_skus": "SKU", "pick_months": "Месяцы", "all_skus": "все SKU", "all_months": "все месяцы",
        "btn_approve": "Утвердить", "btn_unapprove": "Снять утверждение", "btn_zeros": "Пустоты → 0", "btn_delete": "Удалить строки",
        "approved_n": "Утверждено ячеек: {n}.", "approve_empty": "Не утверждено — пустые ячейки: {cells}",
        "unapproved_n": "Снято утверждение: {n}.", "zeros_n": "Заполнено нулями: {n}.",
        "del_has_approved": "Строки с утверждёнными значениями не удаляются: {skus}.",
        "del_confirm": "Удалить {n} строк? В них есть введённые значения. Нажмите ещё раз для подтверждения.",
        "deleted_n": "Удалено строк: {n}.",
        "sec_post": "Проведение", "btn_post": "Провести документ", "post_ok": "Документ {n} проведён: действующих записей {k}, заменено {r}.",
        "post_block": "Проведение заблокировано:", "post_no_rows": "в документе нет ни одного SKU;",
        "post_empty": "не заполнено ячеек: {n} ({cells});", "post_unapproved": "не утверждено ячеек: {n} ({cells});",
        "post_past": "в периоде прошедшие месяцы: {months} — проведение их не меняет и не создаёт (§4);",
        "post_missing": "полный прогноз: в матрице есть продажные SKU, которых нет в документе ({n}): {skus} — добавьте их или переключите на «Частичный» (сценарий 17);",
        "hdr_edit": "Шапка", "hdr_locked": "Объект и период заблокированы: в документе есть утверждённые значения (§9).",
        "btn_hdr_save": "Сохранить шапку", "hdr_saved": "Шапка сохранена.",
        "sec_prices": "Целевая цена по месяцам, €", "prices_help": "Цена не утверждается вместе с количеством и меняется в черновике без снятия утверждения. Прогноз выручки = штуки × цена.",
        "btn_prices_save": "Сохранить цены", "prices_saved": "Сохранено цен: {n}.",
        "sec_states": "Состояние по месяцам", "states_help": "○ не утверждено · ✓ утверждено · ⟲ заменено новой версией · пусто — значения нет",
        "post_dd": "Зависимая потребность: рассчитано {c}, снято {s}, освежено {t}.",
        "post_dd_err": "Ошибок расчёта зависимой потребности: {e} — раздел «Зависимая потребность» в карточке.",
        "post_dd_fail": "Зависимая потребность не рассчитана: {e}. Прогноз проведён; расчёт повторит ночная джоба.",
        "sec_dd": "Зависимая потребность",
        "dd_help": "Потребность в базовых SKU из действующих прогнозов наборов: прогноз набора × количество в составе (ТЗ 011). "
                   "Считается при проведении и ночью. Поверх прогноза наборов не суммируется — это отдельные строки реестра.",
        "dd_empty": "Наборов в действующем прогнозе этого объекта нет — считать нечего.",
        "dd_col_sku": "Базовый SKU", "dd_col_qty": "Потребность", "dd_col_details": "Строк расчёта", "dd_col_errors": "Ошибок", "dd_col_at": "Рассчитано",
        "dd_errors_hdr": "Ошибки расчёта ({n}):", "dd_col_kit": "Набор", "dd_col_err": "Что не так",
        "sec_doclog": "Журнал документа",
        "log_from": "Проведено / изменено с", "log_to": "по", "log_sku": "SKU", "log_month": "Месяц прогноза",
        "log_col_at": "Когда", "log_col_actor": "Кто", "log_col_doc": "Документ", "log_col_field": "Поле", "log_col_old": "Было", "log_col_new": "Стало", "log_col_src": "Источник",
        "log_empty": "Записей нет.",
        "err_read": "Не прочиталось: {e}", "err_write": "Не записалось: {e}",
        "actor_unknown": "kabinet-app", "actor_loader": "загрузчик (принципал)",
    },
    "uk": {
        "title": "Прогноз продажів", "caption": "Документи прогнозу: чернетка → затвердження значень → проведення. "
                 "Чинний прогноз — лише з проведених документів; проведений документ не правиться, зміна — новим документом.",
        "tab_docs": "Документи", "tab_log": "Журнал змін", "tab_new": "Новий документ",
        "f_object": "Обʼєкт", "f_status": "Статус", "f_month": "Місяць у періоді", "all": "усі",
        "st_draft": "Чернетка", "st_posted": "Проведено", "full": "увесь асортимент матриці", "partial": "частина асортименту",
        "col_number": "Номер", "col_date": "Дата", "col_object": "Обʼєкт", "col_period": "Період", "col_compl": "Охоплення матриці",
        "col_status": "Статус", "col_rows": "SKU", "col_filled": "Заповнено", "col_approved": "Затверджено", "col_source": "Джерело",
        "col_created_by": "Створив", "col_posted_at": "Проведено", "col_comment": "Коментар",
        "no_docs": "Документів за фільтром немає.", "open_doc": "Відкрити документ",
        "new_object_type": "Тип обʼєкта", "mp": "Marketplace", "pool": "Пул", "new_first": "Перший місяць", "new_last": "Останній місяць",
        "new_compl": "Охоплення матриці", "new_comment": "Коментар", "btn_create": "Створити чернетку",
        "ph_pick_sku": "виберіть SKU", "lbl_liquidation": "розпродаж", "lbl_no_admission": "немає допуску",
        "btn_matrix_help": "Сценарій 16: додаються лише продажні SKU матриці, яких ще немає; наявні рядки та значення не чіпаються",
        "lost_admission": "SKU без допуску на обʼєкті (рядки не видаляються автоматично, сценарій 16): ",
        "src_sheet": "завантаження з аркуша", "btn_post_confirm": "Так, провести",
        "post_confirm": "Проведення незворотне: {n} стане чинним прогнозом за {k} значеннями, проведений документ не правиться — зміна лише новим документом. Натисніть «Так, провести».",
        "err_period": "Останній місяць не раніше першого і не далі 13 місяців (§4).",
        "err_past": "Перший місяць — поточний або майбутній: минулі місяці заблоковано (§4).",
        "created": "Створено чернетку {n}.",
        "hdr_object": "Обʼєкт", "hdr_period": "Період", "hdr_snapshot": "Склад пулу на {d}", "hdr_created": "Створено {by} {at}",
        "hdr_posted": "Проведено {by} {at}", "hdr_source": "Джерело",
        "m_rows": "SKU у документі", "m_cells": "Заповнено клітинок", "m_approved": "Затверджено клітинок", "m_matrix": "SKU матриці в документі",
        "m_matrix_help": "Для повного прогнозу: унікальні продажні SKU чинної матриці обʼєкта, включені в документ / усі продажні SKU матриці (§12).",
        "m_sum": "Разом за період, шт", "m_rev": "Прогноз виручки, €",
        "grid_help": "Порожньо — прогноз не заповнено, 0 — продажів не плануємо. Минулі місяці та проведений документ не редагуються; "
                     "затверджені клітинки змінюються лише після зняття затвердження.",
        "col_sku": "SKU", "col_type": "Тип", "col_state": "Стан", "col_total": "Разом", "col_name": "Назва",
        "type_base": "базовий", "type_composite": "складений", "type_unknown": "—",
        "state_all_appr": "затверджено", "state_none": "не затверджено", "state_part": "затв. {a}/{n}", "state_empty": "порожньо: {e}",
        "btn_save": "Зберегти значення", "saved": "Збережено змін: {n}.", "nothing_changed": "Змін немає.",
        "rej_approved": "{sku} · {m}: значення затверджено — спершу зніміть затвердження.",
        "rej_past": "{sku} · {m}: минулий місяць заблоковано.",
        "rej_value": "{sku} · {m}: допускаються цілі числа не менше нуля.",
        "rejected": "Не записано {n} значень:", "grid_posted": "Документ проведено — значення лише для читання.",
        "sec_add": "Додати SKU", "add_pick": "SKU з довідника (допущених на обʼєкті: {a}, усього: {n})", "btn_add": "Додати вибрані",
        "btn_matrix": "Заповнити за матрицею", "matrix_added": "Додано за матрицею: {n} SKU.", "matrix_none": "Усі продажні SKU матриці вже в документі.",
        "add_done": "Додано: {n}. Відхилено: {r}.", "add_no_admission": "{sku}: немає допуску до самостійного продажу на обʼєкті (§3).",
        "add_liquidation": "{sku}: допуск закрито — додано як розпродаж за попереднім допуском (§7).", "add_dup": "{sku}: вже в документі.",
        "add_unknown": "{sku}: немає в довіднику SKU.",
        "ro_all_past": "Документ лише для перегляду: усі його місяці вже минули. Непроведена чернетка не видаляється і в розрахунках не бере участі, але змінити, затвердити чи провести її не можна — минулі місяці прогнозом не перезаписуються.",
        "rej_restricted": "{sku} · {m}: продаж SKU зараз заборонено ({why}) — значення збережено в чернетці, затвердження не виконано.",
        "why_inactive": "SKU деактивовано в довіднику", "why_restricted": "обмеження застосування для цього майданчика або країни",
        "why_unknown": "немає в довіднику SKU",
        "post_restricted": "продаж заборонено в SKU: {skus} — приберіть їх з документа або усуньте заборону;",
        # ── завантаження з файлу і з Google Таблиці ──
        "sec_upload": "Завантаження з файлу", "up_help": "Рядок джерела — один SKU, прогнозні значення — колонками за місяцями. "
                 "Обʼєкт береться з документа, у файлі його вказувати не потрібно. Завантаження кладе значення в чернетку і нічого не затверджує: "
                 "порожня клітинка нічого не змінює, 0 означає «продажів не плануємо». Помилка хоча б в одній клітинці зупиняє все завантаження.",
        "up_src": "Джерело", "up_src_file": "Файл Excel або CSV", "up_src_gs": "Google Таблиця",
        "up_file": "Файл", "up_sheet": "Аркуш", "up_header": "Рядок заголовків", "up_gs_url": "Посилання на Google Таблицю",
        "up_sku_col": "Колонка з артикулом SKU", "up_map": "Який місяць документа бере кожна колонка джерела",
        "up_skip": "пропустити", "up_col_nameless": "колонка", "up_col_month": "Місяць", "up_col_old": "Було", "up_col_new": "Стане",
        "up_map_dup": "Один місяць документа вибрано у двох колонок — залиште одну.",
        "up_no_months": "Зіставте хоча б одну колонку з місяцем документа.",
        "up_preview": "До завантаження: SKU {s}, значень {v}; нових SKU {a}, замін заповненого {r}.",
        "up_errors": "Завантаження заблоковано, помилок {n}. Документ не змінено — виправте джерело і перевірте знову.",
        "up_err_unknown": "{sku} — немає в довіднику SKU, завантаження нові артикули не створює",
        "up_err_admission": "{sku} — немає допуску на обʼєкті прогнозу, додати його завантаженням не можна",
        "up_err_value": "{sku} · {m}: «{v}» — потрібне ціле число не менше нуля",
        "up_err_dup": "{sku} · {m} — поєднання артикула і місяця в джерелі повторюється",
        "up_err_approved": "{sku} · {m} — значення затверджено; спершу зніміть затвердження",
        "up_err_past": "{sku} · {m} — минулий місяць не змінюється",
        "up_replace": "Заповнених значень буде замінено: {n}. Перевірте стовпці «Було» і «Стане» та натисніть «Так, замінити і завантажити».",
        "up_btn_apply": "Завантажити", "up_btn_apply_confirm": "Так, замінити і завантажити",
        "up_done": "Завантажено значень: {n}, додано SKU: {k}.",
        "up_nothing": "Завантажувати нічого: значення джерела збігаються з документом.",
        "up_read_fail": "Джерело не прочитано: {e}", "up_gs_fail": "Google Таблиця недоступна: {e}",
        "liq_note": "розпродаж за колишнім допуском", "src_file": "завантаження з файлу", "src_gsheet": "завантаження з Google Таблиці",
        # ── зміна складу пулу: перестворення і спільна заміна ──
        "tab_repl": "Заміна після зміни пулу",
        "col_recreate": "Перестворення", "recreate_needed": "потрібне",
        "recreate_banner": "Склад пулу змінився: {what}. Попередній прогноз далі чинний, "
                 "але окремо цей документ більше не проводиться — заміна виконується цілком на вкладці «{tab}».",
        "repl_help": "Зміна складу пулу сама собою прогнози не переключає: до спільної заміни звіти й забезпечення "
                 "живуть на попередніх прогнозах і збереженому в них складі. Маркетплейс, що вийшов, далі рахується у прогнозі пулу, "
                 "доданий попереднім прогнозом пулу не покривається. Переключення відбувається однією дією: або всі нові документи "
                 "проводяться разом, або не проводиться жоден.",
        "repl_none": "Склади пулів збігаються з чинними прогнозами — перестворювати нічого.",
        "repl_hdr": "Пул «{pool}»", "repl_what": "{what}. Документ {n}: склад у прогнозі — {was}; склад пулу зараз — {now}.",
        "repl_scope": "Замінюються {rows} чинних записів з {m}; минулі місяці не змінюються.",
        "repl_pick_pool": "Новий прогноз пулу «{pool}»", "repl_pick_mp": "Новий прогноз {mp}",
        "repl_none_pick": "— не вибрано —",
        "repl_role_removed": "вийшов з пулу", "repl_role_added": "доданий до пулу",
        "repl_mp_active": "працює", "repl_mp_inactive": "деактивований",
        "repl_reason_mp": "Причина припинення прогнозу {mp}", "repl_reason_ph": "чому прогноз припиняє дію",
        "repl_added_hint": "покривається новим прогнозом пулу; його власний прогноз цією ж операцією перестане діяти",
        "repl_disbanded_hint": "У пулі не залишилося учасників: новий прогноз пулу не потрібен — потрібні прогнози маркетплейсів, що продовжують роботу, або причини припинення.",
        "repl_reason": "Причина зміни складу (потрапить в історію)",
        "repl_m_docs": "Документів", "repl_m_sup": "Записів до заміни", "repl_m_term": "Записів до припинення",
        "repl_blocked": "Заміна не виконується, причин {n}:",
        "repl_ready": "Перевірки пройдено: можна виконувати заміну.",
        "repl_need_op_reason": "Вкажіть причину зміни складу.",
        "repl_confirm": "Заміна незворотна: документів {d}, записів до заміни {s}, до припинення {t}. Натисніть «Так, замінити».",
        "repl_btn": "Замінити прогнози після зміни пулу", "repl_btn_confirm": "Так, замінити",
        "repl_done": "Заміну {op} виконано: проведено документів {d}, замінено записів {s}, припинено {t}.",
        "repl_dd_err": "Залежну потребу перераховано не повністю: {e}",
        "repl_hist": "Виконані заміни", "repl_hist_empty": "Замін ще не було.",
        "repl_c_at": "Коли", "repl_c_what": "Що змінилося", "repl_c_reason": "Причина",
        "repl_no_doc": "Документ {d} не знайдено.", "repl_not_draft": "{n}: документ уже не чернетка.",
        "repl_no_comment": "{n}: у комментарі документа потрібна причина перестворення.",
        "repl_stale_snapshot": "{n}: документ створено з попереднім складом ({was}), а в пулі зараз {now} — створіть новий документ.",
        "repl_doc_empty": "{n}: у документі немає рядків.",
        "repl_need_doc": "{mp} продовжує роботу — потрібен новий прогноз: власний або у складі актуального пулу.",
        "repl_need_reason": "{mp} деактивований — замість нового прогнозу вкажіть причину припинення.",
        "repl_double": "{mp} потрапить разом у власний прогноз і в прогноз пулу {n} — залиште одне джерело.",
        "repl_uncovered": "Не покрито новими прогнозами записів: {n} ({cells}). Або додайте їх у нові документи, або вкажіть причину припинення.",
        "repl_race": "Склад пулу змінився, поки готувалася заміна — перевірте знову.",
        "drift_disbanded": "пул розформовано", "drift_removed": "з пулу вийшли: {mps}", "drift_added": "до пулу додані: {mps}",
        "drift_block_pool": "Склад пулу «{pool}» змінився: документ проводиться лише спільною заміною на вкладці «Заміна після зміни пулу».",
        "drift_block_mp": "Маркетплейс зачеплений зміною складу пулу ({pools}): документ проводиться лише спільною заміною.",
        "drift_block_member": "Маркетплейс входить у пул ({pools}), склад якого змінився: документ проводиться лише спільною заміною.",
        "sec_actions": "Дії", "pick_skus": "SKU", "pick_months": "Місяці", "all_skus": "усі SKU", "all_months": "усі місяці",
        "btn_approve": "Затвердити", "btn_unapprove": "Зняти затвердження", "btn_zeros": "Порожні → 0", "btn_delete": "Видалити рядки",
        "approved_n": "Затверджено клітинок: {n}.", "approve_empty": "Не затверджено — порожні клітинки: {cells}",
        "unapproved_n": "Знято затвердження: {n}.", "zeros_n": "Заповнено нулями: {n}.",
        "del_has_approved": "Рядки із затвердженими значеннями не видаляються: {skus}.",
        "del_confirm": "Видалити {n} рядків? У них є введені значення. Натисніть ще раз для підтвердження.",
        "deleted_n": "Видалено рядків: {n}.",
        "sec_post": "Проведення", "btn_post": "Провести документ", "post_ok": "Документ {n} проведено: чинних записів {k}, замінено {r}.",
        "post_block": "Проведення заблоковано:", "post_no_rows": "у документі немає жодного SKU;",
        "post_empty": "не заповнено клітинок: {n} ({cells});", "post_unapproved": "не затверджено клітинок: {n} ({cells});",
        "post_past": "у періоді минулі місяці: {months} — проведення їх не змінює і не створює (§4);",
        "post_missing": "повний прогноз: у матриці є продажні SKU, яких немає в документі ({n}): {skus} — додайте їх або перемкніть на «Частковий» (сценарій 17);",
        "hdr_edit": "Шапка", "hdr_locked": "Обʼєкт і період заблоковано: у документі є затверджені значення (§9).",
        "btn_hdr_save": "Зберегти шапку", "hdr_saved": "Шапку збережено.",
        "sec_prices": "Цільова ціна за місяцями, €", "prices_help": "Ціна не затверджується разом із кількістю і змінюється в чернетці без зняття затвердження. Прогноз виручки = штуки × ціна.",
        "btn_prices_save": "Зберегти ціни", "prices_saved": "Збережено цін: {n}.",
        "sec_states": "Стан за місяцями", "states_help": "○ не затверджено · ✓ затверджено · ⟲ замінено новою версією · порожньо — значення немає",
        "post_dd": "Залежна потреба: розраховано {c}, знято {s}, освіжено {t}.",
        "post_dd_err": "Помилок розрахунку залежної потреби: {e} — розділ «Залежна потреба» у картці.",
        "post_dd_fail": "Залежну потребу не розраховано: {e}. Прогноз проведено; розрахунок повторить нічна джоба.",
        "sec_dd": "Залежна потреба",
        "dd_help": "Потреба в базових SKU з чинних прогнозів наборів: прогноз набору × кількість у складі (ТЗ 011). "
                   "Рахується під час проведення і вночі. Поверх прогнозу наборів не додається — це окремі рядки реєстру.",
        "dd_empty": "Наборів у чинному прогнозі цього об’єкта немає — рахувати нічого.",
        "dd_col_sku": "Базовий SKU", "dd_col_qty": "Потреба", "dd_col_details": "Рядків розрахунку", "dd_col_errors": "Помилок", "dd_col_at": "Розраховано",
        "dd_errors_hdr": "Помилки розрахунку ({n}):", "dd_col_kit": "Набір", "dd_col_err": "Що не так",
        "sec_doclog": "Журнал документа",
        "log_from": "Проведено / змінено з", "log_to": "по", "log_sku": "SKU", "log_month": "Місяць прогнозу",
        "log_col_at": "Коли", "log_col_actor": "Хто", "log_col_doc": "Документ", "log_col_field": "Поле", "log_col_old": "Було", "log_col_new": "Стало", "log_col_src": "Джерело",
        "log_empty": "Записів немає.",
        "err_read": "Не прочиталося: {e}", "err_write": "Не записалося: {e}",
        "actor_unknown": "kabinet-app", "actor_loader": "завантажувач (принципал)",
    },
    "en": {
        "title": "Sales forecast", "caption": "Forecast documents: draft → approve values → post. "
                 "The effective forecast comes only from posted documents; a posted document is immutable, changes go through a new one.",
        "tab_docs": "Documents", "tab_log": "Change log", "tab_new": "New document",
        "f_object": "Object", "f_status": "Status", "f_month": "Month within period", "all": "all",
        "st_draft": "Draft", "st_posted": "Posted", "full": "whole matrix assortment", "partial": "part of the assortment",
        "col_number": "Number", "col_date": "Date", "col_object": "Object", "col_period": "Period", "col_compl": "Matrix coverage",
        "col_status": "Status", "col_rows": "SKUs", "col_filled": "Filled", "col_approved": "Approved", "col_source": "Source",
        "col_created_by": "Created by", "col_posted_at": "Posted", "col_comment": "Comment",
        "no_docs": "No documents match the filter.", "open_doc": "Open document",
        "new_object_type": "Object type", "mp": "Marketplace", "pool": "Pool", "new_first": "First month", "new_last": "Last month",
        "new_compl": "Matrix coverage", "new_comment": "Comment", "btn_create": "Create draft",
        "ph_pick_sku": "pick SKUs", "lbl_liquidation": "sell-off", "lbl_no_admission": "no admission",
        "btn_matrix_help": "Scenario 16: adds only sellable matrix SKUs not yet present; existing rows and values are kept",
        "lost_admission": "SKUs without admission on this object (rows are not removed automatically, scenario 16): ",
        "src_sheet": "sheet import", "btn_post_confirm": "Yes, post",
        "post_confirm": "Posting is irreversible: {n} becomes the effective forecast for {k} values; a posted document cannot be edited — changes only via a new document. Click «Yes, post».",
        "err_period": "Last month must not precede the first one and the period is at most 13 months (§4).",
        "err_past": "First month must be the current or a future month: past months are locked (§4).",
        "created": "Draft {n} created.",
        "hdr_object": "Object", "hdr_period": "Period", "hdr_snapshot": "Pool members as of {d}", "hdr_created": "Created by {by} {at}",
        "hdr_posted": "Posted by {by} {at}", "hdr_source": "Source",
        "m_rows": "SKUs in document", "m_cells": "Cells filled", "m_approved": "Cells approved", "m_matrix": "Matrix SKUs in document",
        "m_matrix_help": "Full forecast: unique sellable SKUs of the object's active matrix included in the document / all sellable matrix SKUs (§12).",
        "m_sum": "Period total, units", "m_rev": "Forecast revenue, €",
        "grid_help": "Empty — not filled, 0 — no sales planned. Past months and posted documents are read-only; "
                     "approved cells change only after unapproval.",
        "col_sku": "SKU", "col_type": "Type", "col_state": "State", "col_total": "Total", "col_name": "Name",
        "type_base": "base", "type_composite": "composite", "type_unknown": "—",
        "state_all_appr": "approved", "state_none": "not approved", "state_part": "appr. {a}/{n}", "state_empty": "empty: {e}",
        "btn_save": "Save values", "saved": "Saved changes: {n}.", "nothing_changed": "No changes.",
        "rej_approved": "{sku} · {m}: value is approved — unapprove first.",
        "rej_past": "{sku} · {m}: past month is locked.",
        "rej_value": "{sku} · {m}: only non-negative integers are allowed.",
        "rejected": "Not written: {n} values:", "grid_posted": "Document is posted — values are read-only.",
        "sec_add": "Add SKUs", "add_pick": "SKUs from the directory (admitted on this object: {a}, total: {n})", "btn_add": "Add selected",
        "btn_matrix": "Fill from matrix", "matrix_added": "Added from matrix: {n} SKUs.", "matrix_none": "All sellable matrix SKUs are already in the document.",
        "add_done": "Added: {n}. Rejected: {r}.", "add_no_admission": "{sku}: no admission for standalone sale on this object (§3).",
        "add_liquidation": "{sku}: admission closed — added as sell-off under the former admission (§7).", "add_dup": "{sku}: already in the document.",
        "add_unknown": "{sku}: not in the SKU directory.",
        "ro_all_past": "This document is read-only: all of its months are already in the past. An unposted draft is never deleted and takes no part in calculations, but it cannot be edited, approved or posted — past months are not rewritten by a forecast.",
        "rej_restricted": "{sku} · {m}: selling this SKU is currently prohibited ({why}) — the value stays in the draft, approval did not happen.",
        "why_inactive": "the SKU is deactivated in the directory", "why_restricted": "a usage restriction for this platform or country",
        "why_unknown": "not in the SKU directory",
        "post_restricted": "selling is prohibited for SKUs: {skus} — remove them from the document or lift the restriction;",
        # ── upload from a file or a Google Sheet ──
        "sec_upload": "Upload from a file", "up_help": "One source row is one SKU; forecast values go in columns by month. "
                 "The object comes from the document, so the file does not need it. The upload fills the draft and approves nothing: "
                 "an empty cell changes nothing, 0 means no sales planned. A single bad cell stops the whole upload.",
        "up_src": "Source", "up_src_file": "Excel or CSV file", "up_src_gs": "Google Sheet",
        "up_file": "File", "up_sheet": "Sheet", "up_header": "Header row", "up_gs_url": "Google Sheet link",
        "up_sku_col": "SKU column", "up_map": "Which document month each source column feeds",
        "up_skip": "skip", "up_col_nameless": "column", "up_col_month": "Month", "up_col_old": "Was", "up_col_new": "Will be",
        "up_map_dup": "The same document month is picked for two columns — leave one.",
        "up_no_months": "Map at least one column to a document month.",
        "up_preview": "To upload: {s} SKU, {v} values; {a} new SKU, {r} filled values replaced.",
        "up_errors": "Upload blocked, {n} errors. The document is unchanged — fix the source and check again.",
        "up_err_unknown": "{sku} — not in the SKU directory; the upload does not create new codes",
        "up_err_admission": "{sku} — not admitted on this forecast object, the upload cannot add it",
        "up_err_value": "{sku} · {m}: \u00ab{v}\u00bb — an integer of zero or more is required",
        "up_err_dup": "{sku} · {m} — this SKU and month pair repeats in the source",
        "up_err_approved": "{sku} · {m} — the value is approved; unapprove it first",
        "up_err_past": "{sku} · {m} — a past month is not changed",
        "up_replace": "{n} filled values will be replaced. Check the Was / Will be columns and press Yes, replace and upload.",
        "up_btn_apply": "Upload", "up_btn_apply_confirm": "Yes, replace and upload",
        "up_done": "{n} values uploaded, {k} SKU added.",
        "up_nothing": "Nothing to upload: the source matches the document.",
        "up_read_fail": "Source not read: {e}", "up_gs_fail": "Google Sheet unavailable: {e}",
        "liq_note": "liquidation under the former admission", "src_file": "file upload", "src_gsheet": "Google Sheet upload",
        # ── pool composition change: re-creation and joint replacement ──
        "tab_repl": "Replacement after a pool change",
        "col_recreate": "Re-creation", "recreate_needed": "required",
        "recreate_banner": "The pool composition changed: {what}. The previous forecast stays effective, "
                 "but this document can no longer be posted on its own — the replacement happens as a whole on the \u00ab{tab}\u00bb tab.",
        "repl_help": "A pool composition change does not switch forecasts by itself: until the joint replacement, reports and coverage "
                 "use the previously effective forecasts and the composition stored in them. A marketplace that left still counts in the pool forecast, "
                 "and a newly added one is not covered by the pool's old forecast. The switch happens in one action: either every new document "
                 "is posted at once, or none is.",
        "repl_none": "Pool compositions match the effective forecasts — nothing to re-create.",
        "repl_hdr": "Pool \u00ab{pool}\u00bb", "repl_what": "{what}. Document {n}: composition in the forecast — {was}; pool composition now — {now}.",
        "repl_scope": "{rows} effective records from {m} will be replaced; past months stay unchanged.",
        "repl_pick_pool": "New forecast for pool \u00ab{pool}\u00bb", "repl_pick_mp": "New forecast for {mp}",
        "repl_none_pick": "— not picked —",
        "repl_role_removed": "left the pool", "repl_role_added": "added to the pool",
        "repl_mp_active": "operating", "repl_mp_inactive": "deactivated",
        "repl_reason_mp": "Reason the {mp} forecast ends", "repl_reason_ph": "why the forecast stops being effective",
        "repl_added_hint": "covered by the new pool forecast; its own forecast stops being effective in this same operation",
        "repl_disbanded_hint": "No members left in the pool: a new pool forecast is not needed — forecasts for the marketplaces that keep operating are, or reasons for ending them.",
        "repl_reason": "Reason for the composition change (kept in history)",
        "repl_m_docs": "Documents", "repl_m_sup": "Records to replace", "repl_m_term": "Records to end",
        "repl_blocked": "The replacement is blocked, {n} reasons:",
        "repl_ready": "Checks passed: the replacement can run.",
        "repl_need_op_reason": "State the reason for the composition change.",
        "repl_confirm": "The replacement cannot be undone: {d} documents, {s} records replaced, {t} ended. Press Yes, replace.",
        "repl_btn": "Replace forecasts after the pool change", "repl_btn_confirm": "Yes, replace",
        "repl_done": "Replacement {op} done: {d} documents posted, {s} records replaced, {t} ended.",
        "repl_dd_err": "Dependent demand was not fully recalculated: {e}",
        "repl_hist": "Replacements done", "repl_hist_empty": "No replacements yet.",
        "repl_c_at": "When", "repl_c_what": "What changed", "repl_c_reason": "Reason",
        "repl_no_doc": "Document {d} not found.", "repl_not_draft": "{n}: the document is no longer a draft.",
        "repl_no_comment": "{n}: the document comment must state the reason for re-creation.",
        "repl_stale_snapshot": "{n}: the document was created with the former composition ({was}) while the pool now holds {now} — create a new document.",
        "repl_doc_empty": "{n}: the document has no rows.",
        "repl_need_doc": "{mp} keeps operating — it needs a new forecast: its own or within a current pool.",
        "repl_need_reason": "{mp} is deactivated — instead of a new forecast, state why its forecast ends.",
        "repl_double": "{mp} would count both in its own forecast and in pool forecast {n} — leave one source.",
        "repl_uncovered": "{n} records are not covered by new forecasts ({cells}). Either add them to the new documents or state why they end.",
        "repl_race": "The pool composition changed while the replacement was being prepared — check again.",
        "drift_disbanded": "the pool was disbanded", "drift_removed": "left the pool: {mps}", "drift_added": "added to the pool: {mps}",
        "drift_block_pool": "The composition of pool \u00ab{pool}\u00bb changed: the document is posted only through the joint replacement on the Replacement after a pool change tab.",
        "drift_block_mp": "This marketplace is affected by a pool composition change ({pools}): the document is posted only through the joint replacement.",
        "drift_block_member": "This marketplace belongs to a pool whose composition changed ({pools}): the document is posted only through the joint replacement.",
        "sec_actions": "Actions", "pick_skus": "SKUs", "pick_months": "Months", "all_skus": "all SKUs", "all_months": "all months",
        "btn_approve": "Approve", "btn_unapprove": "Unapprove", "btn_zeros": "Empty → 0", "btn_delete": "Delete rows",
        "approved_n": "Approved cells: {n}.", "approve_empty": "Not approved — empty cells: {cells}",
        "unapproved_n": "Unapproved: {n}.", "zeros_n": "Filled with zeros: {n}.",
        "del_has_approved": "Rows with approved values cannot be deleted: {skus}.",
        "del_confirm": "Delete {n} rows? They contain values. Click again to confirm.",
        "deleted_n": "Rows deleted: {n}.",
        "sec_post": "Posting", "btn_post": "Post document", "post_ok": "Document {n} posted: {k} effective records, {r} superseded.",
        "post_block": "Posting is blocked:", "post_no_rows": "the document has no SKUs;",
        "post_empty": "empty cells: {n} ({cells});", "post_unapproved": "unapproved cells: {n} ({cells});",
        "post_past": "the period contains past months: {months} — posting neither changes nor creates them (§4);",
        "post_missing": "full forecast: the matrix has sellable SKUs missing from the document ({n}): {skus} — add them or switch to «Partial» (scenario 17);",
        "hdr_edit": "Header", "hdr_locked": "Object and period are locked: the document has approved values (§9).",
        "btn_hdr_save": "Save header", "hdr_saved": "Header saved.",
        "sec_prices": "Target price by month, €", "prices_help": "Price is not approved together with quantity and can change in a draft without unapproval. Revenue = units × price.",
        "btn_prices_save": "Save prices", "prices_saved": "Prices saved: {n}.",
        "sec_states": "State by month", "states_help": "○ not approved · ✓ approved · ⟲ superseded · blank — no value",
        "post_dd": "Dependent demand: {c} calculated, {s} superseded, {t} refreshed.",
        "post_dd_err": "Dependent demand errors: {e} — see the «Dependent demand» section in the card.",
        "post_dd_fail": "Dependent demand not calculated: {e}. The forecast is posted; the nightly job will retry.",
        "sec_dd": "Dependent demand",
        "dd_help": "Demand for base SKUs derived from effective kit forecasts: kit forecast x component quantity (spec 011). "
                   "Calculated on posting and nightly. It is not added on top of kit forecasts — these are separate register rows.",
        "dd_empty": "No kits in this object's effective forecast — nothing to calculate.",
        "dd_col_sku": "Base SKU", "dd_col_qty": "Demand", "dd_col_details": "Calc rows", "dd_col_errors": "Errors", "dd_col_at": "Calculated",
        "dd_errors_hdr": "Calculation errors ({n}):", "dd_col_kit": "Kit", "dd_col_err": "What is wrong",
        "sec_doclog": "Document log",
        "log_from": "Posted / changed from", "log_to": "to", "log_sku": "SKU", "log_month": "Forecast month",
        "log_col_at": "When", "log_col_actor": "Who", "log_col_doc": "Document", "log_col_field": "Field", "log_col_old": "Old", "log_col_new": "New", "log_col_src": "Source",
        "log_empty": "No records.",
        "err_read": "Read failed: {e}", "err_write": "Write failed: {e}",
        "actor_unknown": "kabinet-app", "actor_loader": "loader (service principal)",
    },
}


def _lang() -> str:
    try:
        lg = str(get_lang() or "ru").lower()[:2]
    except Exception:
        lg = str(st.session_state.get("lang", "ru")).lower()[:2]
    return lg if lg in TR else "ru"


def _tr(key: str) -> str:
    return TR[_lang()].get(key, TR["ru"].get(key, key))


def _trf(key: str, **kw) -> str:
    try:
        return _tr(key).format(**kw)
    except (KeyError, IndexError, ValueError):
        return _tr(key)


FIELD_LBL = {"ru": {"quantity": "количество", "target_price": "целевая цена", "approval": "утверждение", "row": "строка SKU", "document": "документ", "header": "шапка"},
             "uk": {"quantity": "кількість", "target_price": "цільова ціна", "approval": "затвердження", "row": "рядок SKU", "document": "документ", "header": "шапка"},
             "en": {"quantity": "quantity", "target_price": "target price", "approval": "approval", "row": "SKU row", "document": "document", "header": "header"}}
VALUE_LBL = {"ru": {"unapproved": "не утверждено", "approved": "утверждено", "draft": "черновик", "posted": "проведён", "added": "добавлена", "deleted": "удалена", "present": "была",
                    "added (liquidation)": "добавлена (распродажа)"},
             "uk": {"unapproved": "не затверджено", "approved": "затверджено", "draft": "чернетка", "posted": "проведено", "added": "додано", "deleted": "видалено", "present": "була",
                    "added (liquidation)": "додано (розпродаж)"},
             "en": {}}
SOURCE_LBL = {"ru": {"manual": "вручную", "manual:fill_zeros": "пустоты → 0", "approve": "утверждение", "unapprove": "снятие утверждения", "post": "проведение",
                     "import:file": "загрузка из файла", "import:gsheet": "загрузка из Google Таблицы"},
              "uk": {"manual": "вручну", "manual:fill_zeros": "порожні → 0", "approve": "затвердження", "unapprove": "зняття затвердження", "post": "проведення",
                     "import:file": "завантаження з файлу", "import:gsheet": "завантаження з Google Таблиці"},
              "en": {"manual": "manual", "manual:fill_zeros": "empty → 0", "approve": "approve", "unapprove": "unapprove", "post": "post",
                     "import:file": "file upload", "import:gsheet": "Google Sheet upload"}}


def _log_view(lg: pd.DataFrame) -> pd.DataFrame:
    """Журнал на языке интерфейса: токены полей и источников — в слова, импорт из листа — как «загрузка из листа»."""
    L = _lang()
    lg = lg.copy()
    lg["field"] = lg["field"].map(lambda f: FIELD_LBL[L].get(f, f))
    for c in ("old_value", "new_value"):
        lg[c] = lg[c].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) == "None" else VALUE_LBL[L].get(str(v), str(v)))
    # джобы принципала пишут в журнал свой UUID — человеку он ни о чём
    lg["actor"] = lg["actor"].map(lambda a: _tr("actor_loader") if str(a).startswith("b1698364-") else a)
    lg["source"] = lg["source"].map(lambda x: _tr("src_sheet") if str(x).startswith("import:sheet") else SOURCE_LBL[L].get(str(x), str(x)))
    lg["month"] = lg["month"].map(lambda m: month_label(m) if pd.notna(m) else "")
    lg["changed_at"] = pd.to_datetime(lg["changed_at"]).dt.strftime("%d.%m.%Y %H:%M:%S")
    return lg


def _actor() -> str:
    """Кто действует. У приложения нет входа по пользователям (роли ТЗ §9 не реализованы);
    на Streamlit Cloud с закрытым доступом есть st.user.email — берём его, иначе имя приложения."""
    try:
        u = getattr(st, "user", None)
        email = getattr(u, "email", None) if u is not None else None
        if email:
            return str(email)
    except Exception:
        pass
    return _tr("actor_unknown")


# ═══════════════════════════════════════════════════════════════════════════
# БАЗА
# ═══════════════════════════════════════════════════════════════════════════

def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def tx(fn):
    """Одна транзакция на действие: либо всё записалось, либо ничего (проведение — десятки записей)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        out = fn(cur)
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_empty(v) -> bool:
    """Пусто ли значение ячейки: None, NaN, pd.NA (nullable Float64 из редактора) или пустая строка.
    `v == ""` на pd.NA бросает «boolean value of NA is ambiguous», поэтому сравнение — последним и только для строк."""
    if v is None or v is pd.NA:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def blank_na(df: pd.DataFrame, cols: list, fmt="{:.0f}") -> pd.DataFrame:
    """NumberColumn рисует пропуск словом «None» — и у float64, и у nullable Float64/Int64.
    Для нередактируемых таблиц отдаём строки: пусто остаётся пустым, 0 остаётся нулём."""
    out = df.copy()
    for c in cols:
        out[c] = out[c].map(lambda v: "" if pd.isna(v) else fmt.format(float(v)))
    return out


def month_label(m) -> str:
    m = pd.Timestamp(m)
    return f"{m.month:02d}.{m.year}"


def months_between(a: date, b: date) -> list:
    out, cur = [], date(a.year, a.month, 1)
    while cur <= b:
        out.append(cur)
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return out


def add_months(d: date, n: int) -> date:
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


# сервер живёт по UTC: с полуночи до 3 ночи по Киеву date.today() отдаёт вчерашнее число,
# и «по» в журнале отсекает сегодняшние правки, а первого числа CUR_MONTH остаётся прошлым месяцем
TODAY = datetime.now(ZoneInfo("Europe/Kyiv")).date()
CUR_MONTH = date(TODAY.year, TODAY.month, 1)


def load_objects() -> pd.DataFrame:
    mp = q("""SELECT 'marketplace' AS object_type, id AS object_id, code AS name, country_alpha2 AS country, platform_short AS platform
              FROM kabinet_data.v_marketplaces_selectable ORDER BY code""")
    pl = q("""SELECT 'pool' AS object_type, p.id AS object_id, p.name, MIN(m.country_alpha2) AS country, NULL::text AS platform
              FROM kabinet_data.pools p LEFT JOIN kabinet_data.pool_members pm ON pm.pool_id = p.id
                   AND pm.valid_from <= current_date AND (pm.valid_to IS NULL OR pm.valid_to >= current_date)
              LEFT JOIN kabinet_data.marketplaces_new m ON m.id = pm.marketplace_id GROUP BY p.id, p.name ORDER BY p.name""")
    return pd.concat([mp, pl], ignore_index=True)


def object_label(row) -> str:
    return f"{row['name']} ({_tr('pool')})" if row["object_type"] == "pool" else str(row["name"])


def pool_snapshot(pool_id: int) -> list:
    d = q("""SELECT marketplace_id FROM kabinet_data.pool_members WHERE pool_id = %s
             AND valid_from <= current_date AND (valid_to IS NULL OR valid_to >= current_date) ORDER BY 1""", (int(pool_id),))
    return [int(x) for x in d["marketplace_id"]]


def load_docs() -> pd.DataFrame:
    return q("""
        SELECT d.id, d.number, d.doc_date, d.object_type, d.object_id,
               COALESCE(m.code, p.name) AS object_name, d.first_month, d.last_month, d.completeness, d.status, d.comment,
               d.source, d.created_by, d.created_at, d.posted_by, d.posted_at, d.pool_snapshot, d.pool_snapshot_date,
               COUNT(DISTINCT r.sku) AS n_sku, COUNT(r.id) AS n_cells,
               COUNT(r.id) FILTER (WHERE r.quantity IS NOT NULL) AS n_filled,
               COUNT(r.id) FILTER (WHERE r.status = 'approved' OR (d.status = 'posted' AND r.status <> 'unapproved')) AS n_approved
        FROM kabinet_data.forecast_documents d
        LEFT JOIN kabinet_data.marketplaces_new m ON d.object_type = 'marketplace' AND m.id = d.object_id
        LEFT JOIN kabinet_data.pools p ON d.object_type = 'pool' AND p.id = d.object_id
        LEFT JOIN kabinet_data.forecast_register r ON r.document_id = d.id AND r.record_type = 'sales'
        GROUP BY d.id, m.code, p.name
        ORDER BY d.status = 'draft' DESC, d.created_at DESC""")


def load_rows(doc_id: int) -> pd.DataFrame:
    return q("""
        SELECT r.id, r.sku, r.month, r.quantity, r.status, r.target_price, r.line_comment, r.version, r.is_current,
               r.approved_by, r.approved_at, s.sku_type, s.name AS sku_name
        FROM kabinet_data.forecast_register r
        LEFT JOIN kabinet_data.sku_master s ON s.sku = r.sku
        WHERE r.document_id = %s AND r.record_type = 'sales'
        ORDER BY r.sku, r.month""", (int(doc_id),))


def admitted_skus(object_type: str, object_id: int, snapshot) -> tuple:
    """Продажные SKU действующей матрицы объекта (§12) и SKU с закрытым допуском (распродажа, §7).
    Marketplace — записи уровня marketplace; пул — хотя бы на одном marketplace сохранённого состава."""
    if object_type == "marketplace":
        ids = [int(object_id)]
    else:
        ids = [int(x) for x in (snapshot or [])] or pool_snapshot(object_id)
    if not ids:
        return set(), set()
    d = q("""SELECT sku, bool_or(removed_on IS NULL OR removed_on > current_date) AS active
             FROM kabinet_data.assortment_admissions
             WHERE level = 'marketplace' AND marketplace_id = ANY(%s) AND in_listing AND added_on <= current_date
             GROUP BY sku""", (ids,))
    active = set(d.loc[d["active"], "sku"])
    former = set(d.loc[~d["active"], "sku"]) - active
    return active, former


def sale_blocks(doc, skus, active: set, former: set) -> dict:
    """Актуальные ограничения продажи SKU по ТЗ 005 и 007 (ТЗ 010 §9): проверяются ПЕРЕД каждым
    утверждением и проведением, а не один раз при добавлении строки.

    Причина такая: допуск и ограничения живут своей жизнью — SKU могли деактивировать, а площадке
    выставить ограничение уже после того, как строка попала в черновик. Введённые значения при этом
    остаются: блокируется операция, а не работа человека (§9).

    Дата вывода SKU запретом НЕ считается: по §7 это распродажа по прежнему допуску, она разрешена.
    Отсутствие допуска в матрице — тоже не запрет: это §3 и §7, они проверяются при добавлении строки
    и полнотой «Полного» документа. Если считать его запретом, ломается живой процесс: загрузка листа
    планов приносит SKU, которых в матрице нет (в документе ITALY на 26.09 таких три), и проведение
    прогноза остановилось бы на данных, которые заводит не человек."""
    if not skus:
        return {}
    meta = q("""SELECT sku, is_active, COALESCE(ARRAY(SELECT jsonb_array_elements_text(restrictions)), '{}') AS restr
                FROM kabinet_data.sku_master WHERE sku = ANY(%s)""", (list(skus),))
    known = {r.sku: r for r in meta.itertuples()}
    # коды ограничений — площадка, код marketplace или страна покрытия (ТЗ 005 §6)
    if doc["object_type"] == "marketplace":
        ids = [int(doc["object_id"])]
    else:
        snap = doc.get("pool_snapshot")
        if isinstance(snap, str):
            snap = json.loads(snap)
        ids = [int(x) for x in (snap or [])] or pool_snapshot(int(doc["object_id"]))
    codes = set()
    if ids:
        mp = q("""SELECT platform_short, code, country_alpha2 FROM kabinet_data.marketplaces_new WHERE id = ANY(%s)""", (ids,))
        codes = set(mp["platform_short"]) | set(mp["code"]) | set(mp["country_alpha2"])
    out = {}
    for sku in skus:
        r = known.get(sku)
        if r is None:
            out[sku] = _tr("why_unknown")
        elif r.is_active is False:
            out[sku] = _tr("why_inactive")
        elif codes & set(r.restr or []):
            out[sku] = _tr("why_restricted")
    return out


def log(cur, doc_id, sku, month, field, old, new, source, actor):
    cur.execute("""INSERT INTO kabinet_data.forecast_change_log (document_id, sku, month, field, old_value, new_value, source, actor)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (int(doc_id), sku, month, field, None if old is None else str(old), None if new is None else str(new), source, actor))


def next_number(cur, object_name: str) -> str:
    base = f"FC-{TODAY:%Y%m%d}-{object_name.upper()}"
    cur.execute("SELECT count(*) FROM kabinet_data.forecast_documents WHERE number = %s OR number LIKE %s", (base, base + "-%"))
    n = cur.fetchone()[0]
    return base if n == 0 else f"{base}-{n + 1}"


# ═══════════════════════════════════════════════════════════════════════════
# ДЕЙСТВИЯ
# ═══════════════════════════════════════════════════════════════════════════

def create_document(obj, first: date, last: date, completeness: str, comment: str) -> str:
    actor = _actor()
    snap = pool_snapshot(obj["object_id"]) if obj["object_type"] == "pool" else None

    def _do(cur):
        no = next_number(cur, str(obj["name"]))
        cur.execute("""INSERT INTO kabinet_data.forecast_documents
                          (number, object_type, object_id, pool_snapshot, pool_snapshot_date, first_month, last_month,
                           completeness, status, comment, source, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s, 'manual', %s) RETURNING id""",
                    (no, obj["object_type"], int(obj["object_id"]), json.dumps(snap) if snap else None,
                     TODAY if snap else None, first, last, completeness, comment or None, actor))
        doc_id = cur.fetchone()[0]
        log(cur, doc_id, None, None, "document", None, f"created {no}", "manual", actor)
        return no
    return tx(_do)


def add_skus(doc, rows: pd.DataFrame, skus: list, active: set, former: set, known: set) -> tuple:
    """Сценарий 4: SKU есть в справочнике, есть допуск (действующий или прежний — распродажа), нет дубля."""
    actor = _actor()
    months = months_between(doc["first_month"], doc["last_month"])
    present = set(rows["sku"]) if not rows.empty else set()
    ok, rejected = [], []
    for s in skus:
        if s not in known:
            rejected.append(_trf("add_unknown", sku=s))
        elif s in present:
            rejected.append(_trf("add_dup", sku=s))
        elif s in active:
            ok.append((s, None))
        elif s in former:
            ok.append((s, "liquidation"))
            rejected.append(_trf("add_liquidation", sku=s))
        else:
            rejected.append(_trf("add_no_admission", sku=s))
    if ok:
        def _do(cur):
            for s, note in ok:
                for m in months:
                    cur.execute("""INSERT INTO kabinet_data.forecast_register
                                      (record_type, object_type, object_id, sku, month, quantity, version, status, is_current, document_id, line_comment, created_by)
                                   VALUES ('sales', %s, %s, %s, %s, NULL, 1, 'unapproved', FALSE, %s, %s, %s)""",
                                (doc["object_type"], int(doc["object_id"]), s, m, int(doc["id"]),
                                 "распродажа по прежнему допуску (§7)" if note else None, actor))
                log(cur, doc["id"], s, None, "row", None, "added" + (" (liquidation)" if note else ""), "manual", actor)
        tx(_do)
    return len(ok), rejected


def save_grid(doc, rows: pd.DataFrame, edited: pd.DataFrame, months: list) -> tuple:
    """Ручной ввод (§6, §11): пусто → NULL, 0 → 0; утверждённые и прошедшие месяцы не трогаем, ошибку показываем."""
    actor = _actor()
    by_key = {(r.sku, pd.Timestamp(r.month).date()): r for r in rows.itertuples()}
    changes, rejected = [], []
    for _, er in edited.iterrows():
        sku = er["sku"]
        for m in months:
            col = month_label(m)
            if col not in edited.columns:
                continue
            v = er.get(col)
            new = None if is_empty(v) else v
            old_r = by_key.get((sku, m))
            if old_r is None:
                continue
            old = None if pd.isna(old_r.quantity) else int(old_r.quantity)
            if new is not None:
                try:
                    fv = float(new)
                    if fv < 0 or fv != int(fv):
                        raise ValueError
                    new = int(fv)
                except (TypeError, ValueError):
                    rejected.append(_trf("rej_value", sku=sku, m=col))
                    continue
            if new == old:
                continue
            if m < CUR_MONTH:
                rejected.append(_trf("rej_past", sku=sku, m=col))
                continue
            if old_r.status == "approved":
                rejected.append(_trf("rej_approved", sku=sku, m=col))
                continue
            changes.append((old_r.id, sku, m, old, new))
    if changes:
        def _do(cur):
            for rid, sku, m, old, new in changes:
                cur.execute("UPDATE kabinet_data.forecast_register SET quantity = %s WHERE id = %s AND status = 'unapproved'", (new, int(rid)))
                log(cur, doc["id"], sku, m, "quantity", old, new, "manual", actor)
        tx(_do)
    return len(changes), rejected


# ═══════════════════════════════════════════════════════════════════════════
# ЗАГРУЗКА ИЗ ФАЙЛА И ИЗ GOOGLE ТАБЛИЦЫ (§11)
# ═══════════════════════════════════════════════════════════════════════════
# Строка источника — один SKU, значения прогноза — колонками по месяцам; объект прогноза берётся
# из документа, в источнике его не указывают. Загрузка кладёт значения в черновик и ничего не
# утверждает и не проводит — это отдельные действия ниже на карточке.
#
# Главное правило проверок: ошибка хотя бы в одной ячейке останавливает загрузку целиком, и человек
# получает протокол «SKU, месяц, что было в файле, почему отказ». Половина загруженного файла хуже
# незагруженного: по документу потом не понять, какие строки из источника, а какие остались прежними.

GS_SCOPE, GS_KEY = "kabinet-external", "google-sa-json"     # ключ сервисного аккаунта — в скоупе, не в коде
GS_AUTH = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


@st.cache_resource(show_spinner=False)
def _gs_client():
    """Клиент Google Таблиц. Ключ читаем из скоупа Databricks тем же принципалом, что и базу:
    копии в st.secrets нет намеренно — иначе ротация требует правки ещё и в Streamlit."""
    import gspread                                           # не в шапке: без листов страница обязана работать
    from google.oauth2.service_account import Credentials
    raw = base64.b64decode(get_workspace_client().secrets.get_secret(scope=GS_SCOPE, key=GS_KEY).value).decode()
    info = json.loads(raw, strict=False)                     # в ключе переводы строк внутри private_key
    return gspread.authorize(Credentials.from_service_account_info(info, scopes=GS_AUTH))


def gs_open(url: str):
    return _gs_client().open_by_url(url.strip())


def read_source(kind: str, handle, sheet: str) -> pd.DataFrame:
    """Лист целиком, без заголовков: какая строка заголовочная, решает человек (§11.2).
    Всё читаем как текст — иначе Excel отдаёт «08455000» числом 8455000.0 и SKU не сопоставится."""
    if kind == "gsheet":
        return pd.DataFrame(handle.worksheet(sheet).get_values()).astype(object)
    handle.seek(0)                                           # ExcelFile оставляет указатель в конце
    if str(getattr(handle, "name", "")).lower().endswith(".csv"):
        return pd.read_csv(handle, header=None, dtype=str, sep=None, engine="python", keep_default_na=False)
    return pd.read_excel(handle, sheet_name=sheet, header=None, dtype=object)


def source_sheets(kind: str, handle) -> list:
    if kind == "gsheet":
        return [w.title for w in handle.worksheets()]
    if str(getattr(handle, "name", "")).lower().endswith(".csv"):
        return ["CSV"]
    handle.seek(0)
    return pd.ExcelFile(handle).sheet_names


def header_and_body(raw: pd.DataFrame, header_row: int) -> tuple:
    """Заголовки — строка header_row (1-based), дальше данные. Пустые и повторяющиеся имена колонок
    получают номер: в источниках месяцы нередко подписаны одинаково («шт», «шт»)."""
    hdr = raw.iloc[header_row - 1]
    labels, seen = [], {}
    for i, v in enumerate(hdr):
        name = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()
        if isinstance(v, (datetime, date, pd.Timestamp)):
            name = month_label(v)
        name = name or f"{_tr('up_col_nameless')} {i + 1}"
        seen[name] = seen.get(name, 0) + 1
        labels.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    body = raw.iloc[header_row:].reset_index(drop=True)
    body.columns = labels
    return labels, body


def guess_month(label: str, months: list):
    """Месяц по подписи колонки: «11.2026», «2026-11», «ноя.26», дата — всё это встречается в
    присланных файлах. Что не разобралось — человек сопоставляет руками, молча не угадываем."""
    s = str(label).strip().lower()
    for m in months:
        if s in (month_label(m).lower(), f"{m.year}-{m.month:02d}", f"{m.month:02d}/{m.year}",
                 f"{m.month}.{m.year}", f"{m.year}{m.month:02d}"):
            return m
    digits = re.findall(r"\d+", s)
    if len(digits) >= 2:
        a, b = int(digits[0]), int(digits[1])
        for mm, yy in ((a, b), (b, a)):
            yy = yy + 2000 if yy < 100 else yy
            for m in months:
                if m.month == mm and m.year == yy:
                    return m
    return None


def match_sku(raw, known: set):
    """Артикул из ячейки. Excel теряет ведущий ноль и дописывает «.0», поэтому пробуем варианты:
    как есть, без дробной части, дополненный нулями до восьми знаков. Ничего не подошло — вернём
    текст как есть, и проверка скажет «нет в справочнике», а не подставит похожий код."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw).strip().upper()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    for cand in (s, s.zfill(8) if s.isdigit() else s, s.replace(" ", "")):
        if cand in known:
            return cand
    return s


def plan_upload(doc, rows: pd.DataFrame, body: pd.DataFrame, sku_col: str, mapping: dict,
                months: list, active: set, former: set, known: set) -> dict:
    """Протокол загрузки до записи (§11.3–11.4): что изменится, что заменится и что не так.

    Пустая ячейка источника ничего не меняет — это не команда обнулить: явный 0 означает «продаж не
    планируем», пустота означает «не сказано». Значения, совпавшие с документом, в изменения не
    попадают, иначе журнал заполнялся бы строками без содержания."""
    by_key = {(r.sku, pd.Timestamp(r.month).date()): r for r in rows.itertuples()}
    present = set(rows["sku"]) if not rows.empty else set()
    errors, changes, replaces, adds, seen = [], [], [], {}, set()
    for _, sr in body.iterrows():
        sku = match_sku(sr.get(sku_col), known)
        if not sku:
            continue                                  # пустая строка источника — не ошибка, а конец данных
        new_sku = sku not in present
        if new_sku and sku not in known:
            errors.append(_trf("up_err_unknown", sku=sku))
            continue
        if new_sku and sku not in active and sku not in former:
            errors.append(_trf("up_err_admission", sku=sku))
            continue
        for col, m in mapping.items():
            if m is None or col not in body.columns:
                continue
            cell = sr.get(col)
            if is_empty(cell):
                continue                              # §11.4: пустота не меняет и не обнуляет
            if (sku, m) in seen:
                errors.append(_trf("up_err_dup", sku=sku, m=month_label(m)))
                continue
            seen.add((sku, m))
            txt = str(cell).strip().replace(" ", "").replace(" ", "").replace(",", ".")
            try:
                val = float(txt)
                if val < 0 or val != int(val):
                    raise ValueError
                val = int(val)
            except (TypeError, ValueError):
                errors.append(_trf("up_err_value", sku=sku, m=month_label(m), v=str(cell)[:20]))
                continue
            cur = by_key.get((sku, m))
            old = None if cur is None or pd.isna(cur.quantity) else int(cur.quantity)
            if old == val:
                continue                              # совпало — не изменение
            if cur is not None and cur.status == "approved":
                errors.append(_trf("up_err_approved", sku=sku, m=month_label(m)))
                continue
            if m < CUR_MONTH:
                errors.append(_trf("up_err_past", sku=sku, m=month_label(m)))
                continue
            if new_sku:
                adds.setdefault(sku, {})[m] = val
            else:
                changes.append((cur.id, sku, m, old, val))
                if old is not None:
                    replaces.append((sku, month_label(m), old, val))
    return {"errors": errors, "changes": changes, "replaces": replaces, "adds": adds,
            "skus": len({c[1] for c in changes} | set(adds)),
            "values": len(changes) + sum(len(v) for v in adds.values())}


def apply_upload(doc, plan: dict, months: list, former: set, source: str) -> tuple:
    """Одна транзакция: новые строки SKU и значения. Журнал получает источник загрузки — иначе
    через месяц не отличить правку руками от загруженной."""
    actor = _actor()

    def _do(cur):
        for sku, vals in plan["adds"].items():
            for m in months:
                v = vals.get(m)
                cur.execute("""INSERT INTO kabinet_data.forecast_register
                                  (record_type, object_type, object_id, sku, month, quantity, version,
                                   status, is_current, document_id, line_comment, created_by)
                               VALUES ('sales', %s, %s, %s, %s, %s, 1, 'unapproved', FALSE, %s, %s, %s)""",
                            (doc["object_type"], int(doc["object_id"]), sku, m, v, int(doc["id"]),
                             _tr("liq_note") if sku in former else None, actor))
            log(cur, doc["id"], sku, None, "row", None, "added", source, actor)
            for m, v in sorted(vals.items()):
                log(cur, doc["id"], sku, m, "quantity", None, v, source, actor)
        for rid, sku, m, old, new in plan["changes"]:
            cur.execute("""UPDATE kabinet_data.forecast_register SET quantity = %s
                           WHERE id = %s AND status = 'unapproved'""", (new, int(rid)))
            log(cur, doc["id"], sku, m, "quantity", old, new, source, actor)
    tx(_do)
    return plan["values"], len(plan["adds"])


def save_prices(doc, rows: pd.DataFrame, edited: pd.DataFrame, months: list) -> int:
    actor = _actor()
    by_key = {(r.sku, pd.Timestamp(r.month).date()): r for r in rows.itertuples()}
    changes = []
    for _, er in edited.iterrows():
        for m in months:
            if m < CUR_MONTH or month_label(m) not in edited.columns:
                continue
            v = er.get(month_label(m))
            new = None if is_empty(v) else round(float(v), 4)
            r = by_key.get((er["sku"], m))
            if r is None:
                continue
            old = None if pd.isna(r.target_price) else round(float(r.target_price), 4)
            if new != old:
                changes.append((r.id, er["sku"], m, old, new))
    if changes:
        def _do(cur):
            for rid, sku, m, old, new in changes:
                cur.execute("UPDATE kabinet_data.forecast_register SET target_price = %s WHERE id = %s", (new, int(rid)))
                log(cur, doc["id"], sku, m, "target_price", old, new, "manual", actor)
        tx(_do)
    return len(changes)


def _cells(rows: pd.DataFrame, skus, months) -> pd.DataFrame:
    sel = rows[rows["month"].apply(lambda x: pd.Timestamp(x).date()).isin(months)]
    if skus:
        sel = sel[sel["sku"].isin(skus)]
    return sel


def approve(doc, rows, skus, months, active: set = None, former: set = None) -> tuple:
    """Сценарий 6: утверждаем только заполненные ячейки выбранных SKU × месяцев; пустые показываем и не утверждаем.
    Плюс §9: перед утверждением перепроверяем актуальные ограничения продажи SKU."""
    actor = _actor()
    sel = _cells(rows, skus, [m for m in months if m >= CUR_MONTH])
    sel = sel[sel["status"] == "unapproved"]
    blocked = sale_blocks(doc, sorted(set(sel["sku"])), active or set(), former or set()) if len(sel) else {}
    stopped = [_trf("rej_restricted", sku=r.sku, m=month_label(r.month), why=blocked[r.sku])
               for r in sel.itertuples() if r.sku in blocked]
    if blocked:
        sel = sel[~sel["sku"].isin(blocked)]
    empty = sel[sel["quantity"].isna()]
    empties = [f"{r.sku} · {month_label(r.month)}" for r in empty.itertuples()]
    # пустые не утверждаются и перечисляются (сценарий 6), но заполненные из того же выбора — утверждаются:
    # до 20.09 при первой же пустой ячейке функция выходила с нулём, а сообщение читалось как «остальные прошли»
    sel = sel[sel["quantity"].notna()]
    empties += stopped
    if sel.empty:
        return 0, empties
    def _do(cur):
        for r in sel.itertuples():
            cur.execute("""UPDATE kabinet_data.forecast_register SET status = 'approved', approved_by = %s, approved_at = now()
                           WHERE id = %s AND status = 'unapproved' AND quantity IS NOT NULL""", (actor, int(r.id)))
            log(cur, doc["id"], r.sku, pd.Timestamp(r.month).date(), "approval", "unapproved", "approved", "approve", actor)
    tx(_do)
    return len(sel), empties


def unapprove(doc, rows, skus, months) -> int:
    """Сценарий 19: только черновик, только текущие и будущие месяцы; пользователь и дата — в записи и в журнале."""
    actor = _actor()
    sel = _cells(rows, skus, [m for m in months if m >= CUR_MONTH])
    sel = sel[sel["status"] == "approved"]
    if sel.empty:
        return 0
    def _do(cur):
        for r in sel.itertuples():
            cur.execute("""UPDATE kabinet_data.forecast_register SET status = 'unapproved', unapproved_by = %s, unapproved_at = now()
                           WHERE id = %s AND status = 'approved'""", (actor, int(r.id)))
            log(cur, doc["id"], r.sku, pd.Timestamp(r.month).date(), "approval", "approved", "unapproved", "unapprove", actor)
    tx(_do)
    return len(sel)


def fill_zeros(doc, rows) -> int:
    actor = _actor()
    sel = rows[(rows["quantity"].isna()) & (rows["status"] == "unapproved")
               & (rows["month"].apply(lambda x: pd.Timestamp(x).date()) >= CUR_MONTH)]
    if sel.empty:
        return 0
    def _do(cur):
        for r in sel.itertuples():
            cur.execute("UPDATE kabinet_data.forecast_register SET quantity = 0 WHERE id = %s AND quantity IS NULL", (int(r.id),))
            log(cur, doc["id"], r.sku, pd.Timestamp(r.month).date(), "quantity", None, 0, "manual:fill_zeros", actor)
    tx(_do)
    return len(sel)


def delete_rows(doc, rows, skus) -> int:
    """Сценарий 18: физически удаляем только строки черновика без утверждённых значений — они ещё не история."""
    actor = _actor()
    sel = rows[rows["sku"].isin(skus)]
    if sel.empty:
        return 0
    def _do(cur):
        cur.execute("""DELETE FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales'
                       AND sku = ANY(%s) AND status = 'unapproved' AND NOT is_current""", (int(doc["id"]), list(skus)))
        for s in skus:
            log(cur, doc["id"], s, None, "row", "present", "deleted", "manual", actor)
    tx(_do)
    return len(set(sel["sku"]))


def save_header(doc, first, last, completeness, comment, locked: bool) -> None:
    actor = _actor()
    def _do(cur):
        if locked:
            cur.execute("UPDATE kabinet_data.forecast_documents SET completeness = %s, comment = %s WHERE id = %s AND status = 'draft'",
                        (completeness, comment or None, int(doc["id"])))
        else:
            cur.execute("""UPDATE kabinet_data.forecast_documents SET first_month = %s, last_month = %s, completeness = %s, comment = %s
                           WHERE id = %s AND status = 'draft'""", (first, last, completeness, comment or None, int(doc["id"])))
            # период изменился — строки документа приводим к новому набору месяцев (пустые ячейки добавляем, лишние неутверждённые убираем)
            months = months_between(first, last)
            cur.execute("SELECT DISTINCT sku FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales'", (int(doc["id"]),))
            skus = [r[0] for r in cur.fetchall()]
            cur.execute("""DELETE FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales'
                           AND status = 'unapproved' AND NOT is_current AND NOT (month = ANY(%s))""", (int(doc["id"]), months))
            for s in skus:
                for m in months:
                    cur.execute("""INSERT INTO kabinet_data.forecast_register (record_type, object_type, object_id, sku, month, quantity, version, status, is_current, document_id, created_by)
                                   SELECT 'sales', %s, %s, %s, %s, NULL, 1, 'unapproved', FALSE, %s, %s
                                   WHERE NOT EXISTS (SELECT 1 FROM kabinet_data.forecast_register WHERE document_id = %s AND record_type = 'sales' AND sku = %s AND month = %s)""",
                                (doc["object_type"], int(doc["object_id"]), s, m, int(doc["id"]), actor, int(doc["id"]), s, m))
        log(cur, doc["id"], None, None, "header", None, f"{first:%Y-%m}..{last:%Y-%m} {completeness}", "manual", actor)
    tx(_do)


def post_checks(doc, rows: pd.DataFrame, active_matrix: set, former_matrix: set = None) -> list:
    """Сценарий 8 + 17: всё заполнено и утверждено, прошедших месяцев нет, для полного — состав матрицы."""
    problems = []
    if rows.empty:
        problems.append(_tr("post_no_rows"))
        return problems
    empty = rows[rows["quantity"].isna()]
    if len(empty):
        cells = ", ".join(f"{r.sku} · {month_label(r.month)}" for r in empty.head(8).itertuples()) + ("…" if len(empty) > 8 else "")
        problems.append(_trf("post_empty", n=len(empty), cells=cells))
    un = rows[(rows["status"] != "approved")]
    if len(un):
        cells = ", ".join(f"{r.sku} · {month_label(r.month)}" for r in un.head(8).itertuples()) + ("…" if len(un) > 8 else "")
        problems.append(_trf("post_unapproved", n=len(un), cells=cells))
    past = sorted({pd.Timestamp(m).date() for m in rows["month"] if pd.Timestamp(m).date() < CUR_MONTH})
    if past:
        problems.append(_trf("post_past", months=", ".join(month_label(m) for m in past)))
    if doc["completeness"] == "full":
        missing = sorted(active_matrix - set(rows["sku"]))
        if missing:
            problems.append(_trf("post_missing", n=len(missing), skus=", ".join(missing[:12]) + ("…" if len(missing) > 12 else "")))
    # §9: ограничения продажи перепроверяются и перед проведением, а не только при добавлении строки
    blocked = sale_blocks(doc, sorted(set(rows["sku"])), active_matrix, former_matrix or set())
    if blocked:
        problems.append(_trf("post_restricted",
                             skus=", ".join(f"{k} ({v})" for k, v in sorted(blocked.items())[:8])
                                  + ("…" if len(blocked) > 8 else "")))
    return problems


def post_document(doc, rows: pd.DataFrame) -> tuple:
    """Сценарий 20: заменяем записи, действующие на момент проведения; ссылки в обе стороны; дата проведения — дата изменения."""
    actor = _actor()
    def _do(cur):
        cur.execute("SELECT status FROM kabinet_data.forecast_documents WHERE id = %s FOR UPDATE", (int(doc["id"]),))
        if cur.fetchone()[0] != "draft":
            raise RuntimeError("document is not a draft")
        n_cur = n_rep = 0
        for r in rows.itertuples():
            m = pd.Timestamp(r.month).date()
            cur.execute("""SELECT id, version FROM kabinet_data.forecast_register
                           WHERE record_type = 'sales' AND object_type = %s AND object_id = %s AND sku = %s AND month = %s AND is_current
                           FOR UPDATE""", (doc["object_type"], int(doc["object_id"]), r.sku, m))
            old = cur.fetchone()
            if old:
                cur.execute("""UPDATE kabinet_data.forecast_register SET is_current = FALSE, status = 'superseded', superseded_at = now(),
                               replaced_by = array_append(replaced_by, %s) WHERE id = %s""", (int(r.id), int(old[0])))
                n_rep += 1
                # ТЗ 011 §7: замена прогноза немедленно выключает его зависимые результаты — независимо от того,
                # получится ли новый расчёт. Пока нового нет, потребность неизвестна, и это честнее старого числа.
                cur.execute("""UPDATE kabinet_data.forecast_register
                                  SET is_current = FALSE, calculation_status = 'SUPERSEDED', superseded_at = now(), changed_at = now()
                                WHERE record_type = 'dependent' AND is_current AND source_forecast_id = %s""", (int(old[0]),))
            cur.execute("""UPDATE kabinet_data.forecast_register SET is_current = TRUE, version = %s, replaces = %s, changed_at = now()
                           WHERE id = %s AND status = 'approved' AND quantity IS NOT NULL""",
                        ((old[1] + 1) if old else 1, [int(old[0])] if old else [], int(r.id)))
            n_cur += 1
        cur.execute("""UPDATE kabinet_data.forecast_documents SET status = 'posted', posted_by = %s, posted_at = now() WHERE id = %s""",
                    (actor, int(doc["id"])))
        log(cur, doc["id"], None, None, "document", "draft", "posted", "post", actor)
        # ТЗ 011 §11: состав наборов фиксируется на момент проведения. Справочник собирает загрузчик из Odoo,
        # и его правка не должна менять числа уже проведённого прогноза при следующем пересчёте.
        cur.execute("""INSERT INTO kabinet_data.forecast_composition_snapshot (document_id, composite_sku, base_sku, quantity)
                       SELECT %s, c.composite_sku, c.base_sku, c.quantity
                       FROM kabinet_data.sku_composition c
                       JOIN kabinet_data.sku_master m ON m.sku = c.composite_sku AND m.sku_type = 'composite'
                       WHERE c.composite_sku = ANY(%s)
                       ON CONFLICT DO NOTHING""", (int(doc["id"]), list(rows["sku"].astype(str))))
        # ТЗ 011 §7: зависимая потребность пересчитывается сразу после проведения и в той же транзакции —
        # иначе между двумя коммитами читатель видит новый прогноз набора и зависимые строки от старого.
        # Точка сохранения: сбой расчёта не должен отменять проведение (бизнес-действие сделано и проверено),
        # но и молчать о нём нельзя — текст ошибки возвращается на экран, а ночная джоба повторит расчёт.
        dd, dd_err = (0, 0, 0, 0), None
        cur.execute("SAVEPOINT dd")
        try:
            cur.execute("SELECT calculated, errors, superseded, touched FROM kabinet_data.dependent_demand_rebuild(%s, %s)",
                        (doc["object_type"], int(doc["object_id"])))
            dd = cur.fetchone() or (0, 0, 0, 0)
            cur.execute("RELEASE SAVEPOINT dd")
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT dd")
            dd_err = str(e).strip().splitlines()[0]
        return n_cur, n_rep, dd, dd_err
    return tx(_do)


# ═══════════════════════════════════════════════════════════════════════════
# ИЗМЕНЕНИЕ СОСТАВА ПУЛА: ПЕРЕСОЗДАНИЕ И ОБЩАЯ ЗАМЕНА (§12, §21)
# ═══════════════════════════════════════════════════════════════════════════
# Само изменение состава пула ничего не переключает: до общей замены отчёты и обеспечение живут на
# прежних прогнозах и сохранённом в них составе. Вышедший маркетплейс продолжает считаться в
# прогнозе пула, а добавленный прежним прогнозом пула не покрывается — у него свой, если он есть.
#
# Индикатор «Требуется пересоздание» не хранится, а считается вью `v_forecast_pool_drift`
# (сравнение сохранённого в документе состава с действующим) — почему именно так, написано в
# `sql/forecast_pool_replacement_2026-09-26.sql`.


def pool_drift() -> pd.DataFrame:
    """Документы пулов, чей сохранённый состав разошёлся с действующим. Не кешируем: вью читает
    десяток строк, а устаревший на минуту индикатор после замены смущал бы сильнее."""
    return q("""SELECT document_id, number, pool_id, pool_name, snapshot_ids, current_ids,
                       added_ids, removed_ids, disbanded, rows_ahead, first_month_ahead
                FROM kabinet_data.v_forecast_pool_drift ORDER BY pool_id, document_id""")


@st.cache_data(ttl=300, show_spinner=False)
def mp_meta() -> pd.DataFrame:
    return q("SELECT id, code, is_active FROM kabinet_data.marketplaces_new")


def mp_name(mp) -> str:
    d = mp_meta()
    hit = d[d["id"] == int(mp)]
    return str(hit.iloc[0]["code"]) if len(hit) else str(mp)


def mp_is_active(mp) -> bool:
    d = mp_meta()
    hit = d[d["id"] == int(mp)]
    return bool(hit.iloc[0]["is_active"]) if len(hit) else True


def _ids(v) -> set:
    return {int(x) for x in (v if v is not None else [])}


def drift_marketplaces(drift: pd.DataFrame) -> set:
    """Маркетплейсы, затронутые изменением состава: и вышедшие, и добавленные."""
    out = set()
    for r in drift.itertuples():
        out |= _ids(r.added_ids) | _ids(r.removed_ids)
    return out


def drift_text(r) -> str:
    """Что изменилось — словами: и для индикатора, и как заготовка причины операции."""
    parts = []
    if r.disbanded:
        parts.append(_tr("drift_disbanded"))
    if len(r.removed_ids or []):
        parts.append(_trf("drift_removed", mps=", ".join(mp_name(x) for x in r.removed_ids)))
    if len(r.added_ids or []):
        parts.append(_trf("drift_added", mps=", ".join(mp_name(x) for x in r.added_ids)))
    return "; ".join(parts)


def blocked_by_drift(doc, drift: pd.DataFrame) -> str:
    """§21: обычное проведение документа, который переключил бы источник покрытия затронутых
    маркетплейсов, запрещено — такой документ вводится в действие только общей заменой.

    Проверка одна и та же для сценария 8 (обычное проведение) и 20 (последовательная замена):
    отдельное проведение не должно обходить общую замену, иначе один и тот же маркетплейс за те же
    SKU и месяцы окажется разом и в прежнем прогнозе пула, и в новом."""
    if drift.empty:
        return ""
    if doc["object_type"] == "pool":
        hit = drift[drift["pool_id"] == int(doc["object_id"])]
        if len(hit):
            return _trf("drift_block_pool", pool=hit.iloc[0]["pool_name"])
        return ""
    mp = int(doc["object_id"])
    pools = sorted({r.pool_name for r in drift.itertuples() if mp in _ids(r.added_ids) | _ids(r.removed_ids)})
    if pools:
        return _trf("drift_block_mp", pools=", ".join(pools))
    # участник пула, состав которого поменялся: его покрытие переключается той же общей заменой
    still = q("""SELECT DISTINCT p.name FROM kabinet_data.pool_members m
                 JOIN kabinet_data.pools p ON p.id = m.pool_id
                 WHERE m.marketplace_id = %s AND m.valid_from <= current_date
                   AND (m.valid_to IS NULL OR m.valid_to > current_date) AND m.pool_id = ANY(%s)""",
              (mp, [int(x) for x in drift["pool_id"]]))
    return _trf("drift_block_member", pools=", ".join(still["name"])) if len(still) else ""


def object_drafts(object_type: str, object_id: int) -> pd.DataFrame:
    return q("""SELECT id, number, comment FROM kabinet_data.forecast_documents
                WHERE status = 'draft' AND object_type = %s AND object_id = %s ORDER BY id DESC""",
             (object_type, int(object_id)))


def old_records(object_type: str, object_id: int) -> pd.DataFrame:
    """Действующие записи объекта за текущий и будущие месяцы — заменяются только они.
    Прошедшие месяцы и сохранённый для них состав пула этой операцией не меняются (§21)."""
    d = q("""SELECT id, sku, month, document_id, version FROM kabinet_data.forecast_register
             WHERE record_type = 'sales' AND is_current AND object_type = %s AND object_id = %s
               AND month >= date_trunc('month', current_date)""", (object_type, int(object_id)))
    if not d.empty:
        d["month"] = pd.to_datetime(d["month"]).dt.date
    return d


def replacement_plan(drift_row, picks: dict, terminations: dict) -> dict:
    """Собрать и проверить общую замену до записи (§21). `picks` — объект → id подготовленного
    черновика, `terminations` — маркетплейс → причина прекращения."""
    pool_id = int(drift_row.pool_id)
    snapshot, current = _ids(drift_row.snapshot_ids), _ids(drift_row.current_ids)
    removed, added = sorted(snapshot - current), sorted(current - snapshot)
    problems, docs = [], {}

    # 1. Выбранные документы: черновик, с причиной в комментарии (§12), прошедший проверки проведения
    for (otype, oid), did in picks.items():
        if not did:
            continue
        d = q("""SELECT id, number, object_type, object_id, status, comment, completeness,
                        first_month, last_month, pool_snapshot
                 FROM kabinet_data.forecast_documents WHERE id = %s""", (int(did),))
        if d.empty:
            problems.append(_trf("repl_no_doc", d=did)); continue
        d = d.iloc[0]
        if d["status"] != "draft":
            problems.append(_trf("repl_not_draft", n=d["number"])); continue
        if not str(d["comment"] or "").strip():
            problems.append(_trf("repl_no_comment", n=d["number"]))
        if d["object_type"] == "pool":
            snap = _ids(json.loads(d["pool_snapshot"]) if isinstance(d["pool_snapshot"], str) else d["pool_snapshot"])
            if snap != current:
                # документ, созданный до изменения состава, замену не закрывает: в нём прежний состав
                problems.append(_trf("repl_stale_snapshot", n=d["number"],
                                     was=", ".join(mp_name(x) for x in sorted(snap)) or "—",
                                     now=", ".join(mp_name(x) for x in sorted(current)) or "—"))
        rows = load_rows(int(did))
        if rows.empty:
            problems.append(_trf("repl_doc_empty", n=d["number"])); continue
        rows["month"] = pd.to_datetime(rows["month"]).dt.date
        act, former = admitted_skus(d["object_type"], int(d["object_id"]), d["pool_snapshot"])
        problems += [f"{d['number']}: {p}" for p in post_checks(d.to_dict(), rows, act, former)]
        docs[(d["object_type"], int(d["object_id"]))] = (d, rows)

    # 2. Все продолжающие работу затронутые маркетплейсы обеспечены новым прогнозом (§21);
    #    деактивированному новый прогноз не нужен, нужна причина прекращения
    member_of = {}
    if removed:
        mem = q("""SELECT marketplace_id, pool_id FROM kabinet_data.pool_members
                   WHERE marketplace_id = ANY(%s) AND valid_from <= current_date
                     AND (valid_to IS NULL OR valid_to > current_date)""", (removed,))
        member_of = {int(r.marketplace_id): int(r.pool_id) for r in mem.itertuples()}
    for mp in removed:
        if not mp_is_active(mp):
            if not str(terminations.get(mp, "")).strip():
                problems.append(_trf("repl_need_reason", mp=mp_name(mp)))
        elif ("marketplace", mp) not in docs and ("pool", member_of.get(mp, -1)) not in docs:
            problems.append(_trf("repl_need_doc", mp=mp_name(mp)))

    # 3. Один и тот же маркетплейс не считается дважды — и в новом прогнозе пула, и в своём (§21)
    if ("pool", pool_id) in docs:
        for otype, oid in docs:
            if otype == "marketplace" and oid in current:
                problems.append(_trf("repl_double", mp=mp_name(oid), n=docs[("pool", pool_id)][0]["number"]))

    # 4. Что заменяется: прогноз пула, прогнозы добавленных маркетплейсов (иначе двойной учёт рядом
    #    с новым прогнозом пула) и прогнозы объектов, для которых заведён новый документ
    new_cells, new_ids = {}, {}
    for (otype, oid), (d, rows) in docs.items():
        for r in rows.itertuples():
            new_cells.setdefault((r.sku, r.month), []).append(int(r.id))
    replace_objs = {("pool", pool_id)} | {("marketplace", mp) for mp in added} | set(docs)
    supersede, terminate = [], []
    for otype, oid in sorted(replace_objs):
        for r in old_records(otype, oid).itertuples():
            item = (otype, oid, int(r.id), r.sku, r.month, int(r.version or 1), int(r.document_id or 0))
            (supersede if (r.sku, r.month) in new_cells else terminate).append(item)
    if terminate and not any(str(v).strip() for v in terminations.values()):
        cells = ", ".join(f"{s} · {month_label(m)}" for _, _, _, s, m, _, _ in terminate[:8])
        problems.append(_trf("repl_uncovered", n=len(terminate), cells=cells + ("…" if len(terminate) > 8 else "")))
    return {"problems": problems, "docs": docs, "supersede": supersede, "terminate": terminate,
            "new_cells": new_cells, "removed": removed, "added": added, "current": sorted(current),
            "summary": drift_text(drift_row)}


def execute_replacement(drift_row, plan: dict, reason: str, terminations: dict) -> dict:
    """§21: одна транзакция на всё. Либо все новые документы проведены и прежние записи стали
    историческими, либо не введён в действие ни один — с отметкой «Требуется пересоздание» на
    прежнем прогнозе. Промежуточного состояния быть не должно: в нём один и тот же маркетплейс
    считался бы и в старом прогнозе, и в новом."""
    actor, pool_id = _actor(), int(drift_row.pool_id)

    def _do(cur):
        # состав мог измениться, пока человек заполнял форму — перечитываем перед записью
        cur.execute("""SELECT ARRAY(SELECT DISTINCT marketplace_id FROM kabinet_data.pool_members
                         WHERE pool_id = %s AND valid_from <= current_date
                           AND (valid_to IS NULL OR valid_to > current_date) ORDER BY 1)""", (pool_id,))
        if set(cur.fetchone()[0] or []) != set(plan["current"]):
            raise RuntimeError(_tr("repl_race"))
        cur.execute("""INSERT INTO kabinet_data.forecast_replacements (pool_id, reason, change_summary, actor)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (pool_id, reason.strip(), plan["summary"], actor))
        op_id = int(cur.fetchone()[0])
        n_docs = n_sup = n_term = 0

        # 1. Прежние записи снимаем ПЕРВЫМИ. Порядок здесь не вкусовой: частичный уникальный индекс
        #    держит одну действующую запись на объект × SKU × месяц, и если сначала сделать
        #    действующими новые, замена прогноза пула новым прогнозом того же пула упадёт на
        #    нарушении уникальности. Ссылки в обе стороны: старая знает, чем заменена, новая — что
        #    заменила (§21, история).
        for otype, oid, rid, sku, m, ver, doc_id in plan["supersede"]:
            new_ids = plan["new_cells"].get((sku, m), [])
            cur.execute("""UPDATE kabinet_data.forecast_register
                              SET is_current = FALSE, status = 'superseded', superseded_at = now(),
                                  replaced_by = coalesce(replaced_by, '{}') || %s::bigint[]
                            WHERE id = %s AND is_current""", (new_ids, int(rid)))
            n_sup += cur.rowcount
            for nid in new_ids:
                cur.execute("""UPDATE kabinet_data.forecast_register
                                  SET replaces = coalesce(replaces, '{}') || %s::bigint[], version = %s
                                WHERE id = %s""", ([int(rid)], ver + 1, int(nid)))
            # ТЗ 011: зависимые результаты заменённого прогноза выключаются сразу
            cur.execute("""UPDATE kabinet_data.forecast_register
                              SET is_current = FALSE, calculation_status = 'SUPERSEDED',
                                  superseded_at = now(), changed_at = now()
                            WHERE record_type = 'dependent' AND is_current AND source_forecast_id = %s""", (int(rid),))

        # 2. Прекращение без нового прогноза — для деактивированного маркетплейса (§21): ссылки на
        #    несуществующий документ не требуется, требуются причина и связь с операцией
        why = "; ".join(f"{mp_name(mp)}: {str(txt).strip()}" for mp, txt in terminations.items() if str(txt).strip())
        touched_docs = set()
        for otype, oid, rid, sku, m, ver, doc_id in plan["terminate"]:
            cur.execute("""UPDATE kabinet_data.forecast_register
                              SET is_current = FALSE, status = 'superseded', superseded_at = now()
                            WHERE id = %s AND is_current""", (int(rid),))
            n_term += cur.rowcount
            cur.execute("""UPDATE kabinet_data.forecast_register
                              SET is_current = FALSE, calculation_status = 'SUPERSEDED',
                                  superseded_at = now(), changed_at = now()
                            WHERE record_type = 'dependent' AND is_current AND source_forecast_id = %s""", (int(rid),))
            touched_docs.add(doc_id)
        for doc_id in sorted(x for x in touched_docs if x):
            log(cur, doc_id, None, None, "termination", "current", why or reason.strip(), f"replace:{op_id}", actor)
        # причину пишем только если прекращать действительно было что: иначе в составе операции
        # осталась бы строка «прекращено» на ноль записей — читалось бы как потеря прогноза
        for mp, txt in (terminations.items() if plan["terminate"] else ()):
            if str(txt).strip():
                cur.execute("""INSERT INTO kabinet_data.forecast_replacement_items
                                 (replacement_id, kind, object_type, object_id, marketplace_id,
                                  termination_reason, rows_affected)
                               VALUES (%s, 'termination', 'marketplace', %s, %s, %s, %s)""",
                            (op_id, int(mp), int(mp), str(txt).strip(), n_term))

        # 3. И только теперь вводим в действие новые документы — все сразу, как требует §21
        for (otype, oid), (d, rows) in plan["docs"].items():
            cur.execute("SELECT status FROM kabinet_data.forecast_documents WHERE id = %s FOR UPDATE", (int(d["id"]),))
            if cur.fetchone()[0] != "draft":
                raise RuntimeError(_trf("repl_not_draft", n=d["number"]))
            for r in rows.itertuples():
                cur.execute("""UPDATE kabinet_data.forecast_register SET is_current = TRUE, changed_at = now()
                               WHERE id = %s AND status = 'approved' AND quantity IS NOT NULL""", (int(r.id),))
            cur.execute("""UPDATE kabinet_data.forecast_documents
                              SET status = 'posted', posted_by = %s, posted_at = now(), replacement_op_id = %s
                            WHERE id = %s""", (actor, str(op_id), int(d["id"])))
            log(cur, int(d["id"]), None, None, "document", "draft", "posted", f"replace:{op_id}", actor)
            # ТЗ 011 §11: состав наборов фиксируется на момент проведения
            cur.execute("""INSERT INTO kabinet_data.forecast_composition_snapshot (document_id, composite_sku, base_sku, quantity)
                           SELECT %s, c.composite_sku, c.base_sku, c.quantity
                           FROM kabinet_data.sku_composition c
                           JOIN kabinet_data.sku_master m ON m.sku = c.composite_sku AND m.sku_type = 'composite'
                           WHERE c.composite_sku = ANY(%s) ON CONFLICT DO NOTHING""",
                        (int(d["id"]), list(rows["sku"].astype(str))))
            cur.execute("""INSERT INTO kabinet_data.forecast_replacement_items
                             (replacement_id, kind, object_type, object_id, new_document_id, rows_affected)
                           VALUES (%s, 'document', %s, %s, %s, %s)""",
                        (op_id, otype, int(oid), int(d["id"]), len(rows)))
            n_docs += 1

        cur.execute("""UPDATE kabinet_data.forecast_replacements
                          SET documents = %s, superseded_rows = %s, terminated_rows = %s WHERE id = %s""",
                    (n_docs, n_sup, n_term, op_id))

        # 4. Зависимая потребность — по каждому объекту операции, на точке сохранения: сбой расчёта
        #    не отменяет замену (бизнес-действие сделано и проверено), но и молчать о нём нельзя
        dd_err = []
        for otype, oid in sorted(set(plan["docs"]) | {("pool", pool_id)}):
            cur.execute("SAVEPOINT dd")
            try:
                cur.execute("SELECT calculated, errors FROM kabinet_data.dependent_demand_rebuild(%s, %s)",
                            (otype, int(oid)))
                cur.fetchone()
                cur.execute("RELEASE SAVEPOINT dd")
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT dd")
                dd_err.append(str(e).strip().splitlines()[0])
        return {"op_id": op_id, "docs": n_docs, "superseded": n_sup, "terminated": n_term, "dd_err": dd_err}
    return tx(_do)


def flash(kind: str, text: str) -> None:
    """Сообщение после действия: st.rerun() стирает всё, что нарисовано до него, поэтому кладём в session_state
    и показываем при следующем прогоне над карточкой."""
    st.session_state.setdefault("fc_flash", []).append((kind, text))


def show_flash(consume: bool = True) -> None:
    """Кнопки действий внизу длинной карточки, баннер рисовался только над ней: Streamlit сохраняет
    прокрутку, и после «Провести» подтверждение оставалось за экраном. Показываем в обоих местах."""
    for kind, text in st.session_state.get("fc_flash", []):
        getattr(st, kind, st.info)(text)
    if consume:
        st.session_state.pop("fc_flash", None)


# ═══════════════════════════════════════════════════════════════════════════
# ЭКРАН
# ═══════════════════════════════════════════════════════════════════════════

st.title(_tr("title"))
st.caption(_tr("caption"))

try:
    objects = load_objects()
    docs = load_docs()
except Exception as e:
    st.error(_trf("err_read", e=e))
    st.stop()

obj_labels = {f"{r['object_type']}:{r['object_id']}": object_label(r) for _, r in objects.iterrows()}
tab_docs, tab_new, tab_repl, tab_log = st.tabs(
    [_tr("tab_docs"), _tr("tab_new"), _tr("tab_repl"), _tr("tab_log")])

# ───────────────────────────── новый документ ─────────────────────────────
with tab_new:
    c1, c2 = st.columns(2)
    otype = c1.radio(_tr("new_object_type"), ["marketplace", "pool"], format_func=lambda x: _tr("mp") if x == "marketplace" else _tr("pool"),
                     horizontal=True, key="fc_new_type")
    cands = objects[objects["object_type"] == otype]
    pick = c2.selectbox(_tr("f_object"), list(cands["object_id"]), format_func=lambda i: object_label(cands[cands["object_id"] == i].iloc[0]),
                        key="fc_new_obj") if len(cands) else None
    month_opts = [add_months(CUR_MONTH, i) for i in range(0, 25)]
    c3, c4, c5 = st.columns(3)
    first = c3.selectbox(_tr("new_first"), month_opts, format_func=month_label, key="fc_new_first")
    last = c4.selectbox(_tr("new_last"), month_opts, index=min(5, len(month_opts) - 1), format_func=month_label, key="fc_new_last")
    compl = c5.radio(_tr("new_compl"), ["partial", "full"], format_func=lambda x: _tr(x), horizontal=True, key="fc_new_compl")
    comment = st.text_input(_tr("new_comment"), key="fc_new_comment")
    if st.button(_tr("btn_create"), type="primary", disabled=pick is None, key="fc_create"):
        if last < first or add_months(first, 12) < last:
            st.error(_tr("err_period"))
        elif first < CUR_MONTH:
            st.error(_tr("err_past"))
        else:
            try:
                no = create_document(cands[cands["object_id"] == pick].iloc[0], first, last, compl, comment)
                flash("success", _trf("created", n=no))
                st.session_state["fc_open_number"] = no
                st.rerun()
            except Exception as e:
                st.error(_trf("err_write", e=e))

# ───────────────────────────── список ─────────────────────────────
with tab_docs:
    f1, f2, f3 = st.columns(3)
    ALL = "__all__"
    f_obj = f1.selectbox(_tr("f_object"), [ALL] + list(obj_labels.keys()), format_func=lambda k: _tr("all") if k == ALL else obj_labels[k], key="fc_f_obj")
    f_st = f2.selectbox(_tr("f_status"), [ALL, "draft", "posted"], format_func=lambda s: _tr("all") if s == ALL else _tr("st_" + s), key="fc_f_st")
    f_m = f3.selectbox(_tr("f_month"), [ALL] + [add_months(CUR_MONTH, i) for i in range(-3, 13)],
                       format_func=lambda m: _tr("all") if m == ALL else month_label(m), key="fc_f_m")
    view = docs.copy()
    if f_obj != ALL:
        ot, oid = f_obj.split(":")
        view = view[(view["object_type"] == ot) & (view["object_id"] == int(oid))]
    if f_st != ALL:
        view = view[view["status"] == f_st]
    if f_m != ALL:
        view = view[(pd.to_datetime(view["first_month"]).dt.date <= f_m) & (pd.to_datetime(view["last_month"]).dt.date >= f_m)]

    if view.empty:
        st.info(_tr("no_docs"))
    else:
        show = pd.DataFrame({
            _tr("col_number"): view["number"], _tr("col_date"): pd.to_datetime(view["doc_date"]).dt.strftime("%d.%m.%Y"),
            _tr("col_object"): view["object_name"] + view["object_type"].map({"pool": f" ({_tr('pool')})", "marketplace": ""}),
            _tr("col_period"): view["first_month"].map(month_label) + " – " + view["last_month"].map(month_label),
            _tr("col_compl"): view["completeness"].map(lambda x: _tr(x)), _tr("col_status"): view["status"].map(lambda s: _tr("st_" + s)),
            _tr("col_rows"): view["n_sku"], _tr("col_filled"): view["n_filled"].astype(str) + " / " + view["n_cells"].astype(str),
            _tr("col_approved"): view["n_approved"], _tr("col_source"): view["source"], _tr("col_created_by"): view["created_by"],
            _tr("col_posted_at"): pd.to_datetime(view["posted_at"]).dt.strftime("%d.%m.%Y %H:%M").fillna("—"), _tr("col_comment"): view["comment"].fillna(""),
        })
        # §12: индикатор «Требуется пересоздание» — у документов пула, чей сохранённый состав
        # разошёлся с действующим. Он считается, а не хранится: гаснет сам после общей замены.
        _drift = pool_drift()
        if not _drift.empty:
            _need = set(int(x) for x in _drift["document_id"])
            show.insert(5, _tr("col_recreate"),
                        [_tr("recreate_needed") if int(i) in _need else "" for i in view["id"]])
        st.dataframe(show, hide_index=True, use_container_width=True, height=min(420, 38 + 35 * len(show)))

    numbers = list(view["number"])
    default = st.session_state.get("fc_open_number")
    idx = numbers.index(default) if default in numbers else 0
    sel_no = st.selectbox(_tr("open_doc"), numbers, index=idx, key="fc_sel") if numbers else None

    if sel_no:
        doc = docs[docs["number"] == sel_no].iloc[0].to_dict()
        doc["first_month"] = pd.Timestamp(doc["first_month"]).date()
        doc["last_month"] = pd.Timestamp(doc["last_month"]).date()
        is_draft = doc["status"] == "draft"
        months = months_between(doc["first_month"], doc["last_month"])
        # ТЗ 010 §16: непроведённый черновик не удаляется, но когда ВСЕ его месяцы стали прошлыми,
        # он доступен только для просмотра. Правки отдельных прошедших месяцев отклонялись и раньше,
        # но экран всё равно показывал кнопки — человек нажимал и получал отказ по каждой ячейке.
        all_past = bool(months) and all(m < CUR_MONTH for m in months)
        if is_draft and all_past:
            is_draft = False          # дальше карточка ведёт себя как у проведённого: только чтение
        try:
            rows = load_rows(doc["id"])
            snap = doc.get("pool_snapshot")
            if isinstance(snap, str):
                snap = json.loads(snap)
            active_matrix, former_matrix = admitted_skus(doc["object_type"], doc["object_id"], snap)
            known = set(q("SELECT sku FROM kabinet_data.sku_master")["sku"])
        except Exception as e:
            st.error(_trf("err_read", e=e))
            st.stop()
        rows["month"] = pd.to_datetime(rows["month"]).dt.date

        # ── шапка ──
        st.divider()
        st.subheader(f"{doc['number']} · {doc['object_name']}" + (f" ({_tr('pool')})" if doc["object_type"] == "pool" else ""))
        show_flash(consume=False)
        h1, h2, h3, h4 = st.columns(4)
        h1.markdown(f"**{_tr('hdr_period')}**: {month_label(doc['first_month'])} – {month_label(doc['last_month'])}")
        h2.markdown(f"**{_tr('col_status')}**: {_tr('st_' + doc['status'])} · {_tr(doc['completeness'])}")
        h3.markdown(_trf("hdr_created", by=doc["created_by"], at=pd.Timestamp(doc["created_at"]).strftime("%d.%m.%Y %H:%M")))
        if doc["posted_at"] is not None and not pd.isna(doc["posted_at"]):
            h4.markdown(_trf("hdr_posted", by=doc["posted_by"], at=pd.Timestamp(doc["posted_at"]).strftime("%d.%m.%Y %H:%M")))
        # §12: прежний документ, значения и исторический состав пула сохраняются — меняется только
        # то, что по нему больше нельзя проводить поодиночке; заменяется он общей операцией
        _dr = pool_drift()
        _dr = _dr[_dr["document_id"] == int(doc["id"])] if not _dr.empty else _dr
        if len(_dr):
            st.warning(_trf("recreate_banner", what=drift_text(_dr.iloc[0]), tab=_tr("tab_repl")))
        else:
            h4.markdown(f"**{_tr('hdr_source')}**: {doc['source']}")
        if snap:
            names = objects[(objects["object_type"] == "marketplace") & (objects["object_id"].isin(snap))]["name"]
            st.caption(_trf("hdr_snapshot", d=pd.Timestamp(doc["pool_snapshot_date"]).strftime("%d.%m.%Y") if doc.get("pool_snapshot_date") else "—")
                       + ": " + ", ".join(names))
        if doc.get("comment"):
            st.caption(f"{_tr('col_comment')}: {doc['comment']}")

        n_appr = int((rows["status"] == "approved").sum()) if is_draft else int((rows["status"] != "unapproved").sum())
        # колонок ровно столько, сколько метрик: у «части ассортимента» четвёртая из пяти пустовала,
        # и «3042 / 3042» не помещалось в свою пятую ширины — на 1100 px резалось до «3042 / 30…»
        full = doc["completeness"] == "full"
        ks = st.columns(5 if full else 4)
        k1, k2, k3, k5 = ks[0], ks[1], ks[2], ks[-1]
        k1.metric(_tr("m_rows"), rows["sku"].nunique())
        k2.metric(_tr("m_cells"), f"{int(rows['quantity'].notna().sum())} / {len(rows)}")
        k3.metric(_tr("m_approved"), f"{n_appr} / {len(rows)}")
        if full:
            ks[3].metric(_tr("m_matrix"), f"{len(active_matrix & set(rows['sku']))} / {len(active_matrix)}", help=_tr("m_matrix_help"))
        k4_total = int(rows["quantity"].fillna(0).sum())
        k5.metric(_tr("m_sum"), f"{k4_total:,}")
        rev = (rows["quantity"].fillna(0) * rows["target_price"].fillna(0)).sum()
        if rev:
            st.caption(f"{_tr('m_rev')}: {rev:,.0f}")

        # ── редактируемая шапка (черновик) ──
        has_approved = bool((rows["status"] == "approved").any())
        if is_draft:
            with st.expander(_tr("hdr_edit")):
                if has_approved:
                    st.info(_tr("hdr_locked"))
                e1, e2, e3 = st.columns(3)
                opts = sorted(set([add_months(CUR_MONTH, i) for i in range(0, 25)] + [doc["first_month"], doc["last_month"]]))
                ef = e1.selectbox(_tr("new_first"), opts, index=opts.index(doc["first_month"]), format_func=month_label, key=f"fc_hf_{doc['id']}", disabled=has_approved)
                el = e2.selectbox(_tr("new_last"), opts, index=opts.index(doc["last_month"]), format_func=month_label, key=f"fc_hl_{doc['id']}", disabled=has_approved)
                ec = e3.radio(_tr("new_compl"), ["partial", "full"], index=0 if doc["completeness"] == "partial" else 1,
                              format_func=lambda x: _tr(x), horizontal=True, key=f"fc_hc_{doc['id']}")
                ecm = st.text_input(_tr("new_comment"), value=doc.get("comment") or "", key=f"fc_hcm_{doc['id']}")
                if st.button(_tr("btn_hdr_save"), key=f"fc_hsave_{doc['id']}"):
                    if el < ef or add_months(ef, 12) < el:
                        st.error(_tr("err_period"))
                    elif ef < CUR_MONTH and not has_approved and ef != doc["first_month"]:
                        st.error(_tr("err_past"))
                    else:
                        try:
                            save_header(doc, ef, el, ec, ecm, has_approved)
                            flash("success", _tr("hdr_saved"))
                            st.rerun()
                        except Exception as e:
                            st.error(_trf("err_write", e=e))

        # ── таблица SKU × месяц ──
        st.caption(_tr("grid_help") if is_draft else
                   (_tr("ro_all_past") if doc["status"] == "draft" else _tr("grid_posted")))
        sku_meta = rows.groupby("sku").agg(sku_type=("sku_type", "first"), sku_name=("sku_name", "first")).reset_index()
        grid = rows.pivot_table(index="sku", columns="month", values="quantity", aggfunc="first", dropna=False)
        grid = grid.reindex(columns=months)
        grid.columns = [month_label(m) for m in months]
        grid = grid.reset_index().merge(sku_meta, on="sku", how="left")
        for c in grid.columns:
            if c != "sku" and c not in ("sku_type", "sku_name"):
                grid[c] = pd.to_numeric(grid[c], errors="coerce").astype("Float64")   # nullable: pd.NA рисуется пустой ячейкой; NaN float64 редактор писал словом
        stat = rows.groupby("sku").agg(n=("status", "size"), a=("status", lambda s: int((s == "approved").sum())),
                                       e=("quantity", lambda s: int(s.isna().sum())),
                                       sup=("status", lambda s: int((s == "superseded").sum()))).reset_index()

        def _state(r):
            if not is_draft:
                return "⟲" if r.sup else _tr("state_all_appr")
            base = _tr("state_all_appr") if r.a == r.n else (_tr("state_none") if r.a == 0 else _trf("state_part", a=r.a, n=r.n))
            return base + (" · " + _trf("state_empty", e=r.e) if r.e else "")
        stat["state"] = [_state(r) for r in stat.itertuples()]
        grid = grid.merge(stat[["sku", "state"]], on="sku", how="left")
        grid["sku_name"] = grid["sku_name"].fillna("")   # без имени рисовалось «None»
        grid["type"] = grid["sku_type"].map({"base": _tr("type_base"), "composite": _tr("type_composite")}).fillna(_tr("type_unknown"))
        mcols = [month_label(m) for m in months]
        grid[_tr("col_total")] = grid[mcols].fillna(0).sum(axis=1).astype(int)
        show_cols = ["sku", "sku_name", "type", "state"] + mcols + [_tr("col_total")]
        cfg = {"sku": st.column_config.TextColumn(_tr("col_sku"), disabled=True, width="small", pinned=True),
               "type": st.column_config.TextColumn(_tr("col_type"), disabled=True, width="small"),
               "state": st.column_config.TextColumn(_tr("col_state"), disabled=True, width="small"),
               "sku_name": st.column_config.TextColumn(_tr("col_name"), disabled=True, width="medium", pinned=True),
               _tr("col_total"): st.column_config.NumberColumn(_tr("col_total"), disabled=True, format="%d")}
        for m in months:
            cfg[month_label(m)] = st.column_config.NumberColumn(month_label(m), min_value=0, step=1, format="%d",
                                                                disabled=(not is_draft) or m < CUR_MONTH)
        view_grid = grid[show_cols]
        if not is_draft:   # читаем, а не правим: числа строками, чтобы пустая ячейка была пустой
            view_grid = blank_na(view_grid, mcols + [_tr("col_total")])
            for c in mcols + [_tr("col_total")]:
                cfg[c] = st.column_config.TextColumn(c, disabled=True)
        edited = st.data_editor(view_grid, column_config=cfg, hide_index=True, use_container_width=True,
                                disabled=not is_draft, key=f"fc_grid_{doc['id']}_{len(rows)}",
                                height=min(560, 38 + 35 * max(1, len(grid))))
        if is_draft and st.button(_tr("btn_save"), type="primary", key=f"fc_save_{doc['id']}"):
            try:
                n, rej = save_grid(doc, rows, edited, months)
                if n:
                    flash("success", _trf("saved", n=n))
                elif not rej:
                    st.info(_tr("nothing_changed"))
                if rej:
                    msg = _trf("rejected", n=len(rej)) + "\n\n" + "\n".join(f"- {x}" for x in rej[:20])
                    flash("warning", msg) if n else st.warning(msg)   # при rerun — через flash, иначе сообщение сотрётся
                if n:
                    st.rerun()
            except Exception as e:
                st.error(_trf("err_write", e=e))

        with st.expander(_tr("sec_states")):
            st.caption(_tr("states_help"))
            sym = {"unapproved": "○", "approved": "✓", "superseded": "⟲"}
            sm = rows.assign(s=[("" if pd.isna(r.quantity) and r.status == "unapproved" else sym.get(r.status, "?")) for r in rows.itertuples()])
            sm = sm.pivot_table(index="sku", columns="month", values="s", aggfunc="first").reindex(columns=months).fillna("")
            sm.columns = mcols
            st.dataframe(sm, use_container_width=True, height=min(400, 38 + 35 * max(1, len(sm))))

        with st.expander(_tr("sec_prices")):
            st.caption(_tr("prices_help"))
            pg_ = rows.pivot_table(index="sku", columns="month", values="target_price", aggfunc="first", dropna=False).reindex(columns=months)
            pg_.columns = mcols
            pg_ = pg_.reset_index()
            for c in mcols:
                pg_[c] = pd.to_numeric(pg_[c], errors="coerce").astype("Float64")
            pcfg = {"sku": st.column_config.TextColumn(_tr("col_sku"), disabled=True, pinned=True)}
            for m in months:
                pcfg[month_label(m)] = st.column_config.NumberColumn(month_label(m), min_value=0.0, format="%.2f", disabled=(not is_draft) or m < CUR_MONTH)
            view_pg = pg_
            if not is_draft:   # то же, что и в сетке: у проведённого документа цены только читают
                view_pg = blank_na(pg_, mcols, fmt="{:.2f}")
                for c in mcols:
                    pcfg[c] = st.column_config.TextColumn(c, disabled=True)
            pe = st.data_editor(view_pg, column_config=pcfg, hide_index=True, use_container_width=True, disabled=not is_draft,
                                key=f"fc_prices_{doc['id']}_{len(rows)}", height=min(560, 38 + 35 * max(1, len(pg_))))
            if is_draft and st.button(_tr("btn_prices_save"), key=f"fc_psave_{doc['id']}"):
                try:
                    n = save_prices(doc, rows, pe, months)
                    if n:
                        flash("success", _trf("prices_saved", n=n))
                        st.rerun()
                    st.info(_tr("nothing_changed"))
                except Exception as e:
                    st.error(_trf("err_write", e=e))

        # ── добавление SKU и действия (черновик) ──
        if is_draft:
            st.markdown(f"##### {_tr('sec_add')}")
            a1, a2, a3 = st.columns([3, 1, 1])
            present = set(rows["sku"])
            # допущенные первыми: список из 500 SKU по алфавиту начинался с «нет допуска», и казалось, что допущенных нет вовсе (QA 20.09)
            cand = sorted(active_matrix - present) + sorted(former_matrix - present - active_matrix) + sorted(known - present - active_matrix - former_matrix)
            picked = a1.multiselect(_trf("add_pick", a=len(active_matrix - present), n=len(cand)), cand, key=f"fc_add_{doc['id']}", placeholder=_tr("ph_pick_sku"),
                                    format_func=lambda s: s if s in active_matrix else (f"{s} · {_tr('lbl_liquidation')}" if s in former_matrix else f"{s} · {_tr('lbl_no_admission')}"))
            if a2.button(_tr("btn_add"), disabled=not picked, key=f"fc_addbtn_{doc['id']}"):
                try:
                    n, rej = add_skus(doc, rows, picked, active_matrix, former_matrix, known)
                    say = flash if n else (lambda kind, text: getattr(st, kind)(text))
                    say("success", _trf("add_done", n=n, r=len(rej)))
                    if rej:
                        say("warning", "\n".join(f"- {x}" for x in rej[:20]))
                    if n:
                        st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if a3.button(_tr("btn_matrix"), key=f"fc_matrix_{doc['id']}", help=_tr("btn_matrix_help")):
                todo = sorted(active_matrix - present)
                if not todo:
                    st.info(_tr("matrix_none"))
                else:
                    try:
                        n, _ = add_skus(doc, rows, todo, active_matrix, former_matrix, known | active_matrix)
                        flash("success", _trf("matrix_added", n=n))
                        st.rerun()
                    except Exception as e:
                        st.error(_trf("err_write", e=e))
            lost = sorted(present - active_matrix - former_matrix) if present else []
            if lost:
                st.warning(_tr("lost_admission") + ", ".join(lost[:20]))

            with st.expander(_tr("sec_upload")):
                st.caption(_tr("up_help"))
                kind = st.radio(_tr("up_src"), ["file", "gsheet"], horizontal=True,
                                format_func=lambda k: _tr("up_src_file") if k == "file" else _tr("up_src_gs"),
                                key=f"fc_up_kind_{doc['id']}")
                handle, sheets, err = None, [], ""
                if kind == "file":
                    handle = st.file_uploader(_tr("up_file"), type=["xlsx", "xlsm", "xls", "csv"],
                                              key=f"fc_up_file_{doc['id']}")
                else:
                    url = st.text_input(_tr("up_gs_url"), key=f"fc_up_url_{doc['id']}",
                                        placeholder="https://docs.google.com/spreadsheets/d/…")
                    if url.strip():
                        try:
                            handle = gs_open(url)
                        except Exception as e:      # нет библиотеки, нет ключа, нет доступа к листу
                            err = _trf("up_gs_fail", e=str(e)[:200])
                if err:
                    st.warning(err)
                if handle is not None and not err:
                    try:
                        sheets = source_sheets(kind, handle)
                    except Exception as e:
                        st.error(_trf("up_read_fail", e=str(e)[:200]))
                        sheets = []
                if sheets:
                    s1, s2 = st.columns([3, 1])
                    sheet = s1.selectbox(_tr("up_sheet"), sheets, key=f"fc_up_sheet_{doc['id']}")
                    hrow = s2.number_input(_tr("up_header"), min_value=1, max_value=50, value=1, step=1,
                                           key=f"fc_up_hrow_{doc['id']}")
                    try:
                        raw_src = read_source(kind, handle, sheet)
                        labels, body = header_and_body(raw_src, int(hrow))
                    except Exception as e:
                        labels, body = [], None
                        st.error(_trf("up_read_fail", e=str(e)[:200]))
                    if body is not None and len(labels):
                        # колонка артикула: угадываем по подписи, но последнее слово за человеком
                        guess_sku = next((c for c in labels if any(w in str(c).lower()
                                                                   for w in ("sku", "артик", "код", "code"))), labels[0])
                        sku_col = st.selectbox(_tr("up_sku_col"), labels, index=labels.index(guess_sku),
                                               key=f"fc_up_skucol_{doc['id']}")
                        st.caption(_tr("up_map"))
                        mapping, cols_left = {}, [c for c in labels if c != sku_col]
                        mcols_ui = st.columns(3)
                        # сентинел «—», а не None: вариант None в selectbox неотличим от «ничего не
                        # выбрано» и показывается служебным «Choose an option» вместо нашей подписи
                        SKIP = "—"
                        for i, c in enumerate(cols_left):
                            g = guess_month(c, months)
                            opts = [SKIP] + months
                            got = mcols_ui[i % 3].selectbox(
                                c, opts, index=(opts.index(g) if g in opts else 0),
                                format_func=lambda m: _tr("up_skip") if m == SKIP else month_label(m),
                                key=f"fc_up_map_{doc['id']}_{i}")
                            mapping[c] = None if got == SKIP else got
                        picked_months = [m for m in mapping.values() if m is not None]
                        if len(picked_months) != len(set(picked_months)):
                            st.error(_tr("up_map_dup"))
                        elif not picked_months:
                            st.info(_tr("up_no_months"))
                        else:
                            plan = plan_upload(doc, rows, body, sku_col, mapping, months,
                                               active_matrix, former_matrix, known)
                            prev = pd.DataFrame(
                                [(sku, month_label(m), "" if o is None else o, n)
                                 for _, sku, m, o, n in plan["changes"]]
                                + [(sku, month_label(m), "", v) for sku, vals in plan["adds"].items()
                                   for m, v in sorted(vals.items())],
                                columns=[_tr("col_sku"), _tr("up_col_month"), _tr("up_col_old"), _tr("up_col_new")])
                            if plan["errors"]:
                                st.error(_trf("up_errors", n=len(plan["errors"])) + "\n\n"
                                         + "\n".join(f"- {x}" for x in plan["errors"][:30])
                                         + ("\n- …" if len(plan["errors"]) > 30 else ""))
                            if not prev.empty:
                                st.caption(_trf("up_preview", s=plan["skus"], v=plan["values"],
                                                a=len(plan["adds"]), r=len(plan["replaces"])))
                                st.dataframe(prev, use_container_width=True, hide_index=True,
                                             height=min(320, 38 + 35 * max(1, len(prev))))
                            elif not plan["errors"]:
                                st.info(_tr("up_nothing"))
                            uk_ = f"fc_up_confirm_{doc['id']}"
                            need_ok = bool(plan["replaces"])          # §11.5: замену заполненного подтверждают
                            armed = st.session_state.get(uk_) == (plan["values"], len(plan["replaces"]))
                            if need_ok and not armed and not plan["errors"] and not prev.empty:
                                st.warning(_trf("up_replace", n=len(plan["replaces"])))
                            if st.button(_tr("up_btn_apply_confirm") if (need_ok and armed) else _tr("up_btn_apply"),
                                         type="primary", disabled=bool(plan["errors"]) or prev.empty,
                                         key=f"fc_up_apply_{doc['id']}"):
                                if need_ok and not armed:
                                    st.session_state[uk_] = (plan["values"], len(plan["replaces"]))
                                    st.rerun()
                                try:
                                    n, k = apply_upload(doc, plan, months, former_matrix,
                                                        "import:file" if kind == "file" else "import:gsheet")
                                    st.session_state.pop(uk_, None)
                                    flash("success", _trf("up_done", n=n, k=k))
                                    st.rerun()
                                except Exception as e:
                                    st.error(_trf("err_write", e=e))

            st.markdown(f"##### {_tr('sec_actions')}")
            b1, b2 = st.columns(2)
            sel_skus = b1.multiselect(_tr("pick_skus"), sorted(present), key=f"fc_sel_skus_{doc['id']}", placeholder=_tr("all_skus"))
            sel_months = b2.multiselect(_tr("pick_months"), months, format_func=month_label, key=f"fc_sel_months_{doc['id']}", placeholder=_tr("all_months"))
            eff_months = sel_months or months
            c1, c2, c3, c4 = st.columns(4)
            if c1.button(_tr("btn_approve"), type="primary", key=f"fc_appr_{doc['id']}"):
                try:
                    n, empty = approve(doc, rows, sel_skus, eff_months, active_matrix, former_matrix)
                    say = flash if n else (lambda kind, text: getattr(st, kind)(text))
                    if n:
                        say("success", _trf("approved_n", n=n))
                    if empty:
                        say("warning", _trf("approve_empty", cells=", ".join(empty[:15]) + ("…" if len(empty) > 15 else "")))
                    if n:
                        st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if c2.button(_tr("btn_unapprove"), key=f"fc_unappr_{doc['id']}"):
                try:
                    n = unapprove(doc, rows, sel_skus, eff_months)
                    flash("success", _trf("unapproved_n", n=n))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if c3.button(_tr("btn_zeros"), key=f"fc_zeros_{doc['id']}"):
                try:
                    n = fill_zeros(doc, rows)
                    flash("success", _trf("zeros_n", n=n))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))
            if c4.button(_tr("btn_delete"), disabled=not sel_skus, key=f"fc_del_{doc['id']}"):
                with_appr = sorted(set(rows[(rows["sku"].isin(sel_skus)) & (rows["status"] == "approved")]["sku"]))
                if with_appr:
                    st.error(_trf("del_has_approved", skus=", ".join(with_appr)))
                else:
                    has_vals = bool(rows[(rows["sku"].isin(sel_skus)) & rows["quantity"].notna()].shape[0])
                    ck = f"fc_del_confirm_{doc['id']}"
                    if has_vals and st.session_state.get(ck) != tuple(sorted(sel_skus)):
                        st.session_state[ck] = tuple(sorted(sel_skus))
                        st.warning(_trf("del_confirm", n=len(sel_skus)))
                    else:
                        try:
                            n = delete_rows(doc, rows, sel_skus)
                            st.session_state.pop(ck, None)
                            flash("success", _trf("deleted_n", n=n))
                            st.rerun()
                        except Exception as e:
                            st.error(_trf("err_write", e=e))

            st.markdown(f"##### {_tr('sec_post')}")
            problems = post_checks(doc, rows, active_matrix, former_matrix)
            # §21: документ, переключающий покрытие затронутых изменением пула маркетплейсов,
            # поодиночке не проводится — ни обычным проведением, ни последовательной заменой
            _stop = blocked_by_drift(doc, pool_drift())
            if _stop:
                problems = [_stop] + problems
            if problems:
                st.warning(_tr("post_block") + "\n\n" + "\n".join(f"- {p}" for p in problems))
            # проведение необратимо (проведённый документ не правится, §9) — два нажатия, как удаление в справочниках
            pk = f"fc_post_confirm_{doc['id']}"
            armed = st.session_state.get(pk) == len(rows)
            if armed:
                st.warning(_trf("post_confirm", n=doc["number"], k=len(rows)))
            if st.button(_tr("btn_post_confirm") if armed else _tr("btn_post"), type="primary", disabled=bool(problems), key=f"fc_post_{doc['id']}"):
                if not armed:
                    st.session_state[pk] = len(rows)
                    st.rerun()
                try:
                    k, r, dd, dd_err = post_document(doc, rows)
                    st.session_state.pop(pk, None)
                    flash("success", _trf("post_ok", n=doc["number"], k=k, r=r))
                    if dd_err:
                        flash("error", _trf("post_dd_fail", e=dd_err))
                    else:
                        flash("info", _trf("post_dd", c=dd[0], s=dd[2], t=dd[3]))
                        if dd[1]:
                            flash("warning", _trf("post_dd_err", e=dd[1]))
                    st.rerun()
                except Exception as e:
                    st.error(_trf("err_write", e=e))

        show_flash()   # второй показ — рядом с кнопками действий; очередь очищается здесь

        # ── зависимая потребность (ТЗ 011) ──
        with st.expander(_tr("sec_dd")):
            st.caption(_tr("dd_help"))
            try:
                dd_rows = q("""SELECT base_sku, month, dependent_quantity, details, errors, calculated_at
                               FROM kabinet_data.v_dependent_demand_current
                               WHERE object_type = %s AND object_id = %s ORDER BY base_sku, month""",
                            (doc["object_type"], int(doc["object_id"])))
                dd_bad = q("""SELECT composite_sku, sku, month, error_text
                              FROM kabinet_data.forecast_register
                              WHERE is_current AND record_type = 'dependent' AND calculation_status = 'ERROR'
                                AND object_type = %s AND object_id = %s ORDER BY composite_sku, month""",
                           (doc["object_type"], int(doc["object_id"])))
            except Exception as e:
                dd_rows = dd_bad = pd.DataFrame()
                st.error(_trf("err_read", e=e))
            if dd_rows.empty:
                st.caption(_tr("dd_empty"))
            else:
                v = dd_rows.copy()
                v["month"] = v["month"].map(month_label)
                # количество — текстом: пустая числовая ячейка Streamlit рисуется словом «None», а пусто у
                # строки с ошибкой значит «не рассчитано», и ноль тут был бы неправдой (см. AGENTS.md)
                v["dependent_quantity"] = v["dependent_quantity"].map(lambda x: "" if pd.isna(x) else f"{int(x)}")
                v["calculated_at"] = pd.to_datetime(v["calculated_at"]).dt.strftime("%d.%m %H:%M")
                v.columns = [_tr("dd_col_sku"), _tr("log_month"), _tr("dd_col_qty"), _tr("dd_col_details"), _tr("dd_col_errors"), _tr("dd_col_at")]
                st.dataframe(v, hide_index=True, use_container_width=True, height=min(400, 38 + 35 * len(v)))
            if not dd_bad.empty:
                st.warning(_trf("dd_errors_hdr", n=len(dd_bad)))
                b = dd_bad.copy()
                b["month"] = b["month"].map(month_label)
                b.columns = [_tr("dd_col_kit"), _tr("col_sku"), _tr("log_month"), _tr("dd_col_err")]
                st.dataframe(b, hide_index=True, use_container_width=True, height=min(300, 38 + 35 * len(b)))

        # ── журнал документа ──
        with st.expander(_tr("sec_doclog")):
            try:
                lg = q("""SELECT changed_at, actor, sku, month, field, old_value, new_value, source
                          FROM kabinet_data.forecast_change_log WHERE document_id = %s ORDER BY changed_at DESC LIMIT 500""", (int(doc["id"]),))
            except Exception as e:
                lg = pd.DataFrame()
                st.error(_trf("err_read", e=e))
            if lg.empty:
                st.caption(_tr("log_empty"))
            else:
                lg = _log_view(lg)
                lg.columns = [_tr("log_col_at"), _tr("log_col_actor"), _tr("col_sku"), _tr("log_month"), _tr("log_col_field"), _tr("log_col_old"), _tr("log_col_new"), _tr("log_col_src")]
                st.dataframe(lg, hide_index=True, use_container_width=True, height=min(400, 38 + 35 * len(lg)))

# ───────────────────────────── журнал ─────────────────────────────
with tab_repl:
    st.caption(_tr("repl_help"))
    drift = pool_drift()
    if drift.empty:
        st.success(_tr("repl_none"))
    for r in drift.itertuples():
        st.divider()
        st.subheader(_trf("repl_hdr", pool=r.pool_name))
        st.warning(_trf("repl_what", what=drift_text(r), n=r.number,
                        was=", ".join(mp_name(x) for x in r.snapshot_ids) or "—",
                        now=", ".join(mp_name(x) for x in r.current_ids) or "—"))
        st.caption(_trf("repl_scope", rows=int(r.rows_ahead),
                        m=month_label(r.first_month_ahead) if r.first_month_ahead is not None else "—"))
        removed = sorted(_ids(r.snapshot_ids) - _ids(r.current_ids))
        added = sorted(_ids(r.current_ids) - _ids(r.snapshot_ids))
        picks, terms = {}, {}

        # Новый прогноз самого пула — когда в нём остались участники
        if len(r.current_ids or []):
            d_pool = object_drafts("pool", int(r.pool_id))
            opts = [0] + [int(x) for x in d_pool["id"]]
            picks[("pool", int(r.pool_id))] = st.selectbox(
                _trf("repl_pick_pool", pool=r.pool_name), opts,
                format_func=lambda i: _tr("repl_none_pick") if i == 0
                else str(d_pool[d_pool["id"] == i].iloc[0]["number"]),
                key=f"fc_rp_pool_{r.document_id}")
        else:
            st.info(_tr("repl_disbanded_hint"))

        # Затронутые маркетплейсы: продолжающим — новый прогноз, деактивированным — причина
        for mp in removed + added:
            act = mp_is_active(mp)
            role = _tr("repl_role_removed") if mp in removed else _tr("repl_role_added")
            c1, c2 = st.columns([1, 2])
            c1.markdown(f"**{mp_name(mp)}** · {role} · "
                        + (_tr("repl_mp_active") if act else _tr("repl_mp_inactive")))
            if mp in removed and act:
                d_mp = object_drafts("marketplace", mp)
                opts = [0] + [int(x) for x in d_mp["id"]]
                picks[("marketplace", mp)] = c2.selectbox(
                    _trf("repl_pick_mp", mp=mp_name(mp)), opts,
                    format_func=lambda i: _tr("repl_none_pick") if i == 0
                    else str(d_mp[d_mp["id"] == i].iloc[0]["number"]),
                    key=f"fc_rp_mp_{r.document_id}_{mp}", label_visibility="collapsed")
            elif mp in removed:
                terms[mp] = c2.text_input(_trf("repl_reason_mp", mp=mp_name(mp)), key=f"fc_rt_{r.document_id}_{mp}",
                                          placeholder=_tr("repl_reason_ph"), label_visibility="collapsed")
            else:
                c2.caption(_tr("repl_added_hint"))

        reason = st.text_input(_tr("repl_reason"), value=drift_text(r), key=f"fc_rr_{r.document_id}")
        try:
            plan = replacement_plan(r, picks, terms)
        except Exception as e:
            st.error(_trf("err_read", e=e))
            continue
        m1, m2, m3 = st.columns(3)
        m1.metric(_tr("repl_m_docs"), len(plan["docs"]))
        m2.metric(_tr("repl_m_sup"), len(plan["supersede"]))
        m3.metric(_tr("repl_m_term"), len(plan["terminate"]))
        if not str(reason).strip():
            plan["problems"] = [_tr("repl_need_op_reason")] + plan["problems"]
        if plan["problems"]:
            st.error(_trf("repl_blocked", n=len(plan["problems"])) + "\n\n"
                     + "\n".join(f"- {p}" for p in plan["problems"][:20]))
        elif plan["supersede"] or plan["terminate"] or plan["docs"]:
            st.success(_tr("repl_ready"))
        rk = f"fc_rp_confirm_{r.document_id}"
        armed = st.session_state.get(rk) == (len(plan["supersede"]), len(plan["terminate"]), len(plan["docs"]))
        if armed and not plan["problems"]:
            st.warning(_trf("repl_confirm", d=len(plan["docs"]), s=len(plan["supersede"]), t=len(plan["terminate"])))
        if st.button(_tr("repl_btn_confirm") if armed else _tr("repl_btn"), type="primary",
                    disabled=bool(plan["problems"]) or not plan["docs"] and not plan["terminate"],
                    key=f"fc_rp_go_{r.document_id}"):
            if not armed:
                st.session_state[rk] = (len(plan["supersede"]), len(plan["terminate"]), len(plan["docs"]))
                st.rerun()
            try:
                res = execute_replacement(r, plan, reason, terms)
                st.session_state.pop(rk, None)
                flash("success", _trf("repl_done", op=res["op_id"], d=res["docs"],
                                      s=res["superseded"], t=res["terminated"]))
                if res["dd_err"]:
                    flash("warning", _trf("repl_dd_err", e="; ".join(res["dd_err"][:3])))
                st.rerun()
            except Exception as e:
                st.error(_trf("err_write", e=e))

    ops = q("""SELECT r.id, r.executed_at, p.name AS pool, r.reason, r.change_summary,
                      r.documents, r.superseded_rows, r.terminated_rows, r.actor
               FROM kabinet_data.forecast_replacements r JOIN kabinet_data.pools p ON p.id = r.pool_id
               ORDER BY r.id DESC LIMIT 50""")
    st.divider()
    st.markdown(f"##### {_tr('repl_hist')}")
    if ops.empty:
        st.caption(_tr("repl_hist_empty"))
    else:
        st.dataframe(pd.DataFrame({
            _tr("repl_c_at"): pd.to_datetime(ops["executed_at"]).dt.strftime("%d.%m.%Y %H:%M"),
            _tr("col_object"): ops["pool"], _tr("repl_c_what"): ops["change_summary"].fillna(""),
            _tr("repl_c_reason"): ops["reason"], _tr("repl_m_docs"): ops["documents"],
            _tr("repl_m_sup"): ops["superseded_rows"], _tr("repl_m_term"): ops["terminated_rows"],
            _tr("log_col_actor"): ops["actor"],
        }), hide_index=True, use_container_width=True, height=min(300, 38 + 35 * len(ops)))

with tab_log:
    l1, l2, l3, l4, l5 = st.columns(5)
    d_from = l1.date_input(_tr("log_from"), value=TODAY.replace(day=1), key="fc_log_from")
    d_to = l2.date_input(_tr("log_to"), value=TODAY, key="fc_log_to")
    ALL = "__all__"
    lo = l3.selectbox(_tr("f_object"), [ALL] + list(obj_labels.keys()), format_func=lambda k: _tr("all") if k == ALL else obj_labels[k], key="fc_log_obj")
    lsku = l4.text_input(_tr("log_sku"), key="fc_log_sku")
    lm = l5.selectbox(_tr("log_month"), [ALL] + [add_months(CUR_MONTH, i) for i in range(-6, 13)],
                      format_func=lambda m: _tr("all") if m == ALL else month_label(m), key="fc_log_month")
    where, params = ["l.changed_at >= %s", "l.changed_at < %s + INTERVAL '1 day'"], [d_from, d_to]
    if lo != ALL:
        ot, oid = lo.split(":")
        where.append("d.object_type = %s AND d.object_id = %s"); params += [ot, int(oid)]
    if lsku.strip():
        where.append("l.sku ILIKE %s"); params.append(f"%{lsku.strip()}%")
    if lm != ALL:
        where.append("l.month = %s"); params.append(lm)
    try:
        lg = q(f"""SELECT l.changed_at, l.actor, d.number, COALESCE(m.code, p.name) AS object_name, d.status, l.sku, l.month, l.field,
                          l.old_value, l.new_value, l.source
                   FROM kabinet_data.forecast_change_log l JOIN kabinet_data.forecast_documents d ON d.id = l.document_id
                   LEFT JOIN kabinet_data.marketplaces_new m ON d.object_type = 'marketplace' AND m.id = d.object_id
                   LEFT JOIN kabinet_data.pools p ON d.object_type = 'pool' AND p.id = d.object_id
                   WHERE {' AND '.join(where)} ORDER BY l.changed_at DESC LIMIT 2000""", tuple(params))
    except Exception as e:
        lg = pd.DataFrame()
        st.error(_trf("err_read", e=e))
    if lg.empty:
        st.info(_tr("log_empty"))
    else:
        lg = _log_view(lg)
        lg["status"] = lg["status"].map(lambda s: _tr("st_" + s))
        lg.columns = [_tr("log_col_at"), _tr("log_col_actor"), _tr("log_col_doc"), _tr("col_object"), _tr("col_status"), _tr("col_sku"),
                      _tr("log_month"), _tr("log_col_field"), _tr("log_col_old"), _tr("log_col_new"), _tr("log_col_src")]
        st.dataframe(lg, hide_index=True, use_container_width=True, height=min(600, 38 + 35 * len(lg)))
