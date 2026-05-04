# level.py
# Two-digit tile IDs + multi-tile tilesheet support.
#
# CSV cells can be: 00, 01, 02, ...
# We parse them as ints, so "01" becomes 1, etc.
#
# Tilesheet layout: a grid of tiles, each TILE_SIZE x TILE_SIZE.
# Tile ID -> picks a tile image from the sheet (via a mapping).

from __future__ import annotations
import csv
import pygame
from .utils import asset_path, load_image
from . import settings
from .enemies import NormalEnemy, ShooterEnemy, BossEnemy
from .pickup import PickUp


class Level:
    # --- Tile IDs (two-digit in CSV, but int in code) ---
    EMPTY = 0

    # Example “visual/collision” tiles
    SOLID_01 = 1
    SOLID_02 = 2
    SOLID_03 = 3
    SOLID_04 = 4
    SOLID_05 = 5

    # Example “spawn” tiles (not drawn, not solid)
    PLAYER_SPAWN = 90
    ENEMY_SPAWN  = 91
    PICKUP_HEALTH = 92
    BOSS_SPAWN   = 93
    EXIT_FLAG    = 94
    SHOOTER_ENEMY_SPAWN = 95
    SHOTGUN_PICKUP = 96

    def __init__(self, csv_name: str):
        self.csv_name = csv_name

        # Load tilesheet
        self.tilesheet = load_image("tileset.png")

        # Slice the tilesheet into individual tile images
        self.tiles = self.slice_tilesheet(self.tilesheet, settings.TILE_SIZE)

        # Decide which tile IDs are solid (collidable)
        self.solid_ids = {self.SOLID_01, self.SOLID_02, self.SOLID_03, self.SOLID_05}

        # Decide which tile IDs should be drawn as tiles (usually same as “visual tiles”)
        # Note: spawn IDs are typically NOT drawn.
        self.draw_ids = {self.SOLID_01, self.SOLID_02, self.SOLID_03, self.SOLID_04, self.SOLID_05}

        # Map “tile ID in the level” -> “index into tilesheet”
        #
        # tilesheet indices are 0..N-1 in left-to-right, top-to-bottom order.
        # Example: if tileset.png is 8 tiles wide:
        #   index 0 = (0,0), index 1 = (1,0), ...
        #
        # Here, we map tile ID 01 -> tilesheet index 0, tile ID 02 -> index 1, etc.
        self.tile_id_to_sheet_index = {
            self.SOLID_01: 83,
            self.SOLID_02: 88,
            self.SOLID_03: 89,
            self.SOLID_04: 74,
            self.SOLID_05: 98,
        }

        self.grid: list[list[int]] = []
        self.solid_rects: list[pygame.Rect] = []

        # Spawned content
        self.player_spawn = (0, 0)
        self.exit_rect: pygame.Rect | None = None
        self.enemies = pygame.sprite.Group()
        self.pickups = pygame.sprite.Group()
        self.boss: BossEnemy | None = None

        self.width = 0
        self.height = 0
        self.pixel_width = 0
        self.pixel_height = 0

        self.load_csv(csv_name)

    @staticmethod
    def slice_tilesheet(sheet: pygame.Surface, tile_size: int) -> list[pygame.Surface]:
        """Cut a tilesheet image into a list of TILE_SIZE x TILE_SIZE surfaces."""
        sheet_w, sheet_h = sheet.get_size()
        cols = sheet_w // tile_size
        rows = sheet_h // tile_size
        
        
        tiles: list[pygame.Surface] = []
        for y in range(rows):
            for x in range(cols):
                r = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
                tiles.append(sheet.subsurface(r))
        return tiles

    def load_csv(self, csv_name: str) -> None:
        path = asset_path("levels", csv_name)
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            self.grid = [[int(cell.strip()) for cell in row] for row in reader]

        self.height = len(self.grid)
        self.width = len(self.grid[0]) if self.height else 0
        self.pixel_width = self.width * settings.TILE_SIZE
        self.pixel_height = self.height * settings.TILE_SIZE

        # Reset everything
        self.solid_rects.clear()
        self.enemies.empty()
        self.pickups.empty()
        self.boss = None
        self.exit_rect = None

        tile_size = settings.TILE_SIZE

        for gy in range(self.height):
            for gx in range(self.width):
                tile_id = self.grid[gy][gx]

                world_x = gx * tile_size
                world_y = gy * tile_size

                # ------------------------
                # SOLID TILES (collision)
                # ------------------------
                if tile_id in self.solid_ids:
                    self.solid_rects.append(
                        pygame.Rect(world_x, world_y, tile_size, tile_size)
                    )

                # ------------------------
                # PLAYER SPAWN
                # ------------------------
                elif tile_id == self.PLAYER_SPAWN:
                    # Player sprite is 32x32
                    player_height = 32
                    spawn_y = world_y - (player_height - tile_size)
                    self.player_spawn = (world_x, spawn_y)

                # ------------------------
                # NORMAL ENEMY SPAWN
                # ------------------------
                elif tile_id == self.ENEMY_SPAWN:
                    enemy_height = 32
                    spawn_y = world_y - (enemy_height - tile_size)
                    self.enemies.add(NormalEnemy((world_x, spawn_y)))

                # ------------------------
                # PICKUP SPAWN
                # ------------------------
                elif tile_id == self.PICKUP_HEALTH:
                    pickup_height = 32
                    spawn_y = world_y - (pickup_height - tile_size)
                    self.pickups.add(PickUp((world_x, spawn_y), kind="health"))
                
                #-------------------------
                #SHOTGUN PICKUP
                #-------------------------
                elif tile_id == self.SHOTGUN_PICKUP:
                    print("SHOTGUN SPAWNED AT", world_x, world_y)
                    pickup_height = 32
                    spawn_y = world_y - (pickup_height - tile_size)
                    self.pickups.add(PickUp((world_x, spawn_y), kind="shotgun"))

                # ------------------------
                # BOSS SPAWN (64x64 sprite)
                # ------------------------
                elif tile_id == self.BOSS_SPAWN:
                    boss_height = 64
                    spawn_y = world_y - (boss_height - tile_size)
                    self.boss = BossEnemy((world_x, spawn_y))

                # ------------------------
                # EXIT FLAG
                # ------------------------
                elif tile_id == self.EXIT_FLAG:
                    self.exit_rect = pygame.Rect(
                        world_x,
                        world_y - tile_size,
                        tile_size,
                        tile_size
                    )
                elif tile_id == self.SHOOTER_ENEMY_SPAWN:
                    enemy_height = 32
                    spawn_y = world_y - (enemy_height - tile_size)
                    self.enemies.add(ShooterEnemy((world_x, spawn_y)))

    def get_solid_hits(self, rect: pygame.Rect) -> list[pygame.Rect]:
        return [r for r in self.solid_rects if r.colliderect(rect)]

    def rect_collides_solid(self, rect: pygame.Rect) -> bool:
        return any(r.colliderect(rect) for r in self.solid_rects)

    def update(self, dt: float, player, bullets, boss_bullets, enemy_bullets) -> None:
        for e in list(self.enemies):
            # Shooter enemies expect enemy_bullets
            if hasattr(e, "weapon"):
                e.update(dt, self, player, enemy_bullets)
            else:
                e.update(dt, self, player)

        if self.boss and self.boss.alive():
            self.boss.update(dt, self, player, boss_bullets)

        for p in list(self.pickups):
            p.update(dt)

        # Bullet hits
        for b in list(bullets):
            hit_enemy = pygame.sprite.spritecollideany(b, self.enemies)
            if hit_enemy:
                hit_enemy.take_damage(15)
                b.kill()
                continue

            if self.boss and self.boss.alive() and b.rect.colliderect(self.boss.rect):
                self.boss.take_damage(12)
                b.kill()

    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        # Draw tiles by reading the grid (so you can have multiple visual tiles)
        # Simple version: draw everything in draw_ids.
        for gy in range(self.height):
            for gx in range(self.width):
                tile_id = self.grid[gy][gx]
                if tile_id not in self.draw_ids:
                    continue

                sheet_index = self.tile_id_to_sheet_index.get(tile_id, None)
                if sheet_index is None or sheet_index >= len(self.tiles):
                    continue  # unknown tile id or tilesheet too small

                img = self.tiles[sheet_index]
                x = gx * settings.TILE_SIZE - camera_x
                y = gy * settings.TILE_SIZE - camera_y
                surface.blit(img, (x, y))

        # Exit flag (draw a simple outline for now)
        if self.exit_rect:
            pygame.draw.rect(
                surface,
                (80, 240, 180),
                (self.exit_rect.x - camera_x, self.exit_rect.y - camera_y, self.exit_rect.w, self.exit_rect.h),
                2,
            )
            
