"""Story foundation prompting and loading for project creation."""

import typer
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List


class StoryFoundation:
    """Represents the immutable story foundation."""
    
    def __init__(
        self,
        genre: str,
        premise: str,
        protagonist_archetype: str,
        setting: str,
        tone: str,
        themes: Optional[List[str]] = None,
        primary_goal: Optional[str] = None
    ):
        self.genre = genre
        self.premise = premise
        self.protagonist_archetype = protagonist_archetype
        self.setting = setting
        self.tone = tone
        self.themes = themes or []
        self.primary_goal = primary_goal  # Optional user-specified story goal
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state.json."""
        return {
            "genre": self.genre,
            "premise": self.premise,
            "protagonist_archetype": self.protagonist_archetype,
            "setting": self.setting,
            "tone": self.tone,
            "themes": self.themes,
            "primary_goal": self.primary_goal
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryFoundation":
        """Create from dictionary."""
        return cls(
            genre=data["genre"],
            premise=data["premise"],
            protagonist_archetype=data["protagonist_archetype"],
            setting=data["setting"],
            tone=data["tone"],
            themes=data.get("themes", []),
            primary_goal=data.get("primary_goal")
        )


def prompt_for_foundation() -> tuple[StoryFoundation, Dict[str, Any]]:
    """Interactively prompt user for story foundation and plot-first configuration.
    
    Returns:
        Tuple of (StoryFoundation object, plot_config dict)
    """
    typer.echo("\n 故事基础设定")
    typer.echo("━" * 60)
    typer.echo("\n设定故事的核心约束条件。\n")
    
    # Genre
    genre = typer.prompt(
        "故事类型（如：仙侠、科幻、悬疑、现实）",
        type=str
    ).strip()

    # Premise
    typer.echo("\n故事前提（1-2句，描述故事核心问题）：")
    premise = typer.prompt("", type=str).strip()

    # Protagonist archetype
    protagonist_archetype = typer.prompt(
        "\n主角性格/定位",
        type=str
    ).strip()

    # Setting
    setting = typer.prompt(
        "故事背景（时代/地点/世界观）",
        type=str
    ).strip()

    # Tone
    tone = typer.prompt(
        "基调（氛围/风格）",
        type=str
    ).strip()

    # Themes (optional)
    themes_input = typer.prompt(
        "主题（可选，逗号分隔）",
        default="",
        type=str
    ).strip()

    themes = [t.strip() for t in themes_input.split(",") if t.strip()] if themes_input else []

    # Primary goal (optional)
    primary_goal = typer.prompt(
        "主要故事目标（可选，留空则自动生成）",
        default="",
        type=str
    ).strip()
    
    primary_goal = primary_goal if primary_goal else None
    
    # Plot-First Mode Configuration
    typer.echo("\n" + "━" * 60)
    typer.echo(" 情节优先模式配置")
    typer.echo("━" * 60)
    typer.echo("\n情节优先模式会生成情节节拍，引导场景生成。")
    typer.echo("这能提供叙事推进力并减少重复。\n")
    
    use_plot_first = typer.confirm(
        "启用情节优先模式？（结构化故事推荐开启）",
        default=False
    )
    
    plot_config = {}
    
    if use_plot_first:
        typer.echo("\n 情节优先设置：")
        
        # Enforcement level
        typer.echo("\n执行级别：")
        typer.echo("  1. 宽松 - 节拍引导但不阻断（回退到被动模式）")
        typer.echo("  2. 标准 - 验证节拍，未完成时允许跳过")
        typer.echo("  3. 严格 - 必须完成节拍，无回退（推荐）")
        
        enforcement = typer.prompt(
            "\n请选择执行级别",
            type=int,
            default=3
        )
        
        if enforcement == 1:
            # Lenient mode
            plot_config = {
                "use_plot_first": True,
                "plot_first_start_tick": 2,
                "plot_beats_ahead": 5,
                "plot_regeneration_threshold": 2,
                "verify_beat_execution": True,
                "allow_beat_skip": True,
                "fallback_to_reactive": True
            }
        elif enforcement == 2:
            # Standard mode
            plot_config = {
                "use_plot_first": True,
                "plot_first_start_tick": 2,
                "plot_beats_ahead": 5,
                "plot_regeneration_threshold": 2,
                "verify_beat_execution": True,
                "allow_beat_skip": True,
                "fallback_to_reactive": False
            }
        else:
            # Strict mode (default)
            plot_config = {
                "use_plot_first": True,
                "plot_first_start_tick": 2,
                "plot_beats_ahead": 5,
                "plot_regeneration_threshold": 2,
                "verify_beat_execution": True,
                "allow_beat_skip": False,
                "fallback_to_reactive": False
            }
        
        # Advanced options
        if typer.confirm("\n自定义高级设置？", default=False):
            plot_config["plot_beats_ahead"] = typer.prompt(
                "  每次生成节拍数",
                type=int,
                default=5
            )
            plot_config["plot_regeneration_threshold"] = typer.prompt(
                "  待执行节拍低于此数时重新生成",
                type=int,
                default=2
            )
    else:
        # Plot-first disabled
        plot_config = {
            "use_plot_first": False
        }
    
    # Confirmation
    typer.echo("\n" + "━" * 60)
    typer.echo(" 基础设定摘要：")
    typer.echo(f"  类型：{genre}")
    typer.echo(f"  前提：{premise}")
    typer.echo(f"  主角：{protagonist_archetype}")
    typer.echo(f"  背景：{setting}")
    typer.echo(f"  基调：{tone}")
    if themes:
        typer.echo(f"  主题：{', '.join(themes)}")
    if primary_goal:
        typer.echo(f"  主要目标：{primary_goal}")

    typer.echo("\n 情节配置：")
    if plot_config.get("use_plot_first"):
        if not plot_config.get("allow_beat_skip") and not plot_config.get("fallback_to_reactive"):
            typer.echo("  模式：严格（强制节拍）")
        elif plot_config.get("allow_beat_skip"):
            typer.echo("  模式：宽松/标准（节拍引导）")
        typer.echo(f"  每次节拍数：{plot_config.get('plot_beats_ahead', 5)}")
        typer.echo(f"  重生成阈值：{plot_config.get('plot_regeneration_threshold', 2)}")
    else:
        typer.echo("  模式：被动（无情节节拍）")
    typer.echo("━" * 60)

    confirm = typer.confirm("\n确认以上配置并继续？", default=True)
    if not confirm:
        typer.echo("设置已取消。")
        raise typer.Abort()
    
    foundation = StoryFoundation(
        genre=genre,
        premise=premise,
        protagonist_archetype=protagonist_archetype,
        setting=setting,
        tone=tone,
        themes=themes,
        primary_goal=primary_goal
    )
    
    return foundation, plot_config


def load_foundation_from_file(file_path: Path) -> StoryFoundation:
    """Load story foundation from YAML file.
    
    Args:
        file_path: Path to YAML file containing foundation
    
    Returns:
        StoryFoundation object
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid or missing required fields
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Foundation file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML file: {e}")
    
    # Validate required fields
    required_fields = ["genre", "premise", "protagonist_archetype", "setting", "tone"]
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        raise ValueError(f"Missing required fields in foundation file: {', '.join(missing_fields)}")
    
    # Parse themes if present
    themes = data.get("themes", [])
    if isinstance(themes, str):
        themes = [t.strip() for t in themes.split(",") if t.strip()]
    elif not isinstance(themes, list):
        themes = []
    
    # Get primary goal if present
    primary_goal = data.get("primary_goal")
    
    return StoryFoundation(
        genre=data["genre"],
        premise=data["premise"],
        protagonist_archetype=data["protagonist_archetype"],
        setting=data["setting"],
        tone=data["tone"],
        themes=themes,
        primary_goal=primary_goal
    )


