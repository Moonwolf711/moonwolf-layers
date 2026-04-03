"""
Generate multi-track MIDI files for iconic rock songs (Group 1).
Songs: Whole Lotta Love, Kashmir, Riders on the Storm, Light My Fire, Purple Haze, Voodoo Child
Uses mido library. Each song gets its own folder with per-instrument .mid files + combined full.mid + meta.json.
"""

import os
import json
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")

# GM Drum map constants
KICK = 36
SNARE = 38
RIMSHOT = 37  # side stick / rimclick
HAT_CLOSED = 42
HAT_OPEN = 46
HAT_PEDAL = 44
CRASH = 49
RIDE = 51
RIDE_BELL = 53
LOW_TOM = 45
HI_TOM = 48
MID_TOM = 47


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


def swing_offset(eighth_index, amount=20):
    """Return a small timing offset for swing feel on off-beat eighths."""
    if eighth_index % 2 == 1:
        return amount
    return 0


def humanize(vel, spread=8):
    """Add slight velocity variation for human feel."""
    import random
    return max(1, min(127, vel + random.randint(-spread, spread)))


def make_midi(tempo_bpm):
    """Create a MidiFile with one empty track containing tempo."""
    mid = MidiFile(ticks_per_beat=ticks_per_beat())
    return mid


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


