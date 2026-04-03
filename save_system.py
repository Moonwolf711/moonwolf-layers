"""
save_system.py — Player profiles, XP/leveling, and custom character saves.

Saves to saves/ directory as JSON files. Each player gets a profile with:
- Custom character (name, animal base, colors, ability)
- XP, level, stats
- Unlocked abilities and cosmetics
"""

import os
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES_DIR = os.path.join(BASE_DIR, "saves")

# XP curve: level N requires XP_BASE * N^XP_POWER total XP
XP_BASE = 100
XP_POWER = 1.5

# What you earn
XP_PER_HIT = 5
XP_PER_PERFECT = 15
XP_PER_GREAT = 10
XP_PER_GOOD = 5
XP_PER_COMBO_10 = 50
XP_PER_STAR_POWER = 100
XP_PER_LEVEL_COMPLETE = 200
XP_GRADE_BONUS = {"S": 500, "A": 300, "B": 150, "C": 50, "D": 0, "F": 0}

# Unlockable abilities at each level
LEVEL_UNLOCKS = {
    1:  "combo_shield",      # Dog's ability
    3:  "precision",         # Wolf's ability
    5:  "speed_boost",       # Fox's ability
    7:  "star_fill",         # Cat's ability
    10: "predator",          # Puma's ability
    13: "venom",             # Snake's ability
    15: "soar",              # Eagle's ability
    18: "fury",              # Tiger's ability
    20: "agile",             # Monkey's ability
    23: "tank",              # Gorilla's ability
    25: "frenzy",            # Shark's ability
    28: "rage",              # Minotaur's ability
    30: "flight",            # Pegasus's ability
    33: "shell",             # Turtle's ability
}

# Unlockable color palettes
COLOR_PALETTES = {
    "default":  {"label": "Default",       "level": 0},
    "neon":     {"label": "Neon Glow",     "level": 2},
    "fire":     {"label": "Fire",          "level": 6},
    "ice":      {"label": "Ice",           "level": 8},
    "shadow":   {"label": "Shadow",        "level": 12},
    "gold":     {"label": "Golden",        "level": 16},
    "phantom":  {"label": "Phantom",       "level": 22},
    "cosmic":   {"label": "Cosmic",        "level": 27},
    "rainbow":  {"label": "Rainbow",       "level": 35},
}

PALETTE_OVERRIDES = {
    "neon":    {'B': (0,255,200), 'E': (0,255,255), 'W': (200,255,240), 'T': (0,255,150)},
    "fire":    {'B': (255,100,0), 'E': (255,50,0),  'W': (255,200,50),  'T': (255,150,0)},
    "ice":     {'B': (100,180,255),'E': (150,200,255),'W': (220,240,255),'T': (80,160,255)},
    "shadow":  {'B': (30,30,40),  'E': (50,50,60),  'W': (80,80,100),   'T': (40,40,55)},
    "gold":    {'B': (220,180,50),'E': (255,215,0),  'W': (255,240,150),'T': (200,160,30)},
    "phantom": {'B': (150,80,200),'E': (180,100,255),'W': (220,180,255),'T': (130,60,180)},
    "cosmic":  {'B': (80,0,150),  'E': (150,0,255),  'W': (200,150,255),'T': (100,0,200)},
    "rainbow": {'B': (255,100,100),'E': (100,255,100),'W': (100,100,255),'T': (255,255,0)},
}


def xp_for_level(level):
    """Total XP needed to reach a given level."""
    if level <= 1:
        return 0
    return int(XP_BASE * (level ** XP_POWER))


def level_from_xp(xp):
    """What level are you at with this much XP?"""
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def xp_progress(xp):
    """Returns (current_level, xp_into_level, xp_needed_for_next)."""
    level = level_from_xp(xp)
    current_threshold = xp_for_level(level)
    next_threshold = xp_for_level(level + 1)
    return level, xp - current_threshold, next_threshold - current_threshold


def unlocked_abilities(level):
    """Return list of ability names unlocked at this level."""
    return [ability for req_level, ability in LEVEL_UNLOCKS.items() if level >= req_level]


def unlocked_palettes(level):
    """Return list of palette names unlocked at this level."""
    return [name for name, info in COLOR_PALETTES.items() if level >= info["level"]]


def _ensure_saves_dir():
    os.makedirs(SAVES_DIR, exist_ok=True)


