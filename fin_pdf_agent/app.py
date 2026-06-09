from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import fastapi
import yaml
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fin_pdf_agent.core.agent import PDFAgent
from fin_pdf_agent.core.path import config_path, static_dir, workspace_dir
from fin_pdf_agent.core.skills import SkillLoader

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
    use_sandbox=llm_config.get("use_sandbox", False),
)


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    yield
    await agent.close()


app = fastapi.FastAPI(title="fin_agent_backend", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class ConversationCreateResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: str


@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def root():
    return {"message": "正常"}


@app.post("/chat")
async def chat(request: ChatRequest):
    answer = await agent.chat(request.message, conversation_id=request.conversation_id)
    return {"answer": answer}


@app.post("/conversations")
async def create_conversation():
    conversation_id = uuid4().hex
    agent.memory_store.get_session(conversation_id)
    return ConversationCreateResponse(
        conversation_id=conversation_id,
        title="新会话",
        created_at=datetime.now(UTC).isoformat(),
    )


@app.get("/workspace-state")
async def workspace_state():
    skills = SkillLoader().list_skills()
    tools = [{"name": tool.name} for tool in agent.tool_list]
    files = [
        {
            "name": path.name,
            "path": str(path.relative_to(workspace_dir)),
            "size": path.stat().st_size,
        }
        for path in sorted(workspace_dir.rglob("*"))
        if path.is_file()
    ]
    return {"skills": skills, "tools": tools, "files": files}


@app.get("/test")
async def test():
    answer = await agent.chat("你好,这是一次测试", conversation_id="test")
    return {"answer": answer}
