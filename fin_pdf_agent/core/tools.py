import re
from pathlib import Path
from typing import Callable

from agents import Tool, function_tool
from markitdown import MarkItDown

from .path import HOST_PARSED_DOCS_DIR, HOST_REPO_DIR, workspace_dir

TaskStateRecorder = Callable[[str, str], None]
_task_state_recorder: TaskStateRecorder | None = None


def set_task_state_recorder(recorder: TaskStateRecorder | None) -> None:
    """注册任务状态记录器。"""
    global _task_state_recorder
    _task_state_recorder = recorder


def _record_task_state(tool_name: str, value: str) -> None:
    """记录工具执行后的结构化任务状态。"""
    if _task_state_recorder is not None:
        _task_state_recorder(tool_name, value)


def _raise_tool_error(message: str, exc: Exception | None = None) -> None:
    """抛出统一的业务化工具错误。"""
    if exc is None:
        raise ValueError(message)
    raise ValueError(message) from exc


def _resolve_workspace_path(file_path: str) -> Path:
    """将传入路径解析为 workspace 内的绝对路径。"""
    raw_path = Path(file_path)
    base_dir = workspace_dir.resolve()

    if raw_path.is_absolute():
        resolved_path = raw_path.resolve()
    else:
        parts = raw_path.parts
        if parts and parts[0] == workspace_dir.name:
            raw_path = Path(*parts[1:])
        resolved_path = (base_dir / raw_path).resolve()

    try:
        resolved_path.relative_to(base_dir)
    except ValueError as exc:
        _raise_tool_error("禁止访问 workspace 目录外的文件。", exc)

    return resolved_path


@function_tool
def read_file(file_path: str, max_chars: int = 12000) -> str:
    """读取指定文件的文本内容。
    Args:
        file_path: 要读取的文件路径。
        max_chars: 最大读取字符数，文件过大时会截断。
    Returns:
        文件内容；如果内容被截断，会在末尾追加提示。
    """
    path = _resolve_workspace_path(file_path)
    if not path.exists() or not path.is_file():
        _raise_tool_error(f"未找到文件: {file_path}。请确认文件位于 workspace 目录内。")
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
    path = _resolve_workspace_path(file_path)
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

    path = _resolve_workspace_path(file_path)
    if not path.exists() or not path.is_file():
        _raise_tool_error(f"未找到文件: {file_path}。请确认文件位于 workspace 目录内。")
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
    if not source_path.exists() or not source_path.is_file():
        _raise_tool_error(f"未找到文件: {file_path}。请确认文件已放入 workspace/repo 目录。")

    target_path = (HOST_PARSED_DOCS_DIR / file_path).with_suffix(".md")

    # 解析结果统一写入 workspace/parsed_docs，便于和其他输出区分。
    try:
        result = MarkItDown().convert(source_path)
    except Exception as exc:
        _raise_tool_error(
            f"财报解析失败: {source_path.name}。请检查文件格式是否受支持，或确认文件未损坏。",
            exc,
        )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(result.markdown, encoding="utf-8")
    _record_task_state("parse_document_to_md", str(target_path))
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
        if index + 1 < len(statement_indexes):
            end = statement_indexes[index + 1]
        else:
            end = len(lines)
        sections.append("\n".join(lines[start:end]).strip())
    return "\n\n".join(sections)


