"""基础设施组装工厂 — CLI 和 API 共用的唯一入口。

将所有 StoryAgent 依赖组装集中于此，避免 CLI tick()/run()
和 API server 中重复初始化逻辑。
"""

from pathlib import Path
from typing import Optional

from ..configs.constants import DATA_NAMES_DIR
from ..tools.llm_interface import initialize_llm
from ..tools.registry import ToolRegistry
from ..tools.memory_tools import (
    MemorySearchTool,
    CharacterGenerateTool,
    LocationGenerateTool,
    RelationshipCreateTool,
    RelationshipUpdateTool,
    RelationshipQueryTool,
    FactionGenerateTool,
    FactionUpdateTool,
    FactionQueryTool,
)
from ..tools.name_generator import NameGeneratorTool
from ..memory.manager import MemoryManager
from ..memory.vector_store import VectorStore
from .agent import StoryAgent


def create_agent(
    project_dir: Path,
    config: dict,
    llm_backend: Optional[str] = None,
    llm_model: Optional[str] = None,
    codex_bin: Optional[str] = None,
    save_prompts: bool = False,
) -> StoryAgent:
    """创建 StoryAgent 实例，组装全部依赖。

    这是 CLI 和 API 共用的唯一入口。每次调用创建一个新的 agent
    实例（读取最新的 state.json），支持 run() 中每幕重建。

    Args:
        project_dir: 项目根目录
        config: 项目配置（dict 或 Config 对象）
        llm_backend: CLI 覆盖的后端 (codex/api/gemini-cli/claude-cli/ollama)
        llm_model: CLI 覆盖的模型名
        codex_bin: CLI 覆盖的 codex 二进制路径
        save_prompts: 是否保存 prompt 到文件

    Returns:
        完全初始化的 StoryAgent 实例
    """
    # --- 解析 LLM 后端和模型 (CLI 参数 > config > 默认) ---
    backend = llm_backend or config.get('llm.backend', 'codex')
    codex_bin_effective = codex_bin or config.get('llm.codex_bin_path', 'codex')
    model = (
        llm_model
        or config.get('llm.model')
        or config.get('llm.openai_model', 'gpt-5.1')
    )

    # --- 初始化 LLM ---
    llm = initialize_llm(
        backend=backend,
        codex_bin=codex_bin_effective,
        model=model,
        temperature=config.get('llm.temperature', 0.7),
        top_p=config.get('llm.top_p', 0.8),
        top_k=config.get('llm.top_k', 20),
        min_p=config.get('llm.min_p', 0.0),
        repeat_penalty=config.get('llm.repeat_penalty', 1.0),
        enable_thinking=config.get('llm.enable_thinking', False),
    )

    # --- 初始化工具注册表和记忆组件 ---
    tool_registry = ToolRegistry()
    memory_manager = MemoryManager(project_dir)
    vector_store = VectorStore(project_dir)

    # --- 注册 10 个工具 ---
    data_dir = Path(__file__).parent.parent / DATA_NAMES_DIR
    name_gen_tool = NameGeneratorTool(data_dir)
    beat_mode = config.get('plot.beat_mode', 'soft_hint')

    tool_registry.register(name_gen_tool)
    tool_registry.register(MemorySearchTool(memory_manager, vector_store))
    tool_registry.register(CharacterGenerateTool(
        memory_manager, vector_store, name_gen_tool.generator, beat_mode=beat_mode,
    ))
    tool_registry.register(LocationGenerateTool(memory_manager, vector_store))
    tool_registry.register(RelationshipCreateTool(memory_manager))
    tool_registry.register(RelationshipUpdateTool(memory_manager))
    tool_registry.register(RelationshipQueryTool(memory_manager))
    tool_registry.register(FactionGenerateTool(
        memory_manager, vector_store, name_gen_tool.generator,
    ))
    tool_registry.register(FactionUpdateTool(memory_manager, vector_store))
    tool_registry.register(FactionQueryTool(memory_manager, vector_store))

    # --- 创建 Agent ---
    return StoryAgent(project_dir, llm, tool_registry, config, save_prompts=save_prompts)
