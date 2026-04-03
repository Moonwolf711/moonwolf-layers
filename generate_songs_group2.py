"""
Generate Group 2 MIDI files for moonwolf-layers.
Songs: AC/DC (Back in Black, Highway to Hell, Thunderstruck),
       Black Sabbath (Iron Man, Paranoid),
       Eagles (Hotel California, Take It Easy)
"""

import json
import os
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ticks_per_beat():
    return 480

def tempo_from_bpm(bpm):
    return mido.bpm2tempo(bpm)

def note_len(duration_beats):
    """Convert beat duration to ticks."""
    return int(ticks_per_beat() * duration_beats)

WHOLE = note_len(4.0)
HALF = note_len(2.0)
QUARTER = note_len(1.0)
EIGHTH = note_len(0.5)
SIXTEENTH = note_len(0.25)
DOTTED_QUARTER = note_len(1.5)
DOTTED_EIGHTH = note_len(0.75)

# GM Drum map
KICK = 36
SNARE = 38
CLOSED_HAT = 42
OPEN_HAT = 46
CRASH = 49
RIDE = 51
LOW_TOM = 45
HI_TOM = 48

def make_track(name, channel, tempo_val=None):
    """Create a new MidiTrack with name and optional tempo."""
    track = MidiTrack()
    track.append(MetaMessage('track_name', name=name, time=0))
    if tempo_val is not None:
        track.append(MetaMessage('set_tempo', tempo=tempo_val, time=0))
    return track

def add_note(track, note, velocity, duration, channel=0, delay=0):
    """Add a note_on / note_off pair."""
    track.append(Message('note_on', note=note, velocity=velocity, channel=channel, time=delay))
    track.append(Message('note_off', note=note, velocity=0, channel=channel, time=duration))

def add_rest(track, duration, channel=0):
    """Add silence by inserting a zero-velocity note_on/off or just spacing."""
    track.append(Message('note_on', note=0, velocity=0, channel=channel, time=duration))
    track.append(Message('note_off', note=0, velocity=0, channel=channel, time=0))

def add_drum_hit(track, note, velocity, time_offset=0):
    """Single drum hit (note_on + note_off with short gap)."""
    track.append(Message('note_on', note=note, velocity=velocity, channel=9, time=time_offset))
    track.append(Message('note_off', note=note, velocity=0, channel=9, time=SIXTEENTH))

def add_drum_simultaneous(track, notes_vels, time_offset=0):
    """Multiple drum hits at same time. notes_vels = [(note, vel), ...]"""
    for i, (note, vel) in enumerate(notes_vels):
        t = time_offset if i == 0 else 0
        track.append(Message('note_on', note=note, velocity=vel, channel=9, time=t))
    # Turn them all off after a sixteenth
    for i, (note, vel) in enumerate(notes_vels):
        t = SIXTEENTH if i == 0 else 0
        track.append(Message('note_off', note=note, velocity=0, channel=9, time=t))

def add_chord(track, notes, velocity, duration, channel=0, delay=0):
    """Add a chord (multiple notes simultaneously)."""
    for i, n in enumerate(notes):
        t = delay if i == 0 else 0
        track.append(Message('note_on', note=n, velocity=velocity, channel=channel, time=t))
    for i, n in enumerate(notes):
        t = duration if i == 0 else 0
        track.append(Message('note_off', note=n, velocity=0, channel=channel, time=t))

