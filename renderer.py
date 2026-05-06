import math
import sys
import os
import select
import termios
import tty
from entities import (
    FOV, ATTACK_RANGE, ATTACK_FOV,
    Monster, Treasure,
)
from game import elapsed, calc_score

HUD_ROWS = 3


def _wall_char(dist, side):
    if dist < 1.5:
        return '█' if side == 0 else '▓'
    if dist < 3.0:
        return '▓' if side == 0 else '▒'
    if dist < 6.0:
        return '▒' if side == 0 else '░'
    if dist < 10.0:
        return '░' if side == 0 else '·'
    return '·' if side == 0 else ' '


def _ceil_char(frac):
    if frac < 0.4:
        return ' '
    if frac < 0.75:
        return '·'
    return '░'


def _floor_char(frac):
    if frac < 0.25:
        return '░'
    if frac < 0.6:
        return ','
    return '.'


def cast_rays(grid, player, W, view_h):
    z_buf = [1e30] * W
    wall_segs = []

    for col in range(W):
        t = col / max(W - 1, 1)
        ray_angle = player.angle - FOV / 2 + t * FOV
        rdx = math.cos(ray_angle)
        rdy = math.sin(ray_angle)

        mx = int(player.x)
        my = int(player.y)

        ddx = abs(1.0 / rdx) if abs(rdx) > 1e-10 else 1e30
        ddy = abs(1.0 / rdy) if abs(rdy) > 1e-10 else 1e30

        if rdx < 0:
            step_x, sdx = -1, (player.x - mx) * ddx
        else:
            step_x, sdx = 1, (mx + 1.0 - player.x) * ddx

        if rdy < 0:
            step_y, sdy = -1, (player.y - my) * ddy
        else:
            step_y, sdy = 1, (my + 1.0 - player.y) * ddy

        hit_side = 0
        for _ in range(128):
            if sdx < sdy:
                sdx += ddx
                mx += step_x
                hit_side = 0
            else:
                sdy += ddy
                my += step_y
                hit_side = 1

            if my < 0 or my >= len(grid) or mx < 0 or mx >= len(grid[my]):
                break
            if grid[my][mx] == '#':
                break

        if hit_side == 0 and abs(rdx) > 1e-10:
            dist = (mx - player.x + (1 - step_x) / 2) / rdx
        elif hit_side == 1 and abs(rdy) > 1e-10:
            dist = (my - player.y + (1 - step_y) / 2) / rdy
        else:
            dist = 1e30

        dist = max(0.01, dist)
        z_buf[col] = dist

        wh = min(view_h, int(view_h / dist))
        ds = max(0, view_h // 2 - wh // 2)
        de = min(view_h - 1, view_h // 2 + wh // 2)
        wall_segs.append((ds, de, _wall_char(dist, hit_side)))

    return z_buf, wall_segs


def _sprite_label(entity, dist):
    if isinstance(entity, Monster):
        wounded = entity.hp < entity.max_hp // 2
        if dist < 2.0:
            return '(O!)' if wounded else '(O) '
        if dist < 5.0:
            return '[!]' if wounded else '[M]'
        return 'M'
    else:
        return '[T]' if dist < 4.0 else 'T'


def _angle_to_entity(player, entity):
    dx = entity.x - player.x
    dy = entity.y - player.y
    raw = math.atan2(dy, dx) - player.angle
    while raw > math.pi:
        raw -= 2 * math.pi
    while raw < -math.pi:
        raw += 2 * math.pi
    return raw


def render_sprites(buf, state, z_buf, W, view_h):
    p = state.player
    entities = (
        [m for m in state.monsters if m.alive] +
        [t for t in state.treasures if not t.collected]
    )
    entities.sort(
        key=lambda e: (e.x - p.x) ** 2 + (e.y - p.y) ** 2,
        reverse=True,
    )

    for ent in entities:
        dx = ent.x - p.x
        dy = ent.y - p.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.2:
            continue

        angle = _angle_to_entity(p, ent)
        if abs(angle) > FOV / 2 + 0.2:
            continue

        screen_x = int(W / 2 + (angle / (FOV / 2)) * (W / 2))
        label = _sprite_label(ent, dist)
        lw = len(label)
        sx_start = screen_x - lw // 2
        sx_end = sx_start + lw - 1

        sprite_h = max(1, int(view_h / dist))
        mid_y = view_h // 2

        for ci, ch in enumerate(label):
            sx = sx_start + ci
            if 0 <= sx < W and 0 <= mid_y < view_h and dist < z_buf[sx]:
                buf[mid_y * W + sx] = ch


def _hp_bar(hp, max_hp, width=10):
    filled = max(0, min(width, int(hp / max_hp * width)))
    return '█' * filled + '░' * (width - filled)


def _monster_near(state):
    p = state.player
    for m in state.monsters:
        if not m.alive:
            continue
        dx, dy = m.x - p.x, m.y - p.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > ATTACK_RANGE:
            continue
        ang = abs(_angle_to_entity(p, m))
        if ang < ATTACK_FOV:
            return True
    return False


def render_frame(state, W, H, show_map=False):
    buf = [' '] * (W * H)
    view_h = H - HUD_ROWS

    horizon = view_h // 2
    for row in range(view_h):
        if row < horizon:
            frac = row / max(horizon - 1, 1)
            ch = _ceil_char(frac)
        else:
            frac = (row - horizon) / max(view_h - horizon - 1, 1)
            ch = _floor_char(frac)
        for col in range(W):
            buf[row * W + col] = ch

    z_buf, wall_segs = cast_rays(state.grid, state.player, W, view_h)
    for col, (ds, de, ch) in enumerate(wall_segs):
        for row in range(ds, de + 1):
            buf[row * W + col] = ch

    render_sprites(buf, state, z_buf, W, view_h)

    if show_map:
        _draw_minimap(buf, state, W, view_h)

    # HUD separator
    sep_row = view_h
    for ci in range(W):
        buf[sep_row * W + ci] = '─'

    # HUD row 1: stats
    secs = elapsed(state)
    m_time, s_time = divmod(int(secs), 60)
    time_str = f'{m_time:02d}:{s_time:02d}'
    m_alive = sum(1 for m in state.monsters if m.alive)
    t_left = sum(1 for t in state.treasures if not t.collected)
    hud1 = (f' HP:{_hp_bar(state.player.hp, state.player.max_hp)}'
            f'  Zeit:{time_str}  Lv{state.level}:{state.level_name}'
            f'  Monster:{m_alive}  Schätze:{t_left} ')
    for ci, ch in enumerate(hud1[:W]):
        buf[(sep_row + 1) * W + ci] = ch

    # HUD row 2: contextual message
    if state.game_over:
        msg = '★  GAME OVER — Du bist gestorben!  Drücke eine Taste...'
    elif state.won:
        score = calc_score(state)
        msg = f'★  LEVEL GESCHAFFT!  Score: {score}  Drücke eine Taste...'
    elif state.hit_flash > 0:
        msg = '!!! TREFFER — du wurdest angegriffen !!!'
    elif state.attack_flash > 0:
        msg = '>>> ANGRIFF! <<<"'
    elif state.message and state.message_frames > 0:
        msg = state.message
    elif _monster_near(state):
        msg = '[ E / Leertaste ] Monster angreifen!'
    else:
        msg = ' W/S=Laufen  A/D=Drehen  E=Angriff  M=Karte  Q=Beenden'

    offset = max(0, (W - len(msg)) // 2)
    for ci, ch in enumerate(msg[:W - offset]):
        buf[(sep_row + 2) * W + offset + ci] = ch

    sys.stdout.write('\033[H' + '\r\n'.join(
        ''.join(buf[r * W:(r + 1) * W]) for r in range(H)
    ))
    sys.stdout.flush()


def _draw_minimap(buf, state, W, view_h):
    p = state.player
    mw, mh = 23, 12
    ox = W - mw - 1
    oy = 1
    cx, cy = int(p.x), int(p.y)

    for my in range(mh):
        for mx in range(mw):
            gx = cx - mw // 2 + mx
            gy = cy - mh // 2 + my
            sx = ox + mx
            sy = oy + my
            if not (0 <= sy < view_h and 0 <= sx < W):
                continue
            if gy < 0 or gy >= len(state.grid) or gx < 0 or gx >= len(state.grid[gy]):
                ch = ' '
            elif gx == cx and gy == cy:
                ch = '@'
            elif state.grid[gy][gx] == '#':
                ch = '█'
            else:
                ch = '·'
                for m in state.monsters:
                    if m.alive and int(m.x) == gx and int(m.y) == gy:
                        ch = 'm'
                        break
                for t in state.treasures:
                    if not t.collected and int(t.x) == gx and int(t.y) == gy:
                        ch = '$'
                        break
            buf[sy * W + sx] = ch


def setup_terminal():
    try:
        cols, rows = os.get_terminal_size()
    except OSError:
        cols, rows = 80, 24
    W = min(cols, 120)
    H = min(rows - 1, 40)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    sys.stdout.write('\033[?25l\033[2J')
    return W, H, fd, old


def restore_terminal(fd, old):
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.stdout.write('\033[?25h\033[H\033[2J')


def get_input():
    if select.select([sys.stdin], [], [], 0)[0]:
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            if select.select([sys.stdin], [], [], 0.01)[0]:
                seq = sys.stdin.read(2)
                if seq == '[A':
                    return 'w'
                if seq == '[B':
                    return 's'
                if seq == '[C':
                    return 'd'
                if seq == '[D':
                    return 'a'
            return None
        return ch.lower()
    return None
