#!/usr/bin/env python3
"""
Sync skills/ directory to claude.ai Skills API.

Usage:
  python scripts/sync.py [--org personal|team] [--dry-run] [skill_name ...]

Env vars (required):
  CLAUDE_SESSION_KEY_PERSONAL   - session key for personal account
  CLAUDE_SESSION_KEY_TEAM       - session key for team account (optional)
  CLAUDE_ORG_PERSONAL           - org UUID for personal account
  CLAUDE_ORG_TEAM               - org UUID for team account (optional)
"""

import sys
import json
import os
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

CLAUDE_AI_BASE = "https://claude.ai"
SKILLS_DIR = Path(__file__).parent.parent / "skills"
REQUEST_DELAY = 1.2
MAX_RETRIES = 3
REQUEST_TIMEOUT = 60


def make_request(method, url, session_key, body=None, attempt=0):
    headers = {
        "Cookie": f"sessionKey={session_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://claude.ai/",
        "Origin": "https://claude.ai",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:200]
        if e.code in (500, 502, 503) and attempt < MAX_RETRIES:
            time.sleep(REQUEST_DELAY * 2)
            return make_request(method, url, session_key, body, attempt + 1)
        return e.code, {"error": body_text}
    except Exception as e:
        return 0, {"error": str(e)}


def list_remote_skills(org_uuid, session_key):
    url = f"{CLAUDE_AI_BASE}/api/organizations/{org_uuid}/skills/list-skills"
    status, data = make_request("GET", url, session_key)
    if status != 200:
        print(f"  ERROR listing skills: {status} {data}")
        return {}
    skills = data if isinstance(data, list) else data.get("skills", [])
    return {s["name"]: s for s in skills}


def create_skill(org_uuid, session_key, name, description, instructions):
    url = f"{CLAUDE_AI_BASE}/api/organizations/{org_uuid}/skills/create-simple-skill"
    status, data = make_request("POST", url, session_key, {
        "name": name,
        "description": description,
        "instructions": instructions,
    })
    time.sleep(REQUEST_DELAY)
    return status, data


def update_skill(org_uuid, session_key, skill_id, description, instructions):
    url = f"{CLAUDE_AI_BASE}/api/organizations/{org_uuid}/skills/edit-simple-skill"
    status, data = make_request("POST", url, session_key, {
        "skill_id": skill_id,
        "description": description,
        "instructions": instructions,
    })
    time.sleep(REQUEST_DELAY)
    return status, data


def parse_skill_md(path: Path):
    """Parse SKILL.md frontmatter (name, description) and body (instructions)."""
    text = path.read_text(encoding="utf-8")
    name = path.parent.name  # directory name as fallback
    description = ""
    instructions = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            instructions = parts[2].strip()
            for line in frontmatter.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')

    # claude.ai rejects names containing "claude"
    if "claude" in name.lower():
        name = name.lower().replace("claude", "ai")

    return name, description, instructions


def sync_skills(org_uuid, session_key, target_skills=None, dry_run=False):
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Syncing to org: {org_uuid}")

    remote = list_remote_skills(org_uuid, session_key)
    print(f"  Remote: {len(remote)} skills")

    skill_dirs = sorted(SKILLS_DIR.iterdir()) if SKILLS_DIR.exists() else []
    if target_skills:
        skill_dirs = [d for d in skill_dirs if d.name in target_skills]

    results = {"created": [], "updated": [], "skipped": [], "errors": []}

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name, description, instructions = parse_skill_md(skill_md)

        if name in remote:
            existing = remote[name]
            if existing.get("instructions", "") == instructions:
                print(f"  SKIP (unchanged): {name}")
                results["skipped"].append(name)
                continue
            print(f"  UPDATE: {name}")
            if not dry_run:
                status, data = update_skill(org_uuid, session_key, existing["id"], description, instructions)
                if status == 200:
                    results["updated"].append(name)
                else:
                    print(f"    ERROR {status}: {data}")
                    results["errors"].append(name)
            else:
                results["updated"].append(name)
        else:
            print(f"  CREATE: {name}")
            if not dry_run:
                status, data = create_skill(org_uuid, session_key, name, description, instructions)
                if status == 200:
                    results["created"].append(name)
                else:
                    print(f"    ERROR {status}: {data}")
                    results["errors"].append(name)
            else:
                results["created"].append(name)

    print(f"\n  Created: {len(results['created'])} | Updated: {len(results['updated'])} | Skipped: {len(results['skipped'])} | Errors: {len(results['errors'])}")
    if results["errors"]:
        print(f"  Failed: {results['errors']}")
    return len(results["errors"]) == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("skills", nargs="*", help="specific skill dirs to sync (default: all)")
    parser.add_argument("--org", choices=["personal", "team"], default="personal")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.org == "personal":
        session_key = os.environ.get("CLAUDE_SESSION_KEY_PERSONAL")
        org_uuid = os.environ.get("CLAUDE_ORG_PERSONAL")
    else:
        session_key = os.environ.get("CLAUDE_SESSION_KEY_TEAM")
        org_uuid = os.environ.get("CLAUDE_ORG_TEAM")

    if not session_key:
        print(f"ERROR: CLAUDE_SESSION_KEY_{args.org.upper()} not set")
        sys.exit(1)
    if not org_uuid:
        print(f"ERROR: CLAUDE_ORG_{args.org.upper()} not set")
        sys.exit(1)

    ok = sync_skills(org_uuid, session_key, args.skills or None, args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
