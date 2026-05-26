import re
import shutil
from pathlib import Path

import yaml

from .path import HOST_SKILLS_DIR


class SkillLoader:
    """管理本地 SDK 风格的技能目录：skills/<name>/SKILL.md。"""

    def __init__(self, skills_dir=HOST_SKILLS_DIR):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self):
        """列出所有技能的简要信息。"""
        return [
            self._read_skill_file(skill_file, include_content=False)
            for skill_file in sorted(self.skills_dir.glob("*/SKILL.md"))
        ]

    def read_skill(self, name):
        """按目录名读取单个技能。"""
        skill_file = self._skill_file(name)

        if not skill_file.exists():
            raise FileNotFoundError(f"技能不存在: {name}")

        return self._read_skill_file(skill_file, include_content=True)

    def add_skill(
        self,
        name,
        description,
        content,
        *,
        overwrite=False,
        metadata=None,
    ):
        """创建或覆盖包含 SKILL.md 的技能目录。"""
        skill_file = self._skill_file(name)

        if skill_file.exists() and not overwrite:
            raise FileExistsError(f"技能已存在: {name}")

        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_meta = {
            "name": name,
            "description": description,
            **(metadata or {}),
        }
        skill_file.write_text(
            self._format_skill_markdown(skill_meta, content),
            encoding="utf-8",
        )

        return self.read_skill(name)

    def delete_skill(self, name):
        """删除技能目录。"""
        skill_dir = self._skill_file(name).parent

        if not skill_dir.exists():
            raise FileNotFoundError(f"技能不存在: {name}")

        shutil.rmtree(skill_dir)

    def _skill_file(self, name):
        """
        根据技能名称返回对应的 SKILL.md 文件路径，并进行安全验证以防止路径遍历攻击，由ai写的。
        """
        safe_name = self._validate_skill_name(name)
        skill_dir = (self.skills_dir / safe_name).resolve()
        root_dir = self.skills_dir.resolve()

        if skill_dir != root_dir and root_dir not in skill_dir.parents:
            raise ValueError(f"非法技能路径: {name}")

        return skill_dir / "SKILL.md"

    def _validate_skill_name(self, name):
        """
        技能名称只能包含字母、数字、下划线和短横线，并且必须以字母或数字开头。
        """
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
            raise ValueError("技能名称只能包含字母、数字、下划线和短横线")

        return name

    def _format_skill_markdown(self, meta, content):
        frontmatter = yaml.safe_dump(
            meta,
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        return f"---\n{frontmatter}\n---\n\n{content.strip()}\n"

    def _read_skill_file(self, skill_file, include_content):
        """
        解析技能文件，提取 YAML 前置内容和正文。
        """
        text = Path(skill_file).read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)

        meta = {}
        content = text.strip()

        if match:
            try:
                meta = yaml.safe_load(match.group(1)) or {}
                content = match.group(2).strip()
            except yaml.YAMLError:
                pass

        skill = {
            "name": meta.get("name", skill_file.parent.name),
            "description": meta.get("description", "无描述"),
            "path": str(skill_file),
            "metadata": meta,
        }

        if include_content:
            skill["content"] = content

        return skill