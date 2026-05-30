"""Quick test: generate 3 chapters via SSE stream to verify agent pipeline."""
import sys
import json
import urllib.request
import ssl

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiAiMWU3NTllNDExOTFjIiwgImlhdCI6IDE3ODAxNDIxODEsICJleHAiOiAxNzgyNzM0MTgxfQ.hm4BpY-UG9RjDlg0u1Gi3h7KMZ-O9w4SyKKGsENFGPE"
PROJECT_ID = "a07d5f92"
BASE = "http://localhost:8000/api/v1"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def stream_tick(notes: str = "", finale: bool = False):
    url = f"{BASE}/project/{PROJECT_ID}/tick/stream?token={TOKEN}"
    if notes:
        url += f"&notes={urllib.request.quote(notes)}"
    if finale:
        url += "&finale=true"

    print(f"\n{'='*60}")
    print(f"Generating tick... URL: {url}")
    print(f"{'='*60}")

    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=600) as resp:
            buffer = ""
            for line in resp:
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                if text.startswith("data: "):
                    text = text[6:]
                if text == "[DONE]":
                    break
                try:
                    event = json.loads(text)
                    event_type = event.get("type", "?")
                    msg = event.get("message", "")
                    # Truncate long messages
                    if len(msg) > 200:
                        msg = msg[:200] + "..."
                    print(f"  [{event_type}] {msg}")

                    if event_type == "error":
                        print(f"  !!! ERROR: {event}")
                        return False
                    if event_type == "done":
                        # Check evaluation
                        ev = event.get("evaluation", {})
                        if ev:
                            passed = ev.get("passed", "?")
                            issues = ev.get("issues", [])
                            checks = ev.get("checks", {})
                            print(f"  === Scene Eval: passed={passed}, checks={checks}")
                            if issues:
                                for i in issues:
                                    print(f"  ISSUE: {i}")
                        return True
                except json.JSONDecodeError:
                    if text:
                        print(f"  [raw] {text[:100]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False
    return True


if __name__ == "__main__":
    chapters = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    success = 0
    for i in range(chapters):
        print(f"\n>>> Chapter {i+1}/{chapters}")
        if stream_tick():
            success += 1
        else:
            print(f"  Chapter {i+1} FAILED, stopping.")
            break

    print(f"\n{'='*60}")
    print(f"Completed: {success}/{chapters} chapters generated successfully")
