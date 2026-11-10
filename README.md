# ExcelBaas media

Openbare opslag voor de Instagram-beelden van @excelbaas, plus de contentmotor die ze maakt.

- `plans/<week>.json` – weekplan: per item het tijdstip, type (carousel, reel, story), slides en caption.
- `tools/make.py` – maakt van een weekplan alle PNG's en MP4's in de ExcelBaas-huisstijl.
- `media/<week>/` – de gemaakte beelden, met `manifest.json` (openbare links per item).

Gebruik:

```
python3 tools/make.py plans/2026-W46.json
git add -A && git commit -m "Week 2026-W46" && git push
```

De links in `manifest.json` (raw.githubusercontent.com) worden in Metricool ingepland.

Lettertypen: Inter, Oswald en Caveat (SIL Open Font License, zie `tools/fonts/LICENSE-OFL.txt`).
