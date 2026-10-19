# Changelog

All notable changes to the `sfl_extension` / `sfland auto` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Repository Engineering Governance (`AGENTS.md`)**: Established mandatory, enforceable engineering guidelines for all AI coding agents working on the codebase (Rules A–H, 7-step task workflow, response format).
- **Automated CI Workflow (`.github/workflows/ci.yml`)**: Continuous integration testing across Python 3.10, 3.11, and 3.12 on Windows runners.
- **Dependency Manifests (`requirements.txt`, `requirements-dev.txt`)**: Explicit runtime and testing dependency declarations.
- **Documentation Suite (`docs/`)**:
  - `docs/architecture.md`: Comprehensive system architecture, module boundaries, data flows, and HCI behavioral modeling.
  - `docs/testing.md`: Test strategy, test matrix, mock vs. live execution, and regression verification commands.
  - `docs/configuration.md`: Configuration schema, environment variables, default settings, and security guidelines.
- **Profile Name Resolution in GpmAPI (`core/gpm_api.py`)**: Added `find_profile_by_name()`, `start_profile_by_name()`, and `stop_profile_by_name()` to map human-readable profile names directly to GPM UUIDs.
- **Automated Unit & Live Test Suite (`tests/test_gpm_api.py`)**: Added 7 comprehensive tests covering mock HTTP sessions and live GPM-Login connectivity.
- **Web-based GPM Controller & Test Center (`gpm_ui.py`)**: Local web dashboard running on port 18888 for controlling profiles, inspecting CDP tabs, and live testing.

### Changed
- **Secret & Credential Management**: Updated `run.py` and `tests/test_ai_validation.py` to support `AI_VISION_API_KEY` and `BEEKNOEE_API_KEY` via environment variables, eliminating the need to commit real API keys into `config.json`.
- **Windows Console Encoding**: Configured `sys.stdout` and `sys.stderr` to use UTF-8 with replacement fallback in `core/gpm_api.py` to eliminate `cp1252` UnicodeEncodeError crashes on Windows consoles.
- **Git Ignore Whitelist (`.gitignore`)**: Explicitly whitelisted canonical project documentation (`AGENTS.md`, `CHANGELOG.md`, `docs/**`) while ignoring temporary agent scratch files.

---

## [1.0.0] - 2026-03-15

### Added
- Initial implementation of the 5 architectural pillars for Sunflower Land RPA.
- Win32 `user32.dll` SendInput human mouse simulation with Bézier curves, micro-jitter, and fumble click logic.
- Sequential GPM-Login v2 REST API connector with CDP browser evaluation.
- Behavioral engine featuring 33 distinct Vietnamese personas and circadian time-slot clustering.
- AI Vision integration using Claude Haiku and local template-matching fallback.
- Fail-safe Captcha emergency brake and sound alarm guard.
- Core automated task managers: `CropManager`, `MushroomHunter`, `FarmMaintenance`.
