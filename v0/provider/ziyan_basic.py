from typing import Any

from dify_plugin import ToolProvider


class ZiyanBasicProvider(ToolProvider):
    """不需要任何 API 密钥。"""

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        return None
