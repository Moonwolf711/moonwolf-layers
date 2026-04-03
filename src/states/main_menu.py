"""
Main menu state — character selection, song picker, MIDI port, player mode.

Transitions:
    -> "PLAYING" (via LEVEL_INTRO) when START GAME is selected (calls game._init_game()).
    -> "QUIT" on ESC.
"""

import math
import time
import pygame

from src.states.base import GameState
from src.data.constants import (
    WIDTH, HEIGHT,
    C_BG, C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW,
    C_STAR_GOLD, C_ENEMY, C_HUD, C_HUD_DIM, C_GROUND_TOP,
)


# Menu item lists (shared class-level constants)
MENU_ITEMS_2P = [
    "PLAYERS", "SONG", "P1 CHARACTER", "P1 PALETTE", "P1 ROLE",
    "P2 CHARACTER", "P2 ROLE", "MIDI OUTPUT", "START GAME",
]
MENU_ITEMS_1P = [
    "PLAYERS", "SONG", "P1 CHARACTER", "P1 PALETTE", "P1 ROLE",
    "MIDI OUTPUT", "START GAME",
]


class MainMenuState(GameState):

    def __init__(self, game):
        super().__init__(game)
        self.menu_debounce = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _menu_items(self):
        return MENU_ITEMS_2P if self.game.menu_player_mode == 1 else MENU_ITEMS_1P

    def _menu_item_count(self):
        return len(self._menu_items)

    def _menu_adjust(self, direction):
        """Left/Right adjustment on the current menu item."""
        game = self.game
        item = self._menu_items[game.menu_selection]

        from src.rendering.sprites import make_sprite
        from src.data.instruments import INSTRUMENT_ROLES
        import save_system

        if item == "PLAYERS":
            game.menu_player_mode = (game.menu_player_mode + direction) % 2
        elif item == "SONG":
            if game.song_list:
                game.song_idx = (game.song_idx + direction) % len(game.song_list)
            # Clamp selection if menu shrunk
            if game.menu_selection >= self._menu_item_count():
                game.menu_selection = self._menu_item_count() - 1
        elif item == "P1 CHARACTER":
            game.p1_char_idx = (game.p1_char_idx + direction) % len(game.CHARACTERS)
            ch = game.CHARACTERS[game.p1_char_idx]
            pal = save_system.apply_palette_override(ch["palette"], game.profile_palette_name)
            game.p1_sprite = make_sprite(ch["sprite"], pal, 3)
        elif item == "P1 PALETTE":
            # Cycle through unlocked palettes
            level = game.profile["level"] if game.profile else 1
            available = save_system.unlocked_palettes(level)
            if available:
                try:
                    idx = available.index(game.profile_palette_name)
                except ValueError:
                    idx = 0
                idx = (idx + direction) % len(available)
                game.profile_palette_name = available[idx]
                if game.profile:
                    game.profile["color_palette"] = game.profile_palette_name
                # Rebuild P1 sprite with new palette
                ch = game.CHARACTERS[game.p1_char_idx]
                pal = save_system.apply_palette_override(ch["palette"], game.profile_palette_name)
                game.p1_sprite = make_sprite(ch["sprite"], pal, 3)
        elif item == "P2 CHARACTER":
            game.p2_char_idx = (game.p2_char_idx + direction) % len(game.CHARACTERS)
            ch = game.CHARACTERS[game.p2_char_idx]
            game.p2_sprite = make_sprite(ch["sprite"], ch["palette"], 3)
        elif item == "P1 ROLE":
            game.p1_role_idx = (game.p1_role_idx + direction) % len(INSTRUMENT_ROLES)
        elif item == "P2 ROLE":
            game.p2_role_idx = (game.p2_role_idx + direction) % len(INSTRUMENT_ROLES)
        elif item == "MIDI OUTPUT":
            if game.available_midi:
                game.menu_midi_idx = (game.menu_midi_idx + direction) % len(game.available_midi)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def enter(self):
        self.menu_debounce = 0.0
        self.game.detected_controllers = self.game._scan_controllers()
        self.game.available_midi = self.game._scan_midi_ports()

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
            return "QUIT"

        if self.menu_debounce > 0:
            return None

        self.menu_debounce = 0.15

        if event.key == pygame.K_UP:
            game.menu_selection = (game.menu_selection - 1) % self._menu_item_count()
        elif event.key == pygame.K_DOWN:
            game.menu_selection = (game.menu_selection + 1) % self._menu_item_count()
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._menu_adjust(1 if event.key == pygame.K_RIGHT else -1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if game.menu_selection == self._menu_item_count() - 1:
                # START selected — initialize and go to LEVEL_INTRO
                game._init_game()
                return "LEVEL_INTRO"
        elif event.key == pygame.K_F5:
            # Refresh controllers
            game.detected_controllers = game._scan_controllers()
            game.available_midi = game._scan_midi_ports()

        return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt):
        self.menu_debounce = max(0, self.menu_debounce - dt)

        game = self.game

        # Joystick input in menu
        if game.joystick and self.menu_debounce <= 0:
            hat = game.joystick.get_hat(0) if game.joystick.get_numhats() > 0 else (0, 0)
            if hat[1] == 1:  # up
                game.menu_selection = (game.menu_selection - 1) % self._menu_item_count()
                self.menu_debounce = 0.2
            elif hat[1] == -1:  # down
                game.menu_selection = (game.menu_selection + 1) % self._menu_item_count()
                self.menu_debounce = 0.2
            elif hat[0] != 0:
                self._menu_adjust(hat[0])
                self.menu_debounce = 0.2
            if game.joystick.get_button(0):
                if game.menu_selection == self._menu_item_count() - 1:
                    game._init_game()
                    return "LEVEL_INTRO"
                self.menu_debounce = 0.3

        return None

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, screen):
        game = self.game

        from src.rendering.skyline import draw_skyline
        from src.rendering.sprites import make_sprite
        from src.data.instruments import INSTRUMENT_ROLES
        import save_system

        screen.fill(C_BG)

        # Animated skyline
        draw_skyline(screen, game.skyline, int(time.time() * 15), HEIGHT - 170)
        pygame.draw.line(screen, C_GROUND_TOP, (0, HEIGHT - 170), (WIDTH, HEIGHT - 170), 2)

        # Tron grid
        horizon_y = HEIGHT - 230
        ground_y = HEIGHT - 170
        for i in range(12):
            frac = i / 12.0
            y = int(horizon_y + (ground_y - horizon_y) * (frac ** 0.6))
            gs = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
            gs.fill((*C_NEON_CYAN, int(10 + 25 * frac)))
            screen.blit(gs, (0, y))
        vx = WIDTH // 2
        for i in range(-10, 11):
            pygame.draw.line(screen, C_NEON_PINK, (vx + i * 8, horizon_y), (vx + i * 80, ground_y), 1)

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
        screen.blit(title, (cx - title.get_width() // 2, 40))

        # Subtitle
        sub = game.font_menu.render("Layer loops. Build songs. Star Power riffs.", True, C_HUD_DIM)
        screen.blit(sub, (cx - sub.get_width() // 2, 100))

        # Profile info bar
        if game.profile:
            level, xp_into, xp_needed = save_system.xp_progress(game.profile["xp"])
            prof_str = f"{game.profile['name']}  Lv.{level}  XP: {game.profile['xp']}"
            prof_surf = game.font.render(prof_str, True, C_NEON_CYAN)
            screen.blit(prof_surf, (cx - prof_surf.get_width() // 2, 116))
            # Small XP progress bar
            bar_w, bar_h = 200, 6
            bar_x = cx - bar_w // 2
            bar_y = 132
            pygame.draw.rect(screen, (30, 25, 50), (bar_x, bar_y, bar_w, bar_h))
            fill = int(bar_w * xp_into / max(1, xp_needed))
            pygame.draw.rect(screen, C_NEON_CYAN, (bar_x, bar_y, fill, bar_h))

        # Character preview sprites (larger)
        p1_ch = game.CHARACTERS[game.p1_char_idx]
        p2_ch = game.CHARACTERS[game.p2_char_idx]
        p1_preview = make_sprite(p1_ch["sprite"], p1_ch["palette"], 5)
        p2_preview = make_sprite(p2_ch["sprite"], p2_ch["palette"], 5)

        # P1 preview panel (left)
        p1_panel_x = 30
        screen.blit(p1_preview, (p1_panel_x + 10, 140))
        screen.blit(game.font_menu.render("P1", True, p1_ch["color"]), (p1_panel_x + 25, 125))
        p1_role = INSTRUMENT_ROLES[game.p1_role_idx]
        screen.blit(game.font.render(p1_ch["name"], True, p1_ch["color"]), (p1_panel_x, 220))
        screen.blit(game.font.render(p1_role["name"], True, p1_role["color"]), (p1_panel_x, 236))

        # P2 preview panel (right) — only in 2P mode
        if game.menu_player_mode == 1:
            p2_panel_x = WIDTH - 110
            screen.blit(p2_preview, (p2_panel_x + 10, 140))
            screen.blit(game.font_menu.render("P2", True, p2_ch["color"]), (p2_panel_x + 25, 125))
            p2_role = INSTRUMENT_ROLES[game.p2_role_idx]
            screen.blit(game.font.render(p2_ch["name"], True, p2_ch["color"]), (p2_panel_x, 220))
            screen.blit(game.font.render(p2_role["name"], True, p2_role["color"]), (p2_panel_x, 236))

        # Menu items
        menu_x = cx - 200
        menu_y_start = 130
        item_h = 44

        for i, item_name in enumerate(self._menu_items):
            y = menu_y_start + i * item_h
            selected = (i == game.menu_selection)
            base_color = C_NEON_CYAN if selected else C_HUD_DIM
            label_color = (255, 255, 255) if selected else (150, 150, 170)

            # Selection indicator
            if selected:
                sel_bar = pygame.Surface((400, item_h - 4), pygame.SRCALPHA)
                sel_bar.fill((*C_NEON_CYAN, 25))
                screen.blit(sel_bar, (menu_x, y))
                # Arrow
                arrow = game.font_big.render(">", True, C_NEON_CYAN)
                screen.blit(arrow, (menu_x - 25, y + 8))

            # Item label
            label = game.font_menu.render(item_name, True, base_color)
            screen.blit(label, (menu_x + 10, y + 4))

            # Item value
            val_x = menu_x + 180
            if item_name == "PLAYERS":
                modes = ["1P SOLO", "2P CO-OP"]
                val = modes[game.menu_player_mode]
                vc = C_NEON_GREEN if game.menu_player_mode == 1 else C_NEON_YELLOW
                val_surf = game.font_big.render(f"< {val} >", True, vc if selected else C_HUD_DIM)
                screen.blit(val_surf, (val_x, y + 2))

            elif item_name == "SONG":
                if game.song_list:
                    song = game.song_list[game.song_idx]
                    title_str = f"{song['artist']} - {song['title']}"
                    if len(title_str) > 35:
                        title_str = title_str[:32] + "..."
                    val_surf = game.font_big.render(f"< {title_str} >", True, C_NEON_PINK if selected else C_HUD_DIM)
                    screen.blit(val_surf, (val_x, y + 2))
                    # Song details
                    diff_str = "*" * song['difficulty'] + "." * (5 - song['difficulty'])
                    detail = f"{song['bpm']} BPM | Key: {song['key']} | [{diff_str}]"
                    screen.blit(game.font.render(detail, True, (120, 120, 140)), (val_x, y + 26))
                    # Song counter
                    counter = game.font.render(f"{game.song_idx + 1}/{len(game.song_list)}", True, (80, 80, 100))
                    screen.blit(counter, (val_x + 380, y + 4))
                else:
                    val_surf = game.font_big.render("No songs found", True, C_ENEMY)
                    screen.blit(val_surf, (val_x, y + 2))

            elif item_name == "P1 CHARACTER":
                ch = game.CHARACTERS[game.p1_char_idx]
                val_surf = game.font_big.render(f"< {ch['name']} >", True, ch['color'] if selected else C_HUD_DIM)
                screen.blit(val_surf, (val_x, y + 2))
                ability = game.font.render(ch['ability'], True, (120, 120, 140))
                screen.blit(ability, (val_x, y + 26))

            elif item_name == "P1 PALETTE":
                pal_info = save_system.COLOR_PALETTES.get(game.profile_palette_name, {})
                pal_label = pal_info.get("label", game.profile_palette_name)
                pal_color = C_STAR_GOLD if game.profile_palette_name != "default" else C_HUD
                val_surf = game.font_big.render(f"< {pal_label} >", True, pal_color if selected else C_HUD_DIM)
                screen.blit(val_surf, (val_x, y + 2))
                level = game.profile["level"] if game.profile else 1
                n_unlocked = len(save_system.unlocked_palettes(level))
                n_total = len(save_system.COLOR_PALETTES)
                detail = game.font.render(f"{n_unlocked}/{n_total} unlocked", True, (120, 120, 140))
                screen.blit(detail, (val_x, y + 26))

            elif item_name == "P1 ROLE":
                role = INSTRUMENT_ROLES[game.p1_role_idx]
                val_surf = game.font_big.render(f"< {role['name']} >", True, role['color'] if selected else C_HUD_DIM)
                screen.blit(val_surf, (val_x, y + 2))
                desc = game.font.render(role['desc'], True, (120, 120, 140))
                screen.blit(desc, (val_x, y + 26))

            elif item_name == "P2 CHARACTER":
                ch = game.CHARACTERS[game.p2_char_idx]
                val_surf = game.font_big.render(f"< {ch['name']} >", True, ch['color'] if selected else C_HUD_DIM)
                screen.blit(val_surf, (val_x, y + 2))
                ability = game.font.render(ch['ability'], True, (120, 120, 140))
                screen.blit(ability, (val_x, y + 26))

            elif item_name == "P2 ROLE":
                role = INSTRUMENT_ROLES[game.p2_role_idx]
                val_surf = game.font_big.render(f"< {role['name']} >", True, role['color'] if selected else C_HUD_DIM)
                screen.blit(val_surf, (val_x, y + 2))
                desc = game.font.render(role['desc'], True, (120, 120, 140))
                screen.blit(desc, (val_x, y + 26))

            elif item_name == "MIDI OUTPUT":
                if game.available_midi:
                    port = game.available_midi[game.menu_midi_idx]
                    if len(port) > 28:
                        port = port[:25] + "..."
                    val_surf = game.font_big.render(f"< {port} >", True, C_NEON_GREEN if selected else C_HUD_DIM)
                else:
                    val_surf = game.font_big.render("No MIDI ports found", True, C_ENEMY)
                screen.blit(val_surf, (val_x, y + 2))

            elif item_name == "START GAME":
                if selected:
                    pulse2 = 0.5 + 0.5 * math.sin(time.time() * 5)
                    start_color = (
                        int(C_NEON_GREEN[0] * pulse2),
                        int(C_NEON_GREEN[1] * pulse2),
                        int(C_NEON_GREEN[2] * pulse2),
                    )
                    val_surf = game.font_title.render("PRESS ENTER", True, start_color)
                else:
                    val_surf = game.font_big.render(">>", True, C_HUD_DIM)
                screen.blit(val_surf, (val_x, y - 4 if selected else y + 2))

        # Controller status panel
        panel_y = menu_y_start + len(self._menu_items) * item_h + 20
        screen.blit(game.font_menu.render("CONTROLLERS", True, C_HUD), (menu_x + 10, panel_y))
        pygame.draw.line(screen, C_HUD_DIM, (menu_x + 10, panel_y + 22), (menu_x + 390, panel_y + 22), 1)

        if game.detected_controllers:
            for i, ctrl in enumerate(game.detected_controllers):
                cy_ctrl = panel_y + 28 + i * 20
                dot_color = C_NEON_GREEN
                screen.blit(game.font.render("*", True, dot_color), (menu_x + 15, cy_ctrl))
                screen.blit(
                    game.font.render(f"{ctrl['type']}: {ctrl['name'][:40]}", True, (180, 180, 200)),
                    (menu_x + 30, cy_ctrl),
                )
        else:
            screen.blit(
                game.font.render("No controllers detected", True, C_HUD_DIM),
                (menu_x + 15, panel_y + 28),
            )

        # FE + Joystick status
        status_y = panel_y + 28 + max(1, len(game.detected_controllers)) * 20 + 5
        fe_status = "* Connected" if game.fe_connected else "o Not found"
        fe_color = C_NEON_GREEN if game.fe_connected else C_HUD_DIM
        screen.blit(game.font.render(f"Fighting Edge: {fe_status}", True, fe_color), (menu_x + 15, status_y))

        js_status = "* Connected" if game.joystick_connected else "o Not found"
        js_color = C_NEON_GREEN if game.joystick_connected else C_HUD_DIM
        screen.blit(game.font.render(f"Thrustmaster:  {js_status}", True, js_color), (menu_x + 15, status_y + 18))

        # Footer
        footer_items = [
            "[UP/DOWN] Navigate",
            "[LEFT/RIGHT] Change",
            "[ENTER] Select",
            "[F5] Refresh Controllers",
            "[ESC] Quit",
        ]
        footer = "    ".join(footer_items)
        screen.blit(game.font.render(footer, True, (60, 60, 80)), (20, HEIGHT - 22))
