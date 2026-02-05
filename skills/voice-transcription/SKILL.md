---
name: voice-transcription
description: Transcribe audio files (voice memos, recordings) to text using OpenAI Whisper API or local transcription
triggers:
  - voice
  - audio
  - transcribe
  - recording
  - memo
  - speech
  - voice memo
  - audio file
requires:
  bins:
    - ffmpeg                    # Required for audio conversion
  env:
    - OPENAI_API_KEY            # Required for Whisper API
  scripts:
    - transcribe.py             # Helper script in this directory
os:
  - linux
  - darwin
---

# Voice Transcription Skill

Transcribe audio files (voice memos, recordings, podcasts) to text using OpenAI's Whisper API or local transcription tools.

## Purpose

This skill enables PCP to:
- Transcribe voice memos sent via Discord
- Convert audio recordings to searchable text
- Process podcast clips or meeting recordings
- Handle any audio-to-text conversion

## When to Use

- User sends a voice memo or audio file
- User asks to "transcribe this"
- Any audio file needs to be converted to text
- Voice notes need to be captured in the vault

## Supported Formats

OpenAI Whisper supports: `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav`, `webm`, `ogg`, `flac`

For other formats (like `opus`), ffmpeg will convert automatically.

## How to Execute

### Step 1: Identify the Audio File

Check if the file exists and identify its format:
```bash
file /path/to/audio.file
```

### Step 2: Convert if Necessary

If the format isn't directly supported, convert with ffmpeg:
```bash
# Convert to WAV (most compatible)
ffmpeg -i input.opus -ar 16000 -ac 1 -y output.wav

# Common conversions:
ffmpeg -i input.ogg -y output.mp3
ffmpeg -i input.webm -y output.mp3
```

### Step 3: Transcribe Using Helper Script

Use the bundled transcribe.py script:
```bash
python /workspace/skills/voice-transcription/transcribe.py /path/to/audio.wav
```

Or in Python:
```python
from pathlib import Path
import sys
sys.path.insert(0, "/workspace/skills/voice-transcription")
from transcribe import transcribe_audio

result = transcribe_audio("/path/to/audio.wav")
if result["success"]:
    print(result["text"])
else:
    print(f"Error: {result['error']}")
```

### Step 4: Return Results

Present the transcription to the user in a readable format.
Optionally capture it to the vault:

```python
from vault_v2 import smart_capture

# Capture the transcription
result = smart_capture(
    f"Voice memo transcription: {transcription_text}",
    capture_type="note"
)
```

## Fallback: Local Transcription

If OPENAI_API_KEY is not available but local `whisper` CLI is installed:

```bash
# Check if whisper is installed
which whisper

# Use local whisper
whisper /path/to/audio.wav --model base --output_format txt
```

## Configuration

Configure in `/workspace/config/pcp.yaml`:

```yaml
skills:
  entries:
    voice-transcription:
      enabled: true
      model: whisper-1           # OpenAI model
      language: en               # Default language (optional, auto-detect if not set)
      fallback_to_local: true    # Use local whisper if API fails
      max_file_size_mb: 25       # Maximum file size to process
```

## Error Handling

| Error | Solution |
|-------|----------|
| "File too large" | Split audio into smaller chunks |
| "Unsupported format" | Convert with ffmpeg first |
| "API rate limit" | Wait and retry, or use local fallback |
| "No API key" | Set OPENAI_API_KEY or use local whisper |

## Example Workflow

**User sends voice memo via Discord:**

1. Discord attachment saved to `/tmp/discord_attachments/voice-memo.ogg`
2. PCP detects audio file, activates voice-transcription skill
3. Convert to supported format: `ffmpeg -i voice-memo.ogg -y voice-memo.mp3`
4. Transcribe: `transcribe_audio("voice-memo.mp3")`
5. Return text to user: "Here's what you said: ..."
6. Optionally capture to vault

## Related Skills

- `/vault-operations` - Capture transcriptions
- `/email-processing` - Transcribe voice messages from emails
- `/task-delegation` - Delegate long audio files to background processing
