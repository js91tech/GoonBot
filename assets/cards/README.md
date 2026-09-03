# GoonCards portraits

One square PNG per catalog id (`card_*.png`). Each plate is an original
composition from the seeded painterly compositor in `utils/card_art.py` —
inspired by GoonBot palettes and mood (crimson/gold velvet, neon lounge,
pixel city, grow lab) but not cropped from boss portraits, Nikki GIFs, or
brand banners. No wordmarks, no "18+" copy.

Generate or refresh from the repo root:

```bash
python3 scripts/generate_card_portraits.py
python3 scripts/generate_card_portraits.py --force
```

`--ai` is optional and tries the OpenAI-compatible images API first. Missing
files are always filled by the local compositor so the hub never blocks on a
network call.
