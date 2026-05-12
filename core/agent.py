import asyncio

from agents import Agent, Runner
from openai import AsyncOpenAI
from agents import set_default_openai_client
from  memory import Memorystore
from  context import agentContext
from  tools import toolLoader
from  skills import SkillLoader

import os
class PDFAgent:
    """agent会使用openai官方agent sdk,封装了agent的运行组件,包括工具tools，工作目录workspace，技能skills等"""
    def __init__(self, workspace_dir: str, openai_api_key: str = None, base_url: str = None, model: str = "deepseek-v4-flash"):
        """
        初始化agent
        openai_api_key需要兼容openai接口的apikey,可使用环境变量 OPENAI_API_KEY 作为备用。
        base_url: OpenAI 兼容接口的代理/服务地址.
        workspace:用于获取pdf和输出ai操作的结果的地方。
        """
        self.workspace_dir=workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)
        
        
        api_key=os.environ.get("OPENAI_API_KEY") or openai_api_key
        if not api_key:
            raise ValueError("未提供api或者环境变量中未设置OPENAI_API_KEY")      
    

        self.base_url=base_url or os.environ.get("OPENAI_BASE_URL")
        if not self.base_url:
            raise ValueError("未提供base_url或者环境变量中未设置OPENAI_BASE_URL")

        custom_client = AsyncOpenAI(base_url=self.base_url, api_key=api_key)
        set_default_openai_client(custom_client)
        
            
        self.model=model
        # 初始化可用的tools列表,skills列表，构建上下文
        
        tools_loader = toolLoader()
        skills_loader = SkillLoader()
        memory_store = Memorystore()
        context_builder = agentContext(
            memory_store=memory_store,
            skills_loader=skills_loader,
            workspace_dir=self.workspace_dir,
            tools_loader=tools_loader,
        )

        self.tool_list = tools_loader.get_tool()
        self.skill_list = skills_loader.get_skills()
        self.contexts = context_builder.build_context()


        self.agent = Agent(
            name="pdf_agent",
            instructions="财报分析师，目前只用回答用户的问题",
            model=self.model,
            tools=None,
        )

        # 封装了agent的运行的主要组件
        async def chat(question:str):
            """
            核心的对外交互接口。
            1. 拿到用户的当前问题。
            2. 将问题连同历史记录、系统提示组装成一整条消息 Payload：`messages`。

            """


            result = await Runner.run_streamed(self.agent, question,context=self.contexts)
            print(result.final_output)
