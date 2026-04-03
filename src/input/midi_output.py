"""
MIDI output management — port handling, note on/off, transport CCs.
Extracted from moonwolf_layers.py for modular import.
"""

import time

import mido

from src.data.constants import (
    TRANSPORT_CC_PLAY,
    TRANSPORT_CC_STOP,
    TRANSPORT_CC_RECORD,
)


def scan_midi_ports():
    """Get available MIDI output port names.

    Returns:
        List of port name strings.
    """
    try:
        return mido.get_output_names()
    except Exception:
        return []


class MidiOutput:
    """Manages a single MIDI output port with note tracking and transport CCs.

    Handles port lifecycle (open/close with leak prevention),
    note on/off helpers, Ableton transport CC pulses, and a
    pending-note-off list that should be ticked every frame.
    """

    def __init__(self):
        self._port = None
        self.pending_offs = []  # List of (note, channel, off_time)

    # ------------------------------------------------------------------
    # Port lifecycle
    # ------------------------------------------------------------------

    @property
    def is_open(self):
        return self._port is not None

    def open(self, port_name):
        """Open a MIDI output port matching *port_name* (case-insensitive).

        Closes any previously open port first to prevent leaks.
        """
        try:
            self.close()
            available = mido.get_output_names()
            matches = [n for n in available if port_name.lower() in n.lower()]
            if matches:
                self._port = mido.open_output(matches[0])
                print(f"  MIDI output: {matches[0]}")
        except Exception as e:
            print(f"  MIDI error: {e}")

    def close(self):
        """Close the current port if open."""
        if self._port:
            try:
                self._port.close()
            except Exception:
                pass
            self._port = None

    # ------------------------------------------------------------------
    # Note helpers
    # ------------------------------------------------------------------

    def note_on(self, note, vel, ch=0):
        """Send a note-on message."""
        if self._port:
            self._port.send(mido.Message('note_on', note=note, velocity=vel, channel=ch))

    def note_off(self, note, ch=0):
        """Send a note-off message."""
        if self._port:
            self._port.send(mido.Message('note_off', note=note, velocity=0, channel=ch))

    def schedule_off(self, note, ch, duration=0.15):
        """Schedule a note-off after *duration* seconds from now."""
        self.pending_offs.append((note, ch, time.time() + duration))

    def tick_pending_offs(self):
        """Process pending note-offs whose time has arrived.

        Call this once per frame.
        """
        now = time.time()
        still = []
        for note, ch, off_time in self.pending_offs:
            if now >= off_time:
                self.note_off(note, ch)
            else:
                still.append((note, ch, off_time))
        self.pending_offs = still

    # ------------------------------------------------------------------
    # Transport CCs (Ableton)
    # ------------------------------------------------------------------

    def send_transport(self, cc, val=127):
        """Send a transport CC pulse (on then off) to Ableton on channel 15.

        Typical CCs:
            TRANSPORT_CC_PLAY   (119) -> Play
            TRANSPORT_CC_STOP   (118) -> Stop
            TRANSPORT_CC_RECORD (117) -> Record
        """
        if self._port:
            self._port.send(mido.Message('control_change', control=cc, value=val, channel=15))
            time.sleep(0.05)
            self._port.send(mido.Message('control_change', control=cc, value=0, channel=15))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def all_notes_off(self):
        """Send CC 123 (All Notes Off) on every channel, then close."""
        if self._port:
            for ch in range(16):
                self._port.send(mido.Message('control_change', control=123, value=0, channel=ch))
        self.close()
