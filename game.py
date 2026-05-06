import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from entities import (
    Player, Monster, Treasure,
    FOV, MOVE_SPEED, TURN_SPEED, ATTACK_RANGE, ATTACK_FOV,
    MONSTER_MOVE_INTERVAL, MONSTER_ATTACK_RANGE,
)


@dataclass
class GameState:
    grid: list
    player: Player
    monsters: list
    treasures: list
    timer_start: float
    level: int = 1
    level_name: str = ""
    timer_stopped: bool = False
    timer_end: float = 0.0
    frame: int = 0
    attack_flash: int = 0      # frames to show attack indicator
    hit_flash: int = 0         # frames to show damage flash
    message: str = ""
    message_frames: int = 0
    game_over: bool = False
    won: bool = False


def load_map(path):
    lines = Path(path).read_text().splitlines()
    meta = {}
    grid_lines = []
    for line in lines:
        if line.startswith(';'):
            k, _, v = line[1:].partition(':')
            meta[k.strip()] = v.strip()
        else:
            grid_lines.append(line)

    monsters = []
    treasures = []
    player_start = None
    clean_grid = []

    for row, line in enumerate(grid_lines):
        clean_row = ""
        for col, ch in enumerate(line):
            if ch == 'P':
                player_start = (col + 0.5, row + 0.5)
                clean_row += '.'
            elif ch == 'M':
                monsters.append(Monster(x=col + 0.5, y=row + 0.5))
                clean_row += '.'
            elif ch == 'T':
                treasures.append(Treasure(x=col + 0.5, y=row + 0.5))
                clean_row += '.'
            else:
                clean_row += ch
        clean_grid.append(clean_row)

    if player_start is None:
        player_start = (1.5, 1.5)

    player = Player(x=player_start[0], y=player_start[1], angle=0.0)
    return clean_grid, player, monsters, treasures, meta


def is_wall(grid, x, y):
    col, row = int(x), int(y)
    if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[row]):
        return True
    return grid[row][col] == '#'


def _try_move(grid, px, py, dx, dy):
    margin = 0.25
    nx, ny = px + dx, py + dy
    if not is_wall(grid, nx + margin * (1 if dx > 0 else -1), py):
        px = nx
    if not is_wall(grid, px, ny + margin * (1 if dy > 0 else -1)):
        py = ny
    return px, py


def _angle_diff(a, b):
    d = (a - b) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return abs(d)


def _monster_in_attack_range(player, monster):
    dx = monster.x - player.x
    dy = monster.y - player.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist > ATTACK_RANGE:
        return False
    target_angle = math.atan2(dy, dx)
    return _angle_diff(player.angle, target_angle) < ATTACK_FOV


def _move_monster_toward_player(grid, monster, player):
    dx = player.x - monster.x
    dy = player.y - monster.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 0.1:
        return
    step = 0.5
    nx = monster.x + (dx / dist) * step
    ny = monster.y + (dy / dist) * step
    if not is_wall(grid, nx, monster.y):
        monster.x = nx
    if not is_wall(grid, monster.x, ny):
        monster.y = ny


def elapsed(state):
    if state.timer_stopped:
        return state.timer_end - state.timer_start
    return time.time() - state.timer_start


def calc_score(state):
    secs = elapsed(state)
    monsters_killed = sum(1 for m in state.monsters if not m.alive)
    treasures_found = sum(1 for t in state.treasures if t.collected)
    score = 5000 - int(secs * 8) + monsters_killed * 300 + treasures_found * 200
    return max(0, score)


def update(state, key):
    if state.game_over or state.won:
        return state

    p = state.player
    state.frame += 1

    if state.attack_flash > 0:
        state.attack_flash -= 1
    if state.hit_flash > 0:
        state.hit_flash -= 1
    if state.message_frames > 0:
        state.message_frames -= 1
        if state.message_frames == 0:
            state.message = ""

    if key == 'w':
        dx = math.cos(p.angle) * MOVE_SPEED
        dy = math.sin(p.angle) * MOVE_SPEED
        p.x, p.y = _try_move(state.grid, p.x, p.y, dx, dy)
    elif key == 's':
        dx = -math.cos(p.angle) * MOVE_SPEED
        dy = -math.sin(p.angle) * MOVE_SPEED
        p.x, p.y = _try_move(state.grid, p.x, p.y, dx, dy)
    elif key == 'a':
        p.angle -= TURN_SPEED
    elif key == 'd':
        p.angle += TURN_SPEED
    elif key in ('e', ' '):
        for m in state.monsters:
            if m.alive and _monster_in_attack_range(p, m):
                m.hp -= p.attack
                state.attack_flash = 8
                if m.hp <= 0:
                    m.alive = False
                    state.message = "Monster getötet!"
                    state.message_frames = 60
                break

    # treasure pickup
    for t in state.treasures:
        if not t.collected:
            dx, dy = t.x - p.x, t.y - p.y
            if math.sqrt(dx * dx + dy * dy) < 0.6:
                t.collected = True
                state.message = f"Schatz gefunden! +{t.value}"
                state.message_frames = 60

    # monster AI + counter-attack
    if state.frame % MONSTER_MOVE_INTERVAL == 0:
        for m in state.monsters:
            if not m.alive:
                continue
            _move_monster_toward_player(state.grid, m, p)
            dx, dy = m.x - p.x, m.y - p.y
            if math.sqrt(dx * dx + dy * dy) < MONSTER_ATTACK_RANGE:
                p.hp -= m.attack
                state.hit_flash = 10
                if p.hp <= 0:
                    p.hp = 0
                    state.game_over = True
                    return state

    # win condition
    if not state.timer_stopped:
        all_dead = bool(state.monsters) and all(not m.alive for m in state.monsters)
        all_collected = bool(state.treasures) and all(t.collected for t in state.treasures)
        if all_dead or all_collected:
            state.timer_stopped = True
            state.timer_end = time.time()
            state.won = True

    p.angle %= 2 * math.pi
    return state
