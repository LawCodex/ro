# Romania — legislation as Markdown (LawCodex)

Romanian primary legislation (Constituția, coduri, legi, ordonanțe de urgență, ordonanțe,
decrete-lege) as Markdown, one file per act. The source is the **Portal Legislativ** of the
Ministry of Justice (https://legislatie.just.ro), read through its public SOAP web service
*FreeWebService*. The current Constitution comes from Romanian Wikisource (see below).

Retrieved: **2026-10-12**.

> **Important: these are not consolidated texts.** The task was to collect the current
> consolidated form (*forma consolidată / actualizată*) of each act. That was not possible from
> here (see [Limitations](#limitations-read-this-first)). Each file holds the **original text as
> published in the Monitorul Oficial**, or, where the act was later **republished** (*republicare*,
> an official consolidated text that the Consiliul Legislativ publishes in the Monitorul Oficial
> after major amendments), the **most recent republication** in the portal. Later amendments
> are not applied. Repealed acts are included too, because the web service exposes no in-force
> status.

## Coverage

| Directory | Contents | Files |
|---|---|---:|
| `constitutie/` | `constitutia-romaniei.md`: the Constitution as revised in 2003 (Wikisource transcription); `constitutia-romaniei-1991-forma-initiala.md`: original 1991 text (official portal) | 2 |
| `coduri/` | the main codes: civil, procedură civilă, penal, procedură penală, fiscal, procedură fiscală, muncii, administrativ, vamal, silvic (2024), aerian (2020), insolvenței (Legea 85/2014), consumului | 13 |
| `legi/<year>/` | laws (*legi*), 1864–2026 (mostly 1990–2026), excluding the codes above | 12,039 |
| `oug/<year>/` | emergency ordinances of the Government (*ordonanțe de urgență*), 1993–2026 | 4,165 |
| `og/<year>/` | Government ordinances (*ordonanțe*), 1992–2026 | 1,680 |
| `decrete-lege/` | decree-laws of 1989–1990 (CFSN / CPUN) | 158 |
| **Total** | | **18,057** |

- 334 laws, 116 ordinances / emergency ordinances / decree-laws, and 4 of the 13 codes (civil, procedură civilă, muncii, consumului) use a
  republished text (`version: republished` in the front matter). All other files are the original
  published text (`version: original`).
- Completeness check: for 1990–2026 the act numbers in each year should run from 1 to the highest
  number seen. 52 law numbers (out of about 11,500), 96 OUG numbers (out of about 4,260) and
  34 OG numbers (out of about 1,710) are missing. Spot checks with year-filtered queries found
  that these acts are not in the web service's database at all; many are probably acts that were
  never published (e.g. classified ones).
- 91 files have almost no body. In these cases the portal holds only a stub for the act and puts
  the substance in a separate annex document (e.g. a plan, regulation or statute). Annexes stored
  as separate portal documents with another type (REGULAMENT, NORME, ANEXĂ, …) are not included.

## Not covered

- **Consolidated (current) texts.** See below.
- **Status (in force / repealed).** The web service has no status field, so every file says
  `status: unknown` (except the 2003 Constitution). Amending acts (*legi/ordonanțe pentru
  modificarea…*), approval laws (*legi privind aprobarea ordonanței…*) and repealed acts are all
  included.
- **Government decisions (*hotărâri ale Guvernului*).** These are secondary legislation and there
  are more than 40,000 of them, nearly all individual or administrative (appointments, budget
  transfers, expropriations). Without consolidated text or in-force status they were left out.
- Pre-1989 decrees of the Council of State (*decrete*), presidential decrees, ministerial orders,
  decisions of the Constitutional Court and of the High Court, regulations of autonomous
  authorities, international treaties as separate documents, the Monitorul Oficial Part I
  publications other than the above, and local legislation.
- Historical constitutions (1866, 1923, 1938, 1948, 1952, 1965) and repealed codes (Codul civil
  1864, Codul penal 1968, Codul de procedură civilă 1865, …). They are in the portal but not in
  this corpus.

## Limitations (read this first)

1. **The portal's web pages could not be reached.** `https://legislatie.just.ro` (including
   `/Public/DetaliiDocument/<id>`, the only place that shows the *forma consolidată*) accepts the
   TLS handshake but then closes the connection without any HTTP response ("empty reply"). This
   happened for every URL, every user agent, HTTP/1.1 and HTTP/2, with and without the local
   proxy. Plain `http://` only redirects to `https`, and `robots.txt` was unreachable for the same
   reason. It looks like network-level filtering of our location. We did **not** try to get
   around it.
2. **The web service has no consolidated text.** `http://legislatie.just.ro/apiws/FreeWebService.svc`
   (operations `GetToken` and `Search`, 10 results per page) is reachable over plain HTTP. It
   returns, for each document, the act's text as originally published (or the text of a
   republication, which the portal stores as its own document), flattened into plain text.
   Structural units are separated by a `+` marker, and runs of spaces separate paragraphs. The
   conversion rebuilds headings and paragraphs from that, so some paragraph breaks are lost
   (paragraphs separated by only two spaces in the export end up merged). Tables come through as
   one cell per line and are kept as `text` code blocks.
3. **The 2003 Constitution is not in the web service.** Only the 1991 original is (document 1413).
   The republished text (Monitorul Oficial nr. 767/31.10.2003, portal document 47355) is not
   returned. The official site of the Chamber of Deputies timed out, and the Constitutional Court
   and Presidency sites sit behind a browser-verification challenge (not circumvented). So
   `constitutie/constitutia-romaniei.md` is taken from **Romanian Wikisource**
   ([Constituția României (2003)](https://ro.wikisource.org/wiki/Constitu%C8%9Bia_Rom%C3%A2niei_(2003))),
   an unofficial transcription.

## Format

```yaml
---
title: "LEGEA nr. 18 din 19 februarie 1991 (*republicată*) fondului funciar"  # portal title
identifier: "Lege nr. 18/1991"        # kind, number/year
portal_id: 1461                        # document id on legislatie.just.ro
type: act        # constitution | code | act | emergency_ordinance | ordinance | decree_law
jurisdiction: ro
language: ro
date: 1991-02-19                       # date of the act ("din ...")
published: 1998-01-05                  # Monitorul Oficial date of this text (original or republication)
in_force_from: 1998-01-05              # portal "DataVigoare" of this document
version: republished                   # original | republished
original_portal_id: 1459               # for republished texts: id of the original publication
status: unknown
source: "https://legislatie.just.ro/Public/DetaliiDocument/1461"
source_api: "http://legislatie.just.ro/apiws/FreeWebService.svc"
retrieved: 2026-10-12
---
```

Body: H1 with the act's title, then the issuer (*Emitent*), the Monitorul Oficial reference, the
preamble and any notes, then the text. *Partea / Cartea / Titlul / Capitolul / Secțiunea /
Subsecțiunea (§)* become headings, using only the levels that occur in the act. Articles are
headings at the next level down (bold labels beyond `######`), with the marginal title when there
is one (`###### Articolul 1 — Izvoarele dreptului civil`). Annexes are `##` headings. The text is
reproduced as in the source, keeping the original orthography (ş/ţ with cedilla in older texts).

File names: `legi/<year>/lege-<nr>-<year>.md`, `oug/<year>/oug-<nr>-<year>.md`,
`og/<year>/og-<nr>-<year>.md`, `decrete-lege/decret-lege-<nr>-<year>.md`. The year is the year
of the act. Codes are `coduri/codul-<name>.md`. Their underlying law is not repeated in `legi/`
(e.g. Legea 287/2009 is only in `coduri/codul-civil.md`).

## Sources and licence

- Portal Legislativ, Ministerul Justiției: https://legislatie.just.ro (web service
  `http://legislatie.just.ro/apiws/FreeWebService.svc`).
- Romanian Wikisource for the 2003 Constitution (CC BY-SA / public-domain text).

Under Romanian copyright law (Legea nr. 8/1996, art. 9), official texts of a legislative,
administrative or judicial nature, and their official translations, are not protected by
copyright. The texts here are therefore in the public domain. The Markdown conversion is
published without additional restrictions.

## Regenerating

```sh
pip install -r scripts/requirements.txt
python scripts/ro_fetch.py enum          # numbers 1..N × {LEGE, ORDONANȚĂ, DECRET-LEGE}, cached in _raw/ro/api
python scripts/ro_fetch.py extras        # separate code documents ("CODUL ...") and constitution
python scripts/ro_convert.py .           # -> constitutie/ (1991), coduri/, legi/, oug/, og/, decrete-lege/
python scripts/ro_constitution.py .      # -> constitutie/constitutia-romaniei.md (Wikisource)
```

The fetcher queries the search operation for every act number with a title keyword and pages
until no new results come back (about 7,000 search pages in total). It throttles to about 3
requests per second with 4 parallel workers. Pages the server cannot return (HTTP 500) are
retried as single-record pages. If the portal's HTML pages become reachable, a future version
should fetch `/Public/DetaliiDocument/<id>` to get the consolidated texts and in-force status.
