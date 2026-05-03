---
name: watch
description: Watch a video (URL or local path). Downloads with yt-dlp, extracts auto-scaled frames with ffmpeg, pulls the transcript from captions (or Whisper API fallback), runs deep analytical synthesis on frames + transcript, and saves a structured Obsidian-ready markdown note to the vault with embedded notable frames.
argument-hint: "<video-url-or-path> [question] [--template <name>] [--no-save]"
allowed-tools: Bash, Read, Write, AskUserQuestion
homepage: https://github.com/bradautomates/claude-video
repository: https://github.com/bradautomates/claude-video
author: bradautomates
license: MIT
user-invocable: true
---

# /watch — Claude watches a video

You don't have a video input; this skill gives you one. A Python script downloads the video, extracts frames as JPEGs, gets a timestamped transcript (native captions first, then Whisper API as fallback), and prints frame paths + config. You then `Read` each frame path to see the images, identify notable frames, run a deep analysis using the template, save the structured note to the vault, copy notable frames to assets/, and give the user a concise answer with the report location.

## Step 0 — Setup preflight (runs every `/watch` invocation, silent on success)

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux. On **Windows**, substitute `python` — the `python3` command on Windows is the Microsoft Store stub and will not run the script.

**CLAUDE_SKILL_DIR on Windows:** `$CLAUDE_SKILL_DIR` is often unset on Windows. If the variable is empty, locate the scripts directory by running `Glob("**/claude-video/scripts/setup.py")` from the workspace root, or check `~/.claude/plugins/*/scripts/setup.py`. Use the resolved absolute path in all subsequent `python ...` commands.

Before every `/watch` run, verify that dependencies and an API key are in place:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --check
```

This is a <100ms lookup. On exit 0, the script emits **nothing** — proceed to Step 1 without comment. **Do NOT announce "setup is complete" to the user** — they don't need a status message on every turn. The only acceptable user-visible output from Step 0 is when remediation is required.

On non-zero exit, follow the table:

| Exit | Meaning | Action |
|------|---------|--------|
| `2` | Missing binaries (`ffmpeg` / `ffprobe` / `yt-dlp`) | Run installer |
| `3` | No Whisper API key | Run installer to scaffold `.env`, then ask user for a key |
| `4` | Both missing | Run installer, then ask for a key |

The installer is idempotent — safe to re-run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py"
```

On macOS with Homebrew, it auto-installs `ffmpeg` and `yt-dlp`. On Linux/Windows, it prints the exact install commands for the user to run. It scaffolds `~/.config/watch/.env` with commented placeholders at `0600` perms, and writes `SETUP_COMPLETE=true` once deps + a key are in place so the next session knows this user has already been through the wizard.

**If an API key is still missing after install:** use `AskUserQuestion` to ask the user whether they have a Groq API key (preferred — cheaper, faster) or an OpenAI key. Then write it into `~/.config/watch/.env` — set the matching `GROQ_API_KEY=...` or `OPENAI_API_KEY=...` line. If they don't want to set up Whisper, proceed with `--no-whisper` and tell them videos without native captions will come back frames-only.

**Structured mode (optional):** `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --json` emits `{status, first_run, missing_binaries, whisper_backend, has_api_key, config_file, platform, report_dir, default_template, save_transcript, save_notable_frames}`. Use this when you need to branch on specifics.

Within a single session, you can skip Step 0 on follow-up `/watch` calls — once `--check` returned 0, nothing about the environment changes between turns.

## When to use

- User pastes a video URL (YouTube, Vimeo, X, TikTok, Twitch clip, most yt-dlp-supported sites) and asks about it.
- User points at a local video file (`.mp4`, `.mov`, `.mkv`, `.webm`, etc.) and asks about it.
- User types `/watch <url-or-path> [question]`.

## Recommended limits

- **Best accuracy: videos under 10 minutes.** Frame coverage scales inversely with duration.
- **Hard caps: 100 frames total and 2 fps.** Token cost grows with frame count, so the script targets a frame budget by duration (and never exceeds 2 fps even when the budget would imply more):
  - ≤30s → ~1-2 fps (up to 30 frames)
  - 30s-1min → ~40 frames
  - 1-3min → ~60 frames
  - 3-10min → ~80 frames
  - \>10min → 100 frames, sparsely spaced (warning printed)
- If the user hands you a long video, consider asking whether they want a specific section before burning tokens on a sparse scan.

## How to invoke

### Step 1 — Parse user input

