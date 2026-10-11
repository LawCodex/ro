#!/usr/bin/env python3
"""Convert cached FreeWebService records (see ro_fetch.py) into LawCodex Markdown files.

Usage: ro_convert.py <repo_dir>
"""
import glob
import gzip
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date

RAW = os.environ.get("RO_RAW", "/Users/magicaltux/projects/lawcodex/_raw/ro")
CACHE = os.path.join(RAW, "api")
TODAY = os.environ.get("RO_RETRIEVED", date.today().isoformat())
PORTAL = "https://legislatie.just.ro/Public/DetaliiDocument/%d"

MONTHS = {"ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4, "mai": 5, "iunie": 6,
          "iulie": 7, "august": 8, "septembrie": 9, "octombrie": 10, "noiembrie": 11,
          "decembrie": 12}

# ---------------------------------------------------------------- codes (coduri/)
# slug -> (act kind, number, year, title, title regex of a separate "CODUL ..." document)
CODES = {
    "codul-civil": ("lege", 287, 2009, "Codul civil", r"CODUL CIVIL"),
    "codul-de-procedura-civila": ("lege", 134, 2010, "Codul de procedură civilă", r"CODUL DE PROCEDURĂ CIVILĂ"),
    "codul-penal": ("lege", 286, 2009, "Codul penal", r"CODUL PENAL"),
    "codul-de-procedura-penala": ("lege", 135, 2010, "Codul de procedură penală", r"CODUL DE PROCEDURĂ PENALĂ"),
    "codul-fiscal": ("lege", 227, 2015, "Codul fiscal", r"CODUL FISCAL"),
    "codul-de-procedura-fiscala": ("lege", 207, 2015, "Codul de procedură fiscală", r"CODUL DE PROCEDURĂ FISCALĂ"),
    "codul-muncii": ("lege", 53, 2003, "Codul muncii", r"CODUL MUNCII"),
    "codul-administrativ": ("oug", 57, 2019, "Codul administrativ", r"CODUL ADMINISTRATIV"),
    "codul-vamal": ("lege", 86, 2006, "Codul vamal al României", r"CODUL VAMAL"),
    "codul-silvic": ("lege", 331, 2024, "Codul silvic", r"CODUL SILVIC"),
    "codul-aerian": ("lege", 21, 2020, "Codul aerian", r"CODUL AERIAN"),
    "codul-insolventei": ("lege", 85, 2014, "Codul insolvenței (Legea privind procedurile de prevenire a insolvenței și de insolvență)", r"CODUL INSOLVENȚEI"),
    "codul-consumului": ("lege", 296, 2004, "Codul consumului", r"CODUL CONSUMULUI"),
}

KIND_INFO = {
    # kind: (directory, file prefix, front-matter type, label)
    "lege": ("legi", "lege", "act", "Lege"),
    "oug": ("oug", "oug", "emergency_ordinance", "Ordonanță de urgență"),
    "og": ("og", "og", "ordinance", "Ordonanță"),
    "decret-lege": ("decrete-lege", "decret-lege", "decree_law", "Decret-lege"),
}


def kind_of(tip):
    tip = (tip or "").strip()
    if tip == "LEGE":
        return "lege"
    if tip == "ORDONANȚĂ DE URGENȚĂ":
        return "oug"
    if tip == "ORDONANȚĂ":
        return "og"
    if tip.replace(" ", "-") == "DECRET-LEGE":
        return "decret-lege"
    return None


def clean_title(t):
    t = (t or "").replace("﻿", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def act_date(title):
    m = re.search(r"\bdin (\d{1,2}) ([a-zăâîșşțţ]+) (\d{4})", title, re.I)
    if m and m.group(2).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            return None
    return None


def mo_date(text):
    m = re.search(r"MONITORUL OFICIAL[^\n]{0,40}?nr\.\s*[\d\-\w]+(?:\s*bis)?\s+din\s+(\d{1,2})\s+([a-zăâîșşțţ]+)\s+(\d{4})",
                  text[:3000], re.I)
    if m and m.group(2).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))), m.group(0)
        except ValueError:
            pass
    return None, None


def is_republished(title):
    return bool(re.search(r"republicat", title, re.I))


