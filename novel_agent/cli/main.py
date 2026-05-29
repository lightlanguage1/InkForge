"""Main CLI entry point for InkForge."""
import typer
from pathlib import Path
from typing import Optional, Dict, Any
from ..configs.config import Config
from ..configs.constants import DEFAULT_HOST, DEFAULT_PORT
from .. import setup_logging
from .project import (
    create_novel_project,
    find_project_dir,
    load_project_state,
    save_project_state,
    get_project_config
)
from .foundation import (
    prompt_for_foundation,
    load_foundation_from_file,
    create_foundation_from_args
)
from ..agent.factory import create_agent
from ..tools.llm_interface import initialize_llm
from ..memory.manager import MemoryManager
from .recent_projects import RecentProjects
from .commands.plot import (
    get_plot_status,
    display_plot_status,
    display_plot_status_detailed,
    get_next_beat,
    display_next_beat,
    generate_and_append_beats_cli,
    display_generated_beats,
)


def _show_stage_stats(stats: dict):
    """Display multi-stage planner statistics."""
    typer.echo(f"\n 多阶段规划统计：")
    typer.echo(f"   阶段1（战略）：{stats.get('stage1_tokens', 0)} tokens，{stats.get('stage1_time', 0):.2f}s")
    typer.echo(f"   阶段2（语义）：{stats.get('stage2_items', 0)} 项，{stats.get('stage2_time', 0):.2f}s")
    typer.echo(f"   阶段3（战术）：{stats.get('stage3_tokens', 0)} tokens，{stats.get('stage3_time', 0):.2f}s")
    total_time = stats.get('stage1_time', 0) + stats.get('stage2_time', 0) + stats.get('stage3_time', 0)
    total_tokens = stats.get('stage1_tokens', 0) + stats.get('stage3_tokens', 0)
    typer.echo(f"   合计：{total_tokens} tokens，{total_time:.2f}s")


def _show_story_stats(project_dir: Path, state: dict):
    """Display story statistics summary."""
    from ..memory.manager import MemoryManager
    
    memory = MemoryManager(project_dir)
    
    # Count entities
    scene_ids = memory.list_scenes()
    all_chars = memory.list_characters()
    all_locs = memory.list_locations()
    all_factions = memory.list_factions()
    all_loops = memory.load_open_loops()
    all_lore = memory.load_all_lore()
    
    # Calculate total word count and tension from scene files
    total_words = 0
    tensions = []
    for scene_id in scene_ids:
        scene = memory.load_scene(scene_id)
        if scene and scene.word_count:
            total_words += scene.word_count
        if scene and scene.tension_level is not None:
            tensions.append(scene.tension_level)
    
    avg_tension = sum(tensions) / len(tensions) if tensions else 0
    
    typer.echo(f"\n 故事统计：")
    typer.echo(f"   章节：{len(scene_ids)}（共 {total_words:,} 字）")
    typer.echo(f"   角色：{len(all_chars)}")
    typer.echo(f"   地点：{len(all_locs)}")
    typer.echo(f"   势力：{len(all_factions)}")
    typer.echo(f"   悬念线索：{len(all_loops)}")
    typer.echo(f"   世界观条目：{len(all_lore)}")
    if tensions:
        typer.echo(f"   平均张力：{avg_tension:.1f}/10")


def _prompt_for_llm_selection() -> tuple[str, str]:
    """Interactively select LLM backend and model for a new project.

    Returns a (backend, model) tuple which will be stored in the
    project's config.yaml. Defaults are derived from the global
    configuration and adjusted per backend so users can just press
    Enter to accept sensible values.
    """
    config = Config()

    default_backend = config.get("llm.backend", "codex")
    typer.echo("\n LLM 后端与模型")
    typer.echo("请选择本项目使用的 LLM 后端。"
               "该选择将存储在项目的 config.yaml 中，供 `novel tick`/`run` 使用，"
               "除非在 CLI 中覆盖。\n")

    options = [
        ("ollama", "Ollama（本地模型，推荐）"),
        ("codex", "Codex CLI（使用本地 `codex` 二进制）"),
        ("api", "API 后端（OpenAI GPT-5.x、Claude 4.5、Gemini 2.5 Pro）"),
        ("gemini-cli", "Gemini CLI（本地 `gemini` 二进制）"),
        ("claude-cli", "Claude Code CLI（本地 `claude` 二进制）"),
    ]

    # Determine which option index corresponds to the current default backend
    default_index = 1
    for idx, (value, _label) in enumerate(options, start=1):
        if value == default_backend:
            default_index = idx
            break

    typer.echo("可用后端：")
    for idx, (value, label) in enumerate(options, start=1):
        marker = "（默认）" if value == default_backend else ""
        typer.echo(f"  {idx}. {label}{marker}")

    # Prompt for backend choice
    backend: Optional[str] = None
    while backend is None:
        choice = typer.prompt(
            f"选择 LLM 后端 [1-{len(options)}]",
            default=str(default_index),
        ).strip()
        try:
            idx = int(choice)
        except ValueError:
            typer.echo(f"请输入 1 到 {len(options)} 之间的数字。")
            continue

        if 1 <= idx <= len(options):
            backend = options[idx - 1][0]
        else:
            typer.echo(f"请输入 1 到 {len(options)} 之间的数字。")

    # Choose a sensible default model for the selected backend
    if backend == "ollama":
        default_model = "qwen3:8b"
    elif backend == "gemini-cli":
        default_model = "gemini-2.5-pro"
    elif backend == "claude-cli":
        default_model = "claude-4.5"
    else:
        # codex or api: fall back to configured defaults
        default_model = (
            config.get("llm.model")
            or config.get("llm.openai_model", "gpt-5.1")
        )

    typer.echo(
        f"\n后端 '{backend}' 的模型名称"
        f"（直接回车使用默认：{default_model}）"
    )
    model = typer.prompt("模型", default=default_model).strip()
    if not model:
        model = default_model

    return backend, model


