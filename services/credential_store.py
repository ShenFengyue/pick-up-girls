"""Store the app's DeepSeek API key in the operating system credential vault."""

from __future__ import annotations

import os
from typing import Any


SERVICE_NAME = "pick-up-chat-simulator"
CREDENTIAL_NAME = "deepseek-api-key"


class CredentialStoreError(RuntimeError):
    """Raised when the OS credential vault is unavailable or rejects an operation."""


def _backend() -> Any:
    try:
        if os.name == "nt":
            from keyring.backends.Windows import WinVaultKeyring

            return WinVaultKeyring()

        import keyring

        return keyring.get_keyring()
    except Exception as exc:
        raise CredentialStoreError(
            "无法访问本机安全凭据库。请重新启动应用，或检查 keyring 依赖是否安装。"
        ) from exc


def get_saved_api_key() -> str | None:
    try:
        return _backend().get_password(SERVICE_NAME, CREDENTIAL_NAME)
    except CredentialStoreError:
        raise
    except Exception as exc:
        raise CredentialStoreError("读取本机已保存的 API Key 失败。") from exc


def save_api_key(api_key: str) -> None:
    value = api_key.strip()
    if not value:
        raise ValueError("API Key 不能为空。")

    try:
        backend = _backend()
        backend.set_password(SERVICE_NAME, CREDENTIAL_NAME, value)
        if backend.get_password(SERVICE_NAME, CREDENTIAL_NAME) != value:
            raise CredentialStoreError("本机安全凭据库未能确认保存结果，请重试。")
    except CredentialStoreError:
        raise
    except Exception as exc:
        raise CredentialStoreError("保存到本机安全凭据库失败。") from exc


def delete_saved_api_key() -> None:
    try:
        backend = _backend()
        if backend.get_password(SERVICE_NAME, CREDENTIAL_NAME) is not None:
            backend.delete_password(SERVICE_NAME, CREDENTIAL_NAME)
    except CredentialStoreError:
        raise
    except Exception as exc:
        raise CredentialStoreError("删除本机已保存的 API Key 失败。") from exc
