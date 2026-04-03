"""
generate_songs_group3.py — Santana + Muse MIDI generation
Generates multi-track MIDI files with proper song structure for:
  1. Santana - Black Magic Woman (BPM 124, Dm, 4/4, ~36 bars)
  2. Santana - Smooth (BPM 116, Am, 4/4, ~32 bars)
  3. Santana - Evil Ways (BPM 124, Gm, 4/4, ~32 bars)
  4. Muse - Hysteria (BPM 94, Am, 4/4, ~34 bars)
  5. Muse - Supermassive Black Hole (BPM 120, Am, 4/4, ~32 bars)
  6. Muse - Knights of Cydonia (BPM 138, Em, 6/8, ~36 bars)
"""

import os
import json
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_DIR = os.path.join(BASE_DIR, "songs")

# Lycra Kit Drum Map
KICK = 36
SNARE = 38
SIDE_STICK = 37
CLOSED_HAT = 42
OPEN_HAT = 46
RIDE = 44         # Shaker in Lycra Kit
RIDE_BELL = 44    # Shaker (Lycra Kit has no separate ride bell)
CRASH = 39        # Clap Lycra
HIGH_TOM = 47     # Tom 909 Mid 3
MID_TOM = 41      # Tom Mid 1
LOW_TOM = 41      # Tom Mid 1 (Lycra Kit)
CONGA_HIGH = 47   # Tom 909 Mid 3 (mapped for Lycra)
CONGA_LOW = 41    # Tom Mid 1 (mapped for Lycra)
CONGA_MUTE = 42   # Closed Hat (ghost layer for Lycra)
COWBELL = 44      # Shaker (Lycra Kit)
TIMBALE_HIGH = 47 # Tom 909 Mid 3 (Lycra)
TIMBALE_LOW = 41  # Tom Mid 1 (Lycra)

# Channel constants
CH_KEYS = 0
CH_GUITAR = 1
CH_BASS = 2
CH_DRUMS = 9  # GM drum channel


def t(mid, fraction):
    """Convert a fraction of a beat to ticks. e.g. t(mid, 1) = quarter, t(mid, 0.5) = 8th."""
    return int(mid.ticks_per_beat * fraction)


def add_note(track, note, vel, start_tick, duration_ticks, channel=0):
    """Append a note-on/off pair using absolute ticks."""
    track.append(('on', start_tick, note, vel, channel))
    track.append(('off', start_tick + duration_ticks, note, 0, channel))


def finalize_track(midi_track, events):
    """Convert absolute-time events to delta-time and append to midi_track."""
    events.sort(key=lambda e: (e[1], 0 if e[0] == 'off' else 1))
    current = 0
    for ev in events:
        kind, abs_tick, note, vel, ch = ev
        delta = abs_tick - current
        if delta < 0:
            delta = 0
        current = abs_tick
        if kind == 'on':
            midi_track.append(Message('note_on', note=note, velocity=vel, time=delta, channel=ch))
        else:
            midi_track.append(Message('note_off', note=note, velocity=vel, time=delta, channel=ch))


def save_track_midi(mid_template, events_list, filename, track_name, channel):
    """Save a single-track MIDI from event list."""
    mid = MidiFile(ticks_per_beat=mid_template.ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('track_name', name=track_name, time=0))
    track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(mid_template._bpm), time=0))
    finalize_track(track, events_list)
    track.append(MetaMessage('end_of_track', time=0))
    mid.save(filename)


def save_full_midi(mid_template, all_tracks, filename):
    """Save multi-track MIDI combining all instrument event lists."""
    mid = MidiFile(type=1, ticks_per_beat=mid_template.ticks_per_beat)
    for name, events in all_tracks:
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage('track_name', name=name, time=0))
        track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(mid_template._bpm), time=0))
        finalize_track(track, events)
        track.append(MetaMessage('end_of_track', time=0))
    mid.save(filename)


def make_template(bpm):
    """Create a template MidiFile with BPM stored."""
    mid = MidiFile(ticks_per_beat=480)
    mid._bpm = bpm
    return mid


import random


def humanize_events(events, swing=0.0, timing_jitter=0, velocity_jitter=0,
                    ghost_notes=None, flam_before_accents=False,
                    accent_vel_threshold=100, ppq=480,
                    crescendo_per_bar=0, bar_length_beats=4,
                    micro_timing=None, ride_ahead=0):
    """
    Apply humanization to a list of note events in-place.

    Args:
        events: list of ('on'/'off', abs_tick, note, vel, channel) tuples
        swing: float 0.0-0.5, pushes even 8th notes later (swing feel)
        timing_jitter: int, max random +/- tick offset
        velocity_jitter: int, max random +/- velocity offset
        ghost_notes: list of dicts, each: {'note': N, 'vel_range': (lo,hi), 'every_n_ticks': T, 'channel': C}
        flam_before_accents: if True, add a flam (2nd note 8 ticks before) accent hits
        accent_vel_threshold: velocity above which a note counts as accented
        ppq: ticks per quarter note
        crescendo_per_bar: int, velocity added per bar (for gradual builds)
        bar_length_beats: beats per bar (4 for 4/4, 3 for 6/8)
        micro_timing: dict of {note_number: {'jitter': int, 'accent_beats': [0,2], 'accent_boost': int,
                       'soften_offbeats': int}}  — per-note micro-timing rules
        ride_ahead: int, ticks to push ride/bell notes ahead of beat (negative = ahead)
    Returns:
        The modified events list (also modified in place)
    """
    bar_ticks = ppq * bar_length_beats
    new_events = []
    flams_to_add = []

    for i, ev in enumerate(events):
        kind, abs_tick, note, vel, ch = ev

        # Only process note-on for timing/vel changes; note-off follows
        if kind == 'on':
            # --- Swing: push even 8th notes (off-beats) ---
            if swing > 0:
                eighth = ppq // 2
                pos_in_beat = abs_tick % ppq
                # If this note falls on the "and" (second 8th of a beat)
                if eighth - 5 <= pos_in_beat <= eighth + 5:
                    swing_offset = int(ppq * swing)
                    abs_tick += swing_offset

            # --- Ride ahead-of-beat ---
            if ride_ahead != 0 and note in (RIDE, RIDE_BELL, 44):
                abs_tick += ride_ahead

            # --- Micro-timing per note ---
            if micro_timing and note in micro_timing:
                mt = micro_timing[note]
                mt_jitter = mt.get('jitter', 0)
                if mt_jitter > 0:
                    abs_tick += random.randint(-mt_jitter, mt_jitter)
                # Accent boost on certain beats
                accent_beats = mt.get('accent_beats', [])
                if accent_beats:
                    beat_in_bar = (abs_tick % bar_ticks) / ppq
                    for ab in accent_beats:
                        if abs(beat_in_bar - ab) < 0.1:
                            vel = min(127, vel + mt.get('accent_boost', 10))
                            break
                # Soften off-beats
                soften = mt.get('soften_offbeats', 0)
                if soften > 0:
                    beat_in_bar = (abs_tick % bar_ticks) / ppq
                    beat_frac = beat_in_bar - int(beat_in_bar)
                    if beat_frac > 0.2:  # off-beat
                        vel = max(1, vel - soften)

            # --- Timing jitter ---
            if timing_jitter > 0:
                abs_tick += random.randint(-timing_jitter, timing_jitter)

            # --- Velocity jitter ---
            if velocity_jitter > 0:
                vel += random.randint(-velocity_jitter, velocity_jitter)

            # --- Crescendo per bar ---
            if crescendo_per_bar != 0:
                bar_num = abs_tick // bar_ticks
                beat_in_bar = (abs_tick % bar_ticks) / bar_ticks
                vel += int(crescendo_per_bar * (bar_num + beat_in_bar))

            vel = max(1, min(127, vel))
            abs_tick = max(0, abs_tick)

            # --- Flam before accents ---
            if flam_before_accents and vel >= accent_vel_threshold:
                flam_tick = max(0, abs_tick - 8)
                flam_vel = max(1, min(127, vel - 25))
                flams_to_add.append(('on', flam_tick, note, flam_vel, ch))
                flams_to_add.append(('off', flam_tick + 15, note, 0, ch))

        elif kind == 'off':
            # Apply same swing/jitter to note-off to keep duration consistent
            if swing > 0:
                eighth = ppq // 2
                pos_in_beat = abs_tick % ppq
                if eighth - 5 <= pos_in_beat <= eighth + 5:
                    abs_tick += int(ppq * swing)
            if timing_jitter > 0:
                abs_tick += random.randint(-timing_jitter, timing_jitter)
            if ride_ahead != 0 and note in (RIDE, RIDE_BELL, 44):
                abs_tick += ride_ahead
            abs_tick = max(0, abs_tick)
            vel = 0  # note-off velocity stays 0

        events[i] = (kind, abs_tick, note, vel, ch)

    # --- Add ghost notes ---
    if ghost_notes:
        # Determine the range of the events
        on_ticks = [e[1] for e in events if e[0] == 'on']
        if on_ticks:
            start_tick = min(on_ticks)
            end_tick = max(on_ticks)
            for gn in ghost_notes:
                gnote = gn['note']
                gvel_lo, gvel_hi = gn['vel_range']
                gstep = gn['every_n_ticks']
                gch = gn.get('channel', 9)
                gdur = gn.get('duration', int(ppq * 0.08))
                pos = start_tick
                while pos < end_tick:
                    gvel = random.randint(gvel_lo, gvel_hi)
                    # Small timing jitter on ghost notes
                    gjitter = random.randint(-3, 3)
                    gpos = max(0, pos + gjitter)
                    new_events.append(('on', gpos, gnote, gvel, gch))
                    new_events.append(('off', gpos + gdur, gnote, 0, gch))
                    pos += gstep

    events.extend(flams_to_add)
    events.extend(new_events)
    return events


