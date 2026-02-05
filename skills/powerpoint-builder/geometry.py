#!/usr/bin/env python3
"""
Geometry Helpers for PowerPoint Slides

Positioning, scaling, and layout utilities.
All calculations maintain aspect ratios and alignment.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Literal
from pptx.util import Inches, Emu
from PIL import Image
import os


@dataclass
class Box:
    """A rectangular area on a slide."""
    left: Inches
    top: Inches
    width: Inches
    height: Inches

    @property
    def right(self) -> Inches:
        return Inches(self.left.inches + self.width.inches)

    @property
    def bottom(self) -> Inches:
        return Inches(self.top.inches + self.height.inches)

    @property
    def center_x(self) -> Inches:
        return Inches(self.left.inches + self.width.inches / 2)

    @property
    def center_y(self) -> Inches:
        return Inches(self.top.inches + self.height.inches / 2)


def get_image_size(image_path: str) -> Tuple[int, int]:
    """Get image dimensions in pixels."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(image_path) as img:
        return img.size  # (width, height)


def get_image_aspect_ratio(image_path: str) -> float:
    """Get image aspect ratio (width / height)."""
    width, height = get_image_size(image_path)
    return width / height


def fit_image(
    image_path: str,
    max_width: Inches,
    max_height: Inches,
    mode: Literal["contain", "cover"] = "contain"
) -> Tuple[Inches, Inches]:
    """
    Calculate dimensions to fit image in container.

    Args:
        image_path: Path to image file
        max_width: Maximum width
        max_height: Maximum height
        mode: "contain" (letterbox) or "cover" (fill, may crop)

    Returns:
        (width, height) tuple of calculated dimensions
    """
    aspect = get_image_aspect_ratio(image_path)
    container_aspect = max_width.inches / max_height.inches

    if mode == "contain":
        # Fit entire image within container
        if aspect > container_aspect:
            # Image is wider - constrain by width
            width = max_width.inches
            height = width / aspect
        else:
            # Image is taller - constrain by height
            height = max_height.inches
            width = height * aspect
    else:  # cover
        # Fill container, image may overflow
        if aspect > container_aspect:
            # Image is wider - constrain by height
            height = max_height.inches
            width = height * aspect
        else:
            # Image is taller - constrain by width
            width = max_width.inches
            height = width / aspect

    return Inches(width), Inches(height)


def center_in_box(
    content_width: Inches,
    content_height: Inches,
    container: Box
) -> Tuple[Inches, Inches]:
    """
    Calculate position to center content in container.

    Returns:
        (left, top) position tuple
    """
    left = container.left.inches + (container.width.inches - content_width.inches) / 2
    top = container.top.inches + (container.height.inches - content_height.inches) / 2
    return Inches(left), Inches(top)


def align_in_box(
    content_width: Inches,
    content_height: Inches,
    container: Box,
    h_align: Literal["left", "center", "right"] = "center",
    v_align: Literal["top", "center", "bottom"] = "center"
) -> Tuple[Inches, Inches]:
    """
    Calculate position to align content in container.

    Returns:
        (left, top) position tuple
    """
    # Horizontal alignment
    if h_align == "left":
        left = container.left.inches
    elif h_align == "right":
        left = container.right.inches - content_width.inches
    else:  # center
        left = container.left.inches + (container.width.inches - content_width.inches) / 2

    # Vertical alignment
    if v_align == "top":
        top = container.top.inches
    elif v_align == "bottom":
        top = container.bottom.inches - content_height.inches
    else:  # center
        top = container.top.inches + (container.height.inches - content_height.inches) / 2

    return Inches(left), Inches(top)


