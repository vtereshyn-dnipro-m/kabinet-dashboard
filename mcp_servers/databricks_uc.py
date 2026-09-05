# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastmcp>=2.0",
#   "databricks-sql-connector>=2.7",
#   "databricks-sdk>=0.18",
# ]
# ///
"""MCP-сервер к Unity Catalog через SQL Warehouse, только на чтение.

Готового сервера с защитой от записи нет, а пускать модель в склад без
неё нельзя: одна опечатка в запросе — и DROP уходит в прод. Поэтому
здесь свой, и вся его суть в двух вещах: OAuth вместо долгоживущего
токена и разбор запроса до отправки.

Гранты у service principal и так только на SELECT, но полагаться на одни
гранты не стоит. Права меняются на стороне Databricks, и меняются не нами;
проверка на своей стороне переживает такие изменения и делает отказ
понятным — видно, что именно отклонено и почему, вместо ошибки прав из
глубины драйвера.
"""
import os
import re

from databricks import sql
from databricks.sdk.core import Config, oauth_service_principal
from fastmcp import FastMCP

MAX_ROWS = int(os.environ.get("DATABRICKS_MAX_ROWS", "1000"))

# Что разрешено начинать запрос. Всё остальное отклоняется до отправки
ALLOWED_HEADS = ("select", "show", "describe", "desc", "with", "explain")
# Слова, которых не должно быть нигде в запросе — даже внутри CTE.
# WITH ... INSERT синтаксически возможен, и одной проверки первого слова
# мало
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|"
    r"copy|replace|refresh|use|call|msck|set|reset|analyze|optimize|vacuum|"
    r"restore|clone)\b", re.I)

_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_STRINGS = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`(?:[^`]|``)*`")
_HAS_LIMIT = re.compile(r"\blimit\s+\d+\s*$", re.I)

mcp = FastMCP("databricks-uc")


class Refused(Exception):
    """Запрос отклонён защитой, до обращения к складу."""


def _strip(query: str) -> str:
    """Запрос без комментариев и строковых литералов.

    Литералы убираем до поиска запрещённых слов: товар с названием
    «Set of drills» не должен выглядеть как команда SET."""
    q = _COMMENT_BLOCK.sub(" ", query)
    q = _COMMENT_LINE.sub(" ", q)
    return _STRINGS.sub("''", q)


def guard(query: str) -> str:
    """Проверяет запрос и возвращает его готовым к отправке.

    Отказ — исключение с внятным текстом, а не тихое усечение: молча
    выполнить не то, что просили, хуже, чем отказать."""
    bare = _strip(query).strip()
    if not bare:
        raise Refused("Пустой запрос.")

    # Несколько команд через ; — самый простой способ протащить запись
    # следом за безобидным SELECT
    parts = [p for p in bare.split(";") if p.strip()]
    if len(parts) > 1:
        raise Refused(
            f"Отклонено: в запросе {len(parts)} команд через «;». "
            "Разрешена ровно одна — иначе рядом с SELECT можно провезти запись.")
    bare = parts[0].strip()

    head = bare.split(None, 1)[0].lower() if bare.split() else ""
    if head not in ALLOWED_HEADS:
        raise Refused(
            f"Отклонено: запрос начинается с «{head.upper()}». "
            f"Сервер только для чтения, разрешены: "
            f"{', '.join(w.upper() for w in ALLOWED_HEADS)}.")

    found = FORBIDDEN.search(bare)
    if found:
        raise Refused(
            f"Отклонено: в запросе есть «{found.group(0).upper()}». "
            "Даже внутри WITH или подзапроса менять данные нельзя.")

    # Ограничение по строкам ставим сами, если его не поставили. Для
    # SHOW и DESCRIBE не трогаем: у них LIMIT неуместен
    out = query.strip().rstrip(";").strip()
    if head in ("select", "with") and not _HAS_LIMIT.search(_strip(out).strip()):
        out = f"{out}\nLIMIT {MAX_ROWS}"
    return out


def _connect():
    """Соединение по OAuth M2M. Долгоживущий токен не используется:
    он утекает целиком и отзывается вручную, а машинный OAuth сам
    протухает и обновляется драйвером."""
    host = os.environ["DATABRICKS_HOST"].replace("https://", "").strip("/")
    cid = os.environ["DATABRICKS_CLIENT_ID"]
    secret = os.environ["DATABRICKS_CLIENT_SECRET"]

    def provider():
        return oauth_service_principal(
            Config(host=f"https://{host}", client_id=cid, client_secret=secret))

    return sql.connect(server_hostname=host,
                       http_path=os.environ["DATABRICKS_HTTP_PATH"],
                       credentials_provider=provider)


def _rows(query: str, limit: int = MAX_ROWS) -> dict:
    """Результат запроса или текст ошибки в том же виде.

    Исключение драйвера наружу не пускаем: у инструмента MCP оно
    превращается в падение вызова, и вместо «таблицы нет» модель видит
    трассировку на двадцать строк. Первая же проверка на живом складе
    напоролась именно на это."""
    try:
        with _connect() as con, con.cursor() as cur:
            cur.execute(query)
            cols = [d[0] for d in cur.description] if cur.description else []
            data = cur.fetchmany(limit) if cols else []
    except Exception as e:
        first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        return {"error": first, "query": query}
    return {"columns": cols,
            "rows": [[None if v is None else str(v) for v in r] for r in data],
            "row_count": len(data),
            "truncated": len(data) >= limit}


@mcp.tool()
def list_catalogs() -> dict:
    """Каталоги, видимые service principal."""
    return _rows("SHOW CATALOGS")


@mcp.tool()
def list_schemas(catalog: str) -> dict:
    """Схемы в каталоге."""
    return _rows(f"SHOW SCHEMAS IN {catalog}")


@mcp.tool()
def list_tables(catalog: str, schema: str) -> dict:
    """Таблицы и представления в схеме."""
    return _rows(f"SHOW TABLES IN {catalog}.{schema}")


@mcp.tool()
def describe_table(catalog: str, schema: str, table: str) -> dict:
    """Колонки таблицы с типами."""
    return _rows(f"DESCRIBE TABLE {catalog}.{schema}.{table}")


@mcp.tool()
def run_query(query: str, limit: int = MAX_ROWS) -> dict:
    """Выполняет запрос на чтение.

    Всё, что не SELECT / SHOW / DESCRIBE / WITH / EXPLAIN, отклоняется
    до отправки на склад, с объяснением причины."""
    try:
        safe = guard(query)
    except Refused as e:
        return {"error": str(e), "query": query}
    return _rows(safe, min(int(limit or MAX_ROWS), MAX_ROWS))


if __name__ == "__main__":
    mcp.run()