Separate the video source (URL or path) from any question the user asked. Also detect flags the user passed (`--template`, `--no-save`, `--report-dir`). Example: `/watch https://youtu.be/abc what is the core argument?` → source = `https://youtu.be/abc`, question = `what is the core argument?`.

### Step 2 — Read config and run the watch script

First, read the current config to get `report_dir` and `default_template`:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/config.py"
```

Then run the watch script, passing `--template` and `--report-dir` from config (override with user-supplied values if provided):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "<source>" --template "<template_name>" --report-dir "<report_dir>"
```

Append any user-supplied flags: `--start T`, `--end T`, `--max-frames N`, `--resolution W`, `--no-save`, `--no-whisper`, `--force-refresh`, etc.

**Cache:** Frames are cached at `~/.cache/watch/<url-hash>/` and reused across sessions automatically — the script skips download and extraction when cached frames exist. Pass `--force-refresh` to bypass the cache and re-download (useful after a video is updated or the cache is stale).

Optional flags reference:
- `--start T` / `--end T` — focus on a section. Accepts `SS`, `MM:SS`, or `HH:MM:SS`.
- `--max-frames N` — lower the cap for tighter token budget (e.g. `--max-frames 40`)
- `--resolution W` — change frame width in px (default 512; bump to 1024 only if the user needs to read on-screen text)
- `--fps F` — override auto-fps (clamped to 2 fps max)
- `--no-whisper` — disable the Whisper fallback entirely
- `--whisper groq|openai` — force a specific Whisper backend

### Step 3 — Parse config from script output

After the script prints its output, locate the `## Watch Config` block at the bottom. Extract:
- `report_dir` — absolute path where the report will be saved
- `template` — template name (e.g. `video-analysis`)
- `save_report` — `true` or `false`
- `save_transcript` — `true` or `false`
- `save_notable_frames` — `true` or `false`

Also derive the **report slug** from the video title: lowercase, hyphens for spaces, strip diacritics, max 60 chars, truncate at word boundary. Prefix with today's date: `YYYY-MM-DD-{slug}`.

Example: `"Andrej Karpathy: How LLMs Work"` → `2026-05-02-andrej-karpathy-how-llms-work`

This slug is used for: the report filename, the assets subdirectory, and transcript filename.

### Step 4 — Load the template

```
Read "${CLAUDE_SKILL_DIR}/templates/{template_name}.md"
```

The template defines every section and the frontmatter structure. Do NOT hardcode section names — derive them entirely from the template. Hold the full template in context for Step 7.

### Step 5 — Read all frames

**Read each frame path listed in the script output using the Read tool.** Read frames in batches of 20–25 per message (parallel tool calls per batch), then proceed to the next batch. This keeps individual messages manageable while still loading frames efficiently. Frames are in chronological order; `t=MM:SS` is the absolute timestamp in the source video.

During this step, begin mentally scoring each frame against the notable frame criteria (you finalize the selection in Step 6, but start scoring as you read).

### Step 6 — Identify notable frames

After reading all frames, select the subset to embed in the report. A frame is **notable** if it shows any of the following:

| Criterion | Signal |
|-----------|--------|
| Slide / presentation screen | New slide content is visible — title, bullet list, diagram on a slide |
| Data visualization | Chart, graph, table, heat map, benchmark comparison |
| Code or terminal | A code block, diff, terminal output, or CLI demo |
| UI / product demo | A product interface, walkthrough moment, or before/after comparison |
| Person introduction | Speaker name, title, or affiliation visible on screen |
| Significant scene change | First frame of a clearly new setting or segment |
| Bookends | First non-black/non-title frame and last meaningful frame |

**Cap:** Target 5–15 notable frames per video. If more qualify, prefer diversity across criteria and timestamps. If fewer than 5 qualify, include the top candidates even if marginal.

For each notable frame, record:
- Absolute path (from the frames list)
- Timestamp formatted as `MMSS` (e.g. `0214` for 02:14) — used in the asset filename
- Display timestamp `MM:SS` — used in the report section header
- One-line description of what's visible and why it matters

### Step 7 — Run analysis and fill the template

Using the template loaded in Step 4, fill every section. The template is the single source of truth for structure.

**Special instructions per section:**

**Visual Evidence:** Insert one subsection per notable frame. Write a one-sentence caption per frame. Check the `obsidian_wikilinks` value from the `## Watch Config` block (default: `true`):
- If `true`: embed as `![[assets/{slug}-frame-{MMSS}.jpg]]` (Obsidian wikilink)
- If `false`: embed as `![{caption}](assets/{slug}-frame-{MMSS}.jpg)` (standard markdown)

