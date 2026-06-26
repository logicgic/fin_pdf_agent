import asyncio
import os
import sys
from pathlib import Path

from agents import (
    Agent,
    Runner,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.exceptions import MaxTurnsExceeded
from agents.run import RunConfig
from agents.sandbox import Manifest, SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import LocalDirLazySkillSource, Shell, Skills
from agents.sandbox.entries import Dir, LocalDir
from openai import AsyncOpenAI

from .context import agentContext
from .memory import Memorystore
from .path import (
    HOST_OUTPUT_DIR,
    HOST_PARSED_DOCS_DIR,
    HOST_REPO_DIR,
    HOST_SKILLS_DIR,
)
from .tools import ToolLoader, set_task_state_recorder, update_task_state_from_result


class PDFAgent:
    """
    agent会使用openai官方agent sdk,封装了agent的运行组件,
    包括工具tools，工作目录workspace，技能skills等。
    """

    def __init__(
        self,
        workspace_dir: str | Path,
        openai_api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = "deepseek-v4-flash",
        use_sandbox: bool = True,
        max_turns: int = 30,           # 单次请求的模型调用上限从默认的10调整为30
        run_timeout_seconds: int = 300,   #单次请求最多 5 分钟，避免后端挂死
    ) -> None:
        """
        初始化agent
        openai_api_key需要兼容openai接口的apikey,
        可使用环境变量 OPENAI_API_KEY 作为备用。
        base_url: OpenAI 兼容接口的代理/服务地址.
        workspace:用于获取pdf和输出ai操作的结果的地方。
        use_sandbox: 是否启用官方 SandboxAgent。
        启用后会把 repo/、output/、skills/ 放入沙箱语义中。
        Host_REPO_DIR: 沙箱内可访问的财报文件目录，放在 workspace/repo 下。
        Host_OUTPUT_DIR: 沙箱内可写入的输出目录，放在 workspace/output 下。
        Host_SKILLS_DIR: 沙箱内技能来源目录，放在 workspace/skills 下。
        HOST_PARSED_DOCS_DIR: 解析后的文档目录，放在 workspace/parsed_docs 下。
        """
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        HOST_REPO_DIR.mkdir(parents=True, exist_ok=True)
        HOST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        HOST_PARSED_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        HOST_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        self.use_sandbox = use_sandbox
        self.model = model or "deepseek-v4-flash"
        self.max_turns = max(1, int(max_turns))
        self.run_timeout_seconds = max(1, int(run_timeout_seconds))
        self._setup_openai_client(openai_api_key=openai_api_key, base_url=base_url)
        self.memory_store = Memorystore()
        self.active_conversation_id: str | None = None

        tools_loader = ToolLoader()
        self.context_builder = agentContext(
            memory_store=self.memory_store,
            workspace_dir=str(self.workspace_dir),
            tools_loader=tools_loader,
        )

        self.tool_list = tools_loader.get_tools()
        self.contexts = self.context_builder.build_context()
        self.agent = self._build_agent()
        self.run_config = self._build_run_config() if self.use_sandbox else None
        set_task_state_recorder(self._record_task_state)

    # 封装api和base_url的配置，以及设置agent的api模式和构建的过程
    def _setup_openai_client(
        self,
        *,
        openai_api_key: str | None,
        base_url: str | None,
    ) -> None:
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未提供 api_key，且环境变量中未设置 OPENAI_API_KEY")

        api_base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if not api_base_url:
            raise ValueError("未提供 base_url，且环境变量中未设置 OPENAI_BASE_URL")

        custom_client = AsyncOpenAI(base_url=api_base_url, api_key=api_key)
        set_default_openai_client(custom_client)
        set_default_openai_api("chat_completions")
        set_tracing_disabled(True)

    def _build_agent(self) -> Agent:
        # 不启用沙箱时，保留普通 Agent：使用本地 function tools 直接读写文件。
        if not self.use_sandbox:
            return Agent(
                name="pdf_agent",
                instructions=self.context_builder.build_local_instructions(),
                model=self.model,
                tools=self.tool_list,
            )

        # 启用沙箱时，不传入普通 read_file/write_file/edit_file，避免绕过沙箱隔离。
        # chat_completions 下不要使用 Capabilities.default()，因为默认 Filesystem
        # 会带 apply_patch CustomTool，Compaction 也可能不兼容。
        # instructions不放动态加载的文件，减少缓存未命中的问题。
        return SandboxAgent(
            name="pdf_sandbox_agent",
            instructions=self.context_builder.build_sandbox_instructions(),
            model=self.model,
            tools=[],
            default_manifest=Manifest(
                entries={
                    # 沙箱agent的工作目录。
                    # 要读取的财报是repo,输出结果放在output，技能在skills。
                    "repo": LocalDir(src=HOST_REPO_DIR),
                    "output": Dir(),
                }
            ),
            capabilities=[
                # Shell 暴露 exec_command/write_stdin，属于 FunctionTool。
                Shell(),
                # 技能来源是 HOST_SKILLS_DIR，技能会被动态加载到沙箱环境中。
                Skills(
                    lazy_from=LocalDirLazySkillSource(
                        source=LocalDir(src=HOST_SKILLS_DIR),
                    )
                ),
            ],
        )

    def _build_run_config(self) -> RunConfig:
        # SandboxAgent 必须通过 RunConfig(sandbox=...) 提供运行时沙箱客户端。
        sandbox_config: SandboxRunConfig

        if sys.platform == "win32":
            # UnixLocalSandboxClient 不支持 Windows，因此 Windows 下使用 Docker 沙箱。
            from agents.sandbox.sandboxes.docker import (
                DockerSandboxClient,
                DockerSandboxClientOptions,
            )
            from docker import from_env as docker_from_env

            sandbox_config = SandboxRunConfig(
                client=DockerSandboxClient(docker_from_env()),
                options=DockerSandboxClientOptions(image="python:3.12-slim"),
            )
        else:
            # macOS/Linux 可使用官方示例中的 Unix 本地沙箱。
            from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient

            sandbox_config = SandboxRunConfig(client=UnixLocalSandboxClient())

        return RunConfig(
            sandbox=sandbox_config,
            workflow_name="financial-pdf-sandbox-agent",
        )

    async def chat(self, question: str, conversation_id: str):
        """
        核心的对外交互接口。
        1. 拿到用户的当前问题。
        2. 将问题连同历史记录、系统提示组装成一整条消息 Payload：`messages`。
        3. 如果启用 sandbox，则通过 run_config 为本次运行创建沙箱会话。
        """
        session = self.memory_store.get_session(conversation_id)
        self.active_conversation_id = conversation_id
        try:
            result = await asyncio.wait_for(
                Runner.run(
                    starting_agent=self.agent,
                    input=question,
                    run_config=self.run_config,
                    session=session,
                    max_turns=self.max_turns,
                ),
                timeout=self.run_timeout_seconds,
            )
        except MaxTurnsExceeded:
            return "本次任务调用次数过多，已停止。请缩小问题范围或分步骤提问。"
        except asyncio.TimeoutError:
            return "本次任务执行时间过长，已停止。请缩小问题范围或稍后重试。"

        await session.store_run_usage(result)
        self._record_tool_results(result, conversation_id)

        # 假如token达到阈值，压缩压缩记忆
        usage = await session.get_session_usage()
        total_tokens = usage["total_tokens"] if usage else 0
        if total_tokens > self.memory_store.MAX_TOKENS:
            await self.memory_store.compact_session(
                session=session,
                model=self.model,
                conversation_id=conversation_id,
            )

        return result.final_output

    def _record_tool_results(self, result, conversation_id: str) -> None:
        """将 SDK 工具执行结果写入结构化任务状态。"""
        tool_names_by_call_id: dict[str, str] = {}
        for item in result.new_items:
            if getattr(item, "type", None) != "tool_call_item":
                continue

            call_id = getattr(item, "call_id", None)
            tool_name = getattr(item, "tool_name", None)
            if call_id and tool_name:
                tool_names_by_call_id[call_id] = tool_name

        for item in result.new_items:
            if getattr(item, "type", None) != "tool_call_output_item":
                continue

            call_id = getattr(item, "call_id", None)
            tool_name = tool_names_by_call_id.get(call_id)
            if not tool_name:
                continue

            update_task_state_from_result(
                self.memory_store,
                conversation_id,
                tool_name,
                str(getattr(item, "output", "")),
            )

    def _record_task_state(self, tool_name: str, value: str) -> None:
        """记录当前会话的结构化任务状态。"""
        if not self.active_conversation_id:
            return

        if tool_name == "parse_document_to_md":
            self.memory_store.update_task_state(
                self.active_conversation_id,
                parsed_file=value,
                generated_output=value,
            )
            return

        if tool_name == "prepare_report_markdown":
            self.memory_store.update_task_state(
                self.active_conversation_id,
                parsed_file=value,
                generated_output=f"{value} 已生成 markdown 分析内容",
            )
            return

        if tool_name == "prepare_structured_report":
            self.memory_store.update_task_state(
                self.active_conversation_id,
                parsed_file=value,
                generated_output=f"{value} 已生成结构化财报内容",
            )

    async def close(self):
        """关闭 agent 持有的资源。"""
        await self.memory_store.close()
