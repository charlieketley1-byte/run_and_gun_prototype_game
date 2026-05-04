# player.py
# Improved jump responsiveness:
# - Jump buffer
# - Coyote time
# - Variable jump height (short hop)

from __future__ import annotations
import pygame
from .utils import load_image, slice_sprite_sheet_row
from .weapon import Weapon
from .animation import Animation
from . import settings


class Player(pygame.sprite.Sprite):
    def __init__(self, pos: tuple[int, int]):
        super().__init__()
        
        # Sprite sheet: row 4 idle, row 3 run, row 5 jump
        
        sheet = load_image("player_sheet.png")
        self.anim_idle = slice_sprite_sheet_row(sheet, row=4, frame_w=32, frame_h=32, num_frames=6, stride_x=32, start_x=0, start_y=0, clamp=True)
        self.anim_run  = slice_sprite_sheet_row(sheet, row=3, frame_w=32, frame_h=32, num_frames=8, stride_x=32, start_x=0, start_y=0, clamp=True)
        self.anim_jump = slice_sprite_sheet_row(sheet, row=5, frame_w=32, frame_h=32, num_frames=8, stride_x=32, start_x=0, start_y=0, clamp=True)

        # If idle has only 1 frame, you will never see animation.
        # This warns early (common cause of "idle doesn't animate").
        if len(self.anim_idle) < 2:
            print("[WARN] anim_idle has <2 frames. Check slice_sprite_sheet_row row/count arguments.")

        self.image = self.anim_idle[0]
        self.rect = self.image.get_rect(topleft=pos)
        self.pos = pygame.Vector2(self.rect.topleft)  # float position
        
        # Physics
        self.vel = pygame.Vector2(0.0, 0.0)
        self.on_ground = False
        self.facing = 1

        # Jump feel improvements
        self.jump_buffer_time = 0.12
        self.jump_buffer = 0.0

        self.coyote_time = 0.10
        self.coyote_timer = 0.0

        # Combat
        self.weapon = Weapon()
        self.health = settings.PLAYER_MAX_HEALTH
        self.max_health = settings.PLAYER_MAX_HEALTH
        self.invuln_time = 0.0

        # Animation (SLOW + readable by default)
        # Increase frame_duration to slow down.
        self.idle_anim = Animation(self.anim_idle, frame_duration=0.15, loop=True)  # very readable
        self.run_anim  = Animation(self.anim_run,  frame_duration=0.20, loop=True)  # slowed run
        self.jump_anim = Animation(self.anim_jump, frame_duration=0.12, loop=True)

        self.current_anim = self.idle_anim

    # --------------------------
    # Health
    # --------------------------

    def heal(self, amount: int) -> None:
        self.health = min(self.max_health, self.health + amount)

    def take_damage(self, amount: int) -> None:
        if self.invuln_time > 0:
            return
        self.health -= amount
        self.invuln_time = 0.6
        if self.health < 0:
            self.health = 0

    def is_dead(self) -> bool:
        return self.health <= 0

    # --------------------------
    # Input
    # --------------------------

    def handle_input(self, keys: pygame.key.ScancodeWrapper) -> None:
        self.vel.x = 0.0

        self.moving = False
        if keys[pygame.K_a]:
            self.vel.x -= settings.PLAYER_SPEED
            self.facing = -1
            self.moving = True

        if keys[pygame.K_d]:
            self.vel.x += settings.PLAYER_SPEED
            self.facing = 1
            self.moving = True

    def queue_jump(self) -> None:
        """Called on key press. Stores jump for short time."""
        self.jump_buffer = self.jump_buffer_time

    def cut_jump(self) -> None:
        """Called on key release for variable jump height."""
        if self.vel.y < 0:
            self.vel.y *= 0.45

    def try_shoot(self, bullets_group: pygame.sprite.Group) -> bool:
        muzzle = pygame.Vector2(
            self.rect.centerx + 16 * self.facing,
            self.rect.centery + 4
        )
        before = len(bullets_group)
        self.weapon.shoot(bullets_group, muzzle, self.facing)
        return len(bullets_group) > before

    # --------------------------
    # Update
    # --------------------------

    def update(self, dt: float, level) -> None:
        # Timers
        if self.invuln_time > 0:
            self.invuln_time = max(0.0, self.invuln_time - dt)

        if self.jump_buffer > 0:
            self.jump_buffer = max(0.0, self.jump_buffer - dt)

        if self.coyote_timer > 0:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)

        self.weapon.update(dt)
        
        if hasattr(self.weapon, "shots_left") and self.weapon.shots_left <= 0:
            self.weapon = Weapon()

        # Gravity
        self.vel.y += settings.GRAVITY * dt

        # Horizontal movement (float)
        self.pos.x += self.vel.x * dt
        self.rect.x = round(self.pos.x)

        hits = level.get_solid_hits(self.rect)
        for tile_rect in hits:
            if self.vel.x > 0:
                self.rect.right = tile_rect.left
            elif self.vel.x < 0:
                self.rect.left = tile_rect.right
            self.pos.x = self.rect.x  # keep float in sync after collision

        # Vertical movement (float)
        self.pos.y += self.vel.y * dt
        self.rect.y = round(self.pos.y)

        self.on_ground = False
        hits = level.get_solid_hits(self.rect)
        for tile_rect in hits:
            if self.vel.y > 0:
                self.rect.bottom = tile_rect.top
                self.vel.y = 0
                self.on_ground = True
            elif self.vel.y < 0:
                self.rect.top = tile_rect.bottom
                self.vel.y = 0

            self.pos.y = self.rect.y  # keep float in sync after collision

        # --- Ground probe (stabilises grounding when perfectly still) ---
        if not self.on_ground:
            probe = self.rect.move(0, 1)
            if level.get_solid_hits(probe):
                self.on_ground = True

        # Coyote time reset
        if self.on_ground:
            self.coyote_timer = self.coyote_time

        # Buffered jump
        can_jump = self.on_ground or self.coyote_timer > 0.0
        if self.jump_buffer > 0 and can_jump:
            self.vel.y = -settings.JUMP_SPEED
            self.on_ground = False
            self.coyote_timer = 0.0
            self.jump_buffer = 0.0

        # Animation selection
        if not self.on_ground:
            self.set_anim(self.jump_anim, dt)
        elif self.moving:
            self.set_anim(self.run_anim, dt)
        else:
            self.set_anim(self.idle_anim, dt)

    # --------------------------
    # Animation helper
    # --------------------------

    def set_anim(self, anim: Animation, dt: float, speed: float = 1.0) -> None:
        # Only reset when the animation OBJECT changes
        if self.current_anim is not anim:
            self.current_anim = anim
            self.current_anim.reset()
            

        self.current_anim.update(dt, speed=speed)

        img = self.current_anim.image
        if self.facing == -1:
            img = pygame.transform.flip(img, True, False)
        self.image = img