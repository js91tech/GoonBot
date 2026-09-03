# GoonCards portraits

One square PNG per catalog id (`card_*.png`). Each plate is an original
composition inspired by GoonBot palettes and mood (painterly glam velvet,
crimson/gold, neon lounge, pixel city, grow lab) — not cropped from boss
portraits, Nikki GIFs, or brand banners. No wordmarks, no "18+" copy.

`utils/card_art.py` is a seeded unique compositor used as the offline
fallback (no API key). Refresh compositor plates from the repo root:

```bash
python3 scripts/generate_card_portraits.py
python3 scripts/generate_card_portraits.py --force
```

`--ai` is optional and tries the OpenAI-compatible images API first. Missing
files are always filled by the local compositor so the hub never blocks on a
network call.
