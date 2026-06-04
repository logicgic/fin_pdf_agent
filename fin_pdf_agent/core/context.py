from dataclasses import dataclass

from .memory import Memorystore
from .path import prompt_dir
from .tools import ToolLoader


@dataclass
class agentContext:

    def __init__(
        self,
        memory_store: Memorystore,
        workspace_dir: str,
        tools_loader: ToolLoader,
    ):
        self.memory = memory_store
        self.workspace_dir = workspace_dir
        self.tools = tools_loader

    def build_system_prompt(self) -> str:
        """构建系统提示词"""
        prompt = (prompt_dir / "system_prompt.md").read_text(encoding="utf-8")
        return f"{prompt}\n\n## 工作目录\n{self.workspace_dir}"

    def build_sandbox_instructions(self) -> str:
        return (
            f"{self.build_system_prompt()}\n\n"
            "# 沙箱规则\n"
            "- 只能在沙箱工作区内处理文件。\n"
            "- 财报和输入资料位于 repo/。\n"
            "- 分析结果写入 output/。\n"
            "- 不要访问互联网。\n"
            "- 优先生成结构化结果，例如 Markdown、JSON 或 CSV。\n"
            "- 最终回答要说明读取了什么、生成了什么。"
        )

    def build_local_instructions(self) -> str:
        return (
            f"{self.build_system_prompt()}\n\n"
            "# 本地规则\n"
            "- 可以使用 read_file、write_file、edit_file 处理文件。\n"
            "- 只处理工作目录内的文件。\n"
            "- 优先生成结构化结果，例如 Markdown、JSON 或 CSV。"
        )

    def build_context(self):
        """构建agent的上下文，包含系统提示词，长期记忆，技能列表，工具列表等"""
        return {
            "system_prompt": self.build_system_prompt(),
            "memory": self.memory.get_memory(),
        }