app = typer.Typer(
    name="novel",
    help="InkForge - Agentic novel generation system",
    add_completion=False
)

plot_app = typer.Typer(name="plot", help="Plot outline (PlotBeat Phase 3) commands")
app.add_typer(plot_app, name="plot")

skill_app = typer.Typer(name="skill", help="Writing skill import and management")
app.add_typer(skill_app, name="skill")


@app.command()
def new(
    name: str = typer.Argument(..., help="Name of the novel"),
    dir: Optional[str] = typer.Option(
        None,
        "--dir",
        "-d",
        help="Base directory for novel (default: ~/novels)"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Use interactive story foundation wizard (recommended for new users)"
    ),
    foundation_file: Optional[Path] = typer.Option(
        None,
        "--foundation",
        "-f",
        help="Load story foundation from YAML file"
    ),
    genre: Optional[str] = typer.Option(
        None,
        "--genre",
        help="Story genre (e.g., fantasy, sci-fi, thriller)"
    ),
    premise: Optional[str] = typer.Option(
        None,
        "--premise",
        help="Story premise (1-2 sentences)"
    ),
    protagonist: Optional[str] = typer.Option(
        None,
        "--protagonist",
        help="Protagonist archetype (personality/role)"
    ),
    setting: Optional[str] = typer.Option(
        None,
        "--setting",
        help="Story setting (time/place/world)"
    ),
    tone: Optional[str] = typer.Option(
        None,
        "--tone",
        help="Story tone (mood/atmosphere)"
    ),
    themes: Optional[str] = typer.Option(
        None,
        "--themes",
        help="Story themes (comma-separated)"
    )
):
    """Create a new novel project with optional story foundation.

    Creates a complete project structure with memory directories,
    configuration files, and initial state. By default, runs the
    interactive story foundation wizard so the LLM has clear
    constraints (genre, premise, setting, etc.). Advanced users
    can disable the wizard with ``--no-interactive`` or supply a
    foundation via file/CLI options.

    Examples:
        # Recommended: interactive foundation setup (default)
        novel new my-story

        # Explicitly disable interactive wizard (bare project)
        novel new my-story --no-interactive

        # Load foundation from file (non-interactive)
        novel new my-story --foundation foundation.yaml

        # Specify foundation via command-line (non-interactive)
        novel new my-story --genre "science fiction" --premise "..." --protagonist "..." --setting "..." --tone "..."
    """
    try:
        # Determine foundation source
        foundation = None

        # If the user has provided an explicit non-interactive source
        # (foundation file or CLI foundation fields), disable the
        # interactive wizard even though it is the default.
        has_foundation_args = any([genre, premise, protagonist, setting, tone, themes])
        interactive_effective = interactive
        if foundation_file or has_foundation_args:
            interactive_effective = False

        llm_backend_override: Optional[str] = None
        llm_model_override: Optional[str] = None
        plot_config: Optional[Dict[str, Any]] = None

        if interactive_effective:
            # Interactive prompting (recommended default)
            foundation, plot_config = prompt_for_foundation()
            llm_backend_override, llm_model_override = _prompt_for_llm_selection()
        elif foundation_file:
            # Load from file
            foundation = load_foundation_from_file(foundation_file)
            typer.echo(f"[OK] 已加载故事基础设定：{foundation_file}")
        else:
            # Try to create from command-line args (may return None)
            foundation = create_foundation_from_args(
                genre=genre,
                premise=premise,
                protagonist=protagonist,
                setting=setting,
                tone=tone,
                themes=themes
            )
        
        # Create project with optional foundation, LLM overrides, and plot config
        project_dir = create_novel_project(
            name,
            dir,
            foundation=foundation,
            llm_backend=llm_backend_override,
            llm_model=llm_model_override,
            plot_config=plot_config,
        )
        typer.echo(f"[OK] 已创建小说项目：{project_dir}")
        
        if foundation:
            typer.echo(f"\n 故事基础设定：")
            typer.echo(f"   类型：{foundation.genre}")
            typer.echo(f"   背景：{foundation.setting}")
        
        if plot_config and plot_config.get("use_plot_first"):
            typer.echo(f"\n 情节优先模式已启用：")
            if not plot_config.get("allow_beat_skip") and not plot_config.get("fallback_to_reactive"):
                typer.echo(f"   模式：严格（强制执行节拍）")
            else:
                typer.echo(f"   模式：宽松/标准")
            typer.echo(f"   节拍将从第2幕开始自动生成")

        typer.echo(f"\n 下一步：")
        typer.echo(f"  cd {project_dir}")
        typer.echo(f"  novel tick  # 运行几幕以建立角色/世界")
        if plot_config and plot_config.get("use_plot_first"):
            typer.echo(f"  # 情节节拍将从第2幕起自动生成")
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)
    except IOError as e:
        typer.echo(f"[ERR] 创建项目失败：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def tick(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project (default: current directory)"
    ),
    save_prompts: bool = typer.Option(
        False,
        "--save-prompts",
        help="Save prompts to prompts/ directory for inspection"
    ),
    llm_backend: Optional[str] = typer.Option(
        None,
        "--llm-backend",
        help="LLM backend: codex, api (multi-provider API), gemini-cli (Gemini CLI), or claude-cli (Claude Code CLI)"
    ),
    llm_model: Optional[str] = typer.Option(
        None,
        "--llm-model",
        help="Model name for API backend (e.g., gpt-5.1, gpt-5, gpt-5.1-mini, claude-4.5, gemini-2.5-pro)"
    ),
    codex_bin: Optional[str] = typer.Option(
        None,
        "--codex-bin",
        help="Path to Codex CLI binary"
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        "-n",
        help="Direction notes for this scene (injected into planner + writer). "
             "Use for scene steering, tone shifts, if-lines, POV experiments, etc."
    ),
):
    """Run one story generation tick.

    Executes the full story generation pipeline:
    - Planning with LLM
    - Tool execution
    - Scene prose generation
    - Quality evaluation
    - Scene commit to disk and memory

    Example:
        novel tick
        novel tick --project ~/novels/my-story
        novel tick --notes "本场景描写两位主角在月光下的温泉中互诉衷肠"
    """
    # When tick() is called programmatically (e.g., from resume()), Typer
    # may pass OptionInfo objects instead of plain strings for llm_* args.
    # Normalize these to None so our backend/model resolution logic behaves
    # the same as when invoked from the CLI.
    from typer.models import OptionInfo  # type: ignore
    if isinstance(llm_backend, OptionInfo):
        llm_backend = None
    if isinstance(llm_model, OptionInfo):
        llm_model = None
    if isinstance(codex_bin, OptionInfo):
        codex_bin = None

    try:
        # Find project directory
        project_dir = Path(find_project_dir(project))
        typer.echo(f" 正在为项目生成内容：{project_dir}")
        
        # Track as recent project
        recent = RecentProjects()
        state = load_project_state(project_dir)
        recent.add_project(str(project_dir), state.get('novel_name'))
        
        # Load config
        config = get_project_config(project_dir)
        
        # Show prompt saving status
        if save_prompts:
            typer.echo(f"    保存提示词到：{project_dir}/prompts/")

        current_tick = state['current_tick']
        typer.echo(f"   当前幕数：{current_tick}")

        # Assemble agent via shared factory
        try:
            agent = create_agent(
                project_dir, config,
                llm_backend=llm_backend, llm_model=llm_model,
                codex_bin=codex_bin, save_prompts=save_prompts,
            )
            typer.echo(f"[OK] LLM 后端已初始化：{llm_backend or config.get('llm.backend', 'codex')}")
        except RuntimeError as e:
            typer.echo(f"[ERR] {e}", err=True)
            raise typer.Exit(1)

        # Execute tick
        typer.echo(f"\n  执行第 {current_tick} 幕...")
        
        result = agent.tick(notes=notes or "")

        if notes:
            typer.echo(f"\n   方向指导：{notes[:60]}{'...' if len(notes) > 60 else ''}")
        typer.echo(f"\n[OK] 第 {current_tick} 幕生成完成！")
        typer.echo(f"    场景：{result.get('scene_file', '?')}")
        typer.echo(f"    字数：{result.get('word_count', 0)}")
        typer.echo(f"    动作：{result.get('actions_executed', 0)}")
        
        # Show entity updates if any
        entities = result.get('entities_updated', {})
        if entities and any(entities.values()):
            typer.echo(f"\n    实体更新：")
            if entities.get('characters_updated'):
                typer.echo(f"       角色：{entities['characters_updated']}")
            if entities.get('locations_updated'):
                typer.echo(f"       地点：{entities['locations_updated']}")
            if entities.get('loops_created'):
                typer.echo(f"       新增线索：{entities['loops_created']}")
            if entities.get('loops_resolved'):
                typer.echo(f"      [v] 已解决线索：{entities['loops_resolved']}")
            if entities.get('relationships_updated'):
                typer.echo(f"       关系：{entities['relationships_updated']}")
        
        # Show warnings if any
        if result.get('eval_warnings'):
            typer.echo(f"\n   [WARN]  警告：{len(result['eval_warnings'])}")
            for warning in result['eval_warnings']:
                typer.echo(f"      - {warning}")

        typer.echo(f"\n   ⏭  下一幕：{current_tick + 1}")
        
        # Show multi-stage planner stats if available (Phase 7A.5)
        if result.get('stage_stats'):
            _show_stage_stats(result['stage_stats'])
        
        # Show story stats summary
        _show_story_stats(project_dir, state)
        
    except RuntimeError as e:
        # Tool execution error - details saved to /errors/
        typer.echo(f"\n[ERR] 幕生成失败", err=True)
        typer.echo(f"   错误：{str(e)}", err=True)
        typer.echo(f"\n 错误详情已保存至 {project_dir}/errors/", err=True)
        typer.echo(f"\n 恢复选项：", err=True)
        typer.echo(f"   1. 修复问题后重新运行 'novel tick'", err=True)
        typer.echo(f"   2. 手动编辑计划文件", err=True)
        typer.echo(f"   3. 跳过此幕（编辑 state.json）", err=True)
        raise typer.Exit(1)

    except ValueError as e:
        typer.echo(f"[ERR] 验证错误：{e}", err=True)
        raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"[ERR] 意外错误：{e}", err=True)
        import traceback
        typer.echo(traceback.format_exc(), err=True)
        raise typer.Exit(1)


