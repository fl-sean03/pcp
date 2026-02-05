#!/usr/bin/env python3
"""
Transcribe Handwritten Work to Overleaf

Workflow:
1. Read source (image/PDF) with Claude vision
2. Generate LaTeX from handwritten content
3. Save to local project directory
4. Optionally create Overleaf project via Playwright

Usage:
    python transcribe_to_overleaf.py <source_file> --name "Project Name" [--context "Math 301"]
    python transcribe_to_overleaf.py <source_file> --name "HW5" --upload  # Also upload to Overleaf
"""

import os
import sys
import json
import subprocess
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Directories
OVERLEAF_PROJECTS_DIR = "/workspace/overleaf/projects"
VAULT_FILES_DIR = "/workspace/vault/files"

# Ensure directories exist
os.makedirs(OVERLEAF_PROJECTS_DIR, exist_ok=True)
os.makedirs(VAULT_FILES_DIR, exist_ok=True)


def slugify(text: str) -> str:
    """Convert text to a valid directory name."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def transcribe_to_latex(
    source_path: str,
    context: str = "",
    subject: str = ""
) -> Dict[str, Any]:
    """
    Use Claude vision to transcribe handwritten work to LaTeX.

    Args:
        source_path: Path to image or PDF file
        context: Additional context (e.g., "Math 301 HW5")
        subject: Subject area for better formatting hints

    Returns:
        Dict with latex_content, structure info, and metadata
    """
    if not os.path.exists(source_path):
        return {"success": False, "error": f"File not found: {source_path}"}

    # Build the prompt
    prompt = f"""Transcribe this handwritten mathematical/academic work to LaTeX.

Context: {context if context else 'Academic work'}
Subject: {subject if subject else 'Not specified'}

Requirements:
1. Use proper LaTeX math environments (equation, align, cases, etc.)
2. Preserve the structure (problem numbers, parts a, b, c, etc.)
3. Include all work shown, not just final answers
4. Use standard packages: amsmath, amssymb, amsthm
5. Format cleanly with proper spacing and line breaks
6. Use \\section or \\textbf for problem numbers
7. Include any diagrams/figures as \\begin{{tikzpicture}} if simple,
   or note [FIGURE: description] if complex

Return a JSON object with:
{{
    "latex_content": "Full LaTeX document content (complete, compilable)",
    "problems_found": ["Problem 1", "Problem 2", ...],
    "packages_used": ["amsmath", "amssymb", ...],
    "notes": "Any notes about unclear parts or assumptions made"
}}

