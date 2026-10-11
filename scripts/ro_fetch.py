#!/usr/bin/env python3
"""Fetch Romanian primary legislation from the Portal Legislativ FreeWebService (SOAP).

Endpoint: http://legislatie.just.ro/apiws/FreeWebService.svc/SOAP  (operations GetToken, Search)

The service only offers a search: (SearchNumar, SearchAn, SearchTitlu, SearchText), 10 results
per page, ranked by relevance.  We enumerate the corpus by querying every act number with a
title keyword ("LEGE", "ORDONANȚĂ", "DECRET-LEGE", ...) and paging until the result list is
exhausted.  Every page is cached (gzip JSON) under _raw/ro/api/ so re-runs do not re-download.

Usage:
  ro_fetch.py enum  [--kinds lege,ordonanta,decret-lege] [--workers 3]
  ro_fetch.py query --title "CODUL" [--number N] [--year Y] [--text T]   (ad-hoc, cached)
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape

import requests

URL = "http://legislatie.just.ro/apiws/FreeWebService.svc/SOAP"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
RAW = os.environ.get("RO_RAW", "/Users/magicaltux/projects/lawcodex/_raw/ro")
CACHE = os.path.join(RAW, "api")
NS_A = "http://schemas.datacontract.org/2004/07/FreeWebService"

# document types whose full text we keep in the cache
KEEP_TYPES = re.compile(r"^(LEGE|ORDONANȚĂ( DE URGENȚĂ)?|DECRET-LEGE|DECRET LEGE|CONSTITUȚIE|COD.*)$")

KINDS = {
    # name: (title keyword, max consecutive numbers without any hit before stopping)
    "lege": ("LEGE", 40),
    "ordonanta": ("ORDONANȚĂ", 30),
    "decret-lege": ("DECRET-LEGE", 15),
}

_local = threading.local()
_lock = threading.Lock()
_last_call = [0.0]
MIN_INTERVAL = 0.35  # seconds between request starts (global), ~3 req/s max


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Content-Type": "text/xml; charset=utf-8"})
        _local.s = s
        _local.tok = None
    return s


def _throttle():
    with _lock:
        now = time.time()
        wait = _last_call[0] + MIN_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def soap(action, body, timeout=600):
    env = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
           f"{body}</s:Body></s:Envelope>")
    hdr = {"SOAPAction": f'"http://tempuri.org/IFreeWebService/{action}"'}
    delay = 5
    for attempt in range(8):
        _throttle()
        try:
            r = session().post(URL, data=env.encode("utf-8"), headers=hdr, timeout=timeout)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
            if r.status_code == 500 and "token" in r.text.lower():
                _local.tok = None
                body = re.sub(r"<tokenKey>.*?</tokenKey>", f"<tokenKey>{token()}</tokenKey>", body)
            print(f"  HTTP {r.status_code} on {action}, retry {attempt}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  {type(e).__name__} on {action}, retry {attempt}", file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 300)
    raise RuntimeError(f"SOAP {action} failed")


def token():
    session()
    if not _local.tok:
        t = soap("GetToken", '<GetToken xmlns="http://tempuri.org/"/>')
        _local.tok = re.search(r"<GetTokenResult>(.*?)</GetTokenResult>", t).group(1)
    return _local.tok


def parse(xml):
    out = []
    for m in re.finditer(r"<a:Legi>(.*?)</a:Legi>", xml, re.S):
        f = {}
        for k, v in re.findall(r"<a:(\w+)>(.*?)</a:\1>", m.group(1), re.S):
            f[k] = (v.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
                    .replace("&apos;", "'").replace("&#xD;", "\r").replace("&amp;", "&"))
        link = f.get("LinkHtml", "")
        f["id"] = int(link.rstrip("/").split("/")[-1]) if link.rstrip("/").split("/")[-1].isdigit() else None
        out.append(f)
    return out


def search(page, number="", year="", title="", text=""):
    """One cached search page. Returns list of records (text dropped for non-kept types)."""
    key = f"{number}|{year}|{title}|{text}|{page}"
    h = hashlib.sha1(key.encode()).hexdigest()
    path = os.path.join(CACHE, h[:2], h + ".json.gz")
    if os.path.exists(path):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)["records"]
    body = ('<Search xmlns="http://tempuri.org/"><SearchModel xmlns:a="%s">'
            "<a:NumarPagina>%d</a:NumarPagina><a:RezultatePagina>10</a:RezultatePagina>"
            "<a:SearchAn>%s</a:SearchAn><a:SearchNumar>%s</a:SearchNumar>"
            "<a:SearchText>%s</a:SearchText><a:SearchTitlu>%s</a:SearchTitlu>"
            "</SearchModel><tokenKey>%s</tokenKey></Search>") % (
        NS_A, page, escape(str(year)), escape(str(number)), escape(text), escape(title), token())
    recs = parse(soap("Search", body))
    for r in recs:
        if not KEEP_TYPES.match((r.get("TipAct") or "").strip()):
            r.pop("Text", None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump({"query": key, "records": recs}, fh, ensure_ascii=False)
    os.replace(tmp, path)
    return recs


def search_all(number="", year="", title="", text="", max_pages=200):
    """Page through a query until an empty page or a page with only already-seen ids."""
    seen, allrecs = set(), []
    for page in range(1, max_pages + 1):
        recs = search(page, number, year, title, text)
        new = [r for r in recs if r["id"] not in seen]
        if not new:
            break
        for r in new:
            seen.add(r["id"])
        allrecs.extend(new)
        # note: pages may hold fewer than 10 records even when more pages follow
    return allrecs


def type_matches(kind, tip):
    tip = (tip or "").strip()
    if kind == "lege":
        return tip == "LEGE"
    if kind == "ordonanta":
        return tip.startswith("ORDONANȚĂ")
    if kind == "decret-lege":
        return tip.replace(" ", "-") == "DECRET-LEGE"
    return False


def enum_kind(kind, workers):
    title, patience = KINDS[kind]
    n, misses, batch = 1, 0, max(workers * 2, 4)
    stats = {}
    with ThreadPoolExecutor(workers) as ex:
        while misses < patience:
            nums = list(range(n, n + batch))
            results = list(ex.map(lambda k: (k, search_all(number=str(k), title=title)), nums))
            for k, recs in results:
                hits = sum(1 for r in recs if type_matches(kind, r.get("TipAct")))
                stats[k] = hits
                misses = 0 if hits else misses + 1
            n += batch
            print(f"[{kind}] up to nr {n - 1}: last hits {[stats[k] for k in nums]}", flush=True)
    return stats


EXTRA_TITLES = [
    "Constituția", "CODUL CIVIL", "CODUL DE PROCEDURĂ CIVILĂ", "CODUL PENAL",
    "CODUL DE PROCEDURĂ PENALĂ", "CODUL FISCAL", "CODUL DE PROCEDURĂ FISCALĂ", "CODUL MUNCII",
    "CODUL ADMINISTRATIV", "CODUL VAMAL", "CODUL SILVIC", "CODUL AERIAN", "CODUL INSOLVENȚEI",
    "CODUL CONSUMULUI",
]


def extras():
    for t in EXTRA_TITLES:
        recs = search_all(title=t, max_pages=40)
        print(f"[extras] {t}: {len(recs)} records", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["enum", "query", "extras"])
    ap.add_argument("--kinds", default="lege,ordonanta,decret-lege")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--title", default="")
    ap.add_argument("--number", default="")
    ap.add_argument("--year", default="")
    ap.add_argument("--text", default="")
    a = ap.parse_args()
    if a.cmd == "enum":
        for k in a.kinds.split(","):
            enum_kind(k, a.workers)
    elif a.cmd == "extras":
        extras()
    else:
        for r in search_all(a.number, a.year, a.title, a.text):
            print(r["id"], r.get("TipAct"), r.get("Numar"), r.get("DataVigoare"),
                  len(r.get("Text") or ""), re.sub(r"\s+", " ", r.get("Titlu") or "")[:120], sep="|")


if __name__ == "__main__":
    main()
