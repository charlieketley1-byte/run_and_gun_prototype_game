# game.py
# The Game class owns the main loop and high-level states:
# START -> PLAYING -> (GAME_OVER or LEVEL_COMPLETE) -> PLAYING ...

from __future__ import annotations
import pygame

from . import settings
from .level import Level
from .player import Player
from .utils import load_sound, asset_path, clamp


class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        # ---------------------------------------------------------------------
        # Fixed OS window + separate logical "world" surface
        #
        # - Window stays constant: settings.WINDOW_WIDTH x settings.WINDOW_HEIGHT
        # - World is rendered at: settings.RENDER_WIDTH x settings.RENDER_HEIGHT
        # - World is then scaled to the window each frame
        # - Menu + UI are drawn directly onto the window (not scaled)
        # ---------------------------------------------------------------------
        self.window = pygame.display.set_mode((settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT))
        pygame.display.set_caption("Run & Gun Prototype (Pygame-CE)")

        # Draw world/gameplay to this logical surface (scaled up when presenting)
        self.world = pygame.Surface((settings.RENDER_WIDTH, settings.RENDER_HEIGHT)).convert()

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22)
        self.big_font = pygame.font.SysFont("consolas", 44, bold=True)

        # Audio
        self.sfx_shoot = load_sound("shoot.wav")
        self.sfx_pickup = load_sound("pickup.wav")
        self.sfx_hurt = load_sound("hurt.wav")
        self.sfx_shoot.set_volume(settings.SFX_VOLUME)
        self.sfx_pickup.set_volume(settings.SFX_VOLUME)
        self.sfx_hurt.set_volume(settings.SFX_VOLUME)

        music_path = asset_path("audio", "music.wav")
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.set_volume(settings.MUSIC_VOLUME)
        if not settings.SOUND_OFF:
            pygame.mixer.music.play(-1)  # loop

        # Game state
        self.state = "START"  # START, PLAYING, GAME_OVER, LEVEL_COMPLETE
        self.running = True

        # Camera (in WORLD/logical pixels)
        self.camera_x = 0.0
        self.camera_y = 0.0

        # World content
        self.level_index = 1
        self.level: Level | None = None
        self.player: Player | None = None

        self.bullets = pygame.sprite.Group()
        self.boss_bullets = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()

        self.load_level(self.level_index, f"level{self.level_index}.csv")

    def load_level(self, index: int, level_file: str = "level1.csv") -> None:
        # You can expand this into a list of levels later.
        self.level = Level(level_file)
        self.player = Player(self.level.player_spawn)
        self.bullets.empty()
        self.boss_bullets.empty()

        # Reset camera so the start feels consistent
        self.camera_x = 0.0
        self.camera_y = 0.0

    # ------------------ Main loop ------------------
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(settings.FPS) / 1000.0
            dt = min(dt, 1 / 30)  # clamp if debugging causes huge dt

            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()

    # ------------------ Events ------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

                if self.state == "START":
                    if event.key == pygame.K_RETURN:
                        self.state = "PLAYING"

                elif self.state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        self.load_level(self.level_index)
                        self.state = "PLAYING"

                elif self.state == "LEVEL_COMPLETE":
                    if event.key == pygame.K_RETURN:
                        self.load_level(self.level_index)
                        self.state = "PLAYING"

                if self.state == "PLAYING":
                    # self.player is guaranteed in PLAYING
                    if event.key == pygame.K_w:
                        self.player.queue_jump()

                    if event.key == pygame.K_SPACE:
                        fired = self.player.try_shoot(self.bullets)
                        if fired and not settings.SOUND_OFF:
                            self.sfx_shoot.play()

            if event.type == pygame.KEYUP and self.state == "PLAYING":
                if event.key == pygame.K_w:
                    self.player.cut_jump()

    # ------------------ Update ------------------
    def update(self, dt: float) -> None:
        if self.state != "PLAYING":
            return

        # Safety: these exist when PLAYING
        assert self.level is not None
        assert self.player is not None

        keys = pygame.key.get_pressed()
        self.player.handle_input(keys)

        self.player.update(dt, self.level)

        # Update bullets (player and boss)
        for b in list(self.bullets):
            b.update(dt, self.level)

        for b in list(self.boss_bullets):
            b.update(dt, self.level)

        for b in list(self.enemy_bullets):
            b.update(dt, self.level)    

        # Update level entities and bullet hits
        self.level.update(dt, self.player, self.bullets, self.boss_bullets, self.enemy_bullets)

        # --- Player vs pickups
        hit_pickups = pygame.sprite.spritecollide(self.player, self.level.pickups, dokill=True)
        if hit_pickups:
            for p in hit_pickups:
                p.apply(self.player)
            if not settings.SOUND_OFF:
                self.sfx_pickup.play()

        # --- Player vs enemies contact damage
        if pygame.sprite.spritecollideany(self.player, self.level.enemies):
            self.player.take_damage(settings.ENEMY_DAMAGE)
            if self.player.invuln_time > 0.0 and not settings.SOUND_OFF:
                self.sfx_hurt.play()

        # --- Player vs boss contact damage
        if self.level.boss and self.level.boss.alive() and self.player.rect.colliderect(self.level.boss.rect):
            self.player.take_damage(settings.BOSS_DAMAGE)
            if self.player.invuln_time > 0.0 and not settings.SOUND_OFF:
                self.sfx_hurt.play()

        # --- Player vs boss bullets
        if pygame.sprite.spritecollideany(self.player, self.boss_bullets):
            # remove all bullets that hit
            for b in list(self.boss_bullets):
                if b.rect.colliderect(self.player.rect):
                    b.kill()
            self.player.take_damage(settings.BOSS_DAMAGE)
            if self.player.invuln_time > 0.0 and not settings.SOUND_OFF:
                self.sfx_hurt.play()

        # --- Player vs enemy bullets ---
        if pygame.sprite.spritecollideany(self.player, self.enemy_bullets):
            for b in list(self.enemy_bullets):
                if b.rect.colliderect(self.player.rect):
                    b.kill()

            self.player.take_damage(settings.ENEMY_DAMAGE)

            if self.player.invuln_time > 0.0 and not settings.SOUND_OFF:
                self.sfx_hurt.play()

        # --- Game over
        if self.player.is_dead():
            self.state = "GAME_OVER"

        # --- Level complete: require boss dead, then touch exit flag
        boss_dead = (self.level.boss is None) or (not self.level.boss.alive())
        if boss_dead and self.level.exit_rect and self.player.rect.colliderect(self.level.exit_rect):
            self.state = "LEVEL_COMPLETE"

        # --- Camera follow (simple smooth lerp)
        # IMPORTANT: use world/logical viewport size, not the window size.
        vw, vh = settings.RENDER_WIDTH, settings.RENDER_HEIGHT

        target_x = self.player.rect.centerx - vw * 0.5
        target_y = self.player.rect.centery - vh * 0.6
        target_x = clamp(target_x, 0, max(0, self.level.pixel_width - vw))
        target_y = clamp(target_y, 0, max(0, self.level.pixel_height - vh))

        self.camera_x += (target_x - self.camera_x) * settings.CAMERA_LERP
        self.camera_y += (target_y - self.camera_y) * settings.CAMERA_LERP

    # ------------------ Draw ------------------
    def draw(self) -> None:
        # START screen + UI should be fixed-size, so they draw directly to the window.
        if self.state == "START":
            self.window.fill((20, 22, 30))
            self.draw_center_text("RUN & GUN PROTOTYPE", y=170, big=True, target=self.window)
            self.draw_center_text("Press ENTER to start", y=260, target=self.window)
            self.draw_center_text("A/D move, W jump, SPACE shoot", y=310, target=self.window)
            pygame.display.flip()
            return

        # Safety: level/player exist for all non-start states in this prototype
        assert self.level is not None
        assert self.player is not None

        # ---------- WORLD (draw to logical surface, then scale up) ----------
        self.world.fill((20, 22, 30))

        # World / tiles
        self.level.draw(self.world, self.camera_x, self.camera_y)

        # Entities
        # (Draw order: pickups -> enemies -> boss -> bullets -> player)
        for p in self.level.pickups:
            self.world.blit(p.image, (p.rect.x - self.camera_x, p.rect.y - self.camera_y))

        for e in self.level.enemies:
            self.world.blit(e.image, (e.rect.x - self.camera_x, e.rect.y - self.camera_y))

        if self.level.boss and self.level.boss.alive():
            self.world.blit(
                self.level.boss.image,
                (self.level.boss.rect.x - self.camera_x, self.level.boss.rect.y - self.camera_y),
            )

        for b in self.bullets:
            self.world.blit(b.image, (b.rect.x - self.camera_x, b.rect.y - self.camera_y))

        for b in self.boss_bullets:
            self.world.blit(b.image, (b.rect.x - self.camera_x, b.rect.y - self.camera_y))

        for b in self.enemy_bullets:
            self.world.blit(b.image, (b.rect.x - self.camera_x, b.rect.y - self.camera_y))

        # Player (blink if invulnerable)
        if self.player.invuln_time <= 0 or int(self.player.invuln_time * 20) % 2 == 0:
            self.world.blit(
                self.player.image,
                (self.player.rect.x - self.camera_x, self.player.rect.y - self.camera_y),
            )

        # Present scaled world into fixed window
        scaled_world = pygame.transform.scale(self.world, (settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT))
        self.window.blit(scaled_world, (0, 0))

        # ---------- UI + overlays (draw directly to window; not scaled) ----------
        self.draw_ui(target=self.window)

        if self.state == "GAME_OVER":
            self.draw_overlay(target=self.window)
            self.draw_center_text("GAME OVER", y=220, big=True, target=self.window)
            self.draw_center_text("Press R to restart", y=290, target=self.window)

        elif self.state == "LEVEL_COMPLETE":
            self.draw_overlay(target=self.window)
            self.draw_center_text("LEVEL COMPLETE!", y=220, big=True, target=self.window)
            self.draw_center_text("Press ENTER to replay (add more levels!)", y=290, target=self.window)
            
        # DEBUG: show all idle frames in a row
        if self.state == "PLAYING":
            x = 50
            y = settings.WINDOW_HEIGHT - 80

            for frame in self.player.anim_idle:
                img = pygame.transform.scale(frame, (frame.get_width() * 2, frame.get_height() * 2))
                self.window.blit(img, (x, y))
                x += img.get_width() + 10

        pygame.display.flip()

    # ------------------ UI helpers ------------------
    def draw_ui(self, target: pygame.Surface) -> None:
        # Health bar (fixed window coords)
        x, y, w, h = 20, 20, 220, 18
        pygame.draw.rect(target, (50, 50, 50), (x, y, w, h))
        hp_ratio = self.player.health / self.player.max_health if self.player.max_health > 0 else 0
        pygame.draw.rect(target, (80, 220, 120), (x, y, int(w * hp_ratio), h))
        txt = self.font.render(f"HP: {self.player.health}/{self.player.max_health}", True, (230, 230, 230))
        target.blit(txt, (x, y + 22))

        # Boss health (when alive)
        if self.level.boss and self.level.boss.alive():
            bx, by, bw, bh = settings.WINDOW_WIDTH - 280, 20, 260, 14
            pygame.draw.rect(target, (50, 50, 50), (bx, by, bw, bh))
            ratio = self.level.boss.health / self.level.boss.max_health if self.level.boss.max_health > 0 else 0
            pygame.draw.rect(target, (220, 90, 160), (bx, by, int(bw * ratio), bh))
            t = self.font.render("BOSS", True, (230, 230, 230))
            target.blit(t, (bx, by + 18))
            
        if hasattr(self.player.weapon, "shots_left"):
            shots = self.player.weapon.shots_left
            txt = self.font.render(f"SHOTGUN: {shots} shots left", True, (255, 200, 50))
            target.blit(txt, (20, 60))

    def draw_center_text(self, text: str, y: int, big: bool = False, target: pygame.Surface | None = None) -> None:
        if target is None:
            target = self.window
        f = self.big_font if big else self.font
        surf = f.render(text, True, (240, 240, 240))
        rect = surf.get_rect(center=(settings.WINDOW_WIDTH // 2, y))
        target.blit(surf, rect)

    def draw_overlay(self, target: pygame.Surface | None = None) -> None:
        if target is None:
            target = self.window
        overlay = pygame.Surface((settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        target.blit(overlay, (0, 0))