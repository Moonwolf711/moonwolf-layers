"""
Score, combo, star power, and grade tracking.
Extracted from moonwolf_layers.py for modular import.
"""

from src.data.constants import (
    MULT_THRESHOLDS,
    GRADES,
    STAR_POWER_THRESHOLD,
    STAR_POWER_BARS,
    C_NEON_GREEN,
    C_STAR_GOLD,
    C_ENEMY,
)


class ScoreSystem:
    """Tracks score, combo, star power, hit breakdown, and grade.

    Ability flags are set externally after construction (e.g. from
    character selection) via the ``set_abilities`` method.
    """

    def __init__(self):
        # Core scoring
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.hits = 0
        self.total_targets = 0

        # Hit breakdown
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0

        # Star power
        self.star_power = False
        self.star_power_timer = 0.0
        self.star_meter = 0.0

        # Combo pulse for visual feedback (0..1, decays each frame)
        self.combo_pulse = 0.0

        # Ability flags (set via set_abilities)
        self.fury = False       # Tiger: combo thresholds halved
        self.frenzy = False     # Shark: +10% score per combo tier
        self.predator = False   # Puma: 2x score on Perfect
        self.rage = False       # Minotaur: star power 2x duration
        self.venom = False      # Snake: miss immunity timer
        self.venom_timer = 0.0
        self.shell = False      # Turtle: immune for N hits
        self.shell_hits = 0
        self.combo_shield = False  # Dog
        self.combo_shield_max = 1
        self.combo_shield_count = 0
        self.tank = False       # Gorilla: 3 shields
        self.star_fill_bonus = 1.0
        self.perfect_bonus = 1.0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_abilities(self, *, fury=False, frenzy=False, predator=False,
                      rage=False, venom=False, shell=False,
                      combo_shield=False, tank=False,
                      star_fill_bonus=1.0, perfect_bonus=1.0):
        self.fury = fury
        self.frenzy = frenzy
        self.predator = predator
        self.rage = rage
        self.venom = venom
        self.shell = shell
        self.combo_shield = combo_shield
        self.tank = tank
        self.combo_shield_max = 3 if tank else 1
        self.star_fill_bonus = star_fill_bonus
        self.perfect_bonus = perfect_bonus

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self, total_targets=0):
        """Reset per-level state. Call at level start."""
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.hits = 0
        self.total_targets = total_targets
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.star_power = False
        self.star_power_timer = 0.0
        self.star_meter = 0.0
        self.combo_pulse = 0.0
        self.combo_shield_count = 0
        self.venom_timer = 0.0
        self.shell_hits = 0

    # ------------------------------------------------------------------
    # Multiplier / grade helpers
    # ------------------------------------------------------------------

    def get_multiplier(self):
        """Return the current combo multiplier."""
        divisor = 2 if self.fury else 1  # Tiger: thresholds halved
        for threshold, mult in MULT_THRESHOLDS:
            if self.combo >= threshold // divisor:
                return mult
        return 1

    def get_grade(self, pct=None):
        """Return (letter, color) grade for the given accuracy percent.

        If *pct* is None, compute it from hits/total_targets.
        """
        if pct is None:
            pct = (self.hits / max(1, self.total_targets)) * 100
        for threshold, letter, color in GRADES:
            if pct >= threshold:
                return letter, color
        return "F", C_ENEMY

    def _score_multiplier(self, base_score, mult):
        """Apply frenzy bonus (Shark) -- +10% per combo tier."""
        score = base_score * mult
        if self.frenzy:
            tier = 0
            for threshold, m in MULT_THRESHOLDS:
                if self.combo >= threshold:
                    tier = m
                    break
            score = int(score * (1.0 + tier * 0.1))
        return int(score)

    # ------------------------------------------------------------------
    # Combo protection
    # ------------------------------------------------------------------

    def try_break_combo(self, popups=None, popup_x=0, popup_y=0):
        """Try to break the combo. Returns True if combo actually broke.

        If *popups* (a PopupSystem) is provided, visual feedback is added.
        """
        if self.combo <= 0:
            return True

        # Venom -- immune while timer active
        if self.venom and self.venom_timer > 0:
            if popups:
                popups.add(popup_x, popup_y, "VENOM!", (80, 200, 50))
            return False

        # Shell -- immune for N hits
        if self.shell and self.shell_hits < 5:
            self.shell_hits += 1
            if popups:
                popups.add(popup_x, popup_y, f"SHELL! ({5 - self.shell_hits})", (80, 180, 80))
            return False

        # Combo shield (Dog) / Tank (Gorilla, 3 shields)
        if self.combo_shield and self.combo_shield_count < self.combo_shield_max:
            self.combo_shield_count += 1
            remaining = self.combo_shield_max - self.combo_shield_count
            if popups:
                popups.add(popup_x, popup_y, f"SHIELD! ({remaining})", C_NEON_GREEN)
            return False

        # No protection -- combo breaks
        self.combo = 0
        return True

    def _on_hit(self):
        """Called on every successful hit -- refresh venom timer."""
        if self.venom:
            self.venom_timer = 3.0

    # ------------------------------------------------------------------
    # Main scoring entry point
    # ------------------------------------------------------------------

    def award_hit(self, timing_tier, *, bpm=120.0, popups=None,
                  particles=None, popup_x=0, popup_y=0, particle_y=0):
        """Award a hit of the given timing tier.

        Args:
            timing_tier: One of "perfect", "great", "good".
            bpm: Current BPM (for star power duration).
            popups: Optional PopupSystem for visual feedback.
            particles: Optional ParticleSystem for visual feedback.
            popup_x, popup_y: Position for popup text.
            particle_y: Y position for particle burst.

        Returns:
            True if star power was just activated by this hit.
        """
        self.combo += 1
        self.combo_pulse = 1.0
        self._on_hit()
        self.hits += 1
        if self.combo % 10 == 0 and self.combo > 0:
            self.combo_10s += 1
        self.max_combo = max(self.max_combo, self.combo)

        mult = self.get_multiplier()
        star_activated = False

        if timing_tier == "perfect":
            self.perfects += 1
            base = 50 * (2 if self.predator else 1)
            self.score += self._score_multiplier(base, mult)
            self.star_meter = min(1.0, self.star_meter + 0.08 * self.star_fill_bonus)
            if popups:
                popups.add(popup_x, popup_y, f"PERFECT! x{mult}", C_STAR_GOLD)
            if particles:
                particles.emit(popup_x, particle_y, 12, C_STAR_GOLD, 200)
        elif timing_tier == "great":
            self.greats += 1
            self.score += self._score_multiplier(30, mult)
            self.star_meter = min(1.0, self.star_meter + 0.05 * self.star_fill_bonus)
            if popups:
                popups.add(popup_x, popup_y, f"GREAT! x{mult}", C_NEON_GREEN)
            if particles:
                particles.emit(popup_x, particle_y, 8, C_NEON_GREEN, 150)
        elif timing_tier == "good":
            self.goods += 1
            self.score += self._score_multiplier(10, mult)
            self.star_meter = min(1.0, self.star_meter + 0.03 * self.star_fill_bonus)
            if popups:
                from src.data.constants import C_HUD
                popups.add(popup_x, popup_y, f"Good x{mult}", C_HUD)
            if particles:
                from src.data.constants import C_HUD
                particles.emit(popup_x, particle_y, 4, C_HUD, 80)

        # Check star power activation
        if self.combo >= STAR_POWER_THRESHOLD and not self.star_power:
            self.star_power = True
            sp_bars = STAR_POWER_BARS * (2 if self.rage else 1)
            self.star_power_timer = (60.0 / bpm) * 4 * sp_bars
            self.star_power_activations += 1
            star_activated = True

        return star_activated

    # ------------------------------------------------------------------
    # Per-frame tick
    # ------------------------------------------------------------------

    def tick(self, dt):
        """Call once per frame to decay timers and visual pulses."""
        # Venom timer
        if self.venom_timer > 0:
            self.venom_timer -= dt

        # Combo pulse decay
        self.combo_pulse *= 0.88

        # Star power timer
        if self.star_power:
            self.star_power_timer -= dt
            if self.star_power_timer <= 0:
                self.star_power = False
