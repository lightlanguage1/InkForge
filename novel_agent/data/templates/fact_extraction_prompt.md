从以下场景中提取结构化事实更新。所有输出内容必须使用中文。只返回 JSON，不要任何说明、markdown 标记或额外文字。

════════════════════════════════════════
【输入】
════════════════════════════════════════

场景文本：
{scene_text}

POV 角色 ID：{pov_character_id}
地点 ID：{location_id}

已有开放线索：
{existing_open_loops}

════════════════════════════════════════
【提取规则（优先于一切）】
════════════════════════════════════════

① 只提取场景中明确展示的内容——不推断、不假设、不补全
② 无变化时对应字段返回 null，不要编造占位内容
③ 列表字段只包含本场景新增的项目，不重复已有内容
④ 线索判断标准：
   · open_loops_created — 场景中新出现的、尚未解决的悬念或问题
   · open_loops_resolved — 已有线索 ID，且在本场景中得到了明确的解决或闭合
   · 不确定是否解决时，保留为开放状态（宁可不关，不要误关）
⑤ 关系变化标准：仅当两个角色之间的关系性质在本场景中发生了可观察的变化时才填写
⑥ importance 取值：low | medium | high | critical（根据对主线的影响程度判断）

════════════════════════════════════════
【输出格式】
════════════════════════════════════════

{
  "character_updates": [
    {
      "id": "C000",
      "changes": {
        "emotional_state": "字符串或 null",
        "physical_state": "字符串或 null",
        "inventory": ["物品1", "物品2"],
        "goals": ["目标1"],
        "beliefs": ["信念1"]
      }
    }
  ],
  "location_updates": [
    {
      "id": "L000",
      "changes": {
        "description": "字符串或 null",
        "atmosphere": "字符串或 null",
        "features": ["特征1"]
      }
    }
  ],
  "open_loops_created": [
    {
      "description": "用中文描述的新线索",
      "importance": "low|medium|high|critical",
      "category": "根据故事情境自行归类",
      "related_characters": ["C000"],
      "related_locations": ["L000"]
    }
  ],
  "open_loops_resolved": ["OL1"],
  "relationship_changes": [
    {
      "character_a": "C000",
      "character_b": "C001",
      "changes": {
        "status": "字符串或 null",
        "perspective_a": "字符串或 null",
        "perspective_b": "字符串或 null",
        "intensity": 0
      }
    }
  ]
}