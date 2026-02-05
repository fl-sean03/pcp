#!/usr/bin/env python3
"""
PowerPoint Deck Builder

Build polished presentations from YAML/JSON plans.
Part of the powerpoint-builder skill.

Usage:
    python build_deck.py --plan deck_plan.yaml --output deck.pptx
    python build_deck.py --plan deck_plan.yaml --template brand.pptx --output deck.pptx
    python build_deck.py --validate deck_plan.yaml
    python build_deck.py --list-layouts
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

import yaml
from pptx import Presentation

from theme import PCPTheme, get_theme
from layouts import LAYOUT_FUNCTIONS


class BuildLog:
    """Collects warnings and info during build."""

    def __init__(self):
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.errors: List[str] = []

    def warn(self, msg: str):
        self.warnings.append(msg)
        print(f"WARNING: {msg}", file=sys.stderr)

    def info_msg(self, msg: str):
        self.info.append(msg)

    def error(self, msg: str):
        self.errors.append(msg)
        print(f"ERROR: {msg}", file=sys.stderr)

    def save(self, path: str):
        with open(path, 'w') as f:
            f.write(f"Build Log - {datetime.now().isoformat()}\n")
            f.write("=" * 50 + "\n\n")

            if self.errors:
                f.write("ERRORS:\n")
                for e in self.errors:
                    f.write(f"  - {e}\n")
                f.write("\n")

            if self.warnings:
                f.write("WARNINGS:\n")
                for w in self.warnings:
                    f.write(f"  - {w}\n")
                f.write("\n")

            if self.info:
                f.write("INFO:\n")
                for i in self.info:
                    f.write(f"  - {i}\n")

            if not self.errors and not self.warnings:
                f.write("Build completed successfully with no warnings.\n")


class DeckBuilder:
    """
    Build PowerPoint decks from structured plans.

    Example:
        builder = DeckBuilder()
        builder.load_plan("deck_plan.yaml")
        builder.build()
        builder.save("output.pptx")
    """

    def __init__(
        self,
        template: Optional[str] = None,
        theme_name: str = "default"
    ):
        """
        Initialize the builder.

        Args:
            template: Path to template .pptx (recommended)
            theme_name: Theme preset name
        """
        self.template = template
        self.theme = get_theme(theme_name)
        self.plan: Dict[str, Any] = {}
        self.prs: Optional[Presentation] = None
        self.log = BuildLog()
        self.assets_manifest: Dict[int, List[str]] = {}

    def load_plan(self, plan_path: str) -> Dict[str, Any]:
        """Load a deck plan from YAML or JSON file."""
        path = Path(plan_path)

        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_path}")

        with open(path) as f:
            if path.suffix in ['.yaml', '.yml']:
                self.plan = yaml.safe_load(f)
            elif path.suffix == '.json':
                self.plan = json.load(f)
            else:
                raise ValueError(f"Unsupported plan format: {path.suffix}")

        self.log.info_msg(f"Loaded plan from {plan_path}")
        return self.plan

    def load_plan_dict(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Load plan from dictionary (for programmatic use)."""
        self.plan = plan
        return self.plan

    def validate(self) -> List[str]:
        """
        Validate the plan.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        if not self.plan:
            errors.append("No plan loaded")
            return errors

        if 'slides' not in self.plan:
            errors.append("Plan must have 'slides' key")
            return errors

        for i, slide in enumerate(self.plan['slides']):
            slide_num = i + 1

            if 'type' not in slide:
                errors.append(f"Slide {slide_num}: missing 'type'")
                continue

            slide_type = slide['type']
            if slide_type not in LAYOUT_FUNCTIONS:
                errors.append(f"Slide {slide_num}: unknown type '{slide_type}'")
                continue

            # Type-specific validation
            if slide_type in ['title', 'section', 'bullets', 'figure', 'key_number']:
                if 'title' not in slide:
                    errors.append(f"Slide {slide_num} ({slide_type}): missing 'title'")

            if slide_type == 'bullets' and 'bullets' not in slide:
                errors.append(f"Slide {slide_num}: bullets slide missing 'bullets' list")

            if slide_type in ['figure', 'figure_with_text']:
                if 'image' not in slide:
                    errors.append(f"Slide {slide_num}: figure slide missing 'image' path")

            if slide_type == 'key_number' and 'number' not in slide:
                errors.append(f"Slide {slide_num}: key_number slide missing 'number'")

            if slide_type == 'comparison':
                if 'left' not in slide or 'right' not in slide:
                    errors.append(f"Slide {slide_num}: comparison slide missing 'left' or 'right'")

        return errors

    def build(self) -> Presentation:
        """
        Build the presentation from loaded plan.

        Returns the Presentation object.
        """
        if not self.plan:
            raise ValueError("No plan loaded. Call load_plan() first.")

        # Validate first
        errors = self.validate()
        if errors:
            for e in errors:
                self.log.error(e)
            raise ValueError(f"Plan validation failed with {len(errors)} errors")

        # Create presentation
        if self.template and os.path.exists(self.template):
            self.prs = Presentation(self.template)
            self.log.info_msg(f"Using template: {self.template}")
        else:
            self.prs = Presentation()
            if self.template:
                self.log.warn(f"Template not found: {self.template}, using blank")

        # Build each slide
        for i, slide_spec in enumerate(self.plan['slides']):
            slide_num = i + 1
            slide_type = slide_spec['type']

            try:
                self._build_slide(slide_num, slide_spec)
                self.log.info_msg(f"Built slide {slide_num}: {slide_type}")
            except Exception as e:
                self.log.error(f"Slide {slide_num} failed: {e}")

        return self.prs

    def _build_slide(self, slide_num: int, spec: Dict[str, Any]):
        """Build a single slide from spec."""
        slide_type = spec['type']
        func = LAYOUT_FUNCTIONS[slide_type]

        # Track assets
        assets = []
        if 'image' in spec:
            assets.append(spec['image'])
        self.assets_manifest[slide_num] = assets

        # Check for missing assets
        for asset in assets:
            if not os.path.exists(asset):
                self.log.warn(f"Slide {slide_num}: asset not found: {asset}")

        # Map spec to function arguments
        kwargs = self._map_spec_to_kwargs(slide_type, spec)

        # Call the layout function
        func(self.prs, self.theme, **kwargs)

    def _map_spec_to_kwargs(self, slide_type: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Map plan spec to layout function kwargs."""
        # Common mappings
        kwargs = {}

        # Direct mappings
        direct_keys = ['title', 'subtitle', 'note', 'caption', 'number', 'qualifier',
                       'kicker', 'verdict', 'side', 'meta', 'bullets', 'steps',
                       'left', 'right', 'headers', 'data']

        for key in direct_keys:
            if key in spec:
                kwargs[key] = spec[key]

        # Renamed mappings
        if 'image' in spec:
            kwargs['image_path'] = spec['image']

        return kwargs

    def save(self, output_path: str):
        """Save the built presentation."""
        if not self.prs:
            raise ValueError("No presentation built. Call build() first.")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        self.prs.save(output_path)
        self.log.info_msg(f"Saved presentation to {output_path}")

    def save_manifest(self, path: str):
        """Save the assets manifest."""
        with open(path, 'w') as f:
            json.dump(self.assets_manifest, f, indent=2)

    def save_log(self, path: str):
        """Save the build log."""
        self.log.save(path)


