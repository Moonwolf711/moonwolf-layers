"""
Level complete state — shows grade, score, XP earned, and waits for the player
to advance to the next level.

Transitions:
    -> "LEVEL_INTRO" when SPACE/TRIGGER is pressed (advances to next level).
    -> "MAIN_MENU" on ESC (saves profile).
"""

import math
import time
import pygame

from src.states.base import GameState
from src.data.constants import (
    WIDTH, HEIGHT,
    C_BG, C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW,
    C_STAR_GOLD, C_ENEMY, C_HUD, C_HUD_DIM,
)


class LevelCompleteState(GameState):

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def enter(self):
        self.game.state_timer = 0

    def exit(self):
        pass

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event):
        game = self.game

        if event.type != pygame.KEYDOWN:
            return None

        if event.key == pygame.K_ESCAPE:
            import save_system
            if game.profile:
                save_system.save_profile(game.profile)
            return "MAIN_MENU"

        if event.key == pygame.K_SPACE:
            game._next_level()
            return "LEVEL_INTRO"

        return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt):
        game = self.game

        # Keep particles alive during the results screen
        game.particles.update(dt)
        game.popups.update(dt)

        # Beat tracking for background animation
        game.beat_timer += dt
        if game.beat_timer >= game.beat_interval:
            game.beat_timer -= game.beat_interval
            game.beat_flash = 1.0
        game.beat_flash *= 0.85

        # Joystick buttons
        if game.joystick:
            for i in range(min(game.joystick.get_numbuttons(), 16)):
                if game.joystick.get_button(i):
                    if i == 0:
                        game._next_level()
                        return "LEVEL_INTRO"

        return None

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, screen):
        game = self.game

        from src.rendering.skyline import draw_skyline

        screen.fill(C_BG)

        # Draw skyline behind
        draw_skyline(screen, game.skyline, int(game.camera_x), HEIGHT - 170, game.beat_flash)

        # Particles still render
        game.particles.draw(screen)

        cx, cy = WIDTH // 2, HEIGHT // 2

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 180))
        screen.blit(overlay, (0, 0))

        title = game.font_title.render("LEVEL COMPLETE!", True, C_NEON_GREEN)
        screen.blit(title, (cx - title.get_width() // 2, cy - 120))

        pct = (game.hits / max(1, game.total_targets)) * 100
        grade, grade_color = game._get_grade(pct)

        # Big grade letter
        grade_font = pygame.font.SysFont("consolas", 72)
        grade_surf = grade_font.render(grade, True, grade_color)
        # Pulsing glow
        pulse = 0.7 + 0.3 * math.sin(time.time() * 3)
        glow = pygame.Surface(
            (grade_surf.get_width() + 40, grade_surf.get_height() + 40), pygame.SRCALPHA,
        )
        pygame.draw.circle(
            glow, (*grade_color, int(40 * pulse)),
            (glow.get_width() // 2, glow.get_height() // 2), glow.get_width() // 2,
        )
        screen.blit(glow, (cx + 120 - glow.get_width() // 2, cy - 40 - glow.get_height() // 2))
        screen.blit(grade_surf, (cx + 120 - grade_surf.get_width() // 2, cy - 40 - grade_surf.get_height() // 2))

        stats = [
            (f"Accuracy: {pct:.0f}%", C_HUD),
            (f"Score: {game.score:,}", C_NEON_CYAN),
            (f"Max Combo: {game.max_combo}x", C_NEON_PINK),
            (f"Hits: {game.hits}/{game.total_targets}", C_HUD_DIM),
        ]

        # XP results
        if game.xp_result:
            stats.append((f"+{game.xp_result['xp_earned']} XP", C_STAR_GOLD))
            if game.xp_result['leveled_up']:
                stats.append((f"LEVEL UP! Lv.{game.xp_result['new_level']}", C_NEON_GREEN))
                for unlock in game.xp_result.get('new_unlocks', []):
                    stats.append((f"Unlocked: {unlock}", C_NEON_YELLOW))

        for i, (s, color) in enumerate(stats):
            surf = game.font_big.render(s, True, color)
            screen.blit(surf, (cx - 160, cy - 60 + i * 28))

        loop_msg = "Clip recorded! Set to LOOP in Ableton. Arm next track. Press TRIGGER / SPACE"
        pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
        go = game.font.render(loop_msg, True, (int(255 * pulse), int(200 * pulse), 0))
        screen.blit(go, (cx - go.get_width() // 2, cy + 100))
