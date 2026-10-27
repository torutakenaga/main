#!/usr/bin/env python3
"""Add one entry to _data/log.yml from a GitHub issue form.

The issue body is read from the ISSUE_BODY environment variable (never from a shell
argument) and every value is validated before anything is written.

  ISSUE_BODY="$(cat body.md)" python3 scripts/add_activity.py --summary out.md --error err.txt
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logtools as lt  # noqa: E402

FIELDS = {"category": "Category", "date": "Date", "title": "Title", "venue": "Venue", "url": "URL"}


def parse_form(body):
    """Issue forms render as '### Label' followed by the value."""
    out = {}
    for label, value in re.findall(r"^### (.+?)\s*\n\n(.*?)(?=\n### |\Z)", body.replace("\r\n", "\n"), re.S | re.M):
        value = value.strip()
        out[label.strip()] = "" if value == "_No response_" else value
    return out


def fail(msg, error_path):
    print("ERROR: " + msg, file=sys.stderr)
    if error_path:
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(msg + "\n")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="_data/log.yml")
    ap.add_argument("--summary")
    ap.add_argument("--error")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = parse_form(os.environ.get("ISSUE_BODY", ""))
    got = {}
    for key, prefix in FIELDS.items():
        got[key] = next((v for k, v in raw.items() if k.startswith(prefix)), "")

    category = got["category"].strip().lower()
    date = got["date"].strip()
    title = lt.clean(got["title"])
    venue = lt.clean(got["venue"], 200)
    url = got["url"].strip()

    if category not in lt.CATEGORIES:
        fail("Category must be one of: " + ", ".join(lt.CATEGORIES), args.error)
    if not lt.DATE_RE.match(date) or not (1 <= int(date[5:7]) <= 12 or date[5:7] == "00") or int(date[8:10]) > 31:
        fail("Date must look like 2026.11.03 (use 00 for an unknown month or day).", args.error)
    if not title:
        fail("Title is required.", args.error)
    if url and not re.match(r"^https://[^\s\"<>]+$", url):
        fail("URL must start with https:// and contain no spaces.", args.error)

    entry = {"date": date, "title": title, "venue": venue, "category": category, "url": url}
    header, blocks = lt.read_log(args.log)
    if lt.Known(blocks).contains(entry):
        fail("An entry with the same or a very similar title already exists.", args.error)

    flagged = lt.has_money(title, venue)
    print("Adding: %s | %s | %s" % (date, category, title))
    if args.summary:
        text = "Adds one entry from the issue form:\n\n```yaml\n%s```\n" % lt.format_entry(entry)
        if flagged:
            text += "\n**Check:** the title or venue contains a money-like word. This site does not state money.\n"
        text += "\nNothing is published until this PR is merged.\n"
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write(text)
    if not args.dry_run:
        lt.insert_entry(blocks, entry)
        lt.write_log(args.log, header, blocks)


if __name__ == "__main__":
    main()