The latex_content MUST be a complete, compilable document starting with
\\documentclass and ending with \\end{{document}}."""

    # Call Claude with the image/PDF
    try:
        result = subprocess.run(
            [
                "claude",
                "-p", prompt,
                "--image", source_path,
                "--output-format", "json",
                "--max-turns", "1"
            ],
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout for complex transcriptions
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Claude failed: {result.stderr}"
            }

        # Parse the response
        try:
            response = json.loads(result.stdout)
            result_text = response.get("result", result.stdout)

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                # Try to find JSON object in output
                match = re.search(r'\{[\s\S]*\}', result_text)
                if match:
                    result_text = match.group(0)

            data = json.loads(result_text)
            data["success"] = True
            return data

        except json.JSONDecodeError as e:
            # If JSON parsing fails, try to extract LaTeX directly
            latex_match = re.search(r'\\documentclass[\s\S]*\\end\{document\}', result.stdout)
            if latex_match:
                return {
                    "success": True,
                    "latex_content": latex_match.group(0),
                    "problems_found": [],
                    "packages_used": ["amsmath", "amssymb"],
                    "notes": "Extracted LaTeX directly from response"
                }
            return {
                "success": False,
                "error": f"Failed to parse response: {e}",
                "raw_output": result.stdout[:1000]
            }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Transcription timed out after 3 minutes"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_project_directory(
    project_name: str,
    latex_content: str,
    source_path: str
) -> Dict[str, Any]:
    """
    Create a local project directory with the transcribed LaTeX.

    Args:
        project_name: Name for the project
        latex_content: The LaTeX document content
        source_path: Original source file path

    Returns:
        Dict with project_dir, main_tex path, etc.
    """
    # Create project directory
    project_slug = slugify(project_name)
    project_dir = os.path.join(OVERLEAF_PROJECTS_DIR, project_slug)
    source_dir = os.path.join(project_dir, "source")

    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)

    # Write main.tex
    main_tex_path = os.path.join(project_dir, "main.tex")
    with open(main_tex_path, "w") as f:
        f.write(latex_content)

    # Copy source file
    source_filename = os.path.basename(source_path)
    source_copy_path = os.path.join(source_dir, source_filename)
    subprocess.run(["cp", source_path, source_copy_path], check=True)

    # Create manifest
    manifest = {
        "project_name": project_name,
        "created_at": datetime.now().isoformat(),
        "source_file": source_filename,
        "main_tex": "main.tex",
        "overleaf_project_id": None,
        "last_synced": None
    }

    manifest_path = os.path.join(project_dir, ".project_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return {
        "success": True,
        "project_dir": project_dir,
        "main_tex": main_tex_path,
        "source_copy": source_copy_path,
        "manifest": manifest_path
    }


def validate_latex(latex_content: str) -> Dict[str, Any]:
    """
    Basic validation of LaTeX content.
    """
    errors = []
    warnings = []

    # Check for document structure
    if "\\documentclass" not in latex_content:
        errors.append("Missing \\documentclass")
    if "\\begin{document}" not in latex_content:
        errors.append("Missing \\begin{document}")
    if "\\end{document}" not in latex_content:
        errors.append("Missing \\end{document}")

    # Check for balanced environments
    begins = len(re.findall(r'\\begin\{', latex_content))
    ends = len(re.findall(r'\\end\{', latex_content))
    if begins != ends:
        warnings.append(f"Unbalanced environments: {begins} begins, {ends} ends")

    # Check for common issues
    if "\\$" in latex_content and "$" not in latex_content:
        warnings.append("Escaped dollar signs without matching unescaped ones")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def full_transcription_workflow(
    source_path: str,
    project_name: str,
    context: str = "",
    subject: str = "",
    upload_to_overleaf: bool = False
) -> Dict[str, Any]:
    """
    Complete workflow: source -> LaTeX -> local project [-> Overleaf]

    Args:
        source_path: Path to source image/PDF
        project_name: Name for the project
        context: Additional context about the content
        subject: Subject area
        upload_to_overleaf: Whether to create Overleaf project

    Returns:
        Complete result with all workflow stages
    """
    result = {
        "started_at": datetime.now().isoformat(),
        "source_path": source_path,
        "project_name": project_name,
        "stages": {}
    }

    # Stage 1: Transcribe to LaTeX
    print(f"[1/3] Transcribing {source_path} to LaTeX...")
    transcription = transcribe_to_latex(source_path, context, subject)
    result["stages"]["transcription"] = transcription

    if not transcription.get("success"):
        result["success"] = False
        result["error"] = f"Transcription failed: {transcription.get('error')}"
        return result

    latex_content = transcription.get("latex_content", "")

    # Stage 2: Validate LaTeX
    print("[2/3] Validating LaTeX...")
    validation = validate_latex(latex_content)
    result["stages"]["validation"] = validation

    if not validation["valid"]:
        result["success"] = False
        result["error"] = f"Invalid LaTeX: {validation['errors']}"
        return result

    # Stage 3: Create project directory
    print("[3/3] Creating project directory...")
    project = create_project_directory(project_name, latex_content, source_path)
    result["stages"]["project"] = project

    if not project.get("success"):
        result["success"] = False
        result["error"] = "Failed to create project directory"
        return result

    # Stage 4: Upload to Overleaf (optional)
    if upload_to_overleaf:
        print("[4/4] Uploading to Overleaf...")
        # Note: This requires Playwright MCP - the worker agent will handle this
        result["stages"]["overleaf"] = {
            "status": "pending",
            "note": "Use Playwright MCP to create Overleaf project"
        }

    result["success"] = True
    result["completed_at"] = datetime.now().isoformat()
    result["summary"] = {
        "project_dir": project["project_dir"],
        "main_tex": project["main_tex"],
        "problems_found": transcription.get("problems_found", []),
        "warnings": validation.get("warnings", [])
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe handwritten work to LaTeX and create Overleaf project"
    )
    parser.add_argument("source", help="Source file (image or PDF)")
    parser.add_argument("--name", "-n", required=True, help="Project name")
    parser.add_argument("--context", "-c", default="", help="Additional context")
    parser.add_argument("--subject", "-s", default="", help="Subject area")
    parser.add_argument("--upload", action="store_true", help="Upload to Overleaf")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = full_transcription_workflow(
        source_path=args.source,
        project_name=args.name,
        context=args.context,
        subject=args.subject,
        upload_to_overleaf=args.upload
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(f"\nSuccess! Project created at: {result['summary']['project_dir']}")
            print(f"Main TeX: {result['summary']['main_tex']}")
            if result['summary']['problems_found']:
                print(f"Problems found: {', '.join(result['summary']['problems_found'])}")
            if result['summary']['warnings']:
                print(f"Warnings: {', '.join(result['summary']['warnings'])}")
        else:
            print(f"\nFailed: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