def create_project_deck(
    project_context: Dict[str, Any],
    output: str,
    slide_types: Optional[List[str]] = None
) -> str:
    """
    Create a deck from PCP project context.

    Args:
        project_context: Result from vault_v2.get_project_context()
        output: Output path
        slide_types: Which sections to include

    Returns:
        Path to created deck
    """
    if slide_types is None:
        slide_types = ["status", "metrics", "tasks", "people"]

    plan = {
        "title": project_context.get("name", "Project Review"),
        "slides": []
    }

    # Title slide
    plan["slides"].append({
        "type": "title",
        "title": project_context.get("name", "Project"),
        "subtitle": project_context.get("description", ""),
        "meta": datetime.now().strftime("%B %Y")
    })

    # Status section
    if "status" in slide_types:
        health = project_context.get("health", {})
        plan["slides"].append({
            "type": "section",
            "title": "Project Status"
        })
        plan["slides"].append({
            "type": "key_number",
            "title": f"Project health: {health.get('status', 'Unknown')}",
            "number": health.get('status', '?').upper(),
            "qualifier": f"{health.get('days_since_activity', '?')} days since activity"
        })

    # Tasks section
    if "tasks" in slide_types:
        tasks = project_context.get("pending_tasks", [])
        if tasks:
            plan["slides"].append({
                "type": "section",
                "title": "Pending Tasks"
            })
            plan["slides"].append({
                "type": "bullets",
                "title": f"{len(tasks)} tasks pending",
                "bullets": [t.get("content", "") for t in tasks[:5]]
            })

    builder = DeckBuilder()
    builder.load_plan_dict(plan)
    builder.build()
    builder.save(output)

    return output


