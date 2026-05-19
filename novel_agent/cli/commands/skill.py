"""Skill CLI commands — import, list, delete writing skills."""
from pathlib import Path
from typing import Optional

import typer


def _get_store_and_llm():
    """Create SkillStore and LLM interface from global config."""
    from ...configs.config import Config
    from ...tools.llm_interface import initialize_llm
    from ...skill.store import SkillStore

    config = Config().config
    store = SkillStore(config)
    backend = config.get("llm.backend", "api")
    model = config.get("llm.model") or config.get("llm.openai_model", "deepseek-chat")
    llm = initialize_llm(backend=backend, model=model)
    return store, llm, config


def import_skill(
    file_path: str,
    name: Optional[str] = None,
) -> None:
    """Import a novel file and extract a writing skill."""
    from ...skill.importer import SkillImporter

    path = Path(file_path)
    if not path.exists():
        typer.echo(f"[ERR] 文件不存在：{file_path}", err=True)
        raise typer.Exit(1)

    store, llm, _config = _get_store_and_llm()
    importer = SkillImporter(llm, store)

    typer.echo(f" 正在导入：{path}")
    typer.echo(f" 文件名：{path.name}")
    typer.echo(f" 大小：{path.stat().st_size / 1024 / 1024:.1f} MB")

    skill = importer.import_novel(str(path), name=name)

    typer.echo(f"\n[OK] 导入完成！")
    typer.echo(f"   ID：{skill.id}")
    typer.echo(f"   Slug：{skill.slug}")
    typer.echo(f"   名称：{skill.name}")
    typer.echo(f"   标签：{', '.join(skill.tags)}")
    typer.echo(f"   字数：{skill.word_count:,}")
    typer.echo(f"   章节：{skill.chapter_count}")
    typer.echo(f"   叙事模式：{len(skill.patterns)}")
    for p in skill.patterns:
        typer.echo(f"     [{p.type}] {p.template}")
    typer.echo(f"   角色原型：{len(skill.character_archetypes)}")
    for a in skill.character_archetypes:
        typer.echo(f"     [{a.role}] {a.name}")
    typer.echo(f"\n   存储位置：data/skills/{skill.slug}/SKILL.yaml")


def list_skills() -> None:
    """List all imported skills."""
    store, _llm, _config = _get_store_and_llm()
    skills = store.list_skills()

    if not skills:
        typer.echo(" 暂无已导入的技能。")
        typer.echo(" 使用 'novel skill import <文件路径>' 导入小说。")
        return

    typer.echo(f" 已导入技能（共 {len(skills)} 个）：\n")
    for s in skills:
        typer.echo(f"  [{s.slug}] {s.name}")
        typer.echo(f"    标签：{', '.join(s.tags) if s.tags else '(无)'}")
        typer.echo(f"    模式：{len(s.patterns)} 个叙事模式, {len(s.character_archetypes)} 个角色原型")
        typer.echo(f"    字数：{s.word_count:,}")
        typer.echo()


def delete_skill(slug: str, force: bool = False) -> None:
    """Delete a skill by slug or id."""
    store, _llm, _config = _get_store_and_llm()
    skill = store.load_skill(slug)
    if skill is None:
        typer.echo(f"[ERR] 未找到技能：{slug}", err=True)
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f" 确认删除 '{skill.name}' [{skill.slug}]？")
        if not confirm:
            typer.echo(" 已取消。")
            return

    store.delete_skill(slug)
    typer.echo(f"[OK] 已删除：{skill.name}")


def apply_skill(
    slug: str,
    project_path: str,
    mode: str = "reference",
) -> None:
    """Apply a writing skill to a novel project."""
    from ...skill.injector import SkillInjector

    store, _llm, _config = _get_store_and_llm()
    skill = store.load_skill(slug)
    if skill is None:
        typer.echo(f"[ERR] 未找到技能：{slug}", err=True)
        raise typer.Exit(1)

    project_dir = Path(project_path)
    state_file = project_dir / "state.json"
    if not state_file.exists():
        typer.echo(f"[ERR] 不是有效的项目目录：{project_path}", err=True)
        raise typer.Exit(1)

    injector = SkillInjector(str(project_dir), _config)
    injector.inject([skill], mode=mode)

    typer.echo(f"[OK] 已应用技能 '{skill.name}' 到项目")
    typer.echo(f"   模式：{mode}")
    typer.echo(f"   叙事模式：{len(skill.patterns)} 个")
    typer.echo(f"   角色原型：{len(skill.character_archetypes)} 个")
