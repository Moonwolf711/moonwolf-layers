"""
generate_songs_group3.py — Santana + Muse MIDI generation
Generates multi-track MIDI files for:
  1. Santana - Black Magic Woman (BPM 124, Dm, 4/4)
  2. Santana - Smooth (BPM 116, Am, 4/4)
  3. Santana - Evil Ways (BPM 124, Gm, 4/4)
  4. Muse - Hysteria (BPM 94, Am, 4/4)
  5. Muse - Supermassive Black Hole (BPM 120, Am, 4/4)
  6. Muse - Knights of Cydonia (BPM 138, Em, 6/8 -> 4/4)
"""

import os
import json
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_DIR = os.path.join(BASE_DIR, "songs")

# GM Drum Map
KICK = 36
SNARE = 38
SIDE_STICK = 37
CLOSED_HAT = 42
OPEN_HAT = 46
RIDE = 51
RIDE_BELL = 53
CRASH = 49
HIGH_TOM = 50
MID_TOM = 47
LOW_TOM = 45
CONGA_HIGH = 62
CONGA_LOW = 63
CONGA_MUTE = 64
COWBELL = 56
TIMBALE_HIGH = 65
TIMBALE_LOW = 66

# Channel constants
CH_KEYS = 0
CH_GUITAR = 1
CH_BASS = 2
CH_DRUMS = 9  # GM drum channel


def ticks_per_beat(mid):
    return mid.ticks_per_beat


def t(mid, fraction):
    """Convert a fraction of a beat to ticks. e.g. t(mid, 1) = quarter, t(mid, 0.5) = 8th."""
    return int(mid.ticks_per_beat * fraction)


def add_note(track, note, vel, start_tick, duration_ticks, channel=0):
    """Append a note-on/off pair. start_tick is absolute; we convert to delta internally."""
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