def _extract_report_metadata(content: str, source_path: Path) -> dict[str, str]:
    """从 markdown 中提取基础财报信息。"""
    metadata = {"文件名": source_path.name}
    patterns = {
        "公司名称": r"(?:公司名称|企业名称)[：:\s]+(.+)",
        "报告期": r"(?:报告期|报告期间)[：:\s]+(.+)",
        "币种": r"(?:币种|货币单位)[：:\s]+(.+)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            metadata[field] = match.group(1).strip()

    return metadata


def _extract_statement_sections(content: str) -> dict[str, str]:
    """从 markdown 中提取三张主表内容，按标题返回。"""
    statement_titles = ["资产负债表", "利润表", "现金流量表"]
    lines = content.splitlines()
    sections: dict[str, str] = {}

    try:
        for index, title in enumerate(statement_titles):
            start = next(i for i, line in enumerate(lines) if title in line)
            if index + 1 < len(statement_titles):
                next_title = statement_titles[index + 1]
                end = next(
                    i
                    for i, line in enumerate(lines[start + 1 :], start + 1)
                    if next_title in line
                )
            else:
                end = len(lines)
            sections[title] = "\n".join(lines[start:end]).strip()
    except StopIteration as exc:
        _raise_tool_error(
            "已生成 markdown，但未完整识别资产负债表、利润表、现金流量表。",
            exc,
        )

    return sections


def _build_structured_report_content(content: str, source_path: Path) -> str:
    """将财报 markdown 整理为更适合模型分析的结构化文本。"""
    metadata = _extract_report_metadata(content, source_path)
    sections = _extract_statement_sections(content)
    blocks = ["## 报告信息"]
    blocks.extend(f"- {key}: {value}" for key, value in metadata.items())

    for title in ["资产负债表", "利润表", "现金流量表"]:
        blocks.append(f"\n## {title}\n{sections[title]}")

    return "\n".join(blocks)


def _get_or_create_report_markdown(source_path: Path) -> Path:
    """返回财报对应的 markdown 文件，不存在则先生成。"""
    if source_path.suffix.lower() == ".md":
        return source_path

    md_path = (
        HOST_PARSED_DOCS_DIR / source_path.relative_to(HOST_REPO_DIR)
    ).with_suffix(".md")

    if not md_path.exists():
        try:
            result = MarkItDown().convert(source_path)
        except Exception as exc:
            _raise_tool_error(
                f"财报解析失败: {source_path.name}。请检查文件格式是否受支持，或确认文件未损坏。",
                exc,
            )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(result.markdown, encoding="utf-8")

    return md_path


def _find_report_file(report_name: str) -> Path:
    """按文件名或关键字查找财报文件。"""
    try:
        return next(
            path
            for path in HOST_REPO_DIR.rglob("*")
            if path.is_file() and report_name in path.name
        )
    except StopIteration as exc:
        _raise_tool_error(
            f"未找到名称包含 {report_name} 的财报文件。请确认文件已放入 workspace/repo 目录。",
            exc,
        )


@function_tool
def prepare_report_markdown(report_name: str, max_chars: int = 20000) -> str:
    """查找财报并准备可直接分析的 markdown 内容。
    Args:
        report_name: 财报文件名或关键字。
        max_chars: 最大返回字符数，内容过长时只返回三张主表。
    Returns:
        可直接用于分析的 markdown 内容。
    """
    source_path = _find_report_file(report_name)
    md_path = _get_or_create_report_markdown(source_path)

    content = md_path.read_text(encoding="utf-8")
    if len(content) <= max_chars:
        _record_task_state("prepare_report_markdown", source_path.name)
        return content

    # 财报过长时，只保留资产负债表、利润表和现金流量表。
    _record_task_state("prepare_report_markdown", source_path.name)
    return _extract_financial_statements(content)


@function_tool
def prepare_structured_report(report_name: str, max_chars: int = 24000) -> str:
    """查找财报并整理为结构化文本，优先提供给 AI 分析。"""
    source_path = _find_report_file(report_name)
    md_path = _get_or_create_report_markdown(source_path)
    content = md_path.read_text(encoding="utf-8")
    structured_content = _build_structured_report_content(content, source_path)

    if len(structured_content) <= max_chars:
        _record_task_state("prepare_structured_report", source_path.name)
        return structured_content

    sections = _extract_statement_sections(content)
    metadata = _extract_report_metadata(content, source_path)
    blocks = ["## 报告信息"]
    blocks.extend(f"- {key}: {value}" for key, value in metadata.items())

    for title in ["资产负债表", "利润表", "现金流量表"]:
        blocks.append(f"\n## {title}\n{sections[title]}")

    _record_task_state("prepare_structured_report", source_path.name)
    return "\n".join(blocks)[:max_chars] + "\n\n[内容过长，已截断]"

class ToolLoader:
    """
    工具加载器，负责加载和管理可用工具。
    在 chat/completions 中，无法使用 WebSearchTool、FileSearchTool
    等 openai 内置工具，所以通过 @function_tool 手写 FunctionTool。
    """
    def __init__(self):
        self.toolslist: list[Tool] = [
            read_file,
            write_file,
            edit_file,
            parse_document_to_md,
            prepare_report_markdown,
            prepare_structured_report,
        ]

    def get_tools(self):
        """返回可用工具。"""
        return self.toolslist


def update_task_state_from_result(
    memory_store,
    conversation_id: str,
    tool_name: str,
    result_text: str,
) -> None:
    """根据工具结果更新当前会话的结构化任务状态。"""
    if tool_name == "parse_document_to_md":
        path_text = result_text.removeprefix("已生成 markdown 文件: ").strip()
        memory_store.update_task_state(
            conversation_id,
            parsed_file=path_text,
            generated_output=path_text,
        )
        return

    if tool_name in {"prepare_report_markdown", "prepare_structured_report"}:
        memory_store.update_task_state(
            conversation_id,
            generated_output=f"{tool_name} 已生成可分析财报内容",
        )