@app.command()
def run(
    n: int = typer.Option(
        5,
        "--n",
        "-n",
        help="Number of ticks to run"
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    checkpoint_interval: int = typer.Option(
        10,
        "--checkpoint-interval",
        help="Create checkpoint every N ticks (0 to disable)"
    ),
    llm_backend: Optional[str] = typer.Option(
        None,
        "--llm-backend",
        help="LLM backend: codex, api (multi-provider API), gemini-cli (Gemini CLI), or claude-cli (Claude Code CLI)"
    ),
    llm_model: Optional[str] = typer.Option(
        None,
        "--llm-model",
        help="Model name for API backend (e.g., gpt-5.1, gpt-5, gpt-5.1-mini, claude-4.5, gemini-2.5-pro)"
    ),
    codex_bin: Optional[str] = typer.Option(
        None,
        "--codex-bin",
        help="Path to Codex CLI binary"
    ),
):
    """Run multiple story generation ticks.
    
    Runs N consecutive ticks, generating multiple scenes.
    Automatically creates checkpoints at specified intervals.
    
    Example:
        novel run --n 10
        novel run --n 5 --project ~/novels/my-story
        novel run --n 20 --checkpoint-interval 5
    """
    if not isinstance(llm_backend, (str, type(None))):
        llm_backend = None
    if not isinstance(llm_model, (str, type(None))):
        llm_model = None
    if not isinstance(codex_bin, (str, type(None))):
        codex_bin = None

    from ..memory.checkpoint import create_checkpoint, should_create_checkpoint
    
    try:
        project_dir = Path(find_project_dir(project))
        typer.echo(f" 正在为项目生成 {n} 幕：{project_dir}")
        
        # Track as recent project
        recent = RecentProjects()
        state = load_project_state(project_dir)
        recent.add_project(str(project_dir), state.get('novel_name'))
        
        # Show LLM backend info once before the loop
        config = get_project_config(project_dir)
        backend_display = llm_backend or config.get('llm.backend', 'codex')
        model_display = (
            llm_model
            or config.get('llm.model')
            or config.get('llm.openai_model', 'gpt-5.1')
        )
        typer.echo(f" LLM 后端：{backend_display}（模型={model_display}）")

        if checkpoint_interval > 0:
            typer.echo(f" 存档已启用（每 {checkpoint_interval} 幕存档一次）\n")
        else:
            typer.echo(f" 存档已禁用\n")
        
        # Track last checkpoint
        state = load_project_state(project_dir)
        last_checkpoint_tick = None
        
        # Find last checkpoint if any
        from ..memory.checkpoint import list_checkpoints
        checkpoints = list_checkpoints(project_dir)
        if checkpoints:
            last_checkpoint_tick = max(c.tick for c in checkpoints)
        
        successful_ticks = 0
        
        for i in range(n):
            typer.echo(f"--- 第 {i+1}/{n} 幕 ---")
            
            # Execute single tick by calling tick() logic
            # We need to import and reuse the tick logic here
            try:
                # Load fresh state
                state = load_project_state(project_dir)
                config = get_project_config(project_dir)
                current_tick = state['current_tick']
                
                from ..agent.factory import create_agent
                agent = create_agent(
                    project_dir, config,
                    llm_backend=llm_backend, llm_model=llm_model,
                    codex_bin=codex_bin, save_prompts=False,
                )
                
                # Execute tick
                result = agent.tick()
                
                typer.echo(f"   [OK] 第 {current_tick} 幕已完成")
                typer.echo(f"    场景：{result['scene_file']}")
                typer.echo(f"    字数：{result['word_count']}\n")
                
                successful_ticks += 1
                
                # Check if we should create checkpoint
                if checkpoint_interval > 0:
                    new_tick = current_tick + 1  # Tick was incremented
                    if should_create_checkpoint(new_tick, checkpoint_interval, last_checkpoint_tick):
                        typer.echo(f"    正在创建存档...")
                        try:
                            checkpoint_path = create_checkpoint(
                                project_dir,
                                new_tick,
                                f"auto (novel run --n {n})"
                            )
                            typer.echo(f"   [OK] 存档已创建：{checkpoint_path.name}\n")
                            last_checkpoint_tick = new_tick
                        except Exception as e:
                            typer.echo(f"   [WARN]  存档失败：{e}\n")

            except Exception as e:
                typer.echo(f"   [ERR] 幕生成失败：{e}\n")
                typer.echo(f"   已成功完成 {successful_ticks} 幕，停止生成")
                break
        
        typer.echo(f"\n[OK] 已完成 {successful_ticks}/{n} 幕")

    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"[ERR] 意外错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def summarize(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    )
):
    """Compile summaries of all scenes.
    
    Generates a summary document from all scene files.
    
    Example:
        novel summarize
        novel summarize --project ~/novels/my-story
    """
    try:
        project_dir = find_project_dir(project)
        typer.echo(f" 正在汇总项目：{project_dir}")

        from .commands.summarize import display_summary
        summary = display_summary(project_dir)
        typer.echo(summary)

    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def status(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON"
    )
):
    """Show current project status.
    
    Displays project information, current tick, and statistics.
    
    Example:
        novel status
        novel status --json
    """
    from .commands.status import get_status_info, display_status, display_status_json
    
    try:
        project_dir = Path(find_project_dir(project))
        state = load_project_state(project_dir)
        
        info = get_status_info(project_dir, state)
        
        if json_output:
            display_status_json(info)
        else:
            display_status(info)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command(name="list")
