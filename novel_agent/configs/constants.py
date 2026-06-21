"""Project-wide constants — single source of truth.

All magic numbers, directory names, file names, default URLs, and
thresholds live here.  Edit this file to adjust behaviour project-wide.

Imports should be lightweight (stdlib only) so every module can safely
``from novel_agent.configs.constants import ...``.
"""

# ---- LLM provider URLs & models -------------------------------------------

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"

DEFAULT_MODEL = "deepseek-chat"
OLLAMA_DEFAULT_MODEL = "huihui_ai/qwen3-abliterated:8b"

# ---- Timeouts & retries (seconds) ----------------------------------------

DEFAULT_LLM_TIMEOUT = 120
OLLAMA_LLM_TIMEOUT = 300
DEFAULT_MAX_RETRIES = 3

# ---- Project directory structure ------------------------------------------

# Subdirectories under <project>/memory/
MEMORY_SUBDIRS = ("characters", "locations", "scenes", "factions", "qa", "index")

# Subdirectories under <project>/
PROJECT_SUBDIRS = ("scenes", "plans", "errors")

# File names under <project>/
STATE_FILE = "state.json"
CONFIG_FILE = "config.yaml"
README_FILE = "README.md"

# File names under <project>/memory/
OPEN_LOOPS_FILE = "open_loops.json"
RELATIONSHIPS_FILE = "relationships.json"
LORE_FILE = "lore.json"
COUNTERS_FILE = "counters.json"
PLOT_OUTLINE_FILE = "plot_outline.json"

# ---- Data / template paths (relative to package root) ---------------------

DATA_NAMES_DIR = "data/names"
DATA_TEMPLATES_DIR = "data/templates"
DATA_SKILLS_DIR = "data/skills"
DATA_REFERENCES_DIR = "data/references"

# File names under data/skills/<slug>/
SKILL_FILE = "SKILL.yaml"

# ---- Token limits (LLM calls) ---------------------------------------------

DEFAULT_MAX_TOKENS = 2000
PLANNER_MAX_TOKENS = 4000
WRITER_MAX_TOKENS = 8192
EXTRACTOR_MAX_TOKENS = 2000
LORE_EXTRACTOR_MAX_TOKENS = 1500

STYLE_TAG_MAX_TOKENS = 200
PATTERN_EXTRACT_MAX_TOKENS = 500
ARCHETYPE_EXTRACT_MAX_TOKENS = 500
SLUG_GENERATION_MAX_TOKENS = 30
TITLE_GENERATION_MAX_TOKENS = 500

# ---- Evaluation thresholds ------------------------------------------------

BEAT_VERIFICATION_THRESHOLD = 0.5
BEAT_LOW_CONFIDENCE_THRESHOLD = 0.4
TENSION_LOW_THRESHOLD = 3
TENSION_HIGH_THRESHOLD = 7

# ---- Evaluation frequency (cost optimization) -----------------------------
# 前 N 幕每次都做全量 LLM 评估（黄金三章保证质量）
# 之后降频：每 N 幕做一次全量评估，其余只用关键词快速路径
EVAL_FULL_CHECK_FIRST_N = 3      # 前3章全量评估
EVAL_FULL_CHECK_INTERVAL = 3     # 之后每3章一次全量评估
EVAL_ASYNC_POST_PROCESS = True   # Fact/Lore 提取改为后台异步

# ---- Goal / loop promotion ------------------------------------------------

GOAL_PROMOTION_WINDOW_START = 10
GOAL_PROMOTION_WINDOW_END = 15
LOOP_MIN_MENTIONS_FOR_PROMOTION = 5
TOP_CHARACTERS_FOR_TITLES = 5
TOP_CHARACTER_IDS_FOR_TITLES = 10

# ---- Thread audit ----------------------------------------------------------

THREAD_AUDIT_INTERVAL = 5       # 每 N 章触发 LLM 支线审计
THREAD_STALE_WARN = 4           # 停滞提醒阈值（章）
THREAD_STALE_FORCE = 8          # 强制推进阈值（章）

# ---- Quality scoring (黄金三章打磨闭环) -----------------------------------

QUALITY_THRESHOLD_EARLY = 95    # 前三章质量阈值（0-100）
QUALITY_THRESHOLD_NORMAL = 85   # 正常章节质量阈值
QUALITY_FIRST_N_TICKS = 3       # 前N章启用严格打磨
MAX_POLISH_ROUNDS = 3           # 最大打磨轮数

# ---- Text sampling --------------------------------------------------------

TEXT_SAMPLE_CHARS = 3000
SKILL_IMPORT_SAMPLE_CHARS = 6000
SKILL_ARCHETYPE_SAMPLE_CHARS = 4000
RECENT_PROJECTS_LIMIT = 10

# ---- Writer cleanup -------------------------------------------------------

# Lines starting with these phrases are LLM meta-reasoning, not prose.
META_MARKERS = [
    "I'll start by listing the current directory",
    "I'll start by listing the current directory's files",
    "current directory's files",
    "I'll check `docs`",
    "I'll check `work`",
    "Python project, `novel_agent` package",
    "I'm writing a scene for",
]

# ---- Server ---------------------------------------------------------------

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8221

# ---- Tool execution -------------------------------------------------------

MAX_TOOLS_PER_TICK = 3
