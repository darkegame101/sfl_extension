# Configuration Guide & Schema Reference

This document describes the configuration structure of `sfl_extension` / `sfland auto`, covering `config.json`, environment variables, and runtime defaults.

---

## 1. Configuration File: `config.json`

The system reads its main configuration from `config.json` at the repository root.

### Example Schema
```json
{
  "gpm_api": {
    "base_url": "http://127.0.0.1:19995",
    "group_filter": null
  },
  "ai_vision": {
    "enabled": false,
    "api_key": "",
    "base_url": "https://platform.beeknoee.com/v1",
    "model_id": "bee-tok/claude-haiku-5-5"
  },
  "farming": {
    "default_crop": "Sunflower",
    "default_grow_seconds": 60,
    "action_sync_delay_min": 0.45,
    "action_sync_delay_max": 0.85,
    "seed_box_coord": [400, 560],
    "plot_coords": [
      [310, 270], [350, 270], [390, 270],
      [310, 310], [350, 310], [390, 310],
      [310, 350], [350, 350], [390, 350]
    ],
    "tree_coords": [
      [220, 210], [260, 190], [520, 220]
    ],
    "beehive_coords": [
      [180, 360], [210, 360]
    ],
    "composter_coord": [480, 420]
  },
  "scheduler": {
    "sleep_start_hour": 0.5,
    "sleep_end_hour": 6.5,
    "inter_profile_delay_min": 25,
    "inter_profile_delay_max": 50,
    "coffee_break_every_n_profiles": 5
  },
  "reproducibility": {
    "seed": null,
    "audit_logging": true
  }
}
```

---

## 2. Field Definitions

### `gpm_api`
* `base_url` *(string, default: `"http://127.0.0.1:19995"`)*: URL of the GPM-Login Local REST API. If the port is omitted or unavailable, the system automatically inspects `%LOCALAPPDATA%\Programs\GPMLogin\api_port.dat`.
* `group_filter` *(string or null, default: `null`)*: If specified (e.g., `"SFL-ACTIVE"`), only profiles belonging to this group will be scheduled.

### `ai_vision`
* `enabled` *(boolean, default: `false`)*: Enables visual inspection via Claude Vision. When `false`, the system uses heuristic local vision rules.
* `api_key` *(string, default: `""`)*: API key for vision platform. **Recommended**: Leave empty in `config.json` and set via environment variable `AI_VISION_API_KEY`.
* `base_url` *(string, default: `"https://api.openai.com/v1"`)*: OpenAI-compatible endpoint URL.
* `model_id` *(string, default: `"bee-tok/claude-haiku-5-5"`)*: Model identifier for vision processing.

### `farming`
* `default_crop` *(string, default: `"Sunflower"`)*: Fallback crop name if dynamic selection is disabled.
* `default_grow_seconds` *(integer, default: `60`)*: Maturation time in seconds for the default crop.
* `action_sync_delay_min` / `action_sync_delay_max` *(float, default: `0.45` / `0.85`)*: Delay range between individual crop interactions to simulate human pacing.
* `seed_box_coord` *(array of 2 ints)*: Client coordinates `[x, y]` of the seed inventory selector.
* `plot_coords` *(array of arrays of 2 ints)*: Client coordinates `[x, y]` of farm plots.
* `tree_coords` / `beehive_coords` / `composter_coord`: Coordinates of secondary agricultural elements.

### `scheduler`
* `sleep_start_hour` *(float, default: `0.5`)*: Start of circadian sleep lockout (00:30 AM).
* `sleep_end_hour` *(float, default: `6.5`)*: End of circadian sleep lockout (06:30 AM).
* `inter_profile_delay_min` / `inter_profile_delay_max` *(integer, default: `25` / `50`)*: Seconds to wait before launching the next profile.
* `coffee_break_every_n_profiles` *(integer, default: `5`)*: Frequency of extended rest intervals between profiles.

### `reproducibility`
* `seed` *(integer or null, default: `null`)*: Random seed for deterministic simulation benchmarks.
* `audit_logging` *(boolean, default: `true`)*: Enables JSONL structured audit logging to `audit_trail.jsonl`.

---

## 3. Environment Variables

Credentials and secrets must be injected via environment variables or a local `.env` file (never committed to git):

| Variable | Description |
| :--- | :--- |
| `AI_VISION_API_KEY` | Primary API key for Claude Vision platform. |
| `BEEKNOEE_API_KEY` | Alternative key name recognized by `run.py`. |
| `GPM_API_PORT` | Optional override for GPM-Login Local API port. |
| `PYTHONIOENCODING` | Recommended setting on Windows consoles (`utf-8`). |
