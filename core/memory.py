from agents import Agent,Session,Runner,RunConfig,Session,SQLiteSession
from agents.extensions.memory import AdvancedSQLiteSession
import os
class Memorystore:
    def __init__(self):
        """memory实例变量用于存储长期记忆，目前未实现"""
        self.memory=[]


    def get_session(self,user_id: str, session_type: str = "sqlite") -> Session:
        """
        根据用户 ID 获取或创建一个 Session。
        Args:
            user_id: 用户唯一标识 (如 "user_123")
            session_type: "sqlite" 
        """
        session_id = f"agent_session:{user_id}"
        if session_type == "sqlite":
            # 开发环境：使用本地文件
            db_path = os.path.join(os.getcwd(), "database/sessions.db")
            return AdvancedSQLiteSession(session_id=session_id, db_path=db_path, create_tables=True)
        else:
            raise ValueError(f"Unknown session type: {session_type}")

        
        