def list_entities(
    entity_type: str = typer.Argument(
        ...,
        help="Entity type to list: characters, locations, loops, scenes, factions"
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Show detailed information"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON"
    )
):
    """List entities in the project.
    
    Examples:
        novel list characters
        novel list locations --verbose
        novel list loops --json
        novel list scenes
    """
    from .commands.list import (
        list_characters, list_locations, list_open_loops, list_scenes, list_factions,
        display_characters, display_locations, display_loops, display_scenes, display_factions,
        display_json
    )
    
    try:
        project_dir = Path(find_project_dir(project))
        
        if entity_type == "characters":
            items = list_characters(project_dir, verbose)
            if json_output:
                display_json(items)
            else:
                display_characters(items, verbose)
        
        elif entity_type == "locations":
            items = list_locations(project_dir, verbose)
            if json_output:
                display_json(items)
            else:
                display_locations(items, verbose)
        
        elif entity_type == "loops":
            items = list_open_loops(project_dir, verbose)
            if json_output:
                display_json(items)
            else:
                display_loops(items, verbose)
        
        elif entity_type == "scenes":
            items = list_scenes(project_dir, verbose)
            if json_output:
                display_json(items)
            else:
                display_scenes(items, verbose)
        elif entity_type == "factions":
            items = list_factions(project_dir, verbose)
            if json_output:
                display_json(items)
            else:
                display_factions(items, verbose)
        
        else:
            typer.echo(f"[ERR] 未知实体类型：{entity_type}", err=True)
            typer.echo("有效类型：characters、locations、loops、scenes、factions", err=True)
            raise typer.Exit(1)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def inspect(
    id: Optional[str] = typer.Option(
        None,
        "--id",
        help="Entity ID (C0, L0, S001, etc.)"
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        help="Direct file path"
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output raw JSON"
    ),
    history_limit: int = typer.Option(
        5,
        "--history-limit",
        help="Number of history entries to show"
    )
):
    """Inspect detailed information about an entity.
    
    Examples:
        novel inspect --id C0
        novel inspect --id L3 --verbose
        novel inspect --file memory/characters/C0.json --raw
    """
    from .commands.inspect import inspect_entity
    
    try:
        project_dir = Path(find_project_dir(project))
        
        file_path = Path(file) if file else None
        success = inspect_entity(project_dir, id, file_path, raw, history_limit)
        
        if not success:
            raise typer.Exit(1)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def goals(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON"
    )
):
    """Show goal hierarchy and protagonist goals.
    
    Displays the story goal, protagonist goals (immediate, arc, story),
    and goal progress tracking.
    
    Example:
        novel goals
        novel goals --json
    """
    from .commands.goals import get_goals_info, display_goals, display_goals_json
    
    try:
        project_dir = Path(find_project_dir(project))
        state = load_project_state(project_dir)
        
        info = get_goals_info(project_dir, state)
        
        if json_output:
            display_goals_json(info)
        else:
            display_goals(info)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def lore(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    group_by: str = typer.Option(
        "category",
        "--group-by",
        "-g",
        help="Group by: category, type, or none"
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category"
    ),
    lore_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type (rule, fact, constraint, capability, limitation)"
    ),
    importance: Optional[str] = typer.Option(
        None,
        "--importance",
        "-i",
        help="Filter by importance (critical, important, normal, minor)"
    ),
    stats: bool = typer.Option(
        False,
        "--stats",
        "-s",
        help="Show statistics only"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON"
    )
):
    """Show world lore and rules (Phase 7A.4).
    
    Displays established world rules, constraints, and facts extracted
    from scenes. Helps maintain consistency and track world-building.
    
    Examples:
        novel lore                           # Show all lore grouped by category
        novel lore --group-by type           # Group by type instead
        novel lore --category magic          # Show only magic lore
        novel lore --importance critical     # Show only critical lore
        novel lore --stats                   # Show statistics
        novel lore --json                    # JSON output
    """
    from .commands.lore import (
        get_lore_info, display_lore, display_lore_json, display_lore_stats
    )
    
    try:
        project_dir = Path(find_project_dir(project))
        
        info = get_lore_info(project_dir)
        
        if json_output:
            display_lore_json(info)
        elif stats:
            display_lore_stats(info)
        else:
            display_lore(
                info,
                group_by=group_by,
                filter_category=category,
                filter_type=lore_type,
                filter_importance=importance
            )
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def compile(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    output: str = typer.Option(
        "manuscript.md",
        "--output",
        "-o",
        help="Output file path"
    ),
    format: str = typer.Option(
        "markdown",
        "--format",
        help="Output format: markdown, html, prose (prose = clean text, no headers)"
    ),
    include_metadata: bool = typer.Option(
        True,
        "--include-metadata/--no-metadata",
        help="Include metadata appendix"
    ),
    scenes: Optional[str] = typer.Option(
        None,
        "--scenes",
        help="Scene range: 1-10 or 5,7,9"
    )
):
    """Compile all scenes into a single manuscript.
    
    Examples:
        novel compile
        novel compile --output draft.md --scenes 1-10
        novel compile --format html --output manuscript.html
        novel compile --format prose --output story.txt  # Clean prose, no headers
    """
    from .commands.compile import compile_manuscript
    
    try:
        project_dir = Path(find_project_dir(project))
        output_path = Path(output)
        
        success = compile_manuscript(
            project_dir,
            output_path,
            format,
            include_metadata,
            scenes
        )
        
        if not success:
            raise typer.Exit(1)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@plot_app.command("status")
