#!/usr/bin/env python3
"""
PCP Homework Transcription Workflow

Full workflow for transcribing handwritten homework:
1. Process images from Discord
2. Download problem set from OneDrive
3. Transcribe to comprehensive LaTeX using Claude vision
4. Create local Overleaf project
5. (Via Playwright MCP) Create Overleaf project and compile PDF
6. Upload everything to OneDrive

Usage:
    # Full workflow with tag creation
    python homework_workflow.py process \
        --images "/tmp/hw1_p1.jpg" "/tmp/hw1_p2.jpg" \
        --problem-set "Desktop/CHEN5838/problem_sets/PS1.pdf" \
        --output-folder "Desktop/CHEN5838/homeworks/PS1" \
        --project-name "CHEN5838 Problem Set 1" \
        --subject "Chemical Engineering" \
        --class-name "CHEN5838"

    # Just transcribe (no OneDrive interaction)
    python homework_workflow.py transcribe \
        --images "/tmp/hw1_p1.jpg" \
        --project-name "Test Transcription"
"""

import os
import sys
import glob
import json
import shutil
import subprocess
import re
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from onedrive_rclone import OneDriveClient

# Directories - detect container vs host environment
# Inside pcp-agent container: /workspace, /workspace/overleaf
# On host: $PCP_DIR (set via environment variable)
if os.path.exists("/workspace/CLAUDE.md"):
    # Inside container
    WORKSPACE_DIR = "/workspace"
    OVERLEAF_PROJECTS_DIR = "/workspace/overleaf/projects"
    VAULT_FILES_DIR = "/workspace/vault/files"
else:
    # On host
    WORKSPACE_DIR = os.environ.get("PCP_DIR", "/workspace")
    OVERLEAF_PROJECTS_DIR = "/workspace/overleaf/projects"
    VAULT_FILES_DIR = "/workspace/vault/files"

TEMP_DIR = "/tmp/pcp_homework"

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OVERLEAF_PROJECTS_DIR, exist_ok=True)