def save_midi(mid, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mid.save(path)

def save_meta(path, title, artist, bpm, key, bars, difficulty, instruments):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    meta = {
        "title": title,
        "artist": artist,
        "bpm": bpm,
        "key": key,
        "bars": bars,
        "difficulty": difficulty,
        "instruments": instruments
    }
    with open(path, 'w') as f:
        json.dump(meta, f, indent=2)

def combine_tracks(tracks_files, output_path, tpb=480):
    """Combine separate MIDI files into one multi-track file."""
    combined = MidiFile(ticks_per_beat=tpb)
    for fpath in tracks_files:
        m = MidiFile(fpath)
        for track in m.tracks:
            combined.tracks.append(track)
    save_midi(combined, output_path)

# ---------------------------------------------------------------------------
# Note name to MIDI number
# ---------------------------------------------------------------------------
NOTE_MAP = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

def n(name_octave):
    """Convert note name like 'E4' or 'F#2' to MIDI number."""
    if name_octave[-1].isdigit():
        octave = int(name_octave[-1])
        note_name = name_octave[:-1]
    else:
        raise ValueError(f"Bad note: {name_octave}")
    return NOTE_MAP[note_name] + (octave + 1) * 12

# Power chord helper: root + fifth
def power_chord(root_note):
    return [root_note, root_note + 7]

# ---------------------------------------------------------------------------
# SONG 1: AC/DC - Back in Black (BPM 92, key E, 4/4)
# ---------------------------------------------------------------------------
def gen_back_in_black():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/acdc_back_in_black"
    bpm = 92
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    # 16 bars: kick on 1+3, snare on 2+4, open hat 8ths
    for bar in range(bars):
        for beat in range(4):
            # Each beat has 2 eighth notes
            for sub in range(2):
                hits = []
                if sub == 0:
                    # On the beat
                    if beat in (0, 2):
                        hits.append((KICK, 100))
                    if beat in (1, 3):
                        hits.append((SNARE, 100))
                    hits.append((OPEN_HAT, 85))
                else:
                    # Off-beat eighth
                    hits.append((OPEN_HAT, 75))
                if hits:
                    first_time = EIGHTH if not (bar == 0 and beat == 0 and sub == 0) else 0
                    for i, (nt, vel) in enumerate(hits):
                        t = first_time if i == 0 else 0
                        track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=t))
                    for i, (nt, vel) in enumerate(hits):
                        t = 0 if i > 0 else 0
                        track.append(Message('note_off', note=nt, velocity=0, channel=9, time=t))
    # Fix: need proper timing. Let me redo drums more carefully.
    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # The riff: E5-D5-A power chord pattern
    # Pattern per 2 bars: E5 E5 D5 D5 | A5 A5 D5 E5  (eighth notes rhythm)
    e5 = power_chord(n('E4'))   # E power chord (guitar range)
    d5 = power_chord(n('D4'))
    a5 = power_chord(n('A3'))

    riff_pattern = [
        (e5, EIGHTH), (e5, EIGHTH), (d5, EIGHTH), (d5, EIGHTH),
        (e5, EIGHTH), (e5, EIGHTH), (d5, EIGHTH), (d5, EIGHTH),
        (a5, EIGHTH), (a5, EIGHTH), (d5, EIGHTH), (d5, EIGHTH),
        (e5, EIGHTH), (e5, EIGHTH), (e5, EIGHTH), (e5, EIGHTH),
    ]  # 2 bars = 16 eighths

    for rep in range(bars // 2):
        for i, (chord, dur) in enumerate(riff_pattern):
            vel = 95 if i % 2 == 0 else 85
            delay = 0 if (rep == 0 and i == 0) else 0
            if i > 0 or rep > 0:
                # Add spacing from previous note-off
                pass
            add_chord(track, chord, vel, dur, channel=1, delay=0 if (rep == 0 and i == 0) else 0)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # Bass follows guitar roots: E2-D2-A1
    bass_pattern = [
        (n('E2'), EIGHTH), (n('E2'), EIGHTH), (n('D2'), EIGHTH), (n('D2'), EIGHTH),
        (n('E2'), EIGHTH), (n('E2'), EIGHTH), (n('D2'), EIGHTH), (n('D2'), EIGHTH),
        (n('A1'), EIGHTH), (n('A1'), EIGHTH), (n('D2'), EIGHTH), (n('D2'), EIGHTH),
        (n('E2'), EIGHTH), (n('E2'), EIGHTH), (n('E2'), EIGHTH), (n('E2'), EIGHTH),
    ]
    for rep in range(bars // 2):
        for i, (note, dur) in enumerate(bass_pattern):
            vel = 90 if i % 2 == 0 else 80
            add_note(track, note, vel, dur, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    # Combine
    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Back in Black", "AC/DC", bpm, "E", bars, 3,
              ["drums", "guitar", "bass"])
    print("  [OK] AC/DC - Back in Black")

# ---------------------------------------------------------------------------
# SONG 2: AC/DC - Highway to Hell (BPM 116, key A, 4/4)
# ---------------------------------------------------------------------------
def gen_highway_to_hell():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/acdc_highway_to_hell"
    bpm = 116
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    for bar in range(bars):
        for beat in range(4):
            for sub in range(2):
                hits = []
                time_offset = EIGHTH
                if bar == 0 and beat == 0 and sub == 0:
                    time_offset = 0
                if sub == 0:
                    if beat in (0, 2):
                        hits.append((KICK, 100))
                    if beat in (1, 3):
                        hits.append((SNARE, 95))
                    hits.append((CLOSED_HAT, 80))
                    # Crash on beat 1 every 4 bars
                    if beat == 0 and bar % 4 == 0:
                        hits.append((CRASH, 100))
                else:
                    hits.append((CLOSED_HAT, 70))

                for i, (nt, vel) in enumerate(hits):
                    t = time_offset if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=t))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # A5 - D/F# - G5 - D/F# chord progression
    a5 = power_chord(n('A3'))
    d_fsharp = [n('F#3'), n('A3'), n('D4')]  # D/F# voicing
    g5 = power_chord(n('G3'))

    # 4-bar progression: A5 (1 bar) - D/F# (1 bar) - G5 (1 bar) - D/F# (1 bar)
    progression = [a5, d_fsharp, g5, d_fsharp]

    for rep in range(bars // 4):
        for chord in progression:
            # Palm-muted 8th note pattern per bar
            for eighth in range(8):
                vel = 90 if eighth % 2 == 0 else 75  # accent downbeats
                add_chord(track, chord, vel, EIGHTH, channel=1)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # A2 - D2 - G2 - D2 quarter notes
    bass_prog = [n('A2'), n('D2'), n('G2'), n('D2')]
    for rep in range(bars // 4):
        for root in bass_prog:
            for q in range(4):
                vel = 95 if q == 0 else 85
                add_note(track, root, vel, QUARTER, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Highway to Hell", "AC/DC", bpm, "A", bars, 3,
              ["drums", "guitar", "bass"])
    print("  [OK] AC/DC - Highway to Hell")

# ---------------------------------------------------------------------------
# SONG 3: AC/DC - Thunderstruck (BPM 134, key B, 4/4)
# ---------------------------------------------------------------------------
def gen_thunderstruck():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/acdc_thunderstruck"
    bpm = 134
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    # Bars 1-4: just hi-hat 16ths (the intro)
    for bar in range(4):
        for sixteenth in range(16):
            vel = 90 if sixteenth % 4 == 0 else 70
            t = 0 if (bar == 0 and sixteenth == 0) else SIXTEENTH
            track.append(Message('note_on', note=CLOSED_HAT, velocity=vel, channel=9, time=t))
            track.append(Message('note_off', note=CLOSED_HAT, velocity=0, channel=9, time=0))

    # Bars 5-16: full kit
    for bar in range(4, bars):
        for beat in range(4):
            for sub in range(4):  # 16th note subdivisions
                hits = []
                if sub == 0:
                    if beat in (0, 2):
                        hits.append((KICK, 105))
                    if beat in (1, 3):
                        hits.append((SNARE, 100))
                    hits.append((CLOSED_HAT, 85))
                    if beat == 0 and bar % 4 == 0:
                        hits.append((CRASH, 105))
                elif sub == 2:
                    hits.append((CLOSED_HAT, 75))
                    if beat in (0, 2):
                        hits.append((KICK, 85))  # double kick pattern
                else:
                    hits.append((CLOSED_HAT, 65))

                for i, (nt, vel) in enumerate(hits):
                    t = SIXTEENTH if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=t))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # THE legendary hammer-on riff: rapid 16th notes
    # B4-E4-B4-A4-B4-G#4-A4-E4 repeating pattern
    riff_notes = [n('B4'), n('E4'), n('B4'), n('A4'), n('B4'), n('G#4'), n('A4'), n('E4')]

    # 16 bars of the riff pattern in 16th notes
    total_sixteenths = bars * 16
    note_idx = 0
    for i in range(total_sixteenths):
        note_val = riff_notes[note_idx % len(riff_notes)]
        vel = 95 if i % 4 == 0 else 80
        # Slight accent on the B notes
        if note_val == n('B4'):
            vel = min(vel + 10, 110)
        add_note(track, note_val, vel, SIXTEENTH, channel=1)
        note_idx += 1

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # Bars 1-4: silence (bass enters with drums)
    rest_ticks = 4 * 4 * QUARTER
    track.append(Message('note_on', note=0, velocity=0, channel=2, time=rest_ticks))
    track.append(Message('note_off', note=0, velocity=0, channel=2, time=0))

    # Bars 5-16: B2 pedal tone, 8th note pumping
    for bar in range(4, bars):
        for eighth in range(8):
            vel = 95 if eighth % 2 == 0 else 80
            add_note(track, n('B2'), vel, EIGHTH, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Thunderstruck", "AC/DC", bpm, "B", bars, 4,
              ["drums", "guitar", "bass"])
    print("  [OK] AC/DC - Thunderstruck")