def add_ghost_snare_between_backbeats(events, ppq=480, bar_length_beats=4,
                                       vel=30, channel=9):
    """Add ghost snare hits between backbeats (beats 2 and 4 in 4/4)."""
    on_ticks = [e[1] for e in events if e[0] == 'on']
    if not on_ticks:
        return events
    start = min(on_ticks)
    end = max(on_ticks)
    bar_ticks = ppq * bar_length_beats
    new = []
    bar_start_t = start - (start % bar_ticks)
    while bar_start_t < end:
        # Ghost snares at: beat 0.5, 1.5, 2.5, 3.5 (the "e" of each beat)
        for beat_off in [0.5, 1.5, 2.5, 3.5]:
            pos = bar_start_t + int(ppq * beat_off)
            if start <= pos < end:
                gv = vel + random.randint(-5, 5)
                gv = max(1, min(127, gv))
                new.append(('on', pos, SNARE, gv, channel))
                new.append(('off', pos + int(ppq * 0.08), SNARE, 0, channel))
        bar_start_t += bar_ticks
    events.extend(new)
    return events


def add_ghost_kick_16ths(events, ppq=480, bar_length_beats=4, vel=40, channel=9):
    """Add ghost kick 16ths underneath for driving songs like Hysteria."""
    on_ticks = [e[1] for e in events if e[0] == 'on']
    if not on_ticks:
        return events
    start = min(on_ticks)
    end = max(on_ticks)
    bar_ticks = ppq * bar_length_beats
    new = []
    sixteenth = ppq // 4
    bar_start_t = start - (start % bar_ticks)
    while bar_start_t < end:
        for i in range(bar_length_beats * 4):
            pos = bar_start_t + i * sixteenth
            if start <= pos < end:
                # Skip positions where a loud kick already exists
                gv = vel + random.randint(-8, 8)
                gv = max(1, min(127, gv))
                new.append(('on', pos, KICK, gv, channel))
                new.append(('off', pos + int(ppq * 0.06), KICK, 0, channel))
        bar_start_t += bar_ticks
    events.extend(new)
    return events


def add_bass_ghost_notes(events, ppq=480, vel_range=(30, 40), channel=2):
    """Add ghost bass notes between main notes at low velocity."""
    on_events = [(e[1], e[2]) for e in events if e[0] == 'on']
    if len(on_events) < 2:
        return events
    on_events.sort()
    new = []
    for i in range(len(on_events) - 1):
        tick1, note1 = on_events[i]
        tick2, note2 = on_events[i + 1]
        gap = tick2 - tick1
        if gap > ppq // 2:  # only if there's enough space
            mid_tick = tick1 + gap // 2
            gvel = random.randint(*vel_range)
            # Use a chromatic passing tone
            passing = note1 + (1 if note2 > note1 else -1)
            new.append(('on', mid_tick, passing, gvel, channel))
            new.append(('off', mid_tick + int(ppq * 0.1), passing, 0, channel))
    events.extend(new)
    return events


def add_bass_slide(events, ppq=480, channel=2):
    """Convert some bass intervals into quick chromatic slides (3 notes in 30 ticks)."""
    on_events = [(i, e) for i, e in enumerate(events) if e[0] == 'on']
    new = []
    for idx, (i, ev) in enumerate(on_events):
        _, abs_tick, note, vel, ch = ev
        if ch != channel:
            continue
        # Find next note-on on same channel
        for j in range(idx + 1, len(on_events)):
            _, next_ev = on_events[j]
            if next_ev[4] == channel:
                next_note = next_ev[2]
                interval = next_note - note
                if abs(interval) >= 3:
                    # Add chromatic slide before the next note
                    slide_start = next_ev[1] - 30
                    if slide_start > abs_tick:
                        direction = 1 if interval > 0 else -1
                        for s in range(3):
                            sn = next_note - direction * (3 - s)
                            st = slide_start + s * 10
                            sv = max(1, min(127, vel - 20 + s * 5))
                            new.append(('on', st, sn, sv, channel))
                            new.append(('off', st + 8, sn, 0, channel))
                break
    events.extend(new)
    return events


def add_guitar_bend(events, ppq=480, channel=1, bend_semitones=1, bend_duration_ticks=100):
    """Simulate guitar bends by adding a note 1 semitone below that leads into the target.
    For each long note (>= 1 beat), prepend a grace note from below."""
    on_events = [(i, e) for i, e in enumerate(events) if e[0] == 'on' and e[4] == channel]
    new = []
    for i, ev in on_events:
        _, abs_tick, note, vel, ch = ev
        # Find matching note-off to determine duration
        for e2 in events:
            if e2[0] == 'off' and e2[2] == note and e2[1] > abs_tick:
                dur = e2[1] - abs_tick
                if dur >= ppq:  # only bend on sustained notes
                    bend_note = note - bend_semitones
                    bend_start = abs_tick - bend_duration_ticks
                    if bend_start >= 0 and random.random() < 0.3:  # 30% chance
                        new.append(('on', bend_start, bend_note, max(1, vel - 15), ch))
                        new.append(('off', bend_start + bend_duration_ticks - 10, bend_note, 0, ch))
                break
    events.extend(new)
    return events


