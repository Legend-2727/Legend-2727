# Project logos

Drop a square PNG/SVG here and reference it from `projects.json`:

```json
{ "name": "ScholarAI", "repo": "Javafest2025/meta", "logo": "scholarai.png" }
```

The build inlines it as a base64 data URI, so the card stays a single
self-contained SVG. A project with no `logo` renders a monogram tile instead.
