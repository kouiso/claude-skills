# claude-skills

claude.ai Skills sync repo. Skills are encrypted with git-crypt.

## Setup

```bash
git-crypt unlock /path/to/git-crypt-key
```

## Add a skill

```bash
mkdir -p skills/my-skill
cat > skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: What this skill does
---

# Skill instructions here
EOF
git add skills/my-skill/SKILL.md
git commit -m "add my-skill"
git push
```

Pushing to `main` with changes under `skills/` triggers auto-sync to claude.ai.

## Manual sync

```bash
export CLAUDE_SESSION_KEY_PERSONAL="sk-ant-sid02-..."
export CLAUDE_ORG_PERSONAL="..."
python scripts/sync.py --org personal
python scripts/sync.py --org personal --dry-run  # preview
```

## GitHub Secrets required

| Secret | Description |
|--------|-------------|
| `GIT_CRYPT_KEY` | base64-encoded git-crypt key |
| `CLAUDE_SESSION_KEY_PERSONAL` | claude.ai personal session cookie |
| `CLAUDE_SESSION_KEY_TEAM` | claude.ai team session cookie (optional) |

## GitHub Variables required

| Variable | Description |
|----------|-------------|
| `CLAUDE_ORG_PERSONAL` | Personal org UUID |
| `CLAUDE_ORG_TEAM` | Team org UUID (optional) |
