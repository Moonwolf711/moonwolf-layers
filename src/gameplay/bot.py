"""
Demo bot — automated play for testing and attract mode.
Extracted from moonwolf_layers.py for modular import.
"""

import random


class DemoBot:
    """Autonomous player that steers the ship and hits drums optimally.

    The bot uses weighted lookahead for ship steering (PID-style control)
    and fires drum hits within the perfect timing window.  It also
    auto-advances through menus/intros/completion screens.

    Usage::

        bot = DemoBot()
        # In the game loop:
        joy_y = bot.update(game, dt)
        # joy_y replaces joystick input when bot is active.
    """

    def __init__(self):
        self.auto_advance_timer = 0.0

    def reset(self):
        self.auto_advance_timer = 0.0

    def update(self, game, dt):
        """Run one frame of bot logic.

        Args:
            game: The MoonwolfLayers instance (read-only access to state).
            dt: Delta time in seconds.

        Returns:
            float: The joy_y value the bot wants (-1..1), or 0 if not
            in a playing state. The caller is responsible for feeding
            this into the ship update.
        """
        self.auto_advance_timer += dt
        joy_y = 0.0

        # ------------------------------------------------------------------
        # Auto-advance through non-gameplay screens
        # ------------------------------------------------------------------
        if game.state == "PROFILE_SELECT" and self.auto_advance_timer > 0.5:
            self._advance_profile(game)
            self.auto_advance_timer = 0.0
            return joy_y

        if game.state == "MAIN_MENU" and self.auto_advance_timer > 1.0:
            self._advance_menu(game)
            self.auto_advance_timer = 0.0
            return joy_y

        if game.state == "LEVEL_INTRO" and self.auto_advance_timer > 2.0:
            game._start_level()
            self.auto_advance_timer = 0.0
            return joy_y

        if game.state == "LEVEL_COMPLETE" and self.auto_advance_timer > 3.0:
            game._next_level()
            self.auto_advance_timer = 0.0
            return joy_y

        # ------------------------------------------------------------------
        # Playing — steer ship and hit drums
        # ------------------------------------------------------------------
        if game.state not in ("PLAYING", "STAR_POWER"):
            return joy_y

        player_x = game.camera_x + 200

        # -- Ship steering via weighted lookahead --------------------------
        joy_y = self._steer_ship(game, player_x)

        # -- Auto-hit drums within perfect window --------------------------
        self._auto_hit_drums(game, player_x)

        return joy_y

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _advance_profile(game):
        """Auto-create a demo profile and move to main menu."""
        import save_system
        game.profile = save_system.new_profile("DemoBot", "wolf")
        game.state = "MAIN_MENU"

    @staticmethod
    def _advance_menu(game):
        """Pick a random song and start the game."""
        if game.song_list:
            game.song_idx = random.randint(0, len(game.song_list) - 1)
        game._init_game()

    @staticmethod
    def _steer_ship(game, player_x):
        """Weighted lookahead + PID-style steering toward upcoming notes.

        Returns joy_y in [-1, 1].
        """
        upcoming = []
        for pickup in game.level.pickups:
            if pickup[3]:
                continue
            px, py = pickup[0], pickup[1]
            ahead = px - player_x
            if -20 < ahead < 600:
                upcoming.append((ahead, py))
            if len(upcoming) >= 3:
                break

        if upcoming:
            if len(upcoming) >= 2:
                w1, w2 = 0.7, 0.3
                target_y = upcoming[0][1] * w1 + upcoming[1][1] * w2
            else:
                target_y = upcoming[0][1]
        else:
            target_y = game.p1_y

        diff = target_y - game.p1_y
        if abs(diff) > 2:
            p_gain = diff / 25.0       # Proportional
            d_gain = -game.p1_vy / 400.0  # Derivative (velocity damping)
            joy_y = max(-1.0, min(1.0, p_gain + d_gain))
        else:
            joy_y = 0.0
            game.p1_vy *= 0.3  # Hard brake when on target

        return joy_y

    @staticmethod
    def _auto_hit_drums(game, player_x):
        """Fire drum hits within the perfect timing window."""
        for dl in game.level.drum_lanes:
            if dl[3]:
                continue
            dx, lane_idx = dl[0], dl[1]
            dist = player_x - dx  # Positive = past target
            # Fire when target is 0-10px ahead of hit line (guaranteed perfect)
            if -10 <= dist <= 10:
                game._on_fe_button(lane_idx)
