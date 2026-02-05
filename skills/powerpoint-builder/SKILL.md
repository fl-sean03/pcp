---
name: powerpoint-builder
description: PowerPoint, PPTX, presentation, slides, deck, python-pptx, create presentation, build deck
triggers:
  - powerpoint
  - pptx
  - presentation
  - slides
  - deck
  - slide deck
requires:
  bins: []
  env: []
  pip:
    - python-pptx
    - Pillow
    - pyyaml
  scripts:
    - build_deck.py
    - theme.py
    - layouts.py
    - geometry.py
os:
  - linux
  - darwin
---

# PowerPoint Builder

Build polished, human-looking PowerPoint decks with `python-pptx`. No PowerPoint installation required.

## Quick Start

```bash
# Install dependency (if not present)
pip install python-pptx

# Build a deck from a plan
python build_deck.py --plan deck_plan.yaml --output presentation.pptx

# With custom template
python build_deck.py --plan deck_plan.yaml --template brand_template.pptx --output deck.pptx
```

## When the User Says...

| User Says | Action |
|-----------|--------|
| "Create a presentation about X" | 1. Create `deck_plan.yaml` with outline, 2. Gather assets, 3. Run `build_deck.py` |
| "Make slides for my meeting" | Ask for key points, create plan, build deck |
| "Turn this into a PowerPoint" | Extract assertions from content, create plan, build |
| "I need a deck for [topic]" | Create assertion-based outline first, then build |
| "Add a slide about X" | Use `layouts.py` functions directly |

## Mission

Generate `.pptx` files that look like a thoughtful human made them:
- Clear hierarchy and intentional layout
- Consistent visual system (not default templates)
- Zero "AI smell" (generic structure, filler icons, repetitive wording)
- Deterministic, reproducible generation

---

## Required Inputs

### 1. Deck Plan (`deck_plan.yaml`)

```yaml
title: "Q1 Product Review"
subtitle: "January 2026"
author: "User"

slides:
  - type: title
    title: "Q1 Product Review"
    subtitle: "Performance & Roadmap"

  - type: section
    title: "Performance Metrics"

  - type: key_number
    title: "Revenue exceeded target by 23%"
    number: "$4.2M"
    qualifier: "vs $3.4M target"
    note: "Driven by enterprise expansion"

  - type: figure
    title: "Monthly revenue trend shows sustained growth"
    image: "assets/figures/revenue_chart.png"
    caption: "Source: Finance dashboard"

  - type: bullets
    title: "Three factors drove Q1 success"
    bullets:
      - "Enterprise deals closed 2 weeks faster"
      - "Churn reduced to 2.1% (from 3.4%)"
      - "New pricing increased ARPU 15%"
    note: "Speaker note: Emphasize the churn improvement"

  - type: comparison
    title: "New approach outperformed legacy system"
    left:
      header: "Legacy"
      points: ["Manual process", "3-day turnaround", "40% error rate"]
    right:
      header: "New System"
      points: ["Automated", "Real-time", "2% error rate"]
    verdict: "Migration complete by EOQ"

  - type: figure_with_text
    title: "Architecture scales horizontally"
    image: "assets/figures/architecture.png"
    bullets:
      - "Redis caching layer"
      - "Auto-scaling workers"
      - "Multi-region failover"
    side: "right"
```

### 2. Assets Directory

```
assets/
├── figures/           # Charts, diagrams (PNG preferred)
│   ├── revenue_chart.png
│   └── architecture.png
├── tables/            # CSV or pre-rendered images
│   └── metrics.csv
└── icons/             # Optional, curated style only
    └── logo.png
```

### 3. Optional: Template (`template.pptx`)

Using a real template is **strongly preferred**:
- Consistent branding (fonts, colors, logo placement)
- Pre-defined slide layouts with placeholders
- Master slide handles footers/page numbers

---

## Outputs

| File | Purpose |
|------|---------|
| `deck.pptx` | Final presentation |
| `assets_manifest.json` | Slide# to assets mapping |
| `build_log.txt` | Warnings: missing assets, overflow risks |

---

## Avoiding AI Smell

### What Makes a Deck Look AI-Generated (Avoid These)

| Problem | Fix |
|---------|-----|
| Same layout every slide | Vary: figure-first, split, comparison, key-number |
| Default Office template | Use custom template or explicit theme tokens |
| Vague headers: "Introduction", "Benefits" | **Assertion titles**: "X improves Y by Z" |
| Essay-like bullets | Short, parallel statements |
| Decorative icons with no info value | Real figures only, or nothing |
| Overcrowded slides, tiny fonts | Split slides, move detail to speaker notes |

### Good vs Bad Titles

