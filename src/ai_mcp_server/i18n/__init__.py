"""I18n: language detector (via $LANG) + string lookup.

Supported locales:
  "zh-sc" (zh_CN) → Simplified Chinese
  "zh-tc" (zh_TW, zh_HK) → Traditional Chinese
  "en" (anything else) → English
"""
from __future__ import annotations

import os
from typing import Any

from . import en, zh_sc, zh_tc

_locale_to_module = {
    "zh-sc": zh_sc,
    "zh-tc": zh_tc,
    "en": en,
}

_current_module = en


def detect_locale() -> str:
    lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "") or ""
    lang = lang.lower().split(".")[0]
    if lang in ("zh_cn", "zh-hans", "zh_hans_cn", "zh-hans-cn"):
        return "zh-sc"
    if lang in ("zh_tw", "zh_hk", "zh-hant", "zh_hant_tw", "zh-hant-tw", "zh-hant-hk"):
        return "zh-tc"
    return "en"


def set_locale(locale: str) -> None:
    global _current_module
    _current_module = _locale_to_module.get(locale, en)


def init() -> None:
    set_locale(detect_locale())


def t(key: str, **fmt: Any) -> str:
    val = _current_module.STRINGS.get(key, key)
    if fmt and isinstance(val, str):
        return val.format(**fmt)
    return val
