#!/usr/bin/env python3
"""
Parse an OSRS Wiki step-by-step *walkthrough* page (wikitext) into the raw guide JSON that
build_raw_guide.py consumes. Steps live inside {{Checklist|*...}} templates under ===/==== headings;
this extracts them, strips wiki markup, and groups them by heading.

Fetch the source first (build-time, not shipped):
    curl -sL "https://oldschool.runescape.wiki/w/<PAGE>?action=raw" -o <file>.wikitext

Usage:
    py -3 tools/scrape_wiki_guide.py <wikitext_file> <id> --name "<Display Name>" --source "<url>"

Writes tools/data/raw/<id>.json.
"""
import argparse
import json
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent / "data" / "raw"

# Wiki-content licence for OSRS Wiki text (CC BY-NC-SA 3.0); mirrors the other bundled wiki guides.
DEFAULT_LICENSE = ("OSRS Wiki content, CC BY-NC-SA 3.0 (oldschool.runescape.wiki). "
                   "Attribution: the wiki authors of the linked page.")


def strip_markup(s: str) -> str:
    """Wikitext -> plain readable step text."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    # Inner templates we want to keep as words:
    s = re.sub(r"\{\{Coins\|([\d,]+)\}\}", lambda m: m.group(1) + " coins", s)
    s = re.sub(r"\{\{fairycode\|([a-zA-Z]+)\}\}", lambda m: m.group(1).upper(), s)
    s = re.sub(r"\{\{[Cc]lear\}\}", "", s)
    # Any other template -> drop (handle nesting by repeating until stable).
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    # Links: [[a|b]] -> b ; [[a]] -> a ; anchor links [[#x|y]] -> y
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    # External links: [url text] -> text ; [url] -> ''
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\]", "", s)
    # Emphasis / tags / entities
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\|+\s*title\s*=\S*", "", s)  # stray {{Checklist|title=}} param delimiter leaking into text
    return re.sub(r"\s+", " ", s).strip()


def top_level_templates(text):
    """All top-level {{...}} blocks in order, as (start, end, text) with brace-depth matching."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i:i + 2] == "{{":
            depth, j = 1, i + 2
            while j < n and depth > 0:
                if text[j:j + 2] == "{{":
                    depth += 1; j += 2
                elif text[j:j + 2] == "}}":
                    depth -= 1; j += 2
                else:
                    j += 1
            out.append((i, j, text[i:j]))
            i = j
        else:
            i += 1
    return out


def headings(text):
    """(offset, level, cleaned_title) for each == .. == heading."""
    out = []
    for m in re.finditer(r"(?m)^(={2,})[ \t]*(.+?)[ \t]*=+[ \t]*$", text):
        out.append((m.start(), len(m.group(1)), strip_markup(m.group(2))))
    return out


def section_for(offset, hs):
    """Title of the last heading before offset."""
    title = None
    for off, _lvl, t in hs:
        if off < offset:
            title = t
        else:
            break
    return title


def checklist_steps(block: str):
    """Extract step strings from a {{Checklist|...}} block. '*' = step, '**'/'***' = sub-note appended."""
    inner = block[2:-2]  # drop {{ }}
    inner = re.sub(r"^\s*Checklist\s*", "", inner)      # template name
    inner = re.sub(r"^\|?\s*title=[^\n|]*", "", inner)  # optional title= param
    inner = inner.lstrip("|")
    steps = []
    for line in inner.split("\n"):
        raw = line.rstrip()
        stars = len(raw) - len(raw.lstrip("*"))
        body = raw.lstrip("*").strip()
        if not body:
            continue
        if stars >= 2 and steps:            # sub-note: attach to the current step
            note = strip_markup(body)
            if note:
                steps[-1] = steps[-1] + " — " + note
        elif stars == 1:                    # new step
            txt = strip_markup(body)
            if txt:
                steps.append(txt)
        elif steps:                         # wrapped continuation line
            cont = strip_markup(body)
            if cont:
                steps[-1] = (steps[-1] + " " + cont).strip()
    return steps


def inventory_note(block: str, label: str):
    """{{Inventory|a|b||c}} / {{Equipment|...}} -> 'Inventory check: a, b, c' single step, or None."""
    inner = block[2:-2]
    parts = inner.split("|")[1:]  # drop template name
    items = [strip_markup(p) for p in parts]
    items = [it for it in items if it and "=" not in it]
    if not items:
        return None
    return f"{label}: " + ", ".join(items)


def slugify(title, used):
    base = re.sub(r"[^a-z0-9]+", "-", (title or "section").lower()).strip("-")[:24] or "sec"
    slug, n = base, 2
    while slug in used:
        slug = f"{base}-{n}"; n += 1
    used.add(slug)
    return slug


def parse(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    hs = headings(text)
    blocks = top_level_templates(text)
    ordered = []  # (section_title, step_text)
    for start, _end, block in blocks:
        name = re.match(r"\{\{\s*([A-Za-z ]+)", block)
        tname = name.group(1).strip() if name else ""
        sec = section_for(start, hs) or "Guide"
        if tname == "Checklist":
            for st in checklist_steps(block):
                ordered.append((sec, st))
        elif tname == "Inventory":
            note = inventory_note(block, "Inventory check")
            if note:
                ordered.append((sec, note))
        elif tname == "Equipment":
            note = inventory_note(block, "Equipment check")
            if note:
                ordered.append((sec, note))
    # Group consecutive same-section steps into sections (document order).
    sections, used = [], set()
    for sec, st in ordered:
        if not sections or sections[-1]["section"] != sec:
            sections.append({"section": sec, "prefix": slugify(sec, used), "steps": []})
        sections[-1]["steps"].append({"name": st, "loc": None})
    return sections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wikitext")
    ap.add_argument("id")
    ap.add_argument("--name", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--license", default=DEFAULT_LICENSE)
    a = ap.parse_args()

    text = Path(a.wikitext).read_text(encoding="utf-8")
    sections = parse(text)
    total = sum(len(s["steps"]) for s in sections)
    out = {"id": a.id, "name": a.name, "source": a.source, "license": a.license, "sections": sections}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / f"{a.id}.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{a.id}: {len(sections)} sections, {total} steps -> {dest}")


if __name__ == "__main__":
    main()
