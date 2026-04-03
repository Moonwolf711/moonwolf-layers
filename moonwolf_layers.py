"""
Moonwolf Layers v2.0 — Layered Loop Music Game
Each level = one instrument. Complete it, it loops. Next level adds on top.
Two players: Joystick steers melody, Fighting Edge hits drums.
Star Power = freestyle riff mode when combo is high enough.

Level 1: 16-bar drum loop (Fighting Edge buttons = drum lanes)
Level 2: Melody phrase (Joystick steers through notes)
Level 3+: Additional instruments stack on top

Usage:
  python moonwolf_layers.py --midi seven_nation_army.mid --port "FE Bridge"
  python moonwolf_layers.py --bpm 124 --port "FE Bridge"
"""

import sys
import os
import math
import time
import random
import threading
import numpy as np
import pygame
import mido

# Add project dir to path for song_library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from song_library import get_song_list, load_song
import save_system

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

STAR_POWER_THRESHOLD = 15  # Combo needed to activate star power
STAR_POWER_BARS = 8        # How many bars star power lasts

# ======================== SPRITES ========================
def make_sprite(pixels, palette, scale=3):
    lines = [l for l in pixels.strip().split('\n') if l.strip()]
    h = len(lines)
    w = max(len(l) for l in lines)
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch in palette and palette[ch] is not None:
                pygame.draw.rect(surf, palette[ch], (x*scale, y*scale, scale, scale))
    return surf

# Wolf — pointy upright ears, thick neck/shoulders, fierce stance, grey/silver, bushy tail
SPRITE_WOLF = """
.EE........EE.
.EEEE....EEEE.
..EEWW..WWE...
..EWWWWWWWE...
..EWWWWWWWWE..
.DECCWWWWCCED.
.DECCCNNCCCCD.
..DDWWNNWWDD..
..DDBBBBBBD...
..DBBBBBBBD...
.DDBBBBBBBDD..
..DDPPPPPDD...
...DPPDDPPD...
...DPPDDPPD.TT
...DD..DD..TTT
..DD....DD.TT.
"""

# Fox — tall narrow pointed ears, slim/sleek body, LARGE bushy tail, orange with white chest
SPRITE_FOX = """
..E........E..
..EE......EE..
..EEE....EEE..
...EWWWWWE....
...EWWWWWWE...
..DECCWWCCED..
..DECCNNCCDD..
...DWWNNWWD...
...DWWWWWD....
....DBBBD.....
....DWWWD...TT
....DPPD...TTT
....DPPD..TTTT
...DD..DD.TTTT
...DD..DD..TTT
..DD....DD..T.
"""

# Cat — small rounded ears, lithe slim body, long curved tail, whisker dots, arched back
SPRITE_CAT = """
...DEE..EED...
...DEEEEEED...
...EWWWWWWE...
..DEWWWWWWED..
.W.ECCWWCCE.W.
.W.DCCNNCCDD..
...DWWNNWWD...
....DBBBD.....
...DBBBBBD....
..DBBBBBD.....
..DDBBBDD.....
...DPPDD......
...DPP.DPD....
..DD...DDDT...
..D.....DDTT..
.DD......DTT..
"""

# Dog — one ear up one floppy, stocky/sturdy, tongue out (T), wagging tail, friendly
SPRITE_DOG = """
.EEE....EEEE..
.EEEE..EEEEED.
..EEWWWWWEED..
..EWWWWWWWE...
..EWWWWWWWWE..
.DECCWWWWCCED.
.DECCNNNNCCED.
..DWWNNTNNWD..
..DDWWWWTDDD..
..DDBBBBBBD...
..DBBBBBBBD.T.
.DDBBBBBBBDTT.
..DDPPPPPDD.T.
...DPPDDPPD...
...DD..DDDD...
..DD....DD....
"""

# Puma — sleek powerful build, small rounded ears, long sweeping tail, muscular
SPRITE_PUMA = """
..DEE....EED..
..DEWW..WWED..
...DWWWWWWD...
..DCCWWWWCCD..
...DWWNNWWD...
...DBBBBBBD...
..DBBBBBBBD...
..DBBBBBBBBD..
...DPPDDPPD...
...DPPD.DPPD..
..DPP....DPP.T
..DD......DD.TT
.............TTT
"""

# Base palettes per character — E=ears, W=face, C=eyes, N=nose/mouth, B=body, P=legs, D=outline, T=tail/tongue
PALETTE_WOLF = {'E': (130,130,150), 'W': (195,195,210), 'C': (0,255,255),  'N': (40,30,40),  'B': (150,150,170), 'D': (50,40,60),  'P': (70,65,80),  'T': (160,160,175), '.': None}
PALETTE_FOX  = {'E': (220,120,30),  'W': (255,255,240), 'C': (50,200,50),  'N': (30,20,20),  'B': (230,140,40),  'D': (90,45,15),  'P': (70,35,10),  'T': (245,170,50),  '.': None}
PALETTE_CAT  = {'E': (70,70,85),    'W': (210,210,220), 'C': (255,215,0),  'N': (255,140,160),'B': (170,170,185), 'D': (40,40,50),  'P': (55,55,65),  'T': (170,170,185), '.': None}
PALETTE_DOG  = {'E': (160,105,55),  'W': (215,175,115), 'C': (60,40,25),   'N': (45,25,15),   'B': (190,140,75),  'D': (70,45,25),  'P': (65,45,25),  'T': (230,70,70),   '.': None}
PALETTE_PUMA = {'E': (180,150,100), 'W': (210,180,130), 'C': (180,220,0),  'N': (50,35,25),   'B': (190,155,95),  'D': (65,45,25),  'P': (75,55,30),  'T': (175,140,85),  '.': None}

# Snake — long sinuous body, no legs, forked tongue, coiled
SPRITE_SNAKE = """
..............
....DDDD......
...DWWWWD.....
..DCCWWCCD....
...DWNNWD.TT..
....DBBBD.....
...DBBBD......
..DBBBD.......
...DBBBD......
....DBBBD.....
...DBBBD......
..DBBBD.......
...DDDD.......
"""

# Eagle — wings spread wide, sharp beak, talons, majestic
SPRITE_EAGLE = """
.E............E
.EE..........EE
..EEB....BEE...
...EBBBBBBE....
....DWWWWD.....
...DCCWWCCD....
....DWNNWD.....
.....DBBBD.....
.....DBBBD.....
......DPD......
.....DP.PD.....
....DPP.PPD....
"""

# Tiger — bold stripes on body, powerful build, long tail
SPRITE_TIGER = """
..DEE....EED..
..DEWW..WWED..
...DWWWWWWD...
..DCCWWWWCCD..
...DWWNNWWD...
..DBTBTBTBD...
..DBTBTBTBD...
..DBTBTBTBBD..
...DPPDDPPD...
...DPP..DPP..T
..DPP....DPP.TT
..DD......DDTTT
"""

PALETTE_SNAKE = {'E': (40,80,30),   'W': (80,150,50),  'C': (255,50,0),   'N': (50,30,20),   'B': (60,120,40),   'D': (25,50,20),  'P': (60,120,40), 'T': (255,50,50),  '.': None}
PALETTE_EAGLE = {'E': (100,70,40),  'W': (240,230,210), 'C': (255,180,0),  'N': (200,160,50), 'B': (80,55,30),    'D': (40,30,20),  'P': (200,170,50),'T': None,         '.': None}
PALETTE_TIGER = {'E': (220,150,30), 'W': (240,190,80), 'C': (100,200,50), 'N': (50,30,20),   'B': (230,160,40),  'D': (60,35,15),  'P': (80,50,20),  'T': (220,150,30), '.': None}

# Monkey — long arms, curled tail, round face, playful
SPRITE_MONKEY = """
.....DDDD.....
....DWWWWD....
.EE.DWWWWD.EE.
.EWE.CCCC.EWE.
....DWNNWD....
....DBBBBD....
..BDDBBDDBB..
..B..DPPD..B..
..B..DPPD..B..
.....D..D...TT
....DD..DD.TTT
...........TT.
"""

# Gorilla — massive shoulders, small ears, huge arms, powerful
SPRITE_GORILLA = """
..DEE....EED..
..DWWWWWWWD...
..DWWWWWWWD...
..DCCWWWCCD...
...DWNNWD.....
.BBBBBBBBBBB..
BBDBBBBBBBDBB.
BB.DBBBBBD.BB.
BB..DPPPPD..BB
....DPPPPPD...
....DPP.PPD...
...DPP...PPD..
"""

PALETTE_MONKEY = {'E': (160,120,80), 'W': (200,170,120), 'C': (80,50,30),   'N': (140,100,60), 'B': (170,130,80),  'D': (60,40,25),  'P': (70,50,30),  'T': (160,120,70), '.': None}
PALETTE_GORILLA= {'E': (50,50,55),   'W': (80,80,90),    'C': (180,130,50), 'N': (40,35,35),   'B': (60,60,65),    'D': (30,30,35),  'P': (45,45,50),  'T': None,         '.': None}

# Shark — dorsal fin, sleek torpedo body, sharp teeth, no legs
SPRITE_SHARK = """
.......E......
......EE......
.....EEE......
....DDDDDD....
...DWWWWWWD...
..DCCWWWWCCD..
..DWWNNNWWD.TT
...DBBBBBD.TTT
....DBBBD.TT..
.....DBBD.....
......DD......
"""

PALETTE_SHARK = {'E': (80,100,130),  'W': (140,160,190), 'C': (0,0,0),     'N': (255,255,255),'B': (100,120,150), 'D': (40,50,70),  'P': (100,120,150),'T': (120,140,170),'.': None}

# Minotaur — bull horns, massive upper body, hooves
SPRITE_MINOTAUR = """
EE........EE..
.EE......EE...
..EDDDDDE.....
..DWWWWWD.....
.DCCWWWCCD....
..DWWNNWWD....
.DBBBBBBBD....
DBBBBBBBBBD...
.DBBBBBBBD....
..DPPPPPD.....
..DPP..PPD....
.DPP....PPD...
"""

# Pegasus — wings spread, horse body, flowing mane/tail
SPRITE_PEGASUS = """
E.............E
EE...DDDD...EE.
.EE.DWWWWD.EE..
..EEDWWWWDEE...
....DCCWWCD....
....DWNNWD.....
...DBBBBBBBD...
...DBBBBBBD....
....DPPPPD.....
...DPP..PPD..TT
..DPP....PPD.TT
..DD......DDTTT
"""

PALETTE_MINOTAUR = {'E': (120,80,40), 'W': (180,140,90), 'C': (200,50,30), 'N': (60,40,30),  'B': (140,100,60), 'D': (50,35,20), 'P': (90,60,35), 'T': None,        '.': None}
PALETTE_PEGASUS  = {'E': (200,210,240),'W': (240,240,255),'C': (100,150,255),'N': (180,180,200),'B': (220,225,240),'D': (120,130,160),'P': (180,185,200),'T': (200,210,240),'.': None}

# Turtle — dome shell, stubby legs, small head poking out
SPRITE_TURTLE = """
..............
.....DDDD.....
...DBBBBBD....
..DBTBTBTBD...
..DBTBTBTBD...
..DBTBTBTBD...
...DBBBBBD....
.DDWWDDDDDD..
DCWWWD...DPPD.
.DDDD....DPPD.
..........DD..
"""

PALETTE_TURTLE = {'E': (60,100,60),  'W': (100,160,80), 'C': (30,30,30),  'N': (80,120,60),  'B': (50,120,50),   'D': (30,60,30),  'P': (70,110,60), 'T': (50,120,50),  '.': None}

# Legacy aliases for any code that references these
P1_PALETTE = PALETTE_WOLF
P2_PALETTE = PALETTE_FOX

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

