"""
Level data structures and loaders (MIDI file and procedural generation).
Extracted from moonwolf_layers.py for modular import.
"""

import mido

from src.data.constants import (
    WIDTH, HEIGHT, TILE,
    KICK, SNARE, HAT, OHAT, CRASH, RIDE, LTOM, HTOM,
    DRUM_CH, FE_DRUM_MAP,
    ROOT_MIDI, MAJOR_INT, MINOR_INT,
)


class Level:
    """One instrument layer of a song.

    Contains note pickups (melody) and drum lane events placed in
    world-space X coordinates derived from BPM and bar count.

    Args:
        name: Display name (e.g. "DRUMS", "MELODY").
        bpm: Beats per minute.
        bars: Number of bars in this level.
        note_events: List of (time_sec, midi_note, velocity, channel).
        drum_events: List of (time_sec, midi_note, velocity, channel).
        instrument_name: Human-readable instrument label.
    """

    def __init__(self, name, bpm, bars, note_events, drum_events, instrument_name="Synth"):
        self.name = name
        self.bpm = bpm
        self.bars = bars
        self.instrument_name = instrument_name
        self.scroll_speed = (bpm * 4 / 60.0) * (TILE * 2)  # px/sec
        self.level_width = bars * 4 * 4 * (TILE * 2)        # bars * beats * subdivs * px

        # Note pickups: [x, y, note, collected]
        self.pickups = []
        # Drum lanes: [x, lane_idx, drum_note, hit]
        self.drum_lanes = []

        self.play_top = 80
        self.play_bottom = HEIGHT - 200
        self.play_range = self.play_bottom - self.play_top

        # Compute actual note range for better vertical compression
        if note_events:
            notes = [n for _, n, _, _ in note_events]
            self._note_min = min(notes)
            self._note_max = max(notes)
            # Ensure at least an octave of range
            if self._note_max - self._note_min < 12:
                mid = (self._note_min + self._note_max) // 2
                self._note_min = mid - 6
                self._note_max = mid + 6
        else:
            self._note_min = 30
            self._note_max = 80

        # Place events
        for t, note, vel, ch in note_events:
            x = int(t * self.scroll_speed)
            y = self._note_to_y(note)
            self.pickups.append([x, y, note, False])

        for t, note, vel, ch in drum_events:
            x = int(t * self.scroll_speed)
            lane = self._drum_to_lane(note)
            if lane >= 0:
                self.drum_lanes.append([x, lane, note, False])

    def _note_to_y(self, note):
        """Map a MIDI note number to a vertical screen position."""
        if not hasattr(self, '_note_min'):
            self._note_min = 30
            self._note_max = 80
        frac = max(0, min(1, (note - self._note_min) / max(1, self._note_max - self._note_min)))
        # Compress to middle 60% of play area
        margin = self.play_range * 0.2
        usable = self.play_range - margin * 2
        return int(self.play_bottom - margin - frac * usable)

    def _drum_to_lane(self, note):
        """Map a GM drum note to an FE lane index, or -1 if unmapped."""
        for lane_idx, (drum_note, name, color) in FE_DRUM_MAP.items():
            if drum_note == note:
                return lane_idx
        return -1

    def reset(self):
        """Mark all pickups and drum lanes as uncollected/unhit."""
        for p in self.pickups:
            p[3] = False
        for d in self.drum_lanes:
            d[3] = False


# ======================================================================
# MIDI file loader
# ======================================================================

def load_levels_from_midi(filepath, bpm_override=None):
    """Load a MIDI file and split into drum level + melody level.

    Returns:
        Tuple of (levels_list, bpm).
    """
    mid = mido.MidiFile(filepath)
    bpm = bpm_override or 120

    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                bpm = mido.tempo2bpm(msg.tempo)

    if bpm_override:
        bpm = bpm_override

    # Collect events
    drum_events = []
    note_events = []

    for track in mid.tracks:
        abs_time = 0.0
        for msg in track:
            abs_time += mido.tick2second(msg.time, mid.ticks_per_beat, mido.bpm2tempo(bpm))
            if msg.type == 'note_on' and msg.velocity > 0:
                if msg.channel == 9:
                    drum_events.append((abs_time, msg.note, msg.velocity, msg.channel))
                else:
                    note_events.append((abs_time, msg.note, msg.velocity, msg.channel))

    drum_events.sort()
    note_events.sort()

    # Figure out bar counts
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4

    drum_bars = 16
    if drum_events:
        drum_bars = int(drum_events[-1][0] / bar_dur) + 1

    mel_bars = 16
    if note_events:
        mel_start = note_events[0][0]
        note_events_shifted = [(t - mel_start, n, v, c) for t, n, v, c in note_events]
        mel_bars = int(note_events_shifted[-1][0] / bar_dur) + 2
    else:
        note_events_shifted = []

    # Determine the melody MIDI channel
    mel_channel = 0
    if note_events:
        from collections import Counter
        ch_counts = Counter(c for _, _, _, c in note_events)
        mel_channel = ch_counts.most_common(1)[0][0]

    levels = []
    drum_level = Level("DRUMS", bpm, drum_bars, [], drum_events, "Drum Kit")
    drum_level.midi_channel = 9
    levels.append(drum_level)
    if note_events_shifted:
        mel_level = Level("MELODY", bpm, mel_bars, note_events_shifted, [], "Lead Synth")
        mel_level.midi_channel = mel_channel
        levels.append(mel_level)

    return levels, bpm


# ======================================================================
# Procedural level generator
# ======================================================================

def generate_default_levels(bpm, key_name, is_major):
    """Generate procedural drum + melody levels.

    Returns:
        List of Level objects.
    """
    root = ROOT_MIDI.get(key_name, 57)
    intervals = MAJOR_INT if is_major else MINOR_INT
    scale = [root + iv for iv in intervals]
    beat_dur = 60.0 / bpm

    # Level 1: 16-bar drum pattern
    drum_events = []
    for bar in range(16):
        bar_t = bar * 4 * beat_dur
        drum_events.append((bar_t, KICK, 110, 9))
        drum_events.append((bar_t + beat_dur, HAT, 70, 9))
        drum_events.append((bar_t + beat_dur * 1.5, SNARE, 100, 9))
        drum_events.append((bar_t + beat_dur * 2, KICK, 100, 9))
        drum_events.append((bar_t + beat_dur * 2, HAT, 70, 9))
        drum_events.append((bar_t + beat_dur * 3, HAT, 60, 9))
        drum_events.append((bar_t + beat_dur * 3.5, HAT, 50, 9))

    # Level 2: Melody
    note_events = []
    t = 0
    for rep in range(8):
        for degree in [0, 0, 2, 0, 6, 5, 4]:
            note = scale[degree % len(scale)]
            note_events.append((t, note, 100, 0))
            t += beat_dur

    drum_level = Level("DRUMS", bpm, 16, [], drum_events, "Drum Kit")
    drum_level.midi_channel = 9
    mel_level = Level("MELODY", bpm, 16, note_events, [], "Lead Synth")
    mel_level.midi_channel = 0
    return [drum_level, mel_level]