def plot_status(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project (default: current directory)",
    ),
    detailed: bool = typer.Option(
        False,
        "--detailed",
        "-d",
        help="Show detailed beat list with status and execution info",
    ),
):
    """Show plot outline status (beats and validation)."""
    try:
        project_dir = Path(find_project_dir(project))
        info = get_plot_status(project_dir)
        display_plot_status(info)
        if detailed:
            display_plot_status_detailed(project_dir)
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@plot_app.command("next")
def plot_next(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project (default: current directory)",
    ),
):
    """Show the next pending plot beat, if any."""
    try:
        project_dir = Path(find_project_dir(project))
        beat = get_next_beat(project_dir)
        display_next_beat(beat)
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@plot_app.command("generate")
def plot_generate(
    count: int = typer.Option(
        5,
        "--count",
        "-n",
        help="Number of beats to generate (stub; Phase 3 prompt to be implemented)",
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project (default: current directory)",
    ),
):
    """Generate plot beats using the PlotBeat Phase 3 prompt and append them.

    This is CLI-only and does not change the agent tick loop. Beats are stored
    in plot_outline.json and can be inspected with `novel plot status` and
    `novel plot next`.
    """
    try:
        project_dir = Path(find_project_dir(project))
        config = get_project_config(str(project_dir))

        # Determine LLM backend/model from project config (no CLI overrides for now)
        backend = config.get("llm.backend", "codex")
        codex_bin_effective = config.get("llm.codex_bin_path", "codex")
        model = (
            config.get("llm.model")
            or config.get("llm.openai_model", "gpt-5.1")
        )

        typer.echo(f" 项目：{project_dir}")
        typer.echo(f" 使用 LLM 后端：{backend}（模型={model}）")

        # Initialize LLM and generate beats
        try:
            initialize_llm(backend=backend, codex_bin=codex_bin_effective, model=model)
        except RuntimeError as e:
            typer.echo(f"[ERR] LLM 后端初始化失败：{e}", err=True)
            raise typer.Exit(1)

        result = generate_and_append_beats_cli(project_dir, count)
        display_generated_beats(result)

    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@plot_app.command("clear")