def slugify(text: str) -> str:
    """Convert text to a valid directory name."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def transcribe_images_to_latex(
    image_paths: List[str],
    problem_set_path: Optional[str] = None,
    subject: str = "Academic Work",
    context: str = "",
    student_name: str = "",  # Set via config or prompt
    user_instructions: str = ""
) -> Dict[str, Any]:
    """
    Use Claude vision to transcribe handwritten work to LaTeX.

    IMPORTANT: This function is called by a sub-agent that MUST ingest:
    - All handwritten work images (the student's actual solutions)
    - The problem set PDF (the original questions)

    The goal is to create a professional LaTeX document that faithfully
    represents the student's work, mimicking their solution style.

    Args:
        image_paths: List of paths to handwritten work images
        problem_set_path: Path to problem set PDF (questions) - SHOULD be provided
        subject: Subject area for formatting
        context: Additional context about the work
        student_name: Name for the document header
        user_instructions: Custom instructions from user (e.g., "be minimal", "skip given equations")

    Returns:
        Dict with success, latex_content, problems_found, notes
    """
    if not image_paths:
        return {"success": False, "error": "No images provided"}

    for path in image_paths:
        if not os.path.exists(path):
            return {"success": False, "error": f"File not found: {path}"}

    # Build user instructions section if provided
    user_instructions_section = ""
    if user_instructions:
        user_instructions_section = f"""
**IMPORTANT - USER'S CUSTOM INSTRUCTIONS (MUST FOLLOW):**
{user_instructions}

These instructions override default behavior. Follow them exactly.
"""

    # Build the prompt - emphasizing faithful transcription
    prompt = f"""You are creating a professional LaTeX homework submission by transcribing handwritten work.

STUDENT: {student_name}
SUBJECT: {subject}
CONTEXT: {context if context else 'Homework solutions'}
NUMBER OF HANDWRITTEN PAGES: {len(image_paths)}
PROBLEM SET PDF PROVIDED: {'Yes - use it to match problems to solutions' if problem_set_path else 'No'}
{user_instructions_section}
YOUR TASK:
You are looking at {student_name}'s handwritten homework solutions. Your job is to:
1. Faithfully transcribe their work into professional LaTeX
2. Preserve their solution approach and methodology exactly
3. Include ALL steps they showed - this IS their work, not a summary
4. Match their solutions to the corresponding problems from the problem set PDF

CRITICAL REQUIREMENTS:
1. Create a COMPLETE, COMPILABLE LaTeX document
2. Use proper math environments: equation, align, cases, matrix, etc.
3. Preserve ALL problem structure (numbers, parts a, b, c, sub-parts)
4. Include EVERY step of work shown - intermediate calculations matter
5. Use standard packages: amsmath, amssymb, amsthm, geometry, enumitem
6. Match the problem numbering from the problem set PDF
7. Use \\section{{Problem X}} for each problem (matching the PDF)
8. Use \\subsection{{Part (a)}} or similar for sub-parts
9. Include any notes, comments, or annotations from the handwritten work
10. For diagrams: describe as [FIGURE: description] or use tikz if simple

STYLE GUIDELINES:
- Format should look like a professional homework submission
- Header with student name, class, assignment name, date
- Clean spacing between problems
- Box or highlight final answers where appropriate
- Include units for physics/engineering problems

OUTPUT FORMAT:
Return ONLY a valid JSON object (no markdown code blocks):
{{
    "latex_content": "\\\\documentclass{{article}}...full document...\\\\end{{document}}",
    "problems_found": ["Problem 1", "Problem 2", ...],
    "packages_used": ["amsmath", "amssymb", ...],
    "notes": "Any notes about unclear handwriting or assumptions made"
}}

IMPORTANT: The latex_content must be a COMPLETE document that will compile.
This is {student_name}'s actual work - transcribe it faithfully."""

    # Build claude command with all images
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
        "--max-turns", "1"
    ]

    # Add each image
    for img_path in image_paths:
        cmd.extend(["--image", img_path])

    # Also include problem set if provided
    if problem_set_path and os.path.exists(problem_set_path):
        cmd.extend(["--image", problem_set_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for complex work
            cwd=WORKSPACE_DIR
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
                match = re.search(r'\{[\s\S]*\}', result_text)
                if match:
                    result_text = match.group(0)

            data = json.loads(result_text)
            data["success"] = True
            return data

        except json.JSONDecodeError as e:
            # Try to extract LaTeX directly
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
                "raw_output": result.stdout[:2000]
            }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Transcription timed out after 5 minutes"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def validate_latex(latex_content: str) -> Dict[str, Any]:
    """Basic validation of LaTeX content."""
    errors = []
    warnings = []

    if "\\documentclass" not in latex_content:
        errors.append("Missing \\documentclass")
    if "\\begin{document}" not in latex_content:
        errors.append("Missing \\begin{document}")
    if "\\end{document}" not in latex_content:
        errors.append("Missing \\end{document}")

    begins = len(re.findall(r'\\begin\{', latex_content))
    ends = len(re.findall(r'\\end\{', latex_content))
    if begins != ends:
        warnings.append(f"Unbalanced environments: {begins} begins, {ends} ends")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def create_project_directory(
    project_name: str,
    latex_content: str,
    source_files: List[str]
) -> Dict[str, Any]:
    """
    Create a local project directory with the transcribed LaTeX.

    Args:
        project_name: Name for the project
        latex_content: The LaTeX document content
        source_files: Original source file paths

    Returns:
        Dict with project_dir, main_tex path, etc.
    """
    project_slug = slugify(project_name)
    project_dir = os.path.join(OVERLEAF_PROJECTS_DIR, project_slug)
    source_dir = os.path.join(project_dir, "source")

    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)

    # Write main.tex
    main_tex_path = os.path.join(project_dir, "main.tex")
    with open(main_tex_path, "w") as f:
        f.write(latex_content)

    # Copy source files
    copied_sources = []
    for src in source_files:
        if os.path.exists(src):
            dest = os.path.join(source_dir, os.path.basename(src))
            shutil.copy(src, dest)
            copied_sources.append(dest)

    # Create manifest
    manifest = {
        "project_name": project_name,
        "created_at": datetime.now().isoformat(),
        "source_files": [os.path.basename(s) for s in copied_sources],
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
        "source_dir": source_dir,
        "source_files": copied_sources,
        "manifest": manifest_path
    }


