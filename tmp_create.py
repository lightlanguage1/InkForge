import sys
sys.path.insert(0, '/app')
from novel_agent.engine.core import EngineCore
from novel_agent.configs.config import Config
from novel_agent.user.db import Database
import json

config = Config()
engine = EngineCore(config.to_dict())

path = engine.create_project(
    name='星海修仙传',
    directory='/app/work/users/1bd34fa3a353/novels',
    genre='仙侠科幻',
    premise='星际考古学家在遗迹中发现上古修仙法门——宇宙的物理法则和修仙法则竟是同一套系统的两面',
    protagonist='林朔，星际考古学家，逻辑缜密，感情迟钝，对未知有着近乎偏执的好奇心',
    setting='人类星际殖民时代，边缘星球发现与地球上古文明相似的修炼遗迹',
    tone='宏大冷静的太空歌剧与东方仙侠的融合，孤独感与求知欲交织',
    themes='科学与玄学的统一、文明的真相、孤独探索者的自我救赎',
    primary_goal='揭开宇宙法则的双重本质——为什么物理定律和修仙法门是同一套代码',
    use_plot_first=True,
)
print(f'Created: {path}')

state = json.loads(open(f"{path}/state.json").read())
pid = path.split("/")[-1]
Database().upsert_project('1bd34fa3a353', pid, '星海修仙传')
print(f'Project ID: {pid}')
print(f'Tick: {state.get("current_tick", 0)}')
