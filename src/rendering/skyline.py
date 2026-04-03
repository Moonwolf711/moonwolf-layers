"""
Moonwolf Layers — Neon city skyline generation and rendering.
Extracted from moonwolf_layers.py for modular import.
"""

import math
import random
import time

import pygame

from src.data.constants import (
    TILE, WIDTH,
    C_BUILDING, C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW,
)


def generate_skyline(width_tiles=100):
    """Generate a neon city skyline for parallax background."""
    buildings = []
    x = 0
    while x < width_tiles * TILE:
        w = random.randint(30, 80)
        h = random.randint(60, 250)
        has_antenna = random.random() < 0.3
        neon_color = random.choice([C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW, (100, 50, 200)])
        windows = []
        for wy in range(10, h - 10, 14):
            for wx in range(6, w - 6, 12):
                if random.random() < 0.6:
                    lit = random.random() < 0.7
                    windows.append((wx, wy, lit))
        buildings.append({
            'x': x, 'w': w, 'h': h,
            'antenna': has_antenna,
            'neon': neon_color,
            'windows': windows,
            'neon_sign_y': random.randint(20, max(21, h - 40)) if random.random() < 0.2 else -1,
        })
        x += w + random.randint(2, 20)
    return buildings


def draw_skyline(screen, buildings, cam_x, ground_y, beat_flash=0.0):
    """Draw parallax city skyline with optional beat-synced edge glow."""
    for b in buildings:
        sx = int(b['x'] - cam_x * 0.2) % (WIDTH * 3) - WIDTH
        if sx + b['w'] < -20 or sx > WIDTH + 20:
            continue
        by = ground_y - b['h']
        # Building body
        body_color = (random.randint(12, 18), random.randint(10, 16), random.randint(25, 35)) if random.random() < 0.01 else C_BUILDING
        pygame.draw.rect(screen, C_BUILDING, (sx, by, b['w'], b['h']))
        # Edge glow — pulse brighter on beat
        glow_boost = 1.0 + beat_flash * 1.5  # up to 2.5x brightness on beat
        edge_color = tuple(min(255, int(c * glow_boost)) for c in b['neon'][:3])
        edge_width = 1 if beat_flash < 0.3 else 2  # thicker line on strong beats
        pygame.draw.line(screen, edge_color, (sx, by), (sx, by + b['h']), edge_width)
        pygame.draw.line(screen, edge_color, (sx + b['w'], by), (sx + b['w'], by + b['h']), edge_width)
        pygame.draw.line(screen, edge_color, (sx, by), (sx + b['w'], by), edge_width)
        # Windows
        for wx, wy, lit in b['windows']:
            if lit:
                wc = (60, 55, 40)
            else:
                wc = (15, 12, 20)
            pygame.draw.rect(screen, wc, (sx + wx, by + wy, 6, 8))
        # Antenna
        if b['antenna']:
            ax = sx + b['w'] // 2
            pygame.draw.line(screen, (60, 60, 80), (ax, by), (ax, by - 20), 1)
            blink = 1 if int(time.time() * 2) % 2 == 0 else 0
            if blink:
                pygame.draw.circle(screen, (255, 50, 50), (ax, by - 20), 2)
        # Neon sign
        if b['neon_sign_y'] > 0:
            pulse = 0.6 + 0.4 * math.sin(time.time() * 3 + b['x'] * 0.1)
            nc = tuple(int(c * pulse) for c in b['neon'])
            pygame.draw.rect(screen, nc, (sx + 4, by + b['neon_sign_y'], b['w'] - 8, 6))