def load_records():
    recs = {}
    for path in glob.glob(os.path.join(CACHE, "*", "*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for r in json.load(fh)["records"]:
                if r.get("id") is None:
                    continue
                old = recs.get(r["id"])
                if old is None or (r.get("Text") and not old.get("Text")):
                    recs[r["id"]] = r
    return recs


# ---------------------------------------------------------------- text -> markdown
SEP = re.compile(r"\n?[\t ]*\xa0\+\xa0[\t ]*\n?")
HEAD_RANKS = [
    ("partea", r"(?:PARTEA|Partea)\b"),
    ("cartea", r"(?:CARTEA|Cartea)\b"),
    ("titlul", r"(?:TITLUL|Titlul)\b"),
    ("capitolul", r"(?:CAPITOLUL|Capitolul)\b"),
    ("sectiunea", r"(?:SECȚIUNEA|SECŢIUNEA|Secțiunea|Secţiunea|SECTIUNEA|Sectiunea)\b"),
    ("subsectiunea", r"(?:SUBSECȚIUNEA|SUBSECŢIUNEA|Subsecțiunea|Subsecţiunea|Paragraful|§)\b"),
]
ART = re.compile(r"^(Articolul|ARTICOLUL|Art\.)\s+((?:[IVXLC]+|\d+(?:\^\d+)?|UNIC|unic|Unic)[^\s]*)\s*(.*)$", re.S)
ANNEX = re.compile(r"^(ANEXA|ANEXĂ|Anexa|Anexă|ANEXELE)\b")
LABEL_RX = r"(?:\(\d+(?:\^\d+)?\)|[a-zăâîșşțţ]{1,3}(?:\^\d+)?\)|\d+(?:\^\d+)?\.|[IVXLC]+\.|\d+\))"
LABEL = re.compile(r"^(" + LABEL_RX + r"|[-–—•*])$")
TRAIL_LABEL = re.compile(r"[ \t]{2,}(" + LABEL_RX + r")[ \t]{3,}")


def paragraphs(s):
    """Split a flattened segment into paragraphs (runs of >=3 spaces are paragraph breaks)."""
    # the portal export marks structural breaks with a non-breaking-space-delimited "..."
    s = s.replace("\r", "").replace("\xa0...\xa0", "\n")
    s = TRAIL_LABEL.sub(lambda m: "\n" + m.group(1) + "   ", s)
    chunks = [c.strip() for c in re.split(r"(?:[ \t]{3,}|\n+)", s)]
    out = []
    pending = None
    for c in chunks:
        if not c:
            continue
        c = re.sub(r"[ \t\xa0]+", " ", c).strip()
        if c == "...":
            if pending:
                out.append(pending)
                pending = None
            out.append("...")
            continue
        if LABEL.match(c):
            pending = (pending + " " + c) if pending else c
            continue
        if pending:
            c = pending + " " + c
            pending = None
        out.append(c)
    if pending:
        out.append(pending)
    return out


def looks_tabular(seg):
    lines = [l for l in seg.split("\n") if l.strip()]
    if len(lines) < 4:
        return False
    spaced = sum(1 for l in lines if re.search(r"\S {4,}\S", l) or re.match(r"^\s{6,}\S", l))
    return spaced >= len(lines) * 0.5


def md_escape(p):
    # avoid accidental markdown structures at line start
    if re.match(r"^(#|>|=+$|-+$|_+$|\*+$)", p):
        return "\\" + p
    return p


def codeblock(t):
    t = t.replace("\xa0", " ").replace("\t", "    ")
    lines = [l.rstrip() for l in t.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    fence = "````" if any(l.lstrip().startswith("```") for l in lines) else "```"
    return fence + "text\n" + "\n".join(lines) + "\n" + fence


NOT_TITLE = re.compile(
    r"(^(Se|La|În|Prin|Prezenta|Prezentul|Prevederile|Dispozițiile|Dispoziţiile|Articolul|Art\.|Pe|Până|De|Cu)\b)"
    r"|\b(din|a|al|ale|ai|la|de|cu|prin|în|și|şi|sau|pentru|privind|nr\.|art\.|alin\.|lit\.)$"
    r"|\b(art|nr|alin|lit)\.")


def is_art_title(paras):
    return (len(paras) > 1 and len(paras[0]) < 120 and not re.search(r"[.;:,]$", paras[0])
            and not LABEL.match(paras[0].split(" ")[0]) and not paras[0].startswith("("))


def render_body(text):
    segs = SEP.split(text)
    head, segs = segs[0], segs[1:]
    # ranks present
    present = []
    for name, rx in HEAD_RANKS:
        if any(re.match(rx + r"\s", s.strip()) for s in segs):
            present.append(name)
    level_of = {n: min(2 + i, 6) for i, n in enumerate(present)}
    art_level = 2 + len(present)
    arts = [ART.match(x.strip()) for x in segs]
    arts = [a for a in arts if a]
    titled = sum(1 for a in arts if is_art_title(paragraphs(a.group(3))))
    titled_doc = len(arts) >= 5 and titled >= 0.3 * len(arts)
    out = []
    for seg in segs:
        raw = seg
        s = seg.strip()
        if not s:
            continue
        rank = None
        for name, rx in HEAD_RANKS:
            if re.match(rx + r"\s", s):
                rank = name
                break
        m = ART.match(s)
        if rank:
            paras = paragraphs(s)
            title = paras[0]
            rest = paras[1:]
            # heading title of the unit: next short paragraph without final punctuation
            if rest and len(rest[0]) < 200 and not re.search(r"[.;:,]$", rest[0]):
                title += " — " + rest[0]
                rest = rest[1:]
            out.append("#" * level_of[rank] + " " + title)
            out.extend(md_escape(p) for p in rest)
        elif m:
            label = f"{m.group(1)} {m.group(2)}"
            body = m.group(3)
            paras = paragraphs(body)
            if is_art_title(paras):
                label += " — " + paras[0]
                paras = paras[1:]
            elif titled_doc and paras:
                # in documents whose articles carry marginal titles, a title followed by a
                # single-paragraph text is separated by only two spaces
                mm = re.match(r"^(\S.{2,110}?\S)  (\S.*)$", re.sub(r"[ \t\xa0]{3,}", "   ", body.strip()), re.S)
                if mm and not re.search(r"[.;:,]$", mm.group(1)) and mm.group(2)[:1].isupper() \
                        and mm.group(1)[:1].isupper() and "  " not in mm.group(1) \
                        and re.match(r"\d", m.group(2)) and not NOT_TITLE.search(mm.group(1)):
                    label += " — " + re.sub(r"\s+", " ", mm.group(1))
                    paras = paragraphs(mm.group(2))
            if art_level <= 6:
                out.append("#" * art_level + " " + label)
            else:
                out.append(f"**{label}**")
            out.extend(md_escape(p) for p in paras)
        elif ANNEX.match(s):
            if looks_tabular(raw):
                first, _, table = raw.strip("\n").partition("\n")
                paras = paragraphs(first)
                out.append("## " + paras[0])
                out.extend(md_escape(p) for p in paras[1:])
                out.append(codeblock(table))
            else:
                paras = paragraphs(s)
                out.append("## " + paras[0])
                out.extend(md_escape(p) for p in paras[1:])
        elif looks_tabular(raw):
            first, _, table = raw.strip("\n").partition("\n")
            out.extend(md_escape(p) for p in paragraphs(first))
            out.append(codeblock(table))
        else:
            out.extend(md_escape(p) for p in paragraphs(s))
    return head, out


def render_head(head):
    """Header: '<TITLE> EMITENT <x> Publicat în <MO ...> <preamble>'."""
    h = head.replace("﻿", "").replace("\r", "")
    m = re.search(r"\s{2,}EMITENT:?\s+(.*?)\s{2,}(?:Publicat în|PUBLICAT ÎN:?)\s+(.*?MONITORUL OFICIAL[^\n]*?\d{4}|.*?\d{4})(.*)$",
                  h, re.S | re.I)
    lines = []
    if m:
        title = re.sub(r"\s+", " ", h[:m.start()]).strip()
        lines.append(f"**Emitent:** {re.sub(chr(10) + '|\\s+', ' ', m.group(1)).strip()}")
        lines.append("")
        lines.append(f"**Publicat în:** {re.sub(r'\\s+', ' ', m.group(2)).strip()}")
        rest = m.group(3)
    else:
        title = None
        rest = h
    pre = paragraphs(rest)
    if pre:
        lines.append("")
        for p in pre:
            lines.append(md_escape(p))
            lines.append("")
    return title, lines


def yq(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def slugify(s, maxlen=60):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen].rstrip("-")


def write_doc(path, rec, fm_type, title, identifier, extra=None):
    text = rec.get("Text") or ""
    head, body = render_body(text)
    htitle, headlines = render_head(head)
    full_title = clean_title(rec.get("Titlu"))
    full_title = re.split(r"\s+EMITENT:?\s", full_title)[0].strip()
    d = act_date(full_title)
    pub, _ = mo_date(text)
    fm = ["---", f"title: {yq(title or full_title)}", f"identifier: {yq(identifier)}",
          f"portal_id: {rec['id']}", f"type: {fm_type}", "jurisdiction: ro", "language: ro"]
    if d:
        fm.append(f"date: {d.isoformat()}")
    if pub:
        fm.append(f"published: {pub.isoformat()}")
    if rec.get("DataVigoare"):
        fm.append(f"in_force_from: {rec['DataVigoare'][:10]}")
    for k, v in (extra or {}).items():
        fm.append(f"{k}: {v}")
    fm += ["status: unknown", f"source: {yq(PORTAL % rec['id'])}",
           'source_api: "http://legislatie.just.ro/apiws/FreeWebService.svc"', f"retrieved: {TODAY}", "---", ""]
    md = "\n".join(fm) + "\n# " + (htitle or full_title) + "\n\n"
    md += "\n".join(headlines).strip() + "\n\n" if headlines else ""
    md += "\n\n".join(body) + "\n"
    md = re.sub(r"\n{3,}", "\n\n", md)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)


def main():
    repo = sys.argv[1]
    recs = load_records()
    groups = defaultdict(list)
    for r in recs.values():
        k = kind_of(r.get("TipAct"))
        if not k or not r.get("Text"):
            continue
        t = clean_title(r.get("Titlu"))
        d = act_date(t)
        num = (r.get("Numar") or "").strip()
        if not d or not num.isdigit() or int(num) == 0:
            continue
        groups[(k, int(num), d.year)].append(r)

    counts = defaultdict(int)
    written = set()
    done_codes = set()
    # original (1991) text of the Constitution; the current 2003 text comes from ro_constitution.py
    if 1413 in recs and recs[1413].get("Text"):
        path = os.path.join(repo, "constitutie", "constitutia-romaniei-1991-forma-initiala.md")
        write_doc(path, recs[1413], "constitution", "Constituția României (1991) — forma inițială",
                  "Constituția din 21 noiembrie 1991", {"version": "original"})
        written.add(os.path.relpath(path, repo))
    # codes
    for slug, (k, num, year, ctitle, rx) in CODES.items():
        cands = list(groups.get((k, num, year), []))
        if rx:
            for r in recs.values():
                tip = (r.get("TipAct") or "").strip()
                if tip.startswith("COD") and r.get("Text") and re.match(rx, tip.replace("Ş", "Ș").replace("Ţ", "Ț")):
                    t = clean_title(r.get("Titlu"))
                    if re.search(rf"\b{num}/{year}\b|nr\. {num} din .*{year}|\b{year}\b", t):
                        cands.append(r)
        cands = [r for r in cands if len((r.get("Text") or "")) > 2000]
        if not cands:
            print("MISSING code", slug, file=sys.stderr)
            continue
        cands.sort(key=lambda r: (mo_date(r.get("Text") or "")[0] or date(1, 1, 1), r["id"]))
        chosen = cands[-1]
        version = "republished" if is_republished(clean_title(chosen.get("Titlu"))) else "original"
        label = KIND_INFO[k][3]
        path = os.path.join(repo, "coduri", f"{slug}.md")
        write_doc(path, chosen, "code", ctitle, f"{label} nr. {num}/{year}", {"version": version})
        done_codes.add((k, num, year))
        written.add(os.path.relpath(path, repo))
        counts["coduri"] += 1
    for (k, num, year), rs in sorted(groups.items()):
        # choose the most recent republication if any, else the original (lowest portal id)
        rep = [r for r in rs if is_republished(clean_title(r.get("Titlu")))]
        orig = sorted([r for r in rs if r not in rep], key=lambda r: r["id"])
        if rep:
            rep.sort(key=lambda r: (mo_date(r.get("Text") or "")[0] or date(1, 1, 1), r["id"]))
            chosen, version = rep[-1], "republished"
        else:
            chosen, version = orig[0], "original"
        if len((chosen.get("Text") or "").strip()) < 400 and len(rs) > 1:
            alt = max(rs, key=lambda r: len(r.get("Text") or ""))
            chosen = alt
            version = "republished" if alt in rep else "original"
        dirname, prefix, fmtype, label = KIND_INFO[k]
        ident = f"{label} nr. {num}/{year}"
        extra = {"version": version}
        if version == "republished":
            extra["original_portal_id"] = orig[0]["id"] if orig else "null"
        if (k, num, year) in done_codes:
            continue  # handled in codes pass
        if k == "decret-lege":
            path = os.path.join(repo, dirname, f"{prefix}-{num}-{year}.md")
        else:
            path = os.path.join(repo, dirname, str(year), f"{prefix}-{num}-{year}.md")
        write_doc(path, chosen, fmtype, None, ident, extra)
        written.add(os.path.relpath(path, repo))
        counts[dirname] += 1

    print(json.dumps(counts, indent=1))
    with open(os.path.join(RAW, "written.json"), "w") as fh:
        json.dump(sorted(written), fh)


if __name__ == "__main__":
    main()
