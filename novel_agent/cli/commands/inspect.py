"""Inspect command - detailed entity inspection."""
import json
from pathlib import Path
from typing import Optional, Dict, Any


def find_entity_file(project_dir: Path, entity_id: str) -> Optional[Path]:
    """Find entity file by ID.
    
    Args:
        project_dir: Path to project directory
        entity_id: Entity ID (C0, L0, S001, etc.)
        
    Returns:
        Path to entity file or None if not found
    """
    memory_dir = project_dir / "memory"
    
    if entity_id.startswith("C"):
        # Character
        char_file = memory_dir / "characters" / f"{entity_id}.json"
        if char_file.exists():
            return char_file
    elif entity_id.startswith("L"):
        # Location
        loc_file = memory_dir / "locations" / f"{entity_id}.json"
        if loc_file.exists():
            return loc_file
    elif entity_id.startswith("S"):
        # Scene
        scene_file = memory_dir / "scenes" / f"{entity_id}.json"
        if scene_file.exists():
            return scene_file
    elif entity_id.startswith("F"):
        # Faction
        fac_file = memory_dir / "factions" / f"{entity_id}.json"
        if fac_file.exists():
            return fac_file
    
    return None


def load_entity(filepath: Path) -> Optional[Dict[str, Any]]:
    """Load entity from file.
    
    Args:
        filepath: Path to entity file
        
    Returns:
        Entity data dictionary or None
    """
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载实体失败：{e}")
        return None


def display_character(data: Dict[str, Any], filepath: Path, history_limit: int = 5):
    """Display character information.
    
    Args:
        data: Character data dictionary
        filepath: Path to character file
        history_limit: Number of history entries to show
    """
    print(f"\n Inspecting Character: {data.get('id', 'Unknown')}\n")
    
    # Build full name from components (backward compatible)
    if 'first_name' in data or 'family_name' in data:
        name_parts = []
        if data.get('title'):
            name_parts.append(data['title'])
        if data.get('first_name'):
            name_parts.append(data['first_name'])
        if data.get('family_name'):
            name_parts.append(data['family_name'])
        name = ' '.join(name_parts) if name_parts else 'Unknown'
    else:
        name = data.get('name', 'Unknown')
    
    print(f"姓名：{name}")
    print(f"类型：{data.get('type', 'Unknown')}")
    print(f"职能：{data.get('role', 'Unknown')}")
    
    # Current state
    current_state = data.get('current_state', {})
    if current_state:
        print(f"\nCurrent State:")
        if current_state.get('emotional_state'):
            print(f"  情绪：{current_state['emotional_state']}")
        if current_state.get('physical_state'):
            print(f"  体态：{current_state['physical_state']}")
        if current_state.get('location_id'):
            print(f"  位置：{current_state['location_id']}")
        if current_state.get('inventory'):
            print(f"  物品：{', '.join(current_state['inventory'])}")
        if current_state.get('goals'):
            print(f"  目标：{', '.join(current_state['goals'])}")
    
    # Physical traits
    physical = data.get('physical_traits', {})
    if physical:
        print(f"\nPhysical Traits:")
        if physical.get('age'):
            print(f"  年龄：{physical['age']}")
        if physical.get('appearance'):
            print(f"  外貌：{physical['appearance']}")
        if physical.get('distinctive_features'):
            print(f"  特征：{', '.join(physical['distinctive_features'])}")
    
    # Personality
    personality = data.get('personality', {})
    if personality:
        print(f"\nPersonality:")
        if personality.get('core_traits'):
            print(f"  性格特征：{', '.join(personality['core_traits'])}")
        if personality.get('desires'):
            print(f"  欲望：{', '.join(personality['desires'])}")
        if personality.get('fears'):
            print(f"  恐惧：{', '.join(personality['fears'])}")
    
    # Relationships
    relationships = data.get('relationships', [])
    if relationships:
        print(f"\nRelationships:")
        for rel in relationships:
            print(f"  - {rel.get('character_id', 'Unknown')}: {rel.get('relationship_type', '')} ({rel.get('status', '')})")
    
    # History
    history = data.get('history', [])
    if history:
        print(f"\nHistory (last {history_limit} updates):")
        for entry in history[-history_limit:]:
            tick = entry.get('tick', '?')
            scene = entry.get('scene_id', '?')
            summary = entry.get('summary', 'No summary')
            print(f"  [第{tick}幕] {summary}")
    
    print(f"\nFull JSON: {filepath}")
    print()


