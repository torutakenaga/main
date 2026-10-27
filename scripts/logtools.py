"""Helpers for adding entries to _data/log.yml without touching its comments or layout."""
import difflib
import json
import re

CATEGORIES = ("research", "tango", "kendo", "project")
DATE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")

# The site never states money. Entries that look like they do are flagged for review.
MONEY_RE = re.compile(
    r"[¥￥$€£]|[0-9０-９,，]+\s*円|万円|料金|価格|報酬|謝礼|謝金|ギャラ|費用|参加費|入場料|チケット|無料|有料"
    r"|\b(?:fee|fees|price|prices|paid|free|honorarium|ticket|tickets|donation|invoice|salary)\b",
    re.I,
)

SIMILAR_TITLE = 0.88

# The list shows published versions, so preprint servers are skipped.
PREPRINT_DOI_PREFIXES = ("10.1101/", "10.48550/", "10.21203/", "10.20944/", "10.2139/", "10.31219/", "10.31234/")


def is_preprint(entry):
    return (entry.get("doi") or "").startswith(PREPRINT_DOI_PREFIXES) or entry.get("source", "").startswith("ORCID (preprint")


def clean(text, limit=300):
    """One line, no control characters, bounded length."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalize(title):
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", (title or "").lower())


def has_money(*texts):
    return any(MONEY_RE.search(t or "") for t in texts)


def read_log(path):
    """Return (header, blocks). "\\n".join([header] + blocks) restores the file exactly."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"\n(?=- date:)", text)
    return parts[0], parts[1:]


def write_log(path, header, blocks):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join([header] + blocks))


def _field(block, name):
    m = re.search(r"^(?:- |  )%s:\s*(.*)$" % name, block, re.M)
    if not m:
        return ""
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except ValueError:
        return raw.strip('"')


def block_date(block):
    return _field(block, "date")


def format_entry(entry):
    """YAML text for one entry. JSON strings are valid YAML, so quoting is always safe."""
    lines = ["- date: " + json.dumps(entry["date"], ensure_ascii=False),
             "  title: " + json.dumps(entry["title"], ensure_ascii=False)]
    if entry.get("venue"):
        lines.append("  venue: " + json.dumps(entry["venue"], ensure_ascii=False))
    lines.append("  category: " + entry["category"])
    if entry.get("url"):
        lines.append("  url: " + json.dumps(entry["url"], ensure_ascii=False))
    return "\n".join(lines) + "\n"


def insert_entry(blocks, entry):
    """Keep newest-first order: insert before the first older entry."""
    new = format_entry(entry)
    for i, b in enumerate(blocks):
        if block_date(b) < entry["date"]:
            blocks.insert(i, new)
            return
    blocks.append(new)


class Known:
    """What the log already contains, so automation never adds the same thing twice."""

    def __init__(self, blocks):
        self.rm_ids, self.dois, self.titles = set(), set(), []
        for b in blocks:
            url = _field(b, "url")
            m = re.search(r"researchmap\.jp/[^/]+/(?:published_papers|presentations)/(\d+)", url)
            if m:
                self.rm_ids.add(m.group(1))
            m = re.search(r"(10\.\d{4,9}/[^\s\"?#]+)", url)
            if m:
                self.dois.add(m.group(1).lower())
            m = re.search(r"nature\.com/articles/(s[\w-]+)", url)
            if m:
                self.dois.add("10.1038/" + m.group(1).lower())
            t = normalize(_field(b, "title"))
            if t:
                self.titles.append(t)

    def contains(self, entry):
        if entry.get("rm_id") and entry["rm_id"] in self.rm_ids:
            return True
        if entry.get("doi") and entry["doi"] in self.dois:
            return True
        t = normalize(entry["title"])
        if t in self.titles:
            return True
        return any(difflib.SequenceMatcher(None, t, k).ratio() >= SIMILAR_TITLE for k in self.titles)

    def add(self, entry):
        if entry.get("rm_id"):
            self.rm_ids.add(entry["rm_id"])
        if entry.get("doi"):
            self.dois.add(entry["doi"])
        self.titles.append(normalize(entry["title"]))
