from pathlib import Path

from agents import Tool, function_tool
from markitdown import MarkItDown

from .path import HOST_PARSED_DOCS_DIR, HOST_REPO_DIR


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

@function_tool
def parse_document_to_md(file_path: str) -> str:
    """
    使用微软的markItDown库 将 repo 目录中的文件转换为 markdown 文件，方便ai用来分析。
    Args:
        file_path: repo 目录内的文件相对路径。
    Returns:
        转换后的 markdown 文件路径。
    """
    source_path = HOST_REPO_DIR / file_path
    target_path = (HOST_PARSED_DOCS_DIR / file_path).with_suffix(".md")

    # 解析结果统一写入 workspace/parsed_docs，便于和其他输出区分。
    result = MarkItDown().convert(source_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(result.markdown, encoding="utf-8")
    return f"已生成 markdown 文件: {target_path}"


def _extract_financial_statements(content: str) -> str:
    """从 markdown 中提取三张主表内容。"""
    statement_titles = ["资产负债表", "利润表", "现金流量表"]
    lines = content.splitlines()
    statement_indexes = [
        next(index for index, line in enumerate(lines) if title in line)
        for title in statement_titles
    ]
    sections = []
    for index, start in enumerate(statement_indexes):
        end = statement_indexes[index + 1] if index + 1 < len(statement_indexes) else len(lines)
        sections.append("\n".join(lines[start:end]).strip())
    return "\n\n".join(sections)


@function_tool
def prepare_report_markdown(report_name: str, max_chars: int = 20000) -> str:
    """查找财报并准备可直接分析的 markdown 内容。
    Args:
        report_name: 财报文件名或关键字。
        max_chars: 最大返回字符数，内容过长时只返回三张主表。
    Returns:
        可直接用于分析的 markdown 内容。
    """
    source_path = next(
        path
        for path in HOST_REPO_DIR.rglob("*")
        if path.is_file() and report_name in path.name
    )

    if source_path.suffix.lower() == ".md":
        md_path = source_path
    else:
        md_path = (
            HOST_PARSED_DOCS_DIR / source_path.relative_to(HOST_REPO_DIR)
        ).with_suffix(".md")

        # 已经解析过的财报直接复用，避免重复转换。
        if not md_path.exists():
            result = MarkItDown().convert(source_path)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(result.markdown, encoding="utf-8")

    content = md_path.read_text(encoding="utf-8")
    if len(content) <= max_chars:
        return content

    # 财报过长时，只保留资产负债表、利润表和现金流量表。
    return _extract_financial_statements(content)

class ToolLoader:
    """
    工具加载器，负责加载和管理可用工具。在chat/compositions中,无法使用WebSearchTool，FileSearchTool等openai内置的工具，所以通过@function_tool手写 FunctionTool 这一类函数工具。
    """
    def __init__(self):
        self.toolslist: list[Tool] = [
            read_file,
            write_file,
            edit_file,
            parse_document_to_md,
            prepare_report_markdown,
        ]

    def get_tools(self):
        """返回可用工具。"""
        return self.toolslist
