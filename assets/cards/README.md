# GoonCards portraits

One square PNG per catalog id (`card_*.png`).

Generate or refresh from the repo root:

```bash
python3 scripts/generate_card_portraits.py
python3 scripts/generate_card_portraits.py --force
python3 scripts/generate_card_portraits.py --procedural-only
```

With `AI_API_KEY` set, the script uses the same OpenAI-compatible images API as raid avatars. Missing files fall back to procedural busts so the hub never blocks on a network call.
