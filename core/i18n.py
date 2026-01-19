"""
Internationalization (i18n) support for PaperJam.

Loads translations from YAML files in the locales directory.
Falls back to English if translation is missing.

Usage:
    from core.i18n import t
    label = t('player.status.playing')  # Returns "PLAYING"
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Default locale
DEFAULT_LOCALE = 'en'
_current_locale = DEFAULT_LOCALE
_translations: Dict[str, Dict[str, Any]] = {}


def _load_locale(locale: str) -> Dict[str, Any]:
    """Load translations for a locale from YAML file."""
    if not HAS_YAML:
        return {}

    locales_dir = Path(__file__).parent.parent / 'locales'
    locale_file = locales_dir / f'{locale}.yaml'

    if not locale_file.exists():
        return {}

    try:
        with open(locale_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def _get_nested(data: Dict[str, Any], key: str) -> Optional[str]:
    """Get a nested value from dict using dot notation."""
    keys = key.split('.')
    value = data

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None

    return str(value) if value is not None else None


def load_translations():
    """Load all available translations."""
    global _translations
    import logging
    logger = logging.getLogger(__name__)

    if not HAS_YAML:
        logger.warning("PyYAML not installed - translations unavailable")
        return

    locales_dir = Path(__file__).parent.parent / 'locales'
    if not locales_dir.exists():
        logger.warning(f"Locales directory not found: {locales_dir}")
        return

    for locale_file in locales_dir.glob('*.yaml'):
        locale = locale_file.stem
        _translations[locale] = _load_locale(locale)
        logger.info(f"Loaded locale: {locale} ({len(_translations[locale])} keys)")


def set_locale(locale: str):
    """Set the current locale."""
    global _current_locale
    if locale in _translations:
        _current_locale = locale
    elif locale == DEFAULT_LOCALE or not _translations:
        _current_locale = locale
        # Try to load it
        trans = _load_locale(locale)
        if trans:
            _translations[locale] = trans


def get_locale() -> str:
    """Get the current locale."""
    return _current_locale


def t(key: str, default: str = None, **kwargs) -> str:
    """Get a translated string.

    Args:
        key: Translation key in dot notation (e.g., 'player.status.playing')
        default: Default value if translation not found
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string or default/key if not found
    """
    # Try current locale
    if _current_locale in _translations:
        value = _get_nested(_translations[_current_locale], key)
        if value is not None:
            if kwargs:
                try:
                    return value.format(**kwargs)
                except (KeyError, ValueError):
                    pass
            return value

    # Try default locale as fallback
    if _current_locale != DEFAULT_LOCALE and DEFAULT_LOCALE in _translations:
        value = _get_nested(_translations[DEFAULT_LOCALE], key)
        if value is not None:
            if kwargs:
                try:
                    return value.format(**kwargs)
                except (KeyError, ValueError):
                    pass
            return value

    # Return default or key
    return default if default is not None else key.split('.')[-1]


def get_available_locales() -> list:
    """Get list of available locales."""
    return list(_translations.keys())


# Auto-load translations on import
load_translations()
