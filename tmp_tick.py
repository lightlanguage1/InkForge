import sys, json
sys.path.insert(0, '/app')
from novel_agent.agent.agent import StoryAgent
from novel_agent.tools.llm_interface import LLMInterface
from novel_agent.tools.registry import ToolRegistry
from novel_agent.memory.manager import MemoryManager
from novel_agent.memory.vector_store import VectorStore
from novel_agent.tools.memory_tools import *
from novel_agent.configs.config import Config
from pathlib import Path

project_dir = Path('/app/work/users/1bd34fa3a353/novels/星海修仙传_e40636ba')
config_obj = Config()
config = config_obj.to_dict()

llm = LLMInterface(config)
agent = StoryAgent(project_dir, llm, ToolRegistry(), config)
result = agent.tick()
print(json.dumps(result, ensure_ascii=False, indent=2))
