"""
Ship (player character) physics — thrust, drag, magnetism, edge bounce.
Extracted from moonwolf_layers.py for modular import.
"""

from src.data.constants import HEIGHT


class Ship:
    """Player ship with physics-based vertical movement.

    The ship responds to joystick Y input, has drag and velocity clamping,
    bounces softly off level edges, and is pulled toward the next note
    via a magnetism system.

    Args:
        y: Initial vertical position (default: screen center).
    """

    # ------------------------------------------------------------------
    # Physics constants
    # ------------------------------------------------------------------
    THRUST_NORMAL = 1200.0
    THRUST_AGILE = 1800.0        # Monkey ability: +50% acceleration

    DRAG_NORMAL = 4.0
    DRAG_FLIGHT = 1.5            # Pegasus ability: minimal drag

    MAX_VEL_NORMAL = 500.0
    MAX_VEL_FLIGHT = 600.0

    MAGNET_STRENGTH = 200.0
    MAGNET_RANGE = 400.0         # px ahead to consider notes

    def __init__(self, y=None):
        self.y = y if y is not None else HEIGHT // 2
        self.vy = 0.0
        # Guide-line state (read by renderer)
        self._next_note_y = None
        self._next_note_dist = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self, y=None):
        """Reset position and velocity for a new level."""
        self.y = y if y is not None else HEIGHT // 2
        self.vy = 0.0
        self._next_note_y = None
        self._next_note_dist = 0

    def update(self, dt, joy_y, pickups, player_x, abilities):
        """Advance ship physics for one frame.

        Args:
            dt: Delta time in seconds.
            joy_y: Joystick Y axis (-1 up .. +1 down).
            pickups: The level's pickup list [[x, y, note, collected], ...].
            player_x: Current camera_x + hit-line offset (world X of ship).
            abilities: Dict with boolean keys:
                agile, flight, play_top, play_bottom.
        """
        agile = abilities.get('agile', False)
        flight = abilities.get('flight', False)
        play_top = abilities.get('play_top', 80)
        play_bottom = abilities.get('play_bottom', HEIGHT - 200)

        thrust = self.THRUST_AGILE if agile else self.THRUST_NORMAL
        if flight:
            drag = self.DRAG_FLIGHT
            max_vel = self.MAX_VEL_FLIGHT
        else:
            drag = self.DRAG_NORMAL
            max_vel = self.MAX_VEL_NORMAL

        # ------------------------------------------------------------------
        # Note magnetism — find next uncollected note and pull toward it
        # ------------------------------------------------------------------
        best_dist = 99999
        next_note_y = None
        for pickup in pickups:
            if pickup[3]:  # collected
                continue
            px, py = pickup[0], pickup[1]
            ahead = px - player_x
            if -30 < ahead < self.MAGNET_RANGE:
                if ahead < best_dist:
                    best_dist = ahead
                    next_note_y = py

        # Store for guide line rendering
        self._next_note_y = next_note_y
        self._next_note_dist = best_dist if next_note_y is not None else 0

        if next_note_y is not None:
            closeness = max(0.0, 1.0 - best_dist / self.MAGNET_RANGE)
            diff = next_note_y - self.y
            self.vy += diff * self.MAGNET_STRENGTH * closeness * dt

        # ------------------------------------------------------------------
        # Thrust from joystick (overrides magnetism when active)
        # ------------------------------------------------------------------
        self.vy += joy_y * thrust * dt

        # ------------------------------------------------------------------
        # Drag — always pulls velocity toward zero
        # ------------------------------------------------------------------
        self.vy -= self.vy * drag * dt

        # ------------------------------------------------------------------
        # Clamp velocity
        # ------------------------------------------------------------------
        self.vy = max(-max_vel, min(max_vel, self.vy))

        # ------------------------------------------------------------------
        # Move
        # ------------------------------------------------------------------
        self.y += self.vy * dt

        # ------------------------------------------------------------------
        # Edge bounce (soft)
        # ------------------------------------------------------------------
        if self.y < play_top:
            self.y = play_top
            self.vy = abs(self.vy) * 0.3
        elif self.y > play_bottom:
            self.y = play_bottom
            self.vy = -abs(self.vy) * 0.3
