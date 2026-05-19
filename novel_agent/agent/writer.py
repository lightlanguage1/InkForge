"""Scene writer for generating prose with API/local fallback."""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Patterns that indicate the API refused to generate content.
# Checked only in the first 400 chars \u2014 dialogue apologies won't match.
_REFUSAL_PATTERNS = [
    # English
    "i cannot", "i'm unable", "i apologize", "i'm sorry", "sorry,",
    "content policy", "against our", "not able to", "can't write",
    "won't create", "cannot comply", "cannot fulfill",
    # Chinese
    "\u5bf9\u4e0d\u8d77", "\u62b1\u6b49", "\u6211\u65e0\u6cd5", "\u65e0\u6cd5\u751f\u6210", "\u4e0d\u80fd\u751f\u6210", "\u4e0d\u5141\u8bb8",
    "\u8fdd\u53cd", "\u5185\u5bb9\u653f\u7b56", "\u4e0d\u5b89\u5168", "\u4e0d\u7b26\u5408", "\u65e0\u6cd5\u6ee1\u8db3",
]

_REFUSAL_MIN_LENGTH = 500  # Responses shorter than this are suspect


def _detect_refusal(text: str) -> bool:
    """Check if the API response is a content-refusal message.

    Only scans the first 400 characters to avoid matching
    in-character dialogue where someone says "sorry" or "\u5bf9\u4e0d\u8d77".
    A second signal: real scene prose is virtually never under 500 chars.
    """
    head = text.strip()[:400].lower()
    hit_count = sum(1 for p in _REFUSAL_PATTERNS if p in head)
    is_short = len(text.strip()) < _REFUSAL_MIN_LENGTH
    return hit_count >= 2 or (hit_count >= 1 and is_short)