def split_horizontal(
    container: Box,
    ratio: float = 0.5,
    gutter: Inches = Inches(0.5)
) -> Tuple[Box, Box]:
    """
    Split a box horizontally into two boxes.

    Args:
        container: Box to split
        ratio: Ratio for left side (0.0-1.0)
        gutter: Space between boxes

    Returns:
        (left_box, right_box) tuple
    """
    available_width = container.width.inches - gutter.inches
    left_width = available_width * ratio
    right_width = available_width * (1 - ratio)

    left_box = Box(
        left=container.left,
        top=container.top,
        width=Inches(left_width),
        height=container.height
    )

    right_box = Box(
        left=Inches(container.left.inches + left_width + gutter.inches),
        top=container.top,
        width=Inches(right_width),
        height=container.height
    )

    return left_box, right_box


def split_vertical(
    container: Box,
    ratio: float = 0.5,
    gutter: Inches = Inches(0.25)
) -> Tuple[Box, Box]:
    """
    Split a box vertically into two boxes.

    Args:
        container: Box to split
        ratio: Ratio for top side (0.0-1.0)
        gutter: Space between boxes

    Returns:
        (top_box, bottom_box) tuple
    """
    available_height = container.height.inches - gutter.inches
    top_height = available_height * ratio
    bottom_height = available_height * (1 - ratio)

    top_box = Box(
        left=container.left,
        top=container.top,
        width=container.width,
        height=Inches(top_height)
    )

    bottom_box = Box(
        left=container.left,
        top=Inches(container.top.inches + top_height + gutter.inches),
        width=container.width,
        height=Inches(bottom_height)
    )

    return top_box, bottom_box


def estimate_text_height(
    text: str,
    width: Inches,
    font_size_pt: float,
    line_spacing: float = 1.2
) -> Inches:
    """
    Estimate text block height (rough approximation).

    This is a heuristic - actual height depends on font metrics.
    """
    # Average characters per inch at given font size
    chars_per_inch = 72 / font_size_pt * 6  # Rough estimate
    chars_per_line = width.inches * chars_per_inch

    # Estimate number of lines
    num_lines = max(1, len(text) / chars_per_line)

    # Height per line (font size + line spacing)
    line_height_inches = (font_size_pt / 72) * line_spacing

    return Inches(num_lines * line_height_inches)


def check_text_overflow(
    text: str,
    container: Box,
    font_size_pt: float = 18,
    line_spacing: float = 1.2
) -> bool:
    """
    Check if text would overflow container.

    Returns True if overflow likely.
    """
    estimated_height = estimate_text_height(text, container.width, font_size_pt, line_spacing)
    return estimated_height.inches > container.height.inches


def grid_positions(
    container: Box,
    rows: int,
    cols: int,
    h_gutter: Inches = Inches(0.25),
    v_gutter: Inches = Inches(0.25)
) -> list:
    """
    Calculate grid cell positions within container.

    Returns:
        List of Box objects for each cell (row-major order)
    """
    cell_width = (container.width.inches - h_gutter.inches * (cols - 1)) / cols
    cell_height = (container.height.inches - v_gutter.inches * (rows - 1)) / rows

    cells = []
    for row in range(rows):
        for col in range(cols):
            cell = Box(
                left=Inches(container.left.inches + col * (cell_width + h_gutter.inches)),
                top=Inches(container.top.inches + row * (cell_height + v_gutter.inches)),
                width=Inches(cell_width),
                height=Inches(cell_height)
            )
            cells.append(cell)

    return cells


if __name__ == "__main__":
    # Demo geometry calculations
    from theme import get_theme

    theme = get_theme()
    g = theme.geometry

    print("Slide Geometry Demo")
    print("=" * 40)

    # Create content area box
    content = Box(
        left=g.margin_left,
        top=g.body_top,
        width=g.content_width,
        height=Inches(g.slide_height.inches - g.body_top.inches - g.margin_bottom.inches)
    )

    print(f"Content area: {content.width.inches:.2f}\" x {content.height.inches:.2f}\"")

    # Split for two-column layout
    left, right = split_horizontal(content, ratio=0.5, gutter=g.gutter)
    print(f"Left column: {left.width.inches:.2f}\" x {left.height.inches:.2f}\"")
    print(f"Right column: {right.width.inches:.2f}\" x {right.height.inches:.2f}\"")
