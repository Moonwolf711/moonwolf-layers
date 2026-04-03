"""
generate_all_songs.py — Unified multi-layer MIDI generator for all 19 moonwolf-layers songs.

Replaces: generate_songs_group1.py, generate_songs_group2.py, generate_songs_group3.py

Each song produces granular per-layer MIDI files:
    01_lead_melody.mid   — main riff/hook
    02_counter_melody.mid — harmony, answer phrase
    03_chords.mid        — pads, rhythm guitar, organ comps
    04_bass.mid          — bass line
    05_fx_sweep.mid      — filter sweeps
    06_fx_impact.mid     — hits, crashes
    07_fx_riser.mid      — tension builders
    08_vocal_chops.mid   — vocal stabs
    09_kick.mid          — kick drum only
    10_snare.mid         — snare + clap
    11_hihats.mid        — hats (closed, open, ride)
    12_percussion.mid    — toms, shakers, congas
    full.mid             — all layers combined
    meta.json            — song info + layer manifest

Humanization: per-song swing, jitter, late bias, ghost notes, flams.
"""

import os
import json
import random
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# ============================================================================
# CONSTANTS
# ============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_DIR = os.path.join(BASE_DIR, "songs")

TPB = 480  # ticks per beat
WHOLE = TPB * 4
HALF = TPB * 2
QUARTER = TPB
EIGHTH = TPB // 2
SIXTEENTH = TPB // 4
THIRTYSECOND = TPB // 8
TRIPLET_8TH = TPB // 3
DOT_QUARTER = int(TPB * 1.5)
DOT_EIGHTH = int(TPB * 0.75)
BAR = WHOLE  # 4/4 bar

# Lycra Kit drum mapping
KICK = 36
SNARE = 38
CLAP = 39
TOM_LO = 41
HAT_CLOSED = 42
SHAKER = 44
HAT_OPEN = 46
TOM_HI = 47

# Channel constants
CH_LEAD = 0
CH_COUNTER = 1
CH_CHORDS = 2
CH_BASS = 3
CH_FX = 4
CH_DRUMS = 9

# Note name to MIDI number
NOTE_MAP = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}


def n(name_octave):
    """Convert 'E4' or 'F#2' to MIDI number."""
    if name_octave[-1].isdigit():
        octave = int(name_octave[-1])
        note_name = name_octave[:-1]
    else:
        raise ValueError(f"Bad note: {name_octave}")
    return NOTE_MAP[note_name] + (octave + 1) * 12


def pc(root):
    """Power chord: root + 5th."""
    return [root, root + 7]


def pc5(root):
    """Power chord: root + 5th + octave."""
    return [root, root + 7, root + 12]


# ============================================================================
# HUMANIZATION ENGINE
# ============================================================================

def humanize(tick, vel, swing=0.0, jitter=10, vel_jitter=8, late_bias=0):
    """Apply humanization to a single note's tick and velocity."""
    eighth = TPB // 2
    beat_frac = (tick % TPB) / TPB
    if 0.45 < beat_frac < 0.55:
        tick += int(swing * eighth)
    tick += late_bias + random.randint(-jitter, jitter)
    tick = max(0, tick)
    vel += random.randint(-vel_jitter, vel_jitter)
    return max(0, tick), max(25, min(127, vel))


def ghost_note(tick, note, vel_range=(25, 40)):
    """Create a ghost note event tuple."""
    return (tick, note, random.randint(*vel_range))


def flam(tick, note, vel, gap=8):
    """Create flam pair: grace note + main hit."""
    return [(tick - gap, note, max(25, vel - 20)), (tick, note, vel)]


# Per-song humanization style profiles
STYLES = {
    'led_zeppelin': {'swing': 0.15, 'jitter': 12, 'vel_jitter': 10, 'late_bias': 8,
                     'ghost_density': 0.5, 'ghost_snare_vel': (30, 45),
                     'ghost_hat_vel': (20, 35), 'flam_crashes': True},
    'the_doors':    {'swing': 0.20, 'jitter': 10, 'vel_jitter': 6, 'late_bias': 3,
                     'ghost_density': 0.4, 'ghost_snare_vel': (25, 35),
                     'ghost_hat_vel': (18, 28), 'flam_crashes': False},
    'jimi_hendrix': {'swing': 0.18, 'jitter': 15, 'vel_jitter': 12, 'late_bias': 5,
                     'ghost_density': 0.6, 'ghost_snare_vel': (28, 42),
                     'ghost_hat_vel': (20, 35), 'flam_crashes': True},
    'acdc':         {'swing': 0.05, 'jitter': 4, 'vel_jitter': 5, 'late_bias': 0,
                     'ghost_density': 0.2, 'ghost_snare_vel': (25, 35),
                     'ghost_hat_vel': (20, 30), 'flam_crashes': False},
    'black_sabbath': {'swing': 0.10, 'jitter': 12, 'vel_jitter': 10, 'late_bias': 10,
                      'ghost_density': 0.45, 'ghost_snare_vel': (30, 42),
                      'ghost_hat_vel': (22, 32), 'flam_crashes': True},
    'eagles':       {'swing': 0.15, 'jitter': 6, 'vel_jitter': 5, 'late_bias': 2,
                     'ghost_density': 0.3, 'ghost_snare_vel': (25, 35),
                     'ghost_hat_vel': (18, 28), 'flam_crashes': False},
    'santana':      {'swing': 0.22, 'jitter': 8, 'vel_jitter': 6, 'late_bias': -3,
                     'ghost_density': 0.5, 'ghost_snare_vel': (25, 38),
                     'ghost_hat_vel': (18, 28), 'flam_crashes': True},
    'muse':         {'swing': 0.03, 'jitter': 3, 'vel_jitter': 4, 'late_bias': 0,
                     'ghost_density': 0.25, 'ghost_snare_vel': (28, 38),
                     'ghost_hat_vel': (22, 32), 'flam_crashes': False},
}


# ============================================================================
# MIDI HELPERS — absolute-tick event list approach
# ============================================================================

def add_note(events, note, vel, start_tick, duration_ticks, channel=0):
    """Append note-on/off pair to an event list using absolute ticks."""
    events.append(('on', start_tick, note, vel, channel))
    events.append(('off', start_tick + duration_ticks, note, 0, channel))


def add_chord_ev(events, notes, vel, start_tick, duration_ticks, channel=0):
    """Add chord (multiple simultaneous notes) to event list."""
    for nt in notes:
        add_note(events, nt, vel, start_tick, duration_ticks, channel)


def bar_tick(bar, beats_per_bar=4):
    """Absolute tick for the start of a bar."""
    return bar * beats_per_bar * TPB


def beat_tick(bar, beat, beats_per_bar=4):
    """Absolute tick for a specific beat within a bar."""
    return bar_tick(bar, beats_per_bar) + int(beat * TPB)


def t(fraction):
    """Convert beat fraction to ticks. t(0.5) = eighth, t(1) = quarter."""
    return int(TPB * fraction)


def vscale(base_vel, factor):
    """Scale velocity and clamp."""
    return max(1, min(127, int(base_vel * factor)))


def humanize_events(events, style):
    """Apply humanization to all note events in-place."""
    sw = style['swing']
    jit = style['jitter']
    vj = style['vel_jitter']
    lb = style['late_bias']

    for i, ev in enumerate(events):
        kind, tick, note, vel, ch = ev
        if kind == 'on' and vel > 0:
            tick, vel = humanize(tick, vel, swing=sw, jitter=jit,
                                 vel_jitter=vj, late_bias=lb)
            events[i] = (kind, tick, note, vel, ch)
        elif kind == 'off':
            tick += lb + random.randint(-jit // 2, jit // 2)
            tick = max(0, tick)
            events[i] = (kind, tick, note, 0, ch)


def add_ghost_notes_to_kick(kick_events, style, total_bars):
    """Insert ghost kick hits at 16th positions."""
    density = style['ghost_density'] * 0.3
    for bar in range(total_bars):
        for sub in range(16):
            if random.random() < density:
                tick = bar_tick(bar) + sub * SIXTEENTH
                vel = random.randint(25, 40)
                add_note(kick_events, KICK, vel, tick, SIXTEENTH, CH_DRUMS)


def add_ghost_notes_to_snare(snare_events, style, total_bars):
    """Insert ghost snare hits between backbeats."""
    gvel = style['ghost_snare_vel']
    density = style['ghost_density']
    for bar in range(total_bars):
        for beat in range(4):
            # Ghost snares on e and a of each beat
            for sub_frac in [0.25, 0.75]:
                if random.random() < density:
                    tick = beat_tick(bar, beat + sub_frac)
                    vel = random.randint(*gvel)
                    add_note(snare_events, SNARE, vel, tick, SIXTEENTH, CH_DRUMS)
            # Flam before crashes on beat 1
            if style.get('flam_crashes', False) and beat == 0 and bar % 4 == 0:
                tick = bar_tick(bar)
                for ft, fn, fv in flam(tick - THIRTYSECOND, SNARE, random.randint(45, 65)):
                    add_note(snare_events, fn, fv, ft, THIRTYSECOND, CH_DRUMS)


def add_ghost_notes_to_hats(hat_events, style, total_bars):
    """Insert ghost hat taps at 16th subdivisions."""
    gvel = style['ghost_hat_vel']
    density = style['ghost_density'] * 0.6
    for bar in range(total_bars):
        for sub in range(16):
            if random.random() < density:
                tick = bar_tick(bar) + sub * SIXTEENTH
                vel = random.randint(*gvel)
                add_note(hat_events, HAT_CLOSED, vel, tick, SIXTEENTH, CH_DRUMS)


def add_ghost_perc(perc_events, style, total_bars):
    """Add ghost percussion fills at section boundaries."""
    gvel = style.get('ghost_snare_vel', (25, 40))
    for bar in range(total_bars):
        if bar % 8 == 7:  # fill before section change
            for sub in range(4):
                tick = beat_tick(bar, 3 + sub * 0.25)
                vel = random.randint(*gvel) + sub * 5
                note = TOM_HI if sub < 2 else TOM_LO
                add_note(perc_events, note, min(127, vel), tick, SIXTEENTH, CH_DRUMS)


# ============================================================================
# SAVE HELPERS
# ============================================================================

def finalize_track(midi_track, events, bpm):
    """Convert absolute-time events to delta-time MIDI messages."""
    events.sort(key=lambda e: (e[1], 0 if e[0] == 'off' else 1))
    midi_track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    current = 0
    for ev in events:
        kind, abs_tick, note, vel, ch = ev
        delta = max(0, abs_tick - current)
        current = abs_tick
        if kind == 'on':
            midi_track.append(Message('note_on', note=note, velocity=vel,
                                       time=delta, channel=ch))
        else:
            midi_track.append(Message('note_off', note=note, velocity=vel,
                                       time=delta, channel=ch))
    midi_track.append(MetaMessage('end_of_track', time=0))


def save_layer(events, filepath, track_name, bpm, channel=0):
    """Save a single layer as a .mid file."""
    if not events:
        return
    mid = MidiFile(ticks_per_beat=TPB)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('track_name', name=track_name, time=0))
    finalize_track(track, list(events), bpm)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    mid.save(filepath)