def create_brief_deck(
    brief_data: Dict[str, Any],
    output: str
) -> str:
    """
    Create a deck from a PCP brief.

    Args:
        brief_data: Result from brief.generate_brief()
        output: Output path

    Returns:
        Path to created deck
    """
    plan = {
        "title": brief_data.get("type", "Brief").title(),
        "slides": []
    }

    # Title slide
    plan["slides"].append({
        "type": "title",
        "title": f"{brief_data.get('type', 'Weekly').title()} Brief",
        "subtitle": brief_data.get("period", ""),
        "meta": datetime.now().strftime("%B %d, %Y")
    })

    # Stats
    if "stats" in brief_data:
        stats = brief_data["stats"]
        plan["slides"].append({
            "type": "key_number",
            "title": "Activity this period",
            "number": str(stats.get("captures", 0)),
            "qualifier": "captures recorded"
        })

    # Tasks
    if "tasks" in brief_data:
        tasks = brief_data["tasks"]
        if tasks.get("overdue"):
            plan["slides"].append({
                "type": "bullets",
                "title": f"{len(tasks['overdue'])} overdue tasks need attention",
                "bullets": [t.get("content", "") for t in tasks["overdue"][:5]]
            })

    builder = DeckBuilder()
    builder.load_plan_dict(plan)
    builder.build()
    builder.save(output)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Build PowerPoint decks from YAML/JSON plans"
    )
    parser.add_argument("--plan", help="Path to deck plan (YAML or JSON)")
    parser.add_argument("--template", help="Path to template .pptx")
    parser.add_argument("--output", "-o", help="Output path for .pptx")
    parser.add_argument("--theme", default="default", help="Theme name")
    parser.add_argument("--validate", action="store_true", help="Validate plan only")
    parser.add_argument("--dry-run", action="store_true", help="Validate without building")
    parser.add_argument("--list-layouts", action="store_true", help="List available layouts")
    parser.add_argument("--log", help="Path for build log")
    parser.add_argument("--manifest", help="Path for assets manifest")

    args = parser.parse_args()

    # List layouts
    if args.list_layouts:
        print("Available slide layouts:")
        for name in sorted(LAYOUT_FUNCTIONS.keys()):
            print(f"  - {name}")
        return 0

    # Require plan for other operations
    if not args.plan:
        parser.error("--plan is required (or use --list-layouts)")

    # Build
    builder = DeckBuilder(template=args.template, theme_name=args.theme)

    try:
        builder.load_plan(args.plan)
    except Exception as e:
        print(f"Failed to load plan: {e}", file=sys.stderr)
        return 1

    # Validate
    errors = builder.validate()
    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if args.validate or args.dry_run:
        print("Plan is valid.")
        return 0

    # Require output for build
    if not args.output:
        parser.error("--output is required for build")

    # Build and save
    try:
        builder.build()
        builder.save(args.output)
        print(f"Created: {args.output}")

        # Save optional outputs
        if args.log:
            builder.save_log(args.log)
            print(f"Log: {args.log}")

        if args.manifest:
            builder.save_manifest(args.manifest)
            print(f"Manifest: {args.manifest}")

        # Summary
        print(f"\nBuilt {len(builder.plan.get('slides', []))} slides")
        if builder.log.warnings:
            print(f"Warnings: {len(builder.log.warnings)}")

        return 0

    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
