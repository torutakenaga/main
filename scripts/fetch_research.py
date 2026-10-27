#!/usr/bin/env python3
"""Add research items found on ORCID and researchmap to _data/log.yml.

Only adds; never edits or deletes existing entries. Anything already in the log
(matched by researchmap id, DOI, or a near-identical title) is skipped.

  python3 scripts/fetch_research.py --dry-run          # show what would be added
  python3 scripts/fetch_research.py --summary out.md   # write log.yml + a PR summary
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logtools as lt  # noqa: E402

ORCID_ID = "0000-0002-1277-4156"
RESEARCHMAP_ID = "torutakenaga"
UA = "torutakenaga.com-updater (https://torutakenaga.com)"


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fmt_date(y, m=None, d=None):
    return "%s.%s.%s" % (str(y).zfill(4), str(m or 0).zfill(2), str(d or 0).zfill(2))


def parse_iso(s):
    """'2026-04-30' / '2026-04' / '2026' -> '2026.04.30' style (missing parts become 00)."""
    parts = (s or "").split("-")
    if not parts or not parts[0].isdigit():
        return ""
    nums = [int(p) if p.isdigit() else 0 for p in parts[:3]]
    return fmt_date(*nums)


def pick(d, prefer="en"):
    """researchmap localized dict -> the preferred language, then the other, then anything."""
    if not isinstance(d, dict):
        return ""
    other = "ja" if prefer == "en" else "en"
    return d.get(prefer) or d.get(other) or next(iter(d.values()), "")


def from_orcid():
    out = []
    data = get_json("https://pub.orcid.org/v3.0/%s/works" % ORCID_ID)
    for g in data.get("group", []):
        ws = g["work-summary"][0]
        date = ws.get("publication-date") or {}
        year = (date.get("year") or {}).get("value")
        if not year:
            continue
        doi = ""
        for e in (g.get("external-ids") or {}).get("external-id", []):
            if e.get("external-id-type") == "doi":
                doi = e["external-id-value"].lower()
                break
        url = "https://doi.org/" + doi if doi else ((ws.get("url") or {}).get("value") or "")
        out.append({
            "date": fmt_date(year, (date.get("month") or {}).get("value"), (date.get("day") or {}).get("value")),
            "title": lt.clean(ws["title"]["title"]["value"]),
            "venue": lt.clean((ws.get("journal-title") or {}).get("value", ""), 200),
            "category": "research", "url": url, "doi": doi, "source": "ORCID (%s)" % ws.get("type", "work"),
        })
    return out


def from_researchmap():
    out, doi_by_id = [], {}
    base = "https://api.researchmap.jp/%s/" % RESEARCHMAP_ID
    for kind in ("published_papers", "presentations"):
        for it in get_json(base + kind + "?limit=100").get("items", []):
            rid = str(it.get("rm:id", ""))
            # Items written in Japanese are listed in Japanese, like the rest of the log.
            prefer = "ja" if (it.get("languages") or [""])[0] == "jpn" else "en"
            title = pick(it.get("paper_title") or it.get("presentation_title"), prefer)
            date = parse_iso(it.get("publication_date", ""))
            if not (rid and title and date):
                continue
            doi = ((it.get("identifiers") or {}).get("doi") or [""])[0].lower()
            if doi:
                doi_by_id[rid] = doi
            if kind == "presentations" and it.get("invited") and "招待講演" not in title:
                title += "（招待講演）"
            out.append({
                "date": date, "title": lt.clean(title),
                "venue": lt.clean(pick(it.get("publication_name") or it.get("event"), prefer), 200),
                "category": "research",
                "url": "https://researchmap.jp/%s/%s/%s" % (RESEARCHMAP_ID, kind, rid),
                "doi": doi, "rm_id": rid, "source": "researchmap (%s)" % kind,
            })
    return out, doi_by_id


def load_ignore(path):
    """scripts/ignore.txt: one researchmap id, DOI, or title fragment per line ('#' = comment)."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln.split("#")[0].strip().lower() for ln in f if ln.split("#")[0].strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="_data/log.yml")
    ap.add_argument("--summary", help="write a Markdown summary (used as the PR body)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    header, blocks = lt.read_log(args.log)
    known = lt.Known(blocks)

    orcid = from_orcid()
    rmap, doi_by_id = from_researchmap()
    # An item already in the log under a researchmap URL: remember its DOI so the
    # same paper coming from ORCID is recognised.
    for rid, doi in doi_by_id.items():
        if rid in known.rm_ids:
            known.dois.add(doi)

    ignore = load_ignore(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ignore.txt"))

    added, skipped = [], {"preprint": 0, "ignored": 0}
    for entry in orcid + rmap:
        if lt.is_preprint(entry):
            skipped["preprint"] += 1
            continue
        haystack = " ".join([entry.get("rm_id", ""), entry.get("doi", ""), entry["title"]]).lower()
        if any(s in haystack for s in ignore):
            skipped["ignored"] += 1
            continue
        if known.contains(entry):
            continue
        known.add(entry)
        added.append(entry)

    print("ORCID: %d items, researchmap: %d items, skipped: %s, new: %d" % (len(orcid), len(rmap), skipped, len(added)))
    for e in added:
        flag = "  [CHECK: money-like word]" if lt.has_money(e["title"], e["venue"]) else ""
        print("  + %s  %s  (%s)%s" % (e["date"], e["title"][:80], e["source"], flag))

    if args.summary:
        lines = ["Research items found on ORCID / researchmap that are not in the list yet.", "",
                 "| Date | Title | Source |", "|---|---|---|"]
        for e in added:
            lines.append("| %s | %s | %s |" % (e["date"], e["title"].replace("|", "\\|"), e["source"]))
        if any(lt.has_money(e["title"], e["venue"]) for e in added):
            lines += ["", "**Check:** a title or venue contains a money-like word. This site does not state money."]
        lines += ["", "Review the entries, edit `_data/log.yml` on this branch if needed, then merge to publish.",
                  "Nothing is published until this PR is merged."]
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    if added and not args.dry_run:
        for e in sorted(added, key=lambda x: x["date"]):
            lt.insert_entry(blocks, e)
        lt.write_log(args.log, header, blocks)


if __name__ == "__main__":
    main()
