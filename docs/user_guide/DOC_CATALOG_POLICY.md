# DOC_CATALOG_POLICY

This file defines which documents are indexed in Catalog.

## Indexed (Catalog kind=`doc`)

Only actionable docs are indexed:

- user guides (how-to, wiring, contracts, troubleshooting)
- practical guides and walkthroughs
- case docs and component/example references

## Not indexed

These remain in docs navigation but are intentionally excluded from Catalog search:

- architecture philosophy and long-form conceptual docs
- project history / journey / narrative notes
- changelog, evidence, QA discussion, archive files
- temporary/internal scratch docs (`docs/_tmp*`, `_archive/*`)

## Rule of thumb

If a document helps answer "what to do next in implementation", index it.
If it mostly explains "why the architecture exists", keep it out of Catalog.