def save_full(all_layers, filepath, bpm):
    """Save all layers combined into a single multi-track .mid."""
    mid = MidiFile(type=1, ticks_per_beat=TPB)
    for name, events in all_layers:
        if not events:
            continue
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage('track_name', name=name, time=0))
        finalize_track(track, list(events), bpm)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    mid.save(filepath)


def save_meta(song_dir, meta_dict):
    """Save meta.json for a song."""
    os.makedirs(song_dir, exist_ok=True)
    with open(os.path.join(song_dir, "meta.json"), "w") as f:
        json.dump(meta_dict, f, indent=4)


def generate_song(song_func):
    """Wrapper that calls a song generator and handles output."""
    song_func()


# ============================================================================
# LAYER BUILDER — common pattern for assembling per-song layers
# ============================================================================

class SongBuilder:
    """Helper to accumulate events per layer and save everything."""

    def __init__(self, title, artist, bpm, key, bars, difficulty, style_name,
                 song_dir_name, beats_per_bar=4):
        self.title = title
        self.artist = artist
        self.bpm = bpm
        self.key = key
        self.bars = bars
        self.difficulty = difficulty
        self.style_name = style_name
        self.style = STYLES[style_name]
        self.song_dir = os.path.join(SONGS_DIR, song_dir_name)
        self.beats_per_bar = beats_per_bar

        # Event lists per layer
        self.lead = []
        self.counter = []
        self.chords = []
        self.bass = []
        self.fx_sweep = []
        self.fx_impact = []
        self.fx_riser = []
        self.vocal_chops = []
        self.kick = []
        self.snare = []
        self.hihats = []
        self.percussion = []

    def bt(self, bar, beat=0):
        """Bar+beat to absolute tick."""
        return bar_tick(bar, self.beats_per_bar) + int(beat * TPB)

    def save(self):
        """Humanize all layers, add ghost notes, save files."""
        os.makedirs(self.song_dir, exist_ok=True)
        style = self.style
        bars = self.bars

        # Humanize melodic layers
        for layer in [self.lead, self.counter, self.chords, self.bass,
                      self.fx_sweep, self.fx_impact, self.fx_riser, self.vocal_chops]:
            if layer:
                humanize_events(layer, style)

        # Humanize drum layers
        for layer in [self.kick, self.snare, self.hihats, self.percussion]:
            if layer:
                humanize_events(layer, style)

        # Ghost notes on drum layers
        add_ghost_notes_to_kick(self.kick, style, bars)
        add_ghost_notes_to_snare(self.snare, style, bars)
        add_ghost_notes_to_hats(self.hihats, style, bars)
        add_ghost_perc(self.percussion, style, bars)

        # Build layer manifest
        layers_meta = []
        layer_defs = [
            ("01_lead_melody.mid", "Lead Melody", self.lead, CH_LEAD, "Drift - Lead"),
            ("02_counter_melody.mid", "Counter Melody", self.counter, CH_COUNTER, "Drift - Pad"),
            ("03_chords.mid", "Chords", self.chords, CH_CHORDS, "Analog - Chords"),
            ("04_bass.mid", "Bass", self.bass, CH_BASS, "Analog - Bass"),
            ("05_fx_sweep.mid", "FX Sweep", self.fx_sweep, CH_FX, "Wavetable - Sweep"),
            ("06_fx_impact.mid", "FX Impact", self.fx_impact, CH_FX, "Operator - Impact"),
            ("07_fx_riser.mid", "FX Riser", self.fx_riser, CH_FX, "Wavetable - Riser"),
            ("08_vocal_chops.mid", "Vocal Chops", self.vocal_chops, CH_FX, "Sampler - Vox"),
            ("09_kick.mid", "Kick", self.kick, CH_DRUMS, "Drum Rack"),
            ("10_snare.mid", "Snare", self.snare, CH_DRUMS, "Drum Rack"),
            ("11_hihats.mid", "Hi-Hats", self.hihats, CH_DRUMS, "Drum Rack"),
            ("12_percussion.mid", "Percussion", self.percussion, CH_DRUMS, "Drum Rack"),
        ]

        all_layers_for_full = []
        for filename, name, events, ch, device in layer_defs:
            if events:
                filepath = os.path.join(self.song_dir, filename)
                save_layer(events, filepath, name, self.bpm, ch)
                midi_ch = 10 if ch == CH_DRUMS else ch + 1
                layers_meta.append({
                    "file": filename,
                    "name": name,
                    "instrument": name,
                    "midi_ch": midi_ch,
                    "suggested_device": device
                })
                all_layers_for_full.append((name, events))

        # Save full.mid
        save_full(all_layers_for_full,
                  os.path.join(self.song_dir, "full.mid"), self.bpm)

        # Save meta.json
        meta = {
            "title": self.title,
            "artist": self.artist,
            "bpm": self.bpm,
            "key": self.key,
            "bars": self.bars,
            "difficulty": self.difficulty,
            "layers": layers_meta
        }
        save_meta(self.song_dir, meta)

        print(f"  [OK] {self.title} — {self.artist} "
              f"({self.bars} bars, {len(layers_meta)} layers)")


# ============================================================================
# SONG GENERATORS
# ============================================================================

