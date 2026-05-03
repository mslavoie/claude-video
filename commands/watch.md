---
description: Watch a video (URL or local path). Downloads with yt-dlp, extracts frames with ffmpeg, transcribes from captions or Whisper, runs deep analytical synthesis (hype detection, novelty scoring, competitive intelligence), and saves a structured Obsidian-ready note to your vault with embedded notable frames.
argument-hint: <video-url-or-path> [question] [--template video-analysis] [--no-save] [--report-dir <path>]
allowed-tools: [Bash, Read, Write, AskUserQuestion]
---

Invoke the `watch` skill (defined in SKILL.md) with the user's arguments: $ARGUMENTS

Follow the skill's full pipeline: preflight → download → extract frames → transcript → load config → load template → read all frames → identify notable frames → run deep analysis → fill template → save structured report to vault → copy notable frames to assets/ → answer user with summary + report path.

If the user provided no arguments, ask them for a video URL or local path before proceeding.

Key flags:
- `--template <name>` — which template to use (default: from `~/.config/watch/config.json`, usually `video-analysis`)
- `--no-save` — skip writing to vault, display report in chat only
- `--report-dir <path>` — override the save location for this run only
