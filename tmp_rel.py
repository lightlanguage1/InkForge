import json, os, sys

proj = sys.argv[1] if len(sys.argv) > 1 else '/app/work/users/10558c033ddd/novels/回到过去成为女捕头_41a624f3'

# Check relationships
rel_path = os.path.join(proj, 'memory', 'relationships.json')
if os.path.exists(rel_path):
    rel = json.load(open(rel_path))
    rels = rel.get('relationships', [])
    print(f'Relationships: {len(rels)}')
    for r in rels:
        a = r.get('character_a', '?')
        b = r.get('character_b', '?')
        t = r.get('relationship_type', '?')
        s = r.get('status', {})
        print(f'  {a} <-> {b}: {t} status={s}')

# Check characters
chars_dir = os.path.join(proj, 'memory', 'characters')
if os.path.exists(chars_dir):
    print(f'\nCharacters:')
    for f in sorted(os.listdir(chars_dir)):
        c = json.load(open(os.path.join(chars_dir, f)))
        name = (c.get('family_name', '') or '') + (c.get('first_name', '') or '')
        role = c.get('role', '?')
        rels_in = len(c.get('relationships', []))
        status = c.get('status', '?')
        print(f'  {c["id"]}: {name} role={role} status={status} rels={rels_in}')