# ---------------------------------------------------------------------------
# 1. AC/DC — Back in Black (92 BPM, E, 32 bars)
# ---------------------------------------------------------------------------
def gen_back_in_black():
    s = SongBuilder("Back in Black", "AC/DC", 92, "E", 32, 3, 'acdc',
                    "acdc_back_in_black")
    random.seed(101)

    # Section layout
    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 20)
    VERSE2 = (20, 28)
    OUTRO = (28, 32)

    # Lead: E5-D5-A5 power chord gallop riff
    def lead_riff(bar, vel=100):
        b = s.bt(bar)
        # E5-D5-A5 gallop
        for nt, off in [(n('E4'), 0), (n('D4'), QUARTER), (n('A3'), HALF)]:
            add_chord_ev(s.lead, pc(nt), vel, b + off, EIGHTH, CH_LEAD)
        # Repeat with 8th gallop in second half
        for i, nt in enumerate([n('E4'), n('E4'), n('D4'), n('A3')]):
            add_chord_ev(s.lead, pc(nt), vel - 5, b + HALF + i * EIGHTH,
                         EIGHTH, CH_LEAD)

    # Counter: intro bell/chime pattern
    def bell_pattern(bar, vel=75):
        b = s.bt(bar)
        for i, nt in enumerate([n('B5'), n('A5'), n('E5'), n('B4')]):
            add_note(s.counter, nt, vel, b + i * QUARTER, EIGHTH, CH_COUNTER)

    # Chords: E5-D5-A5 sustained
    def chord_pad(bar, vel=85):
        b = s.bt(bar)
        for chord_root, offset in [(n('E3'), 0), (n('D3'), HALF), (n('A2'), HALF * 2)]:
            add_chord_ev(s.chords, pc5(chord_root), vel, b + offset,
                         HALF - SIXTEENTH, CH_CHORDS)

    # Bass: E2-D2-A1 8ths locked to kick
    def bass_line(bar, vel=95):
        b = s.bt(bar)
        roots = [n('E2'), n('E2'), n('D2'), n('D2'),
                 n('A1'), n('A1'), n('E2'), n('E2')]
        for i, nt in enumerate(roots):
            add_note(s.bass, nt, vel, b + i * EIGHTH, EIGHTH - 10, CH_BASS)

    # Drums
    def kick_pattern(bar, vel=110):
        b = s.bt(bar)
        # 1 and 3
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    def snare_pattern(bar, vel=105):
        b = s.bt(bar)
        # 2 and 4
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    def hat_pattern(bar, vel=80):
        b = s.bt(bar)
        # open 8ths
        for i in range(8):
            v = vel if i % 2 == 0 else vel - 10
            add_note(s.hihats, HAT_OPEN, v, b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Intro: bell pattern + hats only
    for bar in range(*INTRO):
        bell_pattern(bar, 70 + bar * 3)
        hat_pattern(bar, 65)
        if bar >= 2:
            lead_riff(bar, 85)

    # Verse: full band
    for bar in range(*VERSE1):
        lead_riff(bar, 95)
        chord_pad(bar, 80)
        bass_line(bar, 90)
        kick_pattern(bar, 105)
        snare_pattern(bar, 100)
        hat_pattern(bar, 78)

    # Chorus: louder
    for bar in range(*CHORUS1):
        lead_riff(bar, 110)
        chord_pad(bar, 95)
        bass_line(bar, 100)
        kick_pattern(bar, 115)
        snare_pattern(bar, 110)
        hat_pattern(bar, 85)
        if bar % 4 == 0:
            add_note(s.percussion, CLAP, 110, s.bt(bar), EIGHTH, CH_DRUMS)

    # Verse 2
    for bar in range(*VERSE2):
        lead_riff(bar, 95)
        chord_pad(bar, 80)
        bass_line(bar, 90)
        kick_pattern(bar, 105)
        snare_pattern(bar, 100)
        hat_pattern(bar, 78)

    # Outro: fade
    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.2
        lead_riff(bar, vscale(95, fade))
        bass_line(bar, vscale(90, fade))
        kick_pattern(bar, vscale(105, fade))
        snare_pattern(bar, vscale(100, fade))
        hat_pattern(bar, vscale(78, fade))

    s.save()


# ---------------------------------------------------------------------------
# 2. AC/DC — Highway to Hell (116 BPM, A, 32 bars)
# ---------------------------------------------------------------------------
def gen_highway_to_hell():
    s = SongBuilder("Highway to Hell", "AC/DC", 116, "A", 32, 2, 'acdc',
                    "acdc_highway_to_hell")
    random.seed(102)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    VERSE2 = (16, 24)
    CHORUS2 = (24, 28)
    OUTRO = (28, 32)

    # Lead: A5-D/F#-G5 riff
    def lead_riff(bar, vel=100):
        b = s.bt(bar)
        riff = [(n('A4'), 0, EIGHTH), (n('A4'), EIGHTH, EIGHTH),
                (n('D4'), QUARTER, EIGHTH), (n('F#4'), DOT_QUARTER, EIGHTH),
                (n('G4'), HALF, QUARTER), (n('A4'), HALF + QUARTER, QUARTER)]
        for nt, off, dur in riff:
            add_note(s.lead, nt, vel, b + off, dur, CH_LEAD)

    # Chords: palm-muted 8th rhythm
    def chord_mute(bar, vel=85):
        b = s.bt(bar)
        roots = [n('A3'), n('A3'), n('D3'), n('D3'),
                 n('G3'), n('G3'), n('A3'), n('A3')]
        for i, rt in enumerate(roots):
            add_chord_ev(s.chords, pc(rt), vel, b + i * EIGHTH,
                         EIGHTH - 20, CH_CHORDS)

    # Bass: root quarters
    def bass_line(bar, vel=95):
        b = s.bt(bar)
        for i, nt in enumerate([n('A2'), n('D2'), n('G2'), n('A2')]):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Drums
    def kick_13(bar, vel=110):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    def snare_24(bar, vel=105):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    def hat_8ths(bar, vel=80):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, HAT_CLOSED, vel - (i % 2) * 10,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    def crash_bar(bar, vel=115):
        add_note(s.percussion, CLAP, vel, s.bt(bar), EIGHTH, CH_DRUMS)

    # Build sections
    for bar in range(*INTRO):
        lead_riff(bar, 85)
        hat_8ths(bar, 65)

    for bar in range(*VERSE1):
        lead_riff(bar, 95)
        chord_mute(bar, 80)
        bass_line(bar, 90)
        kick_13(bar); snare_24(bar); hat_8ths(bar)

    for bar in range(*CHORUS1):
        lead_riff(bar, 110)
        chord_mute(bar, 95)
        bass_line(bar, 100)
        kick_13(bar, 115); snare_24(bar, 110); hat_8ths(bar, 88)
        if bar % 4 == 0: crash_bar(bar)

    for bar in range(*VERSE2):
        lead_riff(bar, 95)
        chord_mute(bar, 80)
        bass_line(bar, 90)
        kick_13(bar); snare_24(bar); hat_8ths(bar)

    for bar in range(*CHORUS2):
        lead_riff(bar, 110)
        chord_mute(bar, 95)
        bass_line(bar, 100)
        kick_13(bar, 115); snare_24(bar, 110); hat_8ths(bar, 88)
        if bar % 4 == 0: crash_bar(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.2
        lead_riff(bar, vscale(100, fade))
        bass_line(bar, vscale(90, fade))
        kick_13(bar, vscale(110, fade))
        snare_24(bar, vscale(105, fade))
        hat_8ths(bar, vscale(78, fade))

    s.save()


# ---------------------------------------------------------------------------
# 3. AC/DC — Thunderstruck (134 BPM, B, 36 bars)
# ---------------------------------------------------------------------------
def gen_thunderstruck():
    s = SongBuilder("Thunderstruck", "AC/DC", 134, "B", 36, 4, 'acdc',
                    "acdc_thunderstruck")
    random.seed(103)

    INTRO = (0, 8)
    VERSE1 = (8, 16)
    CHORUS1 = (16, 24)
    BRIDGE = (24, 28)
    CHORUS2 = (28, 36)

    # Lead: THE hammer-on riff B-E-B-A-B-G#-A-E 16ths
    def hammer_riff(bar, vel=95):
        b = s.bt(bar)
        notes = [n('B4'), n('E5'), n('B4'), n('A4'),
                 n('B4'), n('G#4'), n('A4'), n('E4')]
        # Repeat as 16ths filling 2 beats, then repeat
        for rep in range(2):
            for i, nt in enumerate(notes):
                tick = b + rep * HALF + i * SIXTEENTH
                add_note(s.lead, nt, vel, tick, SIXTEENTH - 5, CH_LEAD)

    # Chords: B5 power chord rhythm (verse)
    def chord_rhythm(bar, vel=90):
        b = s.bt(bar)
        for i in range(8):
            add_chord_ev(s.chords, pc(n('B3')), vel,
                         b + i * EIGHTH, EIGHTH - 15, CH_CHORDS)

    # Bass: B2 pedal 8ths
    def bass_pedal(bar, vel=95):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.bass, n('B2'), vel, b + i * EIGHTH,
                     EIGHTH - 10, CH_BASS)

    # Drums - enters bar 5
    def kick_pattern(bar, vel=110):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    def snare_pattern(bar, vel=105):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    def hat_16ths(bar, vel=75):
        b = s.bt(bar)
        for i in range(16):
            v = vel if i % 4 == 0 else (vel - 10 if i % 2 == 0 else vel - 20)
            add_note(s.hihats, HAT_CLOSED, v, b + i * SIXTEENTH,
                     SIXTEENTH - 5, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        hammer_riff(bar, 90)
        hat_16ths(bar, 65)
        if bar >= 4:
            kick_pattern(bar, 100)
            snare_pattern(bar, 95)

    for bar in range(*VERSE1):
        hammer_riff(bar, 95)
        chord_rhythm(bar, 85)
        bass_pedal(bar, 90)
        kick_pattern(bar); snare_pattern(bar); hat_16ths(bar)

    for bar in range(*CHORUS1):
        hammer_riff(bar, 110)
        chord_rhythm(bar, 100)
        bass_pedal(bar, 100)
        kick_pattern(bar, 115); snare_pattern(bar, 110); hat_16ths(bar, 85)
        if bar % 4 == 0:
            add_note(s.percussion, CLAP, 115, s.bt(bar), EIGHTH, CH_DRUMS)

    for bar in range(*BRIDGE):
        chord_rhythm(bar, 90)
        bass_pedal(bar, 85)
        kick_pattern(bar); snare_pattern(bar); hat_16ths(bar, 70)

    for bar in range(*CHORUS2):
        hammer_riff(bar, 110)
        chord_rhythm(bar, 100)
        bass_pedal(bar, 100)
        kick_pattern(bar, 115); snare_pattern(bar, 110); hat_16ths(bar, 85)

    s.save()


# ---------------------------------------------------------------------------
# 4. Black Sabbath — Iron Man (76 BPM, Bm, 34 bars)
# ---------------------------------------------------------------------------
def gen_iron_man():
    s = SongBuilder("Iron Man", "Black Sabbath", 76, "Bm", 34, 3, 'black_sabbath',
                    "black_sabbath_iron_man")
    random.seed(104)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 18)
    BRIDGE = (18, 22)
    VERSE2 = (22, 30)
    OUTRO = (30, 34)

    # Lead: B-D-E-G-F#-G-F#-D-E slow power chord riff
    def iron_riff(bar, vel=100):
        b = s.bt(bar)
        riff_notes = [n('B3'), n('D4'), n('E4'), n('G4'),
                      n('F#4'), n('G4'), n('F#4'), n('D4')]
        # 2 bars: each note is a dotted quarter except last two = quarters
        for i, nt in enumerate(riff_notes[:4]):
            add_chord_ev(s.lead, pc(nt), vel, b + i * QUARTER,
                         QUARTER - 10, CH_LEAD)
        b2 = s.bt(bar + 1) if bar + 1 < s.bars else b + BAR
        for i, nt in enumerate(riff_notes[4:]):
            add_chord_ev(s.lead, pc(nt), vel - 5, b2 + i * QUARTER,
                         QUARTER - 10, CH_LEAD)

    # Bass: same riff octave down
    def bass_riff(bar, vel=95):
        b = s.bt(bar)
        riff_notes = [n('B2'), n('D3'), n('E3'), n('G3'),
                      n('F#3'), n('G3'), n('F#3'), n('D3')]
        for i, nt in enumerate(riff_notes[:4]):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)
        b2 = s.bt(bar + 1) if bar + 1 < s.bars else b + BAR
        for i, nt in enumerate(riff_notes[4:]):
            add_note(s.bass, nt, vel - 5, b2 + i * QUARTER, QUARTER - 10, CH_BASS)

    # Drums
    def kick_heavy(bar, vel=115):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    def snare_24(bar, vel=110):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    def hat_sparse(bar, vel=70):
        b = s.bt(bar)
        for i in range(4):
            add_note(s.hihats, HAT_CLOSED, vel, b + i * QUARTER,
                     EIGHTH, CH_DRUMS)

    def tom_fill(bar, vel=100):
        b = s.bt(bar)
        for i in range(4):
            nt = TOM_HI if i < 2 else TOM_LO
            add_note(s.percussion, nt, vel + i * 5, b + HALF + i * EIGHTH,
                     EIGHTH, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        iron_riff(bar, 85)
        if bar >= 2:
            kick_heavy(bar, 90)

    for bar in range(VERSE1[0], VERSE1[1], 2):
        iron_riff(bar, 100)
        bass_riff(bar, 95)
    for bar in range(*VERSE1):
        kick_heavy(bar); snare_24(bar); hat_sparse(bar)

    for bar in range(CHORUS1[0], CHORUS1[1], 2):
        iron_riff(bar, 115)
        bass_riff(bar, 105)
    for bar in range(*CHORUS1):
        kick_heavy(bar, 120); snare_24(bar, 115); hat_sparse(bar, 80)
        if bar % 4 == 3: tom_fill(bar)

    for bar in range(BRIDGE[0], BRIDGE[1], 2):
        iron_riff(bar, 90)
        bass_riff(bar, 85)
    for bar in range(*BRIDGE):
        kick_heavy(bar, 100); snare_24(bar); hat_sparse(bar, 65)

    for bar in range(VERSE2[0], VERSE2[1], 2):
        iron_riff(bar, 100)
        bass_riff(bar, 95)
    for bar in range(*VERSE2):
        kick_heavy(bar); snare_24(bar); hat_sparse(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.15
        if bar % 2 == 0:
            iron_riff(bar, vscale(100, fade))
            bass_riff(bar, vscale(95, fade))
        kick_heavy(bar, vscale(110, fade))
        snare_24(bar, vscale(105, fade))

    s.save()


# ---------------------------------------------------------------------------
# 5. Black Sabbath — Paranoid (164 BPM, Em, 32 bars)
# ---------------------------------------------------------------------------
def gen_paranoid():
    s = SongBuilder("Paranoid", "Black Sabbath", 164, "Em", 32, 2, 'black_sabbath',
                    "black_sabbath_paranoid")
    random.seed(105)

    INTRO = (0, 2)
    VERSE1 = (2, 10)
    CHORUS1 = (10, 18)
    VERSE2 = (18, 26)
    OUTRO = (26, 32)

    # Lead: E-D-E-G pull-off melody
    def lead_melody(bar, vel=100):
        b = s.bt(bar)
        notes = [n('E4'), n('D4'), n('E4'), n('G4')]
        for i, nt in enumerate(notes):
            add_note(s.lead, nt, vel, b + i * QUARTER, QUARTER - 10, CH_LEAD)

    # Chords: E5 8th note chug
    def chord_chug(bar, vel=90):
        b = s.bt(bar)
        for i in range(8):
            add_chord_ev(s.chords, pc(n('E3')), vel,
                         b + i * EIGHTH, EIGHTH - 20, CH_CHORDS)

    # Bass: E2 8th pedal
    def bass_pedal(bar, vel=95):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.bass, n('E2'), vel, b + i * EIGHTH,
                     EIGHTH - 10, CH_BASS)

    # Drums
    def kick_13(bar, vel=110):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    def snare_24(bar, vel=105):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    def hat_8ths(bar, vel=78):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, HAT_CLOSED, vel - (i % 2) * 8,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        lead_melody(bar, 90)
        kick_13(bar); hat_8ths(bar, 65)

    for bar in range(*VERSE1):
        lead_melody(bar, 100)
        chord_chug(bar, 85)
        bass_pedal(bar, 90)
        kick_13(bar); snare_24(bar); hat_8ths(bar)

    for bar in range(*CHORUS1):
        lead_melody(bar, 115)
        chord_chug(bar, 100)
        bass_pedal(bar, 100)
        kick_13(bar, 118); snare_24(bar, 112); hat_8ths(bar, 85)

    for bar in range(*VERSE2):
        lead_melody(bar, 100)
        chord_chug(bar, 85)
        bass_pedal(bar, 90)
        kick_13(bar); snare_24(bar); hat_8ths(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.12
        lead_melody(bar, vscale(100, fade))
        chord_chug(bar, vscale(85, fade))
        bass_pedal(bar, vscale(90, fade))
        kick_13(bar, vscale(110, fade))
        snare_24(bar, vscale(105, fade))
        hat_8ths(bar, vscale(78, fade))

    s.save()


# ---------------------------------------------------------------------------
# 6. Eagles — Hotel California (74 BPM, Bm, 36 bars)
# ---------------------------------------------------------------------------
def gen_hotel_california():
    s = SongBuilder("Hotel California", "Eagles", 74, "Bm", 36, 3, 'eagles',
                    "eagles_hotel_california")
    random.seed(106)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 20)
    SOLO = (20, 28)
    OUTRO = (28, 36)

    # Chord progression: Bm-F#-A-E-G-D-Em-F# (8 chords, 1 bar each)
    prog = [n('B2'), n('F#3'), n('A2'), n('E3'),
            n('G2'), n('D3'), n('E3'), n('F#3')]

    # Lead: arpeggios over the progression
    def lead_arp(bar, vel=85):
        b = s.bt(bar)
        root = prog[(bar - INTRO[1]) % 8] + 12  # up an octave
        arp = [root, root + 4, root + 7, root + 12, root + 7, root + 4]
        for i, nt in enumerate(arp):
            add_note(s.lead, nt, vel, b + i * t(0.66), t(0.6), CH_LEAD)

    # Counter: twin guitar harmony (solo section)
    def counter_harmony(bar, vel=90):
        b = s.bt(bar)
        root = prog[(bar - SOLO[0]) % 8] + 24
        thirds = [root, root + 3, root + 7, root + 10]
        for i, nt in enumerate(thirds):
            add_note(s.counter, nt, vel, b + i * QUARTER, QUARTER - 10, CH_COUNTER)

    # Chords: strummed version
    def chord_strum(bar, vel=80):
        b = s.bt(bar)
        root = prog[bar % 8]
        chord = [root, root + 4, root + 7]
        for beat in range(4):
            add_chord_ev(s.chords, chord, vel, b + beat * QUARTER,
                         QUARTER - 15, CH_CHORDS)

    # Bass: root walking
    def bass_walk(bar, vel=85):
        b = s.bt(bar)
        root = prog[bar % 8]
        walk = [root, root + 2, root + 4, root + 5]
        for i, nt in enumerate(walk):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Drums: half-time feel
    def kick_half(bar, vel=95):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)

    def snare_on3(bar, vel=90):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + HALF, EIGHTH, CH_DRUMS)

    def ride_pattern(bar, vel=72):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, SHAKER, vel - (i % 2) * 8,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    def shaker_perc(bar, vel=50):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.percussion, SHAKER, vel, b + i * EIGHTH,
                     EIGHTH - 15, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        lead_arp(bar, 70)
        ride_pattern(bar, 60)

    for bar in range(*VERSE1):
        lead_arp(bar, 80)
        chord_strum(bar, 75)
        bass_walk(bar, 80)
        kick_half(bar); snare_on3(bar); ride_pattern(bar)
        shaker_perc(bar, 45)

    for bar in range(*CHORUS1):
        lead_arp(bar, 95)
        chord_strum(bar, 90)
        bass_walk(bar, 90)
        kick_half(bar, 105); snare_on3(bar, 100); ride_pattern(bar, 80)
        shaker_perc(bar, 55)

    for bar in range(*SOLO):
        counter_harmony(bar, 90)
        chord_strum(bar, 80)
        bass_walk(bar, 85)
        kick_half(bar); snare_on3(bar); ride_pattern(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.08
        lead_arp(bar, vscale(85, fade))
        chord_strum(bar, vscale(80, fade))
        bass_walk(bar, vscale(80, fade))
        kick_half(bar, vscale(95, fade))
        snare_on3(bar, vscale(90, fade))
        ride_pattern(bar, vscale(72, fade))

    s.save()


# ---------------------------------------------------------------------------
# 7. Eagles — Take It Easy (138 BPM, G, 32 bars)
# ---------------------------------------------------------------------------
def gen_take_it_easy():
    s = SongBuilder("Take It Easy", "Eagles", 138, "G", 32, 2, 'eagles',
                    "eagles_take_it_easy")
    random.seed(107)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 20)
    VERSE2 = (20, 28)
    OUTRO = (28, 32)

    # Lead: G-C/G-D strumming pattern
    def lead_strum(bar, vel=90):
        b = s.bt(bar)
        roots_cycle = [n('G4'), n('C4'), n('G4'), n('D4')]
        root = roots_cycle[bar % 4]
        pattern = [0, EIGHTH, QUARTER, QUARTER + EIGHTH,
                   HALF, HALF + EIGHTH, HALF + QUARTER]
        for off in pattern:
            add_note(s.lead, root, vel, b + off, EIGHTH - 10, CH_LEAD)

    # Chords: open chord strum
    def chord_strum(bar, vel=80):
        b = s.bt(bar)
        chords_cycle = [[n('G3'), n('B3'), n('D4')],
                        [n('C3'), n('E3'), n('G3')],
                        [n('G3'), n('B3'), n('D4')],
                        [n('D3'), n('F#3'), n('A3')]]
        chord = chords_cycle[bar % 4]
        for beat in range(4):
            add_chord_ev(s.chords, chord, vel, b + beat * QUARTER,
                         QUARTER - 15, CH_CHORDS)

    # Bass: root quarters
    def bass_roots(bar, vel=90):
        b = s.bt(bar)
        roots = [n('G2'), n('C2'), n('G2'), n('D2')]
        root = roots[bar % 4]
        for i in range(4):
            add_note(s.bass, root, vel, b + i * QUARTER,
                     QUARTER - 10, CH_BASS)

    # Drums: country rock
    def kick_cr(bar, vel=100):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + QUARTER + EIGHTH, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    def snare_24(bar, vel=95):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    def hat_open8(bar, vel=75):
        b = s.bt(bar)
        for i in range(8):
            nt = HAT_OPEN if i % 2 == 0 else HAT_CLOSED
            add_note(s.hihats, nt, vel - (i % 2) * 8,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        lead_strum(bar, 80)
        hat_open8(bar, 60)

    for bar in range(*VERSE1):
        lead_strum(bar, 90)
        chord_strum(bar, 78)
        bass_roots(bar, 88)
        kick_cr(bar); snare_24(bar); hat_open8(bar)

    for bar in range(*CHORUS1):
        lead_strum(bar, 105)
        chord_strum(bar, 92)
        bass_roots(bar, 95)
        kick_cr(bar, 110); snare_24(bar, 105); hat_open8(bar, 85)

    for bar in range(*VERSE2):
        lead_strum(bar, 90)
        chord_strum(bar, 78)
        bass_roots(bar, 88)
        kick_cr(bar); snare_24(bar); hat_open8(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.18
        lead_strum(bar, vscale(90, fade))
        chord_strum(bar, vscale(78, fade))
        bass_roots(bar, vscale(88, fade))
        kick_cr(bar, vscale(100, fade))
        snare_24(bar, vscale(95, fade))

    s.save()


# ---------------------------------------------------------------------------
# 8. Led Zeppelin — Whole Lotta Love (90 BPM, E, 34 bars)
# ---------------------------------------------------------------------------
def gen_whole_lotta_love():
    s = SongBuilder("Whole Lotta Love", "Led Zeppelin", 90, "E", 34, 3,
                    'led_zeppelin', "led_zeppelin_whole_lotta_love")
    random.seed(108)

    INTRO = (0, 2)
    VERSE1 = (2, 10)
    CHORUS1 = (10, 18)
    BRIDGE = (18, 22)
    VERSE2 = (22, 30)
    OUTRO = (30, 34)

    # Lead: E blues riff with chromatic descend
    def blues_riff(bar, vel=100):
        b = s.bt(bar)
        riff = [(n('E4'), 0, EIGHTH), (n('G4'), EIGHTH, EIGHTH),
                (n('A4'), QUARTER, EIGHTH), (n('Bb4'), DOT_QUARTER, EIGHTH),
                (n('A4'), HALF, EIGHTH), (n('G4'), HALF + EIGHTH, EIGHTH),
                (n('E4'), HALF + QUARTER, QUARTER)]
        for nt, off, dur in riff:
            add_note(s.lead, nt, vel, b + off, dur, CH_LEAD)

    # Bass: E2 driving 8ths
    def bass_drive(bar, vel=95):
        b = s.bt(bar)
        for i in range(8):
            nt = n('E2') if i % 4 != 3 else n('G2')
            add_note(s.bass, nt, vel, b + i * EIGHTH, EIGHTH - 10, CH_BASS)

    # Kick: Bonham groove
    def kick_bonham(bar, vel=112):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + QUARTER + EIGHTH, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 15, b + HALF + QUARTER, EIGHTH, CH_DRUMS)

    # Snare: 2-4 with ghosts built into main pattern
    def snare_24(bar, vel=108):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: open hat pattern
    def hat_open(bar, vel=80):
        b = s.bt(bar)
        for i in range(8):
            nt = HAT_OPEN if i % 2 == 0 else HAT_CLOSED
            add_note(s.hihats, nt, vel - (i % 2) * 12,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Perc: tom fills
    def tom_fill(bar, vel=100):
        b = s.bt(bar)
        for i in range(4):
            nt = TOM_HI if i < 2 else TOM_LO
            add_note(s.percussion, nt, vel + i * 5,
                     b + HALF + i * EIGHTH, EIGHTH - 5, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        blues_riff(bar, 90)

    for bar in range(*VERSE1):
        blues_riff(bar, 100)
        bass_drive(bar, 92)
        kick_bonham(bar); snare_24(bar); hat_open(bar)

    for bar in range(*CHORUS1):
        blues_riff(bar, 115)
        bass_drive(bar, 100)
        kick_bonham(bar, 118); snare_24(bar, 115); hat_open(bar, 88)
        if bar % 4 == 1: tom_fill(bar)

    for bar in range(*BRIDGE):
        bass_drive(bar, 80)
        kick_bonham(bar, 90); hat_open(bar, 65)

    for bar in range(*VERSE2):
        blues_riff(bar, 100)
        bass_drive(bar, 92)
        kick_bonham(bar); snare_24(bar); hat_open(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.15
        blues_riff(bar, vscale(100, fade))
        bass_drive(bar, vscale(92, fade))
        kick_bonham(bar, vscale(112, fade))
        snare_24(bar, vscale(108, fade))

    s.save()


# ---------------------------------------------------------------------------
# 9. Led Zeppelin — Kashmir (80 BPM, D, 36 bars)
# ---------------------------------------------------------------------------
def gen_kashmir():
    s = SongBuilder("Kashmir", "Led Zeppelin", 80, "D", 36, 4, 'led_zeppelin',
                    "led_zeppelin_kashmir")
    random.seed(109)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 20)
    BRIDGE = (20, 28)
    OUTRO = (28, 36)

    # Lead: chromatic guitar riff D-Eb-E-F-F#-G
    def chromatic_riff(bar, vel=100):
        b = s.bt(bar)
        notes = [n('D4'), n('Eb4'), n('E4'), n('F4'), n('F#4'), n('G4')]
        for i, nt in enumerate(notes):
            dur = t(0.66) if i < 5 else QUARTER
            add_note(s.lead, nt, vel, b + i * t(0.66), dur, CH_LEAD)

    # Counter: ascending string line D-E-F-G-A
    def string_line(bar, vel=80):
        b = s.bt(bar)
        notes = [n('D5'), n('E5'), n('F5'), n('G5'), n('A5')]
        for i, nt in enumerate(notes):
            add_note(s.counter, nt, vel, b + i * t(0.8), t(0.75), CH_COUNTER)

    # Bass: D2 drone with movement
    def bass_drone(bar, vel=95):
        b = s.bt(bar)
        for i in range(4):
            nt = n('D2') if i != 2 else n('E2')
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Drums: march pattern kick-kick-snare
    def kick_march(bar, vel=110):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + QUARTER, EIGHTH, CH_DRUMS)

    def snare_march(bar, vel=105):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + HALF, EIGHTH, CH_DRUMS)

    def hat_ride(bar, vel=70):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, HAT_CLOSED, vel - (i % 2) * 10,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Perc: heavy toms
    def heavy_toms(bar, vel=100):
        b = s.bt(bar)
        add_note(s.percussion, TOM_HI, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.percussion, TOM_LO, vel + 5, b + HALF + QUARTER, EIGHTH, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        chromatic_riff(bar, 85)
        kick_march(bar, 90)

    for bar in range(*VERSE1):
        chromatic_riff(bar, 100)
        string_line(bar, 70)
        bass_drone(bar, 92)
        kick_march(bar); snare_march(bar); hat_ride(bar)
        heavy_toms(bar)

    for bar in range(*CHORUS1):
        chromatic_riff(bar, 115)
        string_line(bar, 85)
        bass_drone(bar, 100)
        kick_march(bar, 118); snare_march(bar, 112); hat_ride(bar, 80)
        heavy_toms(bar, 110)

    for bar in range(*BRIDGE):
        string_line(bar, 75)
        bass_drone(bar, 85)
        kick_march(bar, 95); snare_march(bar, 90); hat_ride(bar, 65)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.08
        chromatic_riff(bar, vscale(100, fade))
        bass_drone(bar, vscale(92, fade))
        kick_march(bar, vscale(110, fade))
        snare_march(bar, vscale(105, fade))
        heavy_toms(bar, vscale(100, fade))

    s.save()


# ---------------------------------------------------------------------------
# 10. The Doors — Riders on the Storm (108 BPM, Em, 34 bars)
# ---------------------------------------------------------------------------
def gen_riders_on_the_storm():
    s = SongBuilder("Riders on the Storm", "The Doors", 108, "Em", 34, 3,
                    'the_doors', "the_doors_riders_on_the_storm")
    random.seed(110)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 18)
    VERSE2 = (18, 26)
    OUTRO = (26, 34)

    # Lead: Rhodes Em7 rain arpeggio
    def rhodes_arp(bar, vel=78):
        b = s.bt(bar)
        # Em7: E-G-B-D
        arp = [n('E4'), n('G4'), n('B4'), n('D5'), n('B4'), n('G4')]
        for i, nt in enumerate(arp):
            add_note(s.lead, nt, vel, b + i * t(0.66), t(0.6), CH_LEAD)

    # Bass: walking E-G-A-B
    def bass_walk(bar, vel=85):
        b = s.bt(bar)
        walk = [n('E2'), n('G2'), n('A2'), n('B2')]
        for i, nt in enumerate(walk):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Kick: light brush feel
    def kick_brush(bar, vel=80):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 15, b + HALF + EIGHTH, EIGHTH, CH_DRUMS)

    # Snare: rimshot on 2-4 (using low velocity snare)
    def snare_rim(bar, vel=70):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: ride pattern
    def ride(bar, vel=65):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, SHAKER, vel - (i % 2) * 8,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # FX: rain sweep (slow notes)
    def rain_sweep(bar, vel=50):
        b = s.bt(bar)
        add_note(s.fx_sweep, n('E5'), vel, b, BAR - 10, CH_FX)

    # Build
    for bar in range(*INTRO):
        rhodes_arp(bar, 65)
        rain_sweep(bar, 40)

    for bar in range(*VERSE1):
        rhodes_arp(bar, 78)
        bass_walk(bar, 82)
        kick_brush(bar); snare_rim(bar); ride(bar)
        if bar % 4 == 0: rain_sweep(bar, 45)

    for bar in range(*CHORUS1):
        rhodes_arp(bar, 90)
        bass_walk(bar, 90)
        kick_brush(bar, 90); snare_rim(bar, 80); ride(bar, 72)

    for bar in range(*VERSE2):
        rhodes_arp(bar, 78)
        bass_walk(bar, 82)
        kick_brush(bar); snare_rim(bar); ride(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.08
        rhodes_arp(bar, vscale(78, fade))
        bass_walk(bar, vscale(82, fade))
        kick_brush(bar, vscale(80, fade))
        ride(bar, vscale(65, fade))
        rain_sweep(bar, vscale(40, fade))

    s.save()


# ---------------------------------------------------------------------------
# 11. The Doors — Light My Fire (130 BPM, Am, 34 bars)
# ---------------------------------------------------------------------------
def gen_light_my_fire():
    s = SongBuilder("Light My Fire", "The Doors", 130, "Am", 34, 3,
                    'the_doors', "the_doors_light_my_fire")
    random.seed(111)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    SOLO = (16, 26)
    CHORUS2 = (26, 30)
    OUTRO = (30, 34)

    # Lead: organ Am-G-F#m ascending
    def organ_lead(bar, vel=88):
        b = s.bt(bar)
        prog = [(n('A4'), n('C5'), n('E5')),
                (n('G4'), n('B4'), n('D5')),
                (n('F#4'), n('A4'), n('C#5'))]
        chord = prog[bar % 3]
        for i, nt in enumerate(chord):
            add_note(s.lead, nt, vel, b + i * t(0.33), HALF, CH_LEAD)

    # Counter: organ solo arpeggios
    def solo_arp(bar, vel=90):
        b = s.bt(bar)
        scale = [n('A4'), n('B4'), n('C5'), n('D5'), n('E5'),
                 n('F5'), n('G5'), n('A5')]
        phrase_idx = bar % 4
        start = phrase_idx * 2
        for i in range(6):
            nt = scale[(start + i) % len(scale)]
            add_note(s.counter, nt, vel, b + i * t(0.66), t(0.6), CH_COUNTER)

    # Bass: root walking with 5ths
    def bass_walk(bar, vel=88):
        b = s.bt(bar)
        roots = [n('A2'), n('E2'), n('D2'), n('A2')]
        root = roots[bar % 4]
        fifth = root + 7
        pattern = [root, fifth, root + 12, fifth]
        for i, nt in enumerate(pattern):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Kick: bossa nova
    def kick_bossa(bar, vel=90):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + DOT_QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF + QUARTER, EIGHTH, CH_DRUMS)

    # Snare: rimclick
    def snare_rim(bar, vel=68):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: ride bell
    def ride_bell(bar, vel=72):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, SHAKER, vel - (i % 2) * 10,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        organ_lead(bar, 75)
        ride_bell(bar, 60)

    for bar in range(*VERSE1):
        organ_lead(bar, 88)
        bass_walk(bar, 85)
        kick_bossa(bar); snare_rim(bar); ride_bell(bar)

    for bar in range(*CHORUS1):
        organ_lead(bar, 100)
        bass_walk(bar, 95)
        kick_bossa(bar, 100); snare_rim(bar, 78); ride_bell(bar, 80)

    for bar in range(*SOLO):
        solo_arp(bar, 92)
        bass_walk(bar, 85)
        kick_bossa(bar); snare_rim(bar); ride_bell(bar)

    for bar in range(*CHORUS2):
        organ_lead(bar, 100)
        bass_walk(bar, 95)
        kick_bossa(bar, 100); snare_rim(bar, 78); ride_bell(bar, 80)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.15
        organ_lead(bar, vscale(88, fade))
        bass_walk(bar, vscale(85, fade))
        kick_bossa(bar, vscale(90, fade))
        ride_bell(bar, vscale(72, fade))

    s.save()


