#!/usr/bin/env python3

def pct(done, total):
    try:
        done=int(done); total=int(total)
        if total <= 0:
            return 0
        return round(done*100/total)
    except Exception:
        return 0

def format_report(bem, title, date, time, stage_done, stage_total, roadmap_done, roadmap_total, checklist, rows):
    stage_pct=pct(stage_done, stage_total)
    roadmap_pct=pct(roadmap_done, roadmap_total)
    lines=[]
    lines.append(f"{bem} | {title} | {date} | {time} (UTC+3)")
    lines.append("")
    lines.append(f"Этап: {stage_done}/{stage_total} ({stage_pct}%)")
    lines.append(f"Дорожная карта: {roadmap_done}/{roadmap_total} ({roadmap_pct}%)")
    lines.append("")
    lines.append("Чек-лист:")
    for item in checklist:
        lines.append(item)
    lines.append("")
    lines.append("Наименование | Описание | Обоснование")
    for name, desc, why in rows:
        lines.append(f"{name} | {desc} | {why}")
    return "
".join(lines)
