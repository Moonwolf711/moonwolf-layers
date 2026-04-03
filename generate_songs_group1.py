"""
Generate multi-track MIDI files for iconic rock songs (Group 1).
Songs: Whole Lotta Love, Kashmir, Riders on the Storm, Light My Fire, Purple Haze, Voodoo Child
Uses mido library. Each song gets its own folder with per-instrument .mid files + combined full.mid + meta.json.

V2: Full song structures (intro/verse/chorus/bridge/solo/outro), dynamic velocity,
    signature moments, proper note_off messages.
V3: Humanization pass — swing, timing jitter, velocity jitter, ghost notes, pitch bends,
    and per-artist feel (Bonham behind-the-beat, Doors jazz swing, Mitchell looseness).
"""

import os
import json
import random
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")

# GM Drum map constants
KICK = 36
SNARE = 38
RIMSHOT = 37
HAT_CLOSED = 42
HAT_OPEN = 46
HAT_PEDAL = 44
CRASH = 49
RIDE = 51
RIDE_BELL = 53
LOW_TOM = 45
HI_TOM = 48
MID_TOM = 47

# Tick constants
TPB = 480
WHOLE = TPB * 4
HALF = TPB * 2
QUARTER = TPB
EIGHTH = TPB // 2
SIXTEENTH = TPB // 4
TRIPLET_8TH = TPB // 3
DOT_QUARTER = QUARTER + EIGHTH
DOT_EIGHTH = EIGHTH + SIXTEENTH
BAR = WHOLE
THIRTYSECOND = TPB // 8


def ticks_per_beat():
    return 480


def tempo_to_microseconds(bpm):
    return mido.bpm2tempo(bpm)


def note_on(note, vel=100, time=0, channel=0):
    return Message('note_on', note=note, velocity=vel, time=time, channel=channel)


def note_off(note, vel=0, time=0, channel=0):
    return Message('note_off', note=note, velocity=vel, time=time, channel=channel)


def add_note(track, note, duration, velocity=100, time=0, channel=0):
    """Add a note_on then note_off with given duration in ticks."""
    track.append(note_on(note, velocity, time=time, channel=channel))
    track.append(note_off(note, time=duration, channel=channel))


def add_chord(track, notes, duration, velocity=100, time=0, channel=0):
    """Add a chord (multiple notes simultaneously)."""
    for i, n in enumerate(notes):
        track.append(note_on(n, velocity, time=time if i == 0 else 0, channel=channel))
    for i, n in enumerate(notes):
        track.append(note_off(n, time=duration if i == 0 else 0, channel=channel))


def add_rest(track, duration, channel=0):
    """Add silence for given duration."""
    track.append(Message('note_on', note=0, velocity=0, time=duration, channel=channel))
    track.append(Message('note_off', note=0, time=0, channel=channel))


def humanize(vel, spread=6):
    """Add slight velocity variation for human feel."""
    return max(1, min(127, vel + random.randint(-spread, spread)))


def h(vel, spread=6):
    """Shorthand for humanize."""
    return humanize(vel, spread)


# ============================================================
# HUMANIZATION ENGINE (V3)
# ============================================================

