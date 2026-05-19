# run_agent.py
import asyncio
from core.agent import PDFAgent
from core.path import workspace_dir
import os
import yaml

async def main():
    config_path = "config.yaml"
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    llm_config = config.get("llm", {})
    api_key = llm_config.get("api_key", "")
    base_url = llm_config.get("base_url", "")
    model = llm_config.get("model")
    agent = PDFAgent(
        workspace_dir=workspace_dir,
        openai_api_key=api_key,
        base_url=base_url,
        model=model
    )
    await agent.chat("你好,这是一次测试")
    
asyncio.run(main())