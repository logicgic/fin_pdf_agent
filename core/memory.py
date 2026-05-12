from agents import Agent,Session,Runner,MessageItem,RunConfig,Session,SQLiteSession,MemorySession
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
            session_type: "sqlite" | "memory"
        """
        session_id = f"agent_session:{user_id}"
        if session_type == "sqlite":
            # 开发环境：使用本地文件
            db_path = os.path.join(os.getcwd(), "database/sessions.db")
            return SQLiteSession(session_id=session_id, db_path=db_path)

        elif session_type == "memory":
            # 测试环境：内存存储，重启后数据丢失
            return MemorySession(session_id=session_id)
        else:
            raise ValueError(f"Unknown session type: {session_type}")

    async def smart_context_manager(history: list[Item], new_input: list[Item]) -> list[Item]:
        """超过20轮对话时，自动总结历史对话，保留摘要和最近的对话记录"""
        if len(history) > 20:  # 超过20轮对话
            # 取出前10轮让模型总结
            old_stuff = history[:10]
            summary_agent = Agent(name="Summarizer", instructions="Summarize the following conversation.")
            summary = await Runner.run(summary_agent, str(old_stuff)).final_output
            
            # 丢弃旧记录，替换为摘要
            recent_stuff = history[10:]
            history = [MessageItem(role="system", content=f"Previous summary: {summary}")] + recent_stuff
        
        return history + new_input

    config = RunConfig(session_input_callback=smart_context_manager)

    def clear_history(self):
        self.memory = []