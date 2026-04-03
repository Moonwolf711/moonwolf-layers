"""
Playing state — the core gameplay loop.

Handles scrolling, ship physics, note collection, drum timing, star power,
combo scoring, particles, and all gameplay drawing.

Transitions:
    -> "LEVEL_COMPLETE" when the camera passes the end of the level.
    -> "MAIN_MENU" on ESC (saves profile).
    -> "LEVEL_INTRO" on R (restart level).
"""

import math
import time
import random
import pygame

from src.states.base import GameState
from src.data.constants import (
    WIDTH, HEIGHT, TILE, FPS,
    C_BG, C_NEON_CYAN, C_NEON_PINK, C_NEON_GREEN, C_NEON_YELLOW,
    C_STAR_GOLD, C_ENEMY, C_HUD, C_HUD_DIM,
    C_GROUND_TOP, C_BUILDING, C_LANE_BG, C_LANE_LINE,
    HIT_PERFECT, HIT_GREAT, HIT_GOOD, HIT_MISS,
    MULT_THRESHOLDS, GRADES,
    STAR_POWER_THRESHOLD, STAR_POWER_BARS,
    DRUM_CH, FE_DRUM_MAP,
    TRANSPORT_CC_PLAY, TRANSPORT_CC_STOP, TRANSPORT_CC_RECORD,
)


