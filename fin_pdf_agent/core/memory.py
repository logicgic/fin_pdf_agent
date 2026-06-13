from pathlib import Path
from typing import cast

from agents.memory import SessionSettings
from agents.extensions.memory import AdvancedSQLiteSession
from agents import Agent
from agents.items import TResponseInputItem
from .path import database_dir


class Memorystore:
    def __init__(self, db_path: str | Path = database_dir / "sessions.db"):
        """memory实例变量用于存储长期记忆，目前未实现"""
        self.memory = []
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, AdvancedSQLiteSession] = {}
        self.MAX_TOKENS = 125000

    def get_memory(self):
        """获取长期记忆，目前未实现"""
        return self.memory

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



    async def compact_session(self, session: AdvancedSQLiteSession,model: str) -> None:
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

        summary_item = cast(
            TResponseInputItem,
            {
                "type": "message",
            "role": "assistant",
                "content": f"[会话摘要，供后续上下文参考]\n{summary_text}",
            },
        )

        await session.clear_session()
        await session.add_items([summary_item, *recent_items])

    def _get_session_item(self,session: AdvancedSQLiteSession):
        """获取会话中的所有消息"""
        

    def token_count(self):
        """计算长期记忆的token数量，目前未实现"""
        return 0
