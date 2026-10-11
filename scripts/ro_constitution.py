#!/usr/bin/env python3
"""Constitution of Romania (as revised in 2003) from Romanian Wikisource.

The official portal's web service (see ro_fetch.py) only exposes the original 1991 text, not
the 2003 republished version, and the portal's HTML pages are not reachable from our network.
The current text is therefore taken from ro.wikisource.org ("Constituția României (2003)").

Usage: ro_constitution.py <repo_dir>
"""
import os
import re
import sys
from datetime import date

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
PAGE = "Constituția_României_(2003)"
RAW_URL = "https://ro.wikisource.org/w/index.php?title=%s&action=raw" % PAGE
VIEW_URL = "https://ro.wikisource.org/wiki/Constitu%C8%9Bia_Rom%C3%A2niei_(2003)"


def convert(wiki):
    out = []
    alin = 0
    art_start = [None]

    def flush():
        # single-paragraph articles carry no "(1)" label in the official text
        if art_start[0] is not None and alin == 1:
            for i in range(art_start[0], len(out)):
                if out[i].startswith("(1) "):
                    out[i] = out[i][4:]
                    break

    for line in wiki.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("{{") or line.startswith("|") or line.startswith("}}") \
                or line.startswith("[[Categorie") or re.match(r"^\[\[[a-z]{2}:", line):
            continue
        m = re.match(r"^(={2,6})\s*(.*?)\s*\1$", line)
        if m:
            flush()
            art_start[0] = None
            lvl = len(m.group(1))  # == Titlul -> ##, === Capitolul -> ###, ==== Secțiunea -> ####
            title = re.sub(r"^((?:Titlul|Capitolul|Secțiunea)[^:]*):\s*", r"\1 — ", m.group(2))
            out.append("#" * lvl + " " + title)
            continue
        m = re.match(r"^'''(Articolul [^:']+):?'''\s*(?:''(.*?)'')?\s*$", line)
        if m:
            flush()
            alin = 0
            art_start[0] = len(out) + 1
            h = "##### " + m.group(1)
            if m.group(2):
                h += " — " + m.group(2).strip()
            out.append(h)
            continue
        line = line.replace("'''", "**").replace("''", "*")
        m = re.match(r"^#(?![:*#])\s*(.*)$", line)
        if m:
            alin += 1
            out.append(f"({alin}) {m.group(1).strip()}")
            continue
        m = re.match(r"^:(\d+)\.\s*(.*)$", line)
        if m:
            alin = int(m.group(1))
            out.append(f"({alin}) {m.group(2).strip()}")
            continue
        m = re.match(r"^[#:]*:\s*(.*)$", line)
        if m:
            out.append(m.group(1).strip())
            continue
        out.append(line.strip())
    flush()
    return "\n\n".join(out)


def main():
    repo = sys.argv[1]
    r = requests.get(RAW_URL, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    body = convert(r.text)
    fm = f"""---
title: "Constituția României"
identifier: "Constituția României, republicată (M. Of. nr. 767 din 31 octombrie 2003)"
type: constitution
jurisdiction: ro
language: ro
date: 1991-11-21
last_amended: 2003-10-29
status: in_force
source: "{VIEW_URL}"
source_note: "Unofficial transcription (Romanian Wikisource). Official text: Constituția României, republicată în Monitorul Oficial al României, Partea I, nr. 767 din 31 octombrie 2003 (portal legislativ id 47355)."
retrieved: {date.today().isoformat()}
---

# Constituția României

*Constituția din 21 noiembrie 1991, revizuită prin Legea nr. 429/2003 de revizuire a Constituției
României, aprobată prin referendumul național din 18–19 octombrie 2003 și republicată de Consiliul
Legislativ în Monitorul Oficial al României, Partea I, nr. 767 din 31 octombrie 2003.*

"""
    path = os.path.join(repo, "constitutie", "constitutia-romaniei.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fm + body + "\n")


if __name__ == "__main__":
    main()
