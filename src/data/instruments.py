"""
Moonwolf Layers — Instrument role definitions.
Extracted from moonwolf_layers.py for modular import.
"""

# ======================== INSTRUMENT ROLES ========================
INSTRUMENT_ROLES = [
    {"name": "DRUMS",   "icon": "D", "midi_ch": 9,  "color": (255, 80, 50),  "desc": "Kick, snare, hats — the backbone"},
    {"name": "KEYS",    "icon": "K", "midi_ch": 0,  "color": (100, 200, 255), "desc": "Piano, synth pads, Rhodes"},
    {"name": "GUITAR",  "icon": "G", "midi_ch": 1,  "color": (255, 150, 0),   "desc": "Power chords, riffs, solos"},
    {"name": "BASS",    "icon": "B", "midi_ch": 2,  "color": (180, 0, 255),   "desc": "Low-end groove, slap, fingerstyle"},
    {"name": "HORNS",   "icon": "H", "midi_ch": 3,  "color": (255, 215, 0),   "desc": "Trumpet, sax, trombone stabs"},
    {"name": "STRINGS", "icon": "S", "midi_ch": 4,  "color": (0, 200, 150),   "desc": "Violin, cello, orchestral swells"},
    {"name": "VOCALS",  "icon": "V", "midi_ch": 5,  "color": (255, 100, 200), "desc": "Rap, sing, chant, harmonize"},
    {"name": "SYNTH",   "icon": "Y", "midi_ch": 6,  "color": (0, 255, 255),   "desc": "Lead synth, arps, FX sweeps"},
]
