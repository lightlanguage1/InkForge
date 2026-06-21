import urllib.request, json, sys

# Test the timeline endpoint via localhost:9000 inside container
try:
    req = urllib.request.Request("http://127.0.0.1:9000/api/v1/project/test123/timeline")
    resp = urllib.request.urlopen(req)
    print("Timeline OK:", resp.status)
except urllib.error.HTTPError as e:
    print(f"Timeline: HTTP {e.code} (expected - project doesn't exist)")
except Exception as e:
    print(f"Timeline ERROR: {e}")

# Also check openapi.json for the endpoint
try:
    req = urllib.request.Request("http://127.0.0.1:9000/openapi.json")
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    paths = list(data.get("paths", {}).keys())
    timeline_paths = [p for p in paths if "timeline" in p or "switch-branch" in p]
    print("Registered paths:", timeline_paths)
except Exception as e:
    print(f"OpenAPI ERROR: {e}")
