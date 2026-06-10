import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = Path(os.environ.get("FIN_PDF_AGENT_HOME", Path.cwd())).resolve()
prompt_dir = Path(__file__).parent / "resource" / "prompt"
static_dir = PACKAGE_DIR / "static"
memory_dir = PROJECT_DIR / "memory"
database_dir = PROJECT_DIR / "database"
workspace_dir = PROJECT_DIR / "workspace"
config_dir = PROJECT_DIR / "config"
config_path = PROJECT_DIR / "config.yaml"
HOST_SKILLS_DIR = workspace_dir / "skills"
HOST_REPO_DIR = workspace_dir / "repo"
HOST_OUTPUT_DIR = workspace_dir / "output"
HOST_PARSED_DOCS_DIR = workspace_dir / "parsed_docs"
