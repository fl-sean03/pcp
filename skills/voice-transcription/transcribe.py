#!/usr/bin/env python3
"""
Voice Transcription Helper Script

Transcribe audio files using OpenAI's Whisper API or local transcription.
Part of the voice-transcription skill.

Usage:
    python transcribe.py /path/to/audio.mp3
    python transcribe.py /path/to/audio.wav --model whisper-1 --language en

Python API:
    from transcribe import transcribe_audio
    result = transcribe_audio("/path/to/audio.mp3")
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


# Supported formats for OpenAI Whisper API
SUPPORTED_FORMATS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac"}

# Maximum file size (25MB for OpenAI API)
MAX_FILE_SIZE_MB = 25


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def check_local_whisper() -> bool:
    """Check if local whisper CLI is available."""
    return shutil.which("whisper") is not None


def get_file_format(file_path: Path) -> str:
    """Get the audio file format from extension."""
    return file_path.suffix.lower().lstrip(".")


def convert_audio(input_path: Path, output_format: str = "mp3") -> Optional[Path]:
    """Convert audio file to a supported format using ffmpeg."""
    if not check_ffmpeg():
        return None

    output_path = input_path.with_suffix(f".{output_format}")

    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(input_path),
                "-ar", "16000",  # Sample rate
                "-ac", "1",      # Mono
                "-y",            # Overwrite
                str(output_path)
            ],
            capture_output=True,
            check=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr.decode()}", file=sys.stderr)
        return None


def transcribe_with_openai(
    file_path: Path,
    model: str = "whisper-1",
    language: Optional[str] = None
) -> Dict[str, Any]:
    """Transcribe audio using OpenAI Whisper API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"success": False, "error": "OPENAI_API_KEY not set"}

    try:
        import requests
    except ImportError:
        # Use curl as fallback
        return transcribe_with_curl(file_path, api_key, model, language)

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "audio/mpeg")}
        data = {"model": model}
        if language:
            data["language"] = language

        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code == 200:
        result = response.json()
        return {
            "success": True,
            "text": result.get("text", ""),
            "model": model,
            "method": "openai_api"
        }
    else:
        return {
            "success": False,
            "error": f"API error {response.status_code}: {response.text}"
        }


def transcribe_with_curl(
    file_path: Path,
    api_key: str,
    model: str = "whisper-1",
    language: Optional[str] = None
) -> Dict[str, Any]:
    """Transcribe using curl (fallback if requests not available)."""
    cmd = [
        "curl", "-s",
        "https://api.openai.com/v1/audio/transcriptions",
        "-H", f"Authorization: Bearer {api_key}",
        "-F", f"file=@{file_path}",
        "-F", f"model={model}"
    ]

    if language:
        cmd.extend(["-F", f"language={language}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        if "error" in data:
            return {"success": False, "error": data["error"]["message"]}

        return {
            "success": True,
            "text": data.get("text", ""),
            "model": model,
            "method": "curl"
        }
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"curl failed: {e.stderr}"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON response: {e}"}


def transcribe_with_local_whisper(
    file_path: Path,
    model: str = "base",
    language: Optional[str] = None
) -> Dict[str, Any]:
    """Transcribe using local whisper CLI."""
    if not check_local_whisper():
        return {"success": False, "error": "Local whisper not installed"}

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "whisper", str(file_path),
            "--model", model,
            "--output_format", "txt",
            "--output_dir", tmpdir
        ]

        if language:
            cmd.extend(["--language", language])

        try:
            subprocess.run(cmd, capture_output=True, check=True)

            # Read the output file
            output_file = Path(tmpdir) / f"{file_path.stem}.txt"
            if output_file.exists():
                text = output_file.read_text().strip()
                return {
                    "success": True,
                    "text": text,
                    "model": f"local-{model}",
                    "method": "local_whisper"
                }
            else:
                return {"success": False, "error": "No output file generated"}

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Whisper failed: {e.stderr.decode()}"}


def transcribe_audio(
    file_path: str,
    model: str = "whisper-1",
    language: Optional[str] = None,
    fallback_to_local: bool = True
) -> Dict[str, Any]:
    """
    Transcribe an audio file.

    Args:
        file_path: Path to the audio file
        model: Model to use (whisper-1 for API, base/small/medium/large for local)
        language: Language code (e.g., 'en', 'es') - auto-detect if not set
        fallback_to_local: If True, try local whisper if API fails

    Returns:
        Dict with keys: success, text (if success), error (if failed), model, method
    """
    path = Path(file_path)

    # Check file exists
    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return {
            "success": False,
            "error": f"File too large: {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"
        }

    # Get format and convert if necessary
    fmt = get_file_format(path)
    working_path = path

    if fmt not in SUPPORTED_FORMATS:
        print(f"Converting {fmt} to mp3...", file=sys.stderr)
        converted = convert_audio(path, "mp3")
        if converted:
            working_path = converted
        else:
            return {
                "success": False,
                "error": f"Unsupported format '{fmt}' and conversion failed"
            }

    # Try OpenAI API first
    if os.environ.get("OPENAI_API_KEY"):
        result = transcribe_with_openai(working_path, model, language)
        if result["success"]:
            return result
        elif fallback_to_local:
            print(f"OpenAI API failed: {result['error']}, trying local...", file=sys.stderr)
        else:
            return result

    # Try local whisper
    if fallback_to_local or not os.environ.get("OPENAI_API_KEY"):
        local_model = "base" if model == "whisper-1" else model
        result = transcribe_with_local_whisper(working_path, local_model, language)
        return result

    return {"success": False, "error": "No transcription method available"}


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe audio files")
    parser.add_argument("file", help="Audio file to transcribe")
    parser.add_argument("--model", default="whisper-1", help="Model to use")
    parser.add_argument("--language", help="Language code (e.g., en, es)")
    parser.add_argument("--no-fallback", action="store_true",
                       help="Don't fall back to local whisper")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = transcribe_audio(
        args.file,
        model=args.model,
        language=args.language,
        fallback_to_local=not args.no_fallback
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(result["text"])
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
