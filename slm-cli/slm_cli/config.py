"""Configuration management for Sealevel CLI.

Non-secret config lives in ~/.slm/config.toml (or SLM_CONFIG_DIR env var).
API key is stored in the OS keyring (macOS Keychain, Windows Credential Locker,
GNOME keyring, KWallet) when `keyring` is installed. Falls back to TOML otherwise.
"""
import os
from pathlib import Path

DEFAULT_CONFIG: dict[str, str] = {
    "api_url": "https://api.sealevel.tech",
    "mode": "quality",
}

# Key for OS keyring storage
_KEYRING_SERVICE = "slm-cli"
_KEYRING_USER = "default"
_SECRET_KEYS = {"api_key"}


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False


def _keyring_get() -> str | None:
    try:
        import keyring
        return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        return None


def _keyring_set(value: str) -> bool:
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, value)
        return True
    except Exception:
        return False


def _keyring_delete() -> None:
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        pass


def _get_config_dir(config_dir: str | None = None) -> Path:
    """Get the config directory path."""
    if config_dir:
        return Path(config_dir)
    env_dir = os.environ.get("SLM_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".slm"


def _config_file(config_dir: str | None = None) -> Path:
    """Get the config file path."""
    return _get_config_dir(config_dir) / "config.toml"


def _parse_toml(text: str) -> dict[str, str]:
    """Simple TOML parser for flat key-value pairs."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
    return result


def _to_toml(data: dict[str, str]) -> str:
    """Simple TOML serializer for flat key-value pairs."""
    lines: list[str] = []
    for key, value in sorted(data.items()):
        lines.append(f'{key} = "{value}"')
    return "\n".join(lines) + "\n"


def load_config(config_dir: str | None = None) -> dict[str, str]:
    """Load config from disk, returning defaults if file doesn't exist."""
    path = _config_file(config_dir)
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    text = path.read_text(encoding="utf-8")
    loaded = _parse_toml(text)
    # Merge with defaults
    merged = dict(DEFAULT_CONFIG)
    merged.update(loaded)
    return merged


def save_config(data: dict[str, str], config_dir: str | None = None) -> None:
    """Save config dict to disk."""
    path = _config_file(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_toml(data), encoding="utf-8")


def get_value(key: str, config_dir: str | None = None) -> str | None:
    """Get a single config value. Secrets prefer the OS keyring."""
    if key in _SECRET_KEYS and _keyring_available():
        v = _keyring_get()
        if v:
            return v
    config = load_config(config_dir)
    return config.get(key)


def set_value(key: str, value: str, config_dir: str | None = None) -> None:
    """Set a single config value. Secrets go to the OS keyring when available."""
    if key in _SECRET_KEYS and _keyring_available() and _keyring_set(value):
        # Remove any stale plaintext copy
        config = load_config(config_dir)
        if key in config:
            del config[key]
            save_config(config, config_dir)
        return
    config = load_config(config_dir)
    config[key] = value
    save_config(config, config_dir)


def clear_value(key: str, config_dir: str | None = None) -> None:
    """Remove a config value from both keyring and TOML."""
    if key in _SECRET_KEYS and _keyring_available():
        _keyring_delete()
    config = load_config(config_dir)
    if key in config:
        del config[key]
        save_config(config, config_dir)
