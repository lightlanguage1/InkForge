"""Lore extraction from scene prose for world consistency tracking (Phase 7A.4)."""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


LORE_EXTRACTION_PROMPT = """你是一位世界观分析专家，从场景文本中提取已确立的世界规则。

**所有字段必须用中文书写。**

你的任务是识别本场景中已确立的重要世界规则。关注任何定义世界运作方式的信息——无论是物理定律、社会规范、科技水平、魔法体系、还是其他任何影响故事一致性的设定。

**不要提取：**
- 角色情绪或临时状态
- 情节事件或动作本身
- 琐碎细节
- 已经显而易见或通用的常识

## 场景文本

{scene_text}

## 上下文

**POV 角色：**{pov_character_name}（{pov_character_id}）
**地点：**{location_name}（{location_id}）
**Tick：**{tick}

## 输出格式

为每条世界观信息提供：
1. **type**：根据本条目的性质自行归类（如 规则、事实、约束、能力、限制 等）
2. **content**：清晰的陈述（1-2句话）
3. **category**：根据故事世界观自行归类（不要用固定枚举，根据故事实际语境取名）
4. **importance**：critical（核心世界规则）、important（重要约束）、normal（有用细节）、minor（参考信息）
5. **tags**：1-3个中文标签

返回 JSON：

```json
{{
  "lore_items": [
    {{
      "type": "由此场景语境决定",
      "content": "用中文书写的世界观陈述",
      "category": "由此场景语境决定",
      "importance": "critical|important|normal|minor",
      "tags": ["标签1", "标签2"]
    }}
  ]
}}
```

如果没有重要的世界观被确立，返回：
```json
{{
  "lore_items": []
}}
```

只提取明确且重要的世界观条目。有疑问时不提取。
"""


class LoreExtractor:
    """Extracts world lore from scene prose using LLM (Phase 7A.4)."""
    
    def __init__(self, llm_interface, memory_manager, config):
        """Initialize lore extractor.
        
        Args:
            llm_interface: LLM interface for text generation
            memory_manager: Memory manager for accessing entities
            config: Configuration object
        """
        self.llm = llm_interface
        self.memory = memory_manager
        self.config = config
    
    def extract_lore(self, scene_text: str, scene_context: dict, tick: int) -> List[Dict[str, Any]]:
        """Extract lore from scene prose.
        
        Args:
            scene_text: The generated scene prose
            scene_context: Context used to write the scene (POV character, location, etc.)
            tick: Current tick number
        
        Returns:
            List of lore items:
            [
                {
                    "type": "rule",
                    "content": "...",
                    "category": "magic",
                    "importance": "critical",
                    "tags": [...]
                },
                ...
            ]
        """
        # Check if lore tracking is enabled
        if not self.config.get('generation.enable_lore_tracking', True):
            logger.info("Lore tracking disabled, skipping extraction")
            return []
        
        try:
            # Build extraction prompt
            prompt = self._build_extraction_prompt(scene_text, scene_context, tick)
            
            # Get max tokens from config
            max_tokens = self.config.get('llm.lore_extractor_max_tokens', 1500)
            
            # Call LLM
            logger.info("Extracting lore from scene prose...")
            response = self.llm.generate(prompt, max_tokens=max_tokens)
            
            # Parse response
            lore_items = self._parse_extraction_response(response)
            
            logger.info(f"Extracted {len(lore_items)} lore items")
            
            return lore_items
            
        except Exception as e:
            logger.error(f"Error extracting lore: {e}")
            return []
    
    def _build_extraction_prompt(self, scene_text: str, scene_context: dict, tick: int) -> str:
        """Build prompt for lore extraction.
        
        Args:
            scene_text: Scene prose
            scene_context: Scene context
            tick: Current tick
        
        Returns:
            Formatted prompt string
        """
        # Get POV character and location
        pov_char_id = scene_context.get('pov_character')
        location_id = scene_context.get('location')
        
        pov_char = self.memory.load_character(pov_char_id) if pov_char_id else None
        location = self.memory.load_location(location_id) if location_id else None
        
        # Use display name for natural reference in lore extraction
        pov_char_name = pov_char.display_name if pov_char else "Unknown"
        location_name = location.name if location else "Unknown"
        
        return LORE_EXTRACTION_PROMPT.format(
            scene_text=scene_text,
            pov_character_name=pov_char_name,
            pov_character_id=pov_char_id or "Unknown",
            location_name=location_name,
            location_id=location_id or "Unknown",
            tick=tick
        )
    
    def _parse_extraction_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into lore items.
        
        Args:
            response: LLM response text
        
        Returns:
            List of lore item dictionaries
        """
        try:
            # Try to find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in lore extraction response")
                return []
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            lore_items = data.get('lore_items', [])
            
            # Validate each lore item
            validated_items = []
            for item in lore_items:
                if self._validate_lore_item(item):
                    validated_items.append(item)
                else:
                    logger.warning(f"Invalid lore item skipped: {item}")
            
            return validated_items
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lore extraction JSON: {e}")
            logger.debug(f"Response was: {response}")
            return []
        except Exception as e:
            logger.error(f"Error parsing lore extraction response: {e}")
            return []
    
    def _validate_lore_item(self, item: dict) -> bool:
        """Validate a lore item has required fields.
        
        Args:
            item: Lore item dictionary
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['type', 'content', 'category', 'importance']
        
        for field in required_fields:
            if field not in item or not item[field]:
                return False
        
        # Validate type
        valid_types = ['rule', 'fact', 'constraint', 'capability', 'limitation']
        if item['type'] not in valid_types:
            return False
        
        # Validate importance
        valid_importance = ['critical', 'important', 'normal', 'minor']
        if item['importance'] not in valid_importance:
            return False
        
        # Ensure tags is a list
        if 'tags' not in item:
            item['tags'] = []
        elif not isinstance(item['tags'], list):
            item['tags'] = []
        
        return True