def plot_clear(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project (default: current directory)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
):
    """Clear all plot beats from the project.
    
    This deletes the plot_outline.json file. Beats will auto-regenerate
    when plot-first mode is active and the agent reaches the configured
    start tick (default: tick 2).
    
    Examples:
        novel plot clear              # With confirmation
        novel plot clear --yes        # Skip confirmation
    """
    try:
        from .commands.plot import clear_plot_outline
        
        project_dir = Path(find_project_dir(project))
        clear_plot_outline(project_dir, confirm=not yes)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def plan(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    save: Optional[str] = typer.Option(
        None,
        "--save",
        help="Save plan to file"
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Show full context and prompts"
    )
):
    """Preview the next plan without executing it.
    
    Examples:
        novel plan
        novel plan --save preview.json
        novel plan --verbose
    """
    from .commands.plan import preview_plan
    
    try:
        project_dir = Path(find_project_dir(project))
        save_path = Path(save) if save else None
        
        success = preview_plan(project_dir, save_path, verbose)
        
        if not success:
            raise typer.Exit(1)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def checkpoint(
    action: str = typer.Argument(
        ...,
        help="Action: create, list, restore, delete"
    ),
    checkpoint_id: Optional[str] = typer.Option(
        None,
        "--id",
        help="Checkpoint ID (for restore/delete)"
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project"
    ),
    message: Optional[str] = typer.Option(
        None,
        "--message",
        "-m",
        help="Description for checkpoint creation"
    )
):
    """Manage project checkpoints.
    
    Examples:
        novel checkpoint create --message "Before major plot twist"
        novel checkpoint list
        novel checkpoint restore --id checkpoint_tick_010
        novel checkpoint delete --id checkpoint_tick_005
    """
    from .commands.checkpoint import (
        create_checkpoint_cmd,
        list_checkpoints_cmd,
        restore_checkpoint_cmd,
        delete_checkpoint_cmd
    )
    
    try:
        project_dir = Path(find_project_dir(project))
        
        if action == "create":
            create_checkpoint_cmd(project_dir, message)
        elif action == "list":
            list_checkpoints_cmd(project_dir)
        elif action == "restore":
            if not checkpoint_id:
                typer.echo("[ERR] 恢复存档需要指定 --id", err=True)
                raise typer.Exit(1)
            restore_checkpoint_cmd(project_dir, checkpoint_id)
        elif action == "delete":
            if not checkpoint_id:
                typer.echo("[ERR] 删除存档需要指定 --id", err=True)
                raise typer.Exit(1)
            delete_checkpoint_cmd(project_dir, checkpoint_id)
        else:
            typer.echo(f"[ERR] 未知操作：{action}", err=True)
            typer.echo("有效操作：create、list、restore、delete", err=True)
            raise typer.Exit(1)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)
    except IOError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def recent(
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Number of recent projects to show"
    )
):
    """Show recently accessed novel projects.
    
    Lists projects you've worked on recently, ordered by last access time.
    Use this to find project paths with UUIDs.
    
    Example:
        novel recent
        novel recent --limit 5
    """
    try:
        recent_tracker = RecentProjects()
        projects = recent_tracker.get_recent(limit=limit)
        
        if not projects:
            typer.echo(" 暂无最近项目")
            typer.echo("\n 提示：对项目运行 'novel tick' 或 'novel run' 即可追踪")
            return

        typer.echo(f" 最近项目（共 {len(projects)} 个）：\n")
        
        for i, proj in enumerate(projects, 1):
            path = Path(proj['path'])
            name = proj.get('name', path.name)
            last_accessed = proj.get('last_accessed', 'unknown')
            
            # Load state to get tick count and UUID
            try:
                state = load_project_state(path)
                tick_count = state.get('current_tick', 0)
                tick_info = f"{tick_count} scenes"
                project_id = state.get('project_id', None)
            except:
                tick_info = "?"
                project_id = None
            
            typer.echo(f"  {i}. {name}")
            if project_id:
                typer.echo(f"     UUID：{project_id}")
            typer.echo(f"     路径：{path}")
            typer.echo(f"     章节：{tick_info}")
            typer.echo(f"     最近访问：{last_accessed[:19]}")  # Trim milliseconds
            typer.echo()
        
        typer.echo(" 提示：使用 'novel resume' 或 'novel resume --uuid <UUID>'")
        
    except Exception as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def resume(
    n: int = typer.Option(
        1,
        "--n",
        "-n",
        help="Number of ticks to run"
    ),
    uuid: Optional[str] = typer.Option(
        None,
        "--uuid",
        "-u",
        help="Resume project by UUID (e.g., 'f9f163a7')"
    )
):
    """Resume working on a recent project.
    
    Automatically finds and continues your most recently accessed project,
    or a specific project by UUID.
    
    Example:
        novel resume                    # Run 1 tick on most recent project
        novel resume --n 5              # Run 5 ticks on most recent project
        novel resume --uuid f9f163a7    # Resume specific project by UUID
    """
    try:
        recent_tracker = RecentProjects()
        
        # If UUID specified, find project by UUID
        if uuid:
            projects = recent_tracker.get_recent()
            matching_project = None
            
            for proj in projects:
                path = Path(proj['path'])
                # Check if path ends with UUID or state.json contains UUID
                if uuid in str(path):
                    matching_project = proj['path']
                    break
                # Also check state.json for project_id
                try:
                    state = load_project_state(path)
                    if state.get('project_id') == uuid:
                        matching_project = proj['path']
                        break
                except:
                    continue
            
            if not matching_project:
                typer.echo(f"[ERR] 未找到 UUID 为 {uuid} 的最近项目")
                typer.echo("\n 提示：使用 'novel recent' 查看可用项目")
                raise typer.Exit(1)
            
            recent_path = matching_project
        else:
            # Use most recent project
            recent_path = recent_tracker.get_most_recent()
            
            if not recent_path:
                typer.echo("[ERR] 暂无最近项目")
                typer.echo("\n 提示：使用 'novel new <名称>' 创建项目")
                raise typer.Exit(1)
        
        # Load project info
        state = load_project_state(Path(recent_path))
        project_name = state.get('novel_name', Path(recent_path).name)
        project_id = state.get('project_id', 'unknown')
        current_tick = state.get('current_tick', 0)
        
        typer.echo(f" Resuming: {project_name}")
        typer.echo(f"   Path: {recent_path}")
        typer.echo(f"   Current progress: {current_tick} scenes")
        typer.echo()
        
        # Run the ticks using the run command logic
        if n == 1:
            # Use tick command for single tick
            from pathlib import Path as P
            tick(project=str(recent_path))
        else:
            # Use run command for multiple ticks
            run(n=n, project=str(recent_path))
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def titles(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to novel project (default: current directory)",
    ),
    count: int = typer.Option(
        10,
        "--count",
        "-n",
        help="Number of title suggestions to generate",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for suggestions (default: print to console only)",
    ),
):
    """Generate title suggestions for the story.
    
    Uses the LLM to suggest compelling titles based on the story's
    foundation, themes, characters, and content.
    
    Examples:
        novel titles
        novel titles --count 15
        novel titles --output title_ideas.txt
    """
    from .commands.titles import generate_titles
    
    try:
        project_dir = Path(find_project_dir(project))
        output_path = Path(output) if output else None
        
        generate_titles(project_dir, count=count, output_file=output_path)
        
    except ValueError as e:
        typer.echo(f"[ERR] 错误：{e}", err=True)
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="监听地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", help="热重载（开发用）"),
):
    """启动 InkForge 服务（常驻进程模式）。

    以 HTTP 服务模式运行，提供 REST API。
    """
    from .server import start_server
    start_server(host=host, port=port, reload=reload)


