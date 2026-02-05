#!/usr/bin/env python3
"""
File Processor - Handles ingestion of images, PDFs, documents, and other files.
Uses Claude's vision capabilities for images, extracts text from documents.
"""

import os
import json
import sqlite3
import subprocess
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

VAULT_PATH = "/workspace/vault/vault.db"
FILES_DIR = "/workspace/vault/files"

# Ensure files directory exists
os.makedirs(FILES_DIR, exist_ok=True)


def get_mime_type(file_path: str) -> str:
    """Get MIME type of a file."""
    result = subprocess.run(
        ["file", "--mime-type", "-b", file_path],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def hash_file(file_path: str) -> str:
    """Generate SHA256 hash of file for deduplication."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def process_image(file_path: str, context: str = "") -> Dict[str, Any]:
    """
    Process an image using Claude's vision capabilities.
    Returns extracted text (OCR) and description.
    """
    # Read image and encode to base64
    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    mime_type = get_mime_type(file_path)

    # Use Claude to analyze the image
    prompt = f"""Analyze this image and provide:
1. DESCRIPTION: A brief description of what the image shows
2. TEXT_CONTENT: Any text visible in the image (OCR)
3. KEY_INFO: Key information or data points
4. ENTITIES: People, projects, topics, or dates mentioned

Context from user: {context if context else 'None provided'}

Return as JSON:
{{
    "description": "...",
    "text_content": "...",
    "key_info": ["...", "..."],
    "entities": {{
        "people": [],
        "projects": [],
        "topics": [],
        "dates": []
    }}
}}"""

    # Call Claude with the image
    # Note: This uses claude CLI with image input
    result = subprocess.run(
        ["claude", "-p", prompt, "--image", file_path, "--output-format", "json"],
        capture_output=True, text=True, timeout=120
    )

    try:
        response = json.loads(result.stdout)
        # Parse the actual result from Claude's JSON response
        if isinstance(response, dict) and "result" in response:
            result_text = response["result"]
            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            analysis = json.loads(result_text)
        else:
            analysis = response
    except (json.JSONDecodeError, KeyError, IndexError):
        # Try OCR with tesseract as fallback
        try:
            ocr_result = subprocess.run(
                ["tesseract", file_path, "stdout"],
                capture_output=True, text=True, timeout=30
            )
            ocr_text = ocr_result.stdout.strip()
        except:
            ocr_text = ""

        analysis = {
            "description": result.stdout[:500] if result.stdout else "Image analyzed",
            "text_content": ocr_text,
            "key_info": [],
            "entities": {"people": [], "projects": [], "topics": [], "dates": []}
        }

    return {
        "mime_type": mime_type,
        "extracted_text": analysis.get("text_content", ""),
        "summary": analysis.get("description", ""),
        "key_info": analysis.get("key_info", []),
        "entities": analysis.get("entities", {})
    }


def process_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extract text from PDF using pdftotext or fallback methods.
    """
    extracted_text = ""

    # Try pdftotext first
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", file_path, "-"],
            capture_output=True, text=True, timeout=60
        )
        extracted_text = result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # If pdftotext didn't work, try python-based extraction
    if not extracted_text:
        try:
            # Fallback: use strings command for basic extraction
            result = subprocess.run(
                ["strings", file_path],
                capture_output=True, text=True, timeout=30
            )
            extracted_text = result.stdout[:50000]  # Limit size
        except:
            extracted_text = "[PDF text extraction failed]"

    # Generate summary using Claude
    if extracted_text and len(extracted_text) > 100:
        summary_prompt = f"""Summarize this document content in 2-3 sentences.
Also extract any people, projects, topics, or dates mentioned.

Content (truncated to 5000 chars):
{extracted_text[:5000]}

Return as JSON:
{{
    "summary": "...",
    "entities": {{
        "people": [],
        "projects": [],
        "topics": [],
        "dates": []
    }}
}}"""

        result = subprocess.run(
            ["claude", "-p", summary_prompt, "--output-format", "json"],
            capture_output=True, text=True, timeout=60
        )

        try:
            response = json.loads(result.stdout)
            # Parse the actual result from Claude's JSON response
            if isinstance(response, dict) and "result" in response:
                result_text = response["result"]
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                analysis = json.loads(result_text)
            else:
                analysis = response
            summary = analysis.get("summary", "")
            entities = analysis.get("entities", {})
        except:
            summary = extracted_text[:200] + "..."
            entities = {}
    else:
        summary = extracted_text[:200] if extracted_text else "Empty or unreadable PDF"
        entities = {}

    return {
        "mime_type": "application/pdf",
        "extracted_text": extracted_text,
        "summary": summary,
        "entities": entities
    }


