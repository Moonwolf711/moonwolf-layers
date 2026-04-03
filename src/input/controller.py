"""
Fighting Edge HID reader and controller scanning.
Extracted from moonwolf_layers.py for modular import.
"""

import time
import threading

import pygame

from src.data.constants import FE_DRUM_MAP


def scan_controllers(joystick_connected_ref=None):
    """Scan for joysticks and Fighting Edge controllers.

    Args:
        joystick_connected_ref: Optional mutable container (e.g. [False])
            that will be set to [True] if a Thrustmaster is found.

    Returns:
        Tuple of (controllers_list, fe_connected, joystick_connected).
    """
    controllers = []
    fe_connected = False
    joystick_connected = False

    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        name = js.get_name()
        ctype = "Joystick"
        if 't.16000m' in name.lower() or 'thrustmaster' in name.lower():
            ctype = "Thrustmaster T.16000M"
            joystick_connected = True
        elif 'fighting' in name.lower() or '0f0d' in name.lower():
            ctype = "Fighting Edge"
        controllers.append({
            "name": name,
            "type": ctype,
            "idx": i,
            "source": "pygame",
        })

    # Fighting Edge via HID
    try:
        import hid as hidlib
        devs = hidlib.enumerate(0x0F0D, 0x0037)
        if devs:
            fe_connected = True
            # Only add if not already listed via pygame
            if not any("Fighting" in c["type"] for c in controllers):
                controllers.append({
                    "name": "Hori Fighting Edge",
                    "type": "Fighting Edge (HID)",
                    "idx": -1,
                    "source": "hid",
                })
    except Exception:
        pass

    return controllers, fe_connected, joystick_connected


class FightingEdgeReader:
    """Reads Fighting Edge arcade stick via HID in a background thread.

    The reader tracks an 8-element button state list and a hat value.
    On button press/release it invokes the provided callbacks.

    Args:
        on_button_press: Callable(btn_idx: int) called on button down.
        on_button_release: Callable(btn_idx: int) called on button up.
    """

    VENDOR_ID = 0x0F0D
    PRODUCT_ID = 0x0037

    def __init__(self, on_button_press=None, on_button_release=None):
        self.buttons = [False] * 8
        self.hat = -1
        self._on_press = on_button_press
        self._on_release = on_button_release
        self._thread = None

    def start(self):
        """Start the background HID reading thread (daemon)."""
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self):
        try:
            import hid as hidlib
            devs = hidlib.enumerate(self.VENDOR_ID, self.PRODUCT_ID)
            if not devs:
                print("  Fighting Edge not found")
                return
            dev = hidlib.device()
            dev.open_path(devs[0]['path'])
            dev.set_nonblocking(True)
            print("  Fighting Edge: connected")
            prev = None
            while True:
                data = dev.read(64)
                if not data:
                    time.sleep(0.005)
                    continue
                # Parse buttons (byte 0 bitmask)
                for bit in range(8):
                    cur = (data[0] >> bit) & 1
                    old = (prev[0] >> bit) & 1 if prev else 0
                    if cur != old:
                        self.buttons[bit] = bool(cur)
                        if cur:
                            if self._on_press:
                                self._on_press(bit)
                        else:
                            if self._on_release:
                                self._on_release(bit)
                # Hat (byte 2)
                hat = data[2] if len(data) > 2 else 0x0F
                prev_hat = prev[2] if prev and len(prev) > 2 else 0x0F
                if hat != prev_hat:
                    self.hat = hat
                prev = list(data)
        except Exception as e:
            print(f"  FE reader error: {e}")
