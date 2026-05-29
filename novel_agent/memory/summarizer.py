"""Scene summarization using LLM."""

from typing import List


class SceneSummarizer:
    """Generates concise bullet-point summaries of scenes."""
    
    def __init__(self, llm_interface):
        """Initialize summarizer.
        
        Args:
            llm_interface: LLM interface for text generation
        """
        self.llm = llm_interface
    
    def summarize_scene(self, scene_text: str, max_bullets: int = 5) -> List[str]:
        """Generate bullet-point summary of a scene.
        
        Args:
            scene_text: Full scene text
            max_bullets: Maximum number of bullet points (default: 5)
        
        Returns:
            List of summary bullet points
        """
        prompt = self._build_summary_prompt(scene_text, max_bullets)
        
        # Call LLM
        response = self.llm.generate(prompt)
        
        # Parse bullet points
        bullets = self._parse_bullets(response)
        
        return bullets[:max_bullets]
    
    def _build_summary_prompt(self, scene_text: str, max_bullets: int) -> str:
        """Build prompt for scene summarization.
        
        Args:
            scene_text: Scene text to summarize
            max_bullets: Max bullet points
        
        Returns:
            Formatted prompt
        """
        prompt = f"""阅读以下场景文本，生成 {max_bullets} 条简洁的要点摘要，覆盖：
- 发生的关键事件
- 重要的角色行动或决定
- 揭示的新信息
- 情感或关系变化

请具体、事实性地描述。每条要点为一个完整句子，用中文书写。

场景：
{scene_text}

摘要（仅输出要点，每行一条）："""
        
        return prompt
    
    def _parse_bullets(self, response: str) -> List[str]:
        """Parse bullet points from LLM response.
        
        Args:
            response: Raw LLM response
        
        Returns:
            List of cleaned bullet points
        """
        lines = response.strip().split('\n')
        bullets = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Remove common bullet markers
            for marker in ['- ', '* ', '• ', '1. ', '2. ', '3. ', '4. ', '5. ']:
                if line.startswith(marker):
                    line = line[len(marker):].strip()
                    break
            
            # Skip if too short
            if len(line) < 10:
                continue
            
            bullets.append(line)
        
        return bullets
    
    def summarize_multiple_scenes(self, scene_texts: List[str]) -> str:
        """Generate an overall summary of multiple scenes.
        
        Args:
            scene_texts: List of scene texts
        
        Returns:
            Overall summary paragraph
        """
        prompt = f"""阅读以下 {len(scene_texts)} 个场景，用中文生成一个简洁的段落，总结整体故事进展。

场景：
"""
        for i, text in enumerate(scene_texts, 1):
            prompt += f"\n--- 场景 {i} ---\n{text}\n"

        prompt += "\n整体摘要："
        
        response = self.llm.generate(prompt)
        return response.strip()