class PlayingState(GameState):

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def enter(self):
        pass

    def exit(self):
        pass

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_event(self, event):
        game = self.game

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                import save_system
                if game.profile:
                    save_system.save_profile(game.profile)
                return "MAIN_MENU"
            elif event.key == pygame.K_r:
                game._restart_level()
                return "LEVEL_INTRO"
            elif event.key == pygame.K_EQUALS:
                game._adjust_bpm(2)
            elif event.key == pygame.K_MINUS:
                game._adjust_bpm(-2)
            # Number keys for drum testing
            elif pygame.K_1 <= event.key <= pygame.K_8:
                game._on_fe_button(event.key - pygame.K_1)

        elif event.type == pygame.KEYUP:
            if pygame.K_1 <= event.key <= pygame.K_8:
                game._on_fe_button_release(event.key - pygame.K_1)

        return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt):
        game = self.game

        # ---- Common timers (run in all states, extracted here for PLAYING) ----
        game.state_timer += dt

        # Beat tracking
        game.beat_timer += dt
        if game.beat_timer >= game.beat_interval:
            game.beat_timer -= game.beat_interval
            game.beat_flash = 1.0
        game.beat_flash *= 0.85

        # Venom timer decay
        if game.venom_timer > 0:
            game.venom_timer -= dt
        game.combo_pulse *= 0.88

        # Lane flashes decay
        for k in list(game.p2_lane_flash.keys()):
            game.p2_lane_flash[k] *= 0.85
            if game.p2_lane_flash[k] < 0.05:
                del game.p2_lane_flash[k]

        # Star power timer
        if game.star_power:
            game.star_power_timer -= dt
            if game.star_power_timer <= 0:
                game.star_power = False
                print("  Star Power ended")

        # Pending note offs
        now = time.time()
        still = []
        for note, ch, off_time in game.pending_offs:
            if now >= off_time:
                game.note_off(note, ch)
            else:
                still.append((note, ch, off_time))
        game.pending_offs = still

        # Update particles & popups
        game.particles.update(dt)
        game.popups.update(dt)

        # Screen shake decay
        if game.shake_intensity > 0.1:
            game.shake_x = random.uniform(-game.shake_intensity, game.shake_intensity)
            game.shake_y = random.uniform(-game.shake_intensity, game.shake_intensity)
            game.shake_intensity *= 0.85
        else:
            game.shake_x = game.shake_y = 0
            game.shake_intensity = 0

        # ---- Gameplay-specific update ----

        # Joystick input
        joy_x, joy_y = 0, 0
        if game.joystick:
            joy_x = game.joystick.get_axis(0)
            joy_y = game.joystick.get_axis(1)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]:
            joy_y = -0.8
        if keys[pygame.K_DOWN]:
            joy_y = 0.8

        # ===== DEMO BOT =====
        if game.demo_mode:
            joy_y = self._demo_bot_steering(joy_y)
            self._demo_bot_drums()

        # Speed
        game.speed_mult = 1.0 + joy_x * 0.3
        game.speed_mult = max(0.5, min(1.5, game.speed_mult))

        # Scroll
        actual_speed = game.scroll_speed * game.speed_mult * game.speed_bonus
        game.camera_x += actual_speed * dt

        # Level complete?
        if game.camera_x > game.level.level_width + 200:
            self._on_level_complete()
            return "LEVEL_COMPLETE"

        # P1 ship-style flight
        is_melody_level = len(game.level.pickups) > 0
        if is_melody_level:
            self._update_ship_physics(joy_y, dt)

        # Melody notes — auto-play at correct musical time, score based on proximity
        self._update_melody_notes()

        # Auto-play drum targets that pass the hit line
        self._update_auto_drums()

        # Star Power riffing
        if game.star_power:
            if game.beat_flash > 0.9:
                degree = int(game.p1_y / HEIGHT * len(game.scale))
                degree = max(0, min(len(game.scale) - 1, degree))
                riff_note = game.scale[degree]
                riff_ch = getattr(game.level, 'midi_channel', game.p1_midi_ch)
                game.note_on(riff_note, 100, riff_ch)
                game.pending_offs.append((riff_note, riff_ch, time.time() + 0.15))

        # Fire trail and sparkles
        if is_melody_level:
            if game.combo >= 10:
                intensity = min(3.0, game.combo / 15.0)
                game.particles.emit_fire(190, int(game.p1_y) + 10, intensity)
            if game.star_power:
                game.particles.emit_star(200, int(game.p1_y))

        return None

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def _demo_bot_steering(self, joy_y):
        """Auto-steer ship in demo mode. Returns modified joy_y."""
        game = self.game
        player_x = game.camera_x + 200

        upcoming = []
        for pickup in game.level.pickups:
            if pickup[3]:
                continue
            px, py, note, _ = pickup
            ahead = px - player_x
            if -20 < ahead < 600:
                upcoming.append((ahead, py))
            if len(upcoming) >= 3:
                break

        if upcoming:
            if len(upcoming) >= 2:
                w1, w2 = 0.7, 0.3
                target_y = upcoming[0][1] * w1 + upcoming[1][1] * w2
            else:
                target_y = upcoming[0][1]
        else:
            target_y = game.p1_y

        diff = target_y - game.p1_y
        if abs(diff) > 2:
            p_gain = diff / 25.0
            d_gain = -game.p1_vy / 400.0
            joy_y = max(-1.0, min(1.0, p_gain + d_gain))
        else:
            joy_y = 0
            game.p1_vy *= 0.3

        return joy_y

    def _demo_bot_drums(self):
        """Auto-hit drums in demo mode."""
        game = self.game
        player_x = game.camera_x + 200
        for dl in game.level.drum_lanes:
            if dl[3]:
                continue
            dx, lane_idx, drum_note, _ = dl
            dist = player_x - dx
            if -10 <= dist <= 10:
                game._on_fe_button(lane_idx)

    def _update_ship_physics(self, joy_y, dt):
        """Update P1 ship-style flight physics."""
        game = self.game
        play_top = game.level.play_top
        play_bottom = game.level.play_bottom
        thrust = 1800.0 if game.agile else 1200.0
        if game.flight:
            drag = 1.5
            max_vel = 600.0
        else:
            drag = 4.0
            max_vel = 500.0

        # Note magnetism
        player_x = game.camera_x + 200
        magnet_strength = 200.0
        best_dist = 99999
        next_note_y = None
        for pickup in game.level.pickups:
            if pickup[3]:
                continue
            px, py, note, _ = pickup
            ahead = px - player_x
            if -30 < ahead < 400:
                if ahead < best_dist:
                    best_dist = ahead
                    next_note_y = py

        game._next_note_y = next_note_y
        game._next_note_dist = best_dist if next_note_y else 0

        if next_note_y is not None:
            closeness = max(0, 1.0 - best_dist / 400.0)
            diff = next_note_y - game.p1_y
            game.p1_vy += diff * magnet_strength * closeness * dt

        # Thrust from joystick
        game.p1_vy += joy_y * thrust * dt

        # Drag
        game.p1_vy -= game.p1_vy * drag * dt

        # Clamp velocity
        game.p1_vy = max(-max_vel, min(max_vel, game.p1_vy))

        # Move
        game.p1_y += game.p1_vy * dt

        # Bounce off edges (soft)
        if game.p1_y < play_top:
            game.p1_y = play_top
            game.p1_vy = abs(game.p1_vy) * 0.3
        elif game.p1_y > play_bottom:
            game.p1_y = play_bottom
            game.p1_vy = -abs(game.p1_vy) * 0.3

    def _update_melody_notes(self):
        """Score melody notes as they pass the hit line."""
        game = self.game
        player_x = game.camera_x + 200

        for pickup in game.level.pickups:
            if pickup[3]:
                continue
            px, py, note, _ = pickup

            if player_x >= px - 5:
                pickup[3] = True
                dy = abs(game.p1_y - py)

                # Adaptive collection radius
                base_radius = 77 if game.soar else 55
                next_dx = 999
                for p2 in game.level.pickups:
                    if p2[3] or p2 is pickup:
                        continue
                    nd = abs(p2[0] - px)
                    if 0 < nd < next_dx:
                        next_dx = nd
                if next_dx < 40:
                    collect_radius = base_radius + 30
                elif next_dx < 80:
                    collect_radius = base_radius + 15
                else:
                    collect_radius = base_radius

                if dy < collect_radius:
                    # Ship is close — full velocity, score it
                    game.note_on(note, 100, getattr(game.level, 'midi_channel', game.p1_midi_ch))
                    game.hits += 1
                    game.combo += 1
                    game.combo_pulse = 1.0
                    game.max_combo = max(game.max_combo, game.combo)
                    if game.combo % 10 == 0 and game.combo > 0:
                        game.combo_10s += 1
                    mult = game._get_multiplier()

                    if dy < 15 * game.perfect_bonus:
                        game.perfects += 1
                        game.score += game._score_multiplier(50 * (2 if game.predator else 1), mult)
                        game.star_meter = min(1.0, game.star_meter + 0.08 * game.star_fill_bonus)
                        game.popups.add(200, int(game.p1_y) - 30, f"PERFECT! x{mult}", C_STAR_GOLD)
                        game.particles.emit(200, int(py), 12, C_STAR_GOLD, 180)
                        game._shake(4)
                    elif dy < 30:
                        game.greats += 1
                        game.score += game._score_multiplier(30, mult)
                        game.star_meter = min(1.0, game.star_meter + 0.05 * game.star_fill_bonus)
                        game.popups.add(200, int(game.p1_y) - 30, f"GREAT! x{mult}", C_NEON_GREEN)
                        game.particles.emit(200, int(py), 8, C_NEON_GREEN, 120)
                    else:
                        game.goods += 1
                        game.score += game._score_multiplier(10, mult)
                        game.star_meter = min(1.0, game.star_meter + 0.03 * game.star_fill_bonus)
                        game.popups.add(200, int(game.p1_y) - 30, f"Good x{mult}", C_HUD)
                        game.particles.emit(200, int(py), 4, C_HUD, 60)
                else:
                    # Ship is far — play note quietly but no score
                    game.note_on(note, 50, getattr(game.level, 'midi_channel', game.p1_midi_ch))
                    game._try_break_combo(200, int(py))

                mel_ch = getattr(game.level, 'midi_channel', game.p1_midi_ch)
                game.pending_offs.append((note, mel_ch, time.time() + 0.25))

    def _update_auto_drums(self):
        """Auto-play drum targets that pass the hit line (keeps song in time)."""
        game = self.game
        player_x = game.camera_x + 200
        for dl in game.level.drum_lanes:
            if dl[3]:
                continue
            dx, lane_idx, drum_note, _ = dl
            if player_x >= dx + HIT_MISS:
                dl[3] = True
                game.note_on(drum_note, 40, DRUM_CH)
                game.pending_offs.append((drum_note, DRUM_CH, time.time() + 0.1))

    def _on_level_complete(self):
        """Handle level completion — XP award, profile save, transport stop."""
        game = self.game
        import save_system

        # Stop Ableton recording
        if game.ableton_recording:
            game._send_transport(TRANSPORT_CC_RECORD)
            game.ableton_recording = False
        print(f"  Level complete! Hits: {game.hits}/{game.total_targets} | Max combo: {game.max_combo}")

        # Award XP via save system
        pct = (game.hits / max(1, game.total_targets)) * 100
        grade_letter, grade_color = game._get_grade(pct)
        if game.profile:
            game.xp_result = save_system.award_xp(
                game.profile,
                hits=game.hits,
                perfects=game.perfects,
                greats=game.greats,
                goods=game.goods,
                combo_10s=game.combo_10s,
                star_powers=game.star_power_activations,
                levels_complete=1,
                grade=grade_letter,
            )
            game.profile["games_played"] = game.profile.get("games_played", 0) + 1
            game.profile["total_hits"] = game.profile.get("total_hits", 0) + game.hits
            game.profile["total_perfects"] = game.profile.get("total_perfects", 0) + game.perfects
            game.profile["total_score"] = game.profile.get("total_score", 0) + game.score
            game.profile["best_combo"] = max(game.profile.get("best_combo", 0), game.max_combo)
            # Track best grade
            grade_order = ["F", "D", "C", "B", "A", "S"]
            old_g = game.profile.get("best_grade", "F")
            if grade_order.index(grade_letter) > grade_order.index(old_g):
                game.profile["best_grade"] = grade_letter
            save_system.save_profile(game.profile)
            print(f"  XP earned: {game.xp_result['xp_earned']} | Level: {game.xp_result['new_level']}")
            if game.xp_result['leveled_up']:
                print(f"  LEVEL UP! {game.xp_result['old_level']} -> {game.xp_result['new_level']}")

        # Big particle burst in the grade's color
        for _ in range(3):
            bx = random.randint(WIDTH // 4, WIDTH * 3 // 4)
            game.particles.emit(bx, HEIGHT // 3, 40, grade_color, speed=250, life=1.5, size=4, spread=5.0)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, screen):
        game = self.game

        from src.rendering.skyline import draw_skyline

        screen.fill(C_BG)

        cam = int(game.camera_x)
        sx_off = int(game.shake_x)
        sy_off = int(game.shake_y)

        # Stars (parallax layer 0 - slowest)
        for sx, sy, b in game.stars:
            screen_x = int((sx - cam * 0.05) % (WIDTH * 4)) - WIDTH + sx_off
            if 0 <= screen_x < WIDTH:
                brightness = b * (1.0 + game.beat_flash * 0.5)
                screen.set_at(
                    (screen_x, sy),
                    (
                        int(min(255, brightness * 150)),
                        int(min(255, brightness * 130)),
                        int(min(255, brightness * 200)),
                    ),
                )

        # City skyline (parallax layer 1)
        ground_y = HEIGHT - 170
        draw_skyline(screen, game.skyline, cam, ground_y, game.beat_flash)

        # Tron grid floor
        horizon_y = ground_y - 60
        grid_color_h = (*C_NEON_CYAN[:3],)
        grid_color_v = (*C_NEON_PINK[:3],)

        # Horizontal grid lines
        for i in range(12):
            frac = i / 12.0
            y = int(horizon_y + (ground_y - horizon_y) * (frac ** 0.6))
            alpha = int(10 + 30 * frac)
            gs = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
            gs.fill((*grid_color_h, alpha))
            screen.blit(gs, (0, y))

        # Vertical grid lines
        vanish_x = WIDTH // 2
        for i in range(-10, 11):
            bx = vanish_x + i * 80
            tx = vanish_x + i * 8
            pygame.draw.line(screen, (*grid_color_v[:3],), (tx, horizon_y), (bx, ground_y), 1)

        # Ground line with neon glow
        pygame.draw.line(screen, C_GROUND_TOP, (0, ground_y), (WIDTH, ground_y), 2)
        for w, a in [(8, 15), (4, 30), (2, 60)]:
            glow_surf = pygame.Surface((WIDTH, w), pygame.SRCALPHA)
            glow_surf.fill((*C_NEON_CYAN, a))
            screen.blit(glow_surf, (0, ground_y - w // 2))

        # Scrolling ground dashes
        dash_w, dash_h, dash_gap = 20, 3, 40
        dash_y_center = ground_y + 6
        dash_offset = int(cam * 0.8) % (dash_w + dash_gap)
        dash_color = (50, 30, 70)
        for dx in range(-dash_offset, WIDTH + dash_w, dash_w + dash_gap):
            pygame.draw.rect(screen, dash_color, (dx + sx_off, dash_y_center + sy_off, dash_w, dash_h))
        dash_y2 = ground_y + 16
        dash_offset2 = int(cam * 0.8 + (dash_w + dash_gap) // 2) % (dash_w + dash_gap)
        for dx in range(-dash_offset2, WIDTH + dash_w, dash_w + dash_gap):
            pygame.draw.rect(screen, (40, 25, 55), (dx + sx_off, dash_y2 + sy_off, dash_w, dash_h))

        # Drum lanes (bottom section)
        lane_h = 20
        lane_area_top = HEIGHT - 160
        lane_area_h = 8 * lane_h + 16

        lane_bg = pygame.Surface((WIDTH, lane_area_h + 16), pygame.SRCALPHA)
        lane_bg.fill((15, 10, 30, 200))
        screen.blit(lane_bg, (0 + sx_off, lane_area_top - 8 + sy_off))

        hit_line_x = 200

        for lane_idx in range(8):
            lane_y = lane_area_top + lane_idx * lane_h + sy_off
            pygame.draw.line(screen, C_LANE_LINE, (0, lane_y), (WIDTH, lane_y))
            _, name, color = FE_DRUM_MAP[lane_idx]
            label = game.font.render(name, True, color)
            screen.blit(label, (5 + sx_off, lane_y + 2))
            if lane_idx in game.p2_lane_flash:
                flash_surf = pygame.Surface((WIDTH, lane_h), pygame.SRCALPHA)
                alpha = int(game.p2_lane_flash[lane_idx] * 150)
                flash_surf.fill((*color, alpha))
                screen.blit(flash_surf, (0 + sx_off, lane_y))

        # Hit line with glow
        for w, a in [(6, 30), (3, 80), (1, 200)]:
            line_surf = pygame.Surface((w, lane_area_h + 16), pygame.SRCALPHA)
            line_surf.fill((*C_NEON_CYAN, a))
            screen.blit(line_surf, (hit_line_x - w // 2 + sx_off, lane_area_top - 8 + sy_off))

        # Approach indicators
        for dist, color, alpha in [
            (HIT_PERFECT, C_STAR_GOLD, 40),
            (HIT_GREAT, C_NEON_GREEN, 25),
            (HIT_GOOD, C_HUD, 15),
        ]:
            for side in (-1, 1):
                x = hit_line_x + dist * side + sx_off
                s = pygame.Surface((1, lane_area_h), pygame.SRCALPHA)
                s.fill((*color, alpha))
                screen.blit(s, (x, lane_area_top - 4 + sy_off))

        # Drum lane targets
        for dl in game.level.drum_lanes:
            dx, lane_idx, drum_note, hit = dl
            screen_x = dx - cam + sx_off
            if screen_x < -20 or screen_x > WIDTH + 20:
                continue
            if hit:
                continue
            lane_y = lane_area_top + lane_idx * lane_h + sy_off
            _, name, color = FE_DRUM_MAP.get(lane_idx, (0, "?", (100, 100, 100)))

            # Approach glow
            dist_to_hit = abs(screen_x - hit_line_x)
            if dist_to_hit < 150:
                glow_alpha = int((1.0 - dist_to_hit / 150.0) * 80)
                glow_s = pygame.Surface((24, lane_h), pygame.SRCALPHA)
                glow_s.fill((*color, glow_alpha))
                screen.blit(glow_s, (screen_x - 12, lane_y))

            # Target marker
            pygame.draw.rect(screen, color, (screen_x - 8, lane_y + 2, 16, lane_h - 4), border_radius=3)
            pygame.draw.rect(screen, (255, 255, 255), (screen_x - 8, lane_y + 2, 16, lane_h - 4), 1, border_radius=3)

        # Melody pickups
        for pickup in game.level.pickups:
            px, py, note, collected = pickup
            screen_x = px - cam + sx_off
            if collected or screen_x < -20 or screen_x > WIDTH + 20:
                continue
            hue = (note * 30) % 360
            color = game._hsv(hue, 0.9, 1.0)
            bob_y = py + math.sin(time.time() * 4 + px * 0.01) * 4 + sy_off

            glow = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, 60), (16, 16), 16)
            pygame.draw.circle(glow, (*color, 180), (16, 16), 8)
            pygame.draw.circle(glow, (255, 255, 255), (16, 16), 3)
            screen.blit(glow, (screen_x - 16, bob_y - 16))

        # Guide line to next uncollected note
        is_melody_level = len(game.level.pickups) > 0
        if is_melody_level and hasattr(game, '_next_note_y') and game._next_note_y is not None:
            p1_sy = int(game.p1_y) + sy_off
            target_y = int(game._next_note_y) + sy_off
            dist_val = game._next_note_dist
            alpha = max(20, min(80, int((1.0 - dist_val / 400.0) * 80)))
            guide_color = C_STAR_GOLD if game.star_power else (0, 150, 200)
            steps = max(2, int(abs(target_y - p1_sy) / 8))
            for i in range(0, steps, 2):
                frac = i / max(1, steps)
                gy = int(p1_sy + (target_y - p1_sy) * frac)
                gx = 200 + int(frac * min(100, dist_val * 0.3)) + sx_off
                dot = pygame.Surface((3, 3), pygame.SRCALPHA)
                dot.fill((*guide_color, alpha))
                screen.blit(dot, (gx, gy))

        # P1 ship sprite
        if is_melody_level:
            p1_screen_x = 200 + sx_off
            p1_y = int(game.p1_y) + sy_off
            p1_ch = game.CHARACTERS[game.p1_char_idx]
            glow_color = C_STAR_GOLD if game.star_power else p1_ch["color"]

            # Tron light trail
            trail_len = min(180, int(game.combo * 3) + 20)
            trail_color = C_STAR_GOLD if game.star_power else p1_ch["color"]
            for i in range(trail_len, 0, -3):
                alpha = int((1.0 - i / trail_len) * 60)
                ts = pygame.Surface((3, 4), pygame.SRCALPHA)
                ts.fill((*trail_color, alpha))
                screen.blit(ts, (p1_screen_x - i, p1_y - 2))

            # Engine glow
            tilt = game.p1_vy / 350.0
            for radius, alpha in [(40, 15), (30, 25), (20, 40)]:
                aura = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(aura, (*glow_color, alpha), (radius, radius), radius)
                screen.blit(aura, (p1_screen_x + 16 - radius, p1_y - radius + int(tilt * 5)))

            # Sprite (slight visual tilt)
            sprite = game.p1_sprite
            if abs(tilt) > 0.15:
                angle = -tilt * 15
                sprite = pygame.transform.rotate(game.p1_sprite, angle)
            screen.blit(sprite, (p1_screen_x, p1_y - sprite.get_height() // 2))

        # P2 indicator — only in 2P mode
        if game.menu_player_mode == 1:
            screen.blit(game.p2_sprite, (hit_line_x - 16 + sx_off, lane_area_top - 40 + sy_off))

        # Star power meter
        meter_w = 160
        meter_h = 12
        mx = WIDTH - meter_w - 20 + sx_off
        my = 50 + sy_off
        pygame.draw.rect(screen, (20, 20, 40), (mx - 1, my - 1, meter_w + 2, meter_h + 2), border_radius=3)
        fill_w = int(game.star_meter * meter_w)
        star_color = C_STAR_GOLD if game.star_power else (100, 80, 0)
        if fill_w > 0:
            pygame.draw.rect(screen, star_color, (mx, my, fill_w, meter_h), border_radius=2)
            if game.star_power:
                gs = pygame.Surface((fill_w, meter_h + 6), pygame.SRCALPHA)
                gs.fill((*C_STAR_GOLD, 40))
                screen.blit(gs, (mx, my - 3))
        pygame.draw.rect(screen, (80, 80, 100), (mx - 1, my - 1, meter_w + 2, meter_h + 2), 1, border_radius=3)
        star_label = "STAR POWER!" if game.star_power else f"Star: {int(game.star_meter * 100)}%"
        screen.blit(game.font.render(star_label, True, star_color), (mx, my - 18))

        # Combo counter
        mult = game._get_multiplier()
        if game.combo >= 40:
            combo_color = C_STAR_GOLD
        elif game.combo >= 20:
            combo_color = C_NEON_CYAN
        elif game.combo >= 10:
            combo_color = C_NEON_GREEN
        else:
            combo_color = (220, 220, 220)
        if game.combo > 0:
            combo_str = f"{game.combo}"
            pulse_scale = 1.0 + game.combo_pulse * 0.4
            combo_surf = game.font_title.render(combo_str, True, combo_color)
            if pulse_scale > 1.02:
                new_w = int(combo_surf.get_width() * pulse_scale)
                new_h = int(combo_surf.get_height() * pulse_scale)
                combo_surf = pygame.transform.scale(combo_surf, (new_w, new_h))
            cx_combo = WIDTH - 80 + sx_off - combo_surf.get_width() // 2
            cy_combo = 78 + sy_off - combo_surf.get_height() // 2
            screen.blit(combo_surf, (cx_combo, cy_combo))
        if mult > 1:
            mult_colors = {2: C_NEON_GREEN, 4: C_NEON_CYAN, 8: C_STAR_GOLD}
            mc = mult_colors.get(mult, C_NEON_PINK)
            mult_text = game.font.render(f"x{mult}", True, mc)
            screen.blit(mult_text, (WIDTH - 80 + sx_off - mult_text.get_width() // 2, 100 + sy_off))

        # Progress bar
        if game.level.level_width > 0:
            progress = min(1.0, max(0, game.camera_x / game.level.level_width))
            bar_w = WIDTH - 40
            bar_y = 68 + sy_off
            pygame.draw.rect(screen, (20, 20, 40), (20 + sx_off, bar_y, bar_w, 4), border_radius=2)
            fill = int(progress * bar_w)
            if fill > 0:
                bar_color = C_STAR_GOLD if game.star_power else C_NEON_CYAN
                pygame.draw.rect(screen, bar_color, (20 + sx_off, bar_y, fill, 4), border_radius=2)

        # Beat flash edges
        if game.beat_flash > 0.1:
            alpha = int(game.beat_flash * 120)
            for y_pos in [0, HEIGHT - 3]:
                flash = pygame.Surface((WIDTH, 3), pygame.SRCALPHA)
                flash.fill((*C_NEON_CYAN, alpha))
                screen.blit(flash, (0, y_pos))

        # Particles & popups
        game.particles.draw(screen)
        game.popups.draw(screen)

        # HUD
        self._draw_hud(screen)

    def _draw_hud(self, screen):
        """Draw the HUD overlay."""
        game = self.game
        import save_system

        lv = game.level
        bar_num = int(game.camera_x / max(1, lv.level_width) * lv.bars) + 1
        texts = [
            (f"MOONWOLF LAYERS", C_NEON_CYAN, 10, 8, game.font_big),
            (
                f"Level {game.current_level + 1}: {lv.name} | {game.bpm} BPM | Bar {bar_num}/{lv.bars}",
                C_HUD, 10, 35, game.font,
            ),
            (
                f"Score: {game.score} | Combo: x{game.combo} | Layers: {game.locked_levels} | "
                f"{'REC' if game.ableton_recording else 'IDLE'}",
                C_HUD_DIM, 10, 52, game.font,
            ),
            (
                f"[+/-]=BPM [R]=Restart [ESC]=Quit | Combo {STAR_POWER_THRESHOLD}+ = Star Power (free riff!)",
                C_HUD_DIM, 10, HEIGHT - 18, game.font,
            ),
        ]
        for text, color, x, y, font in texts:
            screen.blit(font.render(text, True, color), (x, y))

        # XP bar (top right)
        if game.profile:
            level, xp_into, xp_needed = save_system.xp_progress(game.profile["xp"])
            xp_bar_w, xp_bar_h = 120, 8
            xp_x = WIDTH - xp_bar_w - 10
            xp_y = 10
            lv_surf = game.font.render(f"Lv.{level}", True, C_NEON_CYAN)
            screen.blit(lv_surf, (xp_x - lv_surf.get_width() - 5, xp_y - 2))
            pygame.draw.rect(screen, (30, 25, 50), (xp_x, xp_y, xp_bar_w, xp_bar_h))
            fill = int(xp_bar_w * xp_into / max(1, xp_needed))
            pygame.draw.rect(screen, C_NEON_CYAN, (xp_x, xp_y, fill, xp_bar_h))
