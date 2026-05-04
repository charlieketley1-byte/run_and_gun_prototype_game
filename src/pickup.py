# pickup.py
# Pickups/Powerups. Add more types by extending PickUp and overriding apply().

from __future__ import annotations
import pygame
from .utils import load_image, slice_sprite_sheet_row
from .animation import Animation
from .shotgun import Shotgun


class PickUp(pygame.sprite.Sprite):
    def __init__(self, pos: tuple[int, int], kind: str = "health"):
        super().__init__()
        self.kind = kind
        
        if self.kind == "shotgun":
            self.image = load_image("shotgun.png")
            self.image = pygame.transform.scale(self.image, (64, 64))
            self.rect = self.image.get_rect(topleft=pos)
            self.anim = None
            
        else:

            sheet = load_image("pickup_sheet.png")

            # If your sheet uses gaps/padding, keep using your stride_x version.
            # (Your current call already uses stride_x/clamp=True.)
            self.frames = slice_sprite_sheet_row(
                sheet,
                row=0,
                frame_w=32,
                frame_h=32,
                num_frames=8,        # request “up to” (clamp=True will stop safely)
                stride_x=32,         # change to 64 if you have 32px blanks between frames
                start_x=0,
                start_y=0,
                clamp=True
            )

            if len(self.frames) == 0:
                raise ValueError("pickup_sheet.png: no frames were sliced (check row/stride/frame size).")

        # Animation (tweak duration for how “sparkly” it feels)
            self.anim = Animation(self.frames, frame_duration=0.20, loop=True)

            self.image = self.anim.image
            self.rect = self.image.get_rect(topleft=pos)

    def apply(self, player) -> None:
        print("PICKED UP:", self.kind)
        """What happens when the player collects this pickup."""
        if self.kind == "health":
            player.heal(25)
        elif self.kind == "shotgun":
            player.weapon = Shotgun()

    def update(self, dt: float, *_args) -> None:
        if self.anim:
            self.anim.update(dt)
            self.image = self.anim.image