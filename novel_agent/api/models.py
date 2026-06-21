"""所有 Pydantic 请求/响应模型 — API 数据契约。"""

from typing import List, Optional
from pydantic import BaseModel


# --- 项目 ---

class ProjectCreateRequest(BaseModel):
    name: str
    directory: Optional[str] = None
    genre: Optional[str] = None
    premise: Optional[str] = None
    protagonist: Optional[str] = None
    setting: Optional[str] = None
    tone: Optional[str] = None
    themes: Optional[str] = None
    primary_goal: Optional[str] = None
    use_plot_first: bool = False
    skill_ids: List[str] = []
    style_id: Optional[str] = None
    craft_id: Optional[str] = None


class TickRequest(BaseModel):
    project_path: str = ""
    save_prompts: bool = False
    llm_backend: Optional[str] = None
    llm_model: Optional[str] = None
    notes: Optional[str] = None


class TickResponse(BaseModel):
    success: bool
    tick: int
    scene_id: str
    scene_file: str
    word_count: int
    actions_executed: int
    tension: Optional[dict] = None


class CompileRequest(BaseModel):
    format: str = "markdown"
    include_metadata: bool = True
    scene_range: Optional[str] = None


class TitleRequest(BaseModel):
    count: int = 10


# --- 节拍 ---

class BeatGenerateRequest(BaseModel):
    count: int = 5


# --- 技能 ---

class SkillImportRequest(BaseModel):
    file_path: str
    name: Optional[str] = None


class SkillApplyRequest(BaseModel):
    project_path: str
    skill_ids: List[str]
    mode: str = "reference"


# --- 参考 ---

class ReferenceImportRequest(BaseModel):
    file_path: str
    title: Optional[str] = None


class ReferenceSearchRequest(BaseModel):
    query: str
    top_k: int = 3
    source_filter: Optional[str] = None


# --- 存档 ---

class CheckpointCreateRequest(BaseModel):
    message: Optional[str] = None
