"""
Moonwolf Layers — Particle and hit popup systems.
Extracted from moonwolf_layers.py for modular import.
"""

import math
import random

import pygame

from src.data.constants import C_STAR_GOLD


# ======================== PARTICLES ========================
class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'size')
    def __init__(self, x, y, vx, vy, life, color, size=3):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, count, color, speed=100, life=0.6, size=3, spread=6.28):
        angle_base = -1.57  # up
        for _ in range(count):
            a = angle_base + random.uniform(-spread/2, spread/2)
            s = random.uniform(speed * 0.4, speed)
            self.particles.append(Particle(
                x, y, math.cos(a)*s, math.sin(a)*s,
                life * random.uniform(0.6, 1.0), color, size
            ))

    def emit_fire(self, x, y, intensity=1.0):
        """Trailing fire for combos."""
        for _ in range(int(3 * intensity)):
            self.particles.append(Particle(
                x + random.uniform(-6, 6), y + random.uniform(-4, 4),
                random.uniform(-30, -60), random.uniform(-40, 20),
                random.uniform(0.2, 0.5),
                random.choice([(255,100,0), (255,200,0), (255,60,0), (255,255,100)]),
                random.randint(2, 4)
            ))

    def emit_star(self, x, y):
        """Star power sparkles."""
        for _ in range(2):
            a = random.uniform(0, 6.28)
            s = random.uniform(20, 80)
            self.particles.append(Particle(
                x + random.uniform(-20, 20), y + random.uniform(-20, 20),
                math.cos(a)*s, math.sin(a)*s,
                random.uniform(0.3, 0.8),
                random.choice([C_STAR_GOLD, (255,255,200), (255,200,50)]),
                random.randint(2, 5)
            ))

    def update(self, dt):
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 120 * dt  # gravity
            alive.append(p)
        self.particles = alive

    def draw(self, screen):
        for p in self.particles:
            alpha = p.life / p.max_life
            r, g, b = p.color
            color = (int(r * alpha), int(g * alpha), int(b * alpha))
            sz = max(1, int(p.size * alpha))
            pygame.draw.rect(screen, color, (int(p.x) - sz//2, int(p.y) - sz//2, sz, sz))


# ======================== HIT POPUP ========================
class HitPopup:
    __slots__ = ('x', 'y', 'text', 'color', 'life', 'max_life')
    def __init__(self, x, y, text, color, life=0.8):
        self.x, self.y = x, y
        self.text, self.color = text, color
        self.life = self.max_life = life


class PopupSystem:
    def __init__(self, font):
        self.popups = []
        self.font = font

    def add(self, x, y, text, color):
        self.popups.append(HitPopup(x, y, text, color))

    def update(self, dt):
        alive = []
        for p in self.popups:
            p.life -= dt
            p.y -= 60 * dt  # float up
            if p.life > 0:
                alive.append(p)
        self.popups = alive

    def draw(self, screen):
        for p in self.popups:
            alpha = p.life / p.max_life
            r, g, b = p.color
            color = (int(r * min(1, alpha * 2)), int(g * min(1, alpha * 2)), int(b * min(1, alpha * 2)))
            scale = 1.0 + (1.0 - alpha) * 0.3
            surf = self.font.render(p.text, True, color)
            if scale > 1.05:
                surf = pygame.transform.scale(surf, (int(surf.get_width() * scale), int(surf.get_height() * scale)))
            screen.blit(surf, (int(p.x) - surf.get_width()//2, int(p.y) - surf.get_height()//2))
