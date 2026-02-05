#!/usr/bin/env python3
"""
PowerPoint Theme Tokens

Centralized design system for consistent deck generation.
All measurements, colors, and typography defined here.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


@dataclass
class ColorPalette:
    """Color tokens for the deck."""
    primary: RGBColor = field(default_factory=lambda: RGBColor(0x1A, 0x1A, 0x2E))      # Dark navy
    secondary: RGBColor = field(default_factory=lambda: RGBColor(0x16, 0x21, 0x3E))    # Darker navy
    accent: RGBColor = field(default_factory=lambda: RGBColor(0x0F, 0x4C, 0x81))       # Blue
    highlight: RGBColor = field(default_factory=lambda: RGBColor(0xE9, 0x4D, 0x4D))    # Red accent

    text_primary: RGBColor = field(default_factory=lambda: RGBColor(0x1A, 0x1A, 0x1A))  # Near black
    text_secondary: RGBColor = field(default_factory=lambda: RGBColor(0x4A, 0x4A, 0x4A)) # Dark gray
    text_muted: RGBColor = field(default_factory=lambda: RGBColor(0x7A, 0x7A, 0x7A))    # Medium gray
    text_inverse: RGBColor = field(default_factory=lambda: RGBColor(0xFF, 0xFF, 0xFF))  # White

    background: RGBColor = field(default_factory=lambda: RGBColor(0xFF, 0xFF, 0xFF))    # White
    background_alt: RGBColor = field(default_factory=lambda: RGBColor(0xF5, 0xF5, 0xF5)) # Light gray

    success: RGBColor = field(default_factory=lambda: RGBColor(0x27, 0xAE, 0x60))       # Green
    warning: RGBColor = field(default_factory=lambda: RGBColor(0xF3, 0x9C, 0x12))       # Orange
    error: RGBColor = field(default_factory=lambda: RGBColor(0xE7, 0x4C, 0x3C))         # Red


@dataclass
class Typography:
    """Font settings."""
    title_font: str = "Calibri"
    body_font: str = "Calibri"
    mono_font: str = "Consolas"

    # Font sizes
    title_size: Pt = field(default_factory=lambda: Pt(44))
    subtitle_size: Pt = field(default_factory=lambda: Pt(24))
    section_size: Pt = field(default_factory=lambda: Pt(36))
    heading_size: Pt = field(default_factory=lambda: Pt(28))
    body_size: Pt = field(default_factory=lambda: Pt(18))
    caption_size: Pt = field(default_factory=lambda: Pt(12))
    key_number_size: Pt = field(default_factory=lambda: Pt(72))

    # Line spacing (multiplier)
    line_spacing: float = 1.2
    paragraph_spacing_before: Pt = field(default_factory=lambda: Pt(6))
    paragraph_spacing_after: Pt = field(default_factory=lambda: Pt(6))


@dataclass
class Geometry:
    """Slide geometry and spacing."""
    # Standard slide size (16:9)
    slide_width: Inches = field(default_factory=lambda: Inches(13.333))
    slide_height: Inches = field(default_factory=lambda: Inches(7.5))

    # Margins
    margin_left: Inches = field(default_factory=lambda: Inches(0.75))
    margin_right: Inches = field(default_factory=lambda: Inches(0.75))
    margin_top: Inches = field(default_factory=lambda: Inches(0.75))
    margin_bottom: Inches = field(default_factory=lambda: Inches(0.5))

    # Content area
    @property
    def content_width(self) -> Inches:
        return Inches(self.slide_width.inches - self.margin_left.inches - self.margin_right.inches)

    @property
    def content_height(self) -> Inches:
        return Inches(self.slide_height.inches - self.margin_top.inches - self.margin_bottom.inches)

    # Title positioning
    title_top: Inches = field(default_factory=lambda: Inches(0.5))
    title_height: Inches = field(default_factory=lambda: Inches(1.0))

    # Body area (below title)
    body_top: Inches = field(default_factory=lambda: Inches(1.6))

    # Gutters
    gutter: Inches = field(default_factory=lambda: Inches(0.5))

    # Two-column layout
    @property
    def column_width(self) -> Inches:
        return Inches((self.content_width.inches - self.gutter.inches) / 2)


@dataclass
class PCPTheme:
    """Complete theme configuration."""
    colors: ColorPalette = field(default_factory=ColorPalette)
    typography: Typography = field(default_factory=Typography)
    geometry: Geometry = field(default_factory=Geometry)

    # Alignment preferences
    title_align: PP_ALIGN = PP_ALIGN.LEFT
    body_align: PP_ALIGN = PP_ALIGN.LEFT

    # Max bullets per slide (for quality)
    max_bullets: int = 5

    # Image quality settings
    min_image_dpi: int = 150
    prefer_png: bool = True


# Preset themes
THEMES = {
    "default": PCPTheme(),

    "dark": PCPTheme(
        colors=ColorPalette(
            background=RGBColor(0x1A, 0x1A, 0x2E),
            text_primary=RGBColor(0xFF, 0xFF, 0xFF),
            text_secondary=RGBColor(0xCC, 0xCC, 0xCC),
        )
    ),

    "minimal": PCPTheme(
        colors=ColorPalette(
            primary=RGBColor(0x00, 0x00, 0x00),
            accent=RGBColor(0x00, 0x00, 0x00),
        ),
        typography=Typography(
            title_font="Arial",
            body_font="Arial",
        )
    ),
}


def get_theme(name: str = "default") -> PCPTheme:
    """Get a theme by name."""
    return THEMES.get(name, THEMES["default"])


def apply_text_style(
    paragraph,
    theme: PCPTheme,
    font_size: Optional[Pt] = None,
    color: Optional[RGBColor] = None,
    bold: bool = False,
    italic: bool = False
):
    """Apply consistent text styling to a paragraph."""
    font = paragraph.font
    font.name = theme.typography.body_font
    font.size = font_size or theme.typography.body_size
    font.color.rgb = color or theme.colors.text_primary
    font.bold = bold
    font.italic = italic


def apply_title_style(paragraph, theme: PCPTheme):
    """Apply title styling."""
    apply_text_style(
        paragraph,
        theme,
        font_size=theme.typography.heading_size,
        color=theme.colors.text_primary,
        bold=True
    )
    paragraph.alignment = theme.title_align


if __name__ == "__main__":
    # Print theme info
    theme = get_theme()
    print("PCP PowerPoint Theme")
    print("=" * 40)
    print(f"Title font: {theme.typography.title_font} @ {theme.typography.title_size.pt}pt")
    print(f"Body font: {theme.typography.body_font} @ {theme.typography.body_size.pt}pt")
    print(f"Slide size: {theme.geometry.slide_width.inches}\" x {theme.geometry.slide_height.inches}\"")
    print(f"Content area: {theme.geometry.content_width.inches}\" x {theme.geometry.content_height.inches}\"")
    print(f"Max bullets: {theme.max_bullets}")
