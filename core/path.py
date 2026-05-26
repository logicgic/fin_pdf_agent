from pathlib import Path
PROJECT_DIR=Path(__file__).parent.parent
prompt_dir=Path(__file__).parent / "resource" / "prompt"
memory_dir=Path(__file__).parent / "memory"
database_dir=Path(__file__).parent / "database"
workspace_dir=Path(__file__).parent / "workspace"
config_dir=Path(__file__).parent / "config"
HOST_SKILLS_DIR = workspace_dir / "skills"
HOST_REPO_DIR= workspace_dir / "repo"
HOST_OUTPUT_DIR = workspace_dir / "output"
