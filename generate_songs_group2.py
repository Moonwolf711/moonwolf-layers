"""
Generate Group 2 MIDI files for moonwolf-layers.
Songs: AC/DC (Back in Black, Highway to Hell, Thunderstruck),
       Black Sabbath (Iron Man, Paranoid),
       Eagles (Hotel California, Take It Easy)

Each song has proper structure: intro, verse, chorus, bridge/solo, outro
with section-appropriate dynamics and signature musical moments.
"""

import json
import os
import random
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TPB = 480  # ticks per beat

WHOLE = TPB * 4
HALF = TPB * 2
QUARTER = TPB
EIGHTH = TPB // 2
SIXTEENTH = TPB // 4
DOTTED_QUARTER = int(TPB * 1.5)
DOTTED_EIGHTH = int(TPB * 0.75)
TRIPLET_EIGHTH = TPB // 3

# GM Drum map
KICK = 36
SNARE = 38
CLOSED_HAT = 42
OPEN_HAT = 46
CRASH = 49
CRASH2 = 57
RIDE = 51
RIDE_BELL = 53
LOW_TOM = 45
MID_TOM = 47
HI_TOM = 48
FLOOR_TOM = 41
COWBELL = 56
CHINA = 52

# ---------------------------------------------------------------------------
# Note helpers
# ---------------------------------------------------------------------------
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

def power_chord(root):
    return [root, root + 7]

def power_chord5(root):
    """Root + 5th + octave for big open sound."""
    return [root, root + 7, root + 12]

# ---------------------------------------------------------------------------
# MIDI helpers
# ---------------------------------------------------------------------------
def make_track(name, channel, tempo_val=None):
    track = MidiTrack()
    track.append(MetaMessage('track_name', name=name, time=0))
    if tempo_val is not None:
        track.append(MetaMessage('set_tempo', tempo=tempo_val, time=0))
    return track

def add_note(track, note, velocity, duration, channel=0, delay=0):
    track.append(Message('note_on', note=note, velocity=velocity, channel=channel, time=delay))
    track.append(Message('note_off', note=note, velocity=0, channel=channel, time=duration))

def add_rest(track, duration, channel=0):
    track.append(Message('note_on', note=0, velocity=0, channel=channel, time=duration))
    track.append(Message('note_off', note=0, velocity=0, channel=channel, time=0))

def add_chord(track, notes, velocity, duration, channel=0, delay=0):
    for i, nt in enumerate(notes):
        t = delay if i == 0 else 0
        track.append(Message('note_on', note=nt, velocity=velocity, channel=channel, time=t))
    for i, nt in enumerate(notes):
        t = duration if i == 0 else 0
        track.append(Message('note_off', note=nt, velocity=0, channel=channel, time=t))

def add_drum_hit(track, note, velocity, time_offset=0):
    track.append(Message('note_on', note=note, velocity=velocity, channel=9, time=time_offset))
    track.append(Message('note_off', note=note, velocity=0, channel=9, time=SIXTEENTH))

def add_drum_hits(track, notes_vels, time_offset=0):
    """Multiple simultaneous drum hits. notes_vels = [(note, vel), ...]"""
    for i, (nt, vel) in enumerate(notes_vels):
        t = time_offset if i == 0 else 0
        track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=t))
    for i, (nt, vel) in enumerate(notes_vels):
        t = SIXTEENTH if i == 0 else 0
        track.append(Message('note_off', note=nt, velocity=0, channel=9, time=t))

def drum_rest(track, duration):
    """Rest in drum track."""
    track.append(Message('note_on', note=0, velocity=0, channel=9, time=duration))
    track.append(Message('note_off', note=0, velocity=0, channel=9, time=0))

def save_midi(mid, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mid.save(path)

def save_meta(path, title, artist, bpm, key, bars, difficulty, instruments):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    meta = {
        "title": title, "artist": artist, "bpm": bpm, "key": key,
        "bars": bars, "difficulty": difficulty, "instruments": instruments
    }
    with open(path, 'w') as f:
        json.dump(meta, f, indent=2)

def combine_tracks(track_files, output_path):
    combined = MidiFile(ticks_per_beat=TPB)
    for fpath in track_files:
        m = MidiFile(fpath)
        for track in m.tracks:
            combined.tracks.append(track)
    save_midi(combined, output_path)

# ---------------------------------------------------------------------------
# Drum pattern builders
# ---------------------------------------------------------------------------
def rock_beat(track, bars, vel_kick=100, vel_snare=95, vel_hat=80,
              hat_note=CLOSED_HAT, crash_every=0, double_kick=False,
              first_beat_time=0):
    """Standard rock beat: kick 1+3, snare 2+4, hat 8ths.
    crash_every=N means crash on beat 1 every N bars (0=never)."""
    for bar in range(bars):
        for beat in range(4):
            for sub in range(2):  # 8th subdivisions
                hits = []
                if sub == 0:
                    if beat in (0, 2):
                        hits.append((KICK, vel_kick))
                    if double_kick and beat == 2 and sub == 0:
                        pass  # already added
                    if beat in (1, 3):
                        hits.append((SNARE, vel_snare))
                    hits.append((hat_note, vel_hat))
                    if crash_every > 0 and beat == 0 and bar % crash_every == 0:
                        hits.append((CRASH, vel_kick))
                else:
                    hits.append((hat_note, vel_hat - 15))

                t = first_beat_time if (bar == 0 and beat == 0 and sub == 0) else EIGHTH
                if bar == 0 and beat == 0 and sub == 0:
                    pass  # use first_beat_time
                for i, (nt, vel) in enumerate(hits):
                    tt = t if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))


def halftime_beat(track, bars, vel_kick=90, vel_snare=85, hat_note=RIDE,
                  vel_hat=75, crash_every=0, first_beat_time=0):
    """Half-time feel: kick on 1, snare on 3, hat/ride 8ths."""
    for bar in range(bars):
        for beat in range(4):
            for sub in range(2):
                hits = []
                if sub == 0:
                    if beat == 0:
                        hits.append((KICK, vel_kick))
                    if beat == 2:
                        hits.append((SNARE, vel_snare))
                        hits.append((KICK, vel_kick - 20))
                    hits.append((hat_note, vel_hat))
                    if crash_every > 0 and beat == 0 and bar % crash_every == 0:
                        hits.append((CRASH, vel_kick))
                else:
                    hits.append((hat_note, vel_hat - 15))

                t = first_beat_time if (bar == 0 and beat == 0 and sub == 0) else EIGHTH
                for i, (nt, vel) in enumerate(hits):
                    tt = t if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))


def crash_hit(track, time_offset=0, vel=110):
    """Single crash+kick accent."""
    add_drum_hits(track, [(CRASH, vel), (KICK, vel)], time_offset)


def fill_basic(track, duration_bars=1):
    """Basic snare/tom fill over given bars."""
    pattern = [HI_TOM, HI_TOM, MID_TOM, MID_TOM, LOW_TOM, LOW_TOM, FLOOR_TOM, SNARE]
    notes_per_bar = 8
    for bar in range(duration_bars):
        for i in range(notes_per_bar):
            nt = pattern[i % len(pattern)]
            vel = 100 + (i * 2)
            vel = min(vel, 120)
            track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=EIGHTH))
            track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))


# ---------------------------------------------------------------------------
# Humanization engine
# ---------------------------------------------------------------------------
def humanize_note(tick, velocity, ticks_per_beat, swing_amount=0.0,
                  timing_jitter=10, vel_jitter=8):
    """Apply swing, timing jitter, and velocity variation to a note."""
    eighth = ticks_per_beat // 2
    beat_pos = (tick % ticks_per_beat) / ticks_per_beat
    # Swing offbeats
    if 0.45 < beat_pos < 0.55:
        tick += int(swing_amount * eighth)
    tick += random.randint(-timing_jitter, timing_jitter)
    tick = max(0, tick)
    velocity += random.randint(-vel_jitter, vel_jitter)
    velocity = max(30, min(127, velocity))
    return tick, velocity


# Per-song humanization profiles
STYLE_ACDC = {
    'swing': 0.05,
    'drum_timing_jitter': 5,
    'drum_vel_jitter': 4,
    'guitar_timing_jitter': 3,
    'guitar_vel_jitter': 5,
    'bass_timing_jitter': 3,
    'bass_vel_jitter': 4,
    'ghost_hat_vel': (20, 30),
    'ghost_snare_vel': (25, 35),
    'crash_bar_interval': 4,       # crash on 1 every 4 bars hits HARD
    'crash_vel': 120,
}

STYLE_SABBATH = {
    'swing': 0.10,
    'drum_timing_jitter': 12,
    'drum_vel_jitter': 15,
    'guitar_timing_jitter': 8,
    'guitar_vel_jitter': 10,
    'bass_timing_jitter': 8,
    'bass_vel_jitter': 10,
    'kick_late_offset': 10,        # kick sits slightly behind
    'crash_early_offset': -8,      # crash hits early
    'ghost_snare_vel': (30, 40),
    'ghost_hat_vel': (20, 30),
    'tom_fill_crescendo': True,
}

STYLE_EAGLES_HC = {
    'swing': 0.15,                 # half-time feel
    'drum_timing_jitter': 6,
    'drum_vel_jitter': 5,
    'guitar_timing_jitter': 4,
    'guitar_vel_jitter': 4,
    'bass_timing_jitter': 4,
    'bass_vel_jitter': 3,
    'ghost_hat_vel': (20, 28),
    'ghost_snare_vel': (25, 35),
    'verse_vel_range': (70, 85),
    'chorus_vel_range': (85, 100),
}

