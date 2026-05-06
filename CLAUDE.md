# CLAUDE.md

Dokumentation für Claude Code beim Arbeiten in diesem Repository.

## Starten

```bash
python3 dungeon.py              # Kampagne ab Level 1
python3 dungeon.py --level 2    # Direkt ab Level 2
```

Keine externen Abhängigkeiten — ausschließlich Python-Stdlib (`math`, `time`, `sys`, `os`, `select`, `termios`, `tty`, `json`, `pathlib`, `dataclasses`).

## Architektur

Fünf Module mit klarer Aufgabentrennung:

```
dungeon.py    Kampagnen-Loop, Screens (Titel, Highscore, Level-Abschluss)
renderer.py   Raycaster, Framebuffer, Sprite-Rendering, HUD, Terminal-I/O
game.py       Spiellogik: update(), load_map(), Kampf, Monster-KI, Scoring
entities.py   Dataclasses (Player, Monster, Treasure) + Spielkonstanten
hiscore.py    JSON-Persistenz, Formatierung der Highscore-Tabelle
maps/         Dungeon-Karten als Textdateien (level1–3.txt)
hiscore.json  Persistent gespeicherte Top-10-Einträge (wird zur Laufzeit erzeugt)
```

## Rendering-Pipeline (`renderer.py`)

Exakt wie `cube.py` (Elternprojekt): Framebuffer als flaches `[' '] * (W * H)`-Array, einmaliger ANSI-Cursor-Reset (`\033[H`) pro Frame, Raw-Terminal-Modus via `termios`/`tty`.

Jeder Frame läuft in dieser Reihenfolge:

1. **Decke/Boden** — Jede Zeile im View-Bereich bekommt ein Shading-Zeichen nach Abstand zum Horizont: Decke `' '→'·'→'░'`, Boden `'░'→','→'.'`

2. **Raycasting — `cast_rays(grid, player, W, view_h)`** — DDA-Algorithmus (Digital Differential Analysis): für jede der `W` Spalten wird ein Strahl unter dem Winkel `player.angle ± FOV/2` geworfen. Perpendicular-Distanz (fisheye-frei):
   ```
   dist = (map_x - player.x + (1 - step_x) / 2) / rdx   # x-Seite
   dist = (map_y - player.y + (1 - step_y) / 2) / rdy   # y-Seite
   ```
   ASCII-Shading nach Distanz × Wandseite (x-Seite dunkler als y-Seite):

   | Distanz | x-Wand | y-Wand |
   |---------|--------|--------|
   | < 1.5   | `█`    | `▓`    |
   | < 3.0   | `▓`    | `▒`    |
   | < 6.0   | `▒`    | `░`    |
   | < 10.0  | `░`    | `·`    |
   | ≥ 10.0  | `·`    | ` `    |

   Rückgabe: `z_buf` (Perpendicular-Distanz pro Spalte) + `wall_segs` (start/end-Zeile + Zeichen pro Spalte).

3. **Sprites — `render_sprites(buf, state, z_buf, W, view_h)`** — Für jedes lebendige Monster / nicht eingesammelten Schatz:
   - Relativer Winkel zum Spieler: `atan2(dy, dx) - player.angle` (normiert auf `[-π, π]`)
   - Bildschirm-X: `W/2 + (angle / (FOV/2)) * W/2`
   - Sichtbarkeit: nur rendern wenn `dist < z_buf[col]` (Z-Buffer-Test)
   - Sprite-Label nach Distanz: `(O!)/(O)/[M]/M` für Monster, `[T]/T` für Schätze

4. **Mini-Map** (togglebar mit `M`) — 23×12 Ausschnitt zentriert auf Spieler, in die obere rechte Ecke des Framebuffers geschrieben: `@`=Spieler, `█`=Wand, `m`=Monster, `$`=Schatz, `·`=Boden

5. **HUD** — Unterste 3 Zeilen: Trennlinie (`─`), dann HP-Balken + Timer + Level + Monster/Schatz-Zähler, dann Kontext-Nachricht (Angriff-Prompt / Treffer-Flash / Spielermeldung / Steuerhilfe)

