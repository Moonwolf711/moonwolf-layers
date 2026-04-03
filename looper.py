"""
Moonwolf Looper — Visual MIDI loop builder for Ableton Live.

NOT a game. A performance tool.
Shows you what to play. You play it. Ableton records it.
Loop it. Next layer. Build the song.

All sound comes from Ableton — synths, drum racks, whatever you loaded.
This just sends MIDI and shows you the pattern.

Usage:
    python looper.py --port "FE Bridge"
"""

import sys
import os
import math
import time
import random
import threading
import pygame
import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from song_library import get_song_list, load_song

# ======================== CONFIG ========================
WIDTH, HEIGHT = 1280, 720
FPS = 60

# Colors
BG          = (12, 12, 28)
DARK        = (20, 18, 35)
GRID_LINE   = (30, 28, 50)
GRID_BEAT   = (50, 45, 80)
GRID_BAR    = (80, 70, 120)
TEXT         = (180, 180, 200)
TEXT_DIM     = (80, 80, 100)
CYAN         = (0, 255, 255)
PINK         = (255, 0, 200)
GREEN        = (0, 255, 100)
GOLD         = (255, 215, 0)
RED          = (255, 60, 60)
WHITE        = (255, 255, 255)

# Drum GM mapping
DRUM_NAMES = {36: "KICK", 38: "SNARE", 42: "HH", 46: "OH", 49: "CRASH", 51: "RIDE", 45: "LTOM", 48: "HTOM"}
DRUM_COLORS = {36: (255,80,50), 38: (255,220,50), 42: (50,255,150), 46: (50,200,255),
               49: (255,100,255), 51: (150,150,255), 45: (255,150,50), 48: (200,80,200)}

# FE button → drum note
FE_DRUM = {0: 36, 1: 38, 2: 42, 3: 46, 4: 49, 5: 51, 6: 45, 7: 48}

# Transport CCs (MIDI learn these in Ableton)
CC_PLAY = 119
CC_STOP = 118
CC_RECORD = 117

LOOP_BARS = 8


class Layer:
    """One instrument layer with its MIDI note pattern."""
    def __init__(self, name, notes, channel, bpm):
        self.name = name          # "drums", "bass", "guitar", etc.
        self.channel = channel
        self.bpm = bpm
        self.notes = notes        # [(time_sec, note, velocity, duration_sec), ...]  — reference pattern
        self.recorded = []        # [(time_sec, note, velocity, duration_sec), ...]  — what player actually played
        self.loop_duration = (60.0 / bpm) * 4 * LOOP_BARS  # 8 bars in seconds
        self.state = "waiting"    # waiting, recording, looping, skipped


def extract_layers(song_folder):
    """Load a song and extract per-instrument layers as 8-bar loops."""
    song_data = load_song(song_folder)
    meta = song_data["meta"]
    bpm = meta.get("bpm", 120)
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4
    loop_dur = bar_dur * LOOP_BARS

    layers = []
    for inst_name, mid in song_data["tracks"].items():
        # Extract note events with durations
        notes = []
        active = {}  # (ch, note) -> (start_time, vel)
        abs_time = 0.0

        for track in mid.tracks:
            abs_time = 0.0
            for msg in track:
                abs_time += mido.tick2second(msg.time, mid.ticks_per_beat, mido.bpm2tempo(bpm))
                if msg.type == 'note_on' and msg.velocity > 0:
                    active[(msg.channel, msg.note)] = (abs_time, msg.velocity)
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    key = (msg.channel, msg.note)
                    if key in active:
                        start, vel = active.pop(key)
                        # Wrap to 8-bar loop
                        t = start % loop_dur
                        dur = min(abs_time - start, 2.0)  # Cap duration
                        notes.append((t, msg.note, vel, dur))

        if not notes:
            continue

        notes.sort(key=lambda n: n[0])

        # Channel mapping by instrument name
        ch_map = {"drums": 9, "bass": 2, "guitar": 1, "keys": 0, "strings": 4, "horns": 3, "synth": 6, "vocals": 5}
        ch = ch_map.get(inst_name, 0)

        layers.append(Layer(inst_name, notes, ch, bpm))

    return layers, bpm


