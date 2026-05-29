从本场景中提取结构化更新。

**所有输出内容必须使用中文。**

场景：{scene_text}

POV：{pov_character_id} | 地点：{location_id}

已有开放线索：{existing_open_loops}

只返回 JSON，包含以下更新：

```json
{{
  "character_updates": [
    {{
      "id": "C000",
      "changes": {{
        "emotional_state": "字符串或 null",
        "physical_state": "字符串或 null",
        "inventory": ["物品1", "物品2"] 或 null,
        "goals": ["目标1", "目标2"] 或 null,
        "beliefs": ["信念1", "信念2"] 或 null
      }}
    }}
  ],
  "location_updates": [
    {{
      "id": "L000",
      "changes": {{
        "description": "字符串或 null",
        "atmosphere": "字符串或 null",
        "features": ["特征1", "特征2"] 或 null
      }}
    }}
  ],
  "open_loops_created": [
    {{
      "description": "用中文描述的新线索",
      "importance": "low|medium|high|critical",
      "category": "根据故事情境自行归类",
      "related_characters": ["C000"],
      "related_locations": ["L000"]
    }}
  ],
  "open_loops_resolved": ["OL1", "OL2"],
  "relationship_changes": [
    {{
      "character_a": "C000",
      "character_b": "C001",
      "changes": {{
        "status": "字符串或 null",
        "perspective_a": "字符串或 null",
        "perspective_b": "字符串或 null",
        "intensity": 0-10 或 null
      }}
    }}
  ]
}}
```

规则：无变化时用 null。只提取场景中明确展示的内容。列表只包含新增项。