**Executive Synthesis (§1):** 4 bullets: core thesis, why it matters now, non-obvious insight, biggest transferable idea.

**Signal / Noise Audit (§2):** Be direct. If the video is primarily marketing, say so. List specific hype claims. The verdict must be one of: `Worth taking seriously` / `Read critically` / `Marketing content` / `Pure hype`.

**What's Actually Novel (§3):** Score honestly. Most content is reframed — credit genuine novelty when it exists. The table's `Novel?` column must use one of: `Genuinely new` / `Reframed` / `Recycled`.

**Limitations & Attack Surface (§6):** Do not soften. Enumerate unstated assumptions, failure cases, and what the author avoided. This section has the highest signal for critical thinkers.

**Competitive Intelligence (§7):** Flag even indirect signals — "we outperform GPT-4" is a positioning claim.

**Implementation Playbooks (§8):** Only generate if the video contains actionable methods. If purely opinion or interview, write `_No actionable methods identified — section skipped._`

**YAML frontmatter:** Populate all fields. `frames-captured` = total frames extracted (from the script output). `notable-frames` = count of selected notable frames.

**If the user asked a specific question:** Answer it directly within the relevant section(s) AND add this callout immediately after the Visual Evidence section:

```markdown
> [!question] User Question
> {{question}}
> **Answer:** {{direct answer with timestamp citations}}
```

### Step 8 — Write the report to the vault

If `save_report: true`:

1. Ensure `report_dir` exists. If not, create it:
   - Windows: `New-Item -ItemType Directory -Force -Path "{report_dir}"`
   - macOS/Linux: `mkdir -p "{report_dir}"`
2. Write the filled template using the `Write` tool to: `{report_dir}/{YYYY-MM-DD-slug}.md`

If `save_report: false` (user passed `--no-save`), display the report inline in chat only. Skip Steps 8, 9, 10.

### Step 9 — Copy notable frames to assets/

If `save_notable_frames: true` and notable frames were identified:

1. Ensure `{report_dir}/assets/` exists (create with mkdir).
2. For each notable frame, copy from the work dir to assets with the exact filename used in the report:

Windows (PowerShell):
```powershell
Copy-Item -Path "{frame_absolute_path}" -Destination "{report_dir}/assets/{slug}-frame-{MMSS}.jpg" -Force
```

macOS/Linux:
```bash
cp "{frame_absolute_path}" "{report_dir}/assets/{slug}-frame-{MMSS}.jpg"
```

The filenames **must match exactly** what was written in the Visual Evidence section of the report (`assets/{slug}-frame-{MMSS}.jpg`).

### Step 10 — Save transcript (optional)

If `save_transcript: true` and a transcript was obtained (not "none available"):

1. Ensure `{report_dir}/transcripts/` exists.
2. Write the raw transcript text to: `{report_dir}/transcripts/{YYYY-MM-DD-slug}-transcript.txt`

Use the `Write` tool with the transcript content from inside the ` ``` ` block under `## Transcript` in the script output — **not** the raw `.vtt` file. The script already strips VTT timing headers, deduplicates overlapping segments, and formats the text as plain timestamped lines.

### Step 11 — Answer the user

Deliver a concise reply:

1. **Direct answer** to their question if they asked one (2-3 sentences, timestamp-cited)
2. **3-sentence summary:** core thesis, most interesting insight, and your §2 verdict on signal/noise
3. **Report location:** `Saved to: {report_dir}/{filename}.md — {n} notable frames embedded`
4. **One-line hype verdict** from §2: e.g., `Signal/Noise: Mixed — 2 of 7 claims have supporting data.`

Do NOT reproduce the full report in chat — it is already saved. The user can open it in Obsidian.

### Step 12 — Clean up

If `save_notable_frames: true`: leave the work dir in place (frames were copied from it; follow-up questions may need re-reads).

If `save_notable_frames: false` and the user isn't going to ask follow-ups, delete the work dir:
- macOS/Linux: `rm -rf "{work_dir}"`
- Windows: `Remove-Item -Recurse -Force "{work_dir}"`

## Focusing on a section (higher frame rate)

When the user asks about a specific moment — "what happens at the 2 minute mark?", "zoom into 0:45 to 1:00", "the first 10 seconds" — pass `--start` and/or `--end`. The script switches to focused-mode budgets, which are denser than full-video budgets (still capped at 2 fps):

- ≤5s → 2 fps (up to 10 frames)
- 5-15s → 2 fps (up to 30 frames)
- 15-30s → ~2 fps (up to 60 frames)
- 30-60s → ~1.3 fps (up to 80 frames)
- 60-180s → ~0.6 fps (100 frames, capped)