def write_meta(song_dir, title, artist, bpm, key, bars, difficulty, instruments):
    meta = {
        "title": title,
        "artist": artist,
        "bpm": bpm,
        "key": key,
        "bars": bars,
        "difficulty": difficulty,
        "instruments": instruments
    }
    with open(os.path.join(song_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


def bar_start(mid, bar):
    """Absolute tick for the start of a bar (4/4 time)."""
    return bar * 4 * mid.ticks_per_beat


def bar_start_68(mid, bar):
    """Absolute tick for the start of a bar in 6/8 (3 quarter notes per bar)."""
    return bar * 3 * mid.ticks_per_beat


def vscale(base_vel, factor):
    """Scale velocity and clamp to MIDI range."""
    return max(1, min(127, int(base_vel * factor)))


# ========================================================================
# 1. SANTANA - BLACK MAGIC WOMAN (BPM 124, Dm, 4/4, 36 bars)
# Structure: INTRO(4) VERSE(8) CHORUS(4) SOLO(8) VERSE2(8) OUTRO(4)
# ========================================================================
def gen_black_magic_woman():
    bpm = 124
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "black_magic_woman")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    total_bars = 36

    drums = []
    guitar = []
    bass = []

    # Section layout
    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    SOLO = (16, 24)
    VERSE2 = (24, 32)
    OUTRO = (32, 36)

    # --- Helper: Latin rock drum bar ---
    def latin_drums(bar, vel_mult=1.0, has_crash=False):
        base = bar_start(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        if has_crash:
            add_note(drums, CRASH, v(110), base, t(mid, 0.5), CH_DRUMS)
        # Kick on 1 and "and of 2"
        add_note(drums, KICK, v(110), base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(100), base + t(mid, 2.5), t(mid, 0.25), CH_DRUMS)
        # Snare on 4
        add_note(drums, SNARE, v(105), base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Ride bell on every beat + upbeats
        for beat in range(4):
            add_note(drums, RIDE_BELL, v(85), base + t(mid, beat), t(mid, 0.25), CH_DRUMS)
            add_note(drums, RIDE_BELL, v(65), base + t(mid, beat + 0.5), t(mid, 0.25), CH_DRUMS)
        # Conga pattern
        add_note(drums, CONGA_HIGH, v(80), base + t(mid, 0.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_LOW, v(75), base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_MUTE, v(70), base + t(mid, 1.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_HIGH, v(80), base + t(mid, 2.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_LOW, v(70), base + t(mid, 3.5), t(mid, 0.25), CH_DRUMS)

    # --- Helper: walking bass pattern (2 bars) ---
    def walking_bass_2bar(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        # D2=38, F2=41, G2=43, A2=45, Bb2=46, C3=48
        base = bar_start(mid, start_bar)
        pattern = [
            (0.0, 38, 100, 0.5), (0.5, 38, 60, 0.25), (1.0, 41, 85, 0.5),
            (1.5, 43, 75, 0.5), (2.0, 45, 90, 0.5), (2.5, 43, 70, 0.5),
            (3.0, 41, 85, 0.5), (3.5, 38, 75, 0.5),
            (4.0, 38, 100, 0.5), (4.5, 40, 75, 0.5), (5.0, 41, 90, 0.5),
            (5.5, 42, 65, 0.25), (6.0, 43, 85, 0.5), (6.5, 45, 75, 0.5),
            (7.0, 46, 80, 0.5), (7.5, 45, 75, 0.5),
        ]
        for beat, note, vel, dur in pattern:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, dur), CH_BASS)

    # --- Dm pentatonic phrases ---
    # D4=62, F4=65, G4=67, A4=69, C5=72
    def guitar_lead_phrase_a(start_bar, vel_mult=1.0):
        """Ascending slinky run - signature Santana."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        notes = [
            (0.0, 62, 90, 0.75), (0.75, 65, 85, 0.5), (1.25, 67, 88, 0.5),
            (1.75, 69, 92, 1.0), (3.0, 72, 85, 1.0),
            (4.0, 72, 88, 0.5), (4.5, 69, 85, 0.5), (5.0, 67, 90, 1.0),
            (6.0, 65, 80, 0.75), (6.75, 62, 85, 1.25),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_lead_phrase_b(start_bar, vel_mult=1.0):
        """Staccato hits + bluesy resolution."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        notes = [
            (0.0, 62, 95, 0.25), (0.5, 65, 90, 0.25), (1.0, 67, 92, 0.25),
            (1.5, 69, 88, 0.5), (2.0, 72, 95, 0.75), (2.75, 69, 85, 0.5),
            (3.25, 67, 80, 0.75),
            (4.0, 65, 88, 0.5), (4.5, 63, 82, 0.5), (5.0, 62, 90, 1.5),
            (6.5, 60, 75, 0.5), (7.0, 62, 95, 1.0),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_comp_verse(start_bar, vel_mult=1.0):
        """Rhythmic chord comps Dm - quieter."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # Dm voicing: D3(50), F3(53), A3(57)
        for beat_off in [0.0, 1.5, 2.0, 3.5]:
            for n in [50, 53, 57]:
                add_note(guitar, n, v(75), base + t(mid, beat_off), t(mid, 0.5), CH_GUITAR)

    def guitar_chorus_riff(start_bar, vel_mult=1.0):
        """Louder chorus riff - big Dm pentatonic."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        notes = [
            (0.0, 62, 105, 0.5), (0.5, 65, 100, 0.5), (1.0, 69, 108, 1.0),
            (2.0, 72, 110, 0.75), (2.75, 69, 100, 0.5), (3.25, 67, 95, 0.75),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_solo_phrase(start_bar, phrase_idx, vel_mult=1.0):
        """Carlos Santana-style sustained bends and pentatonic runs."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        phrases = [
            # Phrase 0: sustained bend on A4, descend
            [(0.0, 69, 100, 2.0), (2.0, 72, 95, 1.0), (3.0, 69, 90, 1.0),
             (4.0, 67, 95, 1.5), (5.5, 65, 85, 0.5), (6.0, 62, 90, 2.0)],
            # Phrase 1: fast run up, sustain at top
            [(0.0, 62, 95, 0.25), (0.25, 65, 90, 0.25), (0.5, 67, 92, 0.25),
             (0.75, 69, 95, 0.25), (1.0, 72, 100, 2.5), (3.5, 74, 105, 0.5),
             (4.0, 72, 98, 1.0), (5.0, 69, 90, 1.0), (6.0, 67, 85, 1.0), (7.0, 65, 80, 1.0)],
            # Phrase 2: call and response - high cry
            [(0.0, 74, 105, 1.5), (1.5, 72, 95, 0.5), (2.0, 69, 90, 1.0),
             (3.5, 67, 85, 0.5), (4.0, 72, 100, 2.0), (6.0, 74, 105, 1.0), (7.0, 72, 95, 1.0)],
            # Phrase 3: bluesy resolution with vibrato feel
            [(0.0, 72, 100, 0.5), (0.5, 69, 95, 0.5), (1.0, 67, 90, 0.5),
             (1.5, 65, 88, 0.5), (2.0, 63, 85, 0.5), (2.5, 62, 90, 1.5),
             (4.0, 62, 95, 3.0), (7.0, 62, 80, 1.0)],
        ]
        phrase = phrases[phrase_idx % len(phrases)]
        for beat, note, vel, dur in phrase:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    # === INTRO (bars 0-3): Guitar lead alone ===
    guitar_lead_phrase_a(0, 0.95)
    guitar_lead_phrase_b(2, 0.95)

    # === VERSE 1 (bars 4-11): Full band, verse dynamics ===
    for b in range(VERSE1[0], VERSE1[1]):
        latin_drums(b, vel_mult=0.85, has_crash=(b == VERSE1[0]))
        guitar_comp_verse(b, 0.85)
    for pair in range(4):
        walking_bass_2bar(VERSE1[0] + pair * 2, 0.85)

    # === CHORUS 1 (bars 12-15): Big hits, crash on 1, louder ===
    for b in range(CHORUS1[0], CHORUS1[1]):
        latin_drums(b, vel_mult=1.1, has_crash=True)
        guitar_chorus_riff(b, 1.1)
    for pair in range(2):
        walking_bass_2bar(CHORUS1[0] + pair * 2, 1.05)

    # === SOLO (bars 16-23): Santana sustained bends ===
    for b in range(SOLO[0], SOLO[1]):
        latin_drums(b, vel_mult=0.95, has_crash=(b == SOLO[0]))
    for pair in range(4):
        walking_bass_2bar(SOLO[0] + pair * 2, 0.95)
    for i in range(4):
        guitar_solo_phrase(SOLO[0] + i * 2, i, 1.0)

    # === VERSE 2 (bars 24-31): Same as verse 1 ===
    for b in range(VERSE2[0], VERSE2[1]):
        latin_drums(b, vel_mult=0.88, has_crash=(b == VERSE2[0]))
        guitar_comp_verse(b, 0.88)
    for pair in range(4):
        walking_bass_2bar(VERSE2[0] + pair * 2, 0.88)

    # === OUTRO (bars 32-35): Guitar lead returns, fade ===
    for b in range(OUTRO[0], OUTRO[1]):
        fade = 1.0 - (b - OUTRO[0]) * 0.15
        latin_drums(b, vel_mult=fade * 0.9)
    guitar_lead_phrase_a(32, 0.9)
    walking_bass_2bar(32, 0.85)
    walking_bass_2bar(34, 0.7)

    # --- Humanization: Santana Latin percussion feel ---
    random.seed(42)  # reproducible
    # Drums: heavy swing, ghost 16th hats, flams, conga ghost fills
    humanize_events(drums, swing=0.22, timing_jitter=8, velocity_jitter=6,
                    ghost_notes=[
                        {'note': CLOSED_HAT, 'vel_range': (15, 25), 'every_n_ticks': ppq // 4, 'channel': CH_DRUMS, 'duration': int(ppq * 0.06)},
                    ],
                    flam_before_accents=True, accent_vel_threshold=100, ppq=ppq,
                    bar_length_beats=4, ride_ahead=-5)
    # Guitar: Santana bends on sustained lead notes
    humanize_events(guitar, swing=0.12, timing_jitter=6, velocity_jitter=5,
                    ppq=ppq, bar_length_beats=4)
    add_guitar_bend(guitar, ppq=ppq, channel=CH_GUITAR, bend_semitones=1, bend_duration_ticks=100)
    # Bass: ghost notes between main notes, slight swing
    humanize_events(bass, swing=0.15, timing_jitter=5, velocity_jitter=4,
                    ppq=ppq, bar_length_beats=4,
                    micro_timing={38: {'jitter': 4, 'accent_beats': [0, 2], 'accent_boost': 8, 'soften_offbeats': 6}})
    add_bass_ghost_notes(bass, ppq=ppq, vel_range=(30, 40), channel=CH_BASS)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Black Magic Woman", "Santana", bpm, "Dm", total_bars, 3,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Black Magic Woman ({total_bars} bars)")


# ========================================================================
# 2. SANTANA - SMOOTH (BPM 116, Am, 4/4, 32 bars)
# Structure: INTRO(4) VERSE(8) CHORUS(4) VERSE2(8) SOLO(4) CHORUS2(4)
# ========================================================================
def gen_smooth():
    bpm = 116
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "smooth")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    total_bars = 32

    drums = []
    guitar = []
    bass = []

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    VERSE2 = (16, 24)
    SOLO = (24, 28)
    CHORUS2 = (28, 32)

    # --- Helper: Pop-latin drum bar ---
    def pop_latin_drums(bar, vel_mult=1.0, has_crash=False):
        base = bar_start(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        if has_crash:
            add_note(drums, CRASH, v(110), base, t(mid, 0.5), CH_DRUMS)
        add_note(drums, KICK, v(110), base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(95), base + t(mid, 1.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(100), base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(105), base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(105), base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Hi-hat 16ths
        for i in range(16):
            hv = 75 if i % 4 == 0 else (60 if i % 2 == 0 else 45)
            add_note(drums, CLOSED_HAT, v(hv), base + t(mid, i * 0.25), t(mid, 0.125), CH_DRUMS)

    # --- Bass: Am-F-E7 pattern (4 bars) ---
    def smooth_bass_4bar(start_bar, vel_mult=1.0, syncopated=False):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # A2=45, C3=48, G2=43, F2=41, E2=40, G#2=44
        pattern = [
            # Bar 1-2: Am
            (0.0, 45, 100, 0.5), (0.5, 45, 55, 0.25), (1.0, 48, 85, 0.5),
            (1.5, 45, 60, 0.25), (2.0, 45, 95, 0.5), (2.5, 43, 80, 0.5),
            (3.0, 45, 90, 0.5), (3.5, 45, 55, 0.25),
            (4.0, 45, 100, 0.5), (4.5, 47, 75, 0.5), (5.0, 48, 85, 0.5),
            (5.5, 48, 55, 0.25), (6.0, 45, 90, 0.5), (6.5, 43, 75, 0.5),
            (7.0, 45, 95, 0.5), (7.5, 45, 60, 0.25),
            # Bar 3: F
            (8.0, 41, 100, 0.5), (8.5, 41, 55, 0.25), (9.0, 45, 85, 0.5),
            (9.5, 41, 60, 0.25), (10.0, 41, 95, 0.5), (10.5, 43, 75, 0.5),
            (11.0, 45, 85, 0.5), (11.5, 43, 70, 0.5),
            # Bar 4: E7
            (12.0, 40, 100, 0.5), (12.5, 40, 55, 0.25), (13.0, 44, 85, 0.5),
            (13.5, 40, 60, 0.25), (14.0, 40, 95, 0.5), (14.5, 42, 75, 0.5),
            (15.0, 44, 85, 0.5), (15.5, 45, 80, 0.5),
        ]
        if syncopated:
            # Add extra ghost notes for verse 2
            extras = [
                (0.75, 45, 45, 0.15), (2.75, 43, 45, 0.15),
                (4.75, 48, 45, 0.15), (8.75, 41, 45, 0.15),
            ]
            pattern.extend(extras)
        for beat, note, vel, dur in pattern:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, dur), CH_BASS)

    # --- Guitar: Am arpeggio riff (signature intro/verse) ---
    def guitar_am_arpeggio(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # A3=57, C4=60, E4=64, A4=69, C5=72
        notes = [
            (0.0, 57, 90, 0.5), (0.5, 60, 85, 0.5), (1.0, 64, 88, 0.5),
            (1.5, 69, 92, 0.75), (2.25, 72, 85, 0.5), (2.75, 69, 80, 0.5),
            (3.25, 64, 82, 0.75),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_descending_run(start_bar, vel_mult=1.0):
        """The signature smooth descending lick."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        notes = [
            (0.0, 69, 88, 0.25), (0.25, 67, 85, 0.25), (0.5, 65, 82, 0.25),
            (0.75, 64, 85, 0.25), (1.0, 62, 80, 0.25), (1.25, 60, 82, 0.25),
            (1.5, 59, 78, 0.25), (1.75, 57, 85, 1.0), (3.0, 57, 70, 0.5),
            (3.5, 60, 72, 0.5),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_f_chord_bar(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # F3=53, A3=57, C4=60, F4=65
        notes = [
            (0.0, 53, 88, 0.5), (0.5, 57, 82, 0.5), (1.0, 60, 85, 0.5),
            (1.5, 65, 90, 0.5), (2.0, 60, 80, 0.5), (2.5, 57, 75, 0.5),
            (3.0, 53, 82, 0.5), (3.5, 57, 78, 0.5),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_e7_chord_bar(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # E3=52, G#3=56, B3=59, D4=62
        notes = [
            (0.0, 52, 90, 0.5), (0.5, 56, 85, 0.5), (1.0, 59, 88, 0.5),
            (1.5, 62, 92, 0.75), (2.25, 64, 85, 0.25), (2.5, 62, 80, 0.5),
            (3.0, 59, 82, 0.5), (3.5, 56, 78, 0.5),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_chorus_big(start_bar, vel_mult=1.0):
        """Bigger chorus — descending guitar run with power."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        notes = [
            (0.0, 72, 105, 0.25), (0.25, 69, 100, 0.25), (0.5, 67, 98, 0.25),
            (0.75, 65, 95, 0.25), (1.0, 64, 100, 1.0), (2.0, 60, 95, 0.5),
            (2.5, 57, 90, 0.5), (3.0, 60, 100, 1.0),
        ]
        for beat, note, vel, dur in notes:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_solo_am(start_bar, phrase_idx, vel_mult=1.0):
        """Am pentatonic solo phrases."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        phrases = [
            [(0.0, 69, 100, 0.25), (0.25, 72, 95, 0.25), (0.5, 74, 98, 0.25),
             (0.75, 72, 92, 0.5), (1.25, 69, 88, 0.5), (1.75, 67, 85, 0.25),
             (2.0, 69, 95, 2.0)],
            [(0.0, 72, 100, 1.5), (1.5, 74, 105, 0.5), (2.0, 72, 95, 0.5),
             (2.5, 69, 90, 0.5), (3.0, 67, 88, 0.5), (3.5, 64, 85, 0.5)],
        ]
        phrase = phrases[phrase_idx % len(phrases)]
        for beat, note, vel, dur in phrase:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    # === INTRO (bars 0-3): Am guitar riff alone ===
    guitar_am_arpeggio(0, 0.95)
    guitar_descending_run(1, 0.95)
    guitar_am_arpeggio(2, 0.95)
    guitar_descending_run(3, 0.95)

    # === VERSE 1 (bars 4-11): Full band, verse dynamics ===
    for b in range(VERSE1[0], VERSE1[1]):
        pop_latin_drums(b, vel_mult=0.85, has_crash=(b == VERSE1[0]))
        bar_in_section = (b - VERSE1[0]) % 4
        if bar_in_section < 1:
            guitar_am_arpeggio(b, 0.82)
        elif bar_in_section == 1:
            guitar_descending_run(b, 0.82)
        elif bar_in_section == 2:
            guitar_f_chord_bar(b, 0.82)
        else:
            guitar_e7_chord_bar(b, 0.82)
    smooth_bass_4bar(4, 0.85)
    smooth_bass_4bar(8, 0.85)

    # === CHORUS 1 (bars 12-15): Bigger, crash every 2 bars ===
    for b in range(CHORUS1[0], CHORUS1[1]):
        pop_latin_drums(b, vel_mult=1.1, has_crash=(b % 2 == 0))
        guitar_chorus_big(b, 1.05)
    smooth_bass_4bar(12, 1.05)

    # === VERSE 2 (bars 16-23): Same pattern, bass more syncopated ===
    for b in range(VERSE2[0], VERSE2[1]):
        pop_latin_drums(b, vel_mult=0.88, has_crash=(b == VERSE2[0]))
        bar_in_section = (b - VERSE2[0]) % 4
        if bar_in_section < 1:
            guitar_am_arpeggio(b, 0.85)
        elif bar_in_section == 1:
            guitar_descending_run(b, 0.85)
        elif bar_in_section == 2:
            guitar_f_chord_bar(b, 0.85)
        else:
            guitar_e7_chord_bar(b, 0.85)
    smooth_bass_4bar(16, 0.88, syncopated=True)
    smooth_bass_4bar(20, 0.88, syncopated=True)

    # === SOLO (bars 24-27): Am pentatonic lead ===
    for b in range(SOLO[0], SOLO[1]):
        pop_latin_drums(b, vel_mult=0.95, has_crash=(b == SOLO[0]))
        guitar_solo_am(b, b - SOLO[0], 1.0)
    smooth_bass_4bar(24, 0.95)

    # === CHORUS 2 (bars 28-31): Biggest ending ===
    for b in range(CHORUS2[0], CHORUS2[1]):
        pop_latin_drums(b, vel_mult=1.15, has_crash=True)
        guitar_chorus_big(b, 1.12)
    smooth_bass_4bar(28, 1.1)

    # --- Humanization: Santana pop-latin, ghost notes, bass slides ---
    random.seed(43)
    # Drums: Latin swing, ghost 16th hats underneath everything
    humanize_events(drums, swing=0.20, timing_jitter=7, velocity_jitter=5,
                    ghost_notes=[
                        {'note': CLOSED_HAT, 'vel_range': (15, 25), 'every_n_ticks': ppq // 4, 'channel': CH_DRUMS, 'duration': int(ppq * 0.06)},
                    ],
                    flam_before_accents=True, accent_vel_threshold=100, ppq=ppq,
                    bar_length_beats=4, ride_ahead=-5)
    # Guitar: light swing, bends on sustained Santana lead
    humanize_events(guitar, swing=0.10, timing_jitter=6, velocity_jitter=5,
                    ppq=ppq, bar_length_beats=4)
    add_guitar_bend(guitar, ppq=ppq, channel=CH_GUITAR, bend_semitones=1, bend_duration_ticks=100)
    # Bass: ghost notes vel 30-40 between main notes, slides as quick chromatic runs
    humanize_events(bass, swing=0.12, timing_jitter=5, velocity_jitter=4,
                    ppq=ppq, bar_length_beats=4)
    add_bass_ghost_notes(bass, ppq=ppq, vel_range=(30, 40), channel=CH_BASS)
    add_bass_slide(bass, ppq=ppq, channel=CH_BASS)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Smooth", "Santana", bpm, "Am", total_bars, 3,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Smooth ({total_bars} bars)")


# ========================================================================
# 3. SANTANA - EVIL WAYS (BPM 124, Gm, 4/4, 32 bars)
# Structure: INTRO(4) VERSE(8) CHORUS(4) SOLO(4) VERSE2(8) OUTRO(4)
# ========================================================================
def gen_evil_ways():
    bpm = 124
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "evil_ways")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    total_bars = 32

    drums = []
    keys = []
    bass = []

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    SOLO = (16, 20)
    VERSE2 = (20, 28)
    OUTRO = (28, 32)

    # --- Helper: Latin shuffle drums ---
    def latin_shuffle_drums(bar, vel_mult=1.0, has_crash=False):
        base = bar_start(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        if has_crash:
            add_note(drums, CRASH, v(110), base, t(mid, 0.5), CH_DRUMS)
        add_note(drums, KICK, v(105), base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(95), base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SIDE_STICK, v(90), base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SIDE_STICK, v(90), base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Timbale shuffle 8ths
        for i in range(8):
            swing = 0.08 if i % 2 == 1 else 0
            hv = 80 if i % 2 == 0 else 55
            add_note(drums, TIMBALE_HIGH, v(hv),
                     base + t(mid, i * 0.5 + swing), t(mid, 0.2), CH_DRUMS)
        # Conga
        add_note(drums, CONGA_HIGH, v(85), base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_MUTE, v(70), base + t(mid, 0.5), t(mid, 0.2), CH_DRUMS)
        add_note(drums, CONGA_LOW, v(80), base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_HIGH, v(75), base + t(mid, 1.75), t(mid, 0.2), CH_DRUMS)
        add_note(drums, CONGA_LOW, v(80), base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_MUTE, v(65), base + t(mid, 2.5), t(mid, 0.2), CH_DRUMS)
        add_note(drums, CONGA_HIGH, v(85), base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_LOW, v(70), base + t(mid, 3.5), t(mid, 0.2), CH_DRUMS)
        # Cowbell
        add_note(drums, COWBELL, v(70), base + t(mid, 1.5), t(mid, 0.2), CH_DRUMS)
        add_note(drums, COWBELL, v(70), base + t(mid, 3.5), t(mid, 0.2), CH_DRUMS)

    # --- Organ: Gm7-C7 vamp ---
    def organ_gm7_bar(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # Gm7: G3(55) Bb3(58) D4(62)
        for beat_off in [0.0, 1.5, 2.0, 3.5]:
            dur = 0.75 if beat_off in [0.0, 2.0] else 0.5
            vel = 88 if beat_off in [0.0, 2.0] else 75
            for n in [55, 58, 62]:
                add_note(keys, n, v(vel), base + t(mid, beat_off), t(mid, dur), CH_KEYS)

    def organ_c7_bar(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # C7: C3(48) E3(52) G3(55) Bb3(58)
        for beat_off in [0.0, 1.5, 2.0, 3.5]:
            dur = 0.75 if beat_off in [0.0, 2.0] else 0.5
            vel = 88 if beat_off in [0.0, 2.0] else 75
            chord = [48, 52, 55] if beat_off != 3.5 else [50, 53, 57]
            for n in chord:
                add_note(keys, n, v(vel), base + t(mid, beat_off), t(mid, dur), CH_KEYS)

    def organ_solo_phrase(start_bar, phrase_idx, vel_mult=1.0):
        """Organ solo over Gm7-C7 vamp."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        phrases = [
            # Phrase 0: bluesy Gm run
            [(0.0, 67, 95, 0.5), (0.5, 65, 90, 0.25), (0.75, 62, 88, 0.5),
             (1.25, 58, 85, 0.75), (2.0, 55, 90, 1.0), (3.0, 58, 85, 0.5),
             (3.5, 62, 88, 0.5)],
            # Phrase 1: C7 resolution
            [(0.0, 60, 92, 0.5), (0.5, 64, 88, 0.5), (1.0, 67, 95, 1.0),
             (2.0, 65, 90, 0.5), (2.5, 62, 85, 0.5), (3.0, 60, 88, 1.0)],
        ]
        phrase = phrases[phrase_idx % len(phrases)]
        for beat, note, vel, dur in phrase:
            add_note(keys, note, v(vel), base + t(mid, beat), t(mid, dur), CH_KEYS)

    # --- Bass: Gm-C chromatic ---
    def evil_bass_2bar(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # G2=43, Bb2=46, A2=45, B2=47, C3=48, D3=50, F#2=42
        pattern = [
            (0.0, 43, 100, 0.5), (0.5, 43, 60, 0.25), (1.0, 46, 85, 0.5),
            (1.5, 43, 70, 0.5), (2.0, 45, 90, 0.5), (2.5, 46, 80, 0.5),
            (3.0, 47, 85, 0.5), (3.5, 47, 55, 0.25),
            (4.0, 48, 100, 0.5), (4.5, 48, 60, 0.25), (5.0, 50, 85, 0.5),
            (5.5, 48, 70, 0.5), (6.0, 46, 90, 0.5), (6.5, 45, 80, 0.5),
            (7.0, 43, 85, 0.5), (7.5, 42, 75, 0.5),
        ]
        for beat, note, vel, dur in pattern:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, dur), CH_BASS)

    # === INTRO (bars 0-3): Organ Gm7-C7 vamp alone ===
    for b in range(INTRO[0], INTRO[1]):
        if b % 2 == 0:
            organ_gm7_bar(b, 0.9)
        else:
            organ_c7_bar(b, 0.9)

    # === VERSE 1 (bars 4-11): Full band ===
    for b in range(VERSE1[0], VERSE1[1]):
        latin_shuffle_drums(b, vel_mult=0.85, has_crash=(b == VERSE1[0]))
        if b % 2 == 0:
            organ_gm7_bar(b, 0.85)
        else:
            organ_c7_bar(b, 0.85)
    for pair in range(4):
        evil_bass_2bar(VERSE1[0] + pair * 2, 0.85)

    # === CHORUS (bars 12-15): Louder, crash hits ===
    for b in range(CHORUS1[0], CHORUS1[1]):
        latin_shuffle_drums(b, vel_mult=1.1, has_crash=True)
        if b % 2 == 0:
            organ_gm7_bar(b, 1.1)
        else:
            organ_c7_bar(b, 1.1)
    evil_bass_2bar(12, 1.05)
    evil_bass_2bar(14, 1.05)

    # === SOLO (bars 16-19): Organ solo over the vamp ===
    for b in range(SOLO[0], SOLO[1]):
        latin_shuffle_drums(b, vel_mult=0.95, has_crash=(b == SOLO[0]))
        organ_solo_phrase(b, b - SOLO[0], 1.0)
    evil_bass_2bar(16, 0.95)
    evil_bass_2bar(18, 0.95)

    # === VERSE 2 (bars 20-27) ===
    for b in range(VERSE2[0], VERSE2[1]):
        latin_shuffle_drums(b, vel_mult=0.88, has_crash=(b == VERSE2[0]))
        if b % 2 == 0:
            organ_gm7_bar(b, 0.88)
        else:
            organ_c7_bar(b, 0.88)
    for pair in range(4):
        evil_bass_2bar(VERSE2[0] + pair * 2, 0.88)

    # === OUTRO (bars 28-31): Organ vamp fades ===
    for b in range(OUTRO[0], OUTRO[1]):
        fade = 1.0 - (b - OUTRO[0]) * 0.15
        latin_shuffle_drums(b, vel_mult=fade * 0.85)
        if b % 2 == 0:
            organ_gm7_bar(b, fade * 0.9)
        else:
            organ_c7_bar(b, fade * 0.9)
    evil_bass_2bar(28, 0.8)
    evil_bass_2bar(30, 0.65)

    # --- Humanization: Santana Latin shuffle, ghost hats, organ swing ---
    random.seed(44)
    # Drums: heavy Latin swing, ghost 16th hat layer, flams
    humanize_events(drums, swing=0.25, timing_jitter=8, velocity_jitter=6,
                    ghost_notes=[
                        {'note': CLOSED_HAT, 'vel_range': (15, 25), 'every_n_ticks': ppq // 4, 'channel': CH_DRUMS, 'duration': int(ppq * 0.06)},
                    ],
                    flam_before_accents=True, accent_vel_threshold=100, ppq=ppq,
                    bar_length_beats=4, ride_ahead=-5)
    # Keys: light swing for organ comps
    humanize_events(keys, swing=0.15, timing_jitter=5, velocity_jitter=4,
                    ppq=ppq, bar_length_beats=4)
    # Bass: syncopated kick push, ghost notes
    humanize_events(bass, swing=0.18, timing_jitter=6, velocity_jitter=4,
                    ppq=ppq, bar_length_beats=4)
    add_bass_ghost_notes(bass, ppq=ppq, vel_range=(30, 40), channel=CH_BASS)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, keys, os.path.join(song_dir, "keys.mid"), "Keys", CH_KEYS)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Keys", keys), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Evil Ways", "Santana", bpm, "Gm", total_bars, 2,
               ["drums", "keys", "bass"])
    print(f"  [OK] Evil Ways ({total_bars} bars)")


# ========================================================================
# 4. MUSE - HYSTERIA (BPM 94, Am, 4/4, 34 bars)
# Structure: INTRO(4) VERSE(8) CHORUS(4) VERSE2(8) SOLO(4) CHORUS2(4) OUTRO(2)
# ========================================================================
def gen_hysteria():
    bpm = 94
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "hysteria")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    total_bars = 34

    drums = []
    guitar = []
    bass = []

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    VERSE2 = (16, 24)
    SOLO = (24, 28)
    CHORUS2 = (28, 32)
    OUTRO = (32, 34)

    # --- THE bass riff: A2-E3-A3-G3-F3-E3-D3-C3 in 16ths ---
    def hysteria_bass_riff(start_bar, vel_mult=1.0):
        """The iconic Hysteria bass riff - 2 bars of 16th notes."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # A2=45, E3=52, A3=57, G3=55, F3=53, E3=52, D3=50, C3=48, B2=47
        riff = [
            # Bar 1: A2-A2-E3-E3-A3-G3-F3-E3-D3-C3-A2-C3-D3-E3-F3-E3
            (0.0, 45, 100), (0.25, 45, 85), (0.5, 52, 95), (0.75, 52, 80),
            (1.0, 57, 100), (1.25, 55, 90), (1.5, 53, 95), (1.75, 52, 85),
            (2.0, 50, 100), (2.25, 48, 90), (2.5, 45, 95), (2.75, 48, 85),
            (3.0, 50, 100), (3.25, 52, 90), (3.5, 53, 95), (3.75, 52, 85),
            # Bar 2: variation with octave jump
            (4.0, 45, 100), (4.25, 45, 85), (4.5, 52, 95), (4.75, 52, 80),
            (5.0, 57, 100), (5.25, 57, 85), (5.5, 55, 95), (5.75, 53, 90),
            (6.0, 52, 100), (6.25, 50, 90), (6.5, 48, 95), (6.75, 47, 85),
            (7.0, 45, 100), (7.25, 47, 85), (7.5, 48, 90), (7.75, 50, 85),
        ]
        for beat, note, vel in riff:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, 0.2), CH_BASS)

    def hysteria_bass_riff_shifted(start_bar, vel_mult=1.0):
        """Chorus variation — bass riff shifts to G-D pattern."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # G2=43, D3=50, G3=55, F3=53, E3=52, D3=50, C3=48
        riff = [
            (0.0, 43, 100), (0.25, 43, 85), (0.5, 50, 95), (0.75, 50, 80),
            (1.0, 55, 100), (1.25, 53, 90), (1.5, 52, 95), (1.75, 50, 85),
            (2.0, 48, 100), (2.25, 45, 90), (2.5, 43, 95), (2.75, 45, 85),
            (3.0, 48, 100), (3.25, 50, 90), (3.5, 52, 95), (3.75, 50, 85),
            (4.0, 38, 100), (4.25, 38, 85), (4.5, 45, 95), (4.75, 45, 80),
            (5.0, 50, 100), (5.25, 48, 90), (5.5, 45, 95), (5.75, 43, 90),
            (6.0, 45, 100), (6.25, 43, 90), (6.5, 41, 95), (6.75, 43, 85),
            (7.0, 45, 100), (7.25, 43, 85), (7.5, 41, 90), (7.75, 43, 85),
        ]
        for beat, note, vel in riff:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, 0.2), CH_BASS)

    # --- Drums: Machine-gun 16th kicks ---
    def hysteria_drums(bar, vel_mult=1.0, has_crash=False, machine_gun=True):
        base = bar_start(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        if has_crash:
            add_note(drums, CRASH, v(110), base, t(mid, 0.5), CH_DRUMS)
        if machine_gun:
            for i in range(16):
                kv = 110 if i % 4 == 0 else (95 if i % 4 == 2 else 80)
                add_note(drums, KICK, v(kv), base + t(mid, i * 0.25), t(mid, 0.125), CH_DRUMS)
        else:
            # Simpler kick for intro/outro
            add_note(drums, KICK, v(100), base, t(mid, 0.25), CH_DRUMS)
            add_note(drums, KICK, v(90), base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(110), base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(110), base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        for i in range(8):
            hv = 70 if i % 2 == 0 else 50
            add_note(drums, CLOSED_HAT, v(hv), base + t(mid, i * 0.5), t(mid, 0.2), CH_DRUMS)

    # --- Guitar: Am-E sustained chords, G-D power chords ---
    def guitar_verse_chords(start_bar, vel_mult=1.0, palm_muted=False):
        """Am-E sustained chords over 2 bars."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # Am: A3(57)+E4(64), E5: E3(52)+B3(59)
        # Bar 1: Am sustained
        for n in [57, 64]:
            add_note(guitar, n, v(90), base, t(mid, 1.5), CH_GUITAR)
            add_note(guitar, n, v(75), base + t(mid, 2.0), t(mid, 1.5), CH_GUITAR)
        if palm_muted:
            for pm in range(8):
                add_note(guitar, 57, v(45), base + t(mid, pm * 0.5 + 0.25), t(mid, 0.15), CH_GUITAR)
        # Bar 2: E sustained
        base2 = bar_start(mid, start_bar + 1)
        for n in [52, 59]:
            add_note(guitar, n, v(90), base2, t(mid, 1.5), CH_GUITAR)
            add_note(guitar, n, v(75), base2 + t(mid, 2.0), t(mid, 1.5), CH_GUITAR)
        if palm_muted:
            for pm in range(8):
                add_note(guitar, 52, v(45), base2 + t(mid, pm * 0.5 + 0.25), t(mid, 0.15), CH_GUITAR)

    def guitar_chorus_power(start_bar, vel_mult=1.0):
        """G-D power chords for chorus — full distortion."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # G5: G3(55)+D4(62), D5: D3(50)+A3(57)
        # Bar 1: G power chord hits
        for n in [55, 62]:
            add_note(guitar, n, v(105), base, t(mid, 0.75), CH_GUITAR)
            add_note(guitar, n, v(100), base + t(mid, 1.0), t(mid, 0.75), CH_GUITAR)
            add_note(guitar, n, v(105), base + t(mid, 2.0), t(mid, 0.75), CH_GUITAR)
            add_note(guitar, n, v(100), base + t(mid, 3.0), t(mid, 1.0), CH_GUITAR)
        # Bar 2: D power chord
        base2 = bar_start(mid, start_bar + 1)
        for n in [50, 57]:
            add_note(guitar, n, v(105), base2, t(mid, 0.75), CH_GUITAR)
            add_note(guitar, n, v(100), base2 + t(mid, 1.0), t(mid, 0.75), CH_GUITAR)
            add_note(guitar, n, v(105), base2 + t(mid, 2.0), t(mid, 0.75), CH_GUITAR)
            add_note(guitar, n, v(100), base2 + t(mid, 3.0), t(mid, 1.0), CH_GUITAR)

    def guitar_solo_shred(start_bar, phrase_idx, vel_mult=1.0):
        """Am pentatonic shred over the bass riff."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        phrases = [
            # Fast ascending run
            [(0.0, 69, 100, 0.25), (0.25, 72, 95, 0.25), (0.5, 74, 98, 0.25),
             (0.75, 76, 100, 0.25), (1.0, 77, 105, 1.5), (2.5, 76, 95, 0.5),
             (3.0, 74, 90, 0.5), (3.5, 72, 88, 0.5)],
            # Sustained bend and vibrato
            [(0.0, 74, 105, 2.0), (2.0, 72, 95, 0.5), (2.5, 69, 90, 0.5),
             (3.0, 67, 88, 0.5), (3.5, 69, 92, 0.5)],
            # Descending shred
            [(0.0, 77, 100, 0.25), (0.25, 76, 95, 0.25), (0.5, 74, 98, 0.25),
             (0.75, 72, 95, 0.25), (1.0, 69, 100, 0.25), (1.25, 67, 95, 0.25),
             (1.5, 64, 98, 0.25), (1.75, 62, 95, 0.25), (2.0, 60, 100, 2.0)],
            # Resolution
            [(0.0, 69, 105, 1.0), (1.0, 72, 100, 1.0), (2.0, 69, 95, 1.0),
             (3.0, 64, 90, 0.5), (3.5, 57, 95, 0.5)],
        ]
        phrase = phrases[phrase_idx % len(phrases)]
        for beat, note, vel, dur in phrase:
            add_note(guitar, note, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    # === INTRO (bars 0-3): THE bass riff alone ===
    hysteria_bass_riff(0, 1.0)
    hysteria_bass_riff(2, 1.0)

    # === VERSE 1 (bars 4-11): Machine-gun drums enter, bass continues, guitar Am-E ===
    for b in range(VERSE1[0], VERSE1[1]):
        hysteria_drums(b, vel_mult=0.88, has_crash=(b == VERSE1[0]))
    for pair in range(4):
        hysteria_bass_riff(VERSE1[0] + pair * 2, 0.9)
        guitar_verse_chords(VERSE1[0] + pair * 2, 0.85)

    # === CHORUS 1 (bars 12-15): Full distortion, G-D, crash every beat ===
    for b in range(CHORUS1[0], CHORUS1[1]):
        hysteria_drums(b, vel_mult=1.1, has_crash=True)
    hysteria_bass_riff_shifted(12, 1.05)
    hysteria_bass_riff_shifted(14, 1.05)
    guitar_chorus_power(12, 1.1)
    guitar_chorus_power(14, 1.1)

    # === VERSE 2 (bars 16-23): Same but guitar adds palm-muted 8ths ===
    for b in range(VERSE2[0], VERSE2[1]):
        hysteria_drums(b, vel_mult=0.9, has_crash=(b == VERSE2[0]))
    for pair in range(4):
        hysteria_bass_riff(VERSE2[0] + pair * 2, 0.92)
        guitar_verse_chords(VERSE2[0] + pair * 2, 0.88, palm_muted=True)

    # === SOLO (bars 24-27): Guitar Am pentatonic shred over bass riff ===
    for b in range(SOLO[0], SOLO[1]):
        hysteria_drums(b, vel_mult=0.95, has_crash=(b == SOLO[0]))
        guitar_solo_shred(b, b - SOLO[0], 1.0)
    hysteria_bass_riff(24, 0.95)
    hysteria_bass_riff(26, 0.95)

    # === CHORUS 2 (bars 28-31): Biggest section, everything loud ===
    for b in range(CHORUS2[0], CHORUS2[1]):
        hysteria_drums(b, vel_mult=1.15, has_crash=True)
    hysteria_bass_riff_shifted(28, 1.1)
    hysteria_bass_riff_shifted(30, 1.1)
    guitar_chorus_power(28, 1.15)
    guitar_chorus_power(30, 1.15)

    # === OUTRO (bars 32-33): Bass riff alone, stops ===
    hysteria_bass_riff(32, 0.9)

    # --- Humanization: Muse - Dom Howard tight/aggressive ---
    random.seed(45)
    # Drums: almost zero swing (machine-gun precision), velocity accents on downbeats
    # Ghost snare between backbeats, ghost kick 16ths, flams before accents
    humanize_events(drums, swing=0.02, timing_jitter=3, velocity_jitter=4,
                    flam_before_accents=True, accent_vel_threshold=105, ppq=ppq,
                    bar_length_beats=4,
                    micro_timing={KICK: {'jitter': 2, 'accent_beats': [0, 1, 2, 3], 'accent_boost': 12, 'soften_offbeats': 0}})
    add_ghost_snare_between_backbeats(drums, ppq=ppq, bar_length_beats=4, vel=30, channel=CH_DRUMS)
    add_ghost_kick_16ths(drums, ppq=ppq, bar_length_beats=4, vel=40, channel=CH_DRUMS)
    # Bass: THE riff — micro timing variation +/-5 ticks, alternating velocity,
    # slight crescendo through each bar
    humanize_events(bass, swing=0.0, timing_jitter=0, velocity_jitter=0,
                    ppq=ppq, bar_length_beats=4, crescendo_per_bar=2,
                    micro_timing={
                        45: {'jitter': 5, 'accent_beats': [0, 2], 'accent_boost': 10, 'soften_offbeats': 8},
                        52: {'jitter': 5, 'accent_beats': [0, 2], 'accent_boost': 10, 'soften_offbeats': 8},
                        57: {'jitter': 5, 'accent_beats': [0, 2], 'accent_boost': 10, 'soften_offbeats': 8},
                        55: {'jitter': 5, 'accent_beats': [1, 3], 'accent_boost': 8, 'soften_offbeats': 8},
                        53: {'jitter': 5, 'accent_beats': [1, 3], 'accent_boost': 8, 'soften_offbeats': 8},
                        50: {'jitter': 5, 'accent_beats': [0, 2], 'accent_boost': 10, 'soften_offbeats': 8},
                        48: {'jitter': 5, 'accent_beats': [1, 3], 'accent_boost': 8, 'soften_offbeats': 8},
                        47: {'jitter': 5, 'accent_beats': [1, 3], 'accent_boost': 6, 'soften_offbeats': 8},
                    })
    # Guitar: power chords tight but some hit 5 ticks early for aggression
    humanize_events(guitar, swing=0.0, timing_jitter=5, velocity_jitter=6,
                    ppq=ppq, bar_length_beats=4)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_full_midi(mid, [("Drums", drums), ("Bass", bass), ("Guitar", guitar)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Hysteria", "Muse", bpm, "Am", total_bars, 5,
               ["drums", "bass", "guitar"])
    print(f"  [OK] Hysteria ({total_bars} bars)")


# ========================================================================
# 5. MUSE - SUPERMASSIVE BLACK HOLE (BPM 120, Am, 4/4, 32 bars)
# Structure: INTRO(4) VERSE(8) CHORUS(4) VERSE2(8) BRIDGE(4) CHORUS2(4)
# ========================================================================
def gen_supermassive_black_hole():
    bpm = 120
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "supermassive_black_hole")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    total_bars = 32

    drums = []
    guitar = []
    bass = []

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    VERSE2 = (16, 24)
    BRIDGE = (24, 28)
    CHORUS2 = (28, 32)

    # --- Drums ---
    def smbh_drums(bar, vel_mult=1.0, has_crash=False, sparse=False):
        base = bar_start(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        if has_crash:
            add_note(drums, CRASH, v(110), base, t(mid, 0.5), CH_DRUMS)
        if sparse:
            # Bridge: sparse drums
            add_note(drums, KICK, v(90), base, t(mid, 0.25), CH_DRUMS)
            add_note(drums, SNARE, v(80), base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
            add_note(drums, CLOSED_HAT, v(60), base + t(mid, 1.0), t(mid, 0.2), CH_DRUMS)
            add_note(drums, CLOSED_HAT, v(55), base + t(mid, 3.0), t(mid, 0.2), CH_DRUMS)
            return
        # Syncopated funk kick
        add_note(drums, KICK, v(110), base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(85), base + t(mid, 0.75), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(100), base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(85), base + t(mid, 2.75), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(105), base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(105), base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Ghost snares
        add_note(drums, SNARE, v(40), base + t(mid, 0.5), t(mid, 0.1), CH_DRUMS)
        add_note(drums, SNARE, v(35), base + t(mid, 1.75), t(mid, 0.1), CH_DRUMS)
        add_note(drums, SNARE, v(40), base + t(mid, 2.5), t(mid, 0.1), CH_DRUMS)
        add_note(drums, SNARE, v(35), base + t(mid, 3.75), t(mid, 0.1), CH_DRUMS)
        # Hi-hat 16ths
        for i in range(16):
            hv = 80 if i % 4 == 0 else (60 if i % 2 == 0 else 40)
            add_note(drums, CLOSED_HAT, v(hv), base + t(mid, i * 0.25), t(mid, 0.125), CH_DRUMS)

    # --- Guitar: Funky Am staccato 16ths ---
    def guitar_funky_staccato(start_bar, vel_mult=1.0, wah_variation=False):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # A3=57, C4=60, E4=64
        for i in range(16):
            beat = i * 0.25
            if wah_variation:
                # Different accent pattern for "wah" effect
                if i % 3 == 0:
                    add_note(guitar, 60, v(92), base + t(mid, beat), t(mid, 0.15), CH_GUITAR)
                elif i % 5 == 0:
                    add_note(guitar, 64, v(88), base + t(mid, beat), t(mid, 0.15), CH_GUITAR)
                elif i % 2 == 0:
                    add_note(guitar, 57, v(85), base + t(mid, beat), t(mid, 0.15), CH_GUITAR)
                else:
                    add_note(guitar, 57, v(30), base + t(mid, beat), t(mid, 0.1), CH_GUITAR)
            else:
                if i % 4 == 0:
                    add_note(guitar, 57, v(95), base + t(mid, beat), t(mid, 0.15), CH_GUITAR)
                elif i % 4 == 2:
                    note = 60 if i % 8 == 2 else 64
                    add_note(guitar, note, v(88), base + t(mid, beat), t(mid, 0.15), CH_GUITAR)
                else:
                    add_note(guitar, 57, v(30), base + t(mid, beat), t(mid, 0.1), CH_GUITAR)

    def guitar_chorus_hits(start_bar, vel_mult=1.0):
        """Dm-Am-E7 chord hits."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # Dm: D4(62)+F4(65)+A4(69), Am: A3(57)+C4(60)+E4(64), E7: E3(52)+G#3(56)+B3(59)+D4(62)
        hits = [
            (0.0, [62, 65, 69], 105, 0.75),
            (1.0, [57, 60, 64], 100, 0.75),
            (2.0, [52, 56, 59, 62], 105, 0.75),
            (3.0, [57, 60, 64], 100, 0.75),
        ]
        for beat, notes, vel, dur in hits:
            for n in notes:
                add_note(guitar, n, v(vel), base + t(mid, beat), t(mid, dur), CH_GUITAR)

    def guitar_bridge_feedback(start_bar, vel_mult=1.0):
        """Sustained guitar feedback for bridge."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # Long sustained A4 with slight pitch variation
        add_note(guitar, 69, v(80), base, t(mid, 3.5), CH_GUITAR)
        add_note(guitar, 64, v(70), base + t(mid, 2.0), t(mid, 2.0), CH_GUITAR)

    def guitar_muted_scratch(start_bar, vel_mult=1.0):
        """Intro: funky muted guitar scratch + kick."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        for i in range(16):
            beat = i * 0.25
            if i % 4 == 0:
                add_note(guitar, 57, v(85), base + t(mid, beat), t(mid, 0.15), CH_GUITAR)
            else:
                add_note(guitar, 57, v(25), base + t(mid, beat), t(mid, 0.08), CH_GUITAR)

    # --- Bass: Octave-jump funk ---
    def smbh_bass(start_bar, vel_mult=1.0):
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        # A2=45, A3=57, G2=43, E2=40, C3=48, D3=50
        pattern = [
            (0.0, 45, 100, 0.25), (0.25, 45, 55, 0.15), (0.5, 57, 90, 0.25),
            (0.75, 45, 70, 0.25), (1.0, 45, 95, 0.5), (1.5, 43, 80, 0.25),
            (1.75, 45, 85, 0.25), (2.0, 45, 100, 0.25), (2.25, 45, 55, 0.15),
            (2.5, 57, 90, 0.25), (2.75, 55, 80, 0.25), (3.0, 45, 95, 0.5),
            (3.5, 43, 80, 0.25), (3.75, 45, 85, 0.25),
        ]
        for beat, note, vel, dur in pattern:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, dur), CH_BASS)

    def smbh_bass_slide(start_bar, vel_mult=1.0):
        """Chorus bass with slides."""
        v = lambda x: vscale(x, vel_mult)
        base = bar_start(mid, start_bar)
        pattern = [
            (0.0, 50, 100, 0.5), (0.5, 48, 90, 0.25), (0.75, 45, 85, 0.25),
            (1.0, 45, 95, 0.5), (1.5, 43, 80, 0.5),
            (2.0, 40, 100, 0.5), (2.5, 44, 85, 0.25), (2.75, 45, 90, 0.25),
            (3.0, 45, 95, 0.5), (3.5, 48, 85, 0.5),
        ]
        for beat, note, vel, dur in pattern:
            add_note(bass, note, v(vel), base + t(mid, beat), t(mid, dur), CH_BASS)

    # === INTRO (bars 0-3): Funky muted guitar scratch + kick ===
    for b in range(INTRO[0], INTRO[1]):
        guitar_muted_scratch(b, 0.9)
        # Just kick pattern, no full drums
        base = bar_start(mid, b)
        add_note(drums, KICK, 100, base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 80, base + t(mid, 0.75), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 90, base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 80, base + t(mid, 2.75), t(mid, 0.25), CH_DRUMS)

    # === VERSE 1 (bars 4-11): Full band, staccato guitar ===
    for b in range(VERSE1[0], VERSE1[1]):
        smbh_drums(b, vel_mult=0.88, has_crash=(b == VERSE1[0]))
        guitar_funky_staccato(b, 0.88)
        smbh_bass(b, 0.88)

    # === CHORUS 1 (bars 12-15): Dm-Am-E7 hits, crash accents ===
    for b in range(CHORUS1[0], CHORUS1[1]):
        smbh_drums(b, vel_mult=1.1, has_crash=True)
        guitar_chorus_hits(b, 1.05)
        smbh_bass_slide(b, 1.05)

    # === VERSE 2 (bars 16-23): Wah variation ===
    for b in range(VERSE2[0], VERSE2[1]):
        smbh_drums(b, vel_mult=0.9, has_crash=(b == VERSE2[0]))
        guitar_funky_staccato(b, 0.9, wah_variation=True)
        smbh_bass(b, 0.9)

    # === BRIDGE (bars 24-27): Breakdown, sparse drums, sustained feedback ===
    for b in range(BRIDGE[0], BRIDGE[1]):
        smbh_drums(b, vel_mult=0.7, sparse=True)
        guitar_bridge_feedback(b, 0.8)
        # Sparse bass
        base = bar_start(mid, b)
        add_note(bass, 45, vscale(85, 0.75), base, t(mid, 2.0), CH_BASS)
        add_note(bass, 43, vscale(75, 0.75), base + t(mid, 2.5), t(mid, 1.5), CH_BASS)

    # === CHORUS 2 (bars 28-31): Biggest, everything ===
    for b in range(CHORUS2[0], CHORUS2[1]):
        smbh_drums(b, vel_mult=1.15, has_crash=True)
        guitar_chorus_hits(b, 1.12)
        smbh_bass_slide(b, 1.1)

    # --- Humanization: Muse funk groove ---
    random.seed(46)
    # Drums: funk swing 0.15, ghost snare hits already in pattern, add flams
    humanize_events(drums, swing=0.15, timing_jitter=6, velocity_jitter=5,
                    flam_before_accents=True, accent_vel_threshold=100, ppq=ppq,
                    bar_length_beats=4,
                    ghost_notes=[
                        {'note': CLOSED_HAT, 'vel_range': (15, 22), 'every_n_ticks': ppq // 4, 'channel': CH_DRUMS, 'duration': int(ppq * 0.06)},
                    ])
    add_ghost_snare_between_backbeats(drums, ppq=ppq, bar_length_beats=4, vel=30, channel=CH_DRUMS)
    # Guitar: tight timing but vary attack
    humanize_events(guitar, swing=0.08, timing_jitter=5, velocity_jitter=6,
                    ppq=ppq, bar_length_beats=4)
    # Bass: funk octave jumps, slight humanization
    humanize_events(bass, swing=0.10, timing_jitter=5, velocity_jitter=4,
                    ppq=ppq, bar_length_beats=4)
    add_bass_ghost_notes(bass, ppq=ppq, vel_range=(30, 40), channel=CH_BASS)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Supermassive Black Hole", "Muse", bpm, "Am", total_bars, 4,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Supermassive Black Hole ({total_bars} bars)")


# ========================================================================
# 6. MUSE - KNIGHTS OF CYDONIA (BPM 138, Em, 6/8, 36 bars)
# Structure: INTRO(4) VERSE(8) CHORUS(4) BRIDGE(4) VERSE2(8) CHORUS2(4) OUTRO(4)
# All in 6/8: each bar = 3 quarter notes at BPM 138
# ========================================================================
def gen_knights_of_cydonia():
    bpm = 138
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "knights_of_cydonia")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    total_bars = 36

    drums = []
    guitar = []
    bass = []

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    BRIDGE = (16, 20)
    VERSE2 = (20, 28)
    CHORUS2 = (28, 32)
    OUTRO = (32, 36)

    trip = ppq // 3  # triplet subdivision

    # --- Drums: 6/8 galloping ---
    def gallop_drums(bar, vel_mult=1.0, has_crash=False, busy=False):
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        if has_crash:
            add_note(drums, CRASH, v(110), base, t(mid, 0.5), CH_DRUMS)
        for beat in range(3):
            beat_start = base + beat * ppq
            # Gallop: kick - kick - snare
            add_note(drums, KICK, v(110), beat_start, t(mid, 0.15), CH_DRUMS)
            add_note(drums, KICK, v(90), beat_start + trip, t(mid, 0.15), CH_DRUMS)
            add_note(drums, SNARE, v(100), beat_start + 2 * trip, t(mid, 0.15), CH_DRUMS)
        # Ride on every beat
        for beat in range(3):
            add_note(drums, RIDE, v(75), base + beat * ppq, t(mid, 0.25), CH_DRUMS)
        if busy:
            # Extra hi-hat on upbeats
            for beat in range(3):
                add_note(drums, CLOSED_HAT, v(60), base + beat * ppq + trip, t(mid, 0.1), CH_DRUMS)

    def halftime_drums(bar, vel_mult=1.0):
        """Half-time breakdown drums for bridge."""
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        add_note(drums, KICK, v(100), base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, v(95), base + ppq, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, v(85), base + 2 * ppq, t(mid, 0.25), CH_DRUMS)
        for beat in range(3):
            add_note(drums, CLOSED_HAT, v(65), base + beat * ppq, t(mid, 0.2), CH_DRUMS)

    # --- Guitar: Galloping E5 power chord ---
    def guitar_gallop_power(bar, vel_mult=1.0):
        """Galloping E5 power chord 8ths."""
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        # E5: E4(64)+B4(71)
        for beat in range(3):
            beat_start = base + beat * ppq
            for n in [64, 71]:
                add_note(guitar, n, v(95), beat_start, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, n, v(80), beat_start + trip, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, n, v(90), beat_start + 2 * trip, t(mid, 0.15), CH_GUITAR)

    def guitar_heroic_melody(bar, phrase_idx, vel_mult=1.0, harmony=False):
        """Heroic melody E4-G4-A4-B4-D5."""
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        # E4=64, G4=67, A4=69, B4=71, D5=74
        phrases = [
            [(0, 64, 105, 0.9), (ppq, 67, 100, 0.9), (2*ppq, 69, 105, 0.9)],
            [(0, 71, 110, 0.9), (ppq, 74, 115, 0.9), (2*ppq, 71, 100, 0.9)],
            [(0, 69, 105, 0.9), (ppq, 67, 100, 0.9), (2*ppq, 64, 105, 0.9)],
            [(0, 64, 110, 2.5), (0, 71, 105, 2.5)],  # sustained power chord resolve
        ]
        phrase = phrases[phrase_idx % len(phrases)]
        for tick_off, note, vel, dur in phrase:
            add_note(guitar, note, v(vel), base + tick_off, t(mid, dur), CH_GUITAR)
            if harmony:
                # Add harmony a 3rd above
                add_note(guitar, note + 3, v(vel - 10), base + tick_off, t(mid, dur), CH_GUITAR)

    def guitar_bridge_sustained(bar, vel_mult=1.0):
        """Sustained chords for bridge half-time."""
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        # Em sustained: E4(64)+G4(67)+B4(71)
        for n in [64, 67, 71]:
            add_note(guitar, n, v(85), base, t(mid, 2.5), CH_GUITAR)

    # --- Bass: Galloping root notes ---
    def bass_gallop(bar, vel_mult=1.0, root=40):
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        for beat in range(3):
            beat_start = base + beat * ppq
            add_note(bass, root, v(100), beat_start, t(mid, 0.15), CH_BASS)
            add_note(bass, root, v(80), beat_start + trip, t(mid, 0.15), CH_BASS)
            add_note(bass, root, v(90), beat_start + 2 * trip, t(mid, 0.15), CH_BASS)

    def bass_halftime(bar, vel_mult=1.0, root=40):
        """Half-time bass for bridge."""
        base = bar_start_68(mid, bar)
        v = lambda x: vscale(x, vel_mult)
        add_note(bass, root, v(95), base, t(mid, 1.5), CH_BASS)
        add_note(bass, root, v(80), base + 2 * ppq, t(mid, 0.9), CH_BASS)

    def get_root(bar):
        """Root note selection: E2 mostly, G2/A2 for variation."""
        bar_in_phrase = bar % 4
        if bar_in_phrase < 2:
            return 40  # E2
        elif bar_in_phrase == 2:
            return 43  # G2
        else:
            return 45  # A2

    # === INTRO (bars 0-3): 6/8 galloping drums alone ===
    for b in range(INTRO[0], INTRO[1]):
        gallop_drums(b, vel_mult=0.95, has_crash=(b == 0))

    # === VERSE 1 (bars 4-11): Full band gallop ===
    for b in range(VERSE1[0], VERSE1[1]):
        gallop_drums(b, vel_mult=0.9, has_crash=(b == VERSE1[0]))
        guitar_gallop_power(b, 0.9)
        bass_gallop(b, 0.9, get_root(b - VERSE1[0]))

    # === CHORUS 1 (bars 12-15): Heroic melody, crash every bar ===
    for b in range(CHORUS1[0], CHORUS1[1]):
        gallop_drums(b, vel_mult=1.1, has_crash=True)
        guitar_heroic_melody(b, b - CHORUS1[0], 1.05)
        bass_gallop(b, 1.05, get_root(b - CHORUS1[0]))

    # === BRIDGE (bars 16-19): Half-time breakdown ===
    for b in range(BRIDGE[0], BRIDGE[1]):
        halftime_drums(b, vel_mult=0.8)
        guitar_bridge_sustained(b, 0.8)
        bass_halftime(b, 0.8, get_root(b - BRIDGE[0]))

    # === VERSE 2 (bars 20-27): Gallop returns, busier drums ===
    for b in range(VERSE2[0], VERSE2[1]):
        gallop_drums(b, vel_mult=0.95, has_crash=(b == VERSE2[0]), busy=True)
        guitar_gallop_power(b, 0.95)
        bass_gallop(b, 0.95, get_root(b - VERSE2[0]))

    # === CHORUS 2 (bars 28-31): Biggest, add harmony guitar ===
    for b in range(CHORUS2[0], CHORUS2[1]):
        gallop_drums(b, vel_mult=1.15, has_crash=True, busy=True)
        guitar_heroic_melody(b, b - CHORUS2[0], 1.12, harmony=True)
        bass_gallop(b, 1.1, get_root(b - CHORUS2[0]))

    # === OUTRO (bars 32-35): Gallop -> big crash ending ===
    for b in range(OUTRO[0], OUTRO[1]):
        is_last = (b == OUTRO[1] - 1)
        gallop_drums(b, vel_mult=1.1, has_crash=True)
        guitar_gallop_power(b, 1.1)
        bass_gallop(b, 1.1, 40)
    # Final big crash on the very last beat
    final_base = bar_start_68(mid, OUTRO[1] - 1) + 2 * ppq + 2 * trip
    add_note(drums, CRASH, 120, final_base + trip, t(mid, 1.0), CH_DRUMS)
    add_note(drums, KICK, 120, final_base + trip, t(mid, 0.5), CH_DRUMS)
    for n in [40, 52, 64, 71]:  # E octaves
        add_note(guitar, n, 120, final_base + trip, t(mid, 1.5), CH_GUITAR)
    add_note(bass, 40, 120, final_base + trip, t(mid, 1.5), CH_BASS)

    # --- Humanization: Muse galloping 6/8, tight but dynamic ---
    random.seed(47)
    # Drums: tight triplet timing (only +/-3 ticks jitter), velocity swell 80-110
    humanize_events(drums, swing=0.0, timing_jitter=3, velocity_jitter=8,
                    flam_before_accents=True, accent_vel_threshold=105, ppq=ppq,
                    bar_length_beats=3)  # 6/8 = 3 quarter notes per bar
    # Guitar: gallop strict triplet timing but velocity swells every 2 bars
    # Power chords: some hit 5 ticks early for aggression
    humanize_events(guitar, swing=0.0, timing_jitter=3, velocity_jitter=10,
                    ppq=ppq, bar_length_beats=3, crescendo_per_bar=3)
    # Bass: galloping root, tight
    humanize_events(bass, swing=0.0, timing_jitter=3, velocity_jitter=6,
                    ppq=ppq, bar_length_beats=3, crescendo_per_bar=2)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Knights of Cydonia", "Muse", bpm, "Em", total_bars, 4,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Knights of Cydonia ({total_bars} bars)")


# ========================================================================
# MAIN
# ========================================================================
def main():
    print("Generating Group 3 songs (Santana + Muse)...")
    print()
    gen_black_magic_woman()
    gen_smooth()
    gen_evil_ways()
    gen_hysteria()
    gen_supermassive_black_hole()
    gen_knights_of_cydonia()
    print()
    print("Done! All 6 songs generated.")

    # Summary
    total_files = 0
    for song in ["black_magic_woman", "smooth", "evil_ways", "hysteria",
                 "supermassive_black_hole", "knights_of_cydonia"]:
        song_path = os.path.join(SONGS_DIR, song)
        if os.path.isdir(song_path):
            files = [f for f in os.listdir(song_path) if f.endswith(('.mid', '.json'))]
            total_files += len(files)
            print(f"  {song}/: {', '.join(sorted(files))}")
    print(f"Total files generated: {total_files}")


if __name__ == "__main__":
    main()
