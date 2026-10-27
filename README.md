# torutakenaga.com

Jekyll site on GitHub Pages. The activity list on the home page is built from `_data/log.yml`.
`main` is protected: every change goes through a pull request, and merging publishes.

## Updating the activity list

| How | When | What happens |
|---|---|---|
| Edit `_data/log.yml` | Anything | Copy the template at the top of the file, open a pull request, merge. |
| **Issues > New issue > "Add activity"** | One event, talk, etc. | Fill in the form. A pull request is opened automatically (owner's issues only). |
| **Actions > "Update research list" > Run workflow** | New papers / talks | Looks at ORCID and researchmap and opens a pull request with items not in the list yet. |

Nothing is published until you merge the pull request. Check the entries first.

- Items you do not want from ORCID / researchmap: add the researchmap id, DOI or a title fragment to `scripts/ignore.txt`.
- Preprints are skipped on purpose (the list shows published versions).
- Titles or venues that look like they contain money terms are flagged in the pull request.

## Files

- `scripts/logtools.py` shared helpers (reading and inserting entries)
- `scripts/fetch_research.py` ORCID + researchmap
- `scripts/add_activity.py` issue form
- `.github/workflows/` the two workflows, `.github/ISSUE_TEMPLATE/` the form