# ---------------------------------------------------------------------------
# SONG 4: Black Sabbath - Iron Man (BPM 76, key Bm, 4/4)
# ---------------------------------------------------------------------------
def gen_iron_man():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/black_sabbath_iron_man"
    bpm = 76
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    # Heavy, slow. Kick pattern with snare on 2+4, crash accents on riff hits
    for bar in range(bars):
        for beat in range(4):
            hits = []
            if beat == 0:
                hits.append((KICK, 110))
                if bar % 2 == 0:
                    hits.append((CRASH, 100))
                hits.append((CLOSED_HAT, 80))
            elif beat == 1:
                hits.append((SNARE, 100))
                hits.append((CLOSED_HAT, 80))
            elif beat == 2:
                hits.append((KICK, 100))
                hits.append((CLOSED_HAT, 80))
            elif beat == 3:
                hits.append((SNARE, 95))
                hits.append((CLOSED_HAT, 80))

            t = 0 if (bar == 0 and beat == 0) else QUARTER
            for i, (nt, vel) in enumerate(hits):
                tt = t if i == 0 else 0
                track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
            for i, (nt, vel) in enumerate(hits):
                track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # THE RIFF: B2 B2 | D3 D3 | E3 E3 (bend) | E3 | G3 F#3 G3 F#3 | D3 E3
    # Slow power chord stabs. Each note roughly a quarter or eighth.
    # The actual riff rhythm: da da | da da | daaa | da | da-da da-da | da da
    # Simplified but recognizable pattern per 2 bars:
    riff = [
        # Bar 1: B-B-D-D
        (power_chord(n('B2')), QUARTER, 100),
        (power_chord(n('B2')), QUARTER, 95),
        (power_chord(n('D3')), QUARTER, 100),
        (power_chord(n('D3')), QUARTER, 95),
        # Bar 2: E-E-G-F#-G-F#-D-E
        (power_chord(n('E3')), QUARTER, 105),  # the bend note - held
        (power_chord(n('E3')), QUARTER, 100),
        (power_chord(n('G3')), EIGHTH, 95),
        (power_chord(n('F#3')), EIGHTH, 90),
        (power_chord(n('G3')), EIGHTH, 95),
        (power_chord(n('F#3')), EIGHTH, 90),
        (power_chord(n('D3')), EIGHTH, 95),
        (power_chord(n('E3')), EIGHTH + QUARTER, 100),  # held slightly longer
    ]

    for rep in range(bars // 2):
        for chord, dur, vel in riff:
            add_chord(track, chord, vel, dur, channel=1)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # Follows guitar one octave down
    bass_riff = [
        (n('B1'), QUARTER, 100),
        (n('B1'), QUARTER, 95),
        (n('D2'), QUARTER, 100),
        (n('D2'), QUARTER, 95),
        (n('E2'), QUARTER, 105),
        (n('E2'), QUARTER, 100),
        (n('G2'), EIGHTH, 95),
        (n('F#2'), EIGHTH, 90),
        (n('G2'), EIGHTH, 95),
        (n('F#2'), EIGHTH, 90),
        (n('D2'), EIGHTH, 95),
        (n('E2'), EIGHTH + QUARTER, 100),
    ]

    for rep in range(bars // 2):
        for note_val, dur, vel in bass_riff:
            add_note(track, note_val, vel, dur, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Iron Man", "Black Sabbath", bpm, "Bm", bars, 3,
              ["drums", "guitar", "bass"])
    print("  [OK] Black Sabbath - Iron Man")

# ---------------------------------------------------------------------------
# SONG 5: Black Sabbath - Paranoid (BPM 164, key Em, 4/4)
# ---------------------------------------------------------------------------
def gen_paranoid():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/black_sabbath_paranoid"
    bpm = 164
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    # Fast and steady: kick 1+3, snare 2+4, hat 8ths
    for bar in range(bars):
        for beat in range(4):
            for sub in range(2):
                hits = []
                t = EIGHTH
                if bar == 0 and beat == 0 and sub == 0:
                    t = 0
                if sub == 0:
                    if beat in (0, 2):
                        hits.append((KICK, 105))
                    if beat in (1, 3):
                        hits.append((SNARE, 100))
                    hits.append((CLOSED_HAT, 85))
                else:
                    hits.append((CLOSED_HAT, 75))

                for i, (nt, vel) in enumerate(hits):
                    tt = t if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # E5 power chord chug with lead line
    e5 = power_chord(n('E4'))

    # Pattern per 4 bars:
    # Bars 1-2: E5 eighth note chug (16 eighths)
    # Bars 3-4: Lead line E4-D4-E4-G4-E4 with chug underneath
    lead_line = [n('E5'), n('D5'), n('E5'), n('G5'), n('E5'), n('D5'), n('E5'), n('G5'),
                 n('E5'), n('D5'), n('E5'), n('G5'), n('E5'), n('D5'), n('E5'), n('E5')]

    for rep in range(bars // 4):
        # 2 bars of E5 chug
        for eighth in range(16):
            vel = 95 if eighth % 2 == 0 else 82
            add_chord(track, e5, vel, EIGHTH, channel=1)
        # 2 bars of lead line
        for i, note_val in enumerate(lead_line):
            vel = 100 if i % 4 == 0 else 85
            add_note(track, note_val, vel, EIGHTH, channel=1)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # E2 eighth note pedal
    for bar in range(bars):
        for eighth in range(8):
            vel = 95 if eighth % 2 == 0 else 80
            add_note(track, n('E2'), vel, EIGHTH, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Paranoid", "Black Sabbath", bpm, "Em", bars, 3,
              ["drums", "guitar", "bass"])
    print("  [OK] Black Sabbath - Paranoid")

# ---------------------------------------------------------------------------
# SONG 6: Eagles - Hotel California (BPM 74, key Bm, 4/4)
# ---------------------------------------------------------------------------
def gen_hotel_california():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/eagles_hotel_california"
    bpm = 74
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    # Half-time feel: kick on 1, snare on 3, ride pattern
    for bar in range(bars):
        for beat in range(4):
            for sub in range(2):  # 8th subdivisions
                hits = []
                t = EIGHTH
                if bar == 0 and beat == 0 and sub == 0:
                    t = 0
                if sub == 0:
                    if beat == 0:
                        hits.append((KICK, 95))
                    if beat == 2:
                        hits.append((SNARE, 90))
                        hits.append((KICK, 75))
                    hits.append((RIDE, 75))
                else:
                    hits.append((RIDE, 60))

                for i, (nt, vel) in enumerate(hits):
                    tt = t if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # Arpeggiated chord progression: Bm - F# - A - E - G - D - Em - F#
    # Each chord gets 2 beats (half bar), so full progression = 4 bars
    chords = {
        'Bm': [n('B3'), n('D4'), n('F#4')],
        'F#': [n('F#3'), n('A#3'), n('C#4')],
        'A':  [n('A3'), n('C#4'), n('E4')],
        'E':  [n('E3'), n('G#3'), n('B3')],
        'G':  [n('G3'), n('B3'), n('D4')],
        'D':  [n('D3'), n('F#3'), n('A3')],
        'Em': [n('E3'), n('G3'), n('B3')],
    }
    progression = ['Bm', 'F#', 'A', 'E', 'G', 'D', 'Em', 'F#']

    # Classic fingerpicking: each chord arpeggiated over 2 beats
    # Pattern: root, 3rd, 5th, 3rd (each a sixteenth) repeated
    for rep in range(bars // 4):
        for chord_name in progression:
            ch = chords[chord_name]
            # Arpeggio pattern over 2 beats = 8 sixteenths
            arp_pattern = [ch[0], ch[1], ch[2], ch[1], ch[0], ch[1], ch[2], ch[1]]
            for i, note_val in enumerate(arp_pattern):
                vel = 80 if i % 4 == 0 else 65
                add_note(track, note_val, vel, SIXTEENTH, channel=1)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # Root notes: B2-F#2-A2-E2-G2-D2-E2-F#2 quarter notes
    bass_roots = [n('B2'), n('F#2'), n('A2'), n('E2'), n('G2'), n('D2'), n('E2'), n('F#2')]
    for rep in range(bars // 4):
        for root in bass_roots:
            # Each chord gets 2 beats
            add_note(track, root, 85, QUARTER, channel=2)
            add_note(track, root, 75, QUARTER, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Hotel California", "Eagles", bpm, "Bm", bars, 4,
              ["drums", "guitar", "bass"])
    print("  [OK] Eagles - Hotel California")

# ---------------------------------------------------------------------------
# SONG 7: Eagles - Take It Easy (BPM 138, key G, 4/4)
# ---------------------------------------------------------------------------
def gen_take_it_easy():
    song_dir = "D:/CurrentProjects/moonwolf-layers/songs/eagles_take_it_easy"
    bpm = 138
    tempo = tempo_from_bpm(bpm)
    bars = 16

    # --- DRUMS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Drums", 9, tempo)
    # Country rock: kick on 1, snare on 2+4, open hat 8ths with accent
    for bar in range(bars):
        for beat in range(4):
            for sub in range(2):
                hits = []
                t = EIGHTH
                if bar == 0 and beat == 0 and sub == 0:
                    t = 0
                if sub == 0:
                    if beat == 0:
                        hits.append((KICK, 100))
                    if beat in (1, 3):
                        hits.append((SNARE, 95))
                    if beat == 2:
                        hits.append((KICK, 90))
                    hits.append((OPEN_HAT, 85 if beat in (0, 2) else 75))
                else:
                    hits.append((OPEN_HAT, 65))

                for i, (nt, vel) in enumerate(hits):
                    tt = t if i == 0 else 0
                    track.append(Message('note_on', note=nt, velocity=vel, channel=9, time=tt))
                for i, (nt, vel) in enumerate(hits):
                    track.append(Message('note_off', note=nt, velocity=0, channel=9, time=0))

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/drums.mid")

    # --- GUITAR ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Guitar", 1, tempo)
    # G - C/G - D - Am - C - G strumming, 8th note down-up
    chords = {
        'G':   [n('G3'), n('B3'), n('D4'), n('G4')],
        'C/G': [n('G3'), n('C4'), n('E4'), n('G4')],
        'D':   [n('D3'), n('F#3'), n('A3'), n('D4')],
        'Am':  [n('A3'), n('C4'), n('E4')],
        'C':   [n('C3'), n('E3'), n('G3'), n('C4')],
    }
    # 6 chords over ~4 bars: G(1bar) C/G(1bar) D(1bar) Am(half) C(half) G(1bar) = 4 bars
    # Adjusted: each chord = 2/3 bar ≈ let's do 8 beats per 4-bar cycle
    # Simpler: G(8 eighths) - C/G(8) - D(8) - Am(4) - C(4) - G(8) = 40 eighths = 5 bars
    # Let's make it 4 bars: G(8) C/G(4) D(4) Am(4) C(4) G(8) = 32 = 4 bars
    bar_pattern = [
        ('G', 8), ('C/G', 4), ('D', 4), ('Am', 4), ('C', 4), ('G', 8),
    ]  # 32 eighths = 4 bars

    for rep in range(bars // 4):
        for chord_name, count in bar_pattern:
            ch = chords[chord_name]
            for i in range(count):
                vel = 90 if i % 2 == 0 else 75  # down-up dynamic
                add_chord(track, ch, vel, EIGHTH, channel=1)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/guitar.mid")

    # --- BASS ---
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    track = make_track("Bass", 2, tempo)
    # Root quarter notes following changes
    bass_pattern = [
        (n('G2'), 4), (n('C2'), 2), (n('D2'), 2), (n('A2'), 2), (n('C2'), 2), (n('G2'), 4),
    ]  # 16 quarters = 4 bars

    for rep in range(bars // 4):
        for root, count in bass_pattern:
            for q in range(count):
                vel = 90 if q == 0 else 80
                add_note(track, root, vel, QUARTER, channel=2)

    mid.tracks.append(track)
    save_midi(mid, f"{song_dir}/bass.mid")

    combine_tracks(
        [f"{song_dir}/drums.mid", f"{song_dir}/guitar.mid", f"{song_dir}/bass.mid"],
        f"{song_dir}/full.mid"
    )
    save_meta(f"{song_dir}/meta.json", "Take It Easy", "Eagles", bpm, "G", bars, 2,
              ["drums", "guitar", "bass"])
    print("  [OK] Eagles - Take It Easy")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Generating Group 2 MIDI files...")
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
    print()
    print("Done.")

if __name__ == "__main__":
    main()