# ======================== PARTICLES ========================
class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'size')
    def __init__(self, x, y, vx, vy, life, color, size=3):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, count, color, speed=100, life=0.6, size=3, spread=6.28):
        angle_base = -1.57  # up
        for _ in range(count):
            a = angle_base + random.uniform(-spread/2, spread/2)
            s = random.uniform(speed * 0.4, speed)
            self.particles.append(Particle(
                x, y, math.cos(a)*s, math.sin(a)*s,
                life * random.uniform(0.6, 1.0), color, size
            ))

    def emit_fire(self, x, y, intensity=1.0):
        """Trailing fire for combos."""
        for _ in range(int(3 * intensity)):
            self.particles.append(Particle(
                x + random.uniform(-6, 6), y + random.uniform(-4, 4),
                random.uniform(-30, -60), random.uniform(-40, 20),
                random.uniform(0.2, 0.5),
                random.choice([(255,100,0), (255,200,0), (255,60,0), (255,255,100)]),
                random.randint(2, 4)
            ))

    def emit_star(self, x, y):
        """Star power sparkles."""
        for _ in range(2):
            a = random.uniform(0, 6.28)
            s = random.uniform(20, 80)
            self.particles.append(Particle(
                x + random.uniform(-20, 20), y + random.uniform(-20, 20),
                math.cos(a)*s, math.sin(a)*s,
                random.uniform(0.3, 0.8),
                random.choice([C_STAR_GOLD, (255,255,200), (255,200,50)]),
                random.randint(2, 5)
            ))

    def update(self, dt):
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 120 * dt  # gravity
            alive.append(p)
        self.particles = alive

    def draw(self, screen):
        for p in self.particles:
            alpha = p.life / p.max_life
            r, g, b = p.color
            color = (int(r * alpha), int(g * alpha), int(b * alpha))
            sz = max(1, int(p.size * alpha))
            pygame.draw.rect(screen, color, (int(p.x) - sz//2, int(p.y) - sz//2, sz, sz))


# ======================== HIT POPUP ========================
class HitPopup:
    __slots__ = ('x', 'y', 'text', 'color', 'life', 'max_life')
    def __init__(self, x, y, text, color, life=0.8):
        self.x, self.y = x, y
        self.text, self.color = text, color
        self.life = self.max_life = life

class PopupSystem:
    def __init__(self, font):
        self.popups = []
        self.font = font

    def add(self, x, y, text, color):
        self.popups.append(HitPopup(x, y, text, color))

    def update(self, dt):
        alive = []
        for p in self.popups:
            p.life -= dt
            p.y -= 60 * dt  # float up
            if p.life > 0:
                alive.append(p)
        self.popups = alive

    def draw(self, screen):
        for p in self.popups:
            alpha = p.life / p.max_life
            r, g, b = p.color
            color = (int(r * min(1, alpha * 2)), int(g * min(1, alpha * 2)), int(b * min(1, alpha * 2)))
            scale = 1.0 + (1.0 - alpha) * 0.3
            surf = self.font.render(p.text, True, color)
            if scale > 1.05:
                surf = pygame.transform.scale(surf, (int(surf.get_width() * scale), int(surf.get_height() * scale)))
            screen.blit(surf, (int(p.x) - surf.get_width()//2, int(p.y) - surf.get_height()//2))


# ======================== CITY SKYLINE ========================
def generate_skyline(width_tiles=100):
    """Generate a neon city skyline for parallax background."""
    buildings = []
    x = 0
    while x < width_tiles * TILE:
        w = random.randint(30, 80)
        h = random.randint(60, 250)
        has_antenna = random.random() < 0.3
        neon_color = random.choice([C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW, (100, 50, 200)])
        windows = []
        for wy in range(10, h - 10, 14):
            for wx in range(6, w - 6, 12):
                if random.random() < 0.6:
                    lit = random.random() < 0.7
                    windows.append((wx, wy, lit))
        buildings.append({
            'x': x, 'w': w, 'h': h,
            'antenna': has_antenna,
            'neon': neon_color,
            'windows': windows,
            'neon_sign_y': random.randint(20, max(21, h - 40)) if random.random() < 0.2 else -1,
        })
        x += w + random.randint(2, 20)
    return buildings

def draw_skyline(screen, buildings, cam_x, ground_y, beat_flash=0.0):
    """Draw parallax city skyline with optional beat-synced edge glow."""
    for b in buildings:
        sx = int(b['x'] - cam_x * 0.2) % (WIDTH * 3) - WIDTH
        if sx + b['w'] < -20 or sx > WIDTH + 20:
            continue
        by = ground_y - b['h']
        # Building body
        body_color = (random.randint(12, 18), random.randint(10, 16), random.randint(25, 35)) if random.random() < 0.01 else C_BUILDING
        pygame.draw.rect(screen, C_BUILDING, (sx, by, b['w'], b['h']))
        # Edge glow — pulse brighter on beat
        glow_boost = 1.0 + beat_flash * 1.5  # up to 2.5x brightness on beat
        edge_color = tuple(min(255, int(c * glow_boost)) for c in b['neon'][:3])
        edge_width = 1 if beat_flash < 0.3 else 2  # thicker line on strong beats
        pygame.draw.line(screen, edge_color, (sx, by), (sx, by + b['h']), edge_width)
        pygame.draw.line(screen, edge_color, (sx + b['w'], by), (sx + b['w'], by + b['h']), edge_width)
        pygame.draw.line(screen, edge_color, (sx, by), (sx + b['w'], by), edge_width)
        # Windows
        for wx, wy, lit in b['windows']:
            if lit:
                wc = (60, 55, 40)
            else:
                wc = (15, 12, 20)
            pygame.draw.rect(screen, wc, (sx + wx, by + wy, 6, 8))
        # Antenna
        if b['antenna']:
            ax = sx + b['w'] // 2
            pygame.draw.line(screen, (60, 60, 80), (ax, by), (ax, by - 20), 1)
            blink = 1 if int(time.time() * 2) % 2 == 0 else 0
            if blink:
                pygame.draw.circle(screen, (255, 50, 50), (ax, by - 20), 2)
        # Neon sign
        if b['neon_sign_y'] > 0:
            pulse = 0.6 + 0.4 * math.sin(time.time() * 3 + b['x'] * 0.1)
            nc = tuple(int(c * pulse) for c in b['neon'])
            pygame.draw.rect(screen, nc, (sx + 4, by + b['neon_sign_y'], b['w'] - 8, 6))


# ======================== ABLETON TRANSPORT CONTROL ========================
# MIDI CCs — for triggering notes/samples through LoopBe
TRANSPORT_CC_PLAY = 119
TRANSPORT_CC_STOP = 118
TRANSPORT_CC_RECORD = 117

# ======================== ABLETON LIVEAPI VIA COLAB ========================
# CoLaB M4L device on UDP port 8001 handles /live/... commands directly
# Uses LiveAPI — no extra Remote Script needed, just CoLaB loaded on a track
import socket

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8002  # Moonwolf Bridge M4L device
COLAB_PORT = 8001   # CoLaB fallback

class AbletonOSC:
    """Control Ableton via Moonwolf Bridge M4L device (UDP port 8002).
    Falls back to CoLaB on port 8001 if needed.
    Send plain text /moonwolf/... commands — Bridge executes them via LiveAPI."""
    def __init__(self, host=BRIDGE_HOST, port=BRIDGE_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.connected = True
        print(f"  Ableton LiveAPI: Moonwolf Bridge UDP {host}:{port}")

    def send(self, command):
        """Send a plain text command to Moonwolf Bridge."""
        try:
            self.sock.sendto(command.encode('utf-8'), (self.host, self.port))
        except Exception as e:
            print(f"  Bridge send error: {e}")

    # === Transport ===
    def set_tempo(self, bpm):
        self.send(f"/moonwolf/transport/tempo {bpm}")

    def play(self):
        self.send("/moonwolf/transport/play")

    def stop(self):
        self.send("/moonwolf/transport/stop")

    def record(self):
        self.send("/moonwolf/transport/record")

    def stop_record(self):
        self.send("/moonwolf/transport/stop_record")

    def set_metronome(self, on=True):
        self.send(f"/moonwolf/transport/metronome {1 if on else 0}")

    # === Track management ===
    def create_track(self, name, midi_channel=0):
        self.send(f"/moonwolf/track/create {name} {midi_channel}")

    def arm_track(self, track, armed=True):
        self.send(f"/moonwolf/track/arm {track} {1 if armed else 0}")

    def arm_exclusive(self, track):
        """Arm one track, disarm all others."""
        self.send(f"/moonwolf/arm_all {track}")

    def name_track(self, track, name):
        self.send(f"/moonwolf/track/name {track} {name}")

    def mute_track(self, track, muted=True):
        self.send(f"/moonwolf/track/mute {track} {1 if muted else 0}")

    def set_volume(self, track, vol):
        self.send(f"/moonwolf/track/volume {track} {vol}")

    def delete_track(self, track):
        self.send(f"/moonwolf/track/delete {track}")

    # === Clip control ===
    def fire_clip(self, track, clip):
        self.send(f"/moonwolf/clip/fire {track} {clip}")

    def stop_clips(self, track):
        self.send(f"/moonwolf/clip/stop {track}")

    def quantize_clip(self, track, clip, grid=5):
        self.send(f"/moonwolf/clip/quantize {track} {clip} {grid}")

    def loop_clip(self, track, clip, looping=True):
        self.send(f"/moonwolf/clip/loop {track} {clip} {1 if looping else 0}")

    # === Full session setup ===
    def setup_session(self, bpm, layers):
        """Create a full session for a song.
        layers: list of (name, midi_channel) tuples."""
        layer_str = ",".join(f"{name}:{ch}" for name, ch in layers)
        self.send(f"/moonwolf/setup/session {bpm} {layer_str}")

    # === Query ===
    def query_tracks(self):
        self.send("/moonwolf/query/tracks")

    def query_tempo(self):
        self.send("/moonwolf/query/tempo")

    # === Logging ===
    def log(self, msg):
        """Send to CoLaB console (fallback port)."""
        try:
            self.sock.sendto(f"[INFO] {msg}".encode('utf-8'), (self.host, COLAB_PORT))
        except Exception:
            pass

    def close(self):
        self.sock.close()


# ======================== LEVEL LOADER ========================
class Level:
    def __init__(self, name, bpm, bars, note_events, drum_events, instrument_name="Synth"):
        self.name = name
        self.bpm = bpm
        self.bars = bars
        self.instrument_name = instrument_name
        self.scroll_speed = (bpm * 4 / 60.0) * (TILE * 2)  # px/sec
        self.level_width = bars * 4 * 4 * (TILE * 2)  # bars * beats * subdivs * px

        # Note pickups: [x, y, note, collected]
        self.pickups = []
        # Drum lanes: [x, lane_idx, drum_note, hit]
        self.drum_lanes = []

        self.play_top = 80
        self.play_bottom = HEIGHT - 200
        self.play_range = self.play_bottom - self.play_top

        # Compute actual note range for better vertical compression
        if note_events:
            notes = [n for _, n, _, _ in note_events]
            self._note_min = min(notes)
            self._note_max = max(notes)
            # Ensure at least an octave of range so notes aren't all on one line
            if self._note_max - self._note_min < 12:
                mid = (self._note_min + self._note_max) // 2
                self._note_min = mid - 6
                self._note_max = mid + 6
        else:
            self._note_min = 30
            self._note_max = 80

        # Place events
        for t, note, vel, ch in note_events:
            x = int(t * self.scroll_speed)
            y = self._note_to_y(note)
            self.pickups.append([x, y, note, False])

        for t, note, vel, ch in drum_events:
            x = int(t * self.scroll_speed)
            # Find which lane this drum goes to
            lane = self._drum_to_lane(note)
            if lane >= 0:
                self.drum_lanes.append([x, lane, note, False])

    def _note_to_y(self, note):
        # Map MIDI notes to a compressed center band (not full screen)
        # Use the actual note range in this level, not fixed 30-80
        if not hasattr(self, '_note_min'):
            self._note_min = 30
            self._note_max = 80
        frac = max(0, min(1, (note - self._note_min) / max(1, self._note_max - self._note_min)))
        # Compress to middle 60% of play area (more reachable)
        margin = self.play_range * 0.2
        usable = self.play_range - margin * 2
        return int(self.play_bottom - margin - frac * usable)

    def _drum_to_lane(self, note):
        for lane_idx, (drum_note, name, color) in FE_DRUM_MAP.items():
            if drum_note == note:
                return lane_idx
        return -1

    def reset(self):
        for p in self.pickups:
            p[3] = False
        for d in self.drum_lanes:
            d[3] = False

def load_levels_from_midi(filepath, bpm_override=None):
    """Load a MIDI file and split into drum level + melody level."""
    mid = mido.MidiFile(filepath)
    bpm = bpm_override or 120

    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                bpm = mido.tempo2bpm(msg.tempo)

    if bpm_override:
        bpm = bpm_override

    # Collect events
    drum_events = []
    note_events = []

    for track in mid.tracks:
        abs_time = 0.0
        for msg in track:
            abs_time += mido.tick2second(msg.time, mid.ticks_per_beat, mido.bpm2tempo(bpm))
            if msg.type == 'note_on' and msg.velocity > 0:
                if msg.channel == 9:
                    drum_events.append((abs_time, msg.note, msg.velocity, msg.channel))
                else:
                    note_events.append((abs_time, msg.note, msg.velocity, msg.channel))

    drum_events.sort()
    note_events.sort()

    # Figure out bar counts
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4

    drum_bars = 16  # Default
    if drum_events:
        drum_bars = int(drum_events[-1][0] / bar_dur) + 1

    mel_bars = 16
    if note_events:
        # Shift melody times to start at 0
        mel_start = note_events[0][0]
        note_events_shifted = [(t - mel_start, n, v, c) for t, n, v, c in note_events]
        mel_bars = int(note_events_shifted[-1][0] / bar_dur) + 2
    else:
        note_events_shifted = []

    # Determine the melody MIDI channel from the source data
    mel_channel = 0  # default
    if note_events:
        # Use the most common channel in the melody events
        from collections import Counter
        ch_counts = Counter(c for _, _, _, c in note_events)
        mel_channel = ch_counts.most_common(1)[0][0]

    levels = []
    drum_level = Level("DRUMS", bpm, drum_bars, [], drum_events, "Drum Kit")
    drum_level.midi_channel = 9  # Always drum channel
    levels.append(drum_level)
    if note_events_shifted:
        mel_level = Level("MELODY", bpm, mel_bars, note_events_shifted, [], "Lead Synth")
        mel_level.midi_channel = mel_channel
        levels.append(mel_level)

    return levels, bpm

def generate_default_levels(bpm, key_name, is_major):
    """Generate procedural drum + melody levels."""
    root = ROOT_MIDI.get(key_name, 57)
    intervals = MAJOR_INT if is_major else MINOR_INT
    scale = [root + iv for iv in intervals]
    beat_dur = 60.0 / bpm

    # Level 1: 16-bar drum pattern
    drum_events = []
    for bar in range(16):
        bar_t = bar * 4 * beat_dur
        drum_events.append((bar_t, KICK, 110, 9))
        drum_events.append((bar_t + beat_dur, HAT, 70, 9))
        drum_events.append((bar_t + beat_dur * 1.5, SNARE, 100, 9))
        drum_events.append((bar_t + beat_dur * 2, KICK, 100, 9))
        drum_events.append((bar_t + beat_dur * 2, HAT, 70, 9))
        drum_events.append((bar_t + beat_dur * 3, HAT, 60, 9))
        drum_events.append((bar_t + beat_dur * 3.5, HAT, 50, 9))

    # Level 2: Melody
    note_events = []
    t = 0
    for rep in range(8):
        for degree in [0, 0, 2, 0, 6, 5, 4]:
            note = scale[degree % len(scale)]
            note_events.append((t, note, 100, 0))
            t += beat_dur

    drum_level = Level("DRUMS", bpm, 16, [], drum_events, "Drum Kit")
    drum_level.midi_channel = 9
    mel_level = Level("MELODY", bpm, 16, note_events, [], "Lead Synth")
    mel_level.midi_channel = 0  # Keys/synth channel
    levels = [drum_level, mel_level]
    return levels

# ======================== GAME ========================
class MoonwolfLayers:
    def __init__(self, bpm=124, key_name="E", is_major=False, port_name="FE Bridge", midi_file=None, demo_mode=False):
        pygame.init()
        pygame.joystick.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Moonwolf Layers")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 14)
        self.font_big = pygame.font.SysFont("consolas", 22)
        self.font_title = pygame.font.SysFont("consolas", 36)

        self.bpm = bpm
        self.key_name = key_name
        self.is_major = is_major
        self.port_name = port_name
        self.midi_file = midi_file

        # Fonts
        self.font_huge = pygame.font.SysFont("consolas", 52)
        self.font_menu = pygame.font.SysFont("consolas", 18)

        # Scale for star power riffing
        root = ROOT_MIDI.get(key_name, 57)
        intervals = MAJOR_INT if is_major else MINOR_INT
        self.scale = [root + iv for iv in intervals]

        # Sprites — built from selected character
        self.p1_sprite = make_sprite(self.CHARACTERS[0]["sprite"], self.CHARACTERS[0]["palette"], 3)
        self.p2_sprite = make_sprite(self.CHARACTERS[1]["sprite"], self.CHARACTERS[1]["palette"], 3)

        # Stars bg
        self.stars = [(random.randint(0, WIDTH*4), random.randint(0, HEIGHT//3),
                       random.uniform(0.2, 1.0)) for _ in range(150)]

        # City skyline
        self.skyline = generate_skyline(200)

        # Particle & popup systems
        self.particles = ParticleSystem()
        self.popups = PopupSystem(self.font_big)

        # Screen shake
        self.shake_x, self.shake_y = 0.0, 0.0
        self.shake_intensity = 0.0

        # ===== MENU STATE =====
        self.menu_selection = 0
        self.menu_player_mode = 1      # 0=1P Solo, 1=2P Co-op
        self.menu_midi_idx = 0
        self.p1_char_idx = 0           # Wolf
        self.p2_char_idx = 1           # Fox (different default)
        self.p1_role_idx = 0           # Drums
        self.p2_role_idx = 1           # Keys
        self.song_list = get_song_list()
        self.song_idx = 0              # Selected song index
        self.song_scroll_offset = 0    # For scrolling long lists
        self.available_midi = self._scan_midi_ports()
        self.detected_controllers = self._scan_controllers()
        self.fe_connected = False
        self.joystick_connected = False

        # Pre-select port matching the command line arg
        for i, p in enumerate(self.available_midi):
            if port_name.lower() in p.lower():
                self.menu_midi_idx = i
                break

        # MIDI (notes/samples go through LoopBe)
        self.midi_port = None

        # OSC (transport control goes through AbletonOSC)
        self.osc = AbletonOSC()

        # Joystick
        self.joystick = None

        # Fighting Edge state (read via separate HID thread)
        self.fe_buttons = [False] * 8
        self.fe_hat = -1

        # ===== PROFILE STATE =====
        self.profile = None
        self.profile_list = save_system.list_profiles()
        self.profile_cursor = 0  # 0..len(profiles) where last = "NEW PROFILE"
        self.profile_naming = False  # True when typing a new name
        self.profile_name_buf = ""
        self.profile_animal_idx = 0  # Index into CHARACTERS for new profile
        self.profile_animal_step = False  # True when choosing animal for new profile
        self.profile_palette_name = "default"  # Active palette override

        # XP tracking per level
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.xp_result = None  # Filled after level complete

        # Game state — start at PROFILE_SELECT
        self.state = "PROFILE_SELECT"
        self.state_timer = 0
        self.beat_timer = 0
        self.beat_flash = 0
        self.beat_interval = 60.0 / self.bpm

        # Transport state
        self.ableton_recording = False

        # These get set when we leave the menu
        self.levels = None
        self.level = None
        self.current_level = 0
        self.p1_y = HEIGHT // 2
        self.p1_vy = 0.0              # Ship velocity Y
        self.p2_lane_flash = {}
        self.camera_x = 0.0
        self.scroll_speed = 0
        self.speed_mult = 1.0
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.hits = 0
        self.total_targets = 0
        self.star_power = False
        self.star_power_timer = 0
        self.star_meter = 0.0
        self.locked_levels = 0
        self.recorded_layers = {}  # {level_idx: [(time_sec, note, vel, ch, dur), ...]}
        self.loop_playback_head = 0.0  # Tracks time for looping completed layers
        self.pending_offs = []
        self.perfect_bonus = 1.0
        self.speed_bonus = 1.0
        self.star_fill_bonus = 1.0
        self.combo_shield = False
        self.combo_shield_used = False
        self.combo_shield_max = 1
        self.combo_shield_count = 0
        self.predator = False
        self.venom = False
        self.venom_timer = 0.0
        self.soar = False
        self.fury = False
        self.agile = False
        self.tank = False
        self.frenzy = False
        self.rage = False
        self.flight = False
        self.shell = False
        self.shell_hits = 0
        self._next_note_y = None
        self._next_note_dist = 0
        self.combo_pulse = 0.0  # Visual pulse when combo increases (0..1 decays)

        # Demo/auto-play mode — bot plays optimally
        self.demo_mode = demo_mode
        self.demo_auto_advance_timer = 0.0

    def _scan_midi_ports(self):
        """Get available MIDI output ports."""
        try:
            return mido.get_output_names()
        except Exception:
            return []

    def _scan_controllers(self):
        """Scan for joysticks and Fighting Edge."""
        controllers = []
        # Joysticks
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            name = js.get_name()
            ctype = "Joystick"
            if 't.16000m' in name.lower() or 'thrustmaster' in name.lower():
                ctype = "Thrustmaster T.16000M"
                self.joystick_connected = True
            elif 'fighting' in name.lower() or '0f0d' in name.lower():
                ctype = "Fighting Edge"
            controllers.append({"name": name, "type": ctype, "idx": i, "source": "pygame"})
        # Fighting Edge via HID
        try:
            import hid as hidlib
            devs = hidlib.enumerate(0x0F0D, 0x0037)
            if devs:
                self.fe_connected = True
                # Only add if not already listed via pygame
                if not any("Fighting" in c["type"] for c in controllers):
                    controllers.append({"name": "Hori Fighting Edge", "type": "Fighting Edge (HID)", "idx": -1, "source": "hid"})
        except Exception:
            pass
        return controllers

    def _init_game(self):
        """Initialize game state after menu — load levels, connect MIDI, start HID."""
        # Connect MIDI
        if self.available_midi:
            port_name = self.available_midi[self.menu_midi_idx]
        else:
            port_name = self.port_name
        self._open_midi(port_name)

        # Connect joystick
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            if 't.16000m' in js.get_name().lower() or 'thrustmaster' in js.get_name().lower():
                self.joystick = js
                print(f"  Joystick: {js.get_name()}")
                break

        # Start FE reader
        self._start_fe_reader()

        # Load levels from selected song or fallback
        if self.song_list:
            song_info = self.song_list[self.song_idx]
            song_folder = song_info["folder"]
            # Load full.mid from the song library
            song_data = load_song(song_folder)
            full_mid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs", song_folder, "full.mid")
            if os.path.exists(full_mid_path):
                self.bpm = song_info.get("bpm", self.bpm) or self.bpm
                self.levels, self.bpm = load_levels_from_midi(full_mid_path, self.bpm)
                print(f"  Song: {song_info['artist']} - {song_info['title']}")
            else:
                self.levels = generate_default_levels(self.bpm, self.key_name, self.is_major)
        elif self.midi_file:
            self.levels, self.bpm = load_levels_from_midi(self.midi_file, self.bpm)
        else:
            self.levels = generate_default_levels(self.bpm, self.key_name, self.is_major)

        self.current_level = 0
        self.level = self.levels[0]
        self.scroll_speed = self.level.scroll_speed
        self.beat_interval = 60.0 / self.bpm

        # Auto-setup Ableton session via Moonwolf Bridge
        ch_map = {"drums": 9, "bass": 2, "guitar": 1, "keys": 0, "strings": 4, "horns": 3, "synth": 6, "vocals": 5}
        if hasattr(self, 'song_list') and self.song_list:
            song = self.song_list[self.song_idx]
            song_data = load_song(song["folder"])
            layer_list = [(name, ch_map.get(name, 0)) for name in song_data["tracks"].keys()]
            self.osc.setup_session(self.bpm, layer_list)
            print(f"  Ableton session setup: {self.bpm} BPM, layers: {', '.join(n for n,c in layer_list)}")
        else:
            self.osc.set_tempo(self.bpm)
            self.osc.stop()
            print(f"  Ableton BPM set to {self.bpm}")

        # Reset scoring
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.locked_levels = 0
        self.recorded_layers = {}  # {level_idx: [(time_sec, note, vel, ch, dur), ...]}
        self.loop_playback_head = 0.0  # Tracks time for looping completed layers
        self.star_meter = 0.0

        # Reset XP stat counters
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.xp_result = None

        # Apply character abilities
        p1_ch = self.CHARACTERS[self.p1_char_idx]
        p2_ch = self.CHARACTERS[self.p2_char_idx]
        self.perfect_bonus = p1_ch['perfect_bonus']
        self.speed_bonus = p1_ch['speed_bonus']
        self.star_fill_bonus = p1_ch['star_bonus']
        self.combo_shield = p1_ch.get('shield', False) or p2_ch.get('shield', False)
        self.predator = p1_ch.get('predator', False) or p2_ch.get('predator', False)
        self.venom = p1_ch.get('venom', False) or p2_ch.get('venom', False)
        self.soar = p1_ch.get('soar', False) or p2_ch.get('soar', False)
        self.fury = p1_ch.get('fury', False) or p2_ch.get('fury', False)
        self.agile = p1_ch.get('agile', False) or p2_ch.get('agile', False)
        self.tank = p1_ch.get('tank', False) or p2_ch.get('tank', False)
        self.frenzy = p1_ch.get('frenzy', False) or p2_ch.get('frenzy', False)
        self.rage = p1_ch.get('rage', False) or p2_ch.get('rage', False)
        self.flight = p1_ch.get('flight', False) or p2_ch.get('flight', False)
        self.shell = p1_ch.get('shell', False) or p2_ch.get('shell', False)
        # Reset per-round state
        self.combo_shield_used = False
        self.combo_shield_max = 3 if self.tank else 1
        self.combo_shield_count = 0
        self.venom_timer = 0.0
        self.shell_hits = 0

        self.state = "LEVEL_INTRO"
        self.state_timer = 0

        p1_role = INSTRUMENT_ROLES[self.p1_role_idx]
        p2_role = INSTRUMENT_ROLES[self.p2_role_idx]
        self.p1_midi_ch = p1_role['midi_ch']
        self.p2_midi_ch = p2_role['midi_ch']
        print(f"  Mode: {'2P Co-op' if self.menu_player_mode == 1 else '1P Solo'}")
        print(f"  P1: {p1_ch['name']} — {p1_ch['ability']} — Role: {p1_role['name']} (ch.{p1_role['midi_ch']})")
        print(f"  P2: {p2_ch['name']} — {p2_ch['ability']} — Role: {p2_role['name']} (ch.{p2_role['midi_ch']})")
        print(f"  Levels: {len(self.levels)}")
        for i, lv in enumerate(self.levels):
            tag = " <-- CURRENT" if i == 0 else ""
            print(f"    {i+1}. {lv.name} ({lv.bars} bars, {lv.instrument_name}){tag}")

    # ===== MENU ITEMS =====
    MENU_ITEMS_2P = ["PLAYERS", "SONG", "P1 CHARACTER", "P1 PALETTE", "P1 ROLE", "P2 CHARACTER", "P2 ROLE", "MIDI OUTPUT", "START GAME"]
    MENU_ITEMS_1P = ["PLAYERS", "SONG", "P1 CHARACTER", "P1 PALETTE", "P1 ROLE", "MIDI OUTPUT", "START GAME"]

    @property
    def _menu_items(self):
        return self.MENU_ITEMS_2P if self.menu_player_mode == 1 else self.MENU_ITEMS_1P

    # ===== CHARACTERS =====
    CHARACTERS = [
        {"name": "WOLF",  "animal": "wolf", "color": C_NEON_CYAN,  "sprite": SPRITE_WOLF, "palette": PALETTE_WOLF,
         "ability": "Precision — Perfect window +20%", "perfect_bonus": 1.2, "speed_bonus": 1.0, "star_bonus": 1.0},
        {"name": "FOX",   "animal": "fox",  "color": (255, 150, 50), "sprite": SPRITE_FOX, "palette": PALETTE_FOX,
         "ability": "Speed — Scroll speed +15%",      "perfect_bonus": 1.0, "speed_bonus": 1.15, "star_bonus": 1.0},
        {"name": "CAT",   "animal": "cat",  "color": C_STAR_GOLD,  "sprite": SPRITE_CAT, "palette": PALETTE_CAT,
         "ability": "Star Power — Meter fills 30% faster", "perfect_bonus": 1.0, "speed_bonus": 1.0, "star_bonus": 1.3},
        {"name": "DOG",   "animal": "dog",  "color": C_NEON_GREEN, "sprite": SPRITE_DOG, "palette": PALETTE_DOG,
         "ability": "Combo Shield — Keep combo on 1st miss", "perfect_bonus": 1.0, "speed_bonus": 1.0, "star_bonus": 1.0, "shield": True},
        {"name": "PUMA",    "animal": "puma",    "color": (200, 170, 80),  "sprite": SPRITE_PUMA,    "palette": PALETTE_PUMA,
         "ability": "Predator — 2x score on Perfect hits",      "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "predator": True},
        {"name": "SNAKE",   "animal": "snake",   "color": (80, 200, 50),   "sprite": SPRITE_SNAKE,   "palette": PALETTE_SNAKE,
         "ability": "Venom — Misses don't reset combo for 3s",  "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "venom": True},
        {"name": "EAGLE",   "animal": "eagle",   "color": (240, 200, 80),  "sprite": SPRITE_EAGLE,   "palette": PALETTE_EAGLE,
         "ability": "Soar — Collection radius +40%",            "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "soar": True},
        {"name": "TIGER",   "animal": "tiger",   "color": (255, 160, 30),  "sprite": SPRITE_TIGER,   "palette": PALETTE_TIGER,
         "ability": "Fury — Combo multiplier thresholds halved", "perfect_bonus": 1.0, "speed_bonus": 1.0, "star_bonus": 1.0, "fury": True},
        {"name": "MONKEY",  "animal": "monkey",  "color": (200, 150, 80),  "sprite": SPRITE_MONKEY,  "palette": PALETTE_MONKEY,
         "ability": "Agile — Ship acceleration +50%",           "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "agile": True},
        {"name": "GORILLA", "animal": "gorilla", "color": (120, 120, 140), "sprite": SPRITE_GORILLA, "palette": PALETTE_GORILLA,
         "ability": "Tank — 3 combo shields instead of 1",      "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "tank": True},
        {"name": "SHARK",     "animal": "shark",     "color": (100, 140, 200), "sprite": SPRITE_SHARK,     "palette": PALETTE_SHARK,
         "ability": "Frenzy — Score +10% per combo tier",        "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "frenzy": True},
        {"name": "MINOTAUR", "animal": "minotaur", "color": (180, 100, 50),  "sprite": SPRITE_MINOTAUR, "palette": PALETTE_MINOTAUR,
         "ability": "Rage — Star Power lasts 2x longer",         "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "rage": True},
        {"name": "PEGASUS",  "animal": "pegasus",  "color": (180, 200, 255), "sprite": SPRITE_PEGASUS,  "palette": PALETTE_PEGASUS,
         "ability": "Flight — Zero gravity, instant direction change", "perfect_bonus": 1.0, "speed_bonus": 1.0, "star_bonus": 1.0, "flight": True},
        {"name": "TURTLE",   "animal": "turtle",   "color": (80, 180, 80),   "sprite": SPRITE_TURTLE,   "palette": PALETTE_TURTLE,
         "ability": "Shell — Immune to combo break for 5 hits",  "perfect_bonus": 1.0, "speed_bonus": 1.0,  "star_bonus": 1.0, "shell": True},
    ]

    def _menu_item_count(self):
        return len(self._menu_items)

    def _menu_adjust(self, direction):
        """Left/Right adjustment on current menu item."""
        item = self._menu_items[self.menu_selection]
        if item == "PLAYERS":
            self.menu_player_mode = (self.menu_player_mode + direction) % 2
        elif item == "SONG":
            if self.song_list:
                self.song_idx = (self.song_idx + direction) % len(self.song_list)
            # Clamp selection if menu shrunk
            if self.menu_selection >= self._menu_item_count():
                self.menu_selection = self._menu_item_count() - 1
        elif item == "P1 CHARACTER":
            self.p1_char_idx = (self.p1_char_idx + direction) % len(self.CHARACTERS)
            ch = self.CHARACTERS[self.p1_char_idx]
            pal = save_system.apply_palette_override(ch["palette"], self.profile_palette_name)
            self.p1_sprite = make_sprite(ch["sprite"], pal, 3)
        elif item == "P1 PALETTE":
            # Cycle through unlocked palettes
            level = self.profile["level"] if self.profile else 1
            available = save_system.unlocked_palettes(level)
            if available:
                try:
                    idx = available.index(self.profile_palette_name)
                except ValueError:
                    idx = 0
                idx = (idx + direction) % len(available)
                self.profile_palette_name = available[idx]
                if self.profile:
                    self.profile["color_palette"] = self.profile_palette_name
                # Rebuild P1 sprite with new palette
                ch = self.CHARACTERS[self.p1_char_idx]
                pal = save_system.apply_palette_override(ch["palette"], self.profile_palette_name)
                self.p1_sprite = make_sprite(ch["sprite"], pal, 3)
        elif item == "P2 CHARACTER":
            self.p2_char_idx = (self.p2_char_idx + direction) % len(self.CHARACTERS)
            ch = self.CHARACTERS[self.p2_char_idx]
            self.p2_sprite = make_sprite(ch["sprite"], ch["palette"], 3)
        elif item == "P1 ROLE":
            self.p1_role_idx = (self.p1_role_idx + direction) % len(INSTRUMENT_ROLES)
        elif item == "P2 ROLE":
            self.p2_role_idx = (self.p2_role_idx + direction) % len(INSTRUMENT_ROLES)
        elif item == "MIDI OUTPUT":
            if self.available_midi:
                self.menu_midi_idx = (self.menu_midi_idx + direction) % len(self.available_midi)

    def _draw_menu(self):
        self.screen.fill(C_BG)

        # Animated skyline
        draw_skyline(self.screen, self.skyline, int(time.time() * 15), HEIGHT - 170)
        pygame.draw.line(self.screen, C_GROUND_TOP, (0, HEIGHT - 170), (WIDTH, HEIGHT - 170), 2)

        # Tron grid
        horizon_y = HEIGHT - 230
        ground_y = HEIGHT - 170
        for i in range(12):
            frac = i / 12.0
            y = int(horizon_y + (ground_y - horizon_y) * (frac ** 0.6))
            gs = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
            gs.fill((*C_NEON_CYAN, int(10 + 25 * frac)))
            self.screen.blit(gs, (0, y))
        vx = WIDTH // 2
        for i in range(-10, 11):
            pygame.draw.line(self.screen, C_NEON_PINK, (vx + i * 8, horizon_y), (vx + i * 80, ground_y), 1)

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 120))
        self.screen.blit(overlay, (0, 0))

        cx = WIDTH // 2

        # Title
        pulse = 0.7 + 0.3 * math.sin(time.time() * 2)
        title = self.font_huge.render("MOONWOLF LAYERS", True,
                                       (int(C_NEON_CYAN[0]*pulse), int(C_NEON_CYAN[1]*pulse), int(C_NEON_CYAN[2]*pulse)))
        self.screen.blit(title, (cx - title.get_width()//2, 40))

        # Subtitle
        sub = self.font_menu.render("Layer loops. Build songs. Star Power riffs.", True, C_HUD_DIM)
        self.screen.blit(sub, (cx - sub.get_width()//2, 100))

        # Profile info bar
        if self.profile:
            level, xp_into, xp_needed = save_system.xp_progress(self.profile["xp"])
            prof_str = f"{self.profile['name']}  Lv.{level}  XP: {self.profile['xp']}"
            prof_surf = self.font.render(prof_str, True, C_NEON_CYAN)
            self.screen.blit(prof_surf, (cx - prof_surf.get_width()//2, 116))
            # Small XP progress bar
            bar_w, bar_h = 200, 6
            bar_x = cx - bar_w // 2
            bar_y = 132
            pygame.draw.rect(self.screen, (30, 25, 50), (bar_x, bar_y, bar_w, bar_h))
            fill = int(bar_w * xp_into / max(1, xp_needed))
            pygame.draw.rect(self.screen, C_NEON_CYAN, (bar_x, bar_y, fill, bar_h))

        # Character preview sprites (larger)
        p1_ch = self.CHARACTERS[self.p1_char_idx]
        p2_ch = self.CHARACTERS[self.p2_char_idx]
        p1_preview = make_sprite(p1_ch["sprite"], p1_ch["palette"], 5)
        p2_preview = make_sprite(p2_ch["sprite"], p2_ch["palette"], 5)

        # P1 preview panel (left)
        p1_panel_x = 30
        self.screen.blit(p1_preview, (p1_panel_x + 10, 140))
        self.screen.blit(self.font_menu.render("P1", True, p1_ch["color"]), (p1_panel_x + 25, 125))
        p1_role = INSTRUMENT_ROLES[self.p1_role_idx]
        self.screen.blit(self.font.render(p1_ch["name"], True, p1_ch["color"]), (p1_panel_x, 220))
        self.screen.blit(self.font.render(p1_role["name"], True, p1_role["color"]), (p1_panel_x, 236))

        # P2 preview panel (right) — only in 2P mode
        if self.menu_player_mode == 1:
            p2_panel_x = WIDTH - 110
            self.screen.blit(p2_preview, (p2_panel_x + 10, 140))
            self.screen.blit(self.font_menu.render("P2", True, p2_ch["color"]), (p2_panel_x + 25, 125))
            p2_role = INSTRUMENT_ROLES[self.p2_role_idx]
            self.screen.blit(self.font.render(p2_ch["name"], True, p2_ch["color"]), (p2_panel_x, 220))
            self.screen.blit(self.font.render(p2_role["name"], True, p2_role["color"]), (p2_panel_x, 236))

        # Menu items
        menu_x = cx - 200
        menu_y_start = 130
        item_h = 44

        for i, item_name in enumerate(self._menu_items):
            y = menu_y_start + i * item_h
            selected = (i == self.menu_selection)
            base_color = C_NEON_CYAN if selected else C_HUD_DIM
            label_color = (255, 255, 255) if selected else (150, 150, 170)

            # Selection indicator
            if selected:
                sel_bar = pygame.Surface((400, item_h - 4), pygame.SRCALPHA)
                sel_bar.fill((*C_NEON_CYAN, 25))
                self.screen.blit(sel_bar, (menu_x, y))
                # Arrow
                arrow = self.font_big.render(">", True, C_NEON_CYAN)
                self.screen.blit(arrow, (menu_x - 25, y + 8))

            # Item label
            label = self.font_menu.render(item_name, True, base_color)
            self.screen.blit(label, (menu_x + 10, y + 4))

            # Item value
            val_x = menu_x + 180
            if item_name == "PLAYERS":
                modes = ["1P SOLO", "2P CO-OP"]
                val = modes[self.menu_player_mode]
                vc = C_NEON_GREEN if self.menu_player_mode == 1 else C_NEON_YELLOW
                val_surf = self.font_big.render(f"< {val} >", True, vc if selected else C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y + 2))

            elif item_name == "SONG":
                if self.song_list:
                    song = self.song_list[self.song_idx]
                    title_str = f"{song['artist']} - {song['title']}"
                    if len(title_str) > 35:
                        title_str = title_str[:32] + "..."
                    val_surf = self.font_big.render(f"< {title_str} >", True, C_NEON_PINK if selected else C_HUD_DIM)
                    self.screen.blit(val_surf, (val_x, y + 2))
                    # Song details
                    diff_str = "*" * song['difficulty'] + "." * (5 - song['difficulty'])
                    detail = f"{song['bpm']} BPM | Key: {song['key']} | [{diff_str}]"
                    self.screen.blit(self.font.render(detail, True, (120, 120, 140)), (val_x, y + 26))
                    # Song counter
                    counter = self.font.render(f"{self.song_idx + 1}/{len(self.song_list)}", True, (80, 80, 100))
                    self.screen.blit(counter, (val_x + 380, y + 4))
                else:
                    val_surf = self.font_big.render("No songs found", True, C_ENEMY)
                    self.screen.blit(val_surf, (val_x, y + 2))

            elif item_name == "P1 CHARACTER":
                ch = self.CHARACTERS[self.p1_char_idx]
                val_surf = self.font_big.render(f"< {ch['name']} >", True, ch['color'] if selected else C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y + 2))
                ability = self.font.render(ch['ability'], True, (120, 120, 140))
                self.screen.blit(ability, (val_x, y + 26))

            elif item_name == "P1 PALETTE":
                pal_info = save_system.COLOR_PALETTES.get(self.profile_palette_name, {})
                pal_label = pal_info.get("label", self.profile_palette_name)
                pal_color = C_STAR_GOLD if self.profile_palette_name != "default" else C_HUD
                val_surf = self.font_big.render(f"< {pal_label} >", True, pal_color if selected else C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y + 2))
                level = self.profile["level"] if self.profile else 1
                n_unlocked = len(save_system.unlocked_palettes(level))
                n_total = len(save_system.COLOR_PALETTES)
                detail = self.font.render(f"{n_unlocked}/{n_total} unlocked", True, (120, 120, 140))
                self.screen.blit(detail, (val_x, y + 26))

            elif item_name == "P1 ROLE":
                role = INSTRUMENT_ROLES[self.p1_role_idx]
                val_surf = self.font_big.render(f"< {role['name']} >", True, role['color'] if selected else C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y + 2))
                desc = self.font.render(role['desc'], True, (120, 120, 140))
                self.screen.blit(desc, (val_x, y + 26))

            elif item_name == "P2 CHARACTER":
                ch = self.CHARACTERS[self.p2_char_idx]
                val_surf = self.font_big.render(f"< {ch['name']} >", True, ch['color'] if selected else C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y + 2))
                ability = self.font.render(ch['ability'], True, (120, 120, 140))
                self.screen.blit(ability, (val_x, y + 26))

            elif item_name == "P2 ROLE":
                role = INSTRUMENT_ROLES[self.p2_role_idx]
                val_surf = self.font_big.render(f"< {role['name']} >", True, role['color'] if selected else C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y + 2))
                desc = self.font.render(role['desc'], True, (120, 120, 140))
                self.screen.blit(desc, (val_x, y + 26))

            elif item_name == "MIDI OUTPUT":
                if self.available_midi:
                    port = self.available_midi[self.menu_midi_idx]
                    if len(port) > 28:
                        port = port[:25] + "..."
                    val_surf = self.font_big.render(f"< {port} >", True, C_NEON_GREEN if selected else C_HUD_DIM)
                else:
                    val_surf = self.font_big.render("No MIDI ports found", True, C_ENEMY)
                self.screen.blit(val_surf, (val_x, y + 2))

            elif item_name == "START GAME":
                if selected:
                    pulse2 = 0.5 + 0.5 * math.sin(time.time() * 5)
                    start_color = (int(C_NEON_GREEN[0]*pulse2), int(C_NEON_GREEN[1]*pulse2), int(C_NEON_GREEN[2]*pulse2))
                    val_surf = self.font_title.render("PRESS ENTER", True, start_color)
                else:
                    val_surf = self.font_big.render(">>", True, C_HUD_DIM)
                self.screen.blit(val_surf, (val_x, y - 4 if selected else y + 2))

        # Controller status panel
        panel_y = menu_y_start + len(self._menu_items) * item_h + 20
        self.screen.blit(self.font_menu.render("CONTROLLERS", True, C_HUD), (menu_x + 10, panel_y))
        pygame.draw.line(self.screen, C_HUD_DIM, (menu_x + 10, panel_y + 22), (menu_x + 390, panel_y + 22), 1)

        if self.detected_controllers:
            for i, ctrl in enumerate(self.detected_controllers):
                cy_ctrl = panel_y + 28 + i * 20
                dot_color = C_NEON_GREEN
                self.screen.blit(self.font.render("●", True, dot_color), (menu_x + 15, cy_ctrl))
                self.screen.blit(self.font.render(f"{ctrl['type']}: {ctrl['name'][:40]}", True, (180, 180, 200)), (menu_x + 30, cy_ctrl))
        else:
            self.screen.blit(self.font.render("No controllers detected", True, C_HUD_DIM), (menu_x + 15, panel_y + 28))

        # FE + Joystick status
        status_y = panel_y + 28 + max(1, len(self.detected_controllers)) * 20 + 5
        fe_status = "● Connected" if self.fe_connected else "○ Not found"
        fe_color = C_NEON_GREEN if self.fe_connected else C_HUD_DIM
        self.screen.blit(self.font.render(f"Fighting Edge: {fe_status}", True, fe_color), (menu_x + 15, status_y))

        js_status = "● Connected" if self.joystick_connected else "○ Not found"
        js_color = C_NEON_GREEN if self.joystick_connected else C_HUD_DIM
        self.screen.blit(self.font.render(f"Thrustmaster:  {js_status}", True, js_color), (menu_x + 15, status_y + 18))

        # Footer
        footer_items = [
            "[UP/DOWN] Navigate",
            "[LEFT/RIGHT] Change",
            "[ENTER] Select",
            "[F5] Refresh Controllers",
            "[ESC] Quit",
        ]
        footer = "    ".join(footer_items)
        self.screen.blit(self.font.render(footer, True, (60, 60, 80)), (20, HEIGHT - 22))

    def _open_midi(self, port_name):
        try:
            # Close existing port first to prevent port leak
            if self.midi_port:
                try:
                    self.midi_port.close()
                except Exception:
                    pass
                self.midi_port = None
            available = mido.get_output_names()
            matches = [n for n in available if port_name.lower() in n.lower()]
            if matches:
                self.midi_port = mido.open_output(matches[0])
                print(f"  MIDI output: {matches[0]}")
        except Exception as e:
            print(f"  MIDI error: {e}")

    def note_on(self, note, vel, ch=0):
        if self.midi_port:
            self.midi_port.send(mido.Message('note_on', note=note, velocity=vel, channel=ch))

    def note_off(self, note, ch=0):
        if self.midi_port:
            self.midi_port.send(mido.Message('note_off', note=note, velocity=0, channel=ch))

    def _send_transport(self, cc, val=127):
        """Send transport CC pulse to Ableton (MIDI-learnable)."""
        if self.midi_port:
            self.midi_port.send(mido.Message('control_change', control=cc, value=val, channel=15))
            time.sleep(0.05)
            self.midi_port.send(mido.Message('control_change', control=cc, value=0, channel=15))

    def _start_fe_reader(self):
        """Read Fighting Edge via HID in background thread."""
        import hid as hidlib
        def reader():
            try:
                devs = hidlib.enumerate(0x0F0D, 0x0037)
                if not devs:
                    print("  Fighting Edge not found")
                    return
                dev = hidlib.device()
                dev.open_path(devs[0]['path'])
                dev.set_nonblocking(True)
                print(f"  Fighting Edge: connected")
                prev = None
                while True:
                    data = dev.read(64)
                    if not data:
                        time.sleep(0.005)
                        continue
                    # Parse buttons (byte 0 bitmask)
                    for bit in range(8):
                        cur = (data[0] >> bit) & 1
                        old = (prev[0] >> bit) & 1 if prev else 0
                        if cur != old:
                            self.fe_buttons[bit] = bool(cur)
                            if cur:
                                self._on_fe_button(bit)
                            else:
                                self._on_fe_button_release(bit)
                    # Hat (byte 2)
                    hat = data[2] if len(data) > 2 else 0x0F
                    prev_hat = prev[2] if prev and len(prev) > 2 else 0x0F
                    if hat != prev_hat:
                        self.fe_hat = hat
                    prev = list(data)
            except Exception as e:
                print(f"  FE reader error: {e}")

        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def _get_multiplier(self):
        divisor = 2 if self.fury else 1  # Tiger: thresholds halved
        for threshold, mult in MULT_THRESHOLDS:
            if self.combo >= threshold // divisor:
                return mult
        return 1

    def _get_grade(self, pct):
        for threshold, letter, color in GRADES:
            if pct >= threshold:
                return letter, color
        return "F", C_ENEMY

    def _shake(self, intensity):
        self.shake_intensity = max(self.shake_intensity, intensity)

    def _try_break_combo(self, popup_x, popup_y):
        """Try to break the combo. Returns True if combo actually broke, False if protected."""
        if self.combo <= 0:
            return True
        # Venom — immune to combo break while timer active
        if self.venom and self.venom_timer > 0:
            self.popups.add(popup_x, popup_y, "VENOM!", (80, 200, 50))
            return False
        # Shell — immune for N hits
        if self.shell and self.shell_hits < 5:
            self.shell_hits += 1
            self.popups.add(popup_x, popup_y, f"SHELL! ({5 - self.shell_hits})", (80, 180, 80))
            return False
        # Combo shield (Dog) / Tank (Gorilla, 3 shields)
        if self.combo_shield and self.combo_shield_count < self.combo_shield_max:
            self.combo_shield_count += 1
            remaining = self.combo_shield_max - self.combo_shield_count
            self.popups.add(popup_x, popup_y, f"SHIELD! ({remaining})", C_NEON_GREEN)
            return False
        # No protection — combo breaks
        self.combo = 0
        return True

    def _on_hit(self):
        """Called on every successful hit — refresh venom timer, track combos."""
        if self.venom:
            self.venom_timer = 3.0  # 3s of miss immunity

    def _score_multiplier(self, base_score, mult):
        """Apply frenzy bonus (Shark) — +10% per combo tier."""
        score = base_score * mult
        if self.frenzy:
            tier = 0
            for threshold, m in MULT_THRESHOLDS:
                if self.combo >= threshold:
                    tier = m
                    break
            score = int(score * (1.0 + tier * 0.1))
        return int(score)

    def _on_fe_button(self, btn_idx):
        """Fighting Edge button pressed."""
        if self.state not in ("PLAYING", "STAR_POWER"):
            return

        drum = FE_DRUM_MAP.get(btn_idx)
        if not drum:
            return
        note, name, color = drum

        # Flash the lane
        self.p2_lane_flash[btn_idx] = 1.0

        # Check if there's a drum lane target nearby — timing windows
        hit_something = False
        lane_area_top = HEIGHT - 160
        for dl in self.level.drum_lanes:
            if dl[3]:
                continue
            dx, lane, drum_note, _ = dl
            if lane != btn_idx:
                continue
            dist = abs(self.camera_x + 200 - dx)

            if dist < HIT_PERFECT * self.perfect_bonus:
                dl[3] = True
                hit_something = True
                self.combo += 1
                self.combo_pulse = 1.0
                self._on_hit()
                self.hits += 1
                self.perfects += 1
                if self.combo % 10 == 0 and self.combo > 0:
                    self.combo_10s += 1
                mult = self._get_multiplier()
                self.score += self._score_multiplier(50 * (2 if self.predator else 1), mult)
                self.star_meter = min(1.0, self.star_meter + 0.08 * self.star_fill_bonus)
                self.popups.add(200, lane_area_top - 20, f"PERFECT! x{mult}", C_STAR_GOLD)
                self.particles.emit(200, lane_area_top + lane * 20, 12, C_STAR_GOLD, 200)
                self._shake(6)
                break
            elif dist < HIT_GREAT:
                dl[3] = True
                hit_something = True
                self.combo += 1
                self.combo_pulse = 1.0
                self._on_hit()
                self.hits += 1
                self.greats += 1
                if self.combo % 10 == 0 and self.combo > 0:
                    self.combo_10s += 1
                mult = self._get_multiplier()
                self.score += self._score_multiplier(30, mult)
                self.star_meter = min(1.0, self.star_meter + 0.05 * self.star_fill_bonus)
                self.popups.add(200, lane_area_top - 20, f"GREAT! x{mult}", C_NEON_GREEN)
                self.particles.emit(200, lane_area_top + lane * 20, 8, C_NEON_GREEN, 150)
                self._shake(3)
                break
            elif dist < HIT_GOOD:
                dl[3] = True
                hit_something = True
                self.combo += 1
                self.combo_pulse = 1.0
                self._on_hit()
                self.hits += 1
                self.goods += 1
                if self.combo % 10 == 0 and self.combo > 0:
                    self.combo_10s += 1
                mult = self._get_multiplier()
                self.score += self._score_multiplier(10, mult)
                self.star_meter = min(1.0, self.star_meter + 0.03 * self.star_fill_bonus)
                self.popups.add(200, lane_area_top - 20, f"Good x{mult}", C_HUD)
                self.particles.emit(200, lane_area_top + lane * 20, 4, C_HUD, 80)
                break
            elif dist < HIT_MISS:
                # Too far — miss
                pass

        self.max_combo = max(self.max_combo, self.combo)

        if not hit_something:
            if self._try_break_combo(200, lane_area_top - 20):
                self.popups.add(200, lane_area_top - 20, "Miss", C_ENEMY)

        # Always send drum notes on DRUM_CH (9) — drum rack lives on ch10
        self.note_on(note, 100, DRUM_CH)
        self.pending_offs.append((note, DRUM_CH, time.time() + 0.15))

        # Record into looper
        if self.level and hasattr(self.level, 'loop_duration'):
            t = self.camera_x / max(1, self.level.scroll_speed)  # Convert camera pos to time
            loop_dur = self.level.loop_duration / max(1, self.level.scroll_speed)
            t_in_loop = t % loop_dur if loop_dur > 0 else t
            if self.current_level not in self.recorded_layers:
                self.recorded_layers[self.current_level] = []
            self.recorded_layers[self.current_level].append((t_in_loop, note, 100, DRUM_CH, 0.15))

        # Check star power activation
        if self.combo >= STAR_POWER_THRESHOLD and not self.star_power:
            self.star_power = True
            sp_bars = STAR_POWER_BARS * (2 if self.rage else 1)  # Minotaur: 2x duration
            self.star_power_timer = (60.0 / self.bpm) * 4 * sp_bars
            self.star_power_activations += 1
            self._shake(10)
            self.particles.emit(200, HEIGHT // 2, 30, C_STAR_GOLD, 300, 1.0, 5)
            self.popups.add(WIDTH // 2, HEIGHT // 2 - 60, "STAR POWER!", C_STAR_GOLD)
            print(f"  STAR POWER ACTIVATED! ({STAR_POWER_BARS} bars of free riff)")

    def _on_fe_button_release(self, btn_idx):
        pass

    def run(self):
        running = True
        menu_debounce = 0  # Prevent rapid repeat
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            menu_debounce = max(0, menu_debounce - dt)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state == "PROFILE_SELECT":
                            if self.profile_naming or self.profile_animal_step:
                                self.profile_naming = False
                                self.profile_animal_step = False
                                self.profile_name_buf = ""
                            else:
                                running = False
                        elif self.state == "MAIN_MENU":
                            running = False
                        else:
                            # Return to menu, save profile
                            if self.profile:
                                save_system.save_profile(self.profile)
                            self.state = "MAIN_MENU"
                            self.state_timer = 0
                            self.detected_controllers = self._scan_controllers()
                            self.available_midi = self._scan_midi_ports()

                    elif self.state == "PROFILE_SELECT":
                        self._handle_profile_input(event)

                    elif self.state == "MAIN_MENU" and menu_debounce <= 0:
                        menu_debounce = 0.15
                        if event.key == pygame.K_UP:
                            self.menu_selection = (self.menu_selection - 1) % self._menu_item_count()
                        elif event.key == pygame.K_DOWN:
                            self.menu_selection = (self.menu_selection + 1) % self._menu_item_count()
                        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                            self._menu_adjust(1 if event.key == pygame.K_RIGHT else -1)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if self.menu_selection == self._menu_item_count() - 1:
                                # START selected
                                self._init_game()
                        elif event.key == pygame.K_F5:
                            # Refresh controllers
                            self.detected_controllers = self._scan_controllers()
                            self.available_midi = self._scan_midi_ports()

                    elif event.key == pygame.K_r:
                        self._restart_level()
                    elif event.key == pygame.K_EQUALS:
                        self._adjust_bpm(2)
                    elif event.key == pygame.K_MINUS:
                        self._adjust_bpm(-2)
                    elif event.key == pygame.K_SPACE:
                        if self.state == "LEVEL_INTRO":
                            self._start_level()
                        elif self.state == "LEVEL_COMPLETE":
                            self._next_level()
                    # Number keys for drum testing
                    elif pygame.K_1 <= event.key <= pygame.K_8:
                        self._on_fe_button(event.key - pygame.K_1)
                elif event.type == pygame.KEYUP:
                    if pygame.K_1 <= event.key <= pygame.K_8:
                        self._on_fe_button_release(event.key - pygame.K_1)

            # Joystick input in menu
            if self.joystick and self.state == "MAIN_MENU" and menu_debounce <= 0:
                hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
                if hat[1] == 1:  # up
                    self.menu_selection = (self.menu_selection - 1) % self._menu_item_count()
                    menu_debounce = 0.2
                elif hat[1] == -1:  # down
                    self.menu_selection = (self.menu_selection + 1) % self._menu_item_count()
                    menu_debounce = 0.2
                elif hat[0] != 0:
                    self._menu_adjust(hat[0])
                    menu_debounce = 0.2
                if self.joystick.get_button(0):
                    if self.menu_selection == self._menu_item_count() - 1:
                        self._init_game()
                    menu_debounce = 0.3

            # Joystick buttons during gameplay
            if self.joystick and self.state not in ("MAIN_MENU", "PROFILE_SELECT"):
                for i in range(min(self.joystick.get_numbuttons(), 16)):
                    if self.joystick.get_button(i):
                        if i == 0 and self.state == "LEVEL_INTRO":
                            self._start_level()
                        elif i == 0 and self.state == "LEVEL_COMPLETE":
                            self._next_level()
                        elif i == 4:
                            self._adjust_bpm(-2)
                        elif i == 5:
                            self._adjust_bpm(2)

            # Demo mode auto-advance through menus
            if self.demo_mode:
                self.demo_auto_advance_timer += dt
                if self.state == "PROFILE_SELECT" and self.demo_auto_advance_timer > 0.5:
                    # Auto-create demo profile
                    self.profile = save_system.new_profile("DemoBot", "wolf")
                    self.state = "MAIN_MENU"
                    self.demo_auto_advance_timer = 0
                elif self.state == "MAIN_MENU" and self.demo_auto_advance_timer > 1.0:
                    # Pick a random song and start
                    if self.song_list:
                        self.song_idx = random.randint(0, len(self.song_list) - 1)
                    self._init_game()
                    self.demo_auto_advance_timer = 0
                elif self.state == "LEVEL_INTRO" and self.demo_auto_advance_timer > 2.0:
                    self._start_level()
                    self.demo_auto_advance_timer = 0
                elif self.state == "LEVEL_COMPLETE" and self.demo_auto_advance_timer > 3.0:
                    self._next_level()
                    self.demo_auto_advance_timer = 0

            self._update(dt)
            self._draw()

            # Demo mode overlay with live stats
            if self.demo_mode and self.state in ("PLAYING", "STAR_POWER"):
                pct = (self.hits / max(1, self.total_targets)) * 100 if self.total_targets > 0 else 0
                acc_color = C_STAR_GOLD if pct >= 95 else C_NEON_GREEN if pct >= 80 else C_NEON_CYAN
                demo_line1 = self.font_big.render("DEMO MODE", True, C_STAR_GOLD)
                demo_line2 = self.font.render(
                    f"Accuracy: {pct:.0f}% | Combo: {self.combo} | Hits: {self.hits}/{self.total_targets} | "
                    f"P:{self.perfects} G:{self.greats} OK:{self.goods}",
                    True, acc_color)
                self.screen.blit(demo_line1, (WIDTH // 2 - demo_line1.get_width() // 2, HEIGHT - 42))
                self.screen.blit(demo_line2, (WIDTH // 2 - demo_line2.get_width() // 2, HEIGHT - 22))

            pygame.display.flip()

        self._cleanup()

    def _start_level(self):
        self.state = "PLAYING"
        self.camera_x = -100
        self.combo = 0
        self.hits = 0
        self.total_targets = len(self.level.pickups) + len(self.level.drum_lanes)
        self.level.reset()

        # Reset per-level XP stat counters
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.xp_result = None

        self.combo_shield_used = False  # Reset shield each level
        self.p1_y = HEIGHT // 2        # Reset ship position
        self.loop_playback_head = 0.0  # Sync looper with level start
        self.p1_vy = 0.0               # Reset ship velocity

        # Set Ableton BPM to match the song, then start recording via OSC
        self.osc.set_tempo(self.bpm)
        time.sleep(0.05)
        self.osc.play()
        time.sleep(0.05)
        self.osc.record()
        self.ableton_recording = True
        print(f"  Level {self.current_level + 1}: {self.level.name} - GO! (Ableton: BPM={self.bpm}, REC via OSC)")

    def _next_level(self):
        # Stop Ableton recording via OSC
        self.osc.stop_record()
        self.ableton_recording = False
        self.locked_levels += 1
        recorded_count = len(self.recorded_layers.get(self.current_level, []))
        print(f"  Level {self.current_level + 1} locked! ({self.level.name}) — {recorded_count} notes looping")
        looping_layers = [self.levels[i].name for i in self.recorded_layers if i < self.current_level + 1]
        if looping_layers:
            print(f"  Live looping: {', '.join(looping_layers)}")

        # Move to next level
        self.current_level += 1
        if self.current_level >= len(self.levels):
            self.current_level = 0
            print("  All levels complete! Looping from start with all layers.")

        self.level = self.levels[self.current_level]
        self.scroll_speed = self.level.scroll_speed
        self.state = "LEVEL_INTRO"
        self.state_timer = 0
        self.star_power = False
        self.star_meter = 0

    def _restart_level(self):
        # Stop Ableton recording if active
        if self.ableton_recording:
            self.osc.stop_record()
            self.osc.stop()
            self.ableton_recording = False
        self.camera_x = -100
        self.combo = 0
        self.hits = 0
        self.star_power = False
        self.star_meter = 0
        self.level.reset()
        self.state = "LEVEL_INTRO"

    def _adjust_bpm(self, delta):
        self.bpm = max(60, min(200, self.bpm + delta))
        self.beat_interval = 60.0 / self.bpm
        self.scroll_speed = (self.bpm * 4 / 60.0) * (TILE * 2)
        self.level.scroll_speed = self.scroll_speed
        self.osc.set_tempo(self.bpm)  # Sync Ableton BPM
        print(f"  BPM: {self.bpm} (Ableton synced)")

    def _update(self, dt):
        self.state_timer += dt

        # Beat tracking
        self.beat_timer += dt
        if self.beat_timer >= self.beat_interval:
            self.beat_timer -= self.beat_interval
            self.beat_flash = 1.0
        self.beat_flash *= 0.85

        # Venom timer decay
        if self.venom_timer > 0:
            self.venom_timer -= dt
        self.combo_pulse *= 0.88  # Combo pulse decays each frame

        # Lane flashes decay
        for k in list(self.p2_lane_flash.keys()):
            self.p2_lane_flash[k] *= 0.85
            if self.p2_lane_flash[k] < 0.05:
                del self.p2_lane_flash[k]

        # Star power timer
        if self.star_power:
            self.star_power_timer -= dt
            if self.star_power_timer <= 0:
                self.star_power = False
                print("  Star Power ended")

        # Pending note offs
        now = time.time()
        still = []
        for note, ch, off_time in self.pending_offs:
            if now >= off_time:
                self.note_off(note, ch)
            else:
                still.append((note, ch, off_time))
        self.pending_offs = still

        # === LIVE LOOPER: play back completed layers as MIDI ===
        if self.state in ("PLAYING", "STAR_POWER") and self.level:
            old_loop_head = self.loop_playback_head
            self.loop_playback_head += dt
            # Get loop duration in seconds for the current level
            if self.level.scroll_speed > 0:
                current_loop_dur = self.level.level_width / self.level.scroll_speed
            else:
                current_loop_dur = (60.0 / self.bpm) * 4 * 8  # fallback 8 bars

            # Wrap the playback head
            if current_loop_dur > 0 and self.loop_playback_head >= current_loop_dur:
                self.loop_playback_head -= current_loop_dur

            # Play back all locked layers
            for lvl_idx, recorded in self.recorded_layers.items():
                if lvl_idx >= self.current_level:
                    continue  # Only play back COMPLETED levels
                for t, note, vel, ch, dur in recorded:
                    # Check if this note should play right now
                    if current_loop_dur > 0:
                        t_wrapped = t % current_loop_dur
                        if old_loop_head <= t_wrapped < self.loop_playback_head:
                            self.note_on(note, vel, ch)
                            self.pending_offs.append((note, ch, now + dur))
                        # Handle wrap-around
                        elif old_loop_head > self.loop_playback_head and (t_wrapped >= old_loop_head or t_wrapped < self.loop_playback_head):
                            self.note_on(note, vel, ch)
                            self.pending_offs.append((note, ch, now + dur))

        # Update particles & popups always
        self.particles.update(dt)
        self.popups.update(dt)

        # Screen shake decay
        if self.shake_intensity > 0.1:
            self.shake_x = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_y = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_intensity *= 0.85
        else:
            self.shake_x = self.shake_y = 0
            self.shake_intensity = 0

        if self.state != "PLAYING" and self.state != "STAR_POWER":
            return

        # Joystick input
        joy_x, joy_y = 0, 0
        if self.joystick:
            joy_x = self.joystick.get_axis(0)
            joy_y = self.joystick.get_axis(1)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]: joy_y = -0.8
        if keys[pygame.K_DOWN]: joy_y = 0.8

        # ===== DEMO BOT — auto-play for testing =====
        if self.demo_mode:
            player_x = self.camera_x + 200

            # Auto-steer ship — look ahead at next 2 uncollected notes
            upcoming = []
            for pickup in self.level.pickups:
                if pickup[3]:
                    continue
                px, py, note, _ = pickup
                ahead = px - player_x
                if -20 < ahead < 600:
                    upcoming.append((ahead, py))
                if len(upcoming) >= 3:
                    break

            if upcoming:
                # Weighted average — closer notes matter more, but anticipate the next one
                if len(upcoming) >= 2:
                    w1, w2 = 0.7, 0.3
                    target_y = upcoming[0][1] * w1 + upcoming[1][1] * w2
                else:
                    target_y = upcoming[0][1]
            else:
                target_y = self.p1_y

            # PID-style steering — proportional + derivative + integral
            diff = target_y - self.p1_y
            if abs(diff) > 2:
                p_gain = diff / 25.0  # Stronger proportional
                d_gain = -self.p1_vy / 400.0  # Velocity damping
                joy_y = max(-1.0, min(1.0, p_gain + d_gain))
            else:
                joy_y = 0
                self.p1_vy *= 0.3  # Hard brake when on target

            # Auto-hit drums — fire within the perfect window only
            for dl in self.level.drum_lanes:
                if dl[3]:
                    continue
                dx, lane_idx, drum_note, _ = dl
                dist = player_x - dx  # Positive = past target
                # Fire when target is 0-10px ahead of hit line (guaranteed perfect)
                if -10 <= dist <= 10:
                    self._on_fe_button(lane_idx)

        # Speed
        self.speed_mult = 1.0 + joy_x * 0.3
        self.speed_mult = max(0.5, min(1.5, self.speed_mult))

        # Scroll
        actual_speed = self.scroll_speed * self.speed_mult * self.speed_bonus
        self.camera_x += actual_speed * dt

        # Level complete?
        if self.camera_x > self.level.level_width + 200:
            self.state = "LEVEL_COMPLETE"
            # Stop Ableton recording via OSC — clip captured
            if self.ableton_recording:
                self.osc.stop_record()
                self.ableton_recording = False
            print(f"  Level complete! Hits: {self.hits}/{self.total_targets} | Max combo: {self.max_combo}")

            # Award XP via save system
            pct = (self.hits / max(1, self.total_targets)) * 100
            grade_letter, grade_color = self._get_grade(pct)
            if self.profile:
                self.xp_result = save_system.award_xp(
                    self.profile,
                    hits=self.hits,
                    perfects=self.perfects,
                    greats=self.greats,
                    goods=self.goods,
                    combo_10s=self.combo_10s,
                    star_powers=self.star_power_activations,
                    levels_complete=1,
                    grade=grade_letter,
                )
                self.profile["games_played"] = self.profile.get("games_played", 0) + 1
                self.profile["total_hits"] = self.profile.get("total_hits", 0) + self.hits
                self.profile["total_perfects"] = self.profile.get("total_perfects", 0) + self.perfects
                self.profile["total_score"] = self.profile.get("total_score", 0) + self.score
                self.profile["best_combo"] = max(self.profile.get("best_combo", 0), self.max_combo)
                # Track best grade
                grade_order = ["F", "D", "C", "B", "A", "S"]
                old_g = self.profile.get("best_grade", "F")
                if grade_order.index(grade_letter) > grade_order.index(old_g):
                    self.profile["best_grade"] = grade_letter
                save_system.save_profile(self.profile)
                print(f"  XP earned: {self.xp_result['xp_earned']} | Level: {self.xp_result['new_level']}")
                if self.xp_result['leveled_up']:
                    print(f"  LEVEL UP! {self.xp_result['old_level']} -> {self.xp_result['new_level']}")

            # Big particle burst in the grade's color
            for _ in range(3):  # Multiple burst points across screen
                bx = random.randint(WIDTH // 4, WIDTH * 3 // 4)
                self.particles.emit(bx, HEIGHT // 3, 40, grade_color, speed=250, life=1.5, size=4, spread=5.0)
            return

        # P1 ship-style flight — thrust adds velocity, drag slows you down
        is_melody_level = len(self.level.pickups) > 0
        if is_melody_level:
            play_top = self.level.play_top
            play_bottom = self.level.play_bottom
            thrust = 1800.0 if self.agile else 1200.0  # Monkey: +50% acceleration
            if self.flight:
                drag = 1.5    # Pegasus: minimal drag, floaty feel
                max_vel = 600.0
            else:
                drag = 4.0
                max_vel = 500.0

            # Note magnetism — find next uncollected note and pull toward it
            player_x = self.camera_x + 200
            magnet_strength = 200.0  # pull force
            best_dist = 99999
            next_note_y = None
            for pickup in self.level.pickups:
                if pickup[3]:  # collected
                    continue
                px, py, note, _ = pickup
                ahead = px - player_x
                if -30 < ahead < 400:  # upcoming notes within view
                    if ahead < best_dist:
                        best_dist = ahead
                        next_note_y = py
            # Store for guide line drawing
            self._next_note_y = next_note_y
            self._next_note_dist = best_dist if next_note_y else 0

            if next_note_y is not None:
                # Gentle pull toward next note (stronger when closer)
                closeness = max(0, 1.0 - best_dist / 400.0)  # 1.0 when right on it, 0 when 400px away
                diff = next_note_y - self.p1_y
                self.p1_vy += diff * magnet_strength * closeness * dt

            # Apply thrust from joystick input (overrides magnetism when active)
            self.p1_vy += joy_y * thrust * dt

            # Drag — always pulls velocity toward zero
            self.p1_vy -= self.p1_vy * drag * dt

            # Clamp velocity
            self.p1_vy = max(-max_vel, min(max_vel, self.p1_vy))

            # Move
            self.p1_y += self.p1_vy * dt

            # Bounce off edges (soft)
            if self.p1_y < play_top:
                self.p1_y = play_top
                self.p1_vy = abs(self.p1_vy) * 0.3  # Soft bounce
            elif self.p1_y > play_bottom:
                self.p1_y = play_bottom
                self.p1_vy = -abs(self.p1_vy) * 0.3

        # Melody notes — auto-play at correct musical time, score based on ship proximity
        player_x = self.camera_x + 200
        for pickup in self.level.pickups:
            if pickup[3]:
                continue
            px, py, note, _ = pickup

            # Note reaches the hit line — ALWAYS play it for correct music
            if player_x >= px - 5:
                pickup[3] = True
                dy = abs(self.p1_y - py)

                # Always send the MIDI note so the song sounds right
                # Adaptive collection radius — wider for fast note sequences
                base_radius = 77 if self.soar else 55
                # Check density: if next note is close horizontally, widen radius
                next_dx = 999
                for p2 in self.level.pickups:
                    if p2[3] or p2 is pickup:
                        continue
                    nd = abs(p2[0] - px)
                    if 0 < nd < next_dx:
                        next_dx = nd
                if next_dx < 40:  # Very dense — notes almost on top of each other
                    collect_radius = base_radius + 30
                elif next_dx < 80:
                    collect_radius = base_radius + 15
                else:
                    collect_radius = base_radius
                if dy < collect_radius:
                    # Ship is close — full velocity, score it
                    mel_ch = getattr(self.level, 'midi_channel', self.p1_midi_ch)
                    self.note_on(note, 100, mel_ch)
                    # Record into looper
                    t = self.camera_x / max(1, self.level.scroll_speed)
                    loop_dur = self.level.loop_duration / max(1, self.level.scroll_speed)
                    t_in_loop = t % loop_dur if loop_dur > 0 else t
                    if self.current_level not in self.recorded_layers:
                        self.recorded_layers[self.current_level] = []
                    self.recorded_layers[self.current_level].append((t_in_loop, note, 100, mel_ch, 0.25))
                    self.hits += 1
                    self.combo += 1
                    self.combo_pulse = 1.0
                    self.max_combo = max(self.max_combo, self.combo)
                    if self.combo % 10 == 0 and self.combo > 0:
                        self.combo_10s += 1
                    mult = self._get_multiplier()

                    if dy < 15 * self.perfect_bonus:
                        self.perfects += 1
                        self.score += self._score_multiplier(50 * (2 if self.predator else 1), mult)
                        self.star_meter = min(1.0, self.star_meter + 0.08 * self.star_fill_bonus)
                        self.popups.add(200, int(self.p1_y) - 30, f"PERFECT! x{mult}", C_STAR_GOLD)
                        self.particles.emit(200, int(py), 12, C_STAR_GOLD, 180)
                        self._shake(4)
                    elif dy < 30:
                        self.greats += 1
                        self.score += self._score_multiplier(30, mult)
                        self.star_meter = min(1.0, self.star_meter + 0.05 * self.star_fill_bonus)
                        self.popups.add(200, int(self.p1_y) - 30, f"GREAT! x{mult}", C_NEON_GREEN)
                        self.particles.emit(200, int(py), 8, C_NEON_GREEN, 120)
                    else:
                        self.goods += 1
                        self.score += self._score_multiplier(10, mult)
                        self.star_meter = min(1.0, self.star_meter + 0.03 * self.star_fill_bonus)
                        self.popups.add(200, int(self.p1_y) - 30, f"Good x{mult}", C_HUD)
                        self.particles.emit(200, int(py), 4, C_HUD, 60)
                else:
                    # Ship is far — play note quietly (song stays intact) but no score
                    self.note_on(note, 50, getattr(self.level, 'midi_channel', self.p1_midi_ch))  # Quieter
                    self._try_break_combo(200, int(py))

                mel_ch = getattr(self.level, 'midi_channel', self.p1_midi_ch)
                self.pending_offs.append((note, mel_ch, time.time() + 0.25))

        # Auto-play drum targets that pass the hit line (so song stays in time)
        for dl in self.level.drum_lanes:
            if dl[3]:  # Already hit by player
                continue
            dx, lane_idx, drum_note, _ = dl
            # Target has passed the hit line
            if player_x >= dx + HIT_MISS:
                dl[3] = True  # Mark as passed
                # Play it quietly so the backing track stays intact
                self.note_on(drum_note, 40, DRUM_CH)
                self.pending_offs.append((drum_note, DRUM_CH, time.time() + 0.1))

        # Star Power riffing (joystick freely plays notes)
        if self.star_power:
            # Auto-play notes at rhythm based on joystick position
            if self.beat_flash > 0.9:  # On each beat
                degree = int(self.p1_y / HEIGHT * len(self.scale))
                degree = max(0, min(len(self.scale) - 1, degree))
                riff_note = self.scale[degree]
                riff_ch = getattr(self.level, 'midi_channel', self.p1_midi_ch)
                self.note_on(riff_note, 100, riff_ch)
                self.pending_offs.append((riff_note, riff_ch, time.time() + 0.15))

        # Fire trail and sparkles — only on melody levels with visible ship
        if is_melody_level:
            if self.combo >= 10:
                intensity = min(3.0, self.combo / 15.0)
                self.particles.emit_fire(190, int(self.p1_y) + 10, intensity)
            if self.star_power:
                self.particles.emit_star(200, int(self.p1_y))

    def _draw(self):
        self.screen.fill(C_BG)

        if self.state == "PROFILE_SELECT":
            self._draw_profile_select()
            return
        if self.state == "MAIN_MENU":
            self._draw_menu()
            return
        if self.state == "LEVEL_INTRO":
            self._draw_intro()
            return
        if self.state == "LEVEL_COMPLETE":
            self._draw_complete()
            return

        cam = int(self.camera_x)
        sx_off = int(self.shake_x)
        sy_off = int(self.shake_y)

        # Stars (parallax layer 0 - slowest)
        for sx, sy, b in self.stars:
            screen_x = int((sx - cam * 0.05) % (WIDTH * 4)) - WIDTH + sx_off
            if 0 <= screen_x < WIDTH:
                brightness = b * (1.0 + self.beat_flash * 0.5)
                self.screen.set_at((screen_x, sy), (int(min(255,brightness*150)), int(min(255,brightness*130)), int(min(255,brightness*200))))

        # City skyline (parallax layer 1)
        ground_y = HEIGHT - 170
        draw_skyline(self.screen, self.skyline, cam, ground_y, self.beat_flash)

        # Tron grid floor — perspective lines receding to horizon
        horizon_y = ground_y - 60
        grid_color_h = (*C_NEON_CYAN[:3],)
        grid_color_v = (*C_NEON_PINK[:3],)

        # Horizontal grid lines (receding into distance)
        for i in range(12):
            frac = i / 12.0
            y = int(horizon_y + (ground_y - horizon_y) * (frac ** 0.6))
            alpha = int(10 + 30 * frac)
            gs = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
            gs.fill((*grid_color_h, alpha))
            self.screen.blit(gs, (0, y))

        # Vertical grid lines (converging to vanishing point)
        vanish_x = WIDTH // 2
        for i in range(-10, 11):
            bx = vanish_x + i * 80  # bottom x
            tx = vanish_x + i * 8   # top x (converge)
            alpha = max(8, 25 - abs(i) * 2)
            pygame.draw.line(self.screen, (*grid_color_v[:3],), (tx, horizon_y), (bx, ground_y), 1)

        # Ground line with neon glow
        pygame.draw.line(self.screen, C_GROUND_TOP, (0, ground_y), (WIDTH, ground_y), 2)
        for w, a in [(8, 15), (4, 30), (2, 60)]:
            glow_surf = pygame.Surface((WIDTH, w), pygame.SRCALPHA)
            glow_surf.fill((*C_NEON_CYAN, a))
            self.screen.blit(glow_surf, (0, ground_y - w//2))

        # Scrolling ground dashes — road markings for speed sensation
        dash_w, dash_h, dash_gap = 20, 3, 40
        dash_y_center = ground_y + 6
        dash_offset = int(cam * 0.8) % (dash_w + dash_gap)
        dash_color = (50, 30, 70)
        for dx in range(-dash_offset, WIDTH + dash_w, dash_w + dash_gap):
            pygame.draw.rect(self.screen, dash_color, (dx + sx_off, dash_y_center + sy_off, dash_w, dash_h))
        # Second lane of dashes offset below
        dash_y2 = ground_y + 16
        dash_offset2 = int(cam * 0.8 + (dash_w + dash_gap) // 2) % (dash_w + dash_gap)
        for dx in range(-dash_offset2, WIDTH + dash_w, dash_w + dash_gap):
            pygame.draw.rect(self.screen, (40, 25, 55), (dx + sx_off, dash_y2 + sy_off, dash_w, dash_h))

        # (Light trail drawn after P1 position is set below)

        # Drum lanes (bottom section for Fighting Edge player)
        lane_h = 20
        lane_area_top = HEIGHT - 160
        lane_area_h = 8 * lane_h + 16

        # Lane background with gradient
        lane_bg = pygame.Surface((WIDTH, lane_area_h + 16), pygame.SRCALPHA)
        lane_bg.fill((15, 10, 30, 200))
        self.screen.blit(lane_bg, (0 + sx_off, lane_area_top - 8 + sy_off))

        hit_line_x = 200

        for lane_idx in range(8):
            lane_y = lane_area_top + lane_idx * lane_h + sy_off
            # Lane line
            pygame.draw.line(self.screen, C_LANE_LINE, (0, lane_y), (WIDTH, lane_y))
            # Lane label
            _, name, color = FE_DRUM_MAP[lane_idx]
            label = self.font.render(name, True, color)
            self.screen.blit(label, (5 + sx_off, lane_y + 2))
            # Flash on hit — full lane flash
            if lane_idx in self.p2_lane_flash:
                flash_surf = pygame.Surface((WIDTH, lane_h), pygame.SRCALPHA)
                alpha = int(self.p2_lane_flash[lane_idx] * 150)
                flash_surf.fill((*color, alpha))
                self.screen.blit(flash_surf, (0 + sx_off, lane_y))

        # Hit line with glow
        for w, a in [(6, 30), (3, 80), (1, 200)]:
            line_surf = pygame.Surface((w, lane_area_h + 16), pygame.SRCALPHA)
            line_surf.fill((*C_NEON_CYAN, a))
            self.screen.blit(line_surf, (hit_line_x - w//2 + sx_off, lane_area_top - 8 + sy_off))

        # Approach indicators — lines marking timing windows
        for dist, color, alpha in [(HIT_PERFECT, C_STAR_GOLD, 40), (HIT_GREAT, C_NEON_GREEN, 25), (HIT_GOOD, C_HUD, 15)]:
            for side in (-1, 1):
                x = hit_line_x + dist * side + sx_off
                s = pygame.Surface((1, lane_area_h), pygame.SRCALPHA)
                s.fill((*color, alpha))
                self.screen.blit(s, (x, lane_area_top - 4 + sy_off))

        # Drum lane targets with approach glow
        for dl in self.level.drum_lanes:
            dx, lane_idx, drum_note, hit = dl
            screen_x = dx - cam + sx_off
            if screen_x < -20 or screen_x > WIDTH + 20:
                continue
            if hit:
                continue
            lane_y = lane_area_top + lane_idx * lane_h + sy_off
            _, name, color = FE_DRUM_MAP.get(lane_idx, (0, "?", (100,100,100)))

            # Approach glow — brighter as it nears hit line
            dist_to_hit = abs(screen_x - hit_line_x)
            if dist_to_hit < 150:
                glow_alpha = int((1.0 - dist_to_hit / 150.0) * 80)
                glow_s = pygame.Surface((24, lane_h), pygame.SRCALPHA)
                glow_s.fill((*color, glow_alpha))
                self.screen.blit(glow_s, (screen_x - 12, lane_y))

            # Target marker with border
            pygame.draw.rect(self.screen, color, (screen_x - 8, lane_y + 2, 16, lane_h - 4), border_radius=3)
            pygame.draw.rect(self.screen, (255,255,255), (screen_x - 8, lane_y + 2, 16, lane_h - 4), 1, border_radius=3)

        # Melody pickups (upper area for joystick player)
        for pickup in self.level.pickups:
            px, py, note, collected = pickup
            screen_x = px - cam + sx_off
            if collected or screen_x < -20 or screen_x > WIDTH + 20:
                continue
            hue = (note * 30) % 360
            color = self._hsv(hue, 0.9, 1.0)
            bob_y = py + math.sin(time.time() * 4 + px * 0.01) * 4 + sy_off

            # Connection line to next pickup
            glow = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, 60), (16, 16), 16)
            pygame.draw.circle(glow, (*color, 180), (16, 16), 8)
            pygame.draw.circle(glow, (255, 255, 255), (16, 16), 3)
            self.screen.blit(glow, (screen_x - 16, bob_y - 16))

        # Guide line to next uncollected note
        is_melody_level = len(self.level.pickups) > 0
        if is_melody_level and hasattr(self, '_next_note_y') and self._next_note_y is not None:
            p1_sy = int(self.p1_y) + sy_off
            target_y = int(self._next_note_y) + sy_off
            # Dashed guide line from ship to next note
            dist = self._next_note_dist
            alpha = max(20, min(80, int((1.0 - dist / 400.0) * 80)))
            guide_color = C_STAR_GOLD if self.star_power else (0, 150, 200)
            # Draw dots along the path
            steps = max(2, int(abs(target_y - p1_sy) / 8))
            for i in range(0, steps, 2):  # Dashed
                frac = i / max(1, steps)
                gy = int(p1_sy + (target_y - p1_sy) * frac)
                gx = 200 + int(frac * min(100, dist * 0.3)) + sx_off
                dot = pygame.Surface((3, 3), pygame.SRCALPHA)
                dot.fill((*guide_color, alpha))
                self.screen.blit(dot, (gx, gy))

        # P1 ship sprite — only on melody levels (not drums-only)
        if is_melody_level:
            p1_screen_x = 200 + sx_off
            p1_y = int(self.p1_y) + sy_off
            p1_ch = self.CHARACTERS[self.p1_char_idx]
            glow_color = C_STAR_GOLD if self.star_power else p1_ch["color"]

            # Tron light trail behind ship
            trail_len = min(180, int(self.combo * 3) + 20)
            trail_color = C_STAR_GOLD if self.star_power else p1_ch["color"]
            for i in range(trail_len, 0, -3):
                alpha = int((1.0 - i / trail_len) * 60)
                ts = pygame.Surface((3, 4), pygame.SRCALPHA)
                ts.fill((*trail_color, alpha))
                self.screen.blit(ts, (p1_screen_x - i, p1_y - 2))

            # Engine glow (tilts with velocity)
            tilt = self.p1_vy / 350.0  # -1 to 1
            for radius, alpha in [(40, 15), (30, 25), (20, 40)]:
                aura = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
                pygame.draw.circle(aura, (*glow_color, alpha), (radius, radius), radius)
                self.screen.blit(aura, (p1_screen_x + 16 - radius, p1_y - radius + int(tilt * 5)))

            # Sprite (slight visual tilt)
            sprite = self.p1_sprite
            if abs(tilt) > 0.15:
                angle = -tilt * 15  # tilt sprite with velocity
                sprite = pygame.transform.rotate(self.p1_sprite, angle)
            self.screen.blit(sprite, (p1_screen_x, p1_y - sprite.get_height()//2))

        # P2 indicator — only in 2P mode
        if self.menu_player_mode == 1:
            self.screen.blit(self.p2_sprite, (hit_line_x - 16 + sx_off, lane_area_top - 40 + sy_off))

        # Star power meter with glow
        meter_w = 160
        meter_h = 12
        mx = WIDTH - meter_w - 20 + sx_off
        my = 50 + sy_off
        pygame.draw.rect(self.screen, (20, 20, 40), (mx - 1, my - 1, meter_w + 2, meter_h + 2), border_radius=3)
        fill_w = int(self.star_meter * meter_w)
        star_color = C_STAR_GOLD if self.star_power else (100, 80, 0)
        if fill_w > 0:
            pygame.draw.rect(self.screen, star_color, (mx, my, fill_w, meter_h), border_radius=2)
            # Glow on meter
            if self.star_power:
                gs = pygame.Surface((fill_w, meter_h + 6), pygame.SRCALPHA)
                gs.fill((*C_STAR_GOLD, 40))
                self.screen.blit(gs, (mx, my - 3))
        pygame.draw.rect(self.screen, (80, 80, 100), (mx - 1, my - 1, meter_w + 2, meter_h + 2), 1, border_radius=3)
        star_label = "STAR POWER!" if self.star_power else f"Star: {int(self.star_meter*100)}%"
        self.screen.blit(self.font.render(star_label, True, star_color), (mx, my - 18))

        # Combo counter with pulse animation and tier colors
        mult = self._get_multiplier()
        # Tier color: white(0) -> green(10+) -> cyan(20+) -> gold(40+)
        if self.combo >= 40:
            combo_color = C_STAR_GOLD
        elif self.combo >= 20:
            combo_color = C_NEON_CYAN
        elif self.combo >= 10:
            combo_color = C_NEON_GREEN
        else:
            combo_color = (220, 220, 220)
        if self.combo > 0:
            combo_str = f"{self.combo}"
            pulse_scale = 1.0 + self.combo_pulse * 0.4  # up to 1.4x on hit
            combo_surf = self.font_title.render(combo_str, True, combo_color)
            if pulse_scale > 1.02:
                new_w = int(combo_surf.get_width() * pulse_scale)
                new_h = int(combo_surf.get_height() * pulse_scale)
                combo_surf = pygame.transform.scale(combo_surf, (new_w, new_h))
            cx_combo = WIDTH - 80 + sx_off - combo_surf.get_width() // 2
            cy_combo = 78 + sy_off - combo_surf.get_height() // 2
            self.screen.blit(combo_surf, (cx_combo, cy_combo))
        if mult > 1:
            mult_colors = {2: C_NEON_GREEN, 4: C_NEON_CYAN, 8: C_STAR_GOLD}
            mc = mult_colors.get(mult, C_NEON_PINK)
            mult_text = self.font.render(f"x{mult}", True, mc)
            self.screen.blit(mult_text, (WIDTH - 80 + sx_off - mult_text.get_width() // 2, 100 + sy_off))

        # Progress bar
        if self.level.level_width > 0:
            progress = min(1.0, max(0, self.camera_x / self.level.level_width))
            bar_w = WIDTH - 40
            bar_y = 68 + sy_off
            pygame.draw.rect(self.screen, (20, 20, 40), (20 + sx_off, bar_y, bar_w, 4), border_radius=2)
            fill = int(progress * bar_w)
            if fill > 0:
                bar_color = C_STAR_GOLD if self.star_power else C_NEON_CYAN
                pygame.draw.rect(self.screen, bar_color, (20 + sx_off, bar_y, fill, 4), border_radius=2)

        # Beat flash — bottom and top edges
        if self.beat_flash > 0.1:
            alpha = int(self.beat_flash * 120)
            for y_pos in [0, HEIGHT - 3]:
                flash = pygame.Surface((WIDTH, 3), pygame.SRCALPHA)
                flash.fill((*C_NEON_CYAN, alpha))
                self.screen.blit(flash, (0, y_pos))

        # Particles & popups on top of everything
        self.particles.draw(self.screen)
        self.popups.draw(self.screen)

        # HUD
        self._draw_hud()

    def _draw_intro(self):
        self.screen.fill(C_BG)

        # Skyline behind intro
        draw_skyline(self.screen, self.skyline, int(time.time() * 20), HEIGHT - 170)
        # Ground
        pygame.draw.line(self.screen, C_GROUND_TOP, (0, HEIGHT - 170), (WIDTH, HEIGHT - 170), 2)

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 140))
        self.screen.blit(overlay, (0, 0))

        cx, cy = WIDTH // 2, HEIGHT // 2

        # Level number with large glow
        level_font = pygame.font.SysFont("consolas", 64)
        level_num = level_font.render(f"{self.current_level + 1}", True, C_NEON_CYAN)
        pulse = 0.6 + 0.4 * math.sin(time.time() * 2)
        glow = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_NEON_CYAN, int(30 * pulse)), (60, 60), 60)
        self.screen.blit(glow, (cx - 60, cy - 130))
        self.screen.blit(level_num, (cx - level_num.get_width()//2, cy - 110))

        # Song name (if from library)
        if self.song_list:
            song = self.song_list[self.song_idx]
            song_title = self.font_menu.render(f"{song['artist']} - {song['title']}", True, C_HUD_DIM)
            self.screen.blit(song_title, (cx - song_title.get_width()//2, cy - 60))

        # Level name
        title = self.font_title.render(f"{self.level.name}", True, C_NEON_PINK)
        self.screen.blit(title, (cx - title.get_width()//2, cy - 40))

        inst = self.font_big.render(f"{self.level.instrument_name}  |  {self.bpm} BPM  |  {self.level.bars} bars", True, C_HUD)
        self.screen.blit(inst, (cx - inst.get_width()//2, cy + 10))

        # Active layers
        if self.locked_levels > 0:
            layer_names = ', '.join(self.levels[i].name for i in range(min(self.locked_levels, len(self.levels))))
            loop_text = self.font.render(f"Looping in Ableton: {layer_names}", True, C_NEON_GREEN)
            self.screen.blit(loop_text, (cx - loop_text.get_width()//2, cy + 50))

        # Controls
        if self.level.drum_lanes:
            lines = [
                "Fighting Edge: Sq=KICK  X=SNARE  O=HH  Tri=OH  L1=CRASH  R1=RIDE  L2=LTOM  R2=HTOM",
                "Hit drums in time with the scrolling targets!"
            ]
        else:
            lines = [
                "Joystick UP/DOWN = steer through melody notes",
                "Collect the glowing orbs to play the melody!"
            ]
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, C_HUD_DIM)
            self.screen.blit(surf, (cx - surf.get_width()//2, cy + 80 + i * 20))

        # Timing guide
        timing_y = cy + 130
        for label, color in [("PERFECT", C_STAR_GOLD), ("GREAT", C_NEON_GREEN), ("Good", C_HUD)]:
            surf = self.font.render(f"  {label}  ", True, color)
            self.screen.blit(surf, (cx - 200 + [("PERFECT", C_STAR_GOLD), ("GREAT", C_NEON_GREEN), ("Good", C_HUD)].index((label, color)) * 140, timing_y))

        pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
        go = self.font_big.render("Press TRIGGER / SPACE to start", True,
                                   (int(C_NEON_CYAN[0]*pulse), int(C_NEON_CYAN[1]*pulse), int(C_NEON_CYAN[2]*pulse)))
        self.screen.blit(go, (cx - go.get_width()//2, cy + 170))

    def _draw_complete(self):
        self.screen.fill(C_BG)

        # Draw skyline behind
        draw_skyline(self.screen, self.skyline, int(self.camera_x), HEIGHT - 170, self.beat_flash)

        # Particles still render
        self.particles.draw(self.screen)

        cx, cy = WIDTH // 2, HEIGHT // 2

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 180))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render("LEVEL COMPLETE!", True, C_NEON_GREEN)
        self.screen.blit(title, (cx - title.get_width()//2, cy - 120))

        pct = (self.hits / max(1, self.total_targets)) * 100
        grade, grade_color = self._get_grade(pct)

        # Big grade letter
        grade_font = pygame.font.SysFont("consolas", 72)
        grade_surf = grade_font.render(grade, True, grade_color)
        # Pulsing glow
        pulse = 0.7 + 0.3 * math.sin(time.time() * 3)
        glow = pygame.Surface((grade_surf.get_width() + 40, grade_surf.get_height() + 40), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*grade_color, int(40 * pulse)),
                           (glow.get_width()//2, glow.get_height()//2), glow.get_width()//2)
        self.screen.blit(glow, (cx + 120 - glow.get_width()//2, cy - 40 - glow.get_height()//2))
        self.screen.blit(grade_surf, (cx + 120 - grade_surf.get_width()//2, cy - 40 - grade_surf.get_height()//2))

        stats = [
            (f"Accuracy: {pct:.0f}%", C_HUD),
            (f"Score: {self.score:,}", C_NEON_CYAN),
            (f"Max Combo: {self.max_combo}x", C_NEON_PINK),
            (f"Hits: {self.hits}/{self.total_targets}", C_HUD_DIM),
        ]

        # XP results
        if self.xp_result:
            stats.append((f"+{self.xp_result['xp_earned']} XP", C_STAR_GOLD))
            if self.xp_result['leveled_up']:
                stats.append((f"LEVEL UP! Lv.{self.xp_result['new_level']}", C_NEON_GREEN))
                for unlock in self.xp_result.get('new_unlocks', []):
                    stats.append((f"Unlocked: {unlock}", C_NEON_YELLOW))

        for i, (s, color) in enumerate(stats):
            surf = self.font_big.render(s, True, color)
            self.screen.blit(surf, (cx - 160, cy - 60 + i * 28))

        loop_msg = f"Clip recorded! Set to LOOP in Ableton. Arm next track. Press TRIGGER / SPACE"
        pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
        go = self.font.render(loop_msg, True, (int(255*pulse), int(200*pulse), 0))
        self.screen.blit(go, (cx - go.get_width()//2, cy + 100))

    def _draw_hud(self):
        lv = self.level
        bar_num = int(self.camera_x / max(1, lv.level_width) * lv.bars) + 1
        texts = [
            (f"MOONWOLF LAYERS", C_NEON_CYAN, 10, 8, self.font_big),
            (f"Level {self.current_level+1}: {lv.name} | {self.bpm} BPM | Bar {bar_num}/{lv.bars}", C_HUD, 10, 35, self.font),
            (f"Score: {self.score} | Combo: x{self.combo} | Layers: {self.locked_levels} | {'REC' if self.ableton_recording else 'IDLE'}", C_HUD_DIM, 10, 52, self.font),
            (f"[+/-]=BPM [R]=Restart [ESC]=Quit | Combo {STAR_POWER_THRESHOLD}+ = Star Power (free riff!)", C_HUD_DIM, 10, HEIGHT - 18, self.font),
        ]
        for text, color, x, y, font in texts:
            self.screen.blit(font.render(text, True, color), (x, y))

        # XP bar (top right)
        if self.profile:
            level, xp_into, xp_needed = save_system.xp_progress(self.profile["xp"])
            xp_bar_w, xp_bar_h = 120, 8
            xp_x = WIDTH - xp_bar_w - 10
            xp_y = 10
            lv_surf = self.font.render(f"Lv.{level}", True, C_NEON_CYAN)
            self.screen.blit(lv_surf, (xp_x - lv_surf.get_width() - 5, xp_y - 2))
            pygame.draw.rect(self.screen, (30, 25, 50), (xp_x, xp_y, xp_bar_w, xp_bar_h))
            fill = int(xp_bar_w * xp_into / max(1, xp_needed))
            pygame.draw.rect(self.screen, C_NEON_CYAN, (xp_x, xp_y, fill, xp_bar_h))

    def _hsv(self, h, s, v):
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c
        if h < 60:    r, g, b = c, x, 0
        elif h < 120: r, g, b = x, c, 0
        elif h < 180: r, g, b = 0, c, x
        elif h < 240: r, g, b = 0, x, c
        elif h < 300: r, g, b = x, 0, c
        else:         r, g, b = c, 0, x
        return (int((r+m)*255), int((g+m)*255), int((b+m)*255))

    # ===== PROFILE SELECT SCREEN =====
    def _handle_profile_input(self, event):
        """Handle keyboard input on the profile select screen."""
        if self.profile_naming:
            # Typing a name for new profile
            if event.key == pygame.K_RETURN and len(self.profile_name_buf.strip()) > 0:
                # Move to animal selection step
                self.profile_naming = False
                self.profile_animal_step = True
                self.profile_animal_idx = 0
            elif event.key == pygame.K_BACKSPACE:
                self.profile_name_buf = self.profile_name_buf[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(self.profile_name_buf) < 16:
                    self.profile_name_buf += ch
            return

        if self.profile_animal_step:
            # Choosing animal base for new profile
            if event.key in (pygame.K_LEFT,):
                self.profile_animal_idx = (self.profile_animal_idx - 1) % len(self.CHARACTERS)
            elif event.key in (pygame.K_RIGHT,):
                self.profile_animal_idx = (self.profile_animal_idx + 1) % len(self.CHARACTERS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                animal = self.CHARACTERS[self.profile_animal_idx]["animal"]
                name = self.profile_name_buf.strip()
                self.profile = save_system.new_profile(name, animal)
                save_system.save_profile(self.profile)
                self.profile_palette_name = "default"
                self.profile_animal_step = False
                self.profile_name_buf = ""
                self.profile_list = save_system.list_profiles()
                self.state = "MAIN_MENU"
                self.menu_selection = 0
            return

        # Normal profile list navigation
        total = len(self.profile_list) + 1  # +1 for NEW PROFILE
        if event.key == pygame.K_UP:
            self.profile_cursor = (self.profile_cursor - 1) % total
        elif event.key == pygame.K_DOWN:
            self.profile_cursor = (self.profile_cursor + 1) % total
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.profile_cursor < len(self.profile_list):
                # Select existing profile
                self.profile = self.profile_list[self.profile_cursor]
                self.profile_palette_name = self.profile.get("color_palette", "default")
                self.state = "MAIN_MENU"
                self.menu_selection = 0
            else:
                # New profile — start naming
                self.profile_naming = True
                self.profile_name_buf = ""

    def _draw_profile_select(self):
        """Draw the profile selection / creation screen."""
        self.screen.fill(C_BG)

        # Animated skyline
        draw_skyline(self.screen, self.skyline, int(time.time() * 15), HEIGHT - 170)
        pygame.draw.line(self.screen, C_GROUND_TOP, (0, HEIGHT - 170), (WIDTH, HEIGHT - 170), 2)

        # Overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 8, 24, 120))
        self.screen.blit(overlay, (0, 0))

        cx = WIDTH // 2

        # Title
        pulse = 0.7 + 0.3 * math.sin(time.time() * 2)
        title = self.font_huge.render("MOONWOLF LAYERS", True,
                                       (int(C_NEON_CYAN[0]*pulse), int(C_NEON_CYAN[1]*pulse), int(C_NEON_CYAN[2]*pulse)))
        self.screen.blit(title, (cx - title.get_width()//2, 30))

        sub = self.font_big.render("SELECT PROFILE", True, C_HUD)
        self.screen.blit(sub, (cx - sub.get_width()//2, 90))

        if self.profile_naming:
            # Name entry screen
            prompt = self.font_big.render("Enter your name:", True, C_NEON_CYAN)
            self.screen.blit(prompt, (cx - prompt.get_width()//2, 180))
            # Blinking cursor
            cursor_ch = "_" if int(time.time() * 3) % 2 == 0 else " "
            name_text = self.profile_name_buf + cursor_ch
            name_surf = self.font_title.render(name_text, True, C_STAR_GOLD)
            self.screen.blit(name_surf, (cx - name_surf.get_width()//2, 230))
            hint = self.font.render("Type a name (max 16 chars) then press ENTER", True, C_HUD_DIM)
            self.screen.blit(hint, (cx - hint.get_width()//2, 300))
            return

        if self.profile_animal_step:
            # Animal selection screen
            prompt = self.font_big.render(f"Choose your animal, {self.profile_name_buf}!", True, C_NEON_CYAN)
            self.screen.blit(prompt, (cx - prompt.get_width()//2, 150))
            ch = self.CHARACTERS[self.profile_animal_idx]
            preview = make_sprite(ch["sprite"], ch["palette"], 6)
            self.screen.blit(preview, (cx - preview.get_width()//2, 200))
            name_s = self.font_title.render(f"< {ch['name']} >", True, ch['color'])
            self.screen.blit(name_s, (cx - name_s.get_width()//2, 420))
            ability_s = self.font_menu.render(ch['ability'], True, C_HUD_DIM)
            self.screen.blit(ability_s, (cx - ability_s.get_width()//2, 465))
            hint = self.font.render("LEFT/RIGHT to browse, ENTER to confirm", True, C_HUD_DIM)
            self.screen.blit(hint, (cx - hint.get_width()//2, 500))
            return

        # Profile list
        list_x = cx - 200
        list_y_start = 130
        item_h = 50
        total = len(self.profile_list) + 1

        for i in range(total):
            y = list_y_start + i * item_h
            if y > HEIGHT - 100:
                break  # Don't draw off screen
            selected = (i == self.profile_cursor)
            if selected:
                sel_bar = pygame.Surface((400, item_h - 4), pygame.SRCALPHA)
                sel_bar.fill((*C_NEON_CYAN, 25))
                self.screen.blit(sel_bar, (list_x, y))
                arrow = self.font_big.render(">", True, C_NEON_CYAN)
                self.screen.blit(arrow, (list_x - 25, y + 8))

            if i < len(self.profile_list):
                p = self.profile_list[i]
                name_color = C_NEON_CYAN if selected else C_HUD
                name_s = self.font_big.render(p["name"], True, name_color)
                self.screen.blit(name_s, (list_x + 10, y + 2))
                level, xp_into, xp_needed = save_system.xp_progress(p.get("xp", 0))
                detail = f"Lv.{level} | {p.get('animal_base', 'wolf')} | XP: {p.get('xp', 0)}"
                detail_s = self.font.render(detail, True, (120, 120, 140))
                self.screen.blit(detail_s, (list_x + 10, y + 28))
                # Mini XP bar
                bar_w, bar_h = 100, 4
                bar_x = list_x + 300
                bar_y_pos = y + 14
                pygame.draw.rect(self.screen, (30, 25, 50), (bar_x, bar_y_pos, bar_w, bar_h))
                fill = int(bar_w * xp_into / max(1, xp_needed))
                pygame.draw.rect(self.screen, C_NEON_CYAN, (bar_x, bar_y_pos, fill, bar_h))
            else:
                # NEW PROFILE option
                new_color = C_NEON_GREEN if selected else C_HUD_DIM
                new_s = self.font_big.render("+ NEW PROFILE", True, new_color)
                self.screen.blit(new_s, (list_x + 10, y + 8))

        hint = self.font.render("UP/DOWN to select, ENTER to confirm, ESC to quit", True, C_HUD_DIM)
        self.screen.blit(hint, (cx - hint.get_width()//2, HEIGHT - 40))

    def _cleanup(self):
        # Stop Ableton via OSC
        if self.ableton_recording:
            self.osc.stop_record()
        self.osc.stop()
        self.osc.close()
        if self.midi_port:
            for ch in range(16):
                self.midi_port.send(mido.Message('control_change', control=123, value=0, channel=ch))
            self.midi_port.close()
        pygame.quit()

# ======================== MAIN ========================
def main():
    bpm = 124
    key_name = "E"
    is_major = False
    port_name = "FE Bridge"
    midi_file = None

    demo_mode = False

    for i, arg in enumerate(sys.argv):
        if arg == "--bpm" and i + 1 < len(sys.argv): bpm = int(sys.argv[i + 1])
        elif arg == "--key" and i + 1 < len(sys.argv): key_name = sys.argv[i + 1]
        elif arg == "--major": is_major = True
        elif arg == "--port" and i + 1 < len(sys.argv): port_name = sys.argv[i + 1]
        elif arg == "--midi" and i + 1 < len(sys.argv): midi_file = sys.argv[i + 1]
        elif arg == "--demo": demo_mode = True

    print()
    print("=" * 50)
    if demo_mode:
        print("  MOONWOLF LAYERS v2.0 — DEMO MODE")
        print("  Bot plays optimally. Watch and learn!")
    else:
        print("  MOONWOLF LAYERS v2.0")
        print("  Layer loops. Build songs. Star Power riffs.")
    print("=" * 50)

    game = MoonwolfLayers(bpm, key_name, is_major, port_name, midi_file, demo_mode=demo_mode)
    game.run()

if __name__ == "__main__":
    main()
