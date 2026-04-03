"""
Moonwolf Layers v3.0 — Clean Modular Entry Point

Layer Builder Mode: Instead of fixed DRUMS->MELODY ordering, the player
picks which instrument layer to record next from the song's available tracks.
Completed layers loop in Ableton while the player stacks new ones on top.

Usage:
    python main.py --port "FE Bridge"
    python main.py --port "FE Bridge" --demo
    python main.py --bpm 124 --key E --port "FE Bridge"
"""

import sys
import os
import math
import time
import random
import threading

import pygame
import mido

# Ensure project root is on the path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Extracted modules ---
from src.data.constants import (
    WIDTH, HEIGHT, FPS, TILE,
    C_BG, C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW,
    C_STAR_GOLD, C_ENEMY, C_HUD, C_HUD_DIM,
    C_GROUND_TOP, C_LANE_BG, C_LANE_LINE,
    HIT_PERFECT, HIT_GREAT, HIT_GOOD, HIT_MISS,
    MULT_THRESHOLDS, GRADES,
    STAR_POWER_THRESHOLD, STAR_POWER_BARS,
    KICK, SNARE, HAT, OHAT, CRASH, RIDE, LTOM, HTOM,
    DRUM_CH, FE_DRUM_MAP,
    ROOT_MIDI, MAJOR_INT, MINOR_INT,
    TRANSPORT_CC_PLAY, TRANSPORT_CC_STOP, TRANSPORT_CC_RECORD,
)
from src.data.characters import CHARACTERS
from src.data.instruments import INSTRUMENT_ROLES
from src.rendering.sprites import make_sprite
from src.rendering.particles import ParticleSystem, PopupSystem
from src.rendering.skyline import generate_skyline, draw_skyline
from src.input.controller import scan_controllers, FightingEdgeReader
from src.input.midi_output import MidiOutput, scan_midi_ports
from src.gameplay.level import Level, load_levels_from_midi, generate_default_levels
from src.gameplay.ship import Ship
from src.gameplay.scoring import ScoreSystem
from src.gameplay.bot import DemoBot

from src.states.profile_select import ProfileSelectState
from src.states.main_menu import MainMenuState
from src.states.level_intro import LevelIntroState
from src.states.playing import PlayingState
from src.states.level_complete import LevelCompleteState

from song_library import get_song_list, load_song
import save_system


# ======================================================================
# Game class — shared state + state machine
# ======================================================================

