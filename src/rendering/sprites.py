"""
Moonwolf Layers — Sprite rendering from pixel-art strings.
Extracted from moonwolf_layers.py for modular import.
"""

import pygame


def make_sprite(pixels, palette, scale=3):
    """Render a pixel-art string into a pygame Surface using the given palette.

    Args:
        pixels: Multi-line string where each character maps to a palette color.
        palette: Dict mapping single characters to RGB tuples (or None for transparent).
        scale: Pixel scale factor (default 3).

    Returns:
        pygame.Surface with SRCALPHA transparency.
    """
    lines = [l for l in pixels.strip().split('\n') if l.strip()]
    h = len(lines)
    w = max(len(l) for l in lines)
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch in palette and palette[ch] is not None:
                pygame.draw.rect(surf, palette[ch], (x*scale, y*scale, scale, scale))
    return surf
