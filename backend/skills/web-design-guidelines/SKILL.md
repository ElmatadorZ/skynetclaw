---
name: web-design-guidelines
version: 1.0
role: web-design-guidelines
source: https://raw.githubusercontent.com/vercel-labs/agent-skills/main/skills/web-design-guidelines/SKILL.md
origin: imported (Agent Skill, Claude format)
description: |
  Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
capabilities:
  - design.review
  - quality.verification
triggers:
  - web design guidelines
  - review my ui
  - review ui
  - review ux
  - check accessibility
  - accessibility
  - a11y
  - audit design
  - ตรวจ ui
  - ตรวจหน้าเว็บ
  - ตรวจการเข้าถึง
---

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Fetch the latest guidelines from the source URL below
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Fetch fresh guidelines before each review:

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Use WebFetch to retrieve the latest rules. The fetched content contains all the rules and output format instructions.

## Usage

When a user provides a file or pattern argument:
1. Fetch guidelines from the source URL above
2. Read the specified files
3. Apply all rules from the fetched guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.
