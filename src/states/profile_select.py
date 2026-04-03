"""
Profile selection state — lets the player choose an existing profile or create
a new one (name entry followed by animal selection).

Transitions:
    -> "MAIN_MENU" when a profile is selected or created.
"""

import math
import time
import pygame

from src.states.base import GameState
from src.data.constants import (
    WIDTH, HEIGHT,
    C_BG, C_NEON_CYAN, C_NEON_GREEN, C_STAR_GOLD, C_HUD, C_HUD_DIM,
    C_GROUND_TOP,
)


class ProfileSelectState(GameState):

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def enter(self):
        pass

    def exit(self):
        pass

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event):
        """Handle keyboard input on the profile select screen.

        Returns "MAIN_MENU" when a profile is selected/created, or None.
        """
        if event.type != pygame.KEYDOWN:
            return None

        game = self.game

        # ESC handling
        if event.key == pygame.K_ESCAPE:
            if game.profile_naming or game.profile_animal_step:
                game.profile_naming = False
                game.profile_animal_step = False
                game.profile_name_buf = ""
                return None
            # Signal quit — caller should interpret this
            return "QUIT"

        return self._handle_profile_input(event)

    def _handle_profile_input(self, event):
        """Core profile keyboard logic extracted from MoonwolfLayers._handle_profile_input."""
        game = self.game
        import save_system

        if game.profile_naming:
            # Typing a name for new profile
            if event.key == pygame.K_RETURN and len(game.profile_name_buf.strip()) > 0:
                # Move to animal selection step
                game.profile_naming = False
                game.profile_animal_step = True
                game.profile_animal_idx = 0
            elif event.key == pygame.K_BACKSPACE:
                game.profile_name_buf = game.profile_name_buf[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(game.profile_name_buf) < 16:
                    game.profile_name_buf += ch
            return None

        if game.profile_animal_step:
            # Choosing animal base for new profile
            if event.key == pygame.K_LEFT:
                game.profile_animal_idx = (game.profile_animal_idx - 1) % len(game.CHARACTERS)
            elif event.key == pygame.K_RIGHT:
                game.profile_animal_idx = (game.profile_animal_idx + 1) % len(game.CHARACTERS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                animal = game.CHARACTERS[game.profile_animal_idx]["animal"]
                name = game.profile_name_buf.strip()
                game.profile = save_system.new_profile(name, animal)
                save_system.save_profile(game.profile)
                game.profile_palette_name = "default"
                game.profile_animal_step = False
                game.profile_name_buf = ""
                game.profile_list = save_system.list_profiles()
                game.menu_selection = 0
                return "MAIN_MENU"
            return None

        # Normal profile list navigation
        total = len(game.profile_list) + 1  # +1 for NEW PROFILE
        if event.key == pygame.K_UP:
            game.profile_cursor = (game.profile_cursor - 1) % total
        elif event.key == pygame.K_DOWN:
            game.profile_cursor = (game.profile_cursor + 1) % total
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if game.profile_cursor < len(game.profile_list):
                # Select existing profile
                game.profile = game.profile_list[game.profile_cursor]
                game.profile_palette_name = game.profile.get("color_palette", "default")
                game.menu_selection = 0
                return "MAIN_MENU"
            else:
                # New profile — start naming
                game.profile_naming = True
                game.profile_name_buf = ""

        return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt):
        return None

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, screen):
        """Draw the profile selection / creation screen."""
        game = self.game

        screen.fill(C_BG)

        # Animated skyline — uses the game helper that lives in the main module
        from src.rendering.skyline import draw_skyline
        from src.rendering.sprites import make_sprite
        draw_skyline(screen, game.skyline, int(time.time() * 15), HEIGHT - 170)
        pygame.draw.line(screen, C_GROUND_TOP, (0, HEIGHT - 170), (WIDTH, HEIGHT - 170), 2)

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 120))
        screen.blit(overlay, (0, 0))

        cx = WIDTH // 2

        # Title
        pulse = 0.7 + 0.3 * math.sin(time.time() * 2)
        title = game.font_huge.render(
            "MOONWOLF LAYERS", True,
            (int(C_NEON_CYAN[0] * pulse), int(C_NEON_CYAN[1] * pulse), int(C_NEON_CYAN[2] * pulse)),
        )
        screen.blit(title, (cx - title.get_width() // 2, 30))

        sub = game.font_big.render("SELECT PROFILE", True, C_HUD)
        screen.blit(sub, (cx - sub.get_width() // 2, 90))

        # ---- Name entry sub-screen ----
        if game.profile_naming:
            prompt = game.font_big.render("Enter your name:", True, C_NEON_CYAN)
            screen.blit(prompt, (cx - prompt.get_width() // 2, 180))
            # Blinking cursor
            cursor_ch = "_" if int(time.time() * 3) % 2 == 0 else " "
            name_text = game.profile_name_buf + cursor_ch
            name_surf = game.font_title.render(name_text, True, C_STAR_GOLD)
            screen.blit(name_surf, (cx - name_surf.get_width() // 2, 230))
            hint = game.font.render("Type a name (max 16 chars) then press ENTER", True, C_HUD_DIM)
            screen.blit(hint, (cx - hint.get_width() // 2, 300))
            return

        # ---- Animal selection sub-screen ----
        if game.profile_animal_step:
            prompt = game.font_big.render(f"Choose your animal, {game.profile_name_buf}!", True, C_NEON_CYAN)
            screen.blit(prompt, (cx - prompt.get_width() // 2, 150))
            ch = game.CHARACTERS[game.profile_animal_idx]
            preview = make_sprite(ch["sprite"], ch["palette"], 6)
            screen.blit(preview, (cx - preview.get_width() // 2, 200))
            name_s = game.font_title.render(f"< {ch['name']} >", True, ch['color'])
            screen.blit(name_s, (cx - name_s.get_width() // 2, 420))
            ability_s = game.font_menu.render(ch['ability'], True, C_HUD_DIM)
            screen.blit(ability_s, (cx - ability_s.get_width() // 2, 465))
            hint = game.font.render("LEFT/RIGHT to browse, ENTER to confirm", True, C_HUD_DIM)
            screen.blit(hint, (cx - hint.get_width() // 2, 500))
            return

        # ---- Profile list ----
        import save_system

        list_x = cx - 200
        list_y_start = 130
        item_h = 50
        total = len(game.profile_list) + 1

        for i in range(total):
            y = list_y_start + i * item_h
            if y > HEIGHT - 100:
                break  # Don't draw off screen
            selected = (i == game.profile_cursor)
            if selected:
                sel_bar = pygame.Surface((400, item_h - 4), pygame.SRCALPHA)
                sel_bar.fill((*C_NEON_CYAN, 25))
                screen.blit(sel_bar, (list_x, y))
                arrow = game.font_big.render(">", True, C_NEON_CYAN)
                screen.blit(arrow, (list_x - 25, y + 8))

            if i < len(game.profile_list):
                p = game.profile_list[i]
                name_color = C_NEON_CYAN if selected else C_HUD
                name_s = game.font_big.render(p["name"], True, name_color)
                screen.blit(name_s, (list_x + 10, y + 2))
                level, xp_into, xp_needed = save_system.xp_progress(p.get("xp", 0))
                detail = f"Lv.{level} | {p.get('animal_base', 'wolf')} | XP: {p.get('xp', 0)}"
                detail_s = game.font.render(detail, True, (120, 120, 140))
                screen.blit(detail_s, (list_x + 10, y + 28))
                # Mini XP bar
                bar_w, bar_h = 100, 4
                bar_x = list_x + 300
                bar_y_pos = y + 14
                pygame.draw.rect(screen, (30, 25, 50), (bar_x, bar_y_pos, bar_w, bar_h))
                fill = int(bar_w * xp_into / max(1, xp_needed))
                pygame.draw.rect(screen, C_NEON_CYAN, (bar_x, bar_y_pos, fill, bar_h))
            else:
                # NEW PROFILE option
                new_color = C_NEON_GREEN if selected else C_HUD_DIM
                new_s = game.font_big.render("+ NEW PROFILE", True, new_color)
                screen.blit(new_s, (list_x + 10, y + 8))

        hint = game.font.render("UP/DOWN to select, ENTER to confirm, ESC to quit", True, C_HUD_DIM)
        screen.blit(hint, (cx - hint.get_width() // 2, HEIGHT - 40))