def save_meta(folder, title, artist, bpm, key, bars, difficulty, instruments):
    meta = {
        "title": title,
        "artist": artist,
        "bpm": bpm,
        "key": key,
        "bars": bars,
        "difficulty": difficulty,
        "instruments": instruments
    }
    with open(os.path.join(folder, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


# ============================================================
# Helper: ticks
# ============================================================
TPB = 480  # ticks per beat (quarter note)
WHOLE = TPB * 4
HALF = TPB * 2
QUARTER = TPB
EIGHTH = TPB // 2
SIXTEENTH = TPB // 4
TRIPLET_8TH = TPB // 3


# ============================================================
# 1. LED ZEPPELIN - WHOLE LOTTA LOVE
# ============================================================
def generate_whole_lotta_love():
    import random
    random.seed(42)
    folder = os.path.join(BASE_DIR, "led_zeppelin_whole_lotta_love")
    ensure_dir(folder)
    bpm = 90
    bars = 16
    ch_drum = 9  # MIDI channel 10 (0-indexed = 9)
    ch_bass = 2
    ch_guitar = 1

    # --- DRUMS ---
    drum_track = make_track("Drums", bpm)
    for bar in range(bars):
        for beat in range(4):
            # Kick on 1 and 3 (with ghost kick sometimes on the "and" of 2)
            if beat == 0:
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(105), channel=ch_drum)
                # Closed hat on the beat
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(90), channel=ch_drum)
            elif beat == 1:
                # Snare on 2
                add_note(drum_track, SNARE, EIGHTH, velocity=humanize(110), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(85), channel=ch_drum)
            elif beat == 2:
                # Kick on 3 (not always — Bonham variation)
                if bar % 2 == 0:
                    add_note(drum_track, KICK, EIGHTH, velocity=humanize(95), channel=ch_drum)
                else:
                    add_note(drum_track, KICK, EIGHTH, velocity=humanize(80), channel=ch_drum)
                add_note(drum_track, HAT_OPEN, EIGHTH, velocity=humanize(95), channel=ch_drum)
            elif beat == 3:
                # Snare on 4
                add_note(drum_track, SNARE, EIGHTH, velocity=humanize(108), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(80), channel=ch_drum)

            # Ghost notes on 16ths between beats
            if beat < 3:
                # "and" of the beat — ghost snare
                drum_track.append(Message('note_on', note=SNARE, velocity=humanize(40, 5),
                                          time=EIGHTH, channel=ch_drum))
                drum_track.append(Message('note_off', note=SNARE, time=SIXTEENTH, channel=ch_drum))
                # hat on the "and"
                add_note(drum_track, HAT_CLOSED, SIXTEENTH, velocity=humanize(70), channel=ch_drum)
            else:
                # Last beat — fill space to bar end
                drum_track.append(Message('note_on', note=HAT_CLOSED, velocity=humanize(65),
                                          time=EIGHTH, channel=ch_drum))
                drum_track.append(Message('note_off', note=HAT_CLOSED, time=EIGHTH, channel=ch_drum))

        # Crash on first beat of bars 1, 5, 9, 13
        # (Already placed via kick — add crash overlap at bar transitions)
    # Add crash accents at phrase starts by inserting at key positions
    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS ---
    bass_track = make_track("Bass", bpm)
    # Classic John Paul Jones bass — E blues riff
    # E2=40, A2=45, B2=47, D3=50, G2=43
    E2, A2, B2, D2, G2 = 40, 45, 47, 38, 43
    # The riff: driving 8th note E's with slides to A and B
    for bar in range(bars):
        if bar % 4 < 2:
            # E-based bars — driving 8th notes on E2
            for eighth in range(8):
                vel = humanize(95 if eighth % 2 == 0 else 80)
                if eighth == 6:
                    # Slide up to G2 on the 7th eighth
                    add_note(bass_track, G2, EIGHTH, velocity=vel, channel=ch_bass)
                elif eighth == 7:
                    # A2 on the last eighth
                    add_note(bass_track, A2, EIGHTH, velocity=vel, channel=ch_bass)
                else:
                    add_note(bass_track, E2, EIGHTH, velocity=vel, channel=ch_bass)
        elif bar % 4 == 2:
            # A-based bar
            for eighth in range(8):
                vel = humanize(90 if eighth % 2 == 0 else 78)
                if eighth >= 6:
                    add_note(bass_track, B2, EIGHTH, velocity=vel, channel=ch_bass)
                else:
                    add_note(bass_track, A2, EIGHTH, velocity=vel, channel=ch_bass)
        else:
            # B to E resolution
            for eighth in range(8):
                vel = humanize(92 if eighth % 2 == 0 else 80)
                if eighth < 4:
                    add_note(bass_track, B2, EIGHTH, velocity=vel, channel=ch_bass)
                else:
                    add_note(bass_track, E2, EIGHTH, velocity=vel, channel=ch_bass)
    bass_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR ---
    guitar_track = make_track("Guitar", bpm)
    # The iconic riff: E4-E4-E4-D4-E4 with chromatic descend
    # E4=64, D4=62, C#4=61, C4=60, B3=59
    E4, D4, Cs4, C4, B3 = 64, 62, 61, 60, 59
    # Also uses E5 power chord stabs: E4+B4(71)
    B4 = 71
    for bar in range(bars):
        if bar % 4 < 2:
            # Main riff: E E E D E (bend on D) then chromatic walk down
            # Beat 1: E4 eighth
            add_note(guitar_track, E4, EIGHTH, velocity=humanize(105), channel=ch_guitar)
            # Beat 1+: E4 eighth
            add_note(guitar_track, E4, EIGHTH, velocity=humanize(100), channel=ch_guitar)
            # Beat 2: E4 eighth
            add_note(guitar_track, E4, EIGHTH, velocity=humanize(102), channel=ch_guitar)
            # Beat 2+: D4 (the bend note) — slightly longer
            add_note(guitar_track, D4, EIGHTH + SIXTEENTH, velocity=humanize(108), channel=ch_guitar)
            # Grace note back to E4
            add_note(guitar_track, E4, SIXTEENTH, velocity=humanize(95), channel=ch_guitar)
            # Beat 3-4: Chromatic descend E4-D4-C#4-C4-B3
            add_note(guitar_track, E4, EIGHTH, velocity=humanize(100), channel=ch_guitar)
            add_note(guitar_track, D4, EIGHTH, velocity=humanize(95), channel=ch_guitar)
            add_note(guitar_track, Cs4, EIGHTH, velocity=humanize(90), channel=ch_guitar)
            add_note(guitar_track, B3, EIGHTH, velocity=humanize(88), channel=ch_guitar)
        elif bar % 4 == 2:
            # Power chord stabs on A (A4=69 + E5=76)
            A4, E5 = 69, 76
            add_note(guitar_track, A4, QUARTER, velocity=humanize(110), channel=ch_guitar)
            add_note(guitar_track, E5, QUARTER, velocity=humanize(108), time=0, channel=ch_guitar)
            # rest
            guitar_track.append(Message('note_on', note=0, velocity=0, time=QUARTER, channel=ch_guitar))
            guitar_track.append(Message('note_off', note=0, time=0, channel=ch_guitar))
            # Repeat stab
            add_note(guitar_track, A4, QUARTER, velocity=humanize(105), channel=ch_guitar)
            add_note(guitar_track, E5, QUARTER, velocity=humanize(103), time=0, channel=ch_guitar)
            guitar_track.append(Message('note_on', note=0, velocity=0, time=QUARTER, channel=ch_guitar))
            guitar_track.append(Message('note_off', note=0, time=0, channel=ch_guitar))
        else:
            # E power chord stabs: E4+B4
            add_note(guitar_track, E4, QUARTER, velocity=humanize(110), channel=ch_guitar)
            add_note(guitar_track, B4, QUARTER, velocity=humanize(108), time=0, channel=ch_guitar)
            guitar_track.append(Message('note_on', note=0, velocity=0, time=QUARTER, channel=ch_guitar))
            guitar_track.append(Message('note_off', note=0, time=0, channel=ch_guitar))
            # Riff fragment
            add_note(guitar_track, E4, EIGHTH, velocity=humanize(100), channel=ch_guitar)
            add_note(guitar_track, D4, EIGHTH, velocity=humanize(95), channel=ch_guitar)
            add_note(guitar_track, E4, QUARTER, velocity=humanize(105), channel=ch_guitar)
    guitar_track.append(MetaMessage('end_of_track', time=0))

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_full([drum_track, bass_track, guitar_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Whole Lotta Love", "Led Zeppelin", bpm, "E", bars, 3,
              ["drums", "bass", "guitar"])
    print(f"  [OK] Whole Lotta Love")


# ============================================================
# 2. LED ZEPPELIN - KASHMIR
# ============================================================
def generate_kashmir():
    import random
    random.seed(43)
    folder = os.path.join(BASE_DIR, "led_zeppelin_kashmir")
    ensure_dir(folder)
    bpm = 80
    bars = 16
    ch_drum = 9
    ch_strings = 4
    ch_guitar = 1

    # --- DRUMS: Bonham march ---
    drum_track = make_track("Drums", bpm)
    for bar in range(bars):
        for beat in range(4):
            if beat == 0:
                # Kick-kick pattern (two quick kicks)
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(110), channel=ch_drum)
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(95), channel=ch_drum)
            elif beat == 1:
                # Snare hit (the march snare)
                add_note(drum_track, SNARE, QUARTER, velocity=humanize(112), channel=ch_drum)
            elif beat == 2:
                # Kick again
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(105), channel=ch_drum)
                # Hat
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(80), channel=ch_drum)
            elif beat == 3:
                # Open hat or ride
                add_note(drum_track, HAT_OPEN, EIGHTH, velocity=humanize(90), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(75), channel=ch_drum)
        # Steady 8th hat layer on top (simplified by adding where not already placed)
    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- STRINGS: The ascending D-E-F-G-A line ---
    strings_track = make_track("Strings", bpm)
    # D4=62, E4=64, F4=65, G4=67, A4=69
    # The string line climbs and then descends, repeating over 2-bar phrases
    ascending = [62, 64, 65, 67, 69]  # D E F G A
    descending = [69, 67, 65, 64, 62]  # A G F E D
    for bar in range(bars):
        if bar % 4 < 2:
            # Ascending phrase over 2 bars
            notes = ascending if bar % 2 == 0 else descending
            for i, n in enumerate(notes):
                # Space them as quarter notes, but 5 notes over 2 bars = various rhythms
                # Kashmir strings: quarter notes climbing, with the last held
                vel = humanize(85 + i * 3)
                if i < 4:
                    add_note(strings_track, n, QUARTER, velocity=vel, channel=ch_strings)
                else:
                    add_note(strings_track, n, WHOLE - QUARTER * 4 + QUARTER, velocity=vel,
                             channel=ch_strings)
            # Fill remaining time if needed
            remaining = WHOLE - (QUARTER * 4 + (WHOLE - QUARTER * 4 + QUARTER))
            if remaining > 0:
                strings_track.append(Message('note_on', note=0, velocity=0, time=remaining, channel=ch_strings))
                strings_track.append(Message('note_off', note=0, time=0, channel=ch_strings))
        else:
            # Sustained chord: D minor (D4, F4, A4)
            strings_track.append(note_on(62, humanize(80), channel=ch_strings))
            strings_track.append(note_on(65, humanize(78), time=0, channel=ch_strings))
            strings_track.append(note_on(69, humanize(82), time=0, channel=ch_strings))
            strings_track.append(note_off(62, time=WHOLE, channel=ch_strings))
            strings_track.append(note_off(65, time=0, channel=ch_strings))
            strings_track.append(note_off(69, time=0, channel=ch_strings))
    strings_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR: DADGAD chromatic riff ---
    guitar_track = make_track("Guitar", bpm)
    # The guitar riff is a chromatic ascending line starting on D3(50)
    # with open D drone underneath
    # D3=50, Eb3=51, E3=52, F3=53, F#3=54, G3=55
    D2 = 38  # Low D drone
    riff_notes = [50, 51, 52, 53, 54, 55, 54, 53]  # D Eb E F F# G F# F (chromatic walk)
    for bar in range(bars):
        for i, n in enumerate(riff_notes):
            vel = humanize(100 if i % 2 == 0 else 88)
            # Drone D2 underneath
            if i == 0:
                guitar_track.append(note_on(D2, humanize(75), channel=ch_guitar))
            add_note(guitar_track, n, EIGHTH, velocity=vel, channel=ch_guitar)
            if i == len(riff_notes) - 1:
                guitar_track.append(note_off(D2, time=0, channel=ch_guitar))
    guitar_track.append(MetaMessage('end_of_track', time=0))

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(strings_track, bpm, os.path.join(folder, "strings.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_full([drum_track, strings_track, guitar_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Kashmir", "Led Zeppelin", bpm, "D", bars, 4,
              ["drums", "strings", "guitar"])
    print(f"  [OK] Kashmir")


# ============================================================
# 3. THE DOORS - RIDERS ON THE STORM
# ============================================================
def generate_riders_on_the_storm():
    import random
    random.seed(44)
    folder = os.path.join(BASE_DIR, "the_doors_riders_on_the_storm")
    ensure_dir(folder)
    bpm = 108
    bars = 16
    ch_drum = 9
    ch_keys = 0
    ch_bass = 2

    # --- DRUMS: Brushes feel ---
    drum_track = make_track("Drums", bpm)
    for bar in range(bars):
        for beat in range(4):
            if beat == 0:
                # Light kick on 1
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(75), channel=ch_drum)
                add_note(drum_track, RIDE, EIGHTH, velocity=humanize(70), channel=ch_drum)
            elif beat == 1:
                # Rimshot snare on 2
                add_note(drum_track, RIMSHOT, EIGHTH, velocity=humanize(65), channel=ch_drum)
                add_note(drum_track, RIDE, EIGHTH, velocity=humanize(68), channel=ch_drum)
            elif beat == 2:
                # Light kick on 3
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(70), channel=ch_drum)
                add_note(drum_track, RIDE, EIGHTH, velocity=humanize(72), channel=ch_drum)
            elif beat == 3:
                # Rimshot on 4
                add_note(drum_track, RIMSHOT, EIGHTH, velocity=humanize(63), channel=ch_drum)
                add_note(drum_track, RIDE, EIGHTH, velocity=humanize(65), channel=ch_drum)
            # "and" of each beat — ride continues
            add_note(drum_track, RIDE, EIGHTH, velocity=humanize(55), channel=ch_drum)
    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- KEYS: Rhodes Em7 arpeggio (rain-like) ---
    keys_track = make_track("Keys", bpm)
    # Em7 arpeggio: E3(52), B3(59), D4(62), G4(67)
    # The rain pattern: descending arpeggiated, repeated
    arp_notes = [67, 62, 59, 52]  # G4, D4, B3, E3 — descending rain drops
    for bar in range(bars):
        if bar % 2 == 0:
            # Descending arpeggio pattern
            for i, n in enumerate(arp_notes):
                vel = humanize(72 - i * 3)  # Getting softer as it descends
                add_note(keys_track, n, QUARTER, velocity=vel, channel=ch_keys)
        else:
            # Ascending return
            for i, n in enumerate(reversed(arp_notes)):
                vel = humanize(65 + i * 3)
                add_note(keys_track, n, QUARTER, velocity=vel, channel=ch_keys)
    keys_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS: Walking bass in Em ---
    bass_track = make_track("Bass", bpm)
    # E2=40, G2=43, A2=45, B2=47, D3=50
    walk_patterns = [
        [40, 43, 45, 47],  # E G A B
        [47, 45, 43, 40],  # B A G E (descending)
        [40, 43, 45, 50],  # E G A D
        [50, 47, 45, 40],  # D B A E
    ]
    for bar in range(bars):
        pattern = walk_patterns[bar % len(walk_patterns)]
        for n in pattern:
            vel = humanize(88)
            add_note(bass_track, n, QUARTER, velocity=vel, channel=ch_bass)
    bass_track.append(MetaMessage('end_of_track', time=0))

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(keys_track, bpm, os.path.join(folder, "keys.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, keys_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Riders on the Storm", "The Doors", bpm, "Em", bars, 3,
              ["drums", "keys", "bass"])
    print(f"  [OK] Riders on the Storm")


# ============================================================
# 4. THE DOORS - LIGHT MY FIRE
# ============================================================
def generate_light_my_fire():
    import random
    random.seed(45)
    folder = os.path.join(BASE_DIR, "the_doors_light_my_fire")
    ensure_dir(folder)
    bpm = 130
    bars = 16
    ch_drum = 9
    ch_keys = 0
    ch_bass = 2

    # --- DRUMS: Bossa nova inspired ---
    drum_track = make_track("Drums", bpm)
    for bar in range(bars):
        for beat in range(4):
            if beat == 0:
                # Kick on 1
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(90), channel=ch_drum)
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=humanize(85), channel=ch_drum)
            elif beat == 1:
                # Rimclick on 2
                add_note(drum_track, RIMSHOT, EIGHTH, velocity=humanize(60), channel=ch_drum)
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=humanize(75), channel=ch_drum)
            elif beat == 2:
                # Kick on 3
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(85), channel=ch_drum)
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=humanize(80), channel=ch_drum)
            elif beat == 3:
                # Rimclick on 4
                add_note(drum_track, RIMSHOT, EIGHTH, velocity=humanize(58), channel=ch_drum)
                add_note(drum_track, RIDE_BELL, EIGHTH, velocity=humanize(78), channel=ch_drum)
            # Ride bell continues on "and"
            add_note(drum_track, RIDE_BELL, EIGHTH, velocity=humanize(60), channel=ch_drum)
    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- KEYS: Organ intro and arpeggios ---
    keys_track = make_track("Keys", bpm)
    # Intro: Am(57,60,64) -> G(55,59,62) -> F#m(54,57,61)
    # Then solo section arpeggios in Am
    Am = [57, 60, 64]   # A3, C4, E4
    G = [55, 59, 62]    # G3, B3, D4
    Fsm = [54, 57, 61]  # F#3, A3, C#4

    for bar in range(bars):
        if bar < 4:
            # Intro chord progression: Am for 2 bars, G for 1, F#m for 1
            if bar < 2:
                chord = Am
            elif bar == 2:
                chord = G
            else:
                chord = Fsm
            # Arpeggiated chord
            for i, n in enumerate(chord):
                add_note(keys_track, n, QUARTER, velocity=humanize(82), time=0 if i > 0 else 0,
                         channel=ch_keys)
            # Hold for remaining duration
            keys_track.append(Message('note_on', note=0, velocity=0, time=QUARTER, channel=ch_keys))
            keys_track.append(Message('note_off', note=0, time=0, channel=ch_keys))
        elif bar < 8:
            # Am arpeggio pattern (organ solo feel)
            arp = [57, 60, 64, 67, 64, 60, 57, 60]  # A C E G E C A C
            for n in arp:
                add_note(keys_track, n, EIGHTH, velocity=humanize(78), channel=ch_keys)
        elif bar < 12:
            # G arpeggio
            arp = [55, 59, 62, 67, 62, 59, 55, 59]  # G B D G D B G B
            for n in arp:
                add_note(keys_track, n, EIGHTH, velocity=humanize(80), channel=ch_keys)
        else:
            # F#m to Am resolution
            if bar % 2 == 0:
                arp = [54, 57, 61, 66, 61, 57, 54, 57]
            else:
                arp = [57, 60, 64, 69, 64, 60, 57, 60]
            for n in arp:
                add_note(keys_track, n, EIGHTH, velocity=humanize(82), channel=ch_keys)
    keys_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS: Root following chord changes ---
    bass_track = make_track("Bass", bpm)
    # A2=45, G2=43, F#2=42
    for bar in range(bars):
        if bar % 4 < 2:
            root = 45  # A2
        elif bar % 4 == 2:
            root = 43  # G2
        else:
            root = 42  # F#2
        # 8th note movement with passing tones
        for eighth in range(8):
            if eighth % 4 == 0:
                add_note(bass_track, root, EIGHTH, velocity=humanize(92), channel=ch_bass)
            elif eighth % 4 == 2:
                add_note(bass_track, root + 7, EIGHTH, velocity=humanize(85), channel=ch_bass)  # fifth
            else:
                add_note(bass_track, root, EIGHTH, velocity=humanize(78), channel=ch_bass)
    bass_track.append(MetaMessage('end_of_track', time=0))

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(keys_track, bpm, os.path.join(folder, "keys.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, keys_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Light My Fire", "The Doors", bpm, "Am/G", bars, 4,
              ["drums", "keys", "bass"])
    print(f"  [OK] Light My Fire")


# ============================================================
# 5. JIMI HENDRIX - PURPLE HAZE
# ============================================================
def generate_purple_haze():
    import random
    random.seed(46)
    folder = os.path.join(BASE_DIR, "jimi_hendrix_purple_haze")
    ensure_dir(folder)
    bpm = 108
    bars = 16
    ch_drum = 9
    ch_guitar = 1
    ch_bass = 2

    # --- DRUMS: Mitch Mitchell style ---
    drum_track = make_track("Drums", bpm)
    for bar in range(bars):
        for beat in range(4):
            if beat == 0:
                # Kick (loose)
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(95), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(85), channel=ch_drum)
                # Crash on phrase starts (bars 1, 5, 9, 13)
                if bar % 4 == 0:
                    add_note(drum_track, CRASH, EIGHTH, velocity=humanize(105), time=0, channel=ch_drum)
            elif beat == 1:
                # Crisp snare on 2
                add_note(drum_track, SNARE, EIGHTH, velocity=humanize(108), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(80), channel=ch_drum)
            elif beat == 2:
                # Kick variation
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(88), channel=ch_drum)
                add_note(drum_track, HAT_OPEN, EIGHTH, velocity=humanize(90), channel=ch_drum)
            elif beat == 3:
                # Snare on 4
                add_note(drum_track, SNARE, EIGHTH, velocity=humanize(110), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(78), channel=ch_drum)
            # Mitchell-style offbeat accents
            add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(65), channel=ch_drum)
    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR: Tritone intro + E7#9 ---
    guitar_track = make_track("Guitar", bpm)
    # The ICONIC intro: Bb3(58) to E4(64) — the tritone
    # Then E7#9 chord (the "Hendrix chord"): E4(64), G#4(68), B4(71), D5(74), G5(79)
    # Power chord riff: E-G-A = E4(64), G4(67), A4(69)
    Bb3, E4, Gs4, B4, D5 = 58, 64, 68, 71, 74

    for bar in range(bars):
        if bar < 2:
            # TRITONE INTRO: Bb3 to E4
            # Bb3 for a dotted quarter
            add_note(guitar_track, Bb3, QUARTER + EIGHTH, velocity=humanize(110), channel=ch_guitar)
            # E4 answer
            add_note(guitar_track, E4, QUARTER + EIGHTH, velocity=humanize(112), channel=ch_guitar)
            # Quick Bb-E again
            add_note(guitar_track, Bb3, EIGHTH, velocity=humanize(105), channel=ch_guitar)
            add_note(guitar_track, E4, EIGHTH, velocity=humanize(108), channel=ch_guitar)
        elif bar < 8:
            # E7#9 chord stabs (the "Hendrix chord")
            hendrix_chord = [64, 68, 71, 74]  # E4, G#4, B4, D5
            # Stab on beat 1
            for n in hendrix_chord:
                guitar_track.append(note_on(n, humanize(105), time=0, channel=ch_guitar))
            for n in hendrix_chord:
                guitar_track.append(note_off(n, time=EIGHTH if n == hendrix_chord[-1] else 0,
                                             channel=ch_guitar))
            # Rest
            guitar_track.append(Message('note_on', note=0, velocity=0, time=EIGHTH, channel=ch_guitar))
            guitar_track.append(Message('note_off', note=0, time=0, channel=ch_guitar))
            # Stab on beat 2+
            for n in hendrix_chord:
                guitar_track.append(note_on(n, humanize(100), time=0, channel=ch_guitar))
            for n in hendrix_chord:
                guitar_track.append(note_off(n, time=EIGHTH if n == hendrix_chord[-1] else 0,
                                             channel=ch_guitar))
            # Power chord riff E-G-A for beats 3-4
            add_note(guitar_track, 64, EIGHTH, velocity=humanize(100), channel=ch_guitar)  # E
            add_note(guitar_track, 67, EIGHTH, velocity=humanize(98), channel=ch_guitar)   # G
            add_note(guitar_track, 69, QUARTER, velocity=humanize(105), channel=ch_guitar)  # A
            add_note(guitar_track, 67, EIGHTH, velocity=humanize(95), channel=ch_guitar)   # G
            add_note(guitar_track, 64, EIGHTH, velocity=humanize(100), channel=ch_guitar)  # E
        else:
            # Power chord riff variation: E-G-A repeated
            riff = [64, 67, 69, 67, 64, 67, 69, 64]
            for n in riff:
                add_note(guitar_track, n, EIGHTH, velocity=humanize(100), channel=ch_guitar)
    guitar_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS: Root following guitar ---
    bass_track = make_track("Bass", bpm)
    # E2=40, octave jump E3=52
    E2, E3 = 40, 52
    G2, A2 = 43, 45
    for bar in range(bars):
        if bar < 2:
            # Tritone support: Bb1(34) to E2(40)
            add_note(bass_track, 34, HALF, velocity=humanize(95), channel=ch_bass)
            add_note(bass_track, E2, HALF, velocity=humanize(100), channel=ch_bass)
        elif bar % 2 == 0:
            # E2 with octave jumps, locked with kick
            add_note(bass_track, E2, EIGHTH, velocity=humanize(100), channel=ch_bass)
            add_note(bass_track, E2, EIGHTH, velocity=humanize(85), channel=ch_bass)
            add_note(bass_track, E3, EIGHTH, velocity=humanize(95), channel=ch_bass)  # octave jump
            add_note(bass_track, E2, EIGHTH, velocity=humanize(90), channel=ch_bass)
            add_note(bass_track, G2, EIGHTH, velocity=humanize(92), channel=ch_bass)
            add_note(bass_track, A2, EIGHTH, velocity=humanize(95), channel=ch_bass)
            add_note(bass_track, G2, EIGHTH, velocity=humanize(88), channel=ch_bass)
            add_note(bass_track, E2, EIGHTH, velocity=humanize(100), channel=ch_bass)
        else:
            # Simpler root pattern
            for eighth in range(8):
                if eighth % 2 == 0:
                    add_note(bass_track, E2, EIGHTH, velocity=humanize(95), channel=ch_bass)
                else:
                    add_note(bass_track, E2, EIGHTH, velocity=humanize(78), channel=ch_bass)
    bass_track.append(MetaMessage('end_of_track', time=0))

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, guitar_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Purple Haze", "Jimi Hendrix", bpm, "E", bars, 4,
              ["drums", "guitar", "bass"])
    print(f"  [OK] Purple Haze")