def process_text_file(file_path: str) -> Dict[str, Any]:
    """Process plain text, markdown, code files."""
    with open(file_path, "r", errors="ignore") as f:
        content = f.read()

    # Truncate very large files
    if len(content) > 100000:
        content = content[:100000] + "\n\n[... truncated ...]"

    # Get summary for larger files
    if len(content) > 500:
        summary_prompt = f"""Summarize this file content briefly.
Extract any people, projects, topics mentioned.

Content:
{content[:5000]}

Return JSON: {{"summary": "...", "entities": {{"people":[], "projects":[], "topics":[]}}}}"""

        result = subprocess.run(
            ["claude", "-p", summary_prompt, "--output-format", "json"],
            capture_output=True, text=True, timeout=60
        )

        try:
            response = json.loads(result.stdout)
            # Parse the actual result from Claude's JSON response
            if isinstance(response, dict) and "result" in response:
                result_text = response["result"]
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                analysis = json.loads(result_text)
            else:
                analysis = response
            summary = analysis.get("summary", content[:200])
            entities = analysis.get("entities", {})
        except:
            summary = content[:200]
            entities = {}
    else:
        summary = content
        entities = {}

    return {
        "mime_type": get_mime_type(file_path),
        "extracted_text": content,
        "summary": summary,
        "entities": entities
    }


def process_file(
    file_path: str,
    original_name: str = None,
    source: str = "discord",
    source_id: str = None,
    context: str = ""
) -> Dict[str, Any]:
    """
    Main entry point - process any file type.
    Returns processed data ready for database storage.
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    file_path = os.path.abspath(file_path)
    original_name = original_name or os.path.basename(file_path)
    extension = Path(original_name).suffix.lower()
    mime_type = get_mime_type(file_path)
    file_size = os.path.getsize(file_path)
    file_hash = hash_file(file_path)

    # Copy to vault files directory with hash-based name
    dest_name = f"{file_hash[:16]}_{original_name}"
    dest_path = os.path.join(FILES_DIR, dest_name)

    if not os.path.exists(dest_path):
        subprocess.run(["cp", file_path, dest_path])

    # Process based on type
    if mime_type.startswith("image/"):
        result = process_image(file_path, context)
    elif mime_type == "application/pdf":
        result = process_pdf(file_path)
    elif mime_type.startswith("text/") or extension in [".md", ".py", ".js", ".json", ".yaml", ".yml", ".sh", ".sql"]:
        result = process_text_file(file_path)
    else:
        # Unknown type - just store metadata
        result = {
            "mime_type": mime_type,
            "extracted_text": "",
            "summary": f"File: {original_name} ({mime_type})",
            "entities": {}
        }

    # Add common metadata
    result.update({
        "file_path": dest_path,
        "file_name": original_name,
        "file_size": file_size,
        "file_hash": file_hash,
        "source": source,
        "source_id": source_id,
        "extension": extension
    })

    return result


def ingest_file(
    file_path: str,
    original_name: str = None,
    source: str = "discord",
    source_id: str = None,
    context: str = ""
) -> int:
    """
    Process a file and store in the database.
    Returns the capture ID.
    """
    # Process the file
    result = process_file(file_path, original_name, source, source_id, context)

    if "error" in result:
        print(f"Error processing file: {result['error']}")
        return -1

    # Determine capture type based on content
    content_type = "image" if result["mime_type"].startswith("image/") else "file"

    # Store in database
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Build content description
    content = f"[{content_type.upper()}] {result['file_name']}"
    if context:
        content += f"\nContext: {context}"
    if result.get("summary"):
        content += f"\nSummary: {result['summary']}"

    cursor.execute("""
        INSERT INTO captures_v2 (
            content, content_type, capture_type,
            file_path, file_name, file_size, mime_type,
            extracted_text, summary, extracted_entities,
            source, source_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        content,
        content_type,
        "note",  # Default, can be updated
        result["file_path"],
        result["file_name"],
        result["file_size"],
        result["mime_type"],
        result.get("extracted_text", ""),
        result.get("summary", ""),
        json.dumps(result.get("entities", {})),
        source,
        source_id,
        datetime.now().isoformat()
    ))

    capture_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"Ingested file '{original_name}' as capture #{capture_id}")
    return capture_id


def search_files(query: str, limit: int = 10) -> list:
    """Search through file contents and metadata."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_name, summary, extracted_text, created_at
        FROM captures_v2
        WHERE content_type IN ('image', 'file')
        AND (
            file_name LIKE ?
            OR extracted_text LIKE ?
            OR summary LIKE ?
        )
        ORDER BY created_at DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))

    results = []
    for row in cursor.fetchall():
        results.append({
            "id": row[0],
            "file_name": row[1],
            "summary": row[2],
            "excerpt": row[3][:200] if row[3] else "",
            "created_at": row[4]
        })

    conn.close()
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python file_processor.py <file_path> [context]")
        print("       python file_processor.py --search <query>")
        sys.exit(1)

    if sys.argv[1] == "--search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        results = search_files(query)
        for r in results:
            print(f"[{r['id']}] {r['file_name']}: {r['summary'][:100]}")
    else:
        file_path = sys.argv[1]
        context = sys.argv[2] if len(sys.argv) > 2 else ""
        capture_id = ingest_file(file_path, context=context)
        print(f"Ingested as capture #{capture_id}")
