from dataclasses import dataclass
import os
import json
from .memory import Memorystore
from .tools import ToolLoader
from .path import prompt_dir
@dataclass
class agentContext:

    def __init__(self,memory_store:Memorystore, workspace_dir: str,tools_loader: ToolLoader):
        self.memory=memory_store
        self.workspace_dir = workspace_dir
        self.tools = tools_loader

    def build_system_prompt(self) -> str:
        """构建系统提示词"""
        sys_prompt=[]
        try:
            with open(os.path.join(prompt_dir, "system_prompt.md"), "r", encoding="utf-8") as f:
                sys_prompt.append(f.read())
        except Exception as e:
            print(f"读取系统提示词文件失败: {e}")
        
        if(self.tools):
            sys_prompt.append(f"""
            以下是agent可用的工具列表：tools：{self.tools.get_tools()}                              
            """)

        if(self.memory):
            sys_prompt.append(f"""
            以下是agent的长期记忆：memory：{self.memory.get_memory()}                              
            """)

        if(self.workspace_dir):
            sys_prompt.append(f"你的工作目录，你生成的文件将保存在这里：{self.workspace_dir}")    
        
        return "\n---\n".join(sys_prompt)
    
    def build_context(self):
        """构建agent的上下文，包含系统提示词，长期记忆，技能列表，工具列表等"""
        context={}
        system_prompt=self.build_system_prompt()
        memory_context=self.memory.get_memory() if self.memory else None

        context["system_prompt"]=system_prompt
        context["memory"]=memory_context

        return context
    
    
        

