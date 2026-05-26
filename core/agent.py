import os
import sys
from pathlib import Path

from agents import Agent, Runner
from agents import set_default_openai_api, set_default_openai_client, set_tracing_disabled
from agents.run import RunConfig
from agents.sandbox import Manifest, SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import LocalDirLazySkillSource, Shell, Skills
from agents.sandbox.entries import Dir, LocalDir
from openai import AsyncOpenAI
from .context import agentContext
from .memory import Memorystore
from .path import HOST_OUTPUT_DIR, HOST_REPO_DIR, HOST_SKILLS_DIR
from .tools import ToolLoader
class PDFAgent:
    """agent会使用openai官方agent sdk,封装了agent的运行组件,包括工具tools，工作目录workspace，技能skills等"""

    def __init__(
        self,
        workspace_dir: str | Path,
        openai_api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = "deepseek-v4-flash",
        use_sandbox: bool = True,
    ) -> None:
        """
        初始化agent
        openai_api_key需要兼容openai接口的apikey,可使用环境变量 OPENAI_API_KEY 作为备用。
        base_url: OpenAI 兼容接口的代理/服务地址.
        workspace:用于获取pdf和输出ai操作的结果的地方。
        use_sandbox: 是否启用官方 SandboxAgent。启用后会把 repo/、output/、skills/ 放入沙箱语义中。
        Host_REPO_DIR: 沙箱内可访问的财报文件目录，放在 workspace/repo 下。
        Host_OUTPUT_DIR: 沙箱内可写入的输出目录，放在 workspace/output 下。
        Host_SKILLS_DIR: 沙箱内技能来源目录，放在 workspace/skills 下。
        """
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        HOST_REPO_DIR.mkdir(parents=True, exist_ok=True)
        HOST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        HOST_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        self.use_sandbox = use_sandbox
        self.model = model or "deepseek-v4-flash"
        self._setup_openai_client(openai_api_key=openai_api_key, base_url=base_url)

        tools_loader = ToolLoader()
        memory_store = Memorystore()
        context_builder = agentContext(
            memory_store=memory_store,
            workspace_dir=str(self.workspace_dir),
            tools_loader=tools_loader,
        )

        self.tool_list = tools_loader.get_tools()
        self.contexts = context_builder.build_context()
        self.agent = self._build_agent()
        self.run_config = self._build_run_config() if self.use_sandbox else None
    
    #封装api和base_url的配置，以及设置agent的api模式和构建的过程   
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
                instructions="你是财报分析师。根据用户问题分析财报内容并给出简洁回答。",
                model=self.model,
                tools=self.tool_list,
            )

        # 启用沙箱时，不传入普通 read_file/write_file/edit_file，避免绕过沙箱隔离。
        # chat_completions 下不要使用 Capabilities.default()，因为默认 Filesystem
        # 会带 apply_patch CustomTool，Compaction 也可能不兼容。
        return SandboxAgent(
            name="pdf_sandbox_agent",
            instructions=(
                "你是财报解析智能体。只能在沙箱工作区内处理文件。"
                "财报和输入资料位于 repo/，分析结果写入 output/。"
                "优先生成结构化结果，例如 Markdown、JSON 或 CSV。"
                "不要访问互联网。最终回答要说明读取了什么、生成了什么。"
            ),
            model=self.model,
            tools=[],
            default_manifest=Manifest(
                entries={
                    # 沙箱agent的工作目录，要读取的财报是repo,输出结果放在output，技能在skills
                    "repo": LocalDir(src=HOST_REPO_DIR),
                    "output": Dir(),
                }
            ),
            capabilities=[
                # Shell 暴露 exec_command/write_stdin，属于 FunctionTool，可用于 chat_completions。
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
            from docker import from_env as docker_from_env

            from agents.sandbox.sandboxes.docker import (
                DockerSandboxClient,
                DockerSandboxClientOptions,
            )

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

    async def chat(self, question: str):
        """
        核心的对外交互接口。
        1. 拿到用户的当前问题。
        2. 将问题连同历史记录、系统提示组装成一整条消息 Payload：`messages`。
        3. 如果启用 sandbox，则通过 run_config 为本次运行创建沙箱会话。
        """
        result = await Runner.run(
            starting_agent=self.agent,
            input=question,
            context=self.contexts,
            run_config=self.run_config,
        )
        print("agent的回答：", result.final_output)
        return result.final_output
