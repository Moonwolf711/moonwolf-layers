"""
Level intro state — shows level name, instrument, controls summary, and waits
for the player to press SPACE/TRIGGER to begin.

Transitions:
    -> "PLAYING" when the player presses SPACE or joystick trigger.
    -> "MAIN_MENU" on ESC.
"""

import math
import time
import pygame

from src.states.base import GameState
from src.data.constants import (
    WIDTH, HEIGHT,
    C_BG, C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN,
    C_STAR_GOLD, C_HUD, C_HUD_DIM, C_GROUND_TOP,
)


class LevelIntroState(GameState):

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
            game._start_level()
            return "PLAYING"

        return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt):
        game = self.game

        # Joystick buttons
        if game.joystick:
            for i in range(min(game.joystick.get_numbuttons(), 16)):
                if game.joystick.get_button(i):
                    if i == 0:
                        game._start_level()
                        return "PLAYING"
                    elif i == 4:
                        game._adjust_bpm(-2)
                    elif i == 5:
                        game._adjust_bpm(2)

        return None

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, screen):
        game = self.game

        from src.rendering.skyline import draw_skyline

        screen.fill(C_BG)

        # Skyline behind intro
        draw_skyline(screen, game.skyline, int(time.time() * 20), HEIGHT - 170)
        # Ground
        pygame.draw.line(screen, C_GROUND_TOP, (0, HEIGHT - 170), (WIDTH, HEIGHT - 170), 2)

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 140))
        screen.blit(overlay, (0, 0))

        cx, cy = WIDTH // 2, HEIGHT // 2

        # Level number with large glow
        level_font = pygame.font.SysFont("consolas", 64)
        level_num = level_font.render(f"{game.current_level + 1}", True, C_NEON_CYAN)
        pulse = 0.6 + 0.4 * math.sin(time.time() * 2)
        glow = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_NEON_CYAN, int(30 * pulse)), (60, 60), 60)
        screen.blit(glow, (cx - 60, cy - 130))
        screen.blit(level_num, (cx - level_num.get_width() // 2, cy - 110))

        # Song name (if from library)
        if game.song_list:
            song = game.song_list[game.song_idx]
            song_title = game.font_menu.render(
                f"{song['artist']} - {song['title']}", True, C_HUD_DIM,
            )
            screen.blit(song_title, (cx - song_title.get_width() // 2, cy - 60))

        # Level name
        title = game.font_title.render(f"{game.level.name}", True, C_NEON_PINK)
        screen.blit(title, (cx - title.get_width() // 2, cy - 40))

        inst = game.font_big.render(
            f"{game.level.instrument_name}  |  {game.bpm} BPM  |  {game.level.bars} bars",
            True, C_HUD,
        )
        screen.blit(inst, (cx - inst.get_width() // 2, cy + 10))

        # Active layers
        if game.locked_levels > 0:
            layer_names = ', '.join(
                game.levels[i].name for i in range(min(game.locked_levels, len(game.levels)))
            )
            loop_text = game.font.render(f"Looping in Ableton: {layer_names}", True, C_NEON_GREEN)
            screen.blit(loop_text, (cx - loop_text.get_width() // 2, cy + 50))

        # Controls
        if game.level.drum_lanes:
            lines = [
                "Fighting Edge: Sq=KICK  X=SNARE  O=HH  Tri=OH  L1=CRASH  R1=RIDE  L2=LTOM  R2=HTOM",
                "Hit drums in time with the scrolling targets!",
            ]
        else:
            lines = [
                "Joystick UP/DOWN = steer through melody notes",
                "Collect the glowing orbs to play the melody!",
            ]
        for i, line in enumerate(lines):
            surf = game.font.render(line, True, C_HUD_DIM)
            screen.blit(surf, (cx - surf.get_width() // 2, cy + 80 + i * 20))

        # Timing guide
        timing_y = cy + 130
        timing_labels = [("PERFECT", C_STAR_GOLD), ("GREAT", C_NEON_GREEN), ("Good", C_HUD)]
        for idx, (label, color) in enumerate(timing_labels):
            surf = game.font.render(f"  {label}  ", True, color)
            screen.blit(surf, (cx - 200 + idx * 140, timing_y))

        pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
        go = game.font_big.render(
            "Press TRIGGER / SPACE to start", True,
            (int(C_NEON_CYAN[0] * pulse), int(C_NEON_CYAN[1] * pulse), int(C_NEON_CYAN[2] * pulse)),
        )
        screen.blit(go, (cx - go.get_width() // 2, cy + 170))