| Bad (Generic) | Good (Assertion) |
|---------------|------------------|
| "Performance" | "Response time improved 40% after Redis migration" |
| "Problem" | "Current system fails under 1000+ concurrent users" |
| "Solution" | "Horizontal scaling eliminates single-point bottleneck" |
| "Next Steps" | "Three actions required before March launch" |

---

## Slide Types

The builder supports these layout types:

| Type | Function | Use For |
|------|----------|---------|
| `title` | `add_title_slide()` | Opening slide |
| `section` | `add_section_divider()` | Section breaks |
| `bullets` | `add_bullets_slide()` | Key points (max 5 bullets) |
| `figure` | `add_figure_slide()` | Full image with caption |
| `figure_with_text` | `add_figure_with_text_slide()` | Image + bullets side by side |
| `comparison` | `add_comparison_slide()` | Before/after, A vs B |
| `table` | `add_table_slide()` | Data tables |
| `key_number` | `add_key_number_slide()` | Hero metric with context |
| `process` | `add_process_slide()` | Step-by-step flow |

---

## Python API

### Basic Usage

```python
from build_deck import DeckBuilder

# Create deck from plan
builder = DeckBuilder(template="template.pptx")
builder.load_plan("deck_plan.yaml")
builder.build()
builder.save("output/deck.pptx")
```

### Direct Slide Creation

```python
from pptx import Presentation
from layouts import (
    add_title_slide,
    add_bullets_slide,
    add_figure_slide,
    add_key_number_slide
)
from theme import PCPTheme

prs = Presentation()
theme = PCPTheme()

add_title_slide(prs, theme, "Q1 Review", "January 2026")

add_key_number_slide(
    prs, theme,
    title="Revenue exceeded expectations",
    number="$4.2M",
    qualifier="23% above target"
)

add_bullets_slide(
    prs, theme,
    title="Three key drivers",
    bullets=[
        "Enterprise deals closed faster",
        "Churn reduced to 2.1%",
        "ARPU increased 15%"
    ]
)

add_figure_slide(
    prs, theme,
    title="Revenue trend shows sustained growth",
    image_path="assets/figures/revenue.png"
)

prs.save("deck.pptx")
```

---

## CLI Commands

```bash
# Build from plan (recommended)
python build_deck.py --plan deck_plan.yaml --output deck.pptx

# With template
python build_deck.py --plan deck_plan.yaml --template brand.pptx --output deck.pptx

# Dry run (validate only)
python build_deck.py --plan deck_plan.yaml --dry-run

# List available layouts
python build_deck.py --list-layouts

# Validate plan file
python build_deck.py --validate deck_plan.yaml
```

---

## Quality Checks (Automated)

The builder automatically checks:

| Check | Action if Failed |
|-------|------------------|
| Missing asset | Log warning, leave placeholder |
| Text overflow risk | Log warning with slide number |
| Font not available | Fall back to system font, log |
| Image distortion | Refuse to distort, fit with letterbox |
| Inconsistent title position | Log warning |

---

## Integration with PCP

### From Vault Data

```python
from vault_v2 import get_project_context
from build_deck import create_project_deck

# Generate deck from project context
context = get_project_context(project_id=1)
create_project_deck(
    context,
    output="project_review.pptx",
    slide_types=["status", "metrics", "timeline", "risks"]
)
```

### From Brief Data

```python
from brief import generate_brief
from build_deck import create_brief_deck

# Turn a weekly brief into slides
brief_data = generate_brief("weekly")
create_brief_deck(brief_data, output="weekly_review.pptx")
```

---

## Workflow Summary

```
1. Define outline (deck_plan.yaml)
   - Assertion titles
   - Slide types
   - Asset paths

2. Gather assets
   - Charts as PNG
   - Tables as CSV or images
   - No decorative icons

3. Build deck
   python build_deck.py --plan deck_plan.yaml --output deck.pptx

4. Review build_log.txt
   - Fix any warnings
   - Rebuild if needed

5. Final manual check
   - Open in PowerPoint/Slides
   - Verify alignment, readability
```

---

## Project Structure

```
project/
├── deck_plan.yaml          # Slide outline
├── template.pptx           # Brand template (optional)
├── assets/
│   ├── figures/
│   ├── tables/
│   └── icons/
└── output/
    ├── deck.pptx
    ├── assets_manifest.json
    └── build_log.txt
```

---

## Dependencies

```bash
pip install python-pptx Pillow pyyaml
```

| Package | Purpose |
|---------|---------|
| `python-pptx` | PowerPoint generation |
| `Pillow` | Image handling |
| `pyyaml` | Plan file parsing |

---

## Related Skills

- **task-delegation** - Delegate deck creation to background worker
- **vault-operations** - Pull project data for slides
- **brief-generation** - Generate review decks from briefs

---

## References

- [python-pptx Documentation](https://python-pptx.readthedocs.io/)
- [python-pptx GitHub](https://github.com/scanny/python-pptx)