def humanize_track(track, style_params):
    """Post-process an entire track to add human feel.

    style_params dict keys:
        swing_amount: 0.0-0.3  (push offbeat 8th notes later for shuffle)
        timing_jitter: int     (random tick offset +/- N)
        vel_jitter: int        (random velocity offset +/- N)
        late_offset: int       (constant tick delay for behind-the-beat feel)
        early_offset: int      (constant tick advance for rushing)
        vel_scale: float       (multiply all velocities, e.g. 0.8 for brushes)
        phrase_accent: bool    (if True, first note of each phrase gets +10 vel)
        drum_channel: int|None (if set, apply drum-specific logic)
        kick_late: int         (extra late offset for kick drum only)
        snare_late: int        (extra late offset for snare only)
        crash_early: int       (ticks to pull crash hits earlier)
        add_pitch_bends: bool  (add slight pitch bend on melody notes)
    """
    swing = style_params.get('swing_amount', 0.0)
    jitter = style_params.get('timing_jitter', 10)
    vel_jit = style_params.get('vel_jitter', 8)
    late = style_params.get('late_offset', 0)
    early = style_params.get('early_offset', 0)
    vel_scale = style_params.get('vel_scale', 1.0)
    drum_ch = style_params.get('drum_channel', None)
    kick_late = style_params.get('kick_late', 0)
    snare_late = style_params.get('snare_late', 0)
    crash_early = style_params.get('crash_early', 0)
    add_bends = style_params.get('add_pitch_bends', False)

    # Build absolute-time event list from track
    abs_events = []
    abs_tick = 0
    for msg in track:
        abs_tick += msg.time
        abs_events.append((abs_tick, msg))

    new_events = []
    phrase_start = True  # Track phrase boundaries for accent

    for i, (tick, msg) in enumerate(abs_events):
        if isinstance(msg, MetaMessage):
            new_events.append((tick, msg))
            continue

        new_tick = tick
        new_msg = msg.copy()

        if msg.type == 'note_on' and msg.velocity > 0:
            note = msg.note
            vel = msg.velocity
            ch = msg.channel

            # --- Velocity scaling ---
            vel = int(vel * vel_scale)

            # --- Velocity jitter ---
            vel += random.randint(-vel_jit, vel_jit)
            vel = max(30, min(127, vel))

            # --- Phrase accent (first note after rest) ---
            if style_params.get('phrase_accent', False) and phrase_start:
                vel = min(127, vel + 10)
                phrase_start = False

            # --- Swing: push offbeat 8th notes ---
            if swing > 0:
                pos_in_beat = tick % TPB
                half_beat = TPB // 2
                # If note lands on the offbeat 8th (around half_beat)
                if abs(pos_in_beat - half_beat) < (TPB // 8):
                    new_tick += int(swing * half_beat)

            # --- Drum-specific timing ---
            if drum_ch is not None and ch == drum_ch:
                if note == KICK and kick_late > 0:
                    new_tick += random.randint(kick_late // 2, kick_late)
                elif note == SNARE and snare_late > 0:
                    new_tick += random.randint(snare_late // 2, snare_late)
                elif note == CRASH and crash_early > 0:
                    new_tick -= random.randint(crash_early // 2, crash_early)

            # --- General timing: late/early offset ---
            new_tick += late
            new_tick -= early

            # --- Random timing jitter ---
            new_tick += random.randint(-jitter, jitter)
            new_tick = max(0, new_tick)

            new_msg = Message(msg.type, note=note, velocity=vel,
                              time=0, channel=ch)

            # --- Pitch bend for melody instruments ---
            if add_bends and ch != 9 and drum_ch != ch:
                # ~10% chance of a slight pitch bend approach
                if random.random() < 0.10:
                    # Insert a slight-flat bend 30 ticks before, resolve on the note
                    bend_tick = max(0, new_tick - 30)
                    bend_msg = Message('pitchwheel', pitch=-random.randint(200, 600),
                                       time=0, channel=ch)
                    resolve_msg = Message('pitchwheel', pitch=0, time=0, channel=ch)
                    new_events.append((bend_tick, bend_msg))
                    new_events.append((new_tick + 25, resolve_msg))

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            # Note-off inherits the same jitter direction as its note-on
            new_tick += late - early + random.randint(-jitter // 2, jitter // 2)
            new_tick = max(0, new_tick)

            # Check if this might be a rest boundary (phrase accent tracking)
            if msg.note == 0:
                phrase_start = True

        new_events.append((new_tick, new_msg))

    # Sort by absolute tick, then convert back to delta times
    new_events.sort(key=lambda x: x[0])

    new_track = MidiTrack()
    prev_tick = 0
    for abs_t, msg in new_events:
        delta = max(0, abs_t - prev_tick)
        if isinstance(msg, MetaMessage):
            new_track.append(msg.copy(time=delta))
        else:
            new_track.append(msg.copy(time=delta))
        prev_tick = abs_t

    return new_track


def add_ghost_notes(track, style_params):
    """Insert ghost notes into a drum track for human feel.

    style_params dict keys:
        ghost_snare_vel: (min, max) velocity range for ghost snares
        ghost_hat_vel: (min, max) velocity range for ghost hats
        ghost_density: float 0-1, probability of ghost note between main hits
        flam_before_crash: bool, add 32nd-note snare flam before crashes
        drum_channel: int
    """
    ghost_snare_vel = style_params.get('ghost_snare_vel', (25, 40))
    ghost_hat_vel = style_params.get('ghost_hat_vel', (20, 35))
    density = style_params.get('ghost_density', 0.4)
    flam = style_params.get('flam_before_crash', True)
    ch = style_params.get('drum_channel', 9)

    # Convert to absolute time
    abs_events = []
    abs_tick = 0
    for msg in track:
        abs_tick += msg.time
        abs_events.append((abs_tick, msg))

    # Find main hit positions
    kick_ticks = []
    snare_ticks = []
    hat_ticks = []
    crash_ticks = []

    for tick, msg in abs_events:
        if isinstance(msg, MetaMessage):
            continue
        if msg.type == 'note_on' and msg.velocity > 0 and msg.channel == ch:
            if msg.note == KICK:
                kick_ticks.append(tick)
            elif msg.note == SNARE:
                snare_ticks.append(tick)
            elif msg.note in (HAT_CLOSED, HAT_OPEN, HAT_PEDAL, RIDE, RIDE_BELL):
                hat_ticks.append(tick)
            elif msg.note == CRASH:
                crash_ticks.append(tick)

    ghosts_to_add = []

    # Ghost snares between kick-snare patterns
    all_main = sorted(set(kick_ticks + snare_ticks))
    for i in range(len(all_main) - 1):
        gap = all_main[i + 1] - all_main[i]
        if gap >= EIGHTH:
            # Add 1-3 ghost snares in the gap
            num_ghosts = random.randint(1, min(3, int(gap / SIXTEENTH) - 1))
            for g in range(num_ghosts):
                if random.random() < density:
                    offset = random.randint(SIXTEENTH, gap - SIXTEENTH)
                    ghost_tick = all_main[i] + offset
                    vel = random.randint(*ghost_snare_vel)
                    ghosts_to_add.append((ghost_tick, SNARE, vel, SIXTEENTH))

    # Ghost hats between main hat hits
    if hat_ticks:
        sorted_hats = sorted(hat_ticks)
        for i in range(len(sorted_hats) - 1):
            gap = sorted_hats[i + 1] - sorted_hats[i]
            if gap >= EIGHTH and random.random() < density * 0.7:
                ghost_tick = sorted_hats[i] + gap // 2
                vel = random.randint(*ghost_hat_vel)
                ghosts_to_add.append((ghost_tick, HAT_CLOSED, vel, SIXTEENTH))

    # Flam before crash hits (32nd-note snare pair)
    if flam:
        for ct in crash_ticks:
            flam_tick = ct - THIRTYSECOND * 2
            if flam_tick > 0:
                ghosts_to_add.append((flam_tick, SNARE, random.randint(45, 65), THIRTYSECOND))
                ghosts_to_add.append((flam_tick + THIRTYSECOND - 10, SNARE,
                                      random.randint(55, 75), THIRTYSECOND))

    # Merge ghost notes into event list
    for tick, note, vel, dur in ghosts_to_add:
        abs_events.append((tick, Message('note_on', note=note, velocity=vel,
                                          time=0, channel=ch)))
        abs_events.append((tick + dur, Message('note_off', note=note, velocity=0,
                                                time=0, channel=ch)))

    # Sort and rebuild
    abs_events.sort(key=lambda x: x[0])
    new_track = MidiTrack()
    prev_tick = 0
    for abs_t, msg in abs_events:
        delta = max(0, abs_t - prev_tick)
        if isinstance(msg, MetaMessage):
            new_track.append(msg.copy(time=delta))
        else:
            new_track.append(msg.copy(time=delta))
        prev_tick = abs_t

    return new_track


# --- Style presets ---

STYLE_BONHAM = {
    'swing_amount': 0.15,
    'timing_jitter': 8,
    'vel_jitter': 10,
    'late_offset': 0,
    'drum_channel': 9,
    'kick_late': 12,       # Bonham plays behind the beat
    'snare_late': 10,
    'crash_early': 5,
    'vel_scale': 1.0,
    'ghost_snare_vel': (30, 45),
    'ghost_hat_vel': (20, 35),
    'ghost_density': 0.5,
    'flam_before_crash': True,
}

STYLE_BONHAM_MELODY = {
    'swing_amount': 0.10,
    'timing_jitter': 8,
    'vel_jitter': 6,
    'late_offset': 0,
    'phrase_accent': True,
    'add_pitch_bends': True,
    'vel_scale': 1.0,
}

STYLE_DOORS_DRUMS = {
    'swing_amount': 0.20,
    'timing_jitter': 6,
    'vel_jitter': 8,
    'late_offset': 0,
    'drum_channel': 9,
    'kick_late': 0,
    'snare_late': 0,
    'crash_early': 0,
    'vel_scale': 0.85,     # Brushes feel — lower overall velocity
    'ghost_snare_vel': (25, 40),
    'ghost_hat_vel': (18, 30),
    'ghost_density': 0.35,
    'flam_before_crash': True,
}

STYLE_DOORS_MELODY = {
    'swing_amount': 0.15,
    'timing_jitter': 6,
    'vel_jitter': 5,
    'late_offset': 0,
    'phrase_accent': True,
    'add_pitch_bends': True,
    'vel_scale': 0.90,     # Slightly softer jazz feel
}

STYLE_HENDRIX_DRUMS = {
    'swing_amount': 0.20,
    'timing_jitter': 10,
    'vel_jitter': 12,
    'late_offset': 0,
    'drum_channel': 9,
    'kick_late': 8,        # Mitch Mitchell slightly behind on kick
    'snare_late': 0,
    'crash_early': 5,      # Crash accents slightly early
    'vel_scale': 1.0,
    'ghost_snare_vel': (25, 42),
    'ghost_hat_vel': (20, 35),
    'ghost_density': 0.55, # Ghost snares everywhere
    'flam_before_crash': True,
}

STYLE_HENDRIX_MELODY = {
    'swing_amount': 0.12,
    'timing_jitter': 8,
    'vel_jitter': 8,
    'late_offset': 0,
    'phrase_accent': True,
    'add_pitch_bends': True,
    'vel_scale': 1.0,
}


def apply_humanization(track, style, is_drum=False):
    """Apply full humanization pipeline to a track."""
    result = humanize_track(track, style)
    if is_drum:
        result = add_ghost_notes(result, style)
    return result


def make_track(name, tempo_bpm):
    """Create a track with name and tempo meta messages."""
    track = MidiTrack()
    track.append(MetaMessage('track_name', name=name, time=0))
    track.append(MetaMessage('set_tempo', tempo=tempo_to_microseconds(tempo_bpm), time=0))
    track.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    return track


def save_single_track(track, tempo_bpm, filepath):
    """Save a single track as its own MIDI file."""
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    mid.tracks.append(track)
    mid.save(filepath)


def save_full(tracks, tempo_bpm, filepath):
    """Save all tracks combined into one MIDI file."""
    mid = MidiFile(ticks_per_beat=ticks_per_beat(), type=1)
    for t in tracks:
        mid.tracks.append(t)
    mid.save(filepath)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def save_meta(folder, title, artist, bpm, key, bars, difficulty, instruments, structure=None):
    meta = {
        "title": title,
        "artist": artist,
        "bpm": bpm,
        "key": key,
        "bars": bars,
        "difficulty": difficulty,
        "instruments": instruments,
    }
    if structure:
        meta["structure"] = structure
    with open(os.path.join(folder, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


# ============================================================
# DRUM PATTERN HELPERS
# ============================================================

def drum_beat_rock(track, ch, vel_k=100, vel_s=105, vel_h=85, open_hat=False):
    """One bar of standard rock: kick on 1,3 / snare on 2,4 / 8th hats."""
    hat = HAT_OPEN if open_hat else HAT_CLOSED
    for beat in range(4):
        if beat in (0, 2):
            add_note(track, KICK, SIXTEENTH, velocity=h(vel_k), channel=ch)
            add_note(track, hat, SIXTEENTH, velocity=h(vel_h), channel=ch)
            add_note(track, hat, EIGHTH, velocity=h(vel_h - 10), channel=ch)
        else:
            add_note(track, SNARE, SIXTEENTH, velocity=h(vel_s), channel=ch)
            add_note(track, hat, SIXTEENTH, velocity=h(vel_h), channel=ch)
            add_note(track, hat, EIGHTH, velocity=h(vel_h - 10), channel=ch)


def drum_fill_toms(track, ch, vel=100):
    """One bar tom fill: hi-tom -> mid-tom -> low-tom -> crash+kick."""
    add_note(track, HI_TOM, EIGHTH, velocity=h(vel), channel=ch)
    add_note(track, HI_TOM, EIGHTH, velocity=h(vel - 5), channel=ch)
    add_note(track, MID_TOM, EIGHTH, velocity=h(vel + 2), channel=ch)
    add_note(track, MID_TOM, EIGHTH, velocity=h(vel - 3), channel=ch)
    add_note(track, LOW_TOM, EIGHTH, velocity=h(vel + 5), channel=ch)
    add_note(track, LOW_TOM, EIGHTH, velocity=h(vel), channel=ch)
    add_note(track, SNARE, EIGHTH, velocity=h(vel + 8), channel=ch)
    # Crash landing
    track.append(note_on(CRASH, h(vel + 10), channel=ch))
    track.append(note_on(KICK, h(vel + 5), time=0, channel=ch))
    track.append(note_off(CRASH, time=EIGHTH, channel=ch))
    track.append(note_off(KICK, time=0, channel=ch))


def drum_crash_accent(track, ch, vel=110):
    """Add crash on beat 1 (assumes we are at beat 1 position)."""
    track.append(note_on(CRASH, h(vel), time=0, channel=ch))
    track.append(note_off(CRASH, time=0, channel=ch))


# ============================================================
# 1. LED ZEPPELIN - WHOLE LOTTA LOVE
# Structure: INTRO(4) -> VERSE(8) -> CHORUS(4) -> BRIDGE(4) -> VERSE2(8) -> OUTRO(4) = 32
# ============================================================
def generate_whole_lotta_love():
    random.seed(42)
    folder = os.path.join(BASE_DIR, "led_zeppelin_whole_lotta_love")
    ensure_dir(folder)
    bpm = 90
    total_bars = 32
    ch_drum = 9
    ch_bass = 2
    ch_guitar = 1

    # Note definitions
    E2, G2, A2, B2, D3, E3 = 40, 43, 45, 47, 50, 52
    E4, D4, Cs4, C4, B3, A3 = 64, 62, 61, 60, 59, 57
    B4, A4, E5, D5 = 71, 69, 76, 74

    # Section map: (start_bar, end_bar, section_name)
    sections = {
        'intro':  (0, 4),
        'verse1': (4, 12),
        'chorus': (12, 16),
        'bridge': (16, 20),
        'verse2': (20, 28),
        'outro':  (28, 32),
    }

    def get_section(bar):
        for name, (s, e) in sections.items():
            if s <= bar < e:
                return name
        return 'verse1'

    # --- DRUMS ---
    drum_track = make_track("Drums", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No drums in intro (bass riff alone) - just silence
            add_rest(drum_track, WHOLE, ch_drum)
            continue

        if sec == 'bridge':
            # Sparse trippy breakdown - only sporadic kick and tom hits
            if bar % 2 == 0:
                add_note(drum_track, KICK, QUARTER, velocity=h(65), channel=ch_drum)
                add_rest(drum_track, QUARTER, ch_drum)
                add_note(drum_track, LOW_TOM, QUARTER, velocity=h(55), channel=ch_drum)
                add_rest(drum_track, QUARTER, ch_drum)
            else:
                add_rest(drum_track, HALF, ch_drum)
                add_note(drum_track, MID_TOM, EIGHTH, velocity=h(50), channel=ch_drum)
                add_note(drum_track, LOW_TOM, EIGHTH, velocity=h(55), channel=ch_drum)
                add_rest(drum_track, QUARTER, ch_drum)
            continue

        # Is this a fill bar? (last bar of each section)
        is_fill = (bar == 11 or bar == 15 or bar == 27 or bar == 31)
        if is_fill:
            drum_fill_toms(drum_track, ch_drum, vel=105 if sec in ('chorus', 'outro') else 95)
            continue

        # Set velocity ranges per section
        if sec == 'chorus' or sec == 'outro':
            vk, vs, vh = 105, 110, 95
        elif sec == 'verse2':
            vk, vs, vh = 95, 105, 85
        else:
            vk, vs, vh = 90, 100, 80

        # Add crash on first beat of chorus/outro and first bar of verse entries
        if bar in (4, 12, 20, 28):
            drum_crash_accent(drum_track, ch_drum, vel=115 if sec in ('chorus', 'outro') else 105)

        drum_beat_rock(drum_track, ch_drum, vk, vs, vh, open_hat=(sec == 'chorus' or sec == 'outro'))

    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS ---
    bass_track = make_track("Bass", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro' or sec == 'verse1' or sec == 'verse2':
            # Classic E blues riff - driving 8ths
            vel_base = 80 if sec == 'intro' else (85 if sec == 'verse1' else 90)
            for eighth in range(8):
                vel = h(vel_base + (10 if eighth == 0 else 0))  # accent beat 1
                if eighth == 6:
                    add_note(bass_track, G2, EIGHTH, velocity=vel, channel=ch_bass)
                elif eighth == 7:
                    add_note(bass_track, A2, EIGHTH, velocity=vel, channel=ch_bass)
                else:
                    add_note(bass_track, E2, EIGHTH, velocity=vel, channel=ch_bass)

        elif sec == 'chorus':
            # E-D-A open chord roots, louder
            # 1 bar each of E, D, A, E
            bar_in_sec = bar - sections['chorus'][0]
            if bar_in_sec == 0:
                root = E2
            elif bar_in_sec == 1:
                root = D3 - 12  # D2=38
            elif bar_in_sec == 2:
                root = A2
            else:
                root = E2
            for eighth in range(8):
                vel = h(100 if eighth == 0 else 90)
                if eighth == 0:
                    add_note(bass_track, root, EIGHTH, velocity=vel, channel=ch_bass)
                elif eighth == 4:
                    add_note(bass_track, root + 12, EIGHTH, velocity=h(95), channel=ch_bass)
                else:
                    add_note(bass_track, root, EIGHTH, velocity=h(85), channel=ch_bass)

        elif sec == 'bridge':
            # Sparse bass slides - whole notes with chromatic movement
            bar_in_sec = bar - sections['bridge'][0]
            slide_notes = [E2, G2, A2, E2]
            add_note(bass_track, slide_notes[bar_in_sec], HALF, velocity=h(70), channel=ch_bass)
            add_rest(bass_track, HALF, ch_bass)

        elif sec == 'outro':
            # Big driving E riff, loud
            for eighth in range(8):
                vel = h(105 if eighth == 0 else 95)
                if eighth in (6, 7):
                    add_note(bass_track, A2 if eighth == 6 else B2, EIGHTH, velocity=vel, channel=ch_bass)
                else:
                    add_note(bass_track, E2, EIGHTH, velocity=vel, channel=ch_bass)

    bass_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR ---
    guitar_track = make_track("Guitar", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Silence - bass alone in intro
            add_rest(guitar_track, WHOLE, ch_guitar)

        elif sec == 'verse1' or sec == 'verse2':
            # Main riff: E E E D E chromatic descend
            vel_base = 95 if sec == 'verse1' else 100
            add_note(guitar_track, E4, EIGHTH, velocity=h(vel_base + 5), channel=ch_guitar)
            add_note(guitar_track, E4, EIGHTH, velocity=h(vel_base), channel=ch_guitar)
            add_note(guitar_track, E4, EIGHTH, velocity=h(vel_base), channel=ch_guitar)
            add_note(guitar_track, D4, DOT_EIGHTH, velocity=h(vel_base + 8), channel=ch_guitar)
            add_note(guitar_track, E4, SIXTEENTH, velocity=h(vel_base - 5), channel=ch_guitar)
            # Chromatic descend
            add_note(guitar_track, E4, EIGHTH, velocity=h(vel_base), channel=ch_guitar)
            add_note(guitar_track, D4, EIGHTH, velocity=h(vel_base - 5), channel=ch_guitar)
            add_note(guitar_track, Cs4, EIGHTH, velocity=h(vel_base - 8), channel=ch_guitar)
            add_note(guitar_track, B3, EIGHTH, velocity=h(vel_base - 10), channel=ch_guitar)

            # Verse2 gets extra fills between phrases
            if sec == 'verse2' and bar % 2 == 1:
                # Override last beat with fill notes (already written above for this bar)
                pass  # fills are baked into the velocity variations

        elif sec == 'chorus':
            # Full band hit - open chords E-D-A, louder
            bar_in_sec = bar - sections['chorus'][0]
            if bar_in_sec == 0:
                chord = [E4, B4]  # E power chord
            elif bar_in_sec == 1:
                chord = [D4, A4]  # D power chord (D4+A4)
            elif bar_in_sec == 2:
                chord = [A3, E4]  # A power chord
            else:
                chord = [E4, B4]  # E power chord

            vel = h(110)
            add_chord(guitar_track, chord, QUARTER, velocity=vel, channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_chord(guitar_track, chord, EIGHTH, velocity=h(105), channel=ch_guitar)
            add_chord(guitar_track, chord, QUARTER, velocity=h(108), channel=ch_guitar)
            add_rest(guitar_track, QUARTER, ch_guitar)

        elif sec == 'bridge':
            # Sparse, atmospheric - single notes with space
            bar_in_sec = bar - sections['bridge'][0]
            bridge_notes = [E4, D4, B3, E4]
            add_note(guitar_track, bridge_notes[bar_in_sec], HALF, velocity=h(60), channel=ch_guitar)
            add_rest(guitar_track, HALF, ch_guitar)

        elif sec == 'outro':
            # Big ending - power chord stabs with crash energy
            add_chord(guitar_track, [E4, B4], EIGHTH, velocity=h(115), channel=ch_guitar)
            add_note(guitar_track, E4, EIGHTH, velocity=h(108), channel=ch_guitar)
            add_note(guitar_track, D4, EIGHTH, velocity=h(105), channel=ch_guitar)
            add_note(guitar_track, E4, DOT_EIGHTH, velocity=h(110), channel=ch_guitar)
            add_note(guitar_track, D4, SIXTEENTH, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, E4, EIGHTH, velocity=h(108), channel=ch_guitar)
            add_note(guitar_track, D4, EIGHTH, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, Cs4, EIGHTH, velocity=h(95), channel=ch_guitar)
            add_note(guitar_track, B3, EIGHTH, velocity=h(105), channel=ch_guitar)

    guitar_track.append(MetaMessage('end_of_track', time=0))

    # --- Humanization pass (Bonham: behind the beat, heavy ghost notes) ---
    drum_track = apply_humanization(drum_track, STYLE_BONHAM, is_drum=True)
    bass_track = apply_humanization(bass_track, STYLE_BONHAM_MELODY)
    guitar_track = apply_humanization(guitar_track, STYLE_BONHAM_MELODY)

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_full([drum_track, bass_track, guitar_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Whole Lotta Love", "Led Zeppelin", bpm, "E", total_bars, 3,
              ["drums", "bass", "guitar"],
              structure="intro(4)-verse(8)-chorus(4)-bridge(4)-verse(8)-outro(4)")
    print(f"  [OK] Whole Lotta Love ({total_bars} bars)")


# ============================================================
# 2. LED ZEPPELIN - KASHMIR
# Structure: INTRO(4) -> VERSE(8) -> CHORUS(4) -> VERSE2(8) -> BRIDGE(4) -> OUTRO(4) = 32
# ============================================================
def generate_kashmir():
    random.seed(43)
    folder = os.path.join(BASE_DIR, "led_zeppelin_kashmir")
    ensure_dir(folder)
    bpm = 80
    total_bars = 32
    ch_drum = 9
    ch_strings = 4
    ch_guitar = 1

    # Notes
    D2 = 38
    D3, Eb3, E3, F3, Fs3, G3, A3 = 50, 51, 52, 53, 54, 55, 57
    D4, E4, F4, G4, A4 = 62, 64, 65, 67, 69
    D5, E5 = 74, 76

    sections = {
        'intro':  (0, 4),
        'verse1': (4, 12),
        'chorus': (12, 16),
        'verse2': (16, 24),
        'bridge': (24, 28),
        'outro':  (28, 32),
    }

    def get_section(bar):
        for name, (s, e) in sections.items():
            if s <= bar < e:
                return name
        return 'verse1'

    # --- DRUMS: Bonham march ---
    drum_track = make_track("Drums", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Bonham march drums alone - the iconic opening
            vel = 110
            # Beat 1: double kick
            add_note(drum_track, KICK, EIGHTH, velocity=h(vel), channel=ch_drum)
            add_note(drum_track, KICK, EIGHTH, velocity=h(vel - 15), channel=ch_drum)
            # Beat 2: snare (march hit)
            add_note(drum_track, SNARE, QUARTER, velocity=h(vel + 2), channel=ch_drum)
            # Beat 3: kick
            add_note(drum_track, KICK, EIGHTH, velocity=h(vel - 5), channel=ch_drum)
            add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(80), channel=ch_drum)
            # Beat 4: open hat
            add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(90), channel=ch_drum)
            add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(75), channel=ch_drum)

        elif sec == 'bridge':
            # Breakdown - tom fills
            if bar % 2 == 0:
                drum_fill_toms(drum_track, ch_drum, vel=105)
            else:
                # Sparse tom hits
                add_note(drum_track, HI_TOM, QUARTER, velocity=h(95), channel=ch_drum)
                add_note(drum_track, MID_TOM, QUARTER, velocity=h(90), channel=ch_drum)
                add_note(drum_track, LOW_TOM, QUARTER, velocity=h(95), channel=ch_drum)
                add_note(drum_track, KICK, QUARTER, velocity=h(100), channel=ch_drum)

        elif sec == 'chorus' or sec == 'outro':
            # Full power march with crashes
            if bar == sections[sec][0]:
                drum_crash_accent(drum_track, ch_drum, vel=120)
            add_note(drum_track, KICK, EIGHTH, velocity=h(112), channel=ch_drum)
            add_note(drum_track, KICK, EIGHTH, velocity=h(100), channel=ch_drum)
            add_note(drum_track, SNARE, QUARTER, velocity=h(115), channel=ch_drum)
            add_note(drum_track, KICK, EIGHTH, velocity=h(108), channel=ch_drum)
            if bar == sections[sec][1] - 1:
                # Fill on last bar
                add_note(drum_track, HI_TOM, EIGHTH, velocity=h(105), channel=ch_drum)
                add_note(drum_track, MID_TOM, EIGHTH, velocity=h(105), channel=ch_drum)
                add_note(drum_track, LOW_TOM, EIGHTH, velocity=h(110), channel=ch_drum)
            else:
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(85), channel=ch_drum)
                add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(95), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(80), channel=ch_drum)

        else:
            # Verse - steady march
            vel_base = 95 if sec == 'verse1' else 100
            add_note(drum_track, KICK, EIGHTH, velocity=h(vel_base), channel=ch_drum)
            add_note(drum_track, KICK, EIGHTH, velocity=h(vel_base - 15), channel=ch_drum)
            add_note(drum_track, SNARE, QUARTER, velocity=h(vel_base + 5), channel=ch_drum)
            add_note(drum_track, KICK, EIGHTH, velocity=h(vel_base - 5), channel=ch_drum)
            add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(80), channel=ch_drum)
            add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(85), channel=ch_drum)
            add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(75), channel=ch_drum)

    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- STRINGS ---
    strings_track = make_track("Strings", bpm)
    ascending = [D4, E4, F4, G4, A4]
    descending = [A4, G4, F4, E4, D4]

    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No strings in intro (drums alone)
            add_rest(strings_track, WHOLE, ch_strings)

        elif sec == 'verse1':
            # Ascending D-E-F-G-A as quarter notes (5 notes, last extends)
            bar_in_sec = bar - sections['verse1'][0]
            if bar_in_sec % 2 == 0:
                notes = ascending
            else:
                notes = descending
            # 4 quarter notes per bar, pick from the sequence
            idx_offset = (bar_in_sec % 2) * 0
            for beat in range(4):
                ni = (bar_in_sec * 2 + beat) % 5
                note_list = ascending if bar_in_sec % 2 == 0 else descending
                add_note(strings_track, note_list[ni], QUARTER, velocity=h(80 + beat * 2), channel=ch_strings)

        elif sec == 'verse2':
            # Descending A-G-F-E-D
            bar_in_sec = bar - sections['verse2'][0]
            if bar_in_sec % 2 == 0:
                notes = descending
            else:
                notes = ascending
            for beat in range(4):
                ni = (bar_in_sec * 2 + beat) % 5
                add_note(strings_track, notes[ni], QUARTER, velocity=h(85 + beat * 2), channel=ch_strings)

        elif sec == 'chorus' or sec == 'outro':
            # Full orchestra hit - sustained chords, loud
            # Dm chord: D4, F4, A4
            vel = 110 if sec == 'outro' else 105
            add_chord(strings_track, [D4, F4, A4], WHOLE, velocity=h(vel), channel=ch_strings)

        elif sec == 'bridge':
            # Quiet sustained notes
            add_note(strings_track, D4, WHOLE, velocity=h(60), channel=ch_strings)

    strings_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR: DADGAD chromatic riff ---
    guitar_track = make_track("Guitar", bpm)
    riff_notes = [D3, Eb3, E3, F3, Fs3, G3, Fs3, F3]  # Chromatic walk

    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No guitar in intro
            add_rest(guitar_track, WHOLE, ch_guitar)

        elif sec in ('verse1', 'verse2'):
            # Chromatic riff with D drone
            vel_base = 95 if sec == 'verse1' else 100
            guitar_track.append(note_on(D2, h(75), channel=ch_guitar))
            for i, n in enumerate(riff_notes):
                vel = h(vel_base if i % 2 == 0 else vel_base - 12)
                add_note(guitar_track, n, EIGHTH, velocity=vel, channel=ch_guitar)
            guitar_track.append(note_off(D2, time=0, channel=ch_guitar))

        elif sec == 'chorus' or sec == 'outro':
            # Power chord stabs
            vel = 112 if sec == 'outro' else 108
            add_chord(guitar_track, [D3, A3], QUARTER, velocity=h(vel), channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_chord(guitar_track, [D3, A3], EIGHTH, velocity=h(vel - 5), channel=ch_guitar)
            add_chord(guitar_track, [D3, A3], QUARTER, velocity=h(vel), channel=ch_guitar)
            add_rest(guitar_track, QUARTER, ch_guitar)

        elif sec == 'bridge':
            # Sparse guitar
            add_note(guitar_track, D3, HALF, velocity=h(70), channel=ch_guitar)
            add_rest(guitar_track, HALF, ch_guitar)

    guitar_track.append(MetaMessage('end_of_track', time=0))

    # --- Humanization pass (Bonham: behind the beat, march feel) ---
    drum_track = apply_humanization(drum_track, STYLE_BONHAM, is_drum=True)
    strings_track = apply_humanization(strings_track, STYLE_BONHAM_MELODY)
    guitar_track = apply_humanization(guitar_track, STYLE_BONHAM_MELODY)

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(strings_track, bpm, os.path.join(folder, "strings.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_full([drum_track, strings_track, guitar_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Kashmir", "Led Zeppelin", bpm, "D", total_bars, 4,
              ["drums", "strings", "guitar"],
              structure="intro(4)-verse(8)-chorus(4)-verse(8)-bridge(4)-outro(4)")
    print(f"  [OK] Kashmir ({total_bars} bars)")


# ============================================================
# 3. THE DOORS - RIDERS ON THE STORM
# Structure: INTRO(8) -> VERSE(8) -> CHORUS(4) -> VERSE2(8) -> OUTRO(4) = 32
# ============================================================
def generate_riders_on_the_storm():
    random.seed(44)
    folder = os.path.join(BASE_DIR, "the_doors_riders_on_the_storm")
    ensure_dir(folder)
    bpm = 108
    total_bars = 32
    ch_drum = 9
    ch_keys = 0
    ch_bass = 2

    # Notes
    E2, G2, A2, B2, D3 = 40, 43, 45, 47, 50
    E3, G3, B3, D4, E4, G4, B4 = 52, 55, 59, 62, 64, 67, 71

    sections = {
        'intro':  (0, 8),
        'verse1': (8, 16),
        'chorus': (16, 20),
        'verse2': (20, 28),
        'outro':  (28, 32),
    }

    def get_section(bar):
        for name, (s, e) in sections.items():
            if s <= bar < e:
                return name
        return 'verse1'

    # --- DRUMS ---
    drum_track = make_track("Drums", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No drums in intro (Rhodes alone)
            add_rest(drum_track, WHOLE, ch_drum)

        elif sec in ('verse1', 'verse2'):
            # Light brushes: ride + rimshot
            vel_ride = 65 if sec == 'verse1' else 70
            vel_rim = 55 if sec == 'verse1' else 60
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(70 if sec == 'verse1' else 75), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(vel_ride), channel=ch_drum)
                else:
                    add_note(drum_track, RIMSHOT, EIGHTH, velocity=h(vel_rim), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(vel_ride - 5), channel=ch_drum)

        elif sec == 'chorus':
            # Fuller drums - actual snare, more presence
            vel_base = 90
            if bar == sections['chorus'][0]:
                drum_crash_accent(drum_track, ch_drum, vel=100)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(vel_base), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(80), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(vel_base - 5), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(78), channel=ch_drum)

        elif sec == 'outro':
            # Fade feel - getting sparser
            bar_in_sec = bar - sections['outro'][0]
            vel_fade = 60 - bar_in_sec * 10
            if vel_fade > 20:
                add_note(drum_track, KICK, QUARTER, velocity=h(max(vel_fade, 25)), channel=ch_drum)
                add_note(drum_track, RIDE, QUARTER, velocity=h(max(vel_fade - 5, 20)), channel=ch_drum)
                add_rest(drum_track, HALF, ch_drum)
            else:
                add_rest(drum_track, WHOLE, ch_drum)

    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- KEYS: Rhodes Em7 arpeggio ---
    keys_track = make_track("Keys", bpm)
    arp_desc = [G4, D4, B3, E3]  # Rain drops descending
    arp_asc = [E3, B3, D4, G4]   # Ascending return

    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Rhodes piano alone - rain-like arpeggios Em7
            if bar % 2 == 0:
                for i, n in enumerate(arp_desc):
                    vel = h(72 - i * 4)
                    add_note(keys_track, n, QUARTER, velocity=vel, channel=ch_keys)
            else:
                for i, n in enumerate(arp_asc):
                    vel = h(60 + i * 4)
                    add_note(keys_track, n, QUARTER, velocity=vel, channel=ch_keys)

        elif sec in ('verse1', 'verse2'):
            # Same pattern but slightly different velocity
            vel_base = 68 if sec == 'verse1' else 72
            if bar % 2 == 0:
                for i, n in enumerate(arp_desc):
                    add_note(keys_track, n, QUARTER, velocity=h(vel_base - i * 3), channel=ch_keys)
            else:
                for i, n in enumerate(arp_asc):
                    add_note(keys_track, n, QUARTER, velocity=h(vel_base - 5 + i * 3), channel=ch_keys)
            # Verse2: higher register fills on odd bars
            if sec == 'verse2' and bar % 4 == 3:
                pass  # Fills embedded in vel variation

        elif sec == 'chorus':
            # Organ sustains - Em7 chord held
            vel = h(85)
            add_chord(keys_track, [E3, B3, D4, G4], WHOLE, velocity=vel, channel=ch_keys)

        elif sec == 'outro':
            # Getting sparse
            bar_in_sec = bar - sections['outro'][0]
            if bar_in_sec < 2:
                for i, n in enumerate(arp_desc):
                    vel = h(55 - bar_in_sec * 10 - i * 3)
                    vel = max(vel, 20)
                    add_note(keys_track, n, QUARTER, velocity=vel, channel=ch_keys)
            else:
                # Very sparse - single notes
                add_note(keys_track, E3, WHOLE, velocity=h(max(35 - bar_in_sec * 8, 15)), channel=ch_keys)

    keys_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS: Walking bass in Em ---
    bass_track = make_track("Bass", bpm)
    walk_patterns = [
        [E2, G2, A2, B2],
        [B2, A2, G2, E2],
        [E2, G2, A2, D3],
        [D3, B2, A2, E2],
    ]

    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No bass in intro
            add_rest(bass_track, WHOLE, ch_bass)

        elif sec in ('verse1', 'verse2'):
            # Walking bass enters
            vel_base = 80 if sec == 'verse1' else 85
            bar_in_sec = bar - sections[sec][0]
            pattern = walk_patterns[bar_in_sec % len(walk_patterns)]
            for n in pattern:
                vel = h(vel_base + (8 if n == pattern[0] else 0))
                add_note(bass_track, n, QUARTER, velocity=vel, channel=ch_bass)

        elif sec == 'chorus':
            # More active bass - 8th note walking
            bar_in_sec = bar - sections['chorus'][0]
            pattern = walk_patterns[bar_in_sec % len(walk_patterns)]
            for n in pattern:
                add_note(bass_track, n, EIGHTH, velocity=h(92), channel=ch_bass)
                add_note(bass_track, n + 2, EIGHTH, velocity=h(82), channel=ch_bass)  # chromatic passing

        elif sec == 'outro':
            # Fading bass
            bar_in_sec = bar - sections['outro'][0]
            vel = max(70 - bar_in_sec * 15, 25)
            add_note(bass_track, E2, WHOLE, velocity=h(vel), channel=ch_bass)

    bass_track.append(MetaMessage('end_of_track', time=0))

    # --- Humanization pass (Doors: jazz swing, brushes, laid back) ---
    drum_track = apply_humanization(drum_track, STYLE_DOORS_DRUMS, is_drum=True)
    keys_track = apply_humanization(keys_track, STYLE_DOORS_MELODY)
    bass_track = apply_humanization(bass_track, STYLE_DOORS_MELODY)

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(keys_track, bpm, os.path.join(folder, "keys.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, keys_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Riders on the Storm", "The Doors", bpm, "Em", total_bars, 3,
              ["drums", "keys", "bass"],
              structure="intro(8)-verse(8)-chorus(4)-verse(8)-outro(4)")
    print(f"  [OK] Riders on the Storm ({total_bars} bars)")


# ============================================================
# 4. THE DOORS - LIGHT MY FIRE
# Structure: INTRO(4) -> VERSE(8) -> CHORUS(4) -> SOLO(8) -> VERSE2(8) -> OUTRO(4) = 36
# ============================================================
def generate_light_my_fire():
    random.seed(45)
    folder = os.path.join(BASE_DIR, "the_doors_light_my_fire")
    ensure_dir(folder)
    bpm = 130
    total_bars = 36
    ch_drum = 9
    ch_keys = 0
    ch_bass = 2

    # Notes
    A2, G2, Fs2 = 45, 43, 42
    A3, C4, E4, G4 = 57, 60, 64, 67
    G3, B3, D4 = 55, 59, 62
    Fs3, Cs4 = 54, 61
    A4, C5, E5 = 69, 72, 76

    Am_chord = [A3, C4, E4]
    G_chord = [G3, B3, D4]
    Fsm_chord = [Fs3, A3, Cs4]

    sections = {
        'intro':  (0, 4),
        'verse1': (4, 12),
        'chorus': (12, 16),
        'solo':   (16, 24),
        'verse2': (24, 32),
        'outro':  (32, 36),
    }

    def get_section(bar):
        for name, (s, e) in sections.items():
            if s <= bar < e:
                return name
        return 'verse1'

    # --- DRUMS ---
    drum_track = make_track("Drums", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Light bossa hint - just ride bell ticks
            for beat in range(4):
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=h(65), channel=ch_drum)
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=h(50), channel=ch_drum)

        elif sec in ('verse1', 'verse2'):
            # Bossa nova inspired
            vel_k = 82 if sec == 'verse1' else 85
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(vel_k), channel=ch_drum)
                    add_note(drum_track, RIDE_BELL, EIGHTH, velocity=h(75), channel=ch_drum)
                else:
                    add_note(drum_track, RIMSHOT, EIGHTH, velocity=h(55), channel=ch_drum)
                    add_note(drum_track, RIDE_BELL, EIGHTH, velocity=h(70), channel=ch_drum)

        elif sec == 'chorus':
            # Louder - crash accents, real snare
            if bar == sections['chorus'][0]:
                drum_crash_accent(drum_track, ch_drum, vel=110)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(100), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(90), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(105), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(85), channel=ch_drum)

        elif sec == 'solo':
            # Driving pattern for organ solo
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(90), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(80), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(88), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(78), channel=ch_drum)

        elif sec == 'outro':
            # Return to lighter feel
            for beat in range(4):
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=h(60), channel=ch_drum)
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=h(45), channel=ch_drum)

    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- KEYS: Organ ---
    keys_track = make_track("Keys", bpm)

    # Am scale for arpeggios: A3 B3 C4 D4 E4 F4 G4 A4
    am_scale = [A3, 59, C4, D4, E4, 65, G4, A4]

    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Organ solo ascending Am-G-F#m
            bar_in_sec = bar - sections['intro'][0]
            if bar_in_sec < 2:
                # Am arpeggio ascending
                for n in [A3, C4, E4, A4]:
                    add_note(keys_track, n, QUARTER, velocity=h(82), channel=ch_keys)
            elif bar_in_sec == 2:
                # G chord arpeggio
                for n in [G3, B3, D4, G4]:
                    add_note(keys_track, n, QUARTER, velocity=h(85), channel=ch_keys)
            else:
                # F#m ascending
                for n in [Fs3, A3, Cs4, 66]:  # F#3, A3, C#4, F#4
                    add_note(keys_track, n, QUARTER, velocity=h(88), channel=ch_keys)

        elif sec in ('verse1', 'verse2'):
            # Organ comping - chord stabs
            bar_in_sec = bar - sections[sec][0]
            vel = 75 if sec == 'verse1' else 78
            if bar_in_sec % 4 < 2:
                add_chord(keys_track, Am_chord, HALF, velocity=h(vel), channel=ch_keys)
                add_rest(keys_track, HALF, ch_keys)
            elif bar_in_sec % 4 == 2:
                add_chord(keys_track, G_chord, HALF, velocity=h(vel), channel=ch_keys)
                add_rest(keys_track, HALF, ch_keys)
            else:
                add_chord(keys_track, Fsm_chord, HALF, velocity=h(vel + 3), channel=ch_keys)
                add_rest(keys_track, HALF, ch_keys)

        elif sec == 'chorus':
            # Louder organ sustains
            add_chord(keys_track, Am_chord, WHOLE, velocity=h(100), channel=ch_keys)

        elif sec == 'solo':
            # Organ arpeggios - ascending runs in Am scale
            bar_in_sec = bar - sections['solo'][0]
            # Different ascending patterns each bar
            start_idx = bar_in_sec % 5
            for beat in range(8):
                ni = (start_idx + beat) % len(am_scale)
                vel = h(85 + (beat % 4) * 3)
                add_note(keys_track, am_scale[ni], EIGHTH, velocity=vel, channel=ch_keys)

        elif sec == 'outro':
            # Return to intro organ pattern
            bar_in_sec = bar - sections['outro'][0]
            if bar_in_sec < 2:
                for n in [A3, C4, E4, A4]:
                    add_note(keys_track, n, QUARTER, velocity=h(75 - bar_in_sec * 8), channel=ch_keys)
            else:
                for n in [G3, B3, D4, G4]:
                    add_note(keys_track, n, QUARTER, velocity=h(60), channel=ch_keys)

    keys_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS ---
    bass_track = make_track("Bass", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No bass in intro
            add_rest(bass_track, WHOLE, ch_bass)

        elif sec in ('verse1', 'verse2', 'solo'):
            # Root walking with passing tones
            bar_in_sec = bar - sections[sec][0]
            vel_base = 82 if sec == 'verse1' else (85 if sec == 'verse2' else 88)
            if bar_in_sec % 4 < 2:
                root = A2
            elif bar_in_sec % 4 == 2:
                root = G2
            else:
                root = Fs2
            for eighth in range(8):
                if eighth == 0:
                    add_note(bass_track, root, EIGHTH, velocity=h(vel_base + 8), channel=ch_bass)
                elif eighth == 4:
                    add_note(bass_track, root + 7, EIGHTH, velocity=h(vel_base), channel=ch_bass)
                else:
                    add_note(bass_track, root, EIGHTH, velocity=h(vel_base - 8), channel=ch_bass)

        elif sec == 'chorus':
            # Louder, more active
            for eighth in range(8):
                vel = h(100 if eighth == 0 else 88)
                if eighth % 2 == 0:
                    add_note(bass_track, A2, EIGHTH, velocity=vel, channel=ch_bass)
                else:
                    add_note(bass_track, A2 + 7, EIGHTH, velocity=h(85), channel=ch_bass)

        elif sec == 'outro':
            # Simple root notes fading
            bar_in_sec = bar - sections['outro'][0]
            vel = max(75 - bar_in_sec * 12, 30)
            add_note(bass_track, A2, WHOLE, velocity=h(vel), channel=ch_bass)

    bass_track.append(MetaMessage('end_of_track', time=0))

    # --- Humanization pass (Doors: jazz swing, brushes, fills rush slightly) ---
    # Light My Fire has slightly more energy in fills — use a modified style
    doors_lmf_drums = dict(STYLE_DOORS_DRUMS)
    doors_lmf_drums['early_offset'] = 3  # Slight rushing tendency on fills
    drum_track = apply_humanization(drum_track, doors_lmf_drums, is_drum=True)
    keys_track = apply_humanization(keys_track, STYLE_DOORS_MELODY)
    bass_track = apply_humanization(bass_track, STYLE_DOORS_MELODY)

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(keys_track, bpm, os.path.join(folder, "keys.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, keys_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Light My Fire", "The Doors", bpm, "Am", total_bars, 4,
              ["drums", "keys", "bass"],
              structure="intro(4)-verse(8)-chorus(4)-solo(8)-verse(8)-outro(4)")
    print(f"  [OK] Light My Fire ({total_bars} bars)")


# ============================================================
# 5. JIMI HENDRIX - PURPLE HAZE
# Structure: INTRO(2) -> VERSE(8) -> CHORUS(4) -> VERSE2(8) -> SOLO(4) -> OUTRO(4) = 30
# ============================================================
def generate_purple_haze():
    random.seed(46)
    folder = os.path.join(BASE_DIR, "jimi_hendrix_purple_haze")
    ensure_dir(folder)
    bpm = 108
    total_bars = 30
    ch_drum = 9
    ch_guitar = 1
    ch_bass = 2

    # Notes
    Bb1 = 34
    E2, G2, A2, E3 = 40, 43, 45, 52
    Bb3 = 58
    E4, G4, A4, B4, D5, E5 = 64, 67, 69, 71, 74, 76
    Gs4 = 68
    # E pentatonic lead: E4-G4-A4-B4-D5-E5

    hendrix_chord = [E4, Gs4, B4, D5]  # E7#9

    sections = {
        'intro':  (0, 2),
        'verse1': (2, 10),
        'chorus': (10, 14),
        'verse2': (14, 22),
        'solo':   (22, 26),
        'outro':  (26, 30),
    }

    def get_section(bar):
        for name, (s, e) in sections.items():
            if s <= bar < e:
                return name
        return 'verse1'

    # --- DRUMS ---
    drum_track = make_track("Drums", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Sparse - just a couple hits with the tritone
            if bar == 0:
                add_rest(drum_track, WHOLE, ch_drum)
            else:
                # Kick + crash on the E7#9 entry
                add_note(drum_track, CRASH, QUARTER, velocity=h(110), channel=ch_drum)
                add_note(drum_track, KICK, EIGHTH, velocity=h(105), time=0, channel=ch_drum)
                add_rest(drum_track, QUARTER + HALF, ch_drum)

        elif sec in ('verse1', 'verse2'):
            # Mitch Mitchell loose style
            vel_base = 90 if sec == 'verse1' else 95
            if bar == sections[sec][0]:
                drum_crash_accent(drum_track, ch_drum, vel=105)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(vel_base), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(vel_base - 10), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(vel_base + 5), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(vel_base - 15), channel=ch_drum)

        elif sec == 'chorus':
            # Bigger drums, crash on 1
            if bar == sections['chorus'][0]:
                drum_crash_accent(drum_track, ch_drum, vel=115)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(105), channel=ch_drum)
                    add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(95), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(110), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(85), channel=ch_drum)

        elif sec == 'solo':
            # Driving pattern
            if bar == sections['solo'][0]:
                drum_crash_accent(drum_track, ch_drum, vel=108)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(95), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(88), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(100), channel=ch_drum)
                    add_note(drum_track, RIDE, EIGHTH, velocity=h(85), channel=ch_drum)

        elif sec == 'outro':
            # Big crash ending - fills and crashes
            if bar < total_bars - 1:
                drum_fill_toms(drum_track, ch_drum, vel=108)
            else:
                # Final crash
                track = drum_track
                track.append(note_on(CRASH, h(120), channel=ch_drum))
                track.append(note_on(KICK, h(115), time=0, channel=ch_drum))
                track.append(note_off(CRASH, time=WHOLE, channel=ch_drum))
                track.append(note_off(KICK, time=0, channel=ch_drum))

    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR ---
    guitar_track = make_track("Guitar", bpm)
    penta = [E4, G4, A4, B4, D5, E5]  # E pentatonic

    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # THE tritone: Bb-E alone, then E7#9 stabs
            if bar == 0:
                # Bb3 to E4 - the iconic opening
                add_note(guitar_track, Bb3, DOT_QUARTER, velocity=h(112), channel=ch_guitar)
                add_note(guitar_track, E4, DOT_QUARTER, velocity=h(115), channel=ch_guitar)
                add_note(guitar_track, Bb3, EIGHTH, velocity=h(108), channel=ch_guitar)
                add_note(guitar_track, E4, EIGHTH, velocity=h(110), channel=ch_guitar)
            else:
                # E7#9 chord stab
                add_chord(guitar_track, hendrix_chord, QUARTER, velocity=h(112), channel=ch_guitar)
                add_rest(guitar_track, EIGHTH, ch_guitar)
                add_chord(guitar_track, hendrix_chord, EIGHTH, velocity=h(108), channel=ch_guitar)
                add_rest(guitar_track, HALF, ch_guitar)

        elif sec in ('verse1', 'verse2'):
            # E-G-A power chord riff
            vel_base = 95 if sec == 'verse1' else 100
            add_note(guitar_track, E4, EIGHTH, velocity=h(vel_base + 5), channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_note(guitar_track, G4, EIGHTH, velocity=h(vel_base), channel=ch_guitar)
            add_note(guitar_track, A4, QUARTER, velocity=h(vel_base + 3), channel=ch_guitar)
            add_note(guitar_track, G4, EIGHTH, velocity=h(vel_base - 5), channel=ch_guitar)
            add_note(guitar_track, E4, QUARTER, velocity=h(vel_base), channel=ch_guitar)

            # Verse2: guitar fills between phrases
            if sec == 'verse2' and bar % 2 == 1:
                pass  # Variation built into the pattern

        elif sec == 'chorus':
            # Bigger - E7#9 chord stabs
            add_chord(guitar_track, hendrix_chord, EIGHTH, velocity=h(110), channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_chord(guitar_track, hendrix_chord, EIGHTH, velocity=h(105), channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_note(guitar_track, E4, EIGHTH, velocity=h(108), channel=ch_guitar)
            add_note(guitar_track, G4, EIGHTH, velocity=h(105), channel=ch_guitar)
            add_note(guitar_track, A4, QUARTER, velocity=h(110), channel=ch_guitar)

        elif sec == 'solo':
            # E pentatonic lead run
            bar_in_sec = bar - sections['solo'][0]
            for beat_8th in range(8):
                ni = (bar_in_sec * 8 + beat_8th) % len(penta)
                # Ascending/descending patterns
                if bar_in_sec % 2 == 0:
                    note = penta[ni]
                else:
                    note = penta[len(penta) - 1 - ni]
                vel = h(95 + (beat_8th % 4) * 3)
                add_note(guitar_track, note, EIGHTH, velocity=vel, channel=ch_guitar)

        elif sec == 'outro':
            # Feedback drone on E, big crash ending feel
            if bar < total_bars - 1:
                add_note(guitar_track, E4, WHOLE, velocity=h(100 - (bar - sections['outro'][0]) * 5), channel=ch_guitar)
            else:
                # Final big chord
                add_chord(guitar_track, hendrix_chord, WHOLE, velocity=h(120), channel=ch_guitar)

    guitar_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS ---
    bass_track = make_track("Bass", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Tritone support
            if bar == 0:
                add_note(bass_track, Bb1, HALF, velocity=h(95), channel=ch_bass)
                add_note(bass_track, E2, HALF, velocity=h(100), channel=ch_bass)
            else:
                add_note(bass_track, E2, WHOLE, velocity=h(95), channel=ch_bass)

        elif sec in ('verse1', 'verse2'):
            # Octave jumps locked with kick
            vel_base = 88 if sec == 'verse1' else 92
            add_note(bass_track, E2, EIGHTH, velocity=h(vel_base + 8), channel=ch_bass)
            add_note(bass_track, E2, EIGHTH, velocity=h(vel_base - 5), channel=ch_bass)
            add_note(bass_track, E3, EIGHTH, velocity=h(vel_base), channel=ch_bass)
            add_note(bass_track, E2, EIGHTH, velocity=h(vel_base - 3), channel=ch_bass)
            add_note(bass_track, G2, EIGHTH, velocity=h(vel_base), channel=ch_bass)
            add_note(bass_track, A2, EIGHTH, velocity=h(vel_base + 2), channel=ch_bass)
            add_note(bass_track, G2, EIGHTH, velocity=h(vel_base - 5), channel=ch_bass)
            add_note(bass_track, E2, EIGHTH, velocity=h(vel_base + 5), channel=ch_bass)

        elif sec == 'chorus':
            # Louder, driving
            for eighth in range(8):
                vel = h(105 if eighth == 0 else 92)
                add_note(bass_track, E2 if eighth % 2 == 0 else E3, EIGHTH, velocity=vel, channel=ch_bass)

        elif sec == 'solo':
            # Steady E root
            for eighth in range(8):
                add_note(bass_track, E2, EIGHTH, velocity=h(90), channel=ch_bass)

        elif sec == 'outro':
            # Feedback drone bass
            add_note(bass_track, E2, WHOLE, velocity=h(95), channel=ch_bass)

    bass_track.append(MetaMessage('end_of_track', time=0))

    # --- Humanization pass (Hendrix: Mitchell jazzy+loose, ghost snares everywhere) ---
    drum_track = apply_humanization(drum_track, STYLE_HENDRIX_DRUMS, is_drum=True)
    guitar_track = apply_humanization(guitar_track, STYLE_HENDRIX_MELODY)
    bass_track = apply_humanization(bass_track, STYLE_HENDRIX_MELODY)

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, guitar_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Purple Haze", "Jimi Hendrix", bpm, "E", total_bars, 4,
              ["drums", "guitar", "bass"],
              structure="intro(2)-verse(8)-chorus(4)-verse(8)-solo(4)-outro(4)")
    print(f"  [OK] Purple Haze ({total_bars} bars)")


# ============================================================
# 6. JIMI HENDRIX - VOODOO CHILD (SLIGHT RETURN)
# Structure: INTRO(4) -> VERSE(8) -> CHORUS(4) -> VERSE2(8) -> SOLO(4) -> OUTRO(4) = 32
# ============================================================
def generate_voodoo_child():
    random.seed(47)
    folder = os.path.join(BASE_DIR, "jimi_hendrix_voodoo_child")
    ensure_dir(folder)
    bpm = 88
    total_bars = 32
    ch_drum = 9
    ch_guitar = 1
    ch_bass = 2

    # Notes in Eb
    Eb2, E2n, F2, Gb2, Ab2, Bb2 = 39, 40, 41, 42, 44, 46
    Eb3, Gb3, Ab3, Bb3 = 51, 54, 56, 58
    Eb4, Db4, Bb4 = 63, 61, 70
    Ab4, Gb4 = 68, 66
    # Eb pentatonic: Eb4-Gb4-Ab4-Bb4-Db5
    Db5, Eb5 = 73, 75
    eb_penta = [Eb4, Gb4, Ab4, Bb4, Db5, Eb5]

    sections = {
        'intro':  (0, 4),
        'verse1': (4, 12),
        'chorus': (12, 16),
        'verse2': (16, 24),
        'solo':   (24, 28),
        'outro':  (28, 32),
    }

    def get_section(bar):
        for name, (s, e) in sections.items():
            if s <= bar < e:
                return name
        return 'verse1'

    # --- DRUMS ---
    drum_track = make_track("Drums", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No drums - wah guitar alone
            add_rest(drum_track, WHOLE, ch_drum)

        elif sec in ('verse1', 'verse2'):
            # Heavy shuffle, open hats
            vel_base = 100 if sec == 'verse1' else 105
            if bar == sections[sec][0]:
                drum_crash_accent(drum_track, ch_drum, vel=112)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(vel_base + 5), channel=ch_drum)
                    add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(vel_base - 10), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(vel_base + 8), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(vel_base - 15), channel=ch_drum)

        elif sec == 'chorus':
            # Big - crash accents, louder everything
            if bar == sections['chorus'][0]:
                drum_crash_accent(drum_track, ch_drum, vel=118)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(110), channel=ch_drum)
                    add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(100), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(115), channel=ch_drum)
                    add_note(drum_track, CRASH if beat == 1 and bar == sections['chorus'][0] else HAT_CLOSED,
                             EIGHTH, velocity=h(95), channel=ch_drum)

        elif sec == 'solo':
            # Driving groove
            if bar == sections['solo'][0]:
                drum_crash_accent(drum_track, ch_drum, vel=110)
            for beat in range(4):
                if beat in (0, 2):
                    add_note(drum_track, KICK, EIGHTH, velocity=h(100), channel=ch_drum)
                    add_note(drum_track, HAT_OPEN, EIGHTH, velocity=h(90), channel=ch_drum)
                else:
                    add_note(drum_track, SNARE, EIGHTH, velocity=h(105), channel=ch_drum)
                    add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=h(82), channel=ch_drum)

        elif sec == 'outro':
            # Wah riff return - big ending
            if bar < total_bars - 1:
                drum_beat_rock(drum_track, ch_drum, 108, 112, 92, open_hat=True)
            else:
                # Final crash
                drum_track.append(note_on(CRASH, h(120), channel=ch_drum))
                drum_track.append(note_on(KICK, h(118), time=0, channel=ch_drum))
                drum_track.append(note_off(CRASH, time=WHOLE, channel=ch_drum))
                drum_track.append(note_off(KICK, time=0, channel=ch_drum))

    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR ---
    guitar_track = make_track("Guitar", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # Wah guitar alone - Eb-Db-Bb-Ab descending
            add_note(guitar_track, Eb4, DOT_EIGHTH, velocity=h(108), channel=ch_guitar)
            add_note(guitar_track, Db4, SIXTEENTH, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, Bb3, QUARTER, velocity=h(105), channel=ch_guitar)
            add_note(guitar_track, Ab3, EIGHTH, velocity=h(95), channel=ch_guitar)
            add_note(guitar_track, Bb3, EIGHTH, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, Bb3, QUARTER, velocity=h(108), channel=ch_guitar)
            add_note(guitar_track, Eb4, QUARTER, velocity=h(112), channel=ch_guitar)

        elif sec == 'verse1':
            # Full band wah riff
            add_note(guitar_track, Eb4, DOT_EIGHTH, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, Db4, SIXTEENTH, velocity=h(92), channel=ch_guitar)
            add_note(guitar_track, Bb3, QUARTER, velocity=h(98), channel=ch_guitar)
            add_note(guitar_track, Ab3, EIGHTH, velocity=h(88), channel=ch_guitar)
            add_note(guitar_track, Bb3, EIGHTH, velocity=h(95), channel=ch_guitar)
            add_note(guitar_track, Bb3, QUARTER, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, Eb4, QUARTER, velocity=h(105), channel=ch_guitar)

        elif sec == 'verse2':
            # Wah sweep variations - different note choices
            bar_in_sec = bar - sections['verse2'][0]
            if bar_in_sec % 2 == 0:
                # Variation A: start from Ab
                add_note(guitar_track, Ab3, DOT_EIGHTH, velocity=h(100), channel=ch_guitar)
                add_note(guitar_track, Bb3, SIXTEENTH, velocity=h(95), channel=ch_guitar)
                add_note(guitar_track, Db4, QUARTER, velocity=h(102), channel=ch_guitar)
                add_note(guitar_track, Eb4, EIGHTH, velocity=h(98), channel=ch_guitar)
                add_note(guitar_track, Db4, EIGHTH, velocity=h(92), channel=ch_guitar)
                add_note(guitar_track, Bb3, QUARTER, velocity=h(100), channel=ch_guitar)
                add_note(guitar_track, Eb4, QUARTER, velocity=h(105), channel=ch_guitar)
            else:
                # Variation B: original pattern but octave up moments
                add_note(guitar_track, Eb4, EIGHTH, velocity=h(102), channel=ch_guitar)
                add_note(guitar_track, Gb4, EIGHTH, velocity=h(98), channel=ch_guitar)
                add_note(guitar_track, Ab4, QUARTER, velocity=h(105), channel=ch_guitar)
                add_note(guitar_track, Gb4, EIGHTH, velocity=h(95), channel=ch_guitar)
                add_note(guitar_track, Eb4, EIGHTH, velocity=h(100), channel=ch_guitar)
                add_note(guitar_track, Db4, QUARTER, velocity=h(95), channel=ch_guitar)
                add_note(guitar_track, Eb4, QUARTER, velocity=h(108), channel=ch_guitar)

        elif sec == 'chorus':
            # Big bend riff - power chord stabs
            add_chord(guitar_track, [Eb4, Bb4], EIGHTH, velocity=h(112), channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_chord(guitar_track, [Eb4, Bb4], EIGHTH, velocity=h(108), channel=ch_guitar)
            add_rest(guitar_track, EIGHTH, ch_guitar)
            add_note(guitar_track, Db4, EIGHTH, velocity=h(100), channel=ch_guitar)
            add_note(guitar_track, Eb4, QUARTER, velocity=h(110), channel=ch_guitar)
            add_note(guitar_track, Bb3, EIGHTH, velocity=h(105), channel=ch_guitar)

        elif sec == 'solo':
            # Eb pentatonic shred
            bar_in_sec = bar - sections['solo'][0]
            for beat_8th in range(8):
                ni = (bar_in_sec * 8 + beat_8th) % len(eb_penta)
                if bar_in_sec % 2 == 0:
                    note = eb_penta[ni]
                else:
                    note = eb_penta[len(eb_penta) - 1 - ni]
                vel = h(95 + (beat_8th % 3) * 4)
                add_note(guitar_track, note, EIGHTH, velocity=vel, channel=ch_guitar)

        elif sec == 'outro':
            # Wah riff return
            add_note(guitar_track, Eb4, DOT_EIGHTH, velocity=h(110), channel=ch_guitar)
            add_note(guitar_track, Db4, SIXTEENTH, velocity=h(102), channel=ch_guitar)
            add_note(guitar_track, Bb3, QUARTER, velocity=h(108), channel=ch_guitar)
            add_note(guitar_track, Ab3, EIGHTH, velocity=h(98), channel=ch_guitar)
            add_note(guitar_track, Bb3, EIGHTH, velocity=h(105), channel=ch_guitar)
            # Big ending on last bar
            if bar == total_bars - 1:
                add_chord(guitar_track, [Eb4, Bb4], HALF, velocity=h(120), channel=ch_guitar)
            else:
                add_note(guitar_track, Bb3, QUARTER, velocity=h(110), channel=ch_guitar)
                add_note(guitar_track, Eb4, QUARTER, velocity=h(115), channel=ch_guitar)

    guitar_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS ---
    bass_track = make_track("Bass", bpm)
    for bar in range(total_bars):
        sec = get_section(bar)

        if sec == 'intro':
            # No bass - wah guitar alone
            add_rest(bass_track, WHOLE, ch_bass)

        elif sec in ('verse1', 'verse2'):
            # Chromatic bass walks
            vel_base = 92 if sec == 'verse1' else 95
            add_note(bass_track, Eb2, EIGHTH, velocity=h(vel_base + 8), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=h(vel_base - 5), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=h(vel_base), channel=ch_bass)
            add_note(bass_track, E2n, EIGHTH, velocity=h(vel_base - 3), channel=ch_bass)
            add_note(bass_track, F2, EIGHTH, velocity=h(vel_base + 2), channel=ch_bass)
            add_note(bass_track, Gb2, EIGHTH, velocity=h(vel_base + 4), channel=ch_bass)
            add_note(bass_track, Ab2, EIGHTH, velocity=h(vel_base + 6), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=h(vel_base + 8), channel=ch_bass)

        elif sec == 'chorus':
            # Louder, accented
            add_note(bass_track, Eb2, EIGHTH, velocity=h(108), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=h(95), channel=ch_bass)
            add_note(bass_track, Ab2, EIGHTH, velocity=h(100), channel=ch_bass)
            add_note(bass_track, Bb2, EIGHTH, velocity=h(102), channel=ch_bass)
            add_note(bass_track, Ab2, EIGHTH, velocity=h(98), channel=ch_bass)
            add_note(bass_track, Gb2, EIGHTH, velocity=h(95), channel=ch_bass)
            add_note(bass_track, Eb2, QUARTER, velocity=h(105), channel=ch_bass)

        elif sec == 'solo':
            # Steady Eb root driving
            for eighth in range(8):
                vel = h(95 if eighth == 0 else 85)
                add_note(bass_track, Eb2, EIGHTH, velocity=vel, channel=ch_bass)

        elif sec == 'outro':
            # Wah riff bass support + big ending
            add_note(bass_track, Eb2, EIGHTH, velocity=h(105), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=h(90), channel=ch_bass)
            add_note(bass_track, Ab2, EIGHTH, velocity=h(95), channel=ch_bass)
            add_note(bass_track, Bb2, EIGHTH, velocity=h(98), channel=ch_bass)
            if bar == total_bars - 1:
                add_note(bass_track, Eb2, HALF, velocity=h(115), channel=ch_bass)
            else:
                add_note(bass_track, Ab2, EIGHTH, velocity=h(92), channel=ch_bass)
                add_note(bass_track, Gb2, EIGHTH, velocity=h(90), channel=ch_bass)
                add_note(bass_track, Eb2, QUARTER, velocity=h(100), channel=ch_bass)

    bass_track.append(MetaMessage('end_of_track', time=0))

    # --- Humanization pass (Hendrix: Mitchell jazzy+loose, ghost snares everywhere) ---
    drum_track = apply_humanization(drum_track, STYLE_HENDRIX_DRUMS, is_drum=True)
    guitar_track = apply_humanization(guitar_track, STYLE_HENDRIX_MELODY)
    bass_track = apply_humanization(bass_track, STYLE_HENDRIX_MELODY)

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, guitar_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Voodoo Child (Slight Return)", "Jimi Hendrix", bpm, "Eb", total_bars, 5,
              ["drums", "guitar", "bass"],
              structure="intro(4)-verse(8)-chorus(4)-verse(8)-solo(4)-outro(4)")
    print(f"  [OK] Voodoo Child ({total_bars} bars)")


# ============================================================
# MAIN
# ============================================================
def main():
    print("Generating Group 1 MIDI files (V3 - humanized with swing, ghost notes, feel)...")
    print(f"Output directory: {BASE_DIR}")
    print()

    generate_whole_lotta_love()
    generate_kashmir()
    generate_riders_on_the_storm()
    generate_light_my_fire()
    generate_purple_haze()
    generate_voodoo_child()

    print()
    print("All songs generated successfully!")
    for root, dirs, files in os.walk(BASE_DIR):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), BASE_DIR)
            size = os.path.getsize(os.path.join(root, f))
            print(f"  {rel} ({size} bytes)")


if __name__ == "__main__":
    main()