def new_profile(name, animal_base="wolf", color_palette="default"):
    """Create a new player profile dict."""
    return {
        "name": name,
        "animal_base": animal_base,
        "color_palette": color_palette,
        "custom_ability": None,
        "xp": 0,
        "level": 1,
        "games_played": 0,
        "total_hits": 0,
        "total_perfects": 0,
        "total_score": 0,
        "best_combo": 0,
        "best_grade": "F",
        "songs_completed": [],
        "created": time.time(),
        "last_played": time.time(),
    }


def save_profile(profile):
    """Save profile to disk. Filename based on name."""
    _ensure_saves_dir()
    filename = profile["name"].lower().replace(" ", "_") + ".json"
    filepath = os.path.join(SAVES_DIR, filename)
    # Update level from XP
    profile["level"] = level_from_xp(profile["xp"])
    profile["last_played"] = time.time()
    with open(filepath, "w") as f:
        json.dump(profile, f, indent=2)
    return filepath


def load_profile(name):
    """Load a profile by name."""
    filename = name.lower().replace(" ", "_") + ".json"
    filepath = os.path.join(SAVES_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)


def list_profiles():
    """Return list of all saved profiles, sorted by last played."""
    _ensure_saves_dir()
    profiles = []
    for fn in os.listdir(SAVES_DIR):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(SAVES_DIR, fn), "r") as f:
                    p = json.load(f)
                    profiles.append(p)
            except (json.JSONDecodeError, KeyError):
                continue
    profiles.sort(key=lambda p: p.get("last_played", 0), reverse=True)
    return profiles


def delete_profile(name):
    """Delete a profile by name."""
    filename = name.lower().replace(" ", "_") + ".json"
    filepath = os.path.join(SAVES_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def award_xp(profile, hits=0, perfects=0, greats=0, goods=0,
             combo_10s=0, star_powers=0, levels_complete=0, grade="F"):
    """Award XP to a profile based on gameplay results. Returns XP earned."""
    earned = 0
    earned += hits * XP_PER_HIT
    earned += perfects * XP_PER_PERFECT
    earned += greats * XP_PER_GREAT
    earned += goods * XP_PER_GOOD
    earned += combo_10s * XP_PER_COMBO_10
    earned += star_powers * XP_PER_STAR_POWER
    earned += levels_complete * XP_PER_LEVEL_COMPLETE
    earned += XP_GRADE_BONUS.get(grade, 0)

    old_level = level_from_xp(profile["xp"])
    profile["xp"] += earned
    new_level = level_from_xp(profile["xp"])
    profile["level"] = new_level

    leveled_up = new_level > old_level
    new_unlocks = []
    if leveled_up:
        for lvl in range(old_level + 1, new_level + 1):
            if lvl in LEVEL_UNLOCKS:
                new_unlocks.append(LEVEL_UNLOCKS[lvl])

    return {
        "xp_earned": earned,
        "leveled_up": leveled_up,
        "old_level": old_level,
        "new_level": new_level,
        "new_unlocks": new_unlocks,
    }


def apply_palette_override(base_palette, palette_name):
    """Apply a color palette override to a base character palette."""
    if palette_name == "default" or palette_name not in PALETTE_OVERRIDES:
        return dict(base_palette)
    result = dict(base_palette)
    overrides = PALETTE_OVERRIDES[palette_name]
    for key, color in overrides.items():
        if key in result and result[key] is not None:
            result[key] = color
    return result


# Quick test
if __name__ == "__main__":
    print("Save System Test")
    print("=" * 40)

    # XP curve
    for lvl in [1, 5, 10, 15, 20, 25, 30, 35]:
        print(f"  Level {lvl:2d}: {xp_for_level(lvl):,} XP required")

    print()
    print("Level unlocks:")
    for lvl, ability in sorted(LEVEL_UNLOCKS.items()):
        print(f"  Level {lvl:2d}: {ability}")

    print()
    print("Color palettes:")
    for name, info in sorted(COLOR_PALETTES.items(), key=lambda x: x[1]["level"]):
        print(f"  Level {info['level']:2d}: {info['label']} ({name})")

    # Test profile
    p = new_profile("TestPlayer", "wolf")
    result = award_xp(p, hits=50, perfects=20, greats=15, goods=10, combo_10s=3, levels_complete=2, grade="A")
    print(f"\nTest: {result['xp_earned']} XP earned, level {result['old_level']} -> {result['new_level']}")
    print(f"  Unlocks: {result['new_unlocks']}")
