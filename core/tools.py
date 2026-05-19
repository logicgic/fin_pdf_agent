from pathlib import Path

from agents import Tool, function_tool


@function_tool
def read_file(file_path: str, max_chars: int = 12000) -> str:
    """读取指定文件的文本内容。
    Args:
        file_path: 要读取的文件路径。
        max_chars: 最大读取字符数，文件过大时会截断。
    Returns:
        文件内容；如果内容被截断，会在末尾追加提示。
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n[内容过长，已截断]"


@function_tool
def write_file(file_path: str, content: str) -> str:
    """将内容写入指定文件。
    Args:
        file_path: 要写入的文件路径。
        content: 要写入的文本内容。
    Returns:
        写入成功提示。
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"已写入文件: {path}"


@function_tool
def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """通过字符串替换编辑指定文件。
    Args:
        file_path: 要编辑的文件路径。
        old_text: 需要查找的旧字符串。
        new_text: 用于替换的新字符串。
    Returns:
        编辑成功提示。

    Raises:
        ValueError: 当旧字符串为空或未找到时抛出。
    """
    if not old_text:
        raise ValueError("old_text不能为空")

    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    if old_text not in content:
        raise ValueError("未找到要替换的旧字符串")

    path.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return f"已编辑文件: {path}"


class ToolLoader:
    """
    工具加载器，负责加载和管理可用工具。在chat/compositions中,无法使用WebSearchTool，FileSearchTool等openai内置的工具，所以通过@function_tool手写 FunctionTool 这一类函数工具。
    """
    def __init__(self):
        self.toolslist: list[Tool] = [read_file, write_file, edit_file]

    def get_tools(self):
        """返回可用工具。"""
        return self.toolslist
