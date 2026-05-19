Extract structured updates from this scene.

Scene: {scene_text}

POV: {pov_character_id} | Location: {location_id}

Open Loops: {existing_open_loops}

Return ONLY JSON with these updates:

```json
{{
  "character_updates": [
    {{
      "id": "C000",
      "changes": {{
        "emotional_state": "string or null",
        "physical_state": "string or null",
        "inventory": ["item1", "item2"] or null,
        "goals": ["goal1", "goal2"] or null,
        "beliefs": ["belief1", "belief2"] or null
      }}
    }}
  ],
  "location_updates": [
    {{
      "id": "L000",
      "changes": {{
        "description": "string or null",
        "atmosphere": "string or null",
        "features": ["feature1", "feature2"] or null
      }}
    }}
  ],
  "open_loops_created": [
    {{
      "description": "string",
      "importance": "low|medium|high|critical",
      "category": "mystery|relationship|goal|threat|etc",
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
        "status": "string or null",
        "perspective_a": "string or null",
        "perspective_b": "string or null",
        "intensity": 0-10 or null
      }}
    }}
  ]
}}
```

Rules: Use null for no change. Only extract what's clearly shown. For lists, only include NEW items.