class Game:
    """Central game object that owns all shared state and the state machine.

    The state classes access everything they need through ``self.game``.
    """

    # Class-level references so state code can do ``game.CHARACTERS``
    CHARACTERS = CHARACTERS
    INSTRUMENT_ROLES = INSTRUMENT_ROLES

    def __init__(self, bpm=124, key_name="E", is_major=False,
                 port_name="FE Bridge", midi_file=None, demo_mode=False):
        # ---- Pygame init ----
        pygame.init()
        pygame.joystick.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Moonwolf Layers v3")
        self.clock = pygame.time.Clock()

        # ---- Fonts ----
        self.font      = pygame.font.SysFont("consolas", 14)
        self.font_big  = pygame.font.SysFont("consolas", 22)
        self.font_title = pygame.font.SysFont("consolas", 36)
        self.font_huge = pygame.font.SysFont("consolas", 52)
        self.font_menu = pygame.font.SysFont("consolas", 18)

        # ---- Config ----
        self.bpm = bpm
        self.key_name = key_name
        self.is_major = is_major
        self.port_name = port_name
        self.midi_file = midi_file
        self.demo_mode = demo_mode

        # ---- Music scale for star power riffing ----
        root = ROOT_MIDI.get(key_name, 57)
        intervals = MAJOR_INT if is_major else MINOR_INT
        self.scale = [root + iv for iv in intervals]

        # ---- Character sprites ----
        self.p1_sprite = make_sprite(CHARACTERS[0]["sprite"], CHARACTERS[0]["palette"], 3)
        self.p2_sprite = make_sprite(CHARACTERS[1]["sprite"], CHARACTERS[1]["palette"], 3)

        # ---- Background visuals ----
        self.stars = [
            (random.randint(0, WIDTH * 4), random.randint(0, HEIGHT // 3), random.uniform(0.2, 1.0))
            for _ in range(150)
        ]
        self.skyline = generate_skyline(200)

        # ---- Particle and popup systems ----
        self.particles = ParticleSystem()
        self.popups = PopupSystem(self.font_big)

        # ---- Screen shake ----
        self.shake_x = 0.0
        self.shake_y = 0.0
        self.shake_intensity = 0.0

        # ---- MIDI output ----
        self.midi_out = MidiOutput()
        self.midi_port = None  # Legacy alias — states reference this
        self.pending_offs = []

        # ---- Controller state ----
        self.joystick = None
        self.joystick_connected = False
        self.fe_connected = False
        self.fe_buttons = [False] * 8
        self.fe_hat = -1

        # ---- Menu state ----
        self.menu_selection = 0
        self.menu_player_mode = 1       # 0 = 1P Solo, 1 = 2P Co-op
        self.menu_midi_idx = 0
        self.p1_char_idx = 0
        self.p2_char_idx = 1
        self.p1_role_idx = 0
        self.p2_role_idx = 1
        self.song_list = get_song_list()
        self.song_idx = 0
        self.song_scroll_offset = 0
        self.available_midi = self._scan_midi_ports()
        self.detected_controllers = self._scan_controllers()

        # Pre-select MIDI port matching the CLI arg
        for i, p in enumerate(self.available_midi):
            if port_name.lower() in p.lower():
                self.menu_midi_idx = i
                break

        # ---- Profile state ----
        self.profile = None
        self.profile_list = save_system.list_profiles()
        self.profile_cursor = 0
        self.profile_naming = False
        self.profile_name_buf = ""
        self.profile_animal_idx = 0
        self.profile_animal_step = False
        self.profile_palette_name = "default"

        # ---- XP tracking per level ----
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.xp_result = None

        # ---- Timing / beat ----
        self.state_timer = 0
        self.beat_timer = 0
        self.beat_flash = 0
        self.beat_interval = 60.0 / self.bpm

        # ---- Transport ----
        self.ableton_recording = False

        # ---- Gameplay ----
        self.levels = None
        self.level = None
        self.current_level = 0
        self.p1_y = HEIGHT // 2
        self.p1_vy = 0.0
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
        self.combo_pulse = 0.0

        # ---- Layer Builder Mode ----
        self.available_layers = []    # Instrument tracks from the song
        self.completed_layers = []    # Layers already recorded and looping
        self.active_layer = None      # Currently playing layer name

        # ---- Demo mode ----
        self.demo_auto_advance_timer = 0.0

        # ---- MIDI channel per player (set when game starts) ----
        self.p1_midi_ch = 0
        self.p2_midi_ch = 1

        # ---- State machine ----
        self.state = "PROFILE_SELECT"
        self._states = {
            "PROFILE_SELECT": ProfileSelectState(self),
            "MAIN_MENU":      MainMenuState(self),
            "LEVEL_INTRO":    LevelIntroState(self),
            "PLAYING":        PlayingState(self),
            "LEVEL_COMPLETE": LevelCompleteState(self),
        }
        self._current_state = self._states[self.state]
        self._current_state.enter()

    # ==================================================================
    # Scanner helpers (used by menu state)
    # ==================================================================

    def _scan_midi_ports(self):
        return scan_midi_ports()

    def _scan_controllers(self):
        controllers, self.fe_connected, self.joystick_connected = scan_controllers()
        return controllers

    # ==================================================================
    # MIDI helpers (used by playing/level states)
    # ==================================================================

    def _open_midi(self, port_name):
        self.midi_out.open(port_name)
        # Legacy alias so state code that checks ``game.midi_port`` still works
        self.midi_port = self.midi_out._port

    def note_on(self, note, vel, ch=0):
        self.midi_out.note_on(note, vel, ch)

    def note_off(self, note, ch=0):
        self.midi_out.note_off(note, ch)

    def _send_transport(self, cc, val=127):
        self.midi_out.send_transport(cc, val)

    # ==================================================================
    # Fighting Edge HID
    # ==================================================================

    def _start_fe_reader(self):
        reader = FightingEdgeReader(
            on_button_press=self._on_fe_button,
            on_button_release=self._on_fe_button_release,
        )
        reader.start()

    # ==================================================================
    # Scoring helpers (called from states)
    # ==================================================================

    def _get_multiplier(self):
        divisor = 2 if self.fury else 1
        for threshold, mult in MULT_THRESHOLDS:
            if self.combo >= threshold // divisor:
                return mult
        return 1

    def _get_grade(self, pct):
        for threshold, letter, color in GRADES:
            if pct >= threshold:
                return letter, color
        return "F", C_ENEMY

    def _score_multiplier(self, base_score, mult):
        score = base_score * mult
        if self.frenzy:
            tier = 0
            for threshold, m in MULT_THRESHOLDS:
                if self.combo >= threshold:
                    tier = m
                    break
            score = int(score * (1.0 + tier * 0.1))
        return int(score)

    def _shake(self, intensity):
        self.shake_intensity = max(self.shake_intensity, intensity)

    def _try_break_combo(self, popup_x, popup_y):
        if self.combo <= 0:
            return True
        if self.venom and self.venom_timer > 0:
            self.popups.add(popup_x, popup_y, "VENOM!", (80, 200, 50))
            return False
        if self.shell and self.shell_hits < 5:
            self.shell_hits += 1
            self.popups.add(popup_x, popup_y, f"SHELL! ({5 - self.shell_hits})", (80, 180, 80))
            return False
        if self.combo_shield and self.combo_shield_count < self.combo_shield_max:
            self.combo_shield_count += 1
            remaining = self.combo_shield_max - self.combo_shield_count
            self.popups.add(popup_x, popup_y, f"SHIELD! ({remaining})", C_NEON_GREEN)
            return False
        self.combo = 0
        return True

    def _on_hit(self):
        if self.venom:
            self.venom_timer = 3.0

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
        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))

    # ==================================================================
    # Fighting Edge button callbacks
    # ==================================================================

    def _on_fe_button(self, btn_idx):
        if self.state not in ("PLAYING", "STAR_POWER"):
            return

        drum = FE_DRUM_MAP.get(btn_idx)
        if not drum:
            return
        note, name, color = drum

        self.p2_lane_flash[btn_idx] = 1.0

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

        self.max_combo = max(self.max_combo, self.combo)

        if not hit_something:
            if self._try_break_combo(200, lane_area_top - 20):
                self.popups.add(200, lane_area_top - 20, "Miss", C_ENEMY)

        self.note_on(note, 100, DRUM_CH)
        self.pending_offs.append((note, DRUM_CH, time.time() + 0.15))

        if self.combo >= STAR_POWER_THRESHOLD and not self.star_power:
            self.star_power = True
            sp_bars = STAR_POWER_BARS * (2 if self.rage else 1)
            self.star_power_timer = (60.0 / self.bpm) * 4 * sp_bars
            self.star_power_activations += 1
            self._shake(10)
            self.particles.emit(200, HEIGHT // 2, 30, C_STAR_GOLD, 300, 1.0, 5)
            self.popups.add(WIDTH // 2, HEIGHT // 2 - 60, "STAR POWER!", C_STAR_GOLD)
            print(f"  STAR POWER ACTIVATED! ({STAR_POWER_BARS} bars of free riff)")

    def _on_fe_button_release(self, btn_idx):
        pass

    # ==================================================================
    # Game lifecycle methods (called from states)
    # ==================================================================

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
            song_data = load_song(song_folder)
            full_mid_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "songs", song_folder, "full.mid"
            )
            if os.path.exists(full_mid_path):
                self.bpm = song_info.get("bpm", self.bpm) or self.bpm
                self.levels, self.bpm = load_levels_from_midi(full_mid_path, self.bpm)
                print(f"  Song: {song_info['artist']} - {song_info['title']}")
            else:
                self.levels = generate_default_levels(self.bpm, self.key_name, self.is_major)

            # --- Layer Builder Mode: build available_layers from song tracks ---
            self.available_layers = list(song_data["tracks"].keys())
            self.completed_layers = []
            self.active_layer = None
        elif self.midi_file:
            self.levels, self.bpm = load_levels_from_midi(self.midi_file, self.bpm)
            self.available_layers = [lv.name.lower() for lv in self.levels]
            self.completed_layers = []
            self.active_layer = None
        else:
            self.levels = generate_default_levels(self.bpm, self.key_name, self.is_major)
            self.available_layers = [lv.name.lower() for lv in self.levels]
            self.completed_layers = []
            self.active_layer = None

        self.current_level = 0
        self.level = self.levels[0]
        self.scroll_speed = self.level.scroll_speed
        self.beat_interval = 60.0 / self.bpm

        # Reset scoring
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.locked_levels = 0
        self.star_meter = 0.0

        # Reset XP stat counters
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.xp_result = None

        # Apply character abilities
        p1_ch = CHARACTERS[self.p1_char_idx]
        p2_ch = CHARACTERS[self.p2_char_idx]
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
        self.combo_shield_used = False
        self.combo_shield_max = 3 if self.tank else 1
        self.combo_shield_count = 0
        self.venom_timer = 0.0
        self.shell_hits = 0

        self.state_timer = 0

        p1_role = INSTRUMENT_ROLES[self.p1_role_idx]
        p2_role = INSTRUMENT_ROLES[self.p2_role_idx]
        self.p1_midi_ch = p1_role['midi_ch']
        self.p2_midi_ch = p2_role['midi_ch']
        print(f"  Mode: {'2P Co-op' if self.menu_player_mode == 1 else '1P Solo'}")
        print(f"  P1: {p1_ch['name']} -- {p1_ch['ability']} -- Role: {p1_role['name']} (ch.{p1_role['midi_ch']})")
        print(f"  P2: {p2_ch['name']} -- {p2_ch['ability']} -- Role: {p2_role['name']} (ch.{p2_role['midi_ch']})")
        print(f"  Levels: {len(self.levels)}")
        for i, lv in enumerate(self.levels):
            tag = " <-- CURRENT" if i == 0 else ""
            print(f"    {i+1}. {lv.name} ({lv.bars} bars, {lv.instrument_name}){tag}")
        if self.available_layers:
            print(f"  Available layers: {', '.join(self.available_layers)}")

    def _start_level(self):
        self.camera_x = -100
        self.combo = 0
        self.hits = 0
        self.total_targets = len(self.level.pickups) + len(self.level.drum_lanes)
        self.level.reset()

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.combo_10s = 0
        self.star_power_activations = 0
        self.xp_result = None

        self.combo_shield_used = False
        self.p1_y = HEIGHT // 2
        self.p1_vy = 0.0

        # Mark the active layer
        if self.level.name.lower() not in self.completed_layers:
            self.active_layer = self.level.name.lower()

        # Tell Ableton to start recording
        self._send_transport(TRANSPORT_CC_PLAY)
        time.sleep(0.1)
        self._send_transport(TRANSPORT_CC_RECORD)
        self.ableton_recording = True
        print(f"  Level {self.current_level + 1}: {self.level.name} - GO! (Ableton: RECORD)")

    def _next_level(self):
        # Stop Ableton recording
        self._send_transport(TRANSPORT_CC_RECORD)
        self.ableton_recording = False
        self.locked_levels += 1

        # Mark layer as completed
        layer_name = self.level.name.lower()
        if layer_name not in self.completed_layers:
            self.completed_layers.append(layer_name)
        self.active_layer = None

        print(f"  Level {self.current_level + 1} locked in Ableton! ({self.level.name})")
        print(f"  Completed layers: {', '.join(self.completed_layers)}")
        remaining = [l for l in self.available_layers if l not in self.completed_layers]
        if remaining:
            print(f"  Remaining layers: {', '.join(remaining)}")
        else:
            print(f"  All layers complete!")

        # Move to next level
        self.current_level += 1
        if self.current_level >= len(self.levels):
            self.current_level = 0
            print("  All levels complete! Looping from start with all layers.")

        self.level = self.levels[self.current_level]
        self.scroll_speed = self.level.scroll_speed
        self.state_timer = 0
        self.star_power = False
        self.star_meter = 0

    def _restart_level(self):
        if self.ableton_recording:
            self._send_transport(TRANSPORT_CC_STOP)
            self.ableton_recording = False
        self.camera_x = -100
        self.combo = 0
        self.hits = 0
        self.star_power = False
        self.star_meter = 0
        self.level.reset()

    def _adjust_bpm(self, delta):
        self.bpm = max(60, min(200, self.bpm + delta))
        self.beat_interval = 60.0 / self.bpm
        self.scroll_speed = (self.bpm * 4 / 60.0) * (TILE * 2)
        self.level.scroll_speed = self.scroll_speed
        print(f"  BPM: {self.bpm}")

    # ==================================================================
    # State machine
    # ==================================================================

    def set_state(self, name):
        """Transition to a new state by name."""
        if name == self.state:
            return
        self._current_state.exit()
        self.state = name
        self._current_state = self._states[name]
        self._current_state.enter()

    # ==================================================================
    # Main loop
    # ==================================================================

    def run(self):
        running = True

        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    continue

                next_state = self._current_state.handle_event(event)
                if next_state == "QUIT":
                    running = False
                elif next_state:
                    self.set_state(next_state)

            # Demo mode auto-advance through menus
            if self.demo_mode:
                self.demo_auto_advance_timer += dt
                if self.state == "PROFILE_SELECT" and self.demo_auto_advance_timer > 0.5:
                    self.profile = save_system.new_profile("DemoBot", "wolf")
                    self.set_state("MAIN_MENU")
                    self.demo_auto_advance_timer = 0
                elif self.state == "MAIN_MENU" and self.demo_auto_advance_timer > 1.0:
                    if self.song_list:
                        self.song_idx = random.randint(0, len(self.song_list) - 1)
                    self._init_game()
                    self.set_state("LEVEL_INTRO")
                    self.demo_auto_advance_timer = 0
                elif self.state == "LEVEL_INTRO" and self.demo_auto_advance_timer > 2.0:
                    self._start_level()
                    self.set_state("PLAYING")
                    self.demo_auto_advance_timer = 0
                elif self.state == "LEVEL_COMPLETE" and self.demo_auto_advance_timer > 3.0:
                    self._next_level()
                    self.set_state("LEVEL_INTRO")
                    self.demo_auto_advance_timer = 0

            next_state = self._current_state.update(dt)
            if next_state == "QUIT":
                running = False
            elif next_state:
                self.set_state(next_state)

            self._current_state.draw(self.screen)

            # Demo mode overlay
            if self.demo_mode and self.state in ("PLAYING", "STAR_POWER"):
                pct = (self.hits / max(1, self.total_targets)) * 100 if self.total_targets > 0 else 0
                acc_color = C_STAR_GOLD if pct >= 95 else C_NEON_GREEN if pct >= 80 else C_NEON_CYAN
                demo_line1 = self.font_big.render("DEMO MODE", True, C_STAR_GOLD)
                demo_line2 = self.font.render(
                    f"Accuracy: {pct:.0f}% | Combo: {self.combo} | Hits: {self.hits}/{self.total_targets} | "
                    f"P:{self.perfects} G:{self.greats} OK:{self.goods}",
                    True, acc_color,
                )
                self.screen.blit(demo_line1, (WIDTH // 2 - demo_line1.get_width() // 2, HEIGHT - 42))
                self.screen.blit(demo_line2, (WIDTH // 2 - demo_line2.get_width() // 2, HEIGHT - 22))

            pygame.display.flip()

        self._cleanup()

    def _cleanup(self):
        if self.ableton_recording:
            self._send_transport(TRANSPORT_CC_STOP)
        self.midi_out.all_notes_off()
        pygame.quit()


# ======================================================================
# CLI entry point
# ======================================================================

def main():
    bpm = 124
    key_name = "E"
    is_major = False
    port_name = "FE Bridge"
    midi_file = None
    demo_mode = False

    for i, arg in enumerate(sys.argv):
        if arg == "--bpm" and i + 1 < len(sys.argv):
            bpm = int(sys.argv[i + 1])
        elif arg == "--key" and i + 1 < len(sys.argv):
            key_name = sys.argv[i + 1]
        elif arg == "--major":
            is_major = True
        elif arg == "--port" and i + 1 < len(sys.argv):
            port_name = sys.argv[i + 1]
        elif arg == "--midi" and i + 1 < len(sys.argv):
            midi_file = sys.argv[i + 1]
        elif arg == "--demo":
            demo_mode = True

    print()
    print("=" * 50)
    if demo_mode:
        print("  MOONWOLF LAYERS v3.0 -- DEMO MODE")
        print("  Bot plays optimally. Watch and learn!")
    else:
        print("  MOONWOLF LAYERS v3.0")
        print("  Layer Builder Mode: Pick layers. Build songs.")
    print("=" * 50)

    game = Game(bpm, key_name, is_major, port_name, midi_file, demo_mode=demo_mode)
    game.run()


if __name__ == "__main__":
    main()
