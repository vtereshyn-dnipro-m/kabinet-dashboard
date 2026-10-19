"""Словарь переводов: у каждого ключа три языка и одинаковые подстановки.

Ключ без одного из языков в английском интерфейсе печатается по-русски или самим ключом; разные подстановки
(`{d}` в русском и `{days}` в английском) ронят `t()` с KeyError только в том языке — такое находили глазами.
"""
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
