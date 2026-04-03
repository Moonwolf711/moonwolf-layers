"""
Moonwolf Layers — Global constants and configuration values.
Extracted from moonwolf_layers.py for modular import.
"""

# ======================== CONFIG ========================
WIDTH, HEIGHT = 1280, 720
FPS = 60
TILE = 16

# Colors
C_BG         = (8, 8, 24)
C_GROUND     = (20, 15, 40)
C_GROUND_TOP = (80, 40, 120)
C_BUILDING   = (15, 12, 30)
C_NEON_CYAN  = (0, 255, 255)
C_NEON_PINK  = (255, 0, 200)
C_NEON_GREEN = (0, 255, 100)
C_NEON_YELLOW= (255, 255, 0)
C_ENEMY      = (255, 50, 50)
C_HUD        = (0, 200, 255)
C_HUD_DIM    = (0, 80, 120)
C_STAR_GOLD  = (255, 215, 0)
C_LANE_BG    = (15, 10, 30)
C_LANE_LINE  = (40, 30, 60)

# Hit timing windows (pixels from hit line)
HIT_PERFECT = 15
HIT_GREAT   = 30
HIT_GOOD    = 50
HIT_MISS    = 60  # Beyond this = miss

# Combo multiplier thresholds
MULT_THRESHOLDS = [(40, 8), (20, 4), (10, 2), (0, 1)]  # (combo_min, multiplier)

# Grade thresholds (percentage)
GRADES = [
    (95, "S", C_STAR_GOLD),
    (90, "A", C_NEON_GREEN),
    (80, "B", C_NEON_CYAN),
    (70, "C", C_NEON_YELLOW),
    (60, "D", C_NEON_PINK),
    (0,  "F", C_ENEMY),
]

# Star power
STAR_POWER_THRESHOLD = 15  # Combo needed to activate star power
STAR_POWER_BARS = 8        # How many bars star power lasts

# Drum notes (GM)
KICK = 36; SNARE = 38; HAT = 42; OHAT = 46; CRASH = 49; RIDE = 51; LTOM = 45; HTOM = 48
DRUM_CH = 9

# Fighting Edge button -> drum lane mapping
# Sq=Kick X=Snare O=HiHat Tri=OpenHH L1=Crash R1=Ride L2=LowTom R2=HighTom
FE_DRUM_MAP = {
    0: (KICK,  "KICK",  (255, 80, 50)),
    1: (SNARE, "SNARE", (255, 220, 50)),
    2: (HAT,   "HH",    (50, 255, 150)),
    3: (OHAT,  "OH",    (50, 200, 255)),
    4: (CRASH, "CRASH", (255, 100, 255)),
    5: (RIDE,  "RIDE",  (150, 150, 255)),
    6: (LTOM,  "LTOM",  (255, 150, 50)),
    7: (HTOM,  "HTOM",  (200, 80, 200)),
}

# Music
CIRCLE = ["C","G","D","A","E","B","F#","Db","Ab","Eb","Bb","F"]
ROOT_MIDI = {"C":60,"G":55,"D":62,"A":57,"E":64,"B":59,"F#":66,"Db":61,"Ab":56,"Eb":63,"Bb":58,"F":65}
MAJOR_INT = [0,2,4,5,7,9,11]
MINOR_INT = [0,2,3,5,7,8,10]

# ======================== ABLETON TRANSPORT CONTROL ========================
# These CCs are sent to control Ableton. MIDI-learn them in Ableton:
#   CC 117 -> Session Record button (or Arrangement Record)
#   CC 118 -> Stop button
#   CC 119 -> Play button
# In Ableton: Preferences > Record > Record Quantization = 1/16 for auto-quantize
TRANSPORT_CC_PLAY = 119
TRANSPORT_CC_STOP = 118
TRANSPORT_CC_RECORD = 117
