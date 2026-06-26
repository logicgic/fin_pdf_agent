# 财务报表解析智能体项目

本项目用于学习财报解析智能体的后端实现，当前提供 FastAPI 服务、会话记忆、基础工作区管理，以及可选的 sandbox agent 运行方式。

## 启动项目

### 1. 安装依赖

项目使用 `uv` 管理依赖：

```powershell
uv sync
```

如果没有安装 `uv`，先安装：

```powershell
pip install uv
```

### 2. 配置模型

模型密钥放在根目录 `.env` 中，不再写入 `config.yaml`。

先复制示例文件：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`：

```env
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=https://api.deepseek.com
LANGFUSE_PUBLIC_KEY=pk-lf-...           # 可选：Langfuse 项目公钥
LANGFUSE_SECRET_KEY=sk-lf-...           # 可选：Langfuse 项目私钥
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

`config.yaml` 只保留非敏感配置，例如模型名、接口地址、是否启用沙箱：

```yaml
llm:
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-flash"
  use_sandbox: false
```

当前配置规则：

- `OPENAI_API_KEY` 从 `.env` 读取
- `base_url` 优先从 `config.yaml` 读取，未配置时回退到 `.env` 中的 `OPENAI_BASE_URL`
- `model` 从 `config.yaml` 读取
- `use_sandbox` 从 `config.yaml` 读取
- Langfuse 开启条件：同时配置 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY` 和 `LANGFUSE_BASE_URL`
- Langfuse 会为每次 `/chat` 调用创建顶层 trace，并自动关联 OpenAI Agents SDK 的模型调用与工具调用
- 如需启动时做一次连通性校验，可额外设置 `LANGFUSE_AUTH_CHECK_ON_STARTUP=true`；生产环境默认建议保持关闭

### 3. 启动服务

```powershell
uv run uvicorn fin_pdf_agent.app:app --reload
```

启动后访问：

- 页面：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health`
- 接口文档：`http://127.0.0.1:8000/docs`

## 目录说明

- `fin_pdf_agent/app.py`：FastAPI 入口
- `fin_pdf_agent/core/agent.py`：agent 构建与运行
- `fin_pdf_agent/core/memory.py`：会话记忆存储
- `workspace/repo`：放待处理的财报文件
- `workspace/output`：放 agent 输出结果
- `workspace/skills`：放可加载的技能

## 当前进度

### 已完成

1. `agent.py` 基础框架
2. `memory.py` 基本会话能力，主要基于 openai sdk 的 session 管理上下文
3. `context.py` 用于构建系统提示词
4. 已接入沙箱智能体
5. 已实现上下文压缩功能，当前为简单的 token 计算和智能压缩
### 未完成

1.只有自定义的工具，而且比较简单和粗糙
2. 还未真正加载 skills

## 后续扩展

1. 在 `memory.py` 中增加用户个性化长期记忆
2.  `memory.py` 已经实现简单的上下文压缩，后续可以考虑更复杂的压缩算法
3. 将 Windows sandbox 改为基于临时 Windows 用户运行

## 当前问题

1. 打包后 `path` 中项目根目录的定位可能存在加载问题
2. 还没有处理完整的代码生命周期
3. 上下文压缩功能需要优化，考虑更复杂的压缩算法
4.没有考虑大模型调用次数上限，防止死循环