STYLE_EAGLES_TIE = {
    'swing': 0.10,
    'drum_timing_jitter': 6,
    'drum_vel_jitter': 5,
    'guitar_timing_jitter': 4,
    'guitar_vel_jitter': 4,
    'bass_timing_jitter': 4,
    'bass_vel_jitter': 3,
    'ghost_hat_vel': (20, 28),
    'ghost_snare_vel': (25, 35),
    'verse_vel_range': (70, 85),
    'chorus_vel_range': (85, 100),
}


def humanize_track(track, ticks_per_beat, swing_amount=0.0,
                   timing_jitter=10, vel_jitter=8, kick_late=0,
                   crash_early=0, is_drum=False):
    """Walk a finished track and humanize timing + velocity in-place.
    Works on delta-time MIDI messages."""
    abs_tick = 0
    events = []

    # Convert to absolute ticks
    for msg in track:
        abs_tick += msg.time
        events.append((abs_tick, msg))

    new_track = MidiTrack()
    for i, (abs_t, msg) in enumerate(events):
        if isinstance(msg, MetaMessage):
            events[i] = (abs_t, msg)
            continue
        if msg.type == 'note_on' and msg.velocity > 0:
            note = msg.note
            vel = msg.velocity
            extra_offset = 0
            if is_drum:
                if note == KICK and kick_late:
                    extra_offset = kick_late
                if note == CRASH and crash_early:
                    extra_offset = crash_early
            new_tick, new_vel = humanize_note(
                abs_t + extra_offset, vel, ticks_per_beat,
                swing_amount, timing_jitter, vel_jitter
            )
            events[i] = (max(0, new_tick), msg.copy(velocity=new_vel))
        else:
            events[i] = (abs_t, msg)

    # Sort by absolute tick (stable sort keeps note-on before note-off at same tick)
    events.sort(key=lambda x: x[0])

    # Convert back to delta times
    prev_tick = 0
    for abs_t, msg in events:
        delta = max(0, abs_t - prev_tick)
        if isinstance(msg, MetaMessage):
            new_track.append(msg.copy(time=delta))
        else:
            new_track.append(msg.copy(time=delta))
        prev_tick = abs_t

    # Replace contents
    track.clear()
    for msg in new_track:
        track.append(msg)


