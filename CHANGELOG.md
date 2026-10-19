# Changelog

All notable changes to the `sfl_extension` / `sfland auto` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Repository Engineering Governance (`AGENTS.md`)**: Established mandatory, enforceable engineering guidelines for all AI coding agents working on the codebase (Rules A–H, 7-step task workflow, response format).
- **Automated CI Workflow (`.github/workflows/ci.yml`)**: Continuous integration testing across Python 3.10, 3.11, and 3.12 on Windows runners with automated secret scanning step.
- **Dependency Manifests (`requirements.txt`, `requirements-dev.txt`)**: Explicit runtime dependencies including `opencv-python>=4.8.0` and `numpy>=1.24.0`.
- **Secret Scanner Utility (`scripts/scan_secrets.py`)**: Repository-wide scanner detecting committed credentials, API keys, and secret tokens in compliance with Rule F.
- **Persistence Concurrency & PID-Aware Locking**: Process locks in `FarmMemory` and `ScenarioEngine` now store the owning PID and verify process liveness (`_is_pid_alive`), preventing active lock preemption while cleanly reclaiming stale locks from terminated processes.
- **Automated Concurrency & Secret Hygiene Tests (`tests/test_farm_memory_concurrency.py`)**: 5 new automated tests verifying concurrent updates without lost data, dead PID lock reclamation, active lock timeout, atomic tmp cleanup, and working tree secret hygiene.
- **Documentation Suite (`docs/`)**:
  - `docs/architecture.md`: Comprehensive system architecture, module boundaries, data flows, closed-loop verification, and HCI behavioral modeling.
  - `docs/testing.md`: Test strategy, test matrix, mock vs. live execution, and regression verification commands.
  - `docs/configuration.md`: Configuration schema, environment variables, default settings, and security guidelines.
- **Profile Name Resolution in GpmAPI (`core/gpm_api.py`)**: Added `find_profile_by_name()`, `start_profile_by_name()`, and `stop_profile_by_name()` to map human-readable profile names directly to GPM UUIDs.
- **Automated Unit & Live Test Suite (`tests/test_gpm_api.py`)**: Added 7 comprehensive tests covering mock HTTP sessions and live GPM-Login connectivity.
- **Web-based GPM Controller & Test Center (`gpm_ui.py`)**: Local web dashboard running on port 18888 for controlling profiles, inspecting CDP tabs, and live testing.

### Changed
- **Closed-Loop Verification & False-Positive Elimination (`run.py`)**: Refactored post-condition verification to inspect all configured farm plots, require positive evidence of crop growth (`growing_count > 0 and empty_count == 0`), handle partial states, and classify outcomes into `VERIFIED_SUCCESS`, `VERIFIED_PARTIAL`, `VERIFIED_FAILED`, or `UNVERIFIED`.
- **Perception Failure Fail-Safe (`run.py`)**: Abort immediately with `ABORTED_PERCEPTION_FAILURE` and `VERIFICATION_SKIPPED_NO_SCREENSHOT` if screen capture or AI analysis fails, halting blind mouse operations.
- **Decoupled Execution and Verification Statuses (`run.py`)**: Audit logging now independently records `execution_status`, `verification_status`, and `cleanup_error`.
- **Exception-Safe Browser Cleanup (`run.py`)**: Wrapped `GpmAPI.stop_profile()` inside `finally` with isolated try/except handling to preserve primary execution exceptions.
- **Atomic Locked Mutation (`scheduler/farm_memory.py`, `scheduler/scenario_engine.py`)**: Data is re-read from disk inside the locked critical section before writing, eliminating lost update race conditions between concurrent instances.
- **Windows Console Encoding**: Configured `sys.stdout` and `sys.stderr` to use UTF-8 with replacement fallback across all modules to eliminate `cp1252` UnicodeEncodeError crashes on Windows consoles.
- **Git Ignore Whitelist (`.gitignore`)**: Explicitly whitelisted canonical project documentation (`AGENTS.md`, `CHANGELOG.md`, `docs/**`) while ignoring temporary agent scratch files.

### Security
- **Credential Scrubbing & Rule F Compliance**: Stripped API keys from `config.json`, tightened `test_config_ai_vision_loaded()` to assert empty committed keys, and integrated secret scanning into CI workflow.
- **Compromised Key Warning**: Identified historical commits `b51371f` and `1cff8b7` containing Beeknoee API key `sk-bee-...` on remote repository; flagged for immediate provider revocation and rotation.

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
