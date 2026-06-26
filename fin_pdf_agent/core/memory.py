from pathlib import Path
from typing import cast

from agents import Agent
from agents.extensions.memory import AdvancedSQLiteSession
from agents.items import TResponseInputItem
from agents.extensions.memory import AdvancedSQLiteSession
from agents.memory import SessionSettings

from .path import database_dir


class Memorystore:
    def __init__(self, db_path: str | Path = database_dir / "sessions.db"):
        """memory实例变量用于存储长期记忆，目前未实现"""
        self.memory = []
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, AdvancedSQLiteSession] = {}
        self.task_states: dict[str, dict[str, list[str]]] = {}
        self.MAX_TOKENS = 125000

    def get_memory(self):
        """获取长期记忆，目前未实现"""
        return self.memory

    def get_task_state(self, conversation_id: str) -> dict[str, list[str]]:
        """获取当前会话的结构化任务状态。"""
        return self.task_states.setdefault(
            conversation_id,
            {
                "parsed_files": [],
                "generated_outputs": [],
                "confirmed_metrics": [],
            },
        )

    def update_task_state(
        self,
        conversation_id: str,
        *,
        parsed_file: str | None = None,
        generated_output: str | None = None,
        confirmed_metric: str | None = None,
    ) -> None:
        """更新当前会话的结构化任务状态。"""
        state = self.get_task_state(conversation_id)
        updates = {
            "parsed_files": parsed_file,
            "generated_outputs": generated_output,
            "confirmed_metrics": confirmed_metric,
        }

        for field, value in updates.items():
            if value and value not in state[field]:
                state[field].append(value)

    def get_session(
        self,
        conversation_id: str,
        session_type: str = "sqlite",
    ) -> AdvancedSQLiteSession:
        """
        根据会话 ID 获取或创建一个 Session。
        Args:
            conversation_id: 会话唯一标识
            session_type: "sqlite" 
        """
        session_id = f"conversation:{conversation_id}"
        if session_type == "sqlite":
            if session_id not in self.sessions:
                self.sessions[session_id] = AdvancedSQLiteSession(
                    session_id=session_id,
                    db_path=self.db_path,
                    create_tables=True,
                    session_settings=SessionSettings(limit=50),
                )
            return self.sessions[session_id]

        raise ValueError(f"Unknown session type: {session_type}")

    async def close(self):
        """关闭已缓存的 Session 数据库连接。"""
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()
        self.task_states.clear()

    def build_task_state_summary(self, conversation_id: str) -> str:
        """将结构化任务状态整理为可保留的上下文摘要。"""
        state = self.get_task_state(conversation_id)
        blocks = ["[结构化任务状态]"]
        labels = {
            "parsed_files": "本次已解析文件",
            "generated_outputs": "本次已生成中间结果",
            "confirmed_metrics": "本次已确认指标",
        }

        for field in ["parsed_files", "generated_outputs", "confirmed_metrics"]:
            blocks.append(f"{labels[field]}:")
            values = state[field]
            if values:
                blocks.extend(f"- {value}" for value in values)
            else:
                blocks.append("- 无")

        return "\n".join(blocks)

    async def compact_session(
        self,
        session: AdvancedSQLiteSession,
        model: str,
        conversation_id: str,
    ) -> None:
        """压缩会话，保留最近30条消息"""
        items = await session.get_items()
        if len(items) < 30:
            return

        from agents import Runner

        keep_last_n = 12
        old_items = items[:-keep_last_n]
        recent_items = items[-keep_last_n:]

        if not old_items:
            return

        summarizer = Agent(
            name="session_summarizer",
            instructions=(
                "总结以下会话历史，保留：\n"
                "1. 用户目标\n"
                "2. 已确认的事实\n"
                "3. 已完成的工作\n"
                "4. 未完成事项\n"
                "5. 关键文件/数据/约束\n"
                "要求简洁，适合作为后续上下文。"
            ),
            model=model,
        )
        result = await Runner.run(
            starting_agent=summarizer,
            input=old_items,
        )
        summary_text = result.final_output
        task_state_summary = self.build_task_state_summary(conversation_id)

        summary_item = cast(
            TResponseInputItem,
            {
                "type": "message",
                "role": "assistant",
                "content": (
                    f"[会话摘要，供后续上下文参考]\n{summary_text}\n\n"
                    f"{task_state_summary}"
                ),
            },
        )

        await session.clear_session()
        await session.add_items([summary_item, *recent_items])

    def token_count(self):
        """计算长期记忆的token数量，目前未实现"""
        return 0
