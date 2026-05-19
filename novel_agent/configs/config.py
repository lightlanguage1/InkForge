"""Configuration management for StoryDaemon."""
import os
import warnings
import yaml
from typing import Dict, Any, Optional


# Default configuration
DEFAULT_CONFIG = {
    'llm': {
        'backend': 'api',
        'codex_bin_path': 'codex',
        'default_max_tokens': 2000,
        'planner_max_tokens': 4000,
        'writer_max_tokens': 8192,
        'extractor_max_tokens': 2000,
        'lore_extractor_max_tokens': 1500,
        'timeout': 120,
        'model': 'deepseek-chat',
        'openai_model': 'deepseek-chat',
        # Sampling parameters (Ollama + API backends)
        'temperature': 0.7,
        'top_p': 0.8,
        'top_k': 20,
        'min_p': 0.0,
        'repeat_penalty': 1.0,
        'enable_thinking': False,
    },
    'paths': {
        'novels_dir': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'work', 'novels'),
    },
    'generation': {
        'max_tools_per_tick': 3,
        'recent_scenes_count': 3,
        'summary_scenes_count': 5,    # Number of older scenes to include as summaries in writer context
        'include_overall_summary': True,
        'enable_fact_extraction': True,
        'enable_entity_updates': True,
        'enable_tension_tracking': True,  # Phase 7A.3: Track scene tension levels
        'enable_lore_tracking': True,  # Phase 7A.4: Track world rules and lore
        'beat_verification_threshold': 0.5,  # Semantic similarity threshold for beat verification

        # Word count targets: null = no limit (project config.yaml can override)
        'target_word_count_min': None,
        'target_word_count_max': None,

        # Character detection (Phase 6)
        'auto_detect_characters': True,  # Detect new character names in scenes
        'auto_create_minor_characters': False,  # Auto-create stubs for detected characters
        'prompt_for_character_creation': True,  # Show tips about detected characters

        # Plot-first mode configuration
        'use_plot_first': False,  # Enable emergent plot-first architecture
        'plot_first_start_tick': 2,  # Start plot-first mode from this tick (allows character setup)
        'plot_beats_ahead': 5,  # Generate this many beats at a time
        'plot_regeneration_threshold': 2,  # Regenerate when pending beats < this
        'verify_beat_execution': True,  # Verify beat was accomplished via LLM
        'allow_beat_skip': False,  # Allow skipping beats that aren't accomplished
        'fallback_to_reactive': True,  # Fall back to reactive mode if beat generation fails

        # API content safety fallback: auto-switch to local model on refusal
        'content_safety_fallback': True,
        'prefer_local_writer': False,  # Always use local model for writing when True
    },
    'lore': {
        'contradiction_threshold': 0.5,  # Similarity threshold for flagging contradictions (0.0-2.0)
    },
    'plot': {
        # Beat integration mode: controls how strongly the agent treats plot beats.
        #
        #   off       - no beat hints or QA integration
        #   soft_hint - expose next_plot_beat and compute beat_hint_alignment (default)
        #   guided    - planner expected to fill beat_target and beats may be updated
        #   strict    - future: hard validation around beat usage
        'beat_mode': 'soft_hint',
    },
    'daemon': {
        'health_check_interval': 60,
        'max_error_count': 3,
        'max_concurrent_projects': 10,
    },
    'skill': {
        'store_path': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'skills'),
        'max_reference_count': 3,
    },
    'reference': {
        'store_path': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'references'),
        'max_results': 3,
    },
    'router': {
        'enabled': True,
        # Writer: API (DeepSeek) — creative quality matters
        'writer_model': 'deepseek-chat',
        'writer_backend': 'api',
        'fallback_writer': 'deepseek-chat',
        # Planner: API (DeepSeek) — structural quality matters
        'planner_model': 'deepseek-chat',
        'planner_backend': 'api',
        'fallback_planner': 'deepseek-chat',
        # Extractor / Evaluator / Agent tools: local llama-server — cost efficiency
        'extractor_model': 'local-llama',
        'extractor_backend': 'api',
        'fallback_extractor': 'deepseek-chat',
    },
}


class Config:
    """Configuration manager for StoryDaemon."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to YAML config file (optional)
        """
        self.config = self._deep_copy(DEFAULT_CONFIG)
        
        if config_path and os.path.exists(config_path):
            self.load(config_path)
    
    def load(self, config_path: str):
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML config file
            
        Raises:
            IOError: If file cannot be read
            ValueError: If YAML is invalid
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self._merge_config(user_config)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}")
        except Exception as e:
            raise IOError(f"Error reading config from {config_path}: {e}")
    
    def _merge_config(self, user_config: Dict[str, Any]):
        """Merge user config with defaults (deep merge).
        
        Args:
            user_config: User configuration dictionary
        """
        self._deep_merge(self.config, user_config)
    
    def _deep_merge(self, base: Dict, update: Dict):
        """Recursively merge update dict into base dict.
        
        Args:
            base: Base dictionary to merge into
            update: Dictionary with updates
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _deep_copy(self, d: Dict) -> Dict:
        """Create a deep copy of a dictionary.
        
        Args:
            d: Dictionary to copy
            
        Returns:
            Deep copy of dictionary
        """
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._deep_copy(value)
            else:
                result[key] = value
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., 'llm.codex_bin_path')
            default: Default value if key not found
            
        Returns:
            Config value or default
            
        Examples:
            >>> config.get('llm.codex_bin_path')
            'codex'
            >>> config.get('llm.planner_max_tokens')
            1000
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set config value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., 'llm.codex_bin_path')
            value: Value to set
            
        Examples:
            >>> config.set('llm.codex_bin_path', '/usr/local/bin/codex')
        """
        keys = key.split('.')
        target = self.config
        
        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        # Set the value
        target[keys[-1]] = value
    
    def save(self, config_path: str):
        """Save current configuration to YAML file.
        
        Args:
            config_path: Path to save config file
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            dir_name = os.path.dirname(config_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise IOError(f"Error saving config to {config_path}: {e}")
    
    def __getitem__(self, key: str) -> Any:
        """Direct dict access (deprecated).

        Warns and delegates to ``get()``.
        """
        warnings.warn(
            "Direct dict access is deprecated. Use config.get('...') instead.",
            DeprecationWarning, stacklevel=2,
        )
        return self.config[key]

    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self._deep_copy(self.config)