Focused mode is the right call for:
- Any moment/range the user names explicitly ("around 2:30", "the intro", "the last 30 seconds").
- Any video longer than ~10 minutes where the user's question is about a specific part.
- Re-runs after a full scan didn't have enough detail in some region.

Transcript is auto-filtered to the same range. Frame timestamps are absolute (real video timeline, not offset-from-start).

If you already watched a video this session and the user asks a follow-up, do **not** re-run the script — you already have the frames and transcript in context. Just answer from what you have.

## Transcription

The script gets a timestamped transcript in one of two ways:

1. **Native captions (free, preferred).** yt-dlp pulls manual or auto-generated subtitles from the source platform if available.
2. **Whisper API fallback.** If no captions came back (or the source is a local file), the script extracts audio (`ffmpeg -vn -ac 1 -ar 16000 -b:a 64k`, ~0.5 MB/min) and uploads it to whichever Whisper API has a key configured:
   - **Groq** — `whisper-large-v3`. Preferred default: cheaper, faster. Get a key at console.groq.com/keys.
   - **OpenAI** — `whisper-1`. Fallback. Get a key at platform.openai.com/api-keys.

Both keys live in `~/.config/watch/.env`. The script prefers Groq when both are set; override with `--whisper openai` to force OpenAI. Use `--no-whisper` to skip the fallback entirely.

## Failure modes and handling

- **Setup preflight failed** → run `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py"` (auto-installs ffmpeg/yt-dlp via brew on macOS, scaffolds the `.env`). For API key, ask the user via `AskUserQuestion` and write it to `~/.config/watch/.env`.
- **No transcript available** → captions missing AND (no Whisper key OR Whisper API failed). Script prints a hint pointing to setup. Proceed frames-only and tell the user. §4.3 Detailed Breakdown will rely on visual evidence only.
- **Long video warning printed** → acknowledge it in your answer. Offer to re-run focused on a specific section via `--start`/`--end`.
- **Download fails** → yt-dlp's error goes to stderr. If it's a login-required or region-locked video, tell the user plainly; do not keep retrying.
- **Whisper request fails** → the error is printed to stderr. The report will say "none available" for transcript. You can retry with `--whisper openai` if Groq failed (or vice versa).
- **report_dir not writable** → inform the user and fall back to displaying the report in chat (equivalent to `--no-save`).
- **config.py missing** → watch.py will fail to import config. Run setup first, or check that `scripts/config.py` exists in the plugin directory.

## Token efficiency

This skill burns tokens primarily on frames. Order of magnitude:
- 80 frames at 512px wide is roughly 50-80k image tokens depending on aspect ratio.
- The transcript is cheap (a few thousand tokens at most for a 10-minute video).
- Bumping `--resolution` to 1024 roughly quadruples the image tokens per frame. Only do it when necessary (e.g., reading on-screen text).

## Security & Permissions

**What this skill does:**
- Runs `yt-dlp` locally to download the video and pull native captions when the source supports them (public data; the request goes directly to whatever host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract frames as JPEGs and, when Whisper is needed, a mono 16 kHz audio clip
- Sends the extracted audio clip to Groq's Whisper API (`api.groq.com/openai/v1/audio/transcriptions`) when `GROQ_API_KEY` is set
- Sends the extracted audio clip to OpenAI's audio transcription API (`api.openai.com/v1/audio/transcriptions`) when `OPENAI_API_KEY` is set and Groq is not, or when `--whisper openai` is forced
- Writes the downloaded video, frames, audio, and an intermediate transcript to a working directory under the system temp dir (or `--out-dir` if specified)
- Reads / creates `~/.config/watch/.env` (mode `0600`) to store the Whisper API key(s) and a `SETUP_COMPLETE` marker
- Reads `~/.config/watch/config.json` for report output settings (`report_dir`, `default_template`, etc.)
- Writes the final report `.md` and optional transcript `.txt` to `report_dir` in the user's vault
- Copies notable frames to `{report_dir}/assets/`

**What this skill does NOT do:**
- Does not upload the video itself to any API — only the extracted audio goes out, and only when native captions are missing AND Whisper is not disabled
- Does not access any platform account (no login, no session cookies, no posting)
- Does not share API keys between providers
- Does not log, cache, or write API keys to stdout, stderr, or output files

**Bundled scripts:** `scripts/watch.py` (entry point), `scripts/config.py` (config manager), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg frame extraction), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients), `scripts/setup.py` (preflight + installer)

Review scripts before first use to verify behavior.