# ---------------------------------------------------------------------------
# 12. Jimi Hendrix — Purple Haze (108 BPM, E, 34 bars)
# ---------------------------------------------------------------------------
def gen_purple_haze():
    s = SongBuilder("Purple Haze", "Jimi Hendrix", 108, "E", 34, 3,
                    'jimi_hendrix', "jimi_hendrix_purple_haze")
    random.seed(112)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 18)
    SOLO = (18, 26)
    OUTRO = (26, 34)

    # Lead: Bb-E tritone intro + E7#9 stabs
    def tritone_riff(bar, vel=100):
        b = s.bt(bar)
        # Bb4 to E4 tritone
        add_note(s.lead, n('Bb4'), vel, b, QUARTER, CH_LEAD)
        add_note(s.lead, n('E4'), vel + 5, b + QUARTER, HALF, CH_LEAD)
        # Repeat with octave
        add_note(s.lead, n('Bb4'), vel - 5, b + HALF + QUARTER, EIGHTH, CH_LEAD)

    # Chords: E-G-A power chord riff
    def chord_riff(bar, vel=90):
        b = s.bt(bar)
        prog = [pc(n('E3')), pc(n('G3')), pc(n('A3')), pc(n('E3'))]
        for i, chord in enumerate(prog):
            add_chord_ev(s.chords, chord, vel, b + i * QUARTER,
                         QUARTER - 15, CH_CHORDS)

    # Bass: E2 octave jumps
    def bass_octave(bar, vel=95):
        b = s.bt(bar)
        for i in range(4):
            nt = n('E2') if i % 2 == 0 else n('E3')
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Kick: loose with crashes
    def kick_loose(bar, vel=105):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + QUARTER + EIGHTH, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    # Snare: 2-4 with space
    def snare_24(bar, vel=100):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: crash accents
    def hat_crash(bar, vel=78):
        b = s.bt(bar)
        for i in range(4):
            add_note(s.hihats, HAT_CLOSED, vel, b + i * QUARTER, EIGHTH, CH_DRUMS)
        if bar % 4 == 0:
            add_note(s.hihats, CLAP, vel + 20, b, EIGHTH, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        tritone_riff(bar, 95)
        kick_loose(bar, 90)

    for bar in range(*VERSE1):
        tritone_riff(bar, 100)
        chord_riff(bar, 85)
        bass_octave(bar, 90)
        kick_loose(bar); snare_24(bar); hat_crash(bar)

    for bar in range(*CHORUS1):
        chord_riff(bar, 100)
        bass_octave(bar, 100)
        kick_loose(bar, 112); snare_24(bar, 108); hat_crash(bar, 85)

    for bar in range(*SOLO):
        tritone_riff(bar, 110)
        bass_octave(bar, 92)
        kick_loose(bar); snare_24(bar); hat_crash(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.08
        tritone_riff(bar, vscale(100, fade))
        chord_riff(bar, vscale(85, fade))
        bass_octave(bar, vscale(90, fade))
        kick_loose(bar, vscale(105, fade))
        snare_24(bar, vscale(100, fade))

    s.save()


# ---------------------------------------------------------------------------
# 13. Jimi Hendrix — Voodoo Child (88 BPM, Eb, 34 bars)
# ---------------------------------------------------------------------------
def gen_voodoo_child():
    s = SongBuilder("Voodoo Child", "Jimi Hendrix", 88, "Eb", 34, 4,
                    'jimi_hendrix', "jimi_hendrix_voodoo_child")
    random.seed(113)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 18)
    SOLO = (18, 26)
    OUTRO = (26, 34)

    # Lead: wah riff Eb-Db-Bb-Ab descending
    def wah_riff(bar, vel=100):
        b = s.bt(bar)
        notes = [n('Eb4'), n('Db4'), n('Bb3'), n('Ab3')]
        for i, nt in enumerate(notes):
            dur = QUARTER if i < 3 else HALF
            add_note(s.lead, nt, vel, b + i * QUARTER, dur, CH_LEAD)

    # Bass: Eb2 chromatic walks
    def bass_chromatic(bar, vel=95):
        b = s.bt(bar)
        walk = [n('Eb2'), n('E2'), n('F2'), n('Gb2'),
                n('G2'), n('Ab2'), n('Eb2'), n('Eb2')]
        for i, nt in enumerate(walk):
            add_note(s.bass, nt, vel, b + i * EIGHTH, EIGHTH - 10, CH_BASS)

    # Kick: shuffle groove
    def kick_shuffle(bar, vel=108):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + TRIPLET_8TH * 2, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 12, b + HALF + TRIPLET_8TH * 2, EIGHTH, CH_DRUMS)

    # Snare: backbeat with ghosts
    def snare_bb(bar, vel=105):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: open hat shuffle
    def hat_shuffle(bar, vel=78):
        b = s.bt(bar)
        for i in range(4):
            add_note(s.hihats, HAT_OPEN, vel, b + i * QUARTER, EIGHTH, CH_DRUMS)
            add_note(s.hihats, HAT_CLOSED, vel - 15,
                     b + i * QUARTER + TRIPLET_8TH * 2, EIGHTH, CH_DRUMS)

    # Perc: tom fills
    def tom_fill(bar, vel=95):
        b = s.bt(bar)
        for i in range(4):
            nt = TOM_HI if i < 2 else TOM_LO
            add_note(s.percussion, nt, vel + i * 5,
                     b + HALF + i * EIGHTH, EIGHTH, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        wah_riff(bar, 90)
        kick_shuffle(bar, 85)

    for bar in range(*VERSE1):
        wah_riff(bar, 100)
        bass_chromatic(bar, 92)
        kick_shuffle(bar); snare_bb(bar); hat_shuffle(bar)

    for bar in range(*CHORUS1):
        wah_riff(bar, 115)
        bass_chromatic(bar, 100)
        kick_shuffle(bar, 115); snare_bb(bar, 110); hat_shuffle(bar, 85)

    for bar in range(*SOLO):
        wah_riff(bar, 110)
        bass_chromatic(bar, 92)
        kick_shuffle(bar); snare_bb(bar); hat_shuffle(bar)
        if bar % 4 == 3: tom_fill(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.08
        wah_riff(bar, vscale(100, fade))
        bass_chromatic(bar, vscale(92, fade))
        kick_shuffle(bar, vscale(108, fade))
        snare_bb(bar, vscale(105, fade))
        hat_shuffle(bar, vscale(78, fade))

    s.save()


# ---------------------------------------------------------------------------
# 14. Santana — Black Magic Woman (124 BPM, Dm, 36 bars)
# ---------------------------------------------------------------------------
def gen_black_magic_woman():
    s = SongBuilder("Black Magic Woman", "Santana", 124, "Dm", 36, 3,
                    'santana', "black_magic_woman")
    random.seed(114)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    SOLO = (16, 24)
    VERSE2 = (24, 32)
    OUTRO = (32, 36)

    # Lead: Dm pentatonic lead  D4=62, F4=65, G4=67, A4=69, C5=72
    def dm_lead(bar, vel=90):
        b = s.bt(bar)
        phrases = [
            [(0, 62, 0.75), (0.75, 65, 0.5), (1.25, 67, 0.5),
             (1.75, 69, 1.0), (3.0, 72, 1.0)],
            [(0, 72, 0.5), (0.5, 69, 0.5), (1.0, 67, 1.0),
             (2.0, 65, 0.75), (2.75, 62, 1.25)],
        ]
        phrase = phrases[bar % 2]
        for beat, note, dur in phrase:
            add_note(s.lead, note, vel, b + t(beat), t(dur), CH_LEAD)

    # Chords: Dm-Gm comps
    def dm_gm_comp(bar, vel=80):
        b = s.bt(bar)
        # Dm: D3=50, F3=53, A3=57  Gm: G3=55, Bb3=58, D4=62
        chord = [50, 53, 57] if bar % 2 == 0 else [55, 58, 62]
        for beat_off in [0.0, 1.5, 2.0, 3.5]:
            add_chord_ev(s.chords, chord, vel, b + t(beat_off), t(0.5), CH_CHORDS)

    # Bass: Latin walking D-F-G-A
    def latin_bass(bar, vel=90):
        b = s.bt(bar)
        walk = [n('D2'), n('F2'), n('G2'), n('A2')]
        for i, nt in enumerate(walk):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)
        # Syncopated ghost on "and of 2"
        add_note(s.bass, n('E2'), vel - 25, b + t(2.5), EIGHTH, CH_BASS)

    # Kick: Latin groove
    def kick_latin(bar, vel=105):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + t(2.5), EIGHTH, CH_DRUMS)

    # Snare: on 4
    def snare_on4(bar, vel=100):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: ride bell
    def ride_bell(bar, vel=78):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, SHAKER, vel - (i % 2) * 10,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Perc: conga pattern on toms
    def conga_pattern(bar, vel=80):
        b = s.bt(bar)
        add_note(s.percussion, TOM_HI, vel, b + t(0.5), EIGHTH, CH_DRUMS)
        add_note(s.percussion, TOM_LO, vel - 5, b + t(1.0), EIGHTH, CH_DRUMS)
        add_note(s.percussion, TOM_HI, vel - 10, b + t(1.5), EIGHTH, CH_DRUMS)
        add_note(s.percussion, TOM_HI, vel, b + t(2.5), EIGHTH, CH_DRUMS)
        add_note(s.percussion, TOM_LO, vel - 5, b + t(3.5), EIGHTH, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        dm_lead(bar, 80)

    for bar in range(*VERSE1):
        dm_lead(bar, 88)
        dm_gm_comp(bar, 75)
        latin_bass(bar, 85)
        kick_latin(bar); snare_on4(bar); ride_bell(bar)
        conga_pattern(bar, 72)

    for bar in range(*CHORUS1):
        dm_lead(bar, 105)
        dm_gm_comp(bar, 92)
        latin_bass(bar, 95)
        kick_latin(bar, 112); snare_on4(bar, 108); ride_bell(bar, 85)
        conga_pattern(bar, 85)

    for bar in range(*SOLO):
        dm_lead(bar, 100)
        latin_bass(bar, 88)
        kick_latin(bar); snare_on4(bar); ride_bell(bar)
        conga_pattern(bar, 78)

    for bar in range(*VERSE2):
        dm_lead(bar, 88)
        dm_gm_comp(bar, 75)
        latin_bass(bar, 85)
        kick_latin(bar); snare_on4(bar); ride_bell(bar)
        conga_pattern(bar, 72)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.15
        dm_lead(bar, vscale(88, fade))
        latin_bass(bar, vscale(85, fade))
        kick_latin(bar, vscale(105, fade))
        conga_pattern(bar, vscale(72, fade))

    s.save()


# ---------------------------------------------------------------------------
# 15. Santana — Smooth (116 BPM, Am, 32 bars)
# ---------------------------------------------------------------------------
def gen_smooth():
    s = SongBuilder("Smooth", "Santana", 116, "Am", 32, 3, 'santana', "smooth")
    random.seed(115)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    VERSE2 = (16, 24)
    SOLO = (24, 28)
    OUTRO = (28, 32)

    # Lead: Am arpeggio riff A-C-E-A
    def am_arp(bar, vel=90):
        b = s.bt(bar)
        notes = [n('A4'), n('C5'), n('E5'), n('A5'),
                 n('E5'), n('C5'), n('A4'), n('E4')]
        for i, nt in enumerate(notes):
            add_note(s.lead, nt, vel, b + i * EIGHTH, EIGHTH - 10, CH_LEAD)

    # Chords: Am-F-E7 comps
    def chord_comp(bar, vel=82):
        b = s.bt(bar)
        progs = [[n('A3'), n('C4'), n('E4')],
                 [n('F3'), n('A3'), n('C4')],
                 [n('E3'), n('G#3'), n('B3')],
                 [n('A3'), n('C4'), n('E4')]]
        chord = progs[bar % 4]
        for beat in [0, 1.5, 2, 3.5]:
            add_chord_ev(s.chords, chord, vel, b + t(beat), t(0.5), CH_CHORDS)

    # Bass: syncopated ghost notes
    def bass_synco(bar, vel=92):
        b = s.bt(bar)
        roots = [n('A2'), n('F2'), n('E2'), n('A2')]
        root = roots[bar % 4]
        pattern = [(0, root, 90), (0.75, root + 5, 60), (1.5, root, 85),
                   (2.0, root + 7, 80), (2.75, root + 3, 55), (3.5, root, 88)]
        for beat, nt, v in pattern:
            add_note(s.bass, nt, vscale(v, vel / 92), b + t(beat),
                     t(0.4), CH_BASS)

    # Kick: pop-latin
    def kick_pop(bar, vel=105):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + t(1.5), EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + HALF, EIGHTH, CH_DRUMS)

    # Snare: 2-4
    def snare_24(bar, vel=100):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: 16th pattern
    def hat_16ths(bar, vel=72):
        b = s.bt(bar)
        for i in range(16):
            v = vel if i % 4 == 0 else (vel - 10 if i % 2 == 0 else vel - 20)
            add_note(s.hihats, HAT_CLOSED, v, b + i * SIXTEENTH,
                     SIXTEENTH - 5, CH_DRUMS)

    # Perc: shaker 16ths
    def shaker_16ths(bar, vel=55):
        b = s.bt(bar)
        for i in range(16):
            v = vel if i % 4 == 0 else vel - 12
            add_note(s.percussion, SHAKER, v, b + i * SIXTEENTH,
                     SIXTEENTH - 5, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        am_arp(bar, 78)
        hat_16ths(bar, 55)

    for bar in range(*VERSE1):
        am_arp(bar, 88)
        chord_comp(bar, 78)
        bass_synco(bar, 88)
        kick_pop(bar); snare_24(bar); hat_16ths(bar)
        shaker_16ths(bar, 48)

    for bar in range(*CHORUS1):
        am_arp(bar, 105)
        chord_comp(bar, 95)
        bass_synco(bar, 98)
        kick_pop(bar, 112); snare_24(bar, 108); hat_16ths(bar, 82)
        shaker_16ths(bar, 58)

    for bar in range(*VERSE2):
        am_arp(bar, 88)
        chord_comp(bar, 78)
        bass_synco(bar, 88)
        kick_pop(bar); snare_24(bar); hat_16ths(bar)
        shaker_16ths(bar, 48)

    for bar in range(*SOLO):
        am_arp(bar, 100)
        bass_synco(bar, 90)
        kick_pop(bar); snare_24(bar); hat_16ths(bar)
        shaker_16ths(bar, 52)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.18
        am_arp(bar, vscale(88, fade))
        bass_synco(bar, vscale(88, fade))
        kick_pop(bar, vscale(105, fade))
        snare_24(bar, vscale(100, fade))
        hat_16ths(bar, vscale(72, fade))

    s.save()


# ---------------------------------------------------------------------------
# 16. Santana — Evil Ways (124 BPM, Gm, 32 bars)
# ---------------------------------------------------------------------------
def gen_evil_ways():
    s = SongBuilder("Evil Ways", "Santana", 124, "Gm", 32, 3, 'santana',
                    "evil_ways")
    random.seed(116)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 16)
    VERSE2 = (16, 24)
    CHORUS2 = (24, 28)
    OUTRO = (28, 32)

    # Lead: organ Gm7-C7 vamp
    def organ_vamp(bar, vel=88):
        b = s.bt(bar)
        # Gm7: G3-Bb3-D4-F4   C7: C4-E4-G4-Bb4
        if bar % 2 == 0:
            chord = [n('G3'), n('Bb3'), n('D4'), n('F4')]
        else:
            chord = [n('C4'), n('E4'), n('G4'), n('Bb4')]
        # Rhythmic stabs
        for beat_off in [0, 0.5, 1.5, 2.0, 3.0, 3.5]:
            add_chord_ev(s.lead, chord, vel, b + t(beat_off), t(0.4), CH_LEAD)

    # Bass: chromatic approach
    def bass_chromatic(bar, vel=90):
        b = s.bt(bar)
        if bar % 2 == 0:
            walk = [n('G2'), n('Bb2'), n('C3'), n('D3')]
        else:
            walk = [n('C3'), n('B2'), n('Bb2'), n('A2')]
        for i, nt in enumerate(walk):
            add_note(s.bass, nt, vel, b + i * QUARTER, QUARTER - 10, CH_BASS)

    # Kick: Latin shuffle
    def kick_latin(bar, vel=105):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 10, b + t(2.5), EIGHTH, CH_DRUMS)

    # Snare: on 4
    def snare_on4(bar, vel=100):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: timbale-style
    def hat_timbale(bar, vel=75):
        b = s.bt(bar)
        for i in range(8):
            v = vel if i % 2 == 0 else vel - 15
            add_note(s.hihats, HAT_CLOSED, v, b + i * EIGHTH,
                     EIGHTH - 10, CH_DRUMS)

    # Perc: conga pattern
    def conga(bar, vel=78):
        b = s.bt(bar)
        pattern = [(0.5, TOM_HI, 80), (1.0, TOM_LO, 75),
                   (1.5, TOM_HI, 70), (2.5, TOM_HI, 80),
                   (3.0, TOM_LO, 72), (3.5, TOM_LO, 68)]
        for beat, note, v in pattern:
            add_note(s.percussion, note, vscale(v, vel / 78),
                     b + t(beat), EIGHTH, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        organ_vamp(bar, 75)
        hat_timbale(bar, 60)

    for bar in range(*VERSE1):
        organ_vamp(bar, 88)
        bass_chromatic(bar, 85)
        kick_latin(bar); snare_on4(bar); hat_timbale(bar)
        conga(bar, 72)

    for bar in range(*CHORUS1):
        organ_vamp(bar, 105)
        bass_chromatic(bar, 95)
        kick_latin(bar, 112); snare_on4(bar, 108); hat_timbale(bar, 82)
        conga(bar, 85)

    for bar in range(*VERSE2):
        organ_vamp(bar, 88)
        bass_chromatic(bar, 85)
        kick_latin(bar); snare_on4(bar); hat_timbale(bar)
        conga(bar, 72)

    for bar in range(*CHORUS2):
        organ_vamp(bar, 105)
        bass_chromatic(bar, 95)
        kick_latin(bar, 112); snare_on4(bar, 108); hat_timbale(bar, 82)
        conga(bar, 85)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.18
        organ_vamp(bar, vscale(88, fade))
        bass_chromatic(bar, vscale(85, fade))
        kick_latin(bar, vscale(105, fade))
        conga(bar, vscale(72, fade))

    s.save()


# ---------------------------------------------------------------------------
# 17. Muse — Hysteria (94 BPM, Am, 34 bars)
# ---------------------------------------------------------------------------
def gen_hysteria():
    s = SongBuilder("Hysteria", "Muse", 94, "Am", 34, 5, 'muse', "hysteria")
    random.seed(117)

    INTRO = (0, 2)
    VERSE1 = (2, 10)
    CHORUS1 = (10, 18)
    BRIDGE = (18, 22)
    VERSE2 = (22, 30)
    OUTRO = (30, 34)

    # Lead: Am-E sustained guitar
    def sustained_lead(bar, vel=90):
        b = s.bt(bar)
        notes = [n('A4'), n('E5')] if bar % 2 == 0 else [n('E5'), n('A4')]
        for i, nt in enumerate(notes):
            add_note(s.lead, nt, vel, b + i * HALF, HALF - 10, CH_LEAD)

    # Counter: palm-muted 8ths (verse 2)
    def palm_mute(bar, vel=82):
        b = s.bt(bar)
        for i in range(8):
            add_chord_ev(s.counter, pc(n('A3')), vel,
                         b + i * EIGHTH, EIGHTH - 20, CH_COUNTER)

    # Bass: THE riff A-E-A-G-F-E-D-C 16ths
    def hysteria_bass(bar, vel=100):
        b = s.bt(bar)
        riff = [n('A2'), n('E3'), n('A2'), n('G2'),
                n('F2'), n('E2'), n('D2'), n('C2'),
                n('A2'), n('E3'), n('A2'), n('G2'),
                n('F2'), n('E2'), n('D2'), n('C2')]
        for i, nt in enumerate(riff):
            add_note(s.bass, nt, vel, b + i * SIXTEENTH,
                     SIXTEENTH - 5, CH_BASS)

    # Kick: machine-gun 16ths
    def kick_16ths(bar, vel=105):
        b = s.bt(bar)
        for i in range(16):
            v = vel if i % 4 == 0 else vel - 15
            add_note(s.kick, KICK, v, b + i * SIXTEENTH,
                     SIXTEENTH - 5, CH_DRUMS)

    # Snare: 2-4 heavy
    def snare_heavy(bar, vel=112):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: crash accents
    def hat_crash(bar, vel=80):
        b = s.bt(bar)
        if bar % 4 == 0:
            add_note(s.hihats, CLAP, vel + 20, b, EIGHTH, CH_DRUMS)
        for i in range(4):
            add_note(s.hihats, HAT_CLOSED, vel, b + i * QUARTER,
                     EIGHTH, CH_DRUMS)

    # Perc: tom fills at section changes
    def tom_fill(bar, vel=100):
        b = s.bt(bar)
        for i in range(8):
            nt = TOM_HI if i < 4 else TOM_LO
            add_note(s.percussion, nt, vel + i * 3,
                     b + i * EIGHTH, EIGHTH - 5, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        hysteria_bass(bar, 95)

    for bar in range(*VERSE1):
        sustained_lead(bar, 88)
        hysteria_bass(bar, 100)
        kick_16ths(bar); snare_heavy(bar); hat_crash(bar)

    for bar in range(*CHORUS1):
        sustained_lead(bar, 110)
        hysteria_bass(bar, 108)
        kick_16ths(bar, 112); snare_heavy(bar, 118); hat_crash(bar, 88)
        if bar == CHORUS1[1] - 1: tom_fill(bar)

    for bar in range(*BRIDGE):
        palm_mute(bar, 78)
        hysteria_bass(bar, 90)
        kick_16ths(bar, 95); snare_heavy(bar, 100)

    for bar in range(*VERSE2):
        sustained_lead(bar, 88)
        palm_mute(bar, 75)
        hysteria_bass(bar, 100)
        kick_16ths(bar); snare_heavy(bar); hat_crash(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.15
        sustained_lead(bar, vscale(88, fade))
        hysteria_bass(bar, vscale(100, fade))
        kick_16ths(bar, vscale(105, fade))
        snare_heavy(bar, vscale(112, fade))

    s.save()


# ---------------------------------------------------------------------------
# 18. Muse — Supermassive Black Hole (120 BPM, Am, 32 bars)
# ---------------------------------------------------------------------------
def gen_supermassive_black_hole():
    s = SongBuilder("Supermassive Black Hole", "Muse", 120, "Am", 32, 3,
                    'muse', "supermassive_black_hole")
    random.seed(118)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 20)
    VERSE2 = (20, 28)
    OUTRO = (28, 32)

    # Lead: funky muted scratch Am staccato
    def funky_scratch(bar, vel=92):
        b = s.bt(bar)
        # Staccato Am chord hits on syncopated positions
        chord = [n('A3'), n('C4'), n('E4')]
        hits = [0, 0.5, 1.0, 1.75, 2.5, 3.0, 3.5]
        for off in hits:
            add_chord_ev(s.lead, chord, vel, b + t(off), t(0.2), CH_LEAD)

    # Chords: Dm-Am-E7 hits
    def chord_hits(bar, vel=85):
        b = s.bt(bar)
        progs = [[n('D3'), n('F3'), n('A3')],
                 [n('A3'), n('C4'), n('E4')],
                 [n('E3'), n('G#3'), n('B3')]]
        chord = progs[bar % 3]
        for beat in [0, 2]:
            add_chord_ev(s.chords, chord, vel, b + beat * QUARTER,
                         QUARTER - 15, CH_CHORDS)

    # Bass: octave-jump funk
    def bass_funk(bar, vel=95):
        b = s.bt(bar)
        root = n('A2') if bar % 2 == 0 else n('E2')
        pattern = [(0, root, 95), (0.5, root + 12, 80),
                   (1.0, root, 90), (1.75, root + 12, 75),
                   (2.0, root + 5, 85), (2.5, root + 12, 78),
                   (3.0, root, 92), (3.5, root + 7, 70)]
        for beat, nt, v in pattern:
            add_note(s.bass, nt, vscale(v, vel / 95), b + t(beat),
                     t(0.4), CH_BASS)

    # Kick: syncopated funk
    def kick_funk(bar, vel=108):
        b = s.bt(bar)
        add_note(s.kick, KICK, vel, b, EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 12, b + t(0.75), EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 5, b + t(2.0), EIGHTH, CH_DRUMS)
        add_note(s.kick, KICK, vel - 8, b + t(2.75), EIGHTH, CH_DRUMS)

    # Snare: 2-4 with ghosts
    def snare_24(bar, vel=105):
        b = s.bt(bar)
        add_note(s.snare, SNARE, vel, b + QUARTER, EIGHTH, CH_DRUMS)
        add_note(s.snare, SNARE, vel, b + QUARTER * 3, EIGHTH, CH_DRUMS)

    # Hats: 16th pattern
    def hat_16ths(bar, vel=72):
        b = s.bt(bar)
        for i in range(16):
            v = vel if i % 4 == 0 else (vel - 10 if i % 2 == 0 else vel - 20)
            add_note(s.hihats, HAT_CLOSED, v, b + i * SIXTEENTH,
                     SIXTEENTH - 5, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        funky_scratch(bar, 80)
        hat_16ths(bar, 58)

    for bar in range(*VERSE1):
        funky_scratch(bar, 92)
        chord_hits(bar, 80)
        bass_funk(bar, 90)
        kick_funk(bar); snare_24(bar); hat_16ths(bar)

    for bar in range(*CHORUS1):
        funky_scratch(bar, 108)
        chord_hits(bar, 98)
        bass_funk(bar, 100)
        kick_funk(bar, 115); snare_24(bar, 112); hat_16ths(bar, 82)

    for bar in range(*VERSE2):
        funky_scratch(bar, 92)
        chord_hits(bar, 80)
        bass_funk(bar, 90)
        kick_funk(bar); snare_24(bar); hat_16ths(bar)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.18
        funky_scratch(bar, vscale(92, fade))
        bass_funk(bar, vscale(90, fade))
        kick_funk(bar, vscale(108, fade))
        snare_24(bar, vscale(105, fade))
        hat_16ths(bar, vscale(72, fade))

    s.save()


# ---------------------------------------------------------------------------
# 19. Muse — Knights of Cydonia (138 BPM, Em, 36 bars)
# ---------------------------------------------------------------------------
def gen_knights_of_cydonia():
    s = SongBuilder("Knights of Cydonia", "Muse", 138, "Em", 36, 4, 'muse',
                    "knights_of_cydonia")
    random.seed(119)

    INTRO = (0, 4)
    VERSE1 = (4, 12)
    CHORUS1 = (12, 20)
    BRIDGE = (20, 28)
    OUTRO = (28, 36)

    # Lead: heroic E-G-A-B-D melody
    def heroic_melody(bar, vel=95):
        b = s.bt(bar)
        notes = [n('E4'), n('G4'), n('A4'), n('B4'),
                 n('D5'), n('B4'), n('A4'), n('G4')]
        for i, nt in enumerate(notes):
            add_note(s.lead, nt, vel, b + i * EIGHTH, EIGHTH - 10, CH_LEAD)

    # Chords: E5 galloping 8th triplets
    def gallop_chords(bar, vel=90):
        b = s.bt(bar)
        for i in range(12):
            add_chord_ev(s.chords, pc(n('E3')), vel,
                         b + i * TRIPLET_8TH, TRIPLET_8TH - 10, CH_CHORDS)

    # Bass: E2 gallop matching
    def bass_gallop(bar, vel=95):
        b = s.bt(bar)
        for i in range(12):
            nt = n('E2') if i % 3 != 2 else n('B2')
            add_note(s.bass, nt, vel, b + i * TRIPLET_8TH,
                     TRIPLET_8TH - 10, CH_BASS)

    # Kick: 6/8 gallop kick-kick-snare
    def kick_gallop(bar, vel=110):
        b = s.bt(bar)
        for i in range(4):
            add_note(s.kick, KICK, vel, b + i * QUARTER, EIGHTH, CH_DRUMS)
            add_note(s.kick, KICK, vel - 10, b + i * QUARTER + TRIPLET_8TH,
                     EIGHTH, CH_DRUMS)

    # Snare: gallop pattern (on 3rd triplet of each beat)
    def snare_gallop(bar, vel=105):
        b = s.bt(bar)
        for i in range(4):
            add_note(s.snare, SNARE, vel,
                     b + i * QUARTER + TRIPLET_8TH * 2, EIGHTH, CH_DRUMS)

    # Hats: ride 8ths
    def ride_8ths(bar, vel=75):
        b = s.bt(bar)
        for i in range(8):
            add_note(s.hihats, SHAKER, vel - (i % 2) * 10,
                     b + i * EIGHTH, EIGHTH - 10, CH_DRUMS)

    # Build
    for bar in range(*INTRO):
        heroic_melody(bar, 82)
        ride_8ths(bar, 58)

    for bar in range(*VERSE1):
        heroic_melody(bar, 95)
        gallop_chords(bar, 85)
        bass_gallop(bar, 90)
        kick_gallop(bar); snare_gallop(bar); ride_8ths(bar)

    for bar in range(*CHORUS1):
        heroic_melody(bar, 112)
        gallop_chords(bar, 100)
        bass_gallop(bar, 100)
        kick_gallop(bar, 118); snare_gallop(bar, 112); ride_8ths(bar, 85)

    for bar in range(*BRIDGE):
        gallop_chords(bar, 88)
        bass_gallop(bar, 85)
        kick_gallop(bar, 100); snare_gallop(bar, 95); ride_8ths(bar, 68)

    for i, bar in enumerate(range(*OUTRO)):
        fade = 1.0 - i * 0.08
        heroic_melody(bar, vscale(112, fade))
        gallop_chords(bar, vscale(100, fade))
        bass_gallop(bar, vscale(100, fade))
        kick_gallop(bar, vscale(118, fade))
        snare_gallop(bar, vscale(112, fade))
        ride_8ths(bar, vscale(85, fade))

    s.save()


# ============================================================================
# MAIN
# ============================================================================

ALL_GENERATORS = [
    gen_back_in_black,
    gen_highway_to_hell,
    gen_thunderstruck,
    gen_iron_man,
    gen_paranoid,
    gen_hotel_california,
    gen_take_it_easy,
    gen_whole_lotta_love,
    gen_kashmir,
    gen_riders_on_the_storm,
    gen_light_my_fire,
    gen_purple_haze,
    gen_voodoo_child,
    gen_black_magic_woman,
    gen_smooth,
    gen_evil_ways,
    gen_hysteria,
    gen_supermassive_black_hole,
    gen_knights_of_cydonia,
]


def main():
    print(f"Generating {len(ALL_GENERATORS)} songs into {SONGS_DIR}")
    print("=" * 60)
    os.makedirs(SONGS_DIR, exist_ok=True)

    for gen_func in ALL_GENERATORS:
        try:
            gen_func()
        except Exception as e:
            print(f"  [FAIL] {gen_func.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 60)
    print("Done.")


if __name__ == '__main__':
    main()
