#!/usr/bin/env python3
import sys
import time
import argparse
from pathlib import Path

from game import load_map, GameState, update, elapsed, calc_score
from renderer import setup_terminal, restore_terminal, get_input, render_frame
from hiscore import load_scores, save_score, format_scores

LEVELS = ['maps/level1.txt', 'maps/level2.txt', 'maps/level3.txt']

TITLE_LINES = [
    '',
    '  ╔══════════════════════════════════════════╗',
    '  ║                                          ║',
    '  ║   ██████  ██  ██ ███  ██  ██  ████  ██  ║',
    '  ║   ██  ██  ██  ██  ██  ███ ██ ██  ██ ███ ║',
    '  ║   ██  ██  ██  ██  ██  ██████ ██  ██ ████║',
    '  ║   ██████  ██████  ██  ██  ██  ████  ████║',
    '  ║                                          ║',
    '  ║         C R A W L E R                   ║',
    '  ║                                          ║',
    '  ╚══════════════════════════════════════════╝',
    '',
    '  Ziel: Alle Monster töten ODER alle Schätze',
    '  sammeln — so schnell wie möglich!',
    '',
    '  Steuerung: W/S=Laufen  A/D=Drehen',
    '             E=Angriff   M=Karte  Q=Beenden',
    '',
    '  ─────────────────────────────────────────',
    '         Drücke eine Taste zum Starten',
]


def _draw_screen(lines, W, H):
    buf = [' '] * (W * H)
    start = max(0, H // 2 - len(lines) // 2)
    for i, line in enumerate(lines):
        row = start + i
        if row >= H:
            break
        col = max(0, (W - len(line)) // 2)
        for ci, ch in enumerate(line[:W - col]):
            buf[row * W + col + ci] = ch
    sys.stdout.write('\033[H' + '\r\n'.join(
        ''.join(buf[r * W:(r + 1) * W]) for r in range(H)
    ))
    sys.stdout.flush()


def _wait_key():
    while True:
        key = get_input()
        if key and key != '\x00':
            return key
        time.sleep(0.05)


def run_level(level_num, map_path, W, H):
    grid, player, monsters, treasures, meta = load_map(map_path)
    state = GameState(
        grid=grid,
        player=player,
        monsters=monsters,
        treasures=treasures,
        timer_start=time.time(),
        level=level_num,
        level_name=meta.get('NAME', f'Level {level_num}'),
    )
    show_map = False

    while True:
        key = get_input()

        if key in ('q', '\x03'):
            return None, state

        if key == 'm':
            show_map = not show_map

        if not (state.game_over or state.won):
            state = update(state, key)

        render_frame(state, W, H, show_map=show_map)

        if state.game_over or state.won:
            time.sleep(0.6)
            _wait_key()
            break

        time.sleep(0.033)

    return calc_score(state) if state.won else 0, state


def show_title(W, H):
    _draw_screen(TITLE_LINES, W, H)
    _wait_key()


def show_hiscores(W, H, scores):
    lines = [
        '',
        '  ╔══════════════════════════════════════════════════════╗',
        '  ║             H I G H S C O R E S                     ║',
        '  ╠══════════════════════════════════════════════════════╣',
    ] + ['  ║' + ln.ljust(54) + '║' for ln in format_scores(scores)] + [
        '  ╚══════════════════════════════════════════════════════╝',
        '',
        '        Drücke eine Taste...',
    ]
    _draw_screen(lines, W, H)
    _wait_key()


def show_level_result(W, H, level_num, score, total, state):
    secs = elapsed(state)
    mm, ss = divmod(int(secs), 60)
    killed = sum(1 for m in state.monsters if not m.alive)
    found = sum(1 for t in state.treasures if t.collected)
    lines = [
        '',
        f'  ★  LEVEL {level_num}: {state.level_name}  ★',
        '',
        f'  Zeit:                {mm:02d}:{ss:02d}',
        f'  Monster getötet:     {killed}/{len(state.monsters)}',
        f'  Schätze gefunden:    {found}/{len(state.treasures)}',
        '',
        f'  Level-Score:         {score}',
        f'  Gesamt-Score:        {total}',
        '',
        '     Drücke eine Taste für das nächste Level...',
    ]
    _draw_screen(lines, W, H)
    _wait_key()


def show_game_over(W, H):
    _draw_screen([
        '', '',
        '  ╔════════════════════════════════╗',
        '  ║       G A M E   O V E R        ║',
        '  ║                                ║',
        '  ║    Du bist gestorben...        ║',
        '  ║    Dein Score wird gespeichert ║',
        '  ╚════════════════════════════════╝',
        '', '       Drücke eine Taste...',
    ], W, H)
    _wait_key()


def show_victory(W, H, total, levels, monsters, treasures):
    lines = [
        '',
        '  ╔══════════════════════════════════════╗',
        '  ║  ★  D U N G E O N   B E S I E G T  ★║',
        '  ╚══════════════════════════════════════╝',
        '',
        f'  Gesamt-Score:   {total}',
        f'  Abgeschlossene Levels: {levels}/{len(LEVELS)}',
        f'  Monster getötet:       {monsters}',
        f'  Schätze gefunden:      {treasures}',
        '',
        '       Drücke eine Taste...',
    ]
    _draw_screen(lines, W, H)
    _wait_key()


def main():
    parser = argparse.ArgumentParser(description='Dungeon Crawler')
    parser.add_argument('--level', type=int, default=1,
                        help='Starte bei Level (1-3)')
    args = parser.parse_args()
    start = max(1, min(args.level, len(LEVELS))) - 1

    W, H, fd, old = setup_terminal()
    terminal_alive = True

    try:
        show_title(W, H)

        scores = load_scores()
        if scores:
            show_hiscores(W, H, scores)

        total_score = 0
        total_time = 0.0
        total_monsters = 0
        total_treasures = 0
        completed = 0
        aborted = False

        for i, rel_path in enumerate(LEVELS[start:]):
            level_num = start + i + 1
            map_path = Path(__file__).parent / rel_path
            if not map_path.exists():
                continue

            level_score, state = run_level(level_num, str(map_path), W, H)

            if level_score is None:
                aborted = True
                break

            if state.game_over:
                show_game_over(W, H)
                aborted = True
                break

            total_score += level_score
            total_time += elapsed(state)
            total_monsters += sum(1 for m in state.monsters if not m.alive)
            total_treasures += sum(1 for t in state.treasures if t.collected)
            completed += 1

            remaining = LEVELS[start + i + 1:]
            if remaining:
                show_level_result(W, H, level_num, level_score, total_score, state)

        if not aborted and completed > 0:
            show_victory(W, H, total_score, completed, total_monsters, total_treasures)

        terminal_alive = False
        restore_terminal(fd, old)

        if completed > 0 or aborted:
            print(f'\n  Dein Name für die Highscore-Liste (max 10 Zeichen):')
            try:
                name = input('  > ').strip()[:10] or 'SPIELER'
            except (EOFError, KeyboardInterrupt):
                name = 'SPIELER'

            scores = save_score(name, total_score, total_time,
                                total_monsters, total_treasures, completed)
            print('\n  ── Highscore-Liste ──')
            for line in format_scores(scores):
                print(line)
            print()

    except KeyboardInterrupt:
        pass
    finally:
        if terminal_alive:
            restore_terminal(fd, old)


if __name__ == '__main__':
    main()
