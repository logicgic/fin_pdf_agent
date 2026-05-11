import dataclasses
@dataclasses
class Context:
    def __init__(self,memory_store:Memorystore,skills_loader: SkillsLoader, workspace_dir: str):
        self.memory=memory_store
        self.skills = skills_loader
        self.workspace_dir = workspace_dir

        