def display_location(data: Dict[str, Any], filepath: Path, history_limit: int = 5):
    """Display location information.
    
    Args:
        data: Location data dictionary
        filepath: Path to location file
        history_limit: Number of history entries to show
    """
    print(f"\n Inspecting Location: {data.get('id', 'Unknown')}\n")
    
    print(f"名称：{data.get('name', 'Unknown')}")
    print(f"类型：{data.get('type', 'Unknown')}")
    print(f"氛围：{data.get('atmosphere', 'Unknown')}")
    
    # Description
    if data.get('description'):
        print(f"\nDescription:")
        print(f"  {data['description']}")
    
    # Sensory details
    sensory = data.get('sensory_details', {})
    if sensory:
        print(f"\nSensory Details:")
        if sensory.get('visual'):
            print(f"  视觉：{sensory['visual']}")
        if sensory.get('auditory'):
            print(f"  听觉：{sensory['auditory']}")
        if sensory.get('olfactory'):
            print(f"  嗅觉：{sensory['olfactory']}")
    
    # Significance
    if data.get('significance'):
        print(f"\nSignificance:")
        print(f"  {data['significance']}")
    
    # Current occupants
    occupants = data.get('current_occupants', [])
    if occupants:
        print(f"\nCurrent Occupants:")
        for occ in occupants:
            print(f"  - {occ}")
    
    # History
    history = data.get('history', [])
    if history:
        print(f"\nHistory (last {history_limit} updates):")
        for entry in history[-history_limit:]:
            tick = entry.get('tick', '?')
            scene = entry.get('scene_id', '?')
            summary = entry.get('summary', 'No summary')
            print(f"  [第{tick}幕] {summary}")
    
    print(f"\nFull JSON: {filepath}")
    print()


def display_scene(data: Dict[str, Any], filepath: Path):
    """Display scene information.
    
    Args:
        data: Scene data dictionary
        filepath: Path to scene file
    """
    print(f"\n Inspecting Scene: {data.get('id', 'Unknown')}\n")
    
    print(f"幕数：{data.get('tick', 'Unknown')}")
    print(f"视角角色：{data.get('pov_character', 'Unknown')}")
    
    if data.get('location'):
        print(f"地点：{data['location']}")
    
    # Summary
    if data.get('summary'):
        print(f"\nSummary:")
        if isinstance(data['summary'], list):
            for point in data['summary']:
                print(f"  - {point}")
        else:
            print(f"  {data['summary']}")
    
    # Characters present
    characters = data.get('characters_present', [])
    if characters:
        print(f"\nCharacters Present:")
        for char in characters:
            print(f"  - {char}")
    
    # Key events
    events = data.get('key_events', [])
    if events:
        print(f"\nKey Events:")
        for event in events:
            print(f"  - {event}")
    
    print(f"\nFull JSON: {filepath}")
    print()


def display_raw_json(data: Dict[str, Any]):
    """Display raw JSON data.
    
    Args:
        data: Data dictionary to display
    """
    print(json.dumps(data, indent=2))


def inspect_entity(project_dir: Path, entity_id: Optional[str] = None, 
                  file: Optional[Path] = None, raw: bool = False,
                  history_limit: int = 5) -> bool:
    """Inspect an entity by ID or file path.
    
    Args:
        project_dir: Path to project directory
        entity_id: Entity ID (C0, L0, etc.)
        file: Direct file path
        raw: Output raw JSON
        history_limit: Number of history entries to show
        
    Returns:
        True if successful, False otherwise
    """
    # Determine file path
    if file:
        filepath = Path(file)
        if not filepath.is_absolute():
            filepath = project_dir / filepath
    elif entity_id:
        filepath = find_entity_file(project_dir, entity_id)
        if not filepath:
            print(f"[ERR] 未找到实体：{entity_id}")
            return False
    else:
        print("[ERR] 需要指定 --id 或 --file")
        return False
    
    # Load entity
    data = load_entity(filepath)
    if not data:
        print(f"[ERR] 无法从以下路径加载实体：{filepath}")
        return False
    
    # Display
    if raw:
        display_raw_json(data)
    else:
        entity_type = data.get('id', '')
        if entity_type.startswith('C'):
            display_character(data, filepath, history_limit)
        elif entity_type.startswith('L'):
            display_location(data, filepath, history_limit)
        elif entity_type.startswith('S'):
            display_scene(data, filepath)
        elif entity_type.startswith('F'):
            print(f"\n Inspecting Faction: {data.get('id','Unknown')}\n")
            print(f"名称：{data.get('name','Unknown')}")
            print(f"Type: {data.get('org_type','Unknown')}")
            print(f"重要性：{data.get('importance','medium')}")
            if data.get('summary'):
                print(f"\nSummary:\n  {data['summary']}")
            if data.get('mandate_objectives'):
                print(f"\nMandate/Objectives:\n  - " + "\n  - ".join(data['mandate_objectives']))
            if data.get('influence_domains'):
                print(f"\nInfluence Domains:\n  - " + "\n  - ".join(data['influence_domains']))
            if data.get('assets_resources'):
                print(f"\nAssets/Resources:\n  - " + "\n  - ".join(data['assets_resources']))
            if data.get('methods_tactics'):
                print(f"\nMethods/Tactics:\n  - " + "\n  - ".join(data['methods_tactics']))
            if data.get('tags'):
                print(f"\nTags: {', '.join(data['tags'])}")
            print(f"\nFull JSON: {filepath}")
            print()
        else:
            # Unknown type, show raw
            display_raw_json(data)
    
    return True
