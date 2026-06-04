from pathlib import Path

from agents.memory import SessionSettings
from agents.extensions.memory import AdvancedSQLiteSession

from .path import database_dir


class Memorystore:
    def __init__(self, db_path: str | Path = database_dir / "sessions.db"):
        """memory实例变量用于存储长期记忆，目前未实现"""
        self.memory = []
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, AdvancedSQLiteSession] = {}

    def get_memory(self):
        """获取长期记忆，目前未实现"""
        return self.memory

    def get_session(
        self,
        user_id: str,
        session_type: str = "sqlite",
    ) -> AdvancedSQLiteSession:
        """
        根据用户 ID 获取或创建一个 Session。
        Args:
            user_id: 用户唯一标识 (如 "user_123")
            session_type: "sqlite" 
        """
        session_id = f"agent_session:{user_id}"
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

    def zip_memory(self):
        """压缩长期记忆，目前未实现"""
        pass

    def token_count(self):
        """计算长期记忆的token数量，目前未实现"""
        return 0
