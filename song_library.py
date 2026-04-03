"""
song_library.py — Song loader module for Moonwolf Layers
Scans songs/ directory, loads metadata, provides per-instrument MIDI data.

Usage:
    from song_library import get_song_list, load_song

    songs = get_song_list()
    for s in songs:
        print(f"{s['artist']} - {s['title']} (difficulty {s['difficulty']})")

    song_data = load_song("hysteria")
    for inst, midi in song_data["tracks"].items():
        print(f"  {inst}: {len(midi.tracks)} tracks, {midi.length:.1f}s")
"""

import os
import json
import mido

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_DIR = os.path.join(BASE_DIR, "songs")


def _scan_songs():
    """Scan the songs/ directory and return a dict of {folder_name: meta_dict}."""
    songs = {}
    if not os.path.isdir(SONGS_DIR):
        return songs
    for entry in os.listdir(SONGS_DIR):
        song_path = os.path.join(SONGS_DIR, entry)
        meta_path = os.path.join(song_path, "meta.json")
        if os.path.isdir(song_path) and os.path.isfile(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                meta["folder"] = entry
                # Discover available MIDI files
                midi_files = [fn for fn in os.listdir(song_path) if fn.endswith(".mid")]
                meta["midi_files"] = midi_files
                songs[entry] = meta
            except (json.JSONDecodeError, KeyError):
                continue
    return songs


def get_song_list():
    """
    Return a sorted list of available songs with metadata.
    Each entry: {title, artist, difficulty, folder, bpm, key, bars, instruments}
    Sorted by artist then title.
    """
    songs = _scan_songs()
    result = []
    for folder, meta in songs.items():
        result.append({
            "title": meta.get("title", folder),
            "artist": meta.get("artist", "Unknown"),
            "difficulty": meta.get("difficulty", 1),
            "folder": folder,
            "bpm": meta.get("bpm"),
            "key": meta.get("key"),
            "bars": meta.get("bars"),
            "instruments": meta.get("instruments", []),
        })
    result.sort(key=lambda s: (s["artist"], s["title"]))
    return result


def load_song(song_name):
    """
    Load a song by folder name. Returns a dict with:
      - "meta": full metadata dict
      - "tracks": {instrument_name: mido.MidiFile} for each per-instrument MIDI
      - "full": mido.MidiFile of the combined full.mid (or None)

    Instrument names are derived from filenames: drums.mid -> "drums", etc.
    """
    song_path = os.path.join(SONGS_DIR, song_name)
    meta_path = os.path.join(song_path, "meta.json")

    if not os.path.isdir(song_path):
        raise FileNotFoundError(f"Song folder not found: {song_name}")
    if not os.path.isfile(meta_path):
        raise FileNotFoundError(f"No meta.json in song: {song_name}")

    with open(meta_path, "r") as f:
        meta = json.load(f)

    tracks = {}
    full_mid = None

    for fn in os.listdir(song_path):
        if not fn.endswith(".mid"):
            continue
        fpath = os.path.join(song_path, fn)
        mid = mido.MidiFile(fpath)
        inst_name = os.path.splitext(fn)[0]  # "drums", "bass", "guitar", "keys", "full"
        if inst_name == "full":
            full_mid = mid
        else:
            tracks[inst_name] = mid

    return {
        "meta": meta,
        "tracks": tracks,
        "full": full_mid,
    }


def get_song_notes(song_name, instrument):
    """
    Extract note events from a specific instrument track.
    Returns a list of dicts: [{note, velocity, start_tick, end_tick, channel}, ...]
    Useful for the game to build note highways from.
    """
    song_data = load_song(song_name)
    if instrument not in song_data["tracks"]:
        available = list(song_data["tracks"].keys())
        raise KeyError(f"Instrument '{instrument}' not found. Available: {available}")

    mid = song_data["tracks"][instrument]
    notes = []
    # Track active note-on events to pair with note-off
    active = {}  # (channel, note) -> {start_tick, velocity}
    abs_tick = 0

    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                key = (msg.channel, msg.note)
                active[key] = {"start_tick": abs_tick, "velocity": msg.velocity}
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in active:
                    start_info = active.pop(key)
                    notes.append({
                        "note": msg.note,
                        "velocity": start_info["velocity"],
                        "start_tick": start_info["start_tick"],
                        "end_tick": abs_tick,
                        "channel": msg.channel,
                    })

    notes.sort(key=lambda n: n["start_tick"])
    return notes


# Quick test when run directly
if __name__ == "__main__":
    print("Song Library - Available Songs")
    print("=" * 60)
    songs = get_song_list()
    if not songs:
        print("  No songs found in songs/ directory.")
        print("  Run generate_songs_group3.py first.")
    else:
        for s in songs:
            diff_stars = "*" * s["difficulty"]
            instruments = ", ".join(s["instruments"])
            print(f"  {s['artist']:20s} - {s['title']:30s} [{diff_stars:5s}] {s['bpm']} BPM {s['key']}")
            print(f"  {'':20s}   Instruments: {instruments}")
        print()
        print(f"Total: {len(songs)} songs")

        # Test loading first song
        print()
        first = songs[0]
        print(f"Loading '{first['title']}'...")
        data = load_song(first["folder"])
        for inst, mid in data["tracks"].items():
            note_count = sum(1 for track in mid.tracks for msg in track if msg.type == "note_on")
            print(f"  {inst}: {note_count} notes")
        if data["full"]:
            note_count = sum(1 for track in data["full"].tracks for msg in track if msg.type == "note_on")
            print(f"  full: {note_count} notes total")