# ---- skill commands ----------------------------------------------------


@skill_app.command("import")
def skill_import(
    file_path: str = typer.Argument(..., help="Novel file path (.txt)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Skill name (default: filename stem)"),
):
    """Import a novel file and extract a writing skill.

    Extracts style profiles, narrative patterns, and character archetypes
    via LLM analysis. Stores the result as YAML in data/skills/<slug>/.

    Example:
        novel skill import story.txt
        novel skill import story.txt --name "My Novel"
    """
    from .commands.skill import import_skill
    import_skill(file_path, name=name)


@skill_app.command("list")
def skill_list():
    """List all imported writing skills."""
    from .commands.skill import list_skills
    list_skills()


@skill_app.command("apply")
def skill_apply(
    slug: str = typer.Argument(..., help="Skill slug or ID"),
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project path (default: current directory)"
    ),
    mode: str = typer.Option(
        "reference", "--mode", "-m", help="Injection mode: reference, style_only, full"
    ),
):
    """Apply a writing skill to a novel project.

    Injects style profiles, narrative patterns, and character archetypes
    into the project state to guide the Writer and Planner.

    Example:
        novel skill apply sword-and-fairy-3
        novel skill apply sword-and-fairy-3 --project ./my-novel
        novel skill apply sword-and-fairy-3 --mode full
    """
    from .commands.skill import apply_skill
    from .project import find_project_dir
    project_dir = find_project_dir(project)
    apply_skill(slug, project_dir, mode=mode)


@skill_app.command("delete")
def skill_delete(
    slug: str = typer.Argument(..., help="Skill slug or ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a skill by slug or ID.

    Example:
        novel skill delete sword-and-fairy-3
        novel skill delete sword-and-fairy-3 --force
    """
    from .commands.skill import delete_skill
    delete_skill(slug, force=force)


def main():
    """Entry point for CLI."""
    setup_logging()
    app()


if __name__ == "__main__":
    main()
