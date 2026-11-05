from typing import Any

from dify_plugin import ToolProvider


class ZiyanDataProvider(ToolProvider):
    """该插件不需要任何 API 密钥，凭据校验直接放行。"""

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        return None