6. **Ausgabe** — Identisch `cube.py`:
   ```python
   sys.stdout.write('\033[H' + '\r\n'.join(
       ''.join(buf[r * W:(r + 1) * W]) for r in range(H)
   ))
   ```

## Spiellogik (`game.py`)

### GameState
Immutable-Style: `update(state, key) -> state`. Enthält Grid, Player, Monsters, Treasures, Timer, Frame-Counter, Flash-Zähler, Nachrichten, `game_over`/`won`-Flags.

### update()-Ablauf pro Frame
1. Flash-Zähler dekrementieren (`attack_flash`, `hit_flash`, `message_frames`)
2. Bewegung mit Kollisionsdetektion — `_try_move()` prüft jede Achse separat (Sliding-Methode) mit Margin 0.25
3. `E`/`Space` → Angriff: nächstes Monster in `ATTACK_RANGE=1.5` und `ATTACK_FOV=π/4` wird getroffen
4. Schatz-Aufnahme: automatisch bei Abstand < 0.6
5. Monster-KI alle `MONSTER_MOVE_INTERVAL=25` Frames: Schritt in Richtung Spieler (Richtungsvektor, achsenweise Kollision). Angriff wenn Abstand < `MONSTER_ATTACK_RANGE=0.8`
6. Win-Condition: `all monsters dead` **oder** `all treasures collected` → Timer stoppen, `won=True`

### Scoring
```python
score = max(0, 5000 - int(secs * 8) + monsters_killed * 300 + treasures_collected * 200)
```

## Map-Format (`maps/*.txt`)

```
;NAME: Anzeigename
;DESCRIPTION: Kurzbeschreibung
##########
#P...M..T#
##########
```

| Zeichen | Bedeutung |
|---------|-----------|
| `#`     | Wand (blockiert Bewegung und Strahlen) |
| `.`     | Freier Boden |
| `P`     | Spieler-Startposition (wird zu `.` im Grid) |
| `M`     | Monster-Spawn (wird zu `.`) |
| `T`     | Schatz-Spawn (wird zu `.`) |
| `;`     | Metadaten-Zeile (Key: Value) |

`load_map()` gibt `(clean_grid, player, monsters, treasures, meta)` zurück. Das Grid enthält nur `#` und `.` — alle Entitäten werden als separate Listen geführt.

## Konstanten (`entities.py`)

| Konstante | Wert | Bedeutung |
|-----------|------|-----------|
| `FOV` | `π/3` (60°) | Horizontales Sichtfeld |
| `MOVE_SPEED` | `0.08` | Grid-Einheiten pro Frame vorwärts/rückwärts |
| `TURN_SPEED` | `0.06` | Radiant pro Frame drehen |
| `ATTACK_RANGE` | `1.5` | Max. Distanz für Spielerangriff |
| `ATTACK_FOV` | `π/4` (45°) | Winkel-Toleranz für Angriff |
| `MONSTER_MOVE_INTERVAL` | `25` | Frames zwischen Monster-Bewegungen |
| `MONSTER_ATTACK_RANGE` | `0.8` | Distanz für Monster-Gegenangriff |

## Steuerung

| Taste | Aktion |
|-------|--------|
| `W` / `↑` | Vorwärts |
| `S` / `↓` | Rückwärts |
| `A` / `←` | Links drehen |
| `D` / `→` | Rechts drehen |
| `E` / `Space` | Angreifen |
| `M` | Mini-Map ein/aus |
| `Q` / `Ctrl+C` | Beenden |

## Neue Level hinzufügen

1. `maps/levelN.txt` erstellen (Format wie oben)
2. Pfad in `dungeon.py` zur `LEVELS`-Liste hinzufügen

## Häufige Änderungen

- **Monster schneller machen**: `MONSTER_MOVE_INTERVAL` in `entities.py` verringern (z.B. `15`)
- **Breiteres Sichtfeld**: `FOV` in `entities.py` erhöhen (z.B. `math.pi / 2`)
- **Mehr HP**: `Player.hp`/`Monster.hp` Defaults in `entities.py` anpassen
- **Scoring-Formel**: `calc_score()` in `game.py` (Zeile ~100)
- **Neue Wandtextur**: `_wall_char()` in `renderer.py` — Mapping Distanz→ASCII-Zeichen