def create_foundation_from_args(
    genre: Optional[str] = None,
    premise: Optional[str] = None,
    protagonist: Optional[str] = None,
    setting: Optional[str] = None,
    tone: Optional[str] = None,
    themes: Optional[str] = None
) -> Optional[StoryFoundation]:
    """Create foundation from command-line arguments.
    
    Args:
        genre: Story genre
        premise: Story premise
        protagonist: Protagonist archetype
        setting: Story setting
        tone: Story tone
        themes: Comma-separated themes
    
    Returns:
        StoryFoundation if all required fields provided, None otherwise
    """
    # Check if any foundation args were provided
    if not any([genre, premise, protagonist, setting, tone]):
        return None
    
    # If some but not all are provided, prompt for missing ones
    if not all([genre, premise, protagonist, setting, tone]):
        typer.echo("[WARN]  部分基础设定字段已提供，但并非全部。请提供所有必填字段：")
        typer.echo("   --genre、--premise、--protagonist、--setting、--tone")
        raise typer.Exit(1)
    
    # Parse themes
    theme_list = [t.strip() for t in themes.split(",") if t.strip()] if themes else []
    
    return StoryFoundation(
        genre=genre,
        premise=premise,
        protagonist_archetype=protagonist,
        setting=setting,
        tone=tone,
        themes=theme_list
    )


def format_foundation_display(foundation: StoryFoundation) -> str:
    """Format foundation for display in status command.
    
    Args:
        foundation: StoryFoundation object
    
    Returns:
        Formatted string for display
    """
    lines = [
        " Story Foundation",
        "━" * 60,
        f"Genre: {foundation.genre}",
        f"Premise: {foundation.premise}",
        f"Protagonist: {foundation.protagonist_archetype}",
        f"Setting: {foundation.setting}",
        f"Tone: {foundation.tone}",
    ]
    
    if foundation.themes:
        lines.append(f"Themes: {', '.join(foundation.themes)}")
    
    return "\n".join(lines)
