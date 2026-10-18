# scratchpad — проверки, которые запускаются ЛОКАЛЬНО

Автопроверки GitHub (CI, `.github/workflows/ci.yml`) гоняют только `tests/` — без базы и без секретов: репозиторий
публичный, и ключей к Databricks и Lakebase в GitHub нет и не будет. Всё, что ниже с пометкой «база», в CI не идёт и
запускается здесь, на машине с `.mcp.json` (DSN роли Кабинета):

    uv run -q --with-requirements requirements.txt --with psycopg2-binary python scratchpad/<скрипт>.py

## Нужна база (только локально)

| Скрипт | Что проверяет |
|---|---|
| `smoke_full.py` | все страницы и разделы «Справочников» на живой базе; обязательна перед PR со страницами |
| `smoke_dict_all.py`, `smoke_pages_pool.py` | справочники и страницы, читающие пулы |
| `smoke_ctry.py`, `smoke_plat.py`, `smoke_mp.py`, `smoke_pool.py`, `smoke_norm.py`, `smoke_ch.py`, `smoke_cat.py`, `smoke_cat_en.py` | разделы «Справочников» на временных копиях таблиц |
| `smoke_access.py`, `smoke_ls_auth.py` | экран «Доступ» и права Listing Suite |
| `check_sources.py` | каждый источник паспорта данных читается |
| `auth_matrix.py`, `auth_change_test.py`, `perm_trigger_test.py`, `switch_test.py`, `qa_test.py`, `log_view_test.py`, `test_login_sub.py` | вход, права, рубильник, QA-вход — в откатываемых транзакциях |
| `fx_diff.py`, `fx_impact.py` | разовые замеры валют |

## Без базы (идут и в CI — через `tests/test_auth_scripts.py`)

| Скрипт | Что проверяет |
|---|---|
| `auth_gate.py` | кого пускаем на вход, срок доступа |
| `pages_vis_test.py` | видимость страниц по матрице прав, QA-агент |

## Служебные (не проверки)

`cycle_report.py` (сводка цикла в бот — пишет одну строку в базу), `sync_access_screen.py` (выкладка экрана «Доступ»
в Listing Suite), `deploy_auth_switch.py` (выкладка рубильника входа), `check_login_deps.py` (зависимости входа —
запускать в чистом окружении).