# ========================================================================
# 1. SANTANA - BLACK MAGIC WOMAN (BPM 124, Dm, 4/4, 16 bars)
# ========================================================================
def gen_black_magic_woman():
    bpm = 124
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "black_magic_woman")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    bars = 16

    # --- DRUMS: Latin rock groove ---
    # Kick on 1 and "and of 2", snare on 4, ride bell steady, conga pattern
    drums = []
    for bar in range(bars):
        base = bar * 4 * ppq
        # Kick on beat 1
        add_note(drums, KICK, 110, base, t(mid, 0.25), CH_DRUMS)
        # Kick on "and of 2" (beat 2.5)
        add_note(drums, KICK, 100, base + t(mid, 2.5), t(mid, 0.25), CH_DRUMS)
        # Snare on beat 4
        add_note(drums, SNARE, 105, base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Ride bell on every beat
        for beat in range(4):
            add_note(drums, RIDE_BELL, 85, base + t(mid, beat), t(mid, 0.25), CH_DRUMS)
        # Ride bell on upbeats too
        for beat in range(4):
            add_note(drums, RIDE_BELL, 65, base + t(mid, beat + 0.5), t(mid, 0.25), CH_DRUMS)
        # Conga-style tom pattern: syncopated on "and" of 1, beat 2, "and" of 3
        add_note(drums, CONGA_HIGH, 80, base + t(mid, 0.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_LOW, 75, base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_MUTE, 70, base + t(mid, 1.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_HIGH, 80, base + t(mid, 2.5), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_LOW, 70, base + t(mid, 3.5), t(mid, 0.25), CH_DRUMS)

    # --- GUITAR: Dm pentatonic lead - the slinky blues-latin riff ---
    # D4(62) F4(65) G4(67) A4(69) C5(72) - signature phrases
    guitar = []
    # 4-bar riff pattern repeated 4x
    riff_notes = [
        # Bar 1: D-F-G-A ascending slinky run
        (0.0, 62, 90, 0.75),   # D4 dotted 8th
        (0.75, 65, 85, 0.5),   # F4
        (1.25, 67, 88, 0.5),   # G4
        (1.75, 69, 92, 1.0),   # A4 sustained
        (3.0, 72, 85, 1.0),    # C5 sustained
        # Bar 2: descending with bends (grace notes)
        (4.0, 72, 88, 0.5),    # C5
        (4.5, 69, 85, 0.5),    # A4
        (5.0, 67, 90, 1.0),    # G4 sustained bend
        (6.0, 65, 80, 0.75),   # F4
        (6.75, 62, 85, 1.25),  # D4 sustained
        # Bar 3: rhythmic staccato hits
        (8.0, 62, 95, 0.25),   # D4 staccato
        (8.5, 65, 90, 0.25),   # F4 staccato
        (9.0, 67, 92, 0.25),   # G4 staccato
        (9.5, 69, 88, 0.5),    # A4
        (10.0, 72, 95, 0.75),  # C5
        (10.75, 69, 85, 0.5),  # A4
        (11.25, 67, 80, 0.75), # G4
        # Bar 4: bluesy resolution to D
        (12.0, 65, 88, 0.5),   # F4
        (12.5, 63, 82, 0.5),   # Eb4 blue note
        (13.0, 62, 90, 1.5),   # D4 sustained
        (14.5, 60, 75, 0.5),   # C4 passing
        (15.0, 62, 95, 1.0),   # D4 resolve
    ]
    for rep in range(4):
        offset = rep * 4 * 4 * ppq  # 4 bars per repetition
        for beat, note, vel, dur in riff_notes:
            add_note(guitar, note, vel, offset + t(mid, beat), t(mid, dur), CH_GUITAR)

    # --- BASS: Latin walking bass D2-F2-G2-A2, syncopated 8ths ---
    bass = []
    # D2=38, F2=41, G2=43, A2=45, C3=48, Bb2=46
    bass_pattern = [
        # Bar 1: D root with latin syncopation
        (0.0, 38, 100, 0.5),    # D2
        (0.5, 38, 75, 0.25),    # D2 ghost
        (1.0, 41, 95, 0.5),     # F2
        (1.5, 43, 80, 0.5),     # G2
        (2.0, 45, 90, 0.5),     # A2
        (2.5, 43, 75, 0.5),     # G2
        (3.0, 41, 85, 0.5),     # F2
        (3.5, 38, 80, 0.5),     # D2
        # Bar 2: walking up with chromatic approach
        (4.0, 38, 100, 0.5),    # D2
        (4.5, 40, 80, 0.5),     # E2
        (5.0, 41, 95, 0.5),     # F2
        (5.5, 42, 75, 0.25),    # F#2 chromatic
        (6.0, 43, 90, 0.5),     # G2
        (6.5, 45, 80, 0.5),     # A2
        (7.0, 46, 85, 0.5),     # Bb2
        (7.5, 45, 80, 0.5),     # A2
    ]
    for bar_pair in range(8):  # 8 repetitions of 2-bar pattern = 16 bars
        offset = bar_pair * 2 * 4 * ppq
        for beat, note, vel, dur in bass_pattern:
            add_note(bass, note, vel, offset + t(mid, beat), t(mid, dur), CH_BASS)

    # Save
    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Black Magic Woman", "Santana", bpm, "Dm", bars, 3,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Black Magic Woman")


# ========================================================================
# 2. SANTANA - SMOOTH (BPM 116, Am, 4/4, 16 bars)
# ========================================================================
def gen_smooth():
    bpm = 116
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "smooth")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    bars = 16

    # --- DRUMS: Pop-latin groove ---
    # Kick on 1, "and of 2", 3. Snare on 2+4. Hat 16ths.
    drums = []
    for bar in range(bars):
        base = bar * 4 * ppq
        # Kick pattern
        add_note(drums, KICK, 110, base, t(mid, 0.25), CH_DRUMS)                    # beat 1
        add_note(drums, KICK, 95, base + t(mid, 1.5), t(mid, 0.25), CH_DRUMS)       # and of 2
        add_note(drums, KICK, 100, base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)      # beat 3
        # Snare on 2 and 4
        add_note(drums, SNARE, 105, base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, 105, base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Hi-hat 16ths
        for i in range(16):
            vel = 75 if i % 4 == 0 else (60 if i % 2 == 0 else 45)
            add_note(drums, CLOSED_HAT, vel, base + t(mid, i * 0.25), t(mid, 0.125), CH_DRUMS)

    # --- GUITAR: Am-F-E7 progression with signature Am riff ---
    # Am arpeggio: A3(57)-C4(60)-E4(64)-A4(69), then descending run
    guitar = []
    # 4-bar progression: Am(2 bars) - F(1 bar) - E7(1 bar)
    progressions = [
        # Am bars: the signature arpeggio riff
        # Bar 1: A-C-E-A arpeggio ascending
        (0.0, 57, 90, 0.5),    # A3
        (0.5, 60, 85, 0.5),    # C4
        (1.0, 64, 88, 0.5),    # E4
        (1.5, 69, 92, 0.75),   # A4
        (2.25, 72, 85, 0.5),   # C5
        (2.75, 69, 80, 0.5),   # A4
        (3.25, 64, 82, 0.75),  # E4
        # Bar 2: descending run - the signature smooth lick
        (4.0, 69, 88, 0.25),   # A4
        (4.25, 67, 85, 0.25),  # G4
        (4.5, 65, 82, 0.25),   # F4
        (4.75, 64, 85, 0.25),  # E4
        (5.0, 62, 80, 0.25),   # D4
        (5.25, 60, 82, 0.25),  # C4
        (5.5, 59, 78, 0.25),   # B3
        (5.75, 57, 85, 1.0),   # A3 sustained
        (7.0, 57, 70, 0.5),    # A3 echo
        (7.5, 60, 72, 0.5),    # C4 lead-in
        # Bar 3: F chord voicing (F3-A3-C4)
        (8.0, 53, 88, 0.5),    # F3
        (8.5, 57, 82, 0.5),    # A3
        (9.0, 60, 85, 0.5),    # C4
        (9.5, 65, 90, 0.5),    # F4
        (10.0, 60, 80, 0.5),   # C4
        (10.5, 57, 75, 0.5),   # A3
        (11.0, 53, 82, 0.5),   # F3
        (11.5, 57, 78, 0.5),   # A3
        # Bar 4: E7 (E3-G#3-B3-D4)
        (12.0, 52, 90, 0.5),   # E3
        (12.5, 56, 85, 0.5),   # G#3
        (13.0, 59, 88, 0.5),   # B3
        (13.5, 62, 92, 0.75),  # D4
        (14.25, 64, 85, 0.25), # E4
        (14.5, 62, 80, 0.5),   # D4
        (15.0, 59, 82, 0.5),   # B3
        (15.5, 56, 78, 0.5),   # G#3
    ]
    for rep in range(4):
        offset = rep * 4 * 4 * ppq
        for beat, note, vel, dur in progressions:
            add_note(guitar, note, vel, offset + t(mid, beat), t(mid, dur), CH_GUITAR)

    # --- BASS: A2-F2-E2 root movement, latin syncopation, ghosts ---
    # A2=45, F2=41, E2=40
    bass = []
    bass_pattern = [
        # Bar 1-2: Am bass (A2 root)
        (0.0, 45, 100, 0.5),    # A2
        (0.5, 45, 60, 0.25),    # ghost
        (1.0, 48, 85, 0.5),     # C3
        (1.5, 45, 65, 0.25),    # ghost
        (2.0, 45, 95, 0.5),     # A2
        (2.5, 43, 80, 0.5),     # G2
        (3.0, 45, 90, 0.5),     # A2
        (3.5, 45, 60, 0.25),    # ghost
        (4.0, 45, 100, 0.5),    # A2
        (4.5, 47, 75, 0.5),     # B2
        (5.0, 48, 85, 0.5),     # C3
        (5.5, 48, 60, 0.25),    # ghost
        (6.0, 45, 90, 0.5),     # A2
        (6.5, 43, 75, 0.5),     # G2
        (7.0, 45, 95, 0.5),     # A2
        (7.5, 45, 65, 0.25),    # ghost
        # Bar 3: F bass
        (8.0, 41, 100, 0.5),    # F2
        (8.5, 41, 60, 0.25),    # ghost
        (9.0, 45, 85, 0.5),     # A2
        (9.5, 41, 65, 0.25),    # ghost
        (10.0, 41, 95, 0.5),    # F2
        (10.5, 43, 75, 0.5),    # G2
        (11.0, 45, 85, 0.5),    # A2
        (11.5, 43, 70, 0.5),    # G2
        # Bar 4: E bass
        (12.0, 40, 100, 0.5),   # E2
        (12.5, 40, 60, 0.25),   # ghost
        (13.0, 44, 85, 0.5),    # G#2
        (13.5, 40, 65, 0.25),   # ghost
        (14.0, 40, 95, 0.5),    # E2
        (14.5, 42, 75, 0.5),    # F#2
        (15.0, 44, 85, 0.5),    # G#2
        (15.5, 45, 80, 0.5),    # A2 chromatic up
    ]
    for rep in range(4):
        offset = rep * 4 * 4 * ppq
        for beat, note, vel, dur in bass_pattern:
            add_note(bass, note, vel, offset + t(mid, beat), t(mid, dur), CH_BASS)

    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Smooth", "Santana", bpm, "Am", bars, 3,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Smooth")


# ========================================================================
# 3. SANTANA - EVIL WAYS (BPM 124, Gm, 4/4, 16 bars)
# ========================================================================
def gen_evil_ways():
    bpm = 124
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "evil_ways")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    bars = 16

    # --- DRUMS: Latin shuffle with timbale hi-hat, conga feel ---
    drums = []
    for bar in range(bars):
        base = bar * 4 * ppq
        # Kick on 1 and 3
        add_note(drums, KICK, 105, base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 95, base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        # Snare on 2 and 4 (light, side-stick feel)
        add_note(drums, SIDE_STICK, 90, base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SIDE_STICK, 90, base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Timbale-style hi-hat: shuffled 8ths (swing feel)
        for i in range(8):
            swing = 0.08 if i % 2 == 1 else 0  # slight swing
            vel = 80 if i % 2 == 0 else 55
            add_note(drums, TIMBALE_HIGH, vel,
                     base + t(mid, i * 0.5 + swing), t(mid, 0.2), CH_DRUMS)
        # Conga pattern: syncopated latin groove
        add_note(drums, CONGA_HIGH, 85, base + t(mid, 0.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_MUTE, 70, base + t(mid, 0.5), t(mid, 0.2), CH_DRUMS)
        add_note(drums, CONGA_LOW, 80, base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_HIGH, 75, base + t(mid, 1.75), t(mid, 0.2), CH_DRUMS)
        add_note(drums, CONGA_LOW, 80, base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_MUTE, 65, base + t(mid, 2.5), t(mid, 0.2), CH_DRUMS)
        add_note(drums, CONGA_HIGH, 85, base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, CONGA_LOW, 70, base + t(mid, 3.5), t(mid, 0.2), CH_DRUMS)
        # Cowbell on and-of-2 and and-of-4
        add_note(drums, COWBELL, 70, base + t(mid, 1.5), t(mid, 0.2), CH_DRUMS)
        add_note(drums, COWBELL, 70, base + t(mid, 3.5), t(mid, 0.2), CH_DRUMS)

    # --- KEYS: Organ riff Gm7 to C7 vamp ---
    # Gm7: G3(55) Bb3(58) D4(62) F4(65)
    # C7:  C3(48) E3(52) G3(55) Bb3(58)
    keys = []
    # The signature 2-chord groove per bar, repeated
    for bar in range(bars):
        base = bar * 4 * ppq
        if bar % 2 == 0:
            # Gm7 bar - organ stabs
            # Stab on beat 1
            for n in [55, 58, 62]:
                add_note(keys, n, 88, base, t(mid, 0.75), CH_KEYS)
            # Stab on and-of-2
            for n in [55, 58, 62]:
                add_note(keys, n, 80, base + t(mid, 1.5), t(mid, 0.5), CH_KEYS)
            # Stab on beat 3
            for n in [55, 58, 62]:
                add_note(keys, n, 85, base + t(mid, 2.0), t(mid, 0.75), CH_KEYS)
            # Pickup stab on and-of-4
            for n in [55, 58, 62]:
                add_note(keys, n, 75, base + t(mid, 3.5), t(mid, 0.5), CH_KEYS)
        else:
            # C7 bar
            # Stab on beat 1
            for n in [48, 52, 55]:
                add_note(keys, n, 88, base, t(mid, 0.75), CH_KEYS)
            # Stab on and-of-2
            for n in [48, 52, 55]:
                add_note(keys, n, 80, base + t(mid, 1.5), t(mid, 0.5), CH_KEYS)
            # Stab on beat 3
            for n in [48, 52, 55]:
                add_note(keys, n, 85, base + t(mid, 2.0), t(mid, 0.75), CH_KEYS)
            # Stab on and-of-4 (rising to Gm)
            for n in [50, 53, 57]:
                add_note(keys, n, 75, base + t(mid, 3.5), t(mid, 0.5), CH_KEYS)

    # --- BASS: G2-C2 alternating, chromatic approaches, latin 8th notes ---
    # G2=43, C2=36 (low), C3=48, Bb2=46, A2=45, F#2=42
    bass = []
    bass_pattern = [
        # Bar 1: Gm root
        (0.0, 43, 100, 0.5),    # G2
        (0.5, 43, 65, 0.25),    # ghost
        (1.0, 46, 85, 0.5),     # Bb2
        (1.5, 43, 70, 0.5),     # G2
        (2.0, 45, 90, 0.5),     # A2
        (2.5, 46, 80, 0.5),     # Bb2
        (3.0, 47, 85, 0.5),     # B2 chromatic approach
        (3.5, 47, 60, 0.25),    # ghost
        # Bar 2: C root
        (4.0, 48, 100, 0.5),    # C3
        (4.5, 48, 65, 0.25),    # ghost
        (5.0, 50, 85, 0.5),     # D3
        (5.5, 48, 70, 0.5),     # C3
        (6.0, 46, 90, 0.5),     # Bb2
        (6.5, 45, 80, 0.5),     # A2
        (7.0, 43, 85, 0.5),     # G2
        (7.5, 42, 75, 0.5),     # F#2 chromatic approach back
    ]
    for rep in range(8):
        offset = rep * 2 * 4 * ppq
        for beat, note, vel, dur in bass_pattern:
            add_note(bass, note, vel, offset + t(mid, beat), t(mid, dur), CH_BASS)

    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, keys, os.path.join(song_dir, "keys.mid"), "Keys", CH_KEYS)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Keys", keys), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Evil Ways", "Santana", bpm, "Gm", bars, 2,
               ["drums", "keys", "bass"])
    print(f"  [OK] Evil Ways")


# ========================================================================
# 4. MUSE - HYSTERIA (BPM 94, Am, 4/4, 16 bars)
# ========================================================================
def gen_hysteria():
    bpm = 94
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "hysteria")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    bars = 16

    # --- DRUMS: Machine-gun 16th kick, snare 2+4, crash accents ---
    drums = []
    for bar in range(bars):
        base = bar * 4 * ppq
        # 16th note kick drum pattern (the Dom Howard machine gun)
        for i in range(16):
            # Accent pattern: stronger on downbeats, slightly varied
            if i % 4 == 0:
                vel = 110
            elif i % 4 == 2:
                vel = 95
            else:
                vel = 80
            add_note(drums, KICK, vel, base + t(mid, i * 0.25), t(mid, 0.125), CH_DRUMS)
        # Snare on 2 and 4
        add_note(drums, SNARE, 110, base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, 110, base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Crash accent every 4 bars on beat 1
        if bar % 4 == 0:
            add_note(drums, CRASH, 100, base, t(mid, 0.5), CH_DRUMS)
        # Hi-hat on 8ths
        for i in range(8):
            vel = 70 if i % 2 == 0 else 50
            add_note(drums, CLOSED_HAT, vel, base + t(mid, i * 0.5), t(mid, 0.2), CH_DRUMS)

    # --- BASS: THE iconic riff ---
    # A2(45)-E3(52)-A3(57)-G3(55)-F3(53)-E3(52)-D3(50)-C3(48)
    # Rapid 16th note sequence, the defining riff of the song
    bass = []
    # The riff is 2 bars long, repeated
    riff = [
        # Bar 1: ascending then descending - the full Hysteria riff
        (0.0, 45, 100),    # A2
        (0.25, 45, 85),    # A2
        (0.5, 52, 95),     # E3
        (0.75, 52, 80),    # E3
        (1.0, 57, 100),    # A3
        (1.25, 55, 90),    # G3
        (1.5, 53, 95),     # F3
        (1.75, 52, 85),    # E3
        (2.0, 50, 100),    # D3
        (2.25, 48, 90),    # C3
        (2.5, 45, 95),     # A2
        (2.75, 48, 85),    # C3
        (3.0, 50, 100),    # D3
        (3.25, 52, 90),    # E3
        (3.5, 53, 95),     # F3
        (3.75, 52, 85),    # E3
        # Bar 2: variation with octave jump
        (4.0, 45, 100),    # A2
        (4.25, 45, 85),    # A2
        (4.5, 52, 95),     # E3
        (4.75, 52, 80),    # E3
        (5.0, 57, 100),    # A3
        (5.25, 57, 85),    # A3
        (5.5, 55, 95),     # G3
        (5.75, 53, 90),    # F3
        (6.0, 52, 100),    # E3
        (6.25, 50, 90),    # D3
        (6.5, 48, 95),     # C3
        (6.75, 47, 85),    # B2
        (7.0, 45, 100),    # A2
        (7.25, 47, 85),    # B2
        (7.5, 48, 90),     # C3
        (7.75, 50, 85),    # D3
    ]
    for rep in range(8):  # 8 x 2 bars = 16 bars
        offset = rep * 2 * 4 * ppq
        for beat, note, vel in riff:
            add_note(bass, note, vel, offset + t(mid, beat), t(mid, 0.2), CH_BASS)

    # --- GUITAR: Am-E-G-D power chord progression ---
    # Am5: A3(57)+E4(64), E5: E3(52)+B3(59), G5: G3(55)+D4(62), D5: D3(50)+A3(57)
    guitar = []
    chords = [
        # 4-bar progression repeated 4x
        # Bar 1: Am power chord - sustained with palm-muted 8ths
        (0.0, [57, 64], 95, 1.5),
        (1.5, [57, 64], 75, 0.5),
        (2.0, [57, 64], 90, 1.5),
        (3.5, [57, 64], 70, 0.5),
        # Bar 2: E power chord
        (4.0, [52, 59], 95, 1.5),
        (5.5, [52, 59], 75, 0.5),
        (6.0, [52, 59], 90, 1.5),
        (7.5, [52, 59], 70, 0.5),
        # Bar 3: G power chord
        (8.0, [55, 62], 95, 1.5),
        (9.5, [55, 62], 75, 0.5),
        (10.0, [55, 62], 90, 1.5),
        (11.5, [55, 62], 70, 0.5),
        # Bar 4: D power chord
        (12.0, [50, 57], 95, 1.5),
        (13.5, [50, 57], 75, 0.5),
        (14.0, [50, 57], 90, 1.5),
        (15.5, [50, 57], 70, 0.5),
    ]
    for rep in range(4):
        offset = rep * 4 * 4 * ppq
        for beat, notes, vel, dur in chords:
            for n in notes:
                add_note(guitar, n, vel, offset + t(mid, beat), t(mid, dur), CH_GUITAR)

    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_full_midi(mid, [("Drums", drums), ("Bass", bass), ("Guitar", guitar)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Hysteria", "Muse", bpm, "Am", bars, 5,
               ["drums", "bass", "guitar"])
    print(f"  [OK] Hysteria")


# ========================================================================
# 5. MUSE - SUPERMASSIVE BLACK HOLE (BPM 120, Am, 4/4, 16 bars)
# ========================================================================
def gen_supermassive_black_hole():
    bpm = 120
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "supermassive_black_hole")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    bars = 16

    # --- DRUMS: Funk-rock syncopated kick, snare 2+4 with ghosts, hat 16ths ---
    drums = []
    for bar in range(bars):
        base = bar * 4 * ppq
        # Syncopated kick: 1, and-of-1, 3, and-of-3
        add_note(drums, KICK, 110, base, t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 85, base + t(mid, 0.75), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 100, base + t(mid, 2.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, KICK, 85, base + t(mid, 2.75), t(mid, 0.25), CH_DRUMS)
        # Snare on 2 and 4
        add_note(drums, SNARE, 105, base + t(mid, 1.0), t(mid, 0.25), CH_DRUMS)
        add_note(drums, SNARE, 105, base + t(mid, 3.0), t(mid, 0.25), CH_DRUMS)
        # Ghost snare notes
        add_note(drums, SNARE, 40, base + t(mid, 0.5), t(mid, 0.1), CH_DRUMS)
        add_note(drums, SNARE, 35, base + t(mid, 1.75), t(mid, 0.1), CH_DRUMS)
        add_note(drums, SNARE, 40, base + t(mid, 2.5), t(mid, 0.1), CH_DRUMS)
        add_note(drums, SNARE, 35, base + t(mid, 3.75), t(mid, 0.1), CH_DRUMS)
        # Hi-hat 16ths
        for i in range(16):
            vel = 80 if i % 4 == 0 else (60 if i % 2 == 0 else 40)
            add_note(drums, CLOSED_HAT, vel, base + t(mid, i * 0.25), t(mid, 0.125), CH_DRUMS)

    # --- GUITAR: Funky Am riff with muted scratches, Dm-Am-E7 hits ---
    guitar = []
    # 4-bar pattern: 2 bars funky Am staccato, then Dm-Am-E7 chord hits
    riff = [
        # Bar 1: A3 staccato 16ths with muted notes (low velocity = muted)
        (0.0, 57, 95, 0.15),    # A3 staccato
        (0.25, 57, 30, 0.1),    # muted scratch
        (0.5, 57, 90, 0.15),    # A3
        (0.75, 57, 30, 0.1),    # muted
        (1.0, 57, 95, 0.15),    # A3
        (1.25, 57, 30, 0.1),    # muted
        (1.5, 60, 88, 0.15),    # C4
        (1.75, 57, 30, 0.1),    # muted
        (2.0, 57, 95, 0.15),    # A3
        (2.25, 57, 30, 0.1),    # muted
        (2.5, 57, 90, 0.15),    # A3
        (2.75, 60, 85, 0.15),   # C4
        (3.0, 57, 95, 0.15),    # A3
        (3.25, 57, 30, 0.1),    # muted
        (3.5, 64, 88, 0.25),    # E4
        (3.75, 60, 82, 0.25),   # C4
        # Bar 2: continuation with variation
        (4.0, 57, 95, 0.15),
        (4.25, 57, 30, 0.1),
        (4.5, 57, 90, 0.15),
        (4.75, 60, 85, 0.15),
        (5.0, 64, 92, 0.25),    # E4
        (5.25, 60, 85, 0.25),   # C4
        (5.5, 57, 90, 0.5),     # A3
        (6.0, 57, 30, 0.1),
        (6.25, 57, 30, 0.1),
        (6.5, 57, 95, 0.15),
        (6.75, 57, 30, 0.1),
        (7.0, 57, 90, 0.25),
        (7.5, 60, 85, 0.5),     # C4
        # Bar 3: Dm chord hit (D4-F4-A4)
        (8.0, 62, 100, 0.75),   # D4
        (8.0, 65, 100, 0.75),   # F4
        (8.0, 69, 100, 0.75),   # A4
        (8.75, 62, 30, 0.1),    # muted
        (9.0, 62, 90, 0.5),     # D4
        (9.0, 65, 90, 0.5),     # F4
        (9.5, 62, 30, 0.1),
        # Am hit
        (10.0, 57, 100, 0.75),  # A3
        (10.0, 60, 100, 0.75),  # C4
        (10.0, 64, 100, 0.75),  # E4
        (10.75, 57, 30, 0.1),
        (11.0, 57, 90, 0.5),
        (11.0, 60, 90, 0.5),
        (11.5, 57, 30, 0.1),
        # Bar 4: E7 hit
        (12.0, 52, 100, 0.75),  # E3
        (12.0, 56, 100, 0.75),  # G#3
        (12.0, 59, 100, 0.75),  # B3
        (12.0, 62, 100, 0.75),  # D4
        (13.0, 52, 85, 0.5),
        (13.0, 56, 85, 0.5),
        (14.0, 57, 90, 0.15),   # A3 pickup 16ths
        (14.25, 57, 30, 0.1),
        (14.5, 57, 90, 0.15),
        (14.75, 57, 30, 0.1),
        (15.0, 57, 95, 0.15),
        (15.25, 60, 85, 0.15),
        (15.5, 57, 90, 0.25),
        (15.75, 57, 30, 0.1),
    ]
    for rep in range(4):
        offset = rep * 4 * 4 * ppq
        for beat, note, vel, dur in riff:
            add_note(guitar, note, vel, offset + t(mid, beat), t(mid, dur), CH_GUITAR)

    # --- BASS: A2 funk line with octave jumps and ghosts ---
    bass = []
    # A2=45, A3=57, G2=43, E2=40
    bass_pattern = [
        # Bar 1: funky A root with octave jumps
        (0.0, 45, 100, 0.25),   # A2
        (0.25, 45, 60, 0.15),   # ghost
        (0.5, 57, 90, 0.25),    # A3 octave up
        (0.75, 45, 70, 0.25),   # A2
        (1.0, 45, 95, 0.5),     # A2
        (1.5, 43, 80, 0.25),    # G2 slide
        (1.75, 45, 85, 0.25),   # A2
        (2.0, 45, 100, 0.25),   # A2
        (2.25, 45, 60, 0.15),   # ghost
        (2.5, 57, 90, 0.25),    # A3
        (2.75, 55, 80, 0.25),   # G3
        (3.0, 45, 95, 0.5),     # A2
        (3.5, 43, 80, 0.25),    # G2
        (3.75, 45, 85, 0.25),   # A2
        # Bar 2
        (4.0, 45, 100, 0.25),
        (4.25, 45, 60, 0.15),
        (4.5, 48, 90, 0.25),    # C3
        (4.75, 45, 70, 0.25),
        (5.0, 50, 95, 0.25),    # D3
        (5.25, 48, 80, 0.25),   # C3
        (5.5, 45, 90, 0.25),    # A2
        (5.75, 43, 75, 0.25),   # G2
        (6.0, 40, 100, 0.5),    # E2
        (6.5, 40, 60, 0.15),    # ghost
        (7.0, 43, 90, 0.5),     # G2
        (7.5, 44, 80, 0.25),    # G#2 chromatic
        (7.75, 45, 85, 0.25),   # A2
    ]
    for rep in range(8):
        offset = rep * 2 * 4 * ppq
        for beat, note, vel, dur in bass_pattern:
            add_note(bass, note, vel, offset + t(mid, beat), t(mid, dur), CH_BASS)

    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Supermassive Black Hole", "Muse", bpm, "Am", bars, 4,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Supermassive Black Hole")


# ========================================================================
# 6. MUSE - KNIGHTS OF CYDONIA (BPM 138, Em, 6/8 -> 4/4, 16 bars)
# ========================================================================
def gen_knights_of_cydonia():
    bpm = 138
    mid = make_template(bpm)
    song_dir = os.path.join(SONGS_DIR, "knights_of_cydonia")
    os.makedirs(song_dir, exist_ok=True)
    ppq = mid.ticks_per_beat
    bars = 16

    # In 6/8 at 138 BPM (dotted quarter = pulse), each bar = 2 dotted quarters = 3 quarter notes
    # We'll treat the MIDI as quarter=138, with 6/8 bars being 3 beats long
    # For the gallop: each beat is divided into triplets (kick-kick-snare)

    # --- DRUMS: Galloping 6/8 rhythm ---
    # kick-kick-snare triplet pattern per beat (like a horse gallop)
    drums = []
    for bar in range(bars):
        # 6/8 bar = 3 quarter note beats
        base = bar * 3 * ppq
        for beat in range(3):
            beat_start = base + beat * ppq
            trip = ppq // 3  # triplet subdivision
            # Gallop: kick - kick - snare
            add_note(drums, KICK, 110, beat_start, t(mid, 0.15), CH_DRUMS)
            add_note(drums, KICK, 90, beat_start + trip, t(mid, 0.15), CH_DRUMS)
            add_note(drums, SNARE, 100, beat_start + 2 * trip, t(mid, 0.15), CH_DRUMS)
        # Crash on bar 1 of every 4-bar phrase
        if bar % 4 == 0:
            add_note(drums, CRASH, 100, base, t(mid, 0.5), CH_DRUMS)
        # Ride on every beat
        for beat in range(3):
            add_note(drums, RIDE, 75, base + beat * ppq, t(mid, 0.25), CH_DRUMS)

    # --- GUITAR: Galloping E5 power chord triplets, then heroic melody ---
    # E5 power chord: E4(64) + B4(71)
    # Heroic melody: E4-G4-A4-B4-D5
    guitar = []
    for bar in range(bars):
        base = bar * 3 * ppq
        trip = ppq // 3
        if bar < 8:
            # First 8 bars: galloping E5 power chord
            for beat in range(3):
                beat_start = base + beat * ppq
                # Galloping 8th note triplets on power chord
                add_note(guitar, 64, 95, beat_start, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, 71, 95, beat_start, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, 64, 80, beat_start + trip, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, 71, 80, beat_start + trip, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, 64, 90, beat_start + 2 * trip, t(mid, 0.15), CH_GUITAR)
                add_note(guitar, 71, 90, beat_start + 2 * trip, t(mid, 0.15), CH_GUITAR)
        else:
            # Bars 9-16: heroic melody E4(64)-G4(67)-A4(69)-B4(71)-D5(74)
            # 2-bar melody phrase repeated
            melody_bar = (bar - 8) % 4
            if melody_bar == 0:
                # E4 - G4 - A4 ascending heroic
                add_note(guitar, 64, 100, base, t(mid, 0.9), CH_GUITAR)
                add_note(guitar, 67, 95, base + ppq, t(mid, 0.9), CH_GUITAR)
                add_note(guitar, 69, 100, base + 2 * ppq, t(mid, 0.9), CH_GUITAR)
            elif melody_bar == 1:
                # B4 - D5 - B4 peak and return
                add_note(guitar, 71, 105, base, t(mid, 0.9), CH_GUITAR)
                add_note(guitar, 74, 110, base + ppq, t(mid, 0.9), CH_GUITAR)
                add_note(guitar, 71, 95, base + 2 * ppq, t(mid, 0.9), CH_GUITAR)
            elif melody_bar == 2:
                # A4 - G4 - E4 descending
                add_note(guitar, 69, 100, base, t(mid, 0.9), CH_GUITAR)
                add_note(guitar, 67, 95, base + ppq, t(mid, 0.9), CH_GUITAR)
                add_note(guitar, 64, 100, base + 2 * ppq, t(mid, 0.9), CH_GUITAR)
            else:
                # E4 sustained resolve with power chord
                add_note(guitar, 64, 105, base, t(mid, 2.5), CH_GUITAR)
                add_note(guitar, 71, 100, base, t(mid, 2.5), CH_GUITAR)

    # --- BASS: E2 galloping 8ths matching drum/guitar ---
    # E2=40, with some movement: E2-G2-A2-B2
    bass = []
    for bar in range(bars):
        base = bar * 3 * ppq
        trip = ppq // 3
        # Root note selection: E2 mostly, with movement every 4 bars
        bar_in_phrase = bar % 4
        if bar_in_phrase == 0 or bar_in_phrase == 1:
            root = 40  # E2
        elif bar_in_phrase == 2:
            root = 43  # G2
        else:
            root = 45  # A2

        # Galloping triplets on root
        for beat in range(3):
            beat_start = base + beat * ppq
            add_note(bass, root, 100, beat_start, t(mid, 0.15), CH_BASS)
            add_note(bass, root, 80, beat_start + trip, t(mid, 0.15), CH_BASS)
            add_note(bass, root, 90, beat_start + 2 * trip, t(mid, 0.15), CH_BASS)

    save_track_midi(mid, drums, os.path.join(song_dir, "drums.mid"), "Drums", CH_DRUMS)
    save_track_midi(mid, guitar, os.path.join(song_dir, "guitar.mid"), "Guitar", CH_GUITAR)
    save_track_midi(mid, bass, os.path.join(song_dir, "bass.mid"), "Bass", CH_BASS)
    save_full_midi(mid, [("Drums", drums), ("Guitar", guitar), ("Bass", bass)],
                   os.path.join(song_dir, "full.mid"))
    write_meta(song_dir, "Knights of Cydonia", "Muse", bpm, "Em", bars, 4,
               ["drums", "guitar", "bass"])
    print(f"  [OK] Knights of Cydonia")


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
    for song in os.listdir(SONGS_DIR):
        song_path = os.path.join(SONGS_DIR, song)
        if os.path.isdir(song_path):
            files = [f for f in os.listdir(song_path) if f.endswith(('.mid', '.json'))]
            total_files += len(files)
    print(f"Total files in songs/: {total_files}")


if __name__ == "__main__":
    main()
