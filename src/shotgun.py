from __future__ import annotations
import pygame
from .weapon import Bullet

class Shotgun:
    def __init__(self):
        self.cooldown = 0.6
        self.time_since_shot = 999.0
        self.pellets = 5
        self.spread = 120
        self.shots_left = 3
        
    def update(self,dt):
            self.time_since_shot += dt
            
    def shoot(self, bullets_group, pos, direction):
        if self.shots_left <= 0:
            return     
        if  self.time_since_shot < self.cooldown:
            return
        
        self.time_since_shot = 0
        self.shots_left -=1
        
        for i in range(self.pellets):
            bullet = Bullet(pos, direction)
            bullet.vel.y = (i - 2) * self.spread
            
            bullets_group.add(bullet)
        
