import math
from dataclasses import dataclass, field

FOV = math.pi / 3
MOVE_SPEED = 0.08
TURN_SPEED = 0.06
ATTACK_RANGE = 1.5
ATTACK_FOV = math.pi / 4
MONSTER_MOVE_INTERVAL = 25  # frames between monster moves
MONSTER_ATTACK_RANGE = 0.8


@dataclass
class Player:
    x: float
    y: float
    angle: float = 0.0
    hp: int = 100
    max_hp: int = 100
    attack: int = 25


@dataclass
class Monster:
    x: float
    y: float
    hp: int = 40
    max_hp: int = 40
    attack: int = 12
    alive: bool = True


@dataclass
class Treasure:
    x: float
    y: float
    collected: bool = False
    value: int = 200