class SceneWriter:
    """Generates scene prose using LLM with automatic API\u2192local fallback."""

    def __init__(self, llm_interface, config, fallback_llm=None):
        self.llm = llm_interface
        self.fallback_llm = fallback_llm
        self.config = config

    def _call_llm(self, prompt: str, max_tokens: int, llm) -> str:
        """Call an LLM (primary or fallback) with the writer prompt."""
        from .prompts import SYSTEM_WRITER

        if getattr(llm, 'backend_type', None) == "anthropic":
            messages = [
                {"role": "system", "content": [
                    {"type": "text", "text": SYSTEM_WRITER,
                     "cache_control": {"type": "ephemeral"}}
                ]},
                {"role": "user", "content": prompt}
            ]
            return llm.chat(messages, max_tokens=max_tokens)
        else:
            return llm.generate(prompt, max_tokens=max_tokens)

    def write_scene(self, writer_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate scene prose, falling back to local model on API refusal."""
        max_tokens = self.config.get('llm.writer_max_tokens', 3000)
        prompt = self._format_writer_prompt(writer_context)
        prefer_local = self.config.get('generation.prefer_local_writer', False)
        fallback_enabled = self.config.get('generation.content_safety_fallback', True)

        # Choose starting model
        if prefer_local and self.fallback_llm:
            primary, fallback = self.fallback_llm, self.llm
            primary_label, fb_label = "local", "api"
        else:
            primary, fallback = self.llm, self.fallback_llm
            primary_label, fb_label = "api", "local"

        response = self._call_llm(prompt, max_tokens, primary)
        refused = _detect_refusal(response)

        if refused and fallback and fallback_enabled:
            logger.warning("API \u5185\u5bb9\u62d2\u6b62\u68c0\u6d4b\u89e6\u53d1\uff0c\u5207\u6362\u5230\u672c\u5730\u6a21\u578b\u91cd\u5199...")
            response = self._call_llm(prompt, max_tokens, fallback)
            refused = _detect_refusal(response)
            if refused:
                logger.warning("\u672c\u5730\u6a21\u578b\u4e5f\u8fd4\u56de\u53ef\u7591\u54cd\u5e94\uff0c\u7ee7\u7eed\u4f7f\u7528")

        result = self._parse_scene_response(response, writer_context)
        result["text"] = self._polish_scene_text(result["text"])
        text = result["text"]
        cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        result["word_count"] = cjk if cjk > len(text) * 0.3 else len(text.split())
        result["model_used"] = fb_label if refused else primary_label
        return result
    
    @staticmethod
    def _polish_scene_text(text: str) -> str:
        """Normalize paragraph spacing and flag content issues.

        - Single blank lines → 2 blank lines for readability.
        - Warns if the same sentence appears multiple times.
        """
        import re

        lines = text.split('\n')
        result_lines = []
        blank_count = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_count += 1
            else:
                if blank_count > 0:
                    result_lines.append('')
                    result_lines.append('')
                blank_count = 0
                result_lines.append(line)

        polished = '\n'.join(result_lines)

        # detect repeated sentences (>= 20 chars, appearing >= 3 times)
        sentences = re.findall(r'[^。！？\n]{20,}[。！？]', polished)
        if sentences:
            from collections import Counter
            counts = Counter(sentences)
            dupes = [s for s, c in counts.items() if c >= 3]
            if dupes:
                logger.warning("检测到重复句子 (%d处): %s...",
                               len(dupes), dupes[0][:60])

        return polished

    def _format_writer_prompt(self, context: Dict[str, Any]) -> str:
        """Format writer prompt with context.
        
        Args:
            context: Context dictionary
        
        Returns:
            Formatted prompt string
        """
        from .prompts import format_writer_prompt
        return format_writer_prompt(context)
    
    def _parse_scene_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response into scene data.
        
        Args:
            response: Raw LLM response
            context: Original context (for fallback title generation)
        
        Returns:
            Dictionary with text, word_count, and title
        """
        # Clean up response
        text = response.strip()
        
        # Strip obvious meta-reasoning header that some backends may emit
        # (e.g., lines about listing directories or inspecting project files
        #  before starting the actual scene prose). We only remove a leading
        #  block of such lines; once we see normal prose, we keep everything.
        from ..configs.constants import META_MARKERS

        lines = text.split('\n')
        cleaned_lines = []
        skipping_meta = True
        for line in lines:
            stripped = line.strip()
            if skipping_meta and stripped:
                if any(marker in stripped for marker in META_MARKERS):
                    # Skip this meta line and continue looking for real prose
                    continue
                else:
                    skipping_meta = False
            if not skipping_meta or not stripped:
                cleaned_lines.append(line)
        text = "\n".join(cleaned_lines).strip()
        
        # Extract title first (before stripping it from text)
        lines = text.split('\n')
        title = self._extract_title(lines, context)
        
        # Strip the LLM-generated title/header from the text to avoid duplication
        # The scene_committer will add its own standardized header
        text = self._strip_llm_header(text)
        
        # Count Chinese characters (spaces are rare in Chinese text)
        word_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        
        return {
            "text": text,
            "word_count": word_count,
            "title": title
        }
    
    def _extract_title(self, lines: List[str], context: Dict[str, Any]) -> str:
        """Extract or generate scene title.
        
        Args:
            lines: Lines of the scene text
            context: Original context
        
        Returns:
            Scene title
        """
        # Check if first line looks like a title
        # (short, no period at end, possibly markdown header)
        if lines:
            first_line = lines[0].strip()
            
            # Remove markdown header markers
            if first_line.startswith('#'):
                first_line = first_line.lstrip('#').strip()
            
            # If it's short and doesn't end with a period, use it as title
            if len(first_line) < 60 and not first_line.endswith('.'):
                return first_line
        
        # Generate from scene intention
        intention = context.get('scene_intention', '')
        if intention:
            # Use full intention if it's short enough, otherwise truncate smartly
            if len(intention) <= 60:
                title = intention
            else:
                # Truncate at word boundary near 60 chars
                words = intention.split()
                title = ''
                for word in words:
                    if len(title) + len(word) + 1 <= 60:
                        title += (' ' if title else '') + word
                    else:
                        break
            
            # Capitalize first letter and ensure no trailing punctuation
            if title:
                title = title.rstrip('.,;:!?')
                return title[0].upper() + title[1:]
        
        # Fallback to tick number
        tick = context.get('current_tick', 0)
        return f"Scene {tick}"
    
    def _strip_llm_header(self, text: str) -> str:
        """Strip LLM-generated markdown header and metadata from scene text.
        
        The LLM often generates a title like "# Title" followed by metadata
        like "*Scene ID: ...*" and "---". We strip this to avoid duplication
        since the scene_committer adds its own standardized header.
        
        Args:
            text: Raw scene text from LLM
        
        Returns:
            Text with header stripped
        """
        lines = text.split('\n')
        start_index = 0
        
        # Skip leading markdown title (# Title)
        if lines and lines[0].strip().startswith('#'):
            start_index = 1
        
        # Skip blank lines after title
        while start_index < len(lines) and not lines[start_index].strip():
            start_index += 1
        
        # Skip metadata lines (*Scene ID: ...*, *Tick: ...*)
        while start_index < len(lines):
            stripped = lines[start_index].strip()
            if stripped.startswith('*') and stripped.endswith('*'):
                start_index += 1
            else:
                break
        
        # Skip blank lines after metadata
        while start_index < len(lines) and not lines[start_index].strip():
            start_index += 1
        
        # Skip horizontal rule (---)
        if start_index < len(lines) and lines[start_index].strip().startswith('---'):
            start_index += 1
        
        # Skip blank lines after horizontal rule
        while start_index < len(lines) and not lines[start_index].strip():
            start_index += 1
        
        # Return remaining text
        return '\n'.join(lines[start_index:]).strip()
