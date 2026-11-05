from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class TextLengthTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        text = str(tool_parameters.get("text") or "")
        length = len(text)

        yield self.create_json_message(
            {
                "length": length,
                "message": f"文本长度为 {length} 个字符",
            }
        )