# ============================================================
# 6. JIMI HENDRIX - VOODOO CHILD (SLIGHT RETURN)
# ============================================================
def generate_voodoo_child():
    import random
    random.seed(47)
    folder = os.path.join(BASE_DIR, "jimi_hendrix_voodoo_child")
    ensure_dir(folder)
    bpm = 88
    bars = 16
    ch_drum = 9
    ch_guitar = 1
    ch_bass = 2

    # --- DRUMS: Heavy shuffle groove ---
    drum_track = make_track("Drums", bpm)
    for bar in range(bars):
        for beat in range(4):
            if beat == 0:
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(108), channel=ch_drum)
                add_note(drum_track, HAT_OPEN, EIGHTH, velocity=humanize(92), channel=ch_drum)
            elif beat == 1:
                # Snare backbeat
                add_note(drum_track, SNARE, EIGHTH, velocity=humanize(112), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(80), channel=ch_drum)
            elif beat == 2:
                # Kick with hat
                add_note(drum_track, KICK, EIGHTH, velocity=humanize(100), channel=ch_drum)
                add_note(drum_track, HAT_OPEN, EIGHTH, velocity=humanize(88), channel=ch_drum)
            elif beat == 3:
                # Snare backbeat
                add_note(drum_track, SNARE, EIGHTH, velocity=humanize(110), channel=ch_drum)
                add_note(drum_track, HAT_CLOSED, EIGHTH, velocity=humanize(82), channel=ch_drum)
            # Shuffle feel: triplet-ish offbeat
            add_note(drum_track, HAT_CLOSED, TRIPLET_8TH, velocity=humanize(60), channel=ch_drum)
            # Extra ghost note padding to fill the beat
            remaining = EIGHTH - TRIPLET_8TH
            if remaining > 0:
                drum_track.append(Message('note_on', note=SNARE, velocity=humanize(30, 5),
                                          time=remaining, channel=ch_drum))
                drum_track.append(Message('note_off', note=SNARE, time=0, channel=ch_drum))
    drum_track.append(MetaMessage('end_of_track', time=0))

    # --- GUITAR: Wah-wah riff in Eb ---
    guitar_track = make_track("Guitar", bpm)
    # Eb4=63, Db4=61, Bb3=58, Ab3=56 — descending blues
    # Then big bend up from Bb3 to Eb4
    Eb4, Db4, Bb3, Ab3 = 63, 61, 58, 56
    Eb3, Gb3 = 51, 54  # Lower octave notes

    for bar in range(bars):
        if bar % 4 < 2:
            # Main wah riff: descending Eb4-Db4-Bb3-Ab3
            add_note(guitar_track, Eb4, EIGHTH + SIXTEENTH, velocity=humanize(108), channel=ch_guitar)
            add_note(guitar_track, Db4, SIXTEENTH, velocity=humanize(100), channel=ch_guitar)
            add_note(guitar_track, Bb3, QUARTER, velocity=humanize(105), channel=ch_guitar)
            add_note(guitar_track, Ab3, EIGHTH, velocity=humanize(95), channel=ch_guitar)
            add_note(guitar_track, Bb3, EIGHTH, velocity=humanize(100), channel=ch_guitar)
            # The big bend: Bb3 held then slide to Eb4
            add_note(guitar_track, Bb3, QUARTER, velocity=humanize(110), channel=ch_guitar)
            add_note(guitar_track, Eb4, QUARTER, velocity=humanize(112), channel=ch_guitar)
        elif bar % 4 == 2:
            # Low register answer phrase
            add_note(guitar_track, Eb3, QUARTER, velocity=humanize(100), channel=ch_guitar)
            add_note(guitar_track, Gb3, EIGHTH, velocity=humanize(95), channel=ch_guitar)
            add_note(guitar_track, Ab3, EIGHTH, velocity=humanize(98), channel=ch_guitar)
            add_note(guitar_track, Bb3, HALF, velocity=humanize(105), channel=ch_guitar)
        else:
            # Eb power chord stabs: Eb4 + Bb4(70)
            Bb4 = 70
            guitar_track.append(note_on(Eb4, humanize(110), channel=ch_guitar))
            guitar_track.append(note_on(Bb4, humanize(108), time=0, channel=ch_guitar))
            guitar_track.append(note_off(Eb4, time=EIGHTH, channel=ch_guitar))
            guitar_track.append(note_off(Bb4, time=0, channel=ch_guitar))
            # Rest
            guitar_track.append(Message('note_on', note=0, velocity=0, time=EIGHTH, channel=ch_guitar))
            guitar_track.append(Message('note_off', note=0, time=0, channel=ch_guitar))
            # Another stab
            guitar_track.append(note_on(Eb4, humanize(105), channel=ch_guitar))
            guitar_track.append(note_on(Bb4, humanize(103), time=0, channel=ch_guitar))
            guitar_track.append(note_off(Eb4, time=EIGHTH, channel=ch_guitar))
            guitar_track.append(note_off(Bb4, time=0, channel=ch_guitar))
            # Fill
            add_note(guitar_track, Db4, EIGHTH, velocity=humanize(95), channel=ch_guitar)
            add_note(guitar_track, Eb4, QUARTER, velocity=humanize(100), channel=ch_guitar)
            add_note(guitar_track, Db4, EIGHTH, velocity=humanize(90), channel=ch_guitar)
            add_note(guitar_track, Bb3, EIGHTH, velocity=humanize(95), channel=ch_guitar)
    guitar_track.append(MetaMessage('end_of_track', time=0))

    # --- BASS: Eb2 with chromatic walk-ups ---
    bass_track = make_track("Bass", bpm)
    # Eb2=39, E2=40, F2=41, Gb2=42, Ab2=44, Bb2=46
    Eb2, E2_n, F2, Gb2, Ab2, Bb2 = 39, 40, 41, 42, 44, 46
    for bar in range(bars):
        if bar % 4 < 2:
            # Root Eb2 with chromatic walk up
            add_note(bass_track, Eb2, EIGHTH, velocity=humanize(100), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=humanize(85), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=humanize(90), channel=ch_bass)
            add_note(bass_track, E2_n, EIGHTH, velocity=humanize(88), channel=ch_bass)  # chromatic
            add_note(bass_track, F2, EIGHTH, velocity=humanize(92), channel=ch_bass)
            add_note(bass_track, Gb2, EIGHTH, velocity=humanize(95), channel=ch_bass)
            add_note(bass_track, Ab2, EIGHTH, velocity=humanize(98), channel=ch_bass)
            add_note(bass_track, Eb2, EIGHTH, velocity=humanize(100), channel=ch_bass)
        elif bar % 4 == 2:
            # Ab2 based
            add_note(bass_track, Ab2, QUARTER, velocity=humanize(95), channel=ch_bass)
            add_note(bass_track, Ab2, EIGHTH, velocity=humanize(82), channel=ch_bass)
            add_note(bass_track, Bb2, EIGHTH, velocity=humanize(88), channel=ch_bass)
            add_note(bass_track, Ab2, QUARTER, velocity=humanize(90), channel=ch_bass)
            add_note(bass_track, Eb2, QUARTER, velocity=humanize(95), channel=ch_bass)
        else:
            # Bb2 to Eb2 resolution
            add_note(bass_track, Bb2, QUARTER, velocity=humanize(95), channel=ch_bass)
            add_note(bass_track, Ab2, QUARTER, velocity=humanize(90), channel=ch_bass)
            add_note(bass_track, Gb2, QUARTER, velocity=humanize(88), channel=ch_bass)
            add_note(bass_track, Eb2, QUARTER, velocity=humanize(100), channel=ch_bass)
    bass_track.append(MetaMessage('end_of_track', time=0))

    # Save
    save_single_track(drum_track, bpm, os.path.join(folder, "drums.mid"))
    save_single_track(guitar_track, bpm, os.path.join(folder, "guitar.mid"))
    save_single_track(bass_track, bpm, os.path.join(folder, "bass.mid"))
    save_full([drum_track, guitar_track, bass_track], bpm, os.path.join(folder, "full.mid"))
    save_meta(folder, "Voodoo Child (Slight Return)", "Jimi Hendrix", bpm, "Eb", bars, 5,
              ["drums", "guitar", "bass"])
    print(f"  [OK] Voodoo Child (Slight Return)")


# ============================================================
# MAIN
# ============================================================
def main():
    print("Generating Group 1 MIDI files...")
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
    # List generated files
    for root, dirs, files in os.walk(BASE_DIR):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), BASE_DIR)
            size = os.path.getsize(os.path.join(root, f))
            print(f"  {rel} ({size} bytes)")


if __name__ == "__main__":
    main()
