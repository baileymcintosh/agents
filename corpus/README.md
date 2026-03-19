# Research Corpus

Public research articles ingested from major investment firm insights pages.

## Structure

```
corpus/
├── index.json          ← full metadata manifest
├── bridgewater/        ← articles by firm
├── oaktree/
├── apollo/
└── ...
```

## Adding a new firm

Edit `scripts/ingest_corpus.py` — add an entry to the `FIRMS` dict with:
- `insights_url`: the listing page URL
- `article_pattern`: regex to identify article URLs on that domain
- `type`: firm category (hedge_fund, private_equity, private_credit, etc.)

Then run: `python scripts/ingest_corpus.py --firm <key>`
