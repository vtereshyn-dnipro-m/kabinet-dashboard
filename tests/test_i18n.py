"""Словарь переводов: у каждого ключа три языка и одинаковые подстановки, и каждый ключ объявлен один раз.

Ключ без одного из языков в английском интерфейсе печатается по-русски или самим ключом; разные подстановки
(`{d}` в русском и `{days}` в английском) ронят `t()` с KeyError только в том языке — такое находили глазами.
Повтор ключа в литерале словаря Python молча схлопывает: побеждает последнее объявление, и правка первого не
действует — так `stock.cov.filter_all` был объявлен дважды (убран в #380). Повторы видны только в тексте файла,
поэтому их ищем разбором исходника, а не по готовому словарю.
"""
import ast
import os
import re

from i18n import TRANSLATIONS

LANGS = ("ru", "uk", "en")
PLACEHOLDER = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)[^{}]*\}(?!\})")


def test_every_key_has_three_languages():
    missing = [f"{k}: нет {l}" for k, v in TRANSLATIONS.items() for l in LANGS
               if not isinstance(v, dict) or not str(v.get(l) or "").strip()]
    assert not missing, f"{len(missing)} ключей без языка, например: {missing[:10]}"


def test_placeholders_match_across_languages():
    bad = []
    for k, v in TRANSLATIONS.items():
        if not isinstance(v, dict):
            continue
        sets = {l: set(PLACEHOLDER.findall(str(v.get(l) or ""))) for l in LANGS}
        if len({frozenset(s) for s in sets.values()}) > 1:
            bad.append(f"{k}: " + ", ".join(f"{l}={sorted(s)}" for l, s in sets.items()))
    assert not bad, f"{len(bad)} ключей с разными подстановками, например: {bad[:10]}"


def test_no_duplicate_keys():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "i18n.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    node = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(tg, ast.Name) and tg.id == "TRANSLATIONS" for tg in n.targets))
    assert isinstance(node, ast.Dict)
    seen, dups = {}, []
    for k in node.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            if k.value in seen:
                dups.append(f"{k.value}: строки {seen[k.value]} и {k.lineno}")
            else:
                seen[k.value] = k.lineno
    assert not dups, f"{len(dups)} ключей объявлены дважды, например: {dups[:10]}"
