"""
Base state class for the Moonwolf Layers game state machine.

All game states inherit from GameState and override the relevant methods.
Each state receives a reference to the main MoonwolfLayers game instance
via self.game, which provides access to all shared state (score, combo,
level, midi_port, profile, fonts, particles, etc.).
"""


class GameState:
    """Abstract base class for all game states."""

    def __init__(self, game):
        """
        Args:
            game: Reference to the MoonwolfLayers instance that owns this state.
        """
        self.game = game

    def enter(self):
        """Called when entering this state. Override to set up state-specific data."""
        pass

    def exit(self):
        """Called when leaving this state. Override to clean up state-specific data."""
        pass

    def handle_event(self, event):
        """Handle a single pygame event.

        Args:
            event: A pygame event object.

        Returns:
            str or None: The name of the next state to transition to,
            or None to stay in the current state.
        """
        return None

    def update(self, dt):
        """Update logic for this state.

        Args:
            dt: Delta time in seconds since the last frame.

        Returns:
            str or None: The name of the next state to transition to,
            or None to stay in the current state.
        """
        return None

    def draw(self, screen):
        """Draw this state to the given screen surface.

        Args:
            screen: The pygame display surface to draw on.
        """
        pass
