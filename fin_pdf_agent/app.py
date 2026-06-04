from contextlib import asynccontextmanager

import fastapi
import yaml
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fin_pdf_agent.core.agent import PDFAgent
from fin_pdf_agent.core.path import config_path, static_dir, workspace_dir

if config_path.exists():
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
else:
    config = {}

llm_config = config.get("llm", {})
agent = PDFAgent(
    workspace_dir=workspace_dir,
    openai_api_key=llm_config.get("api_key", ""),
    base_url=llm_config.get("base_url", ""),
    model=llm_config.get("model"),
    use_sandbox=True,
)


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    yield
    await agent.close()


app = fastapi.FastAPI(title="fin_agent_backend", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"


@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def root():
    return {"message": "正常"}


@app.post("/chat")
async def chat(request: ChatRequest):
    answer = await agent.chat(request.message, user_id=request.user_id)
    return {"answer": answer}


@app.get("/test")
async def test():
    answer = await agent.chat("你好,这是一次测试", user_id="001")
    return {"answer": answer}
