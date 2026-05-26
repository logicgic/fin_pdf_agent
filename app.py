import os
import fastapi
import yaml
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.agent import PDFAgent
from core.path import PROJECT_DIR, workspace_dir

#加载配置文件
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
    model=model,
    use_sandbox=True,
)
app = fastapi.FastAPI(title="fin_agent_backend")
app.mount("/static", StaticFiles(directory=PROJECT_DIR / "static"), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/")
async def index():
    return FileResponse(PROJECT_DIR / "static" / "index.html")


@app.get("/health")
async def root():
    return {"message": "正常"}


@app.post("/chat")
async def chat(request: ChatRequest):
    answer = await agent.chat(request.message)
    return {"answer": answer}


@app.get("/test")
async def test():
    answer = await agent.chat("你好,这是一次测试")
    return {"answer": answer}