class Looper:
    def __init__(self, port_name="FE Bridge"):
        pygame.init()
        pygame.joystick.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Moonwolf Looper")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 14)
        self.font_med = pygame.font.SysFont("consolas", 18)
        self.font_big = pygame.font.SysFont("consolas", 28)
        self.font_title = pygame.font.SysFont("consolas", 40)

        # MIDI
        self.midi_port = None
        self.port_name = port_name
        self._open_midi(port_name)
        self.pending_offs = []

        # Songs
        self.song_list = get_song_list()
        self.song_idx = 0

        # State
        self.state = "SONG_SELECT"  # SONG_SELECT, LAYER_SELECT, PLAYING, REVIEW
        self.layers = []
        self.bpm = 120
        self.current_layer_idx = 0
        self.playhead = 0.0  # seconds into the loop
        self.loop_count = 0
        self.beat_flash = 0.0

        # Recording
        self.played_notes = []  # Notes the player actually hit this pass

        # Controllers
        self.joystick = None
        self.fe_buttons = [False] * 8
        self._init_controllers()
        self._start_fe_reader()

    def _open_midi(self, port_name):
        try:
            if self.midi_port:
                self.midi_port.close()
                self.midi_port = None
            available = mido.get_output_names()
            matches = [n for n in available if port_name.lower() in n.lower()]
            if matches:
                self.midi_port = mido.open_output(matches[0])
                print(f"  MIDI output: {matches[0]}")
            elif available:
                self.midi_port = mido.open_output(available[0])
                print(f"  MIDI output (fallback): {available[0]}")
        except Exception as e:
            print(f"  MIDI error: {e}")

    def _init_controllers(self):
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            if 't.16000m' in js.get_name().lower() or 'thrustmaster' in js.get_name().lower():
                self.joystick = js
                print(f"  Joystick: {js.get_name()}")
                break

    def _start_fe_reader(self):
        def reader():
            try:
                import hid as hidlib
                devs = hidlib.enumerate(0x0F0D, 0x0037)
                if not devs:
                    print("  Fighting Edge: not found")
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
                    for bit in range(8):
                        cur = (data[0] >> bit) & 1
                        old = (prev[0] >> bit) & 1 if prev else 0
                        if cur and not old:
                            self._on_button(bit)
                    prev = list(data)
            except Exception as e:
                print(f"  FE reader error: {e}")
        threading.Thread(target=reader, daemon=True).start()

    def _on_button(self, idx):
        """Button pressed — send MIDI + record into layer."""
        if self.state != "PLAYING":
            return
        layer = self.layers[self.current_layer_idx]
        note = FE_DRUM.get(idx, 36)
        self._send_note(note, 100, layer.channel, 0.15)
        # Record into layer for live looping
        layer.recorded.append((self.playhead, note, 100, 0.15))
        self.played_notes.append((self.playhead, note, 100))

    def _send_note(self, note, vel, ch, dur=0.2):
        if self.midi_port:
            self.midi_port.send(mido.Message('note_on', note=note, velocity=vel, channel=ch))
            self.pending_offs.append((note, ch, time.time() + dur))

    def _send_transport(self, cc):
        if self.midi_port:
            self.midi_port.send(mido.Message('control_change', control=cc, value=127, channel=15))
            time.sleep(0.05)
            self.midi_port.send(mido.Message('control_change', control=cc, value=0, channel=15))

    def _tick_note_offs(self):
        now = time.time()
        still = []
        for note, ch, off_time in self.pending_offs:
            if now >= off_time:
                if self.midi_port:
                    self.midi_port.send(mido.Message('note_off', note=note, velocity=0, channel=ch))
            else:
                still.append((note, ch, off_time))
        self.pending_offs = still

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state == "SONG_SELECT":
                            running = False
                        elif self.state == "PLAYING":
                            # Stop recording, go to review
                            self._send_transport(CC_RECORD)
                            self.state = "REVIEW"
                        else:
                            self.state = "SONG_SELECT"

                    elif self.state == "SONG_SELECT":
                        if event.key == pygame.K_UP:
                            self.song_idx = (self.song_idx - 1) % max(1, len(self.song_list))
                        elif event.key == pygame.K_DOWN:
                            self.song_idx = (self.song_idx + 1) % max(1, len(self.song_list))
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self._load_song()

                    elif self.state == "LAYER_SELECT":
                        if event.key == pygame.K_UP:
                            self._move_layer_cursor(-1)
                        elif event.key == pygame.K_DOWN:
                            self._move_layer_cursor(1)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self._start_recording()
                        elif event.key == pygame.K_s:
                            # Skip this layer
                            self.layers[self.current_layer_idx].state = "skipped"
                            self._move_layer_cursor(1)

                    elif self.state == "REVIEW":
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            # Accept — lock this layer as looping
                            self.layers[self.current_layer_idx].state = "looping"
                            self._advance_to_next_layer()
                        elif event.key == pygame.K_r:
                            # Retry — record again
                            self._start_recording()
                        elif event.key == pygame.K_s:
                            # Skip
                            self.layers[self.current_layer_idx].state = "skipped"
                            self._advance_to_next_layer()

                    # Controls during PLAYING
                    elif self.state == "PLAYING":
                        if pygame.K_1 <= event.key <= pygame.K_8:
                            self._on_button(event.key - pygame.K_1)
                        elif event.key == pygame.K_RETURN:
                            # Accept this take — lock the layer as looping
                            layer = self.layers[self.current_layer_idx]
                            layer.state = "looping"
                            self._send_transport(CC_RECORD)
                            print(f"  Locked: {layer.name} ({len(layer.recorded)} notes looping)")
                            self._advance_to_next_layer()
                        elif event.key == pygame.K_r:
                            # Redo — clear and restart recording this layer
                            self.layers[self.current_layer_idx].recorded = []
                            self.played_notes = []
                            self.playhead = 0.0
                            self.loop_count = 0
                            print(f"  Redo: {self.layers[self.current_layer_idx].name}")
                        elif event.key == pygame.K_TAB:
                            # Quick-skip to next layer without recording
                            self.layers[self.current_layer_idx].state = "skipped"
                            self._advance_to_next_layer()

            self._tick_note_offs()
            self._update(dt)
            self._draw()
            pygame.display.flip()

        self._cleanup()

    def _load_song(self):
        if not self.song_list:
            return
        song = self.song_list[self.song_idx]
        self.layers, self.bpm = extract_layers(song["folder"])
        self.current_layer_idx = 0
        self.state = "LAYER_SELECT"
        print(f"\n  Loaded: {song['artist']} - {song['title']} ({self.bpm} BPM)")
        print(f"  Layers: {', '.join(l.name for l in self.layers)}")

    def _move_layer_cursor(self, direction):
        for _ in range(len(self.layers)):
            self.current_layer_idx = (self.current_layer_idx + direction) % len(self.layers)
            if self.layers[self.current_layer_idx].state == "waiting":
                return
        # All layers done
        self.state = "SONG_SELECT"

    def _start_recording(self):
        self.playhead = 0.0
        self.loop_count = 0
        self.played_notes = []
        layer = self.layers[self.current_layer_idx]
        layer.recorded = []  # Clear previous recording
        layer.state = "recording"
        self.state = "PLAYING"
        # Tell Ableton to record
        self._send_transport(CC_PLAY)
        time.sleep(0.1)
        self._send_transport(CC_RECORD)
        looping = [l.name for l in self.layers if l.state == "looping"]
        print(f"  Recording: {layer.name} (ch.{layer.channel}) — 8 bars at {self.bpm} BPM")
        if looping:
            print(f"  Looping: {', '.join(looping)}")

    def _advance_to_next_layer(self):
        # Find next waiting layer
        for i in range(len(self.layers)):
            idx = (self.current_layer_idx + 1 + i) % len(self.layers)
            if self.layers[idx].state == "waiting":
                self.current_layer_idx = idx
                self.state = "LAYER_SELECT"
                return
        # All done
        print("  All layers complete! Song built.")
        self.state = "SONG_SELECT"

    def _update(self, dt):
        # Beat flash
        self.beat_flash *= 0.85

        if self.state != "PLAYING":
            return

        layer = self.layers[self.current_layer_idx]
        old_playhead = self.playhead
        self.playhead += dt
        beat_dur = 60.0 / self.bpm
        loop_dur = layer.loop_duration

        # Beat tracking
        old_beat = int(old_playhead / beat_dur)
        new_beat = int(self.playhead / beat_dur)
        if new_beat > old_beat:
            self.beat_flash = 1.0

        # === LIVE LOOPER: play back all completed layers ===
        for l in self.layers:
            if l.state != "looping" or not l.recorded:
                continue
            for t, note, vel, dur in l.recorded:
                if old_playhead % loop_dur <= t < self.playhead % loop_dur:
                    self._send_note(note, vel, l.channel, dur)
                # Handle loop wrap-around
                elif old_playhead % loop_dur > self.playhead % loop_dur:
                    # We wrapped — check if note is in the wrap zone
                    if t >= old_playhead % loop_dur or t < self.playhead % loop_dur:
                        self._send_note(note, vel, l.channel, dur)

        # Guide track — quiet reference notes for the current recording layer
        if self.loop_count == 0:
            # First pass: play guide at low velocity so player hears what to play
            for t, note, vel, dur in layer.notes:
                if old_playhead <= t < self.playhead:
                    ref_vel = min(vel, 40)
                    self._send_note(note, ref_vel, layer.channel, dur)

        # Loop wrap
        if self.playhead >= loop_dur:
            self.playhead -= loop_dur
            self.loop_count += 1
            print(f"  Loop {self.loop_count} complete ({len(layer.recorded)} notes recorded)")
            # No auto-stop — keep looping until player presses ESC or ENTER

    def _draw(self):
        self.screen.fill(BG)

        if self.state == "SONG_SELECT":
            self._draw_song_select()
        elif self.state == "LAYER_SELECT":
            self._draw_layer_select()
        elif self.state == "PLAYING":
            self._draw_playing()
        elif self.state == "REVIEW":
            self._draw_review()

        pygame.display.flip()

    # ===== SONG SELECT =====
    def _draw_song_select(self):
        cx = WIDTH // 2

        title = self.font_title.render("MOONWOLF LOOPER", True, CYAN)
        self.screen.blit(title, (cx - title.get_width()//2, 30))

        sub = self.font_med.render("Pick a song. Build it live. 8 bars at a time.", True, TEXT_DIM)
        self.screen.blit(sub, (cx - sub.get_width()//2, 80))

        # Song list
        visible = 15
        start = max(0, self.song_idx - visible // 2)
        end = min(len(self.song_list), start + visible)

        for i in range(start, end):
            song = self.song_list[i]
            y = 120 + (i - start) * 36
            selected = (i == self.song_idx)

            if selected:
                pygame.draw.rect(self.screen, (25, 25, 50), (100, y - 2, WIDTH - 200, 32), border_radius=4)
                pygame.draw.rect(self.screen, CYAN, (100, y - 2, WIDTH - 200, 32), 1, border_radius=4)

            color = WHITE if selected else TEXT_DIM
            artist = self.font_med.render(f"{song['artist']}", True, PINK if selected else TEXT_DIM)
            title = self.font_med.render(f"{song['title']}", True, color)
            info = self.font.render(f"{song['bpm']} BPM  |  {song['key']}  |  {'*' * song['difficulty']}", True, TEXT_DIM)

            self.screen.blit(artist, (120, y))
            self.screen.blit(title, (340, y))
            self.screen.blit(info, (700, y + 4))

        # Footer
        footer = self.font.render("[UP/DOWN] Browse   [ENTER] Load   [ESC] Quit", True, TEXT_DIM)
        self.screen.blit(footer, (cx - footer.get_width()//2, HEIGHT - 30))

    # ===== LAYER SELECT =====
    def _draw_layer_select(self):
        cx = WIDTH // 2
        song = self.song_list[self.song_idx]

        # Song header
        header = self.font_big.render(f"{song['artist']} - {song['title']}", True, WHITE)
        self.screen.blit(header, (cx - header.get_width()//2, 30))

        bpm_text = self.font_med.render(f"{self.bpm} BPM  |  {LOOP_BARS} bar loop  |  {LOOP_BARS * 4} beats", True, TEXT_DIM)
        self.screen.blit(bpm_text, (cx - bpm_text.get_width()//2, 70))

        # Layer list
        self.screen.blit(self.font_med.render("LAYERS", True, CYAN), (80, 120))
        pygame.draw.line(self.screen, GRID_LINE, (80, 145), (WIDTH - 80, 145))

        for i, layer in enumerate(self.layers):
            y = 160 + i * 50
            selected = (i == self.current_layer_idx)

            # Status indicator
            if layer.state == "looping":
                status_color = GREEN
                status = "LOOPING"
                icon = ">>>"
            elif layer.state == "skipped":
                status_color = TEXT_DIM
                status = "SKIPPED"
                icon = "---"
            elif layer.state == "recording":
                status_color = RED
                status = "REC"
                icon = "REC"
            else:
                status_color = TEXT_DIM if not selected else CYAN
                status = "READY"
                icon = "..."

            if selected and layer.state == "waiting":
                pygame.draw.rect(self.screen, (20, 30, 50), (70, y - 4, WIDTH - 140, 44), border_radius=6)
                pygame.draw.rect(self.screen, CYAN, (70, y - 4, WIDTH - 140, 44), 1, border_radius=6)

            # Layer name
            name_color = WHITE if selected and layer.state == "waiting" else status_color
            name = self.font_big.render(layer.name.upper(), True, name_color)
            self.screen.blit(name, (100, y))

            # Note count + channel
            info = self.font.render(f"ch.{layer.channel + 1}  |  {len(layer.notes)} notes  |  {status}", True, status_color)
            self.screen.blit(info, (350, y + 8))

            # Status icon
            icon_surf = self.font_med.render(icon, True, status_color)
            self.screen.blit(icon_surf, (WIDTH - 160, y + 4))

        # Footer
        footer = self.font.render("[ENTER] Record   [S] Skip   [ESC] Back to songs", True, TEXT_DIM)
        self.screen.blit(footer, (cx - footer.get_width()//2, HEIGHT - 30))

    # ===== PLAYING (8-bar loop view) =====
    def _draw_playing(self):
        layer = self.layers[self.current_layer_idx]
        beat_dur = 60.0 / self.bpm
        total_beats = LOOP_BARS * 4
        loop_dur = layer.loop_duration

        # Header
        song = self.song_list[self.song_idx]
        header = self.font_med.render(
            f"{song['artist']} - {song['title']}  |  {layer.name.upper()}  |  "
            f"Loop {self.loop_count + 1}/2  |  {self.bpm} BPM",
            True, WHITE)
        self.screen.blit(header, (20, 10))

        # REC indicator
        pulse = 0.5 + 0.5 * math.sin(time.time() * 6)
        rec = self.font_big.render("REC", True, (int(255 * pulse), 0, 0))
        self.screen.blit(rec, (WIDTH - 100, 8))

        # ===== NOTE GRID =====
        grid_top = 50
        grid_bottom = HEIGHT - 60
        grid_left = 60
        grid_right = WIDTH - 20
        grid_w = grid_right - grid_left
        grid_h = grid_bottom - grid_top

        # Background
        pygame.draw.rect(self.screen, DARK, (grid_left, grid_top, grid_w, grid_h))

        # Playhead position (fraction through loop)
        frac = self.playhead / loop_dur

        if layer.name == "drums":
            self._draw_drum_grid(layer, grid_left, grid_top, grid_w, grid_h, frac, total_beats, beat_dur, loop_dur)
        else:
            self._draw_melody_grid(layer, grid_left, grid_top, grid_w, grid_h, frac, total_beats, beat_dur, loop_dur)

        # Playhead line
        px = grid_left + int(frac * grid_w)
        pygame.draw.line(self.screen, WHITE, (px, grid_top), (px, grid_bottom), 2)

        # Beat flash
        if self.beat_flash > 0.1:
            flash = pygame.Surface((grid_w, 3), pygame.SRCALPHA)
            flash.fill((*CYAN, int(self.beat_flash * 120)))
            self.screen.blit(flash, (grid_left, grid_bottom))

        # Beat counter
        current_beat = int(self.playhead / beat_dur) + 1
        current_bar = (current_beat - 1) // 4 + 1
        beat_in_bar = (current_beat - 1) % 4 + 1
        counter = self.font_big.render(f"Bar {current_bar} . {beat_in_bar}", True, CYAN)
        self.screen.blit(counter, (WIDTH // 2 - counter.get_width()//2, HEIGHT - 50))

        # Footer
        # Looping layers indicator
        looping = [l for l in self.layers if l.state == "looping"]
        if looping:
            loop_text = "LOOPING: " + " | ".join(f"{l.name} ({len(l.recorded)})" for l in looping)
            loop_surf = self.font.render(loop_text, True, GREEN)
            self.screen.blit(loop_surf, (20, HEIGHT - 52))

        footer = self.font.render(
            "[1-8] Play   [ENTER] Accept & next layer   [R] Redo   [TAB] Skip   [ESC] Stop",
            True, TEXT_DIM)
        self.screen.blit(footer, (20, HEIGHT - 20))

    def _draw_drum_grid(self, layer, x, y, w, h, frac, total_beats, beat_dur, loop_dur):
        """Draw drum lane view — lanes for each drum, notes as blocks."""
        # Get unique drums used
        drums_used = sorted(set(n[1] for n in layer.notes))
        if not drums_used:
            drums_used = list(DRUM_NAMES.keys())
        lane_h = h / max(1, len(drums_used))

        # Beat grid lines
        for beat in range(total_beats + 1):
            bx = x + int((beat / total_beats) * w)
            color = GRID_BAR if beat % 4 == 0 else GRID_BEAT if beat % 2 == 0 else GRID_LINE
            pygame.draw.line(self.screen, color, (bx, y), (bx, y + h), 1)
            if beat % 4 == 0:
                bar_num = beat // 4 + 1
                if bar_num <= LOOP_BARS:
                    label = self.font.render(str(bar_num), True, TEXT_DIM)
                    self.screen.blit(label, (bx + 3, y + 2))

        # Lanes
        for i, drum_note in enumerate(drums_used):
            lane_y = y + int(i * lane_h)
            pygame.draw.line(self.screen, GRID_LINE, (x, lane_y), (x + w, lane_y))

            # Lane label
            name = DRUM_NAMES.get(drum_note, f"N{drum_note}")
            color = DRUM_COLORS.get(drum_note, TEXT)
            label = self.font.render(name, True, color)
            self.screen.blit(label, (5, lane_y + int(lane_h//2) - 7))

        # Draw note blocks
        for t, note, vel, dur in layer.notes:
            if note not in drums_used:
                continue
            lane_idx = drums_used.index(note)
            note_x = x + int((t / loop_dur) * w)
            note_y = y + int(lane_idx * lane_h) + 4
            note_w = max(4, int((0.05) * w / (loop_dur / total_beats)))  # Thin blocks for hits
            note_h = int(lane_h) - 8
            color = DRUM_COLORS.get(note, CYAN)

            # Approaching playhead — glow
            px = x + int(frac * w)
            dist = abs(note_x - px)
            if dist < 30:
                glow = pygame.Surface((note_w + 8, note_h + 8), pygame.SRCALPHA)
                glow.fill((*color, 60))
                self.screen.blit(glow, (note_x - 4, note_y - 4))

            pygame.draw.rect(self.screen, color, (note_x, note_y, note_w, note_h), border_radius=2)

        # Draw played notes (player's hits)
        for t, note, vel in self.played_notes:
            if note not in drums_used:
                continue
            lane_idx = drums_used.index(note)
            hit_x = x + int((t / loop_dur) * w)
            hit_y = y + int(lane_idx * lane_h) + int(lane_h // 2)
            pygame.draw.circle(self.screen, GREEN, (hit_x, hit_y), 5)

    def _draw_melody_grid(self, layer, x, y, w, h, frac, total_beats, beat_dur, loop_dur):
        """Draw piano roll view — vertical = pitch, horizontal = time."""
        # Note range
        notes = [n[1] for n in layer.notes]
        if not notes:
            return
        min_note = min(notes) - 2
        max_note = max(notes) + 2
        note_range = max(1, max_note - min_note)

        # Beat grid
        for beat in range(total_beats + 1):
            bx = x + int((beat / total_beats) * w)
            color = GRID_BAR if beat % 4 == 0 else GRID_BEAT if beat % 2 == 0 else GRID_LINE
            pygame.draw.line(self.screen, color, (bx, y), (bx, y + h), 1)
            if beat % 4 == 0:
                bar_num = beat // 4 + 1
                if bar_num <= LOOP_BARS:
                    label = self.font.render(str(bar_num), True, TEXT_DIM)
                    self.screen.blit(label, (bx + 3, y + 2))

        # Piano key labels on left
        for midi_note in range(min_note, max_note + 1):
            note_y = y + h - int(((midi_note - min_note) / note_range) * h)
            name = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][midi_note % 12]
            octave = midi_note // 12 - 1
            if name in ('C', 'E', 'G'):
                label = self.font.render(f"{name}{octave}", True, TEXT_DIM)
                self.screen.blit(label, (5, note_y - 7))
                pygame.draw.line(self.screen, GRID_LINE, (x, note_y), (x + w, note_y), 1)

        # Draw note blocks
        px = x + int(frac * w)
        for t, note, vel, dur in layer.notes:
            note_x = x + int((t / loop_dur) * w)
            note_y = y + h - int(((note - min_note) / note_range) * h) - 4
            note_w = max(6, int((dur / loop_dur) * w))
            note_h = max(4, int(h / note_range * 0.8))

            # Color by hue
            hue = (note * 30) % 360
            r = max(0, min(255, int(255 * abs((hue / 60) % 6 - 3) - 1)))
            g = max(0, min(255, int(255 * (2 - abs((hue / 60) % 6 - 2)))))
            b = max(0, min(255, int(255 * (2 - abs((hue / 60) % 6 - 4)))))
            color = (r, g, b)

            # Glow near playhead
            dist = abs(note_x - px)
            if dist < 40:
                glow = pygame.Surface((note_w + 6, note_h + 6), pygame.SRCALPHA)
                glow.fill((*color, 50))
                self.screen.blit(glow, (note_x - 3, note_y - 3))

            pygame.draw.rect(self.screen, color, (note_x, note_y, note_w, note_h), border_radius=2)
            pygame.draw.rect(self.screen, WHITE, (note_x, note_y, note_w, note_h), 1, border_radius=2)

    # ===== REVIEW =====
    def _draw_review(self):
        cx = WIDTH // 2
        layer = self.layers[self.current_layer_idx]

        title = self.font_big.render(f"{layer.name.upper()} — RECORDED", True, GREEN)
        self.screen.blit(title, (cx - title.get_width()//2, 100))

        hits = self.font_med.render(f"You played {len(self.played_notes)} notes", True, TEXT)
        self.screen.blit(hits, (cx - hits.get_width()//2, 180))

        # Show layer status
        y_start = 250
        for i, l in enumerate(self.layers):
            color = GREEN if l.state == "looping" else RED if l.state == "recording" else TEXT_DIM
            status = l.state.upper()
            line = self.font_med.render(f"  {l.name.upper():12s}  {status}", True, color)
            self.screen.blit(line, (cx - 150, y_start + i * 30))

        # Instructions
        opts = [
            "[ENTER] Accept & loop — move to next layer",
            "[R] Retry — record this layer again",
            "[S] Skip — move on without this layer",
        ]
        for i, opt in enumerate(opts):
            surf = self.font.render(opt, True, TEXT_DIM)
            self.screen.blit(surf, (cx - surf.get_width()//2, HEIGHT - 120 + i * 22))

    def _cleanup(self):
        if self.midi_port:
            for ch in range(16):
                self.midi_port.send(mido.Message('control_change', control=123, value=0, channel=ch))
            self.midi_port.close()
        pygame.quit()


def main():
    port_name = "FE Bridge"
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port_name = sys.argv[i + 1]

    print()
    print("=" * 50)
    print("  MOONWOLF LOOPER")
    print("  Build songs live. 8 bars at a time.")
    print("  All sound comes from Ableton.")
    print("=" * 50)

    looper = Looper(port_name)
    looper.run()


if __name__ == "__main__":
    main()