def add_ghost_notes_to_drum_track(track, ticks_per_beat, style,
                                  total_bars, section_boundaries=None):
    """Insert ghost snare and ghost hat notes into a drum track.
    section_boundaries = list of (bar_start, bar_end) for each section.
    Adds snare drags before transitions."""
    ghost_snare_lo, ghost_snare_hi = style.get('ghost_snare_vel', (25, 40))
    ghost_hat_lo, ghost_hat_hi = style.get('ghost_hat_vel', (20, 30))
    sixteenth = ticks_per_beat // 4
    eighth = ticks_per_beat // 2
    bar_len = ticks_per_beat * 4

    # Convert to absolute time events
    abs_tick = 0
    events = []
    for msg in track:
        abs_tick += msg.time
        events.append([abs_tick, msg])

    ghost_events = []

    # Walk through bars and add ghost notes
    for bar in range(total_bars):
        bar_start = bar * bar_len
        for beat in range(4):
            beat_start = bar_start + beat * ticks_per_beat
            # Ghost hat taps at 16th note positions (e+a between 8th notes)
            for sub in [1, 3]:  # the "e" and "a" of each beat
                ghost_tick = beat_start + sub * sixteenth
                vel = random.randint(ghost_hat_lo, ghost_hat_hi)
                ghost_events.append((ghost_tick, CLOSED_HAT, vel))

            # Ghost snare between main snare hits (beats 2 and 4)
            if beat in (0, 2):  # add ghost snare before beats 2/4
                ghost_tick = beat_start + ticks_per_beat - sixteenth
                vel = random.randint(ghost_snare_lo, ghost_snare_hi)
                # Only 50% chance to avoid cluttering
                if random.random() < 0.5:
                    ghost_events.append((ghost_tick, SNARE, vel))

    # Add snare drags before section transitions
    if section_boundaries:
        for (sec_start, sec_end) in section_boundaries:
            transition_bar = sec_end - 1
            if transition_bar < 0 or transition_bar >= total_bars:
                continue
            drag_tick = (transition_bar + 1) * bar_len - eighth
            # Two ghost hits before the main downbeat
            ghost_events.append((drag_tick - sixteenth * 2, SNARE,
                                 random.randint(ghost_snare_lo, ghost_snare_hi)))
            ghost_events.append((drag_tick - sixteenth, SNARE,
                                 random.randint(ghost_snare_lo, ghost_snare_hi + 5)))

    # Merge ghost events into existing events
    for tick, note, vel in ghost_events:
        on_msg = Message('note_on', note=note, velocity=vel, channel=9, time=0)
        off_msg = Message('note_off', note=note, velocity=0, channel=9, time=sixteenth // 2)
        events.append([tick, on_msg])
        events.append([tick + sixteenth // 2, off_msg])

    # Sort by absolute tick
    events.sort(key=lambda x: x[0])

    # Convert back to delta times
    track.clear()
    prev_tick = 0
    for abs_t, msg in events:
        delta = max(0, abs_t - prev_tick)
        if isinstance(msg, MetaMessage):
            track.append(msg.copy(time=delta))
        else:
            track.append(msg.copy(time=delta))
        prev_tick = abs_t


def apply_guitar_alternating_vel(track, down_vel=90, up_vel=80):
    """For palm-muted 8th note patterns, alternate down/up pick velocity."""
    idx = 0
    for msg in track:
        if msg.type == 'note_on' and msg.velocity > 0:
            if idx % 2 == 0:
                msg.velocity = min(127, max(30, msg.velocity + (down_vel - 85)))
            else:
                msg.velocity = min(127, max(30, msg.velocity + (up_vel - 85)))
            idx += 1


def apply_arpeggio_crescendo(track, ticks_per_beat, notes_per_arp=8):
    """Apply subtle crescendo through each arpeggio pattern."""
    note_idx = 0
    for msg in track:
        if msg.type == 'note_on' and msg.velocity > 0:
            pos_in_arp = note_idx % notes_per_arp
            # Gradual velocity increase through the arpeggio
            crescendo_add = int((pos_in_arp / notes_per_arp) * 8)
            msg.velocity = min(127, msg.velocity + crescendo_add)
            note_idx += 1


# ===========================================================================
# SONG 1: AC/DC - Back in Black (BPM 92, key E)
# Structure: INTRO(4) VERSE(8) CHORUS(4) VERSE2(8) SOLO(4) OUTRO(4) = 32 bars
# ===========================================================================
def gen_back_in_black():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/acdc_back_in_black"
    bpm = 92
    tempo = mido.bpm2tempo(bpm)
    total_bars = 32

    e5 = power_chord(n('E4'))
    d5 = power_chord(n('D4'))
    a5 = power_chord(n('A3'))
    b5 = power_chord(n('B3'))

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (4 bars): bars 1-2 silence (bell hits only), bars 3-4 sparse kick enters
    # Bars 1-2: just cowbell / hi-hat ticks (the iconic bell intro)
    for bar in range(2):
        for beat in range(4):
            t = 0 if (bar == 0 and beat == 0) else QUARTER
            track.append(Message('note_on', note=COWBELL, velocity=110, channel=9, time=t))
            track.append(Message('note_off', note=COWBELL, velocity=0, channel=9, time=0))
    # Bars 3-4: kick enters on 1+3 with hat
    for bar in range(2):
        for beat in range(4):
            hits = []
            if beat in (0, 2):
                hits.append((KICK, 90))
            hits.append((CLOSED_HAT, 75))
            for i, (nt, vel) in enumerate(hits):
                tt = QUARTER if i == 0 else 0
                track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
            for i, (nt, vel) in enumerate(hits):
                track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # VERSE 1 (8 bars): Phil Rudd straight beat, moderate velocity
    rock_beat(track, 8, vel_kick=95, vel_snare=90, vel_hat=80,
              hat_note=OPEN_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS (4 bars): louder, crash every bar
    rock_beat(track, 4, vel_kick=110, vel_snare=105, vel_hat=90,
              hat_note=CRASH, crash_every=1, first_beat_time=EIGHTH)

    # VERSE 2 (8 bars): same as verse 1
    rock_beat(track, 8, vel_kick=95, vel_snare=90, vel_hat=80,
              hat_note=OPEN_HAT, crash_every=4, first_beat_time=EIGHTH)

    # SOLO (4 bars): driving, crash every 2 bars
    rock_beat(track, 3, vel_kick=105, vel_snare=100, vel_hat=85,
              hat_note=OPEN_HAT, crash_every=2, first_beat_time=EIGHTH)
    fill_basic(track, 1)

    # OUTRO (4 bars): big ending
    rock_beat(track, 3, vel_kick=115, vel_snare=110, vel_hat=90,
              hat_note=CRASH, crash_every=1, first_beat_time=EIGHTH)
    # Final crash
    crash_hit(track, EIGHTH, 120)
    drum_rest(track, WHOLE - SIXTEENTH)

    # -- Humanize drums: AC/DC Phil Rudd tight style --
    style = STYLE_ACDC
    section_bounds = [(0, 4), (4, 12), (12, 16), (16, 24), (24, 28), (28, 32)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'], is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (4 bars): bars 1-2 bell/chime hits (high harmonics), bars 3-4 riff enters
    # Bars 1-2: bell-like high harmonics
    bell_notes = [n('E5'), n('B4'), n('E5'), n('B4')]
    for i, nt in enumerate(bell_notes):
        add_note(track, nt, 100, HALF, channel=1, delay=0 if i == 0 else HALF)
    # Bars 3-4: riff enters alone
    riff_2bar = [
        (e5, EIGHTH, 95), (e5, EIGHTH, 85), (d5, EIGHTH, 90), (d5, EIGHTH, 80),
        (e5, EIGHTH, 95), (e5, EIGHTH, 85), (d5, EIGHTH, 90), (d5, EIGHTH, 80),
        (a5, EIGHTH, 95), (a5, EIGHTH, 85), (d5, EIGHTH, 90), (d5, EIGHTH, 80),
        (e5, EIGHTH, 95), (e5, EIGHTH, 85), (e5, QUARTER, 100),
    ]
    # This is slightly less than 2 bars (15 eighths = 1.875 bars), pad
    for chord, dur, vel in riff_2bar:
        add_chord(track, chord, vel, dur, channel=1)
    add_rest(track, EIGHTH, channel=1)  # pad to 2 bars

    # VERSE 1 (8 bars): E5-D5-A5 gallop riff, verse velocity
    def verse_riff(track, bars, vel_base=80):
        riff = [
            (e5, EIGHTH, vel_base+10), (e5, EIGHTH, vel_base),
            (d5, EIGHTH, vel_base+5), (d5, EIGHTH, vel_base-5),
            (e5, EIGHTH, vel_base+10), (e5, EIGHTH, vel_base),
            (d5, EIGHTH, vel_base+5), (d5, EIGHTH, vel_base-5),
            (a5, EIGHTH, vel_base+10), (a5, EIGHTH, vel_base),
            (d5, EIGHTH, vel_base+5), (d5, EIGHTH, vel_base-5),
            (e5, EIGHTH, vel_base+15), (e5, EIGHTH, vel_base+5),
            (e5, EIGHTH, vel_base+10), (e5, EIGHTH, vel_base),
        ]
        for rep in range(bars // 2):
            for chord, dur, vel in riff:
                add_chord(track, chord, vel, dur, channel=1)

    verse_riff(track, 8, vel_base=80)

    # CHORUS (4 bars): open power chords, louder
    chorus_chords = [
        (power_chord5(n('A3')), HALF, 105),
        (power_chord5(n('E4')), HALF, 110),
        (power_chord5(n('B3')), HALF, 105),
        (power_chord5(n('A3')), HALF, 110),
        (power_chord5(n('E4')), HALF, 105),
        (power_chord5(n('D4')), HALF, 100),
        (power_chord5(n('A3')), HALF, 110),
        (power_chord5(n('E4')), HALF, 115),
    ]
    for chord, dur, vel in chorus_chords:
        add_chord(track, chord, vel, dur, channel=1)

    # VERSE 2 (8 bars): same riff + guitar fills between phrases
    verse_riff(track, 6, vel_base=82)
    # 2 bars with fill
    for chord, dur, vel in riff_2bar:
        add_chord(track, chord, vel + 5, dur, channel=1)
    add_rest(track, EIGHTH, channel=1)

    # SOLO (4 bars): Angus pentatonic run E-G-A-B-D
    solo_notes = [
        n('E4'), n('G4'), n('A4'), n('B4'), n('D5'), n('E5'),
        n('D5'), n('B4'), n('A4'), n('G4'), n('E4'), n('G4'),
        n('A4'), n('B4'), n('D5'), n('E5'), n('D5'), n('B4'),
        n('E5'), n('D5'), n('B4'), n('A4'), n('G4'), n('A4'),
        n('B4'), n('D5'), n('E5'), n('G5'), n('E5'), n('D5'),
        n('B4'), n('A4'),
    ]
    for i, nt in enumerate(solo_notes):
        vel = 110 if i % 4 == 0 else 95
        add_note(track, nt, vel, EIGHTH, channel=1)

    # OUTRO (4 bars): big riff + crashes
    verse_riff(track, 2, vel_base=95)
    # Final 2 bars: sustained E5
    add_chord(track, power_chord5(n('E4')), 115, WHOLE, channel=1)
    add_chord(track, power_chord5(n('E4')), 120, WHOLE, channel=1)

    # -- Humanize guitar: AC/DC tight palm mutes --
    apply_guitar_alternating_vel(track, down_vel=90, up_vel=80)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (4 bars): silent bars 1-2, enters bars 3-4
    add_rest(track, WHOLE * 2, channel=2)
    bass_2bar = [
        (n('E2'), EIGHTH, 90), (n('E2'), EIGHTH, 80),
        (n('D2'), EIGHTH, 85), (n('D2'), EIGHTH, 75),
        (n('E2'), EIGHTH, 90), (n('E2'), EIGHTH, 80),
        (n('D2'), EIGHTH, 85), (n('D2'), EIGHTH, 75),
        (n('A1'), EIGHTH, 90), (n('A1'), EIGHTH, 80),
        (n('D2'), EIGHTH, 85), (n('D2'), EIGHTH, 75),
        (n('E2'), EIGHTH, 95), (n('E2'), EIGHTH, 85),
        (n('E2'), EIGHTH, 90), (n('E2'), EIGHTH, 80),
    ]
    for nt, dur, vel in bass_2bar:
        add_note(track, nt, vel, dur, channel=2)

    # VERSE 1 (8 bars): locked to kick
    def bass_verse(track, bars, vel_base=80):
        pattern = [
            (n('E2'), EIGHTH), (n('E2'), EIGHTH),
            (n('D2'), EIGHTH), (n('D2'), EIGHTH),
            (n('E2'), EIGHTH), (n('E2'), EIGHTH),
            (n('D2'), EIGHTH), (n('D2'), EIGHTH),
            (n('A1'), EIGHTH), (n('A1'), EIGHTH),
            (n('D2'), EIGHTH), (n('D2'), EIGHTH),
            (n('E2'), EIGHTH), (n('E2'), EIGHTH),
            (n('E2'), EIGHTH), (n('E2'), EIGHTH),
        ]
        for rep in range(bars // 2):
            for i, (nt, dur) in enumerate(pattern):
                vel = vel_base + 10 if i % 2 == 0 else vel_base
                add_note(track, nt, vel, dur, channel=2)

    bass_verse(track, 8, vel_base=78)

    # CHORUS (4 bars): root notes following guitar
    chorus_bass = [n('A1'), n('E2'), n('B1'), n('A1'), n('E2'), n('D2'), n('A1'), n('E2')]
    for nt in chorus_bass:
        add_note(track, nt, 100, HALF, channel=2)

    # VERSE 2 (8 bars)
    bass_verse(track, 8, vel_base=82)

    # SOLO (4 bars): pedal E
    for bar in range(4):
        for eighth in range(8):
            vel = 95 if eighth % 2 == 0 else 82
            add_note(track, n('E2'), vel, EIGHTH, channel=2)

    # OUTRO (4 bars)
    bass_verse(track, 2, vel_base=90)
    add_note(track, n('E2'), 110, WHOLE, channel=2)
    add_note(track, n('E2'), 115, WHOLE, channel=2)

    # -- Humanize bass: AC/DC tight --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Back in Black", "AC/DC", bpm, "E",
              total_bars, 3, ["drums", "guitar", "bass"])
    print("  [OK] AC/DC - Back in Black (32 bars)")


# ===========================================================================
# SONG 2: AC/DC - Highway to Hell (BPM 116, key A)
# Structure: INTRO(2) VERSE(8) CHORUS(8) VERSE2(8) CHORUS2(8) OUTRO(4) = 38 bars
# ===========================================================================
def gen_highway_to_hell():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/acdc_highway_to_hell"
    bpm = 116
    tempo = mido.bpm2tempo(bpm)
    total_bars = 38

    a5 = power_chord(n('A3'))
    d_fsharp = [n('F#3'), n('A3'), n('D4')]
    g5 = power_chord(n('G3'))
    d5 = power_chord(n('D4'))

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (2 bars): count-in snare hits then crash + A5
    # Bar 1: 4 snare quarter hits (count-in)
    for beat in range(4):
        t = 0 if beat == 0 else QUARTER
        track.append(Message('note_on', note=SNARE, velocity=100 + beat * 5, channel=9, time=t))
        track.append(Message('note_off', note=SNARE, velocity=0, channel=9, time=0))
    # Bar 2: crash on 1, then rock beat
    crash_hit(track, QUARTER, 115)
    for beat in range(1, 4):
        hits = []
        if beat == 2:
            hits.append((KICK, 100))
        if beat in (1, 3):
            hits.append((SNARE, 95))
        hits.append((OPEN_HAT, 85))
        for i, (nt, vel) in enumerate(hits):
            tt = (QUARTER - SIXTEENTH) if (i == 0 and beat == 1) else (QUARTER if i == 0 else 0)
            track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
        for i, (nt, vel) in enumerate(hits):
            track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # VERSE 1 (8 bars): driving beat, hat 8ths
    rock_beat(track, 8, vel_kick=95, vel_snare=90, vel_hat=80,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS 1 (8 bars): louder, crash every bar, open hat
    rock_beat(track, 8, vel_kick=110, vel_snare=105, vel_hat=90,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)

    # VERSE 2 (8 bars)
    rock_beat(track, 8, vel_kick=95, vel_snare=90, vel_hat=80,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS 2 (8 bars)
    rock_beat(track, 7, vel_kick=110, vel_snare=105, vel_hat=90,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)
    fill_basic(track, 1)

    # OUTRO (4 bars): big riff ending
    rock_beat(track, 3, vel_kick=115, vel_snare=110, vel_hat=95,
              hat_note=CRASH, crash_every=1, first_beat_time=EIGHTH)
    crash_hit(track, EIGHTH, 127)
    drum_rest(track, WHOLE - SIXTEENTH)

    # -- Humanize drums: AC/DC Phil Rudd tight --
    style = STYLE_ACDC
    section_bounds = [(0, 2), (2, 10), (10, 18), (18, 26), (26, 34), (34, 38)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'], is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (2 bars): silent bar 1 (drums count-in), bar 2 A5 chord hit
    add_rest(track, WHOLE, channel=1)
    add_chord(track, power_chord5(n('A3')), 110, WHOLE, channel=1)

    # Verse riff: A5 - D/F# - G5 - D/F# palm muted 8ths
    def hth_verse(track, bars, vel_base=80):
        progression = [a5, d_fsharp, g5, d_fsharp]
        for rep in range(bars // 4):
            for chord in progression:
                for eighth in range(8):
                    vel = vel_base + 10 if eighth % 2 == 0 else vel_base - 5
                    # Accent beat 1
                    if eighth == 0:
                        vel = vel_base + 15
                    add_chord(track, chord, vel, EIGHTH, channel=1)

    # VERSE 1 (8 bars)
    hth_verse(track, 8, vel_base=78)

    # CHORUS 1 (8 bars): open chords, louder
    def hth_chorus(track, bars, vel_base=100):
        # A - D - G - D progression with open voicings
        chorus_prog = [
            power_chord5(n('A3')), power_chord5(n('D4')),
            power_chord5(n('G3')), power_chord5(n('D4')),
        ]
        for rep in range(bars // 4):
            for chord in chorus_prog:
                # Quarter note strums
                for q in range(4):
                    vel = vel_base + 10 if q == 0 else vel_base
                    add_chord(track, chord, vel, QUARTER, channel=1)

    hth_chorus(track, 8, vel_base=100)

    # VERSE 2 (8 bars)
    hth_verse(track, 8, vel_base=82)

    # CHORUS 2 (8 bars)
    hth_chorus(track, 8, vel_base=105)

    # OUTRO (4 bars): big riff, sustained ending
    hth_verse(track, 2, vel_base=95)
    add_chord(track, power_chord5(n('A3')), 115, WHOLE, channel=1)
    add_chord(track, power_chord5(n('A3')), 120, WHOLE, channel=1)

    # -- Humanize guitar: AC/DC tight palm mutes --
    apply_guitar_alternating_vel(track, down_vel=90, up_vel=80)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (2 bars): silent bar 1, A2 bar 2
    add_rest(track, WHOLE, channel=2)
    add_note(track, n('A2'), 100, WHOLE, channel=2)

    # Verse bass: root 8ths locked to kick
    def hth_bass_verse(track, bars, vel_base=80):
        roots = [n('A2'), n('D2'), n('G2'), n('D2')]
        for rep in range(bars // 4):
            for root in roots:
                for eighth in range(8):
                    vel = vel_base + 10 if eighth % 2 == 0 else vel_base
                    if eighth == 0:
                        vel = vel_base + 15
                    add_note(track, root, vel, EIGHTH, channel=2)

    hth_bass_verse(track, 8, vel_base=78)

    # Chorus bass: quarter notes, louder
    def hth_bass_chorus(track, bars, vel_base=95):
        roots = [n('A2'), n('D2'), n('G2'), n('D2')]
        for rep in range(bars // 4):
            for root in roots:
                for q in range(4):
                    vel = vel_base + 10 if q == 0 else vel_base
                    add_note(track, root, vel, QUARTER, channel=2)

    hth_bass_chorus(track, 8, vel_base=95)
    hth_bass_verse(track, 8, vel_base=82)
    hth_bass_chorus(track, 8, vel_base=100)

    # OUTRO (4 bars)
    hth_bass_verse(track, 2, vel_base=90)
    add_note(track, n('A2'), 110, WHOLE, channel=2)
    add_note(track, n('A2'), 115, WHOLE, channel=2)

    # -- Humanize bass: AC/DC tight --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Highway to Hell", "AC/DC", bpm, "A",
              total_bars, 3, ["drums", "guitar", "bass"])
    print("  [OK] AC/DC - Highway to Hell (38 bars)")


# ===========================================================================
# SONG 3: AC/DC - Thunderstruck (BPM 134, key B)
# Structure: INTRO(8) BUILD(4) VERSE(8) CHORUS(4) VERSE2(8) SOLO(4) OUTRO(4) = 40 bars
# ===========================================================================
def gen_thunderstruck():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/acdc_thunderstruck"
    bpm = 134
    tempo = mido.bpm2tempo(bpm)
    total_bars = 40

    b5 = power_chord(n('B3'))
    a5 = power_chord(n('A3'))
    e5 = power_chord(n('E4'))

    # THE hammer-on riff pattern
    riff_notes = [n('B4'), n('E4'), n('B4'), n('A4'), n('B4'), n('G#4'), n('A4'), n('E4')]

    def hammer_on_bars(track, bars, vel_base=90):
        """The iconic 16th note hammer-on riff."""
        total = bars * 16
        for i in range(total):
            nt = riff_notes[i % len(riff_notes)]
            vel = vel_base + 10 if i % 4 == 0 else vel_base
            if nt == n('B4'):
                vel = min(vel + 8, 120)
            add_note(track, nt, vel, SIXTEENTH, channel=1)

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (8 bars): NO DRUMS -- complete silence
    drum_rest(track, WHOLE * 8)

    # BUILD (4 bars): hi-hat 16ths enter, then kick, then full kit
    # Bar 1: just hi-hat 16ths
    for s in range(16):
        vel = 80 if s % 4 == 0 else 65
        t = 0 if s == 0 else SIXTEENTH
        track.append(Message('note_on', note=CLOSED_HAT, velocity=vel, channel=9, time=t))
        track.append(Message('note_off', note=CLOSED_HAT, velocity=0, channel=9, time=0))
    # Bar 2: hi-hat + kick on 1 and 3
    for s in range(16):
        hits = [(CLOSED_HAT, 80 if s % 4 == 0 else 65)]
        if s % 8 == 0:
            hits.append((KICK, 90))
        for i, (nt, vel) in enumerate(hits):
            tt = SIXTEENTH if i == 0 else 0
            track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
        for i, (nt, vel) in enumerate(hits):
            track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))
    # Bar 3-4: full kit enters
    rock_beat(track, 2, vel_kick=100, vel_snare=95, vel_hat=85,
              hat_note=CLOSED_HAT, crash_every=0, first_beat_time=EIGHTH)

    # VERSE 1 (8 bars): full band driving
    rock_beat(track, 8, vel_kick=105, vel_snare=100, vel_hat=85,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS (4 bars): crash accents, louder
    rock_beat(track, 4, vel_kick=115, vel_snare=110, vel_hat=95,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)

    # VERSE 2 (8 bars)
    rock_beat(track, 8, vel_kick=105, vel_snare=100, vel_hat=85,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)

    # SOLO (4 bars): double kick feel
    for bar in range(4):
        for beat in range(4):
            for sub in range(4):
                hits = []
                if sub == 0:
                    hits.append((KICK, 110))
                    if beat in (1, 3):
                        hits.append((SNARE, 105))
                    hits.append((CLOSED_HAT, 90))
                    if beat == 0 and bar % 2 == 0:
                        hits.append((CRASH, 110))
                elif sub == 2:
                    hits.append((KICK, 90))
                    hits.append((CLOSED_HAT, 75))
                else:
                    hits.append((CLOSED_HAT, 65))
                for i, (nt, vel) in enumerate(hits):
                    tt = SIXTEENTH if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # OUTRO (4 bars): big ending with crash
    rock_beat(track, 3, vel_kick=115, vel_snare=110, vel_hat=90,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)
    crash_hit(track, EIGHTH, 127)
    drum_rest(track, WHOLE - SIXTEENTH)

    # -- Humanize drums: AC/DC Phil Rudd tight --
    style = STYLE_ACDC
    section_bounds = [(0, 8), (8, 12), (12, 20), (20, 24), (24, 32), (32, 36), (36, 40)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'], is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (8 bars): THE hammer-on riff ALONE
    hammer_on_bars(track, 8, vel_base=88)

    # BUILD (4 bars): riff continues with slightly more intensity
    hammer_on_bars(track, 4, vel_base=95)

    # VERSE 1 (8 bars): B5 power chord rhythm
    for bar in range(8):
        # Driving 8th note power chord rhythm
        for eighth in range(8):
            vel = 95 if eighth == 0 else (85 if eighth % 2 == 0 else 75)
            chord = b5 if eighth < 6 else a5
            add_chord(track, chord, vel, EIGHTH, channel=1)

    # CHORUS (4 bars): open chords, louder
    chorus_prog = [
        (power_chord5(n('B3')), HALF, 110), (power_chord5(n('E4')), HALF, 105),
        (power_chord5(n('A3')), HALF, 108), (power_chord5(n('E4')), HALF, 112),
        (power_chord5(n('B3')), HALF, 110), (power_chord5(n('E4')), HALF, 105),
        (power_chord5(n('A3')), HALF, 108), (power_chord5(n('B3')), HALF, 115),
    ]
    for chord, dur, vel in chorus_prog:
        add_chord(track, chord, vel, dur, channel=1)

    # VERSE 2 (8 bars): same rhythm
    for bar in range(8):
        for eighth in range(8):
            vel = 98 if eighth == 0 else (88 if eighth % 2 == 0 else 78)
            chord = b5 if eighth < 6 else a5
            add_chord(track, chord, vel, EIGHTH, channel=1)

    # SOLO (4 bars): B pentatonic shred
    solo = [
        n('B4'), n('D5'), n('E5'), n('F#5'), n('A5'), n('B5'),
        n('A5'), n('F#5'), n('E5'), n('D5'), n('B4'), n('D5'),
        n('E5'), n('F#5'), n('A5'), n('B5'), n('A5'), n('F#5'),
        n('B5'), n('A5'), n('F#5'), n('E5'), n('D5'), n('E5'),
        n('F#5'), n('A5'), n('B5'), n('A5'), n('F#5'), n('E5'),
        n('D5'), n('B4'),
        # Second phrase
        n('B4'), n('E5'), n('F#5'), n('B5'), n('A5'), n('F#5'),
        n('E5'), n('D5'), n('B4'), n('D5'), n('F#5'), n('A5'),
        n('B5'), n('A5'), n('F#5'), n('E5'), n('D5'), n('B4'),
        n('D5'), n('E5'), n('F#5'), n('A5'), n('B5'), n('A5'),
        n('F#5'), n('E5'), n('D5'), n('B4'), n('A4'), n('B4'),
        n('D5'), n('E5'),
    ]
    for i, nt in enumerate(solo):
        vel = 112 if i % 4 == 0 else 95
        add_note(track, nt, vel, EIGHTH, channel=1)

    # OUTRO (4 bars): hammer-on riff returns with full band
    hammer_on_bars(track, 3, vel_base=100)
    # Final bar: big B5
    add_chord(track, power_chord5(n('B3')), 120, WHOLE, channel=1)

    # -- Humanize guitar: AC/DC tight palm mutes --
    apply_guitar_alternating_vel(track, down_vel=90, up_vel=80)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (8 bars): silent
    add_rest(track, WHOLE * 8, channel=2)

    # BUILD (4 bars): bars 1-2 silent, bars 3-4 B2 pedal enters
    add_rest(track, WHOLE * 2, channel=2)
    for bar in range(2):
        for eighth in range(8):
            vel = 90 if eighth % 2 == 0 else 78
            add_note(track, n('B2'), vel, EIGHTH, channel=2)

    # VERSE 1 (8 bars): B2 pumping 8ths
    for bar in range(8):
        for eighth in range(8):
            vel = 92 if eighth == 0 else (82 if eighth % 2 == 0 else 75)
            add_note(track, n('B2'), vel, EIGHTH, channel=2)

    # CHORUS (4 bars): root motion following guitar
    chorus_roots = [n('B2'), n('E2'), n('A2'), n('E2'), n('B2'), n('E2'), n('A2'), n('B2')]
    for root in chorus_roots:
        add_note(track, root, 100, HALF, channel=2)

    # VERSE 2 (8 bars)
    for bar in range(8):
        for eighth in range(8):
            vel = 95 if eighth == 0 else (85 if eighth % 2 == 0 else 78)
            add_note(track, n('B2'), vel, EIGHTH, channel=2)

    # SOLO (4 bars): driving 8ths
    for bar in range(4):
        for eighth in range(8):
            vel = 100 if eighth % 2 == 0 else 85
            add_note(track, n('B2'), vel, EIGHTH, channel=2)

    # OUTRO (4 bars)
    for bar in range(3):
        for eighth in range(8):
            vel = 100 if eighth == 0 else 88
            add_note(track, n('B2'), vel, EIGHTH, channel=2)
    add_note(track, n('B2'), 115, WHOLE, channel=2)

    # -- Humanize bass: AC/DC tight --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Thunderstruck", "AC/DC", bpm, "B",
              total_bars, 4, ["drums", "guitar", "bass"])
    print("  [OK] AC/DC - Thunderstruck (40 bars)")


# ===========================================================================
# SONG 4: Black Sabbath - Iron Man (BPM 76, key Bm)
# Structure: INTRO(4) THE_RIFF(8) VERSE(8) CHORUS(4) BRIDGE(4) RIFF_RETURN(8) OUTRO(4) = 40 bars
# ===========================================================================
def gen_iron_man():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/black_sabbath_iron_man"
    bpm = 76
    tempo = mido.bpm2tempo(bpm)
    total_bars = 40

    # THE RIFF notes as power chords
    def iron_man_riff(track, bars, vel_base=95, channel=1):
        """The iconic B-D-E (bend) - G-F#-G-F#-D-E riff, 2 bars per cycle."""
        riff = [
            (power_chord(n('B2')), QUARTER, vel_base + 5),
            (power_chord(n('B2')), QUARTER, vel_base),
            (power_chord(n('D3')), QUARTER, vel_base + 5),
            (power_chord(n('D3')), QUARTER, vel_base),
            # Bar 2
            (power_chord(n('E3')), DOTTED_QUARTER, vel_base + 10),  # the bend
            (power_chord(n('E3')), EIGHTH, vel_base + 5),
            (power_chord(n('G3')), EIGHTH, vel_base),
            (power_chord(n('F#3')), EIGHTH, vel_base - 5),
            (power_chord(n('G3')), EIGHTH, vel_base),
            (power_chord(n('F#3')), EIGHTH, vel_base - 5),
            (power_chord(n('D3')), EIGHTH, vel_base),
            (power_chord(n('E3')), EIGHTH + QUARTER, vel_base + 5),
        ]
        for rep in range(bars // 2):
            for chord, dur, vel in riff:
                add_chord(track, chord, vel, dur, channel=channel)

    def iron_man_bass_riff(track, bars, vel_base=90):
        """Bass follows guitar, octave down."""
        riff = [
            (n('B1'), QUARTER, vel_base + 5),
            (n('B1'), QUARTER, vel_base),
            (n('D2'), QUARTER, vel_base + 5),
            (n('D2'), QUARTER, vel_base),
            (n('E2'), DOTTED_QUARTER, vel_base + 10),
            (n('E2'), EIGHTH, vel_base + 5),
            (n('G2'), EIGHTH, vel_base),
            (n('F#2'), EIGHTH, vel_base - 5),
            (n('G2'), EIGHTH, vel_base),
            (n('F#2'), EIGHTH, vel_base - 5),
            (n('D2'), EIGHTH, vel_base),
            (n('E2'), EIGHTH + QUARTER, vel_base + 5),
        ]
        for rep in range(bars // 2):
            for nt, dur, vel in riff:
                add_note(track, nt, vel, dur, channel=2)

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (4 bars): no drums, just the drone
    drum_rest(track, WHOLE * 4)

    # THE RIFF (8 bars): heavy kick+crash on chord hits, Bill Ward style
    for bar in range(8):
        for beat in range(4):
            hits = []
            if beat == 0:
                hits.append((KICK, 110))
                if bar % 2 == 0:
                    hits.append((CRASH, 105))
                hits.append((CLOSED_HAT, 80))
            elif beat == 1:
                hits.append((SNARE, 95))
                hits.append((CLOSED_HAT, 80))
            elif beat == 2:
                hits.append((KICK, 100))
                hits.append((CLOSED_HAT, 80))
            else:
                hits.append((SNARE, 90))
                hits.append((CLOSED_HAT, 80))
            t = 0 if (bar == 0 and beat == 0) else QUARTER
            for i, (nt, vel) in enumerate(hits):
                tt = t if i == 0 else 0
                track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
            for i, (nt, vel) in enumerate(hits):
                track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # VERSE (8 bars): drums get busier, hi-hat 8ths
    rock_beat(track, 8, vel_kick=100, vel_snare=95, vel_hat=85,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS (4 bars): double-time feel, faster drums
    for bar in range(4):
        for beat in range(4):
            for sub in range(2):
                hits = []
                if sub == 0:
                    hits.append((KICK, 110))
                    if beat in (1, 3):
                        hits.append((SNARE, 108))
                    hits.append((OPEN_HAT, 90))
                    if beat == 0:
                        hits.append((CRASH, 110))
                else:
                    hits.append((KICK, 85))
                    hits.append((CLOSED_HAT, 75))
                for i, (nt, vel) in enumerate(hits):
                    tt = EIGHTH if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # BRIDGE (4 bars): tom breakdown, sparser
    for bar in range(4):
        for beat in range(4):
            if beat == 0:
                add_drum_hits(track, [(FLOOR_TOM, 100), (KICK, 95)], QUARTER)
            elif beat == 1:
                add_drum_hits(track, [(LOW_TOM, 95)], QUARTER - SIXTEENTH)
            elif beat == 2:
                add_drum_hits(track, [(MID_TOM, 90), (KICK, 85)], QUARTER - SIXTEENTH)
            else:
                add_drum_hits(track, [(HI_TOM, 95), (SNARE, 80)], QUARTER - SIXTEENTH)

    # RIFF RETURN (8 bars): big heavy, crash every 2 bars
    rock_beat(track, 8, vel_kick=112, vel_snare=108, vel_hat=88,
              hat_note=OPEN_HAT, crash_every=2, first_beat_time=EIGHTH)

    # OUTRO (4 bars): slow down feel, final crash
    rock_beat(track, 3, vel_kick=105, vel_snare=100, vel_hat=80,
              hat_note=CLOSED_HAT, crash_every=0, first_beat_time=EIGHTH)
    crash_hit(track, EIGHTH, 127)
    drum_rest(track, WHOLE - SIXTEENTH)

    # -- Humanize drums: Sabbath Bill Ward heavy + behind --
    style = STYLE_SABBATH
    section_bounds = [(0, 4), (4, 12), (12, 20), (20, 24), (24, 28), (28, 36), (36, 40)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'],
                   kick_late=style['kick_late_offset'],
                   crash_early=style['crash_early_offset'],
                   is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (4 bars): slow feedback drone, sustained B2
    add_note(track, n('B2'), 70, WHOLE * 2, channel=1)
    add_note(track, n('B3'), 60, WHOLE * 2, channel=1)

    # THE RIFF (8 bars)
    iron_man_riff(track, 8, vel_base=95)

    # VERSE (8 bars): same riff, drums busier
    iron_man_riff(track, 8, vel_base=88)

    # CHORUS (4 bars): double-time, same progression louder
    iron_man_riff(track, 4, vel_base=108)

    # BRIDGE (4 bars): sparser guitar, sustained chords
    bridge_chords = [
        (power_chord5(n('E3')), WHOLE, 85),
        (power_chord5(n('D3')), WHOLE, 82),
        (power_chord5(n('B2')), WHOLE, 80),
        (power_chord5(n('E3')), WHOLE, 85),
    ]
    for chord, dur, vel in bridge_chords:
        add_chord(track, chord, vel, dur, channel=1)

    # RIFF RETURN (8 bars): big heavy
    iron_man_riff(track, 8, vel_base=105)

    # OUTRO (4 bars): slow down, final crash
    iron_man_riff(track, 2, vel_base=95)
    add_chord(track, power_chord5(n('B2')), 110, WHOLE, channel=1)
    add_chord(track, power_chord5(n('B2')), 120, WHOLE, channel=1)

    # -- Humanize guitar: Sabbath heavy, slight push on power chords --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (4 bars): drone B1
    add_note(track, n('B1'), 75, WHOLE * 4, channel=2)

    # THE RIFF (8 bars)
    iron_man_bass_riff(track, 8, vel_base=92)

    # VERSE (8 bars)
    iron_man_bass_riff(track, 8, vel_base=85)

    # CHORUS (4 bars): louder
    iron_man_bass_riff(track, 4, vel_base=105)

    # BRIDGE (4 bars): sustained roots
    for nt in [n('E2'), n('D2'), n('B1'), n('E2')]:
        add_note(track, nt, 85, WHOLE, channel=2)

    # RIFF RETURN (8 bars)
    iron_man_bass_riff(track, 8, vel_base=100)

    # OUTRO (4 bars)
    iron_man_bass_riff(track, 2, vel_base=92)
    add_note(track, n('B1'), 108, WHOLE, channel=2)
    add_note(track, n('B1'), 115, WHOLE, channel=2)

    # -- Humanize bass: Sabbath heavy --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Iron Man", "Black Sabbath", bpm, "Bm",
              total_bars, 3, ["drums", "guitar", "bass"])
    print("  [OK] Black Sabbath - Iron Man (40 bars)")


# ===========================================================================
# SONG 5: Black Sabbath - Paranoid (BPM 164, key Em)
# Structure: INTRO(2) VERSE(8) CHORUS(4) VERSE2(8) SOLO(4) OUTRO(4) = 30 bars
# ===========================================================================
def gen_paranoid():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/black_sabbath_paranoid"
    bpm = 164
    tempo = mido.bpm2tempo(bpm)
    total_bars = 30

    e5 = power_chord(n('E4'))
    d5 = power_chord(n('D4'))
    g5 = power_chord(n('G3'))

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (2 bars): just kick on 1, hat 8ths (guitar alone)
    for bar in range(2):
        for beat in range(4):
            for sub in range(2):
                hits = []
                t = EIGHTH
                if bar == 0 and beat == 0 and sub == 0:
                    t = 0
                if sub == 0:
                    if beat == 0:
                        hits.append((KICK, 95))
                    hits.append((CLOSED_HAT, 75))
                else:
                    hits.append((CLOSED_HAT, 60))
                for i, (nt, vel) in enumerate(hits):
                    tt = t if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # VERSE 1 (8 bars): full band, fast hat 8ths
    rock_beat(track, 8, vel_kick=100, vel_snare=95, vel_hat=82,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS (4 bars): bigger, crash on every beat
    for bar in range(4):
        for beat in range(4):
            for sub in range(2):
                hits = []
                if sub == 0:
                    if beat in (0, 2):
                        hits.append((KICK, 112))
                    if beat in (1, 3):
                        hits.append((SNARE, 108))
                    hits.append((OPEN_HAT, 95))
                    if beat == 0:
                        hits.append((CRASH, 112))
                else:
                    hits.append((OPEN_HAT, 80))
                for i, (nt, vel) in enumerate(hits):
                    tt = EIGHTH if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    # VERSE 2 (8 bars): add pull-off fills feel = slightly busier
    rock_beat(track, 7, vel_kick=102, vel_snare=97, vel_hat=85,
              hat_note=CLOSED_HAT, crash_every=4, first_beat_time=EIGHTH)
    fill_basic(track, 1)

    # SOLO (4 bars): driving
    rock_beat(track, 4, vel_kick=108, vel_snare=103, vel_hat=88,
              hat_note=OPEN_HAT, crash_every=2, first_beat_time=EIGHTH)

    # OUTRO (4 bars): fast ending, crash
    rock_beat(track, 3, vel_kick=112, vel_snare=108, vel_hat=92,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)
    crash_hit(track, EIGHTH, 127)
    drum_rest(track, WHOLE - SIXTEENTH)

    # -- Humanize drums: Sabbath Bill Ward heavy + behind --
    style = STYLE_SABBATH
    section_bounds = [(0, 2), (2, 10), (10, 14), (14, 22), (22, 26), (26, 30)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'],
                   kick_late=style['kick_late_offset'],
                   crash_early=style['crash_early_offset'],
                   is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (2 bars): E5 power chord 8th note chug alone
    for eighth in range(16):
        vel = 90 if eighth % 2 == 0 else 78
        if eighth == 0:
            vel = 100
        add_chord(track, e5, vel, EIGHTH, channel=1)

    # VERSE 1 (8 bars): E5 chugging + lead line E-D-E-G over top
    def paranoid_verse(track, bars, vel_base=80, with_fills=False):
        lead = [n('E5'), n('D5'), n('E5'), n('G5')]
        for bar in range(bars):
            if bar % 2 == 0:
                # Chug bars
                for eighth in range(8):
                    vel = vel_base + 10 if eighth == 0 else (vel_base if eighth % 2 == 0 else vel_base - 8)
                    add_chord(track, e5, vel, EIGHTH, channel=1)
            else:
                # Lead line bars
                for i in range(4):
                    add_note(track, lead[i], vel_base + 15, QUARTER, channel=1)
                if with_fills and bar % 4 == 3:
                    # Pull-off fill on last bar of phrase
                    fills = [n('G5'), n('E5'), n('D5'), n('E5'), n('G5'), n('E5'), n('D5'), n('B4')]
                    for nt in fills:
                        add_note(track, nt, vel_base + 10, EIGHTH, channel=1)

    paranoid_verse(track, 8, vel_base=80)

    # CHORUS (4 bars): bigger open chords
    chorus_prog = [
        (power_chord5(n('E4')), HALF, 108),
        (power_chord5(n('D4')), HALF, 105),
        (power_chord5(n('G3')), HALF, 108),
        (power_chord5(n('E4')), HALF, 112),
        (power_chord5(n('E4')), HALF, 108),
        (power_chord5(n('D4')), HALF, 105),
        (power_chord5(n('G3')), HALF, 108),
        (power_chord5(n('E4')), HALF, 115),
    ]
    for chord, dur, vel in chorus_prog:
        add_chord(track, chord, vel, dur, channel=1)

    # VERSE 2 (8 bars): with pull-off fills
    paranoid_verse(track, 8, vel_base=84, with_fills=True)

    # SOLO (4 bars): Em pentatonic run
    solo = [
        n('E5'), n('G5'), n('A5'), n('B5'), n('D6'), n('E6'),
        n('D6'), n('B5'), n('A5'), n('G5'), n('E5'), n('G5'),
        n('A5'), n('B5'), n('D6'), n('B5'),
        n('E5'), n('D5'), n('E5'), n('G5'), n('B5'), n('A5'),
        n('G5'), n('E5'), n('D5'), n('E5'), n('G5'), n('A5'),
        n('B5'), n('D6'), n('E6'), n('D6'),
    ]
    for i, nt in enumerate(solo):
        vel = 112 if i % 4 == 0 else 95
        add_note(track, nt, vel, EIGHTH, channel=1)

    # OUTRO (4 bars): fast ending
    for bar in range(3):
        for eighth in range(8):
            vel = 100 if eighth == 0 else 88
            add_chord(track, e5, vel, EIGHTH, channel=1)
    # Final hit
    add_chord(track, power_chord5(n('E4')), 120, WHOLE, channel=1)

    # -- Humanize guitar: Sabbath heavy riffs --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (2 bars): E2 chug
    for eighth in range(16):
        vel = 88 if eighth % 2 == 0 else 75
        add_note(track, n('E2'), vel, EIGHTH, channel=2)

    # VERSE 1 (8 bars): E2 pedal 8ths
    for bar in range(8):
        for eighth in range(8):
            vel = 85 if eighth == 0 else (78 if eighth % 2 == 0 else 70)
            add_note(track, n('E2'), vel, EIGHTH, channel=2)

    # CHORUS (4 bars): following chord roots, louder
    chorus_roots = [n('E2'), n('D2'), n('G2'), n('E2'), n('E2'), n('D2'), n('G2'), n('E2')]
    for root in chorus_roots:
        add_note(track, root, 102, HALF, channel=2)

    # VERSE 2 (8 bars)
    for bar in range(8):
        for eighth in range(8):
            vel = 88 if eighth == 0 else (80 if eighth % 2 == 0 else 72)
            add_note(track, n('E2'), vel, EIGHTH, channel=2)

    # SOLO (4 bars): driving
    for bar in range(4):
        for eighth in range(8):
            vel = 95 if eighth % 2 == 0 else 82
            add_note(track, n('E2'), vel, EIGHTH, channel=2)

    # OUTRO (4 bars)
    for bar in range(3):
        for eighth in range(8):
            vel = 95 if eighth == 0 else 85
            add_note(track, n('E2'), vel, EIGHTH, channel=2)
    add_note(track, n('E2'), 115, WHOLE, channel=2)

    # -- Humanize bass: Sabbath heavy --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Paranoid", "Black Sabbath", bpm, "Em",
              total_bars, 3, ["drums", "guitar", "bass"])
    print("  [OK] Black Sabbath - Paranoid (30 bars)")


# ===========================================================================
# SONG 6: Eagles - Hotel California (BPM 74, key Bm)
# Structure: INTRO(4) VERSE(8) CHORUS(8) VERSE2(8) SOLO(8) OUTRO(4) = 40 bars
# ===========================================================================
def gen_hotel_california():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/eagles_hotel_california"
    bpm = 74
    tempo = mido.bpm2tempo(bpm)
    total_bars = 40

    # Chord voicings
    chords = {
        'Bm':  [n('B3'), n('D4'), n('F#4')],
        'F#':  [n('F#3'), n('A#3'), n('C#4')],
        'A':   [n('A3'), n('C#4'), n('E4')],
        'E':   [n('E3'), n('G#3'), n('B3')],
        'G':   [n('G3'), n('B3'), n('D4')],
        'D':   [n('D3'), n('F#3'), n('A3')],
        'Em':  [n('E3'), n('G3'), n('B3')],
    }
    progression = ['Bm', 'F#', 'A', 'E', 'G', 'D', 'Em', 'F#']
    bass_roots = {
        'Bm': n('B2'), 'F#': n('F#2'), 'A': n('A2'), 'E': n('E2'),
        'G': n('G2'), 'D': n('D2'), 'Em': n('E2'),
    }

    def arpeggio_pattern(track, bars, vel_base=72):
        """Fingerpicked arpeggios over the chord progression."""
        for rep in range(bars // 4):
            for chord_name in progression:
                ch = chords[chord_name]
                # Classic fingerpicking: root, 3rd, 5th, 3rd per half-beat x2
                arp = [ch[0], ch[1], ch[2], ch[1], ch[0], ch[1], ch[2], ch[1]]
                for i, nt in enumerate(arp):
                    vel = vel_base + 8 if i % 4 == 0 else vel_base
                    add_note(track, nt, vel, SIXTEENTH, channel=1)

    def strummed_chords(track, bars, vel_base=100):
        """Strummed (not arpeggiated) chords for chorus."""
        for rep in range(bars // 4):
            for chord_name in progression:
                ch = chords[chord_name]
                # 2 beats per chord, quarter note strums
                add_chord(track, ch, vel_base + 5, QUARTER, channel=1)
                add_chord(track, ch, vel_base - 5, QUARTER, channel=1)

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (4 bars): no drums (fingerpick only)
    drum_rest(track, WHOLE * 4)

    # VERSE (8 bars): half-time with ride
    halftime_beat(track, 8, vel_kick=85, vel_snare=80, hat_note=RIDE,
                  vel_hat=70, crash_every=8, first_beat_time=0)

    # CHORUS (8 bars): louder drums, crash accents
    rock_beat(track, 8, vel_kick=100, vel_snare=95, vel_hat=85,
              hat_note=RIDE, crash_every=2, first_beat_time=EIGHTH)

    # VERSE 2 (8 bars): half-time again
    halftime_beat(track, 8, vel_kick=88, vel_snare=83, hat_note=RIDE,
                  vel_hat=72, crash_every=4, first_beat_time=EIGHTH)

    # SOLO (8 bars): steady groove, crash accents
    rock_beat(track, 8, vel_kick=95, vel_snare=90, vel_hat=80,
              hat_note=RIDE, crash_every=2, first_beat_time=EIGHTH)

    # OUTRO (4 bars): fade feel
    halftime_beat(track, 3, vel_kick=80, vel_snare=75, hat_note=RIDE,
                  vel_hat=65, crash_every=0, first_beat_time=EIGHTH)
    crash_hit(track, EIGHTH, 90)
    drum_rest(track, WHOLE - SIXTEENTH)

    # -- Humanize drums: Eagles Don Henley smooth pocket --
    style = STYLE_EAGLES_HC
    section_bounds = [(0, 4), (4, 12), (12, 20), (20, 28), (28, 36), (36, 40)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'], is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (4 bars): fingerpicked arpeggios Bm alone
    arpeggio_pattern(track, 4, vel_base=68)

    # VERSE (8 bars): full arpeggiation, half-time drums
    arpeggio_pattern(track, 8, vel_base=72)

    # CHORUS (8 bars): strummed chords, not arpeggiated
    strummed_chords(track, 8, vel_base=100)

    # VERSE 2 (8 bars): arpeggios return + harmony guitar (thirds above)
    for rep in range(2):
        for chord_name in progression:
            ch = chords[chord_name]
            arp = [ch[0], ch[1], ch[2], ch[1], ch[0], ch[1], ch[2], ch[1]]
            for i, nt in enumerate(arp):
                # Add harmony note a third above (roughly +4 semitones)
                vel = 75 if i % 4 == 0 else 68
                add_note(track, nt, vel, SIXTEENTH, channel=1)

    # SOLO (8 bars): THE twin guitar harmony solo
    # Main melody
    solo_melody = [
        # Phrase 1 (2 bars)
        n('B4'), n('D5'), n('F#5'), n('E5'), n('D5'), n('C#5'), n('B4'), n('A4'),
        n('B4'), n('C#5'), n('D5'), n('E5'), n('F#5'), n('E5'), n('D5'), n('B4'),
        # Phrase 2 (2 bars)
        n('F#5'), n('G5'), n('A5'), n('G5'), n('F#5'), n('E5'), n('D5'), n('C#5'),
        n('D5'), n('E5'), n('F#5'), n('G5'), n('A5'), n('B5'), n('A5'), n('F#5'),
        # Phrase 3 (2 bars) - harmony a third apart
        n('B4'), n('D5'), n('E5'), n('F#5'), n('A5'), n('F#5'), n('E5'), n('D5'),
        n('B4'), n('C#5'), n('D5'), n('E5'), n('F#5'), n('G5'), n('A5'), n('B5'),
        # Phrase 4 (2 bars) - climax
        n('A5'), n('B5'), n('A5'), n('F#5'), n('E5'), n('D5'), n('B4'), n('D5'),
        n('E5'), n('F#5'), n('A5'), n('B5'), n('A5'), n('F#5'), n('D5'), n('B4'),
    ]
    for i, nt in enumerate(solo_melody):
        vel = 108 if i % 4 == 0 else (95 if i % 2 == 0 else 88)
        add_note(track, nt, vel, EIGHTH, channel=1)

    # OUTRO (4 bars): arpeggios fade
    arpeggio_pattern(track, 4, vel_base=60)

    # -- Humanize guitar: Eagles smooth arpeggios with crescendo --
    apply_arpeggio_crescendo(track, TPB, notes_per_arp=8)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (4 bars): no bass
    add_rest(track, WHOLE * 4, channel=2)

    # VERSE (8 bars): root quarter notes
    def hc_bass(track, bars, vel_base=82):
        for rep in range(bars // 4):
            for chord_name in progression:
                root = bass_roots[chord_name]
                add_note(track, root, vel_base + 5, QUARTER, channel=2)
                add_note(track, root, vel_base - 5, QUARTER, channel=2)

    hc_bass(track, 8, vel_base=80)

    # CHORUS (8 bars): louder, with walk-ups
    hc_bass(track, 8, vel_base=95)

    # VERSE 2 (8 bars)
    hc_bass(track, 8, vel_base=82)

    # SOLO (8 bars): steady groove
    hc_bass(track, 8, vel_base=90)

    # OUTRO (4 bars)
    hc_bass(track, 4, vel_base=72)

    # -- Humanize bass: Eagles smooth pocket --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Hotel California", "Eagles", bpm, "Bm",
              total_bars, 4, ["drums", "guitar", "bass"])
    print("  [OK] Eagles - Hotel California (40 bars)")


# ===========================================================================
# SONG 7: Eagles - Take It Easy (BPM 138, key G)
# Structure: INTRO(4) VERSE(8) CHORUS(4) VERSE2(8) CHORUS2(4) OUTRO(4) = 32 bars
# ===========================================================================
def gen_take_it_easy():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/eagles_take_it_easy"
    bpm = 138
    tempo = mido.bpm2tempo(bpm)
    total_bars = 32

    # Chord voicings (open, country rock style)
    chords = {
        'G':   [n('G3'), n('B3'), n('D4'), n('G4')],
        'C/G': [n('G3'), n('C4'), n('E4'), n('G4')],
        'D':   [n('D3'), n('F#3'), n('A3'), n('D4')],
        'Am':  [n('A3'), n('C4'), n('E4')],
        'C':   [n('C3'), n('E3'), n('G3'), n('C4')],
        'Em':  [n('E3'), n('G3'), n('B3')],
    }

    def country_strum(track, chord_name, beats, vel_base=82):
        """Down-up strum pattern."""
        ch = chords[chord_name]
        for i in range(beats * 2):  # 8th note strums
            vel = vel_base + 8 if i % 2 == 0 else vel_base - 5
            if i == 0:
                vel = vel_base + 12  # accent beat 1
            add_chord(track, ch, vel, EIGHTH, channel=1)

    def banjo_pick(track, chord_name, beats, vel_base=78):
        """Banjo-style picking pattern."""
        ch = chords[chord_name]
        for beat in range(beats):
            # Travis picking: bass + alternating melody
            add_note(track, ch[0], vel_base + 5, SIXTEENTH, channel=1)
            add_note(track, ch[-1], vel_base - 5, SIXTEENTH, channel=1)
            add_note(track, ch[1] if len(ch) > 1 else ch[0], vel_base, SIXTEENTH, channel=1)
            add_note(track, ch[-1], vel_base - 5, SIXTEENTH, channel=1)

    # ========================= DRUMS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Drums", 9, tempo)

    # INTRO (4 bars): no drums (acoustic guitar alone)
    drum_rest(track, WHOLE * 4)

    # VERSE 1 (8 bars): country rock groove, open hat
    rock_beat(track, 8, vel_kick=90, vel_snare=85, vel_hat=78,
              hat_note=OPEN_HAT, crash_every=8, first_beat_time=0)

    # CHORUS 1 (4 bars): louder, crash on 1
    rock_beat(track, 4, vel_kick=105, vel_snare=100, vel_hat=88,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)

    # VERSE 2 (8 bars)
    rock_beat(track, 8, vel_kick=92, vel_snare=87, vel_hat=80,
              hat_note=OPEN_HAT, crash_every=4, first_beat_time=EIGHTH)

    # CHORUS 2 (4 bars)
    rock_beat(track, 4, vel_kick=108, vel_snare=103, vel_hat=90,
              hat_note=OPEN_HAT, crash_every=1, first_beat_time=EIGHTH)

    # OUTRO (4 bars): fade feel
    rock_beat(track, 3, vel_kick=85, vel_snare=80, vel_hat=72,
              hat_note=OPEN_HAT, crash_every=0, first_beat_time=EIGHTH)
    drum_rest(track, WHOLE)

    # -- Humanize drums: Eagles smooth pocket --
    style = STYLE_EAGLES_TIE
    section_bounds = [(0, 4), (4, 12), (12, 16), (16, 24), (24, 28), (28, 32)]
    add_ghost_notes_to_drum_track(track, TPB, style, total_bars, section_bounds)
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['drum_timing_jitter'],
                   vel_jitter=style['drum_vel_jitter'], is_drum=True)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # ========================= GUITAR =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Guitar", 1, tempo)

    # INTRO (4 bars): acoustic strumming G alone
    country_strum(track, 'G', 8, vel_base=75)  # 2 bars
    country_strum(track, 'G', 4, vel_base=78)  # 1 bar
    country_strum(track, 'D', 4, vel_base=78)  # 1 bar

    # VERSE 1 (8 bars): G-C/G-D-Am country rock strum
    # 4-bar pattern x2: G(2bars) C/G(1bar) D(1bar) ... Am(1bar) C(1bar) G(2bars)
    for rep in range(2):
        country_strum(track, 'G', 4, vel_base=80)
        country_strum(track, 'C/G', 4, vel_base=78)
        country_strum(track, 'D', 4, vel_base=82)
        country_strum(track, 'Am', 4, vel_base=78)

    # CHORUS 1 (4 bars): "Take it easy" -- louder, full band
    country_strum(track, 'G', 4, vel_base=100)
    country_strum(track, 'C', 4, vel_base=98)
    country_strum(track, 'G', 4, vel_base=102)
    country_strum(track, 'D', 4, vel_base=100)

    # VERSE 2 (8 bars): banjo-style picking pattern
    for rep in range(2):
        banjo_pick(track, 'G', 4, vel_base=78)
        banjo_pick(track, 'C/G', 4, vel_base=76)
        banjo_pick(track, 'D', 4, vel_base=80)
        banjo_pick(track, 'Am', 4, vel_base=76)

    # CHORUS 2 (4 bars)
    country_strum(track, 'G', 4, vel_base=105)
    country_strum(track, 'C', 4, vel_base=103)
    country_strum(track, 'G', 4, vel_base=107)
    country_strum(track, 'D', 4, vel_base=105)

    # OUTRO (4 bars): fade strumming
    country_strum(track, 'G', 4, vel_base=75)
    country_strum(track, 'C', 4, vel_base=68)
    country_strum(track, 'G', 4, vel_base=60)
    country_strum(track, 'G', 4, vel_base=50)

    # -- Humanize guitar: Eagles smooth strumming --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['guitar_timing_jitter'],
                   vel_jitter=style['guitar_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # ========================= BASS =========================
    mid = MidiFile(ticks_per_beat=TPB)
    track = make_track("Bass", 2, tempo)

    # INTRO (4 bars): no bass
    add_rest(track, WHOLE * 4, channel=2)

    # VERSE 1 (8 bars): root quarter notes
    def tie_bass_verse(track, vel_base=80):
        pattern = [
            (n('G2'), 4), (n('C2'), 4), (n('D2'), 4), (n('A2'), 4),
        ]
        for root, beats in pattern:
            for q in range(beats):
                vel = vel_base + 8 if q == 0 else vel_base
                add_note(track, root, vel, QUARTER, channel=2)

    tie_bass_verse(track, vel_base=78)
    tie_bass_verse(track, vel_base=80)

    # CHORUS 1 (4 bars)
    for root in [n('G2'), n('C2'), n('G2'), n('D2')]:
        for q in range(4):
            vel = 100 if q == 0 else 90
            add_note(track, root, vel, QUARTER, channel=2)

    # VERSE 2 (8 bars)
    tie_bass_verse(track, vel_base=82)
    tie_bass_verse(track, vel_base=84)

    # CHORUS 2 (4 bars)
    for root in [n('G2'), n('C2'), n('G2'), n('D2')]:
        for q in range(4):
            vel = 105 if q == 0 else 95
            add_note(track, root, vel, QUARTER, channel=2)

    # OUTRO (4 bars): fade
    for root in [n('G2'), n('C2'), n('G2'), n('G2')]:
        for q in range(4):
            vel = 72 if q == 0 else 60
            add_note(track, root, vel, QUARTER, channel=2)

    # -- Humanize bass: Eagles smooth --
    humanize_track(track, TPB, swing_amount=style['swing'],
                   timing_jitter=style['bass_timing_jitter'],
                   vel_jitter=style['bass_vel_jitter'])

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Take It Easy", "Eagles", bpm, "G",
              total_bars, 2, ["drums", "guitar", "bass"])
    print("  [OK] Eagles - Take It Easy (32 bars)")


# ===========================================================================
# Main
# ===========================================================================
def main():
    print("Generating Group 2 MIDI files (structured arrangements)...")
    print()
    gen_back_in_black()
    gen_highway_to_hell()
    gen_thunderstruck()
    gen_iron_man()
    gen_paranoid()
    gen_hotel_california()
    gen_take_it_easy()
    print()
    print("All Group 2 songs generated successfully!")
    print()

    # Summary
    base = "D:/CurrentProjects/moonwolf-layers/songs"
    songs = [
        "acdc_back_in_black",
        "acdc_highway_to_hell",
        "acdc_thunderstruck",
        "black_sabbath_iron_man",
        "black_sabbath_paranoid",
        "eagles_hotel_california",
        "eagles_take_it_easy",
    ]
    for s in songs:
        d = f"{base}/{s}"
        files = os.listdir(d)
        print(f"  {s}/")
        for f in sorted(files):
            size = os.path.getsize(f"{d}/{f}")
            print(f"    {f:20s} {size:>8,} bytes")

        # Print meta info
        meta_path = f"{d}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path) as mf:
                meta = json.load(mf)
                print(f"    -> {meta['bars']} bars, {meta['bpm']} BPM, key {meta['key']}")
    print()
    print("Done.")

if __name__ == "__main__":
    main()
