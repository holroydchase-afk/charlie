#!/usr/bin/env bash
# PreToolUse hook on the Agent tool (from holroydchase-afk/studio-agents): appends "<UTC time> <agent>"
# to .claude/agent-runs/<branch>.log, so a PR's Agents: line can be checked against what really ran
# (scripts/check-agent-runs.sh). Logs the agent name only, never the prompt. Never blocks the call.
# Commit the log with the PR.
input=$(cat)
agent=$(printf '%s' "$input" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("tool_input") or {}).get("subagent_type") or "")' 2>/dev/null)
[[ "$agent" =~ ^[a-z0-9][a-z0-9-]{0,40}$ ]] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
branch=$(git symbolic-ref --short HEAD 2>/dev/null | tr '/' '-' | tr -cd 'A-Za-z0-9._-')
mkdir -p .claude/agent-runs 2>/dev/null && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $agent" >> ".claude/agent-runs/${branch:-detached}.log"
exit 0
