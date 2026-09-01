# -*- coding: utf-8 -*-
# Module: auth.py
"""
openSquat API key resolution.

Resolves the openSquat API key from one of three sources, in priority order:
    1. CLI value (--api-key flag)
    2. Environment variable (OPENSQUAT_API_KEY)
    3. Key file in CWD (api_key.txt)

This module is intentionally a clean rewrite — it does not call into vt.py,
which has known key-loading bugs (last-line overwrite, no .strip(), no
empty-file guard).
"""
import os


DEFAULT_KEY_FILE = "api_key.txt"
DEFAULT_ENV_VAR = "OPENSQUAT_API_KEY"


class AuthError(Exception):
    """Raised when no usable API key can be resolved."""


def load_api_key(cli_value=None, key_file=DEFAULT_KEY_FILE, env_var=DEFAULT_ENV_VAR):
    """
    Resolve the openSquat API key from CLI > env var > key file.

    Args:
        cli_value: value from --api-key flag, or None/empty
        key_file: path to the key file (default: api_key.txt in CWD)
        env_var: environment variable name (default: OPENSQUAT_API_KEY)

    Returns:
        str: the resolved API key

    Raises:
        AuthError: when no usable key can be found in any source
    """
    if cli_value:
        cli_value = cli_value.strip()
        if cli_value:
            return cli_value

    env_value = os.environ.get(env_var, "").strip()
    if env_value:
        return env_value

    if os.path.isfile(key_file):
        try:
            file_value = _read_first_usable_line(key_file)
        except OSError as e:
            raise AuthError(
                f"Could not read API key file '{key_file}': {e}"
            )
        if file_value:
            return file_value

    raise AuthError(
        "No openSquat API key found. Tried (in order):\n"
        f"  1. --api-key CLI flag\n"
        f"  2. ${env_var} environment variable\n"
        f"  3. {key_file} (in current directory)\n"
        "Get a key at https://opensquat.com"
    )


def _read_first_usable_line(path):
    """
    Return the first non-comment, non-blank, stripped line of a text file.
    Returns None if no usable line is found.
    """
    with open(path, mode='r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def mask_key(key):
    """
    Mask an API key for safe display in error messages and logs.
    Returns 'os_abcde...wxyz' style for keys long enough, otherwise '***'.
    """
    if not key or len(key) < 12:
        return "***"
    return f"{key[:5]}...{key[-4:]}"