class HomeworkWorkflow:
    """
    Orchestrates the full homework transcription workflow.

    Flow:
    1. Create OneDrive workspace folder
    2. Upload original images to workspace
    3. Copy problem set PDF to workspace
    4. Transcribe images (agent sees images + problem set)
    5. Create local LaTeX project
    6. (Via Playwright) Create Overleaf project and compile
    7. Download compiled PDF
    8. Upload PDF to OneDrive workspace

    The sub-agent that writes LaTeX MUST ingest:
    - All handwritten work images
    - The problem set PDF (questions)
    To mimic the user's solutions as closely as possible.
    """

    def __init__(self):
        self.onedrive = None  # Lazy init
        self.temp_dir = TEMP_DIR

    def _get_onedrive(self):
        """Lazy initialization of OneDrive client."""
        if self.onedrive is None:
            self.onedrive = OneDriveClient()
        return self.onedrive

    def setup_workspace(
        self,
        class_name: str,
        assignment_name: str,
        base_path: str = "Desktop"
    ) -> Dict[str, str]:
        """
        Create OneDrive workspace folder structure.

        Args:
            class_name: e.g., "CHEN5838"
            assignment_name: e.g., "PS1" or "Problem_Set_1"
            base_path: Base OneDrive path

        Returns:
            Dict with workspace paths
        """
        client = self._get_onedrive()

        # Build workspace path
        workspace = f"{base_path}/{class_name}/homeworks/{assignment_name}"

        # Create directories
        client.mkdir(f"{base_path}/{class_name}")
        client.mkdir(f"{base_path}/{class_name}/homeworks")
        client.mkdir(workspace)
        client.mkdir(f"{workspace}/original_work")
        client.mkdir(f"{workspace}/source")

        return {
            "workspace": workspace,
            "original_work": f"{workspace}/original_work",
            "source": f"{workspace}/source",
            "class_name": class_name,
            "assignment_name": assignment_name
        }

    def upload_source_files(
        self,
        workspace_paths: Dict[str, str],
        image_paths: List[str],
        problem_set_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload source files to OneDrive workspace.

        Args:
            workspace_paths: From setup_workspace()
            image_paths: Local paths to handwritten work images
            problem_set_source: OneDrive path to problem set PDF (to copy)

        Returns:
            Dict with uploaded file paths
        """
        client = self._get_onedrive()
        result = {"uploaded_images": [], "problem_set": None}

        # Upload images
        for i, img_path in enumerate(image_paths, 1):
            if os.path.exists(img_path):
                ext = os.path.splitext(img_path)[1]
                remote_path = f"{workspace_paths['original_work']}/page_{i}{ext}"
                if client.upload(img_path, remote_path):
                    result["uploaded_images"].append(remote_path)

        # Copy problem set if provided
        if problem_set_source:
            # Download then upload to workspace (rclone copy within remote)
            local_ps = os.path.join(self.temp_dir, "problem_set.pdf")
            os.makedirs(self.temp_dir, exist_ok=True)

            if client.download(problem_set_source, local_ps):
                ps_dest = f"{workspace_paths['source']}/problem_set.pdf"
                if client.upload(local_ps, ps_dest):
                    result["problem_set"] = ps_dest
                    result["problem_set_local"] = local_ps

        return result

    def process(
        self,
        image_paths: List[str],
        problem_set_path: Optional[str],
        output_folder: str,
        project_name: str,
        subject: str = "Academic Work",
        class_name: str = None,
        user_instructions: str = ""
    ) -> Dict[str, Any]:
        """
        Run the complete homework workflow.

        Args:
            image_paths: List of paths to handwritten work images
            problem_set_path: OneDrive path to problem set PDF (or None)
            output_folder: OneDrive folder for output
            project_name: Name for the Overleaf project
            subject: Subject for transcription context
            class_name: Class/course name for Overleaf tag (e.g., "CHEN5838")
            user_instructions: Custom instructions from user (e.g., "be minimal", "skip equations for P3")

        Returns:
            Dict with workflow results and next steps
        """
        result = {
            "started_at": datetime.now().isoformat(),
            "project_name": project_name,
            "stages": {},
            "success": False,
            "next_steps": []
        }

        try:
            # Stage 1: Setup temp directory
            os.makedirs(self.temp_dir, exist_ok=True)
            result["stages"]["setup"] = {"success": True}

            # Stage 2: Download problem set from OneDrive (if provided)
            ps_local = None
            if problem_set_path:
                ps_local = os.path.join(self.temp_dir, "problem_set.pdf")
                try:
                    client = self._get_onedrive()
                    if client.download(problem_set_path, ps_local):
                        result["stages"]["download_problem_set"] = {
                            "success": True,
                            "source": problem_set_path,
                            "local": ps_local
                        }
                    else:
                        result["stages"]["download_problem_set"] = {
                            "success": False,
                            "error": f"Failed to download: {problem_set_path}"
                        }
                        ps_local = None  # Continue without problem set
                except Exception as e:
                    result["stages"]["download_problem_set"] = {
                        "success": False,
                        "error": str(e)
                    }
                    ps_local = None

            # Stage 3: Transcribe images to LaTeX
            transcription = transcribe_images_to_latex(
                image_paths,
                problem_set_path=ps_local,
                subject=subject,
                context=f"Homework for {subject}: {project_name}",
                user_instructions=user_instructions
            )
            result["stages"]["transcription"] = transcription

            if not transcription.get("success"):
                raise Exception(f"Transcription failed: {transcription.get('error')}")

            latex_content = transcription.get("latex_content", "")

            # Stage 4: Validate LaTeX
            validation = validate_latex(latex_content)
            result["stages"]["validation"] = validation

            if not validation["valid"]:
                raise Exception(f"Invalid LaTeX: {validation['errors']}")

            # Stage 5: Create local project directory
            project = create_project_directory(
                project_name,
                latex_content,
                image_paths
            )
            result["stages"]["create_project"] = project

            if not project.get("success"):
                raise Exception("Failed to create project directory")

            # Stage 6: Generate Overleaf instructions for Playwright MCP
            # Use file upload approach (more robust than typing content)
            overleaf_instructions = {
                "action": "create_overleaf_project_with_upload",
                "project_name": project_name,
                "local_project_dir": project["project_dir"],
                "main_tex_path": project["main_tex"],
                "class_name": class_name,
                "steps": [
                    "1. Navigate to https://www.overleaf.com/project",
                    "2. Click 'New Project' -> 'Blank Project'",
                    f"3. Enter project name: {project_name}",
                    "4. Wait for editor to load",
                    "5. Click Upload button (folder icon with arrow)",
                    f"6. Upload file: {project['main_tex']}",
                    "7. Click 'Overwrite' if prompted (to replace default main.tex)",
                    "8. Wait for compilation to complete",
                    "9. Download the compiled PDF via Menu -> Download PDF",
                    f"10. Save PDF to: {self.temp_dir}/{slugify(project_name)}.pdf"
                ],
                "helper_functions": {
                    "create_project": "get_playwright_create_project_with_upload_steps(project_name, main_tex_path)",
                    "download_pdf": "get_playwright_download_pdf_steps(project_url, output_path)"
                }
            }

            # Add tag instructions if class_name provided
            if class_name:
                overleaf_instructions["tag_operations"] = {
                    "tag_name": class_name,
                    "steps": [
                        f"1. Check if tag '{class_name}' exists (use api.tag_exists('{class_name}'))",
                        f"2. If not, create tag using get_playwright_create_tag_steps('{class_name}')",
                        f"3. Assign tag to project using get_playwright_assign_tag_steps(project_id, '{class_name}')"
                    ],
                    "helper_functions": {
                        "check_tag": f"api.tag_exists('{class_name}')",
                        "create_tag": f"get_playwright_create_tag_steps('{class_name}')",
                        "assign_tag": f"get_playwright_assign_tag_steps(project_id, '{class_name}')"
                    }
                }

            result["stages"]["overleaf_instructions"] = overleaf_instructions

            # Stage 7: OneDrive upload instructions
            upload_instructions = {
                "output_folder": output_folder,
                "files_to_upload": [
                    {
                        "type": "pdf",
                        "local_path": f"{self.temp_dir}/{slugify(project_name)}.pdf",
                        "remote_path": f"{output_folder}/solutions.pdf",
                        "description": "Compiled PDF from Overleaf"
                    },
                    {
                        "type": "latex",
                        "local_path": project["main_tex"],
                        "remote_path": f"{output_folder}/main.tex",
                        "description": "LaTeX source file"
                    }
                ]
            }

            # Add source images
            for i, img_path in enumerate(image_paths, 1):
                upload_instructions["files_to_upload"].append({
                    "type": "image",
                    "local_path": img_path,
                    "remote_path": f"{output_folder}/original_work/page_{i}{os.path.splitext(img_path)[1]}",
                    "description": f"Original handwritten page {i}"
                })

            result["stages"]["upload_instructions"] = upload_instructions

            # Build next steps
            next_steps = [
                f"1. Use Playwright MCP to create Overleaf project '{project_name}'",
                f"2. Upload {project['main_tex']} to replace default content (use file upload, not paste)",
                "3. Wait for compilation to complete",
            ]

            if class_name:
                next_steps.extend([
                    f"4. Check if tag '{class_name}' exists, create if not",
                    f"5. Assign tag '{class_name}' to the new project",
                    "6. Download compiled PDF from Overleaf",
                    f"7. Upload all files to OneDrive: {output_folder}",
                    "8. Notify user when complete"
                ])
            else:
                next_steps.extend([
                    "4. Download compiled PDF from Overleaf",
                    f"5. Upload all files to OneDrive: {output_folder}",
                    "6. Notify user when complete"
                ])

            result["next_steps"] = next_steps

            result["success"] = True
            result["completed_at"] = datetime.now().isoformat()

            # Summary for user
            result["summary"] = {
                "project_dir": project["project_dir"],
                "main_tex": project["main_tex"],
                "problems_found": transcription.get("problems_found", []),
                "warnings": validation.get("warnings", []),
                "output_folder": output_folder
            }

        except Exception as e:
            result["error"] = str(e)
            result["success"] = False

        return result

    def upload_to_onedrive(
        self,
        local_files: List[Dict],
        output_folder: str
    ) -> Dict[str, Any]:
        """
        Upload completed work to OneDrive.

        Args:
            local_files: List of dicts with 'local_path' and 'remote_path'
            output_folder: Base OneDrive folder

        Returns:
            Dict with upload results
        """
        client = self._get_onedrive()
        results = {
            "success": True,
            "uploaded": [],
            "failed": []
        }

        # Create output folder
        client.mkdir(output_folder)
        client.mkdir(f"{output_folder}/original_work")

        for file_info in local_files:
            local = file_info.get("local_path")
            remote = file_info.get("remote_path")

            if local and remote and os.path.exists(local):
                if client.upload(local, remote):
                    results["uploaded"].append(remote)
                else:
                    results["failed"].append(remote)
                    results["success"] = False
            else:
                results["failed"].append(f"{local} (not found)")

        return results


def transcribe_only(
    image_paths: List[str],
    project_name: str,
    subject: str = "Academic Work",
    user_instructions: str = ""
) -> Dict[str, Any]:
    """
    Just transcribe and create local project (no OneDrive).

    Args:
        image_paths: List of image paths
        project_name: Project name
        subject: Subject area
        user_instructions: Custom instructions from user (e.g., "be minimal", "skip equations")

    Returns:
        Transcription result
    """
    result = {
        "started_at": datetime.now().isoformat(),
        "success": False
    }

    # Transcribe
    transcription = transcribe_images_to_latex(
        image_paths,
        subject=subject,
        context=project_name,
        user_instructions=user_instructions
    )

    if not transcription.get("success"):
        result["error"] = transcription.get("error")
        return result

    # Validate
    validation = validate_latex(transcription.get("latex_content", ""))
    if not validation["valid"]:
        result["error"] = f"Invalid LaTeX: {validation['errors']}"
        return result

    # Create project
    project = create_project_directory(
        project_name,
        transcription["latex_content"],
        image_paths
    )

    result["success"] = True
    result["project_dir"] = project["project_dir"]
    result["main_tex"] = project["main_tex"]
    result["problems_found"] = transcription.get("problems_found", [])
    result["completed_at"] = datetime.now().isoformat()

    return result


def main():
    parser = argparse.ArgumentParser(
        description="PCP Homework Transcription Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full workflow with OneDrive
  python homework_workflow.py process \\
      --images page1.jpg page2.jpg \\
      --problem-set "Desktop/CHEN5838/PS1.pdf" \\
      --output-folder "Desktop/CHEN5838/homeworks/PS1" \\
      --project-name "CHEN5838 PS1 Solutions" \\
      --subject "Chemical Engineering"

  # Just transcribe (no OneDrive)
  python homework_workflow.py transcribe \\
      --images page1.jpg \\
      --project-name "Test"
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Process command (full workflow)
    process_parser = subparsers.add_parser("process", help="Full homework workflow")
    process_parser.add_argument("--images", "-i", nargs="+", required=True,
                                help="Paths to handwritten work images")
    process_parser.add_argument("--problem-set", "-p",
                                help="OneDrive path to problem set PDF")
    process_parser.add_argument("--output-folder", "-o", required=True,
                                help="OneDrive folder for output")
    process_parser.add_argument("--project-name", "-n", required=True,
                                help="Name for the Overleaf project")
    process_parser.add_argument("--subject", "-s", default="Academic Work",
                                help="Subject area")
    process_parser.add_argument("--class-name", "-c",
                                help="Class/course name for Overleaf tag (e.g., CHEN5838)")
    process_parser.add_argument("--instructions", "--user-instructions",
                                help="Custom instructions (e.g., 'be minimal', 'skip given equations for P3')")
    process_parser.add_argument("--json", action="store_true",
                                help="Output as JSON")

    # Transcribe command (just transcribe, no OneDrive)
    transcribe_parser = subparsers.add_parser("transcribe",
                                              help="Just transcribe to LaTeX")
    transcribe_parser.add_argument("--images", "-i", nargs="+", required=True,
                                   help="Paths to handwritten work images")
    transcribe_parser.add_argument("--project-name", "-n", required=True,
                                   help="Name for the project")
    transcribe_parser.add_argument("--subject", "-s", default="Academic Work",
                                   help="Subject area")
    transcribe_parser.add_argument("--instructions", "--user-instructions",
                                   help="Custom instructions (e.g., 'be minimal', 'skip given equations')")
    transcribe_parser.add_argument("--json", action="store_true",
                                   help="Output as JSON")

    args = parser.parse_args()

    if args.command == "process":
        workflow = HomeworkWorkflow()
        result = workflow.process(
            image_paths=args.images,
            problem_set_path=args.problem_set,
            output_folder=args.output_folder,
            project_name=args.project_name,
            subject=args.subject,
            class_name=getattr(args, 'class_name', None),
            user_instructions=getattr(args, 'instructions', '') or ''
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"\nWorkflow completed successfully!")
                print(f"\nProject created at: {result['summary']['project_dir']}")
                print(f"Main TeX: {result['summary']['main_tex']}")
                if result['summary']['problems_found']:
                    print(f"Problems found: {', '.join(result['summary']['problems_found'])}")
                print(f"\nNext steps:")
                for step in result.get("next_steps", []):
                    print(f"  {step}")
            else:
                print(f"\nWorkflow failed: {result.get('error')}")
                sys.exit(1)

    elif args.command == "transcribe":
        result = transcribe_only(
            image_paths=args.images,
            project_name=args.project_name,
            subject=args.subject,
            user_instructions=getattr(args, 'instructions', '') or ''
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"\nTranscription complete!")
                print(f"Project: {result['project_dir']}")
                print(f"Main TeX: {result['main_tex']}")
                if result.get('problems_found'):
                    print(f"Problems: {', '.join(result['problems_found'])}")
            else:
                print(f"\nFailed: {result.get('error')}")
                sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
