import json
from pathlib import Path
from datetime import date

HISCORE_FILE = Path(__file__).parent / 'hiscore.json'
MAX_ENTRIES = 10


def load_scores():
    if not HISCORE_FILE.exists():
        return []
    try:
        return json.loads(HISCORE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def save_score(name, score, time_secs, monsters, treasures, levels):
    scores = load_scores()
    scores.append({
        'name': name[:10],
        'score': score,
        'time': int(time_secs),
        'monsters': monsters,
        'treasures': treasures,
        'levels': levels,
        'date': str(date.today()),
    })
    scores.sort(key=lambda e: e['score'], reverse=True)
    scores = scores[:MAX_ENTRIES]
    HISCORE_FILE.write_text(json.dumps(scores, indent=2, ensure_ascii=False))
    return scores


def format_scores(scores):
    if not scores:
        return ['  Noch keine Einträge.']
    lines = [
        f"  {'#':>2}  {'Name':<12}  {'Score':>7}  {'Zeit':>5}  {'M':>3}  {'T':>3}  {'Datum'}",
        '  ' + '─' * 52,
    ]
    for i, e in enumerate(scores, 1):
        m, s = divmod(e['time'], 60)
        lines.append(
            f"  {i:>2}  {e['name']:<12}  {e['score']:>7}  "
            f"{m:02d}:{s:02d}  {e['monsters']:>3}  {e['treasures']:>3}  {e['date']}"
        )
    return lines
