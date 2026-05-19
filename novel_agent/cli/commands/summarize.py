"""Summarize command - generate scene summary document."""

from pathlib import Path
from typing import List
from ...memory.manager import MemoryManager


def generate_summary(project_dir: Path) -> str:
    """Generate a comprehensive summary of all scenes.

    Args:
        project_dir: Path to novel project directory

    Returns:
        Markdown-formatted summary string
    """
    memory = MemoryManager(project_dir)
    scene_ids = memory.list_scenes()

    if not scene_ids:
        return "# Story Summary\n\n*No scenes found.*\n"

    sections: List[str] = ["# Story Summary\n"]

    # Collect stats
    total_words = 0
    tensions: list = []
    pov_characters: set = set()

    for sid in sorted(scene_ids):
        scene = memory.load_scene(sid)
        if not scene:
            continue

        sections.append(f"## Scene {scene.tick}: {scene.title or 'Untitled'}")
        sections.append(f"**ID:** {scene.id}")
        sections.append(f"**POV:** {scene.pov_character_id or 'N/A'}")
        sections.append(f"**Location:** {scene.location_id or 'N/A'}")

        if scene.tension_level is not None:
            sections.append(f"**Tension:** {scene.tension_level}/10")
            tensions.append(scene.tension_level)

        if scene.characters_present:
            sections.append(f"**Characters:** {', '.join(scene.characters_present)}")

        if scene.summary:
            sections.append("\n**Summary:**")
            for point in scene.summary:
                sections.append(f"- {point}")

        if scene.key_events:
            sections.append("\n**Key Events:**")
            for event in scene.key_events:
                sections.append(f"- {event}")

        if scene.open_loops_created:
            sections.append(f"\n**Loops Created:** {', '.join(scene.open_loops_created)}")
        if scene.open_loops_resolved:
            sections.append(f"\n**Loops Resolved:** {', '.join(scene.open_loops_resolved)}")

        sections.append("")
        total_words += scene.word_count or 0
        if scene.pov_character_id:
            pov_characters.add(scene.pov_character_id)

    # Add overall stats
    sections.insert(1, f"**Total Scenes:** {len(scene_ids)}")
    sections.insert(2, f"**Total Word Count:** {total_words}")
    sections.insert(3, f"**POV Characters:** {', '.join(sorted(pov_characters))}")
    if tensions:
        avg_tension = sum(tensions) / len(tensions)
        sections.insert(4, f"**Average Tension:** {avg_tension:.1f}/10")
    sections.insert(5, "---\n")

    return "\n".join(sections)


def display_summary(project_dir: Path) -> str:
    """Generate and display project summary.

    Args:
        project_dir: Path to novel project directory

    Returns:
        Generated summary text
    """
    summary = generate_summary(project_dir)

    # Also write to project directory
    summary_file = project_dir / "summary.md"
    try:
        summary_file.write_text(summary, encoding="utf-8")
    except IOError:
        pass  # Writing summary file is optional

    return summary
