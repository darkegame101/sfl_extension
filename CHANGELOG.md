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
- **Single-Profile Execution CLI (`run.py`)**: Added `--profile` / `-p` and `--config` / `-c` arguments for targeted on-demand execution on specific profiles.
- **Automated WindowHelper Tests (`tests/test_window_helper.py`)**: Added unit tests covering interactive desktop switching, PID window detection, and coordinate transformations.
- **Automated FarmMaintenance Tests (`tests/test_farm_maintenance.py`)**: Added unit tests validating the 3-hit tree chopping invariant, human fumble recovery, and 2-hour tree respawn cooldown (suite expanded to 46 tests).
- **Web-based GPM Controller & Test Center (`gpm_ui.py`)**: Local web dashboard running on port 18888 for controlling profiles, inspecting CDP tabs, and live testing.
- **Evidence-Based Perception & Closed-Loop Verification (`core/evidence_engine.py`) [Branch 1]**:
  - Implemented POMDP belief state modeling (`PlotBelief`, `EnvironmentBeliefState`) based on Kurniawati (2022).
  - Bayesian multi-source evidence fusion (`EvidenceFuser`) fusing LocalVision (HSV/OpenCV) and Cloud VLM (Claude Haiku 5.5) with conflict penalties.
  - Explicit Abstention Policy halting automation on Captcha, game syncing, or uncertainty > 50%.
  - OSWorld-style verifiable predicate engine (`TaskVerifier`, Xie et al., NeurIPS 2024) asserting strict pre/post-conditions on harvest and planting actions.
- **Goal Hierarchy, Task Resumption & State-Aware Scheduling (`scheduler/goal_tracker.py`) [Branch 2, C3.1, C5]**:
  - Implemented ACT-R cognitive goal decomposition (`GoalTracker`, `SubGoal`) following Ritter et al. (WIREs 2019).
  - Problem state serialization (`TaskCheckpoint`) based on Borst et al. (CHI 2015) problem state bottleneck.
  - Enforced single active subgoal policy and bounded valid transitions table (`VALID_GOAL_TRANSITIONS`).
  - Added `COMMANDS_ISSUED` and `SKIPPED` goal statuses; decoupled command issuance from post-condition verification.
  - Resolved `active_index` drift upon out-of-order completions via `_sync_active_index_after_terminal`.
  - Added `fail_subgoal`, `skip_subgoal`, `abort_subgoal`, `record_commands_issued`, and `interrupt_active_subgoal` APIs.
  - Memory for Goals reconciler (`TaskResumptionManager`, Trafton & Altmann 2003) comparing checkpoints with observed environment belief to resume partial harvests/planting, abstaining on uncertainty, and replanning adaptively when observed belief contradicts stale checkpoints.
  - Backward-compatible legacy checkpoint parsing in `get_verified_action` ensuring unverified actions are never promoted to verified.
- **Precision Hardware Mouse Win32 Contract & In-Place Clicking (`core/human_mouse.py`) [C1]**:
  - Declared strict ctypes `argtypes` and `restype` for Win32 `user32.SendInput`.
  - Implemented `click_in_place(button='left')` bypassing trajectory recalculation for repeated multi-clicks.
  - Added unit test suite `tests/test_human_mouse_api.py` validating exact `INPUT` structures, `dwFlags` order (down before up), and return contracts.
- **CropManager Error Handling & Memory Consistency (`tasks/crop_manager.py`) [C2, C2.3]**:
  - Added immediate abort upon tool selection failure (`TOOL_SELECTION_FAILED`), skipping clicks and preventing invalid memory mutations.
  - Wrapped plot operations in exception-safe reporting returning `commands_attempted`, `commands_issued`, and `PARTIALLY_EXECUTED` / `FAILED` statuses without hiding partial actions.
  - Added `record_memory` flag, preventing memory corruption when 0 clicks succeed or errors occur mid-loop.
  - Added comprehensive test suite `tests/test_crop_manager.py` (18 unit tests).
- **Unified Task Return & Verification Contract (`tasks/`, `run.py`, `tests/test_audit_and_verification.py`) [C4]**:
  - Standardized task return contracts across `crop_manager.py` and `farm_maintenance.py` to distinguish `COMMANDS_ISSUED`, `PARTIALLY_EXECUTED`, `FAILED`, and `NOOP`, explicitly marking `verified: False`.
  - Maintained memory consistency by marking planting unverified until post-verification confirmation (`mark_planting_verified`).
- **Atomic Checkpoint Persistence (`scheduler/farm_memory.py`)**: Added `save_checkpoint()`, `get_checkpoint()`, and `clear_checkpoint()` with atomic `.tmp -> os.replace` guarantees.
- **Automated Unit Tests Expanded (108 tests passing)**: Full suite passes deterministically offline across all modules.

### Changed
- **3-Hit Tree Chopping Rule & Human Fumble Recovery (`tasks/farm_maintenance.py`)**: Updated `chop_trees` to strictly require exactly 3 successful hits per tree in alignment with Sunflower Land mechanics. If a human miss/fumble click occurs, the agent automatically recovers and delivers compensation strikes until all 3 hits land on the tree.
- **Tree Respawn Cooldown Tracking (`scheduler/farm_memory.py`, `run.py`)**: Added `record_tree_chop` and `is_tree_ready_for_chop` to track the 2-hour tree recovery window and prevent wasteful clicking on tree stumps.
- **Windows Multi-Desktop & Sandbox Window Resolution (`core/window_helper.py`)**: `WindowHelper` now automatically attaches threads to `WinSta0\default` via `OpenDesktopW` / `SetThreadDesktop` and uses 64-bit safe `EnumDesktopWindows`, eliminating invisible window enumeration failures across Windows service and IDE sandbox environments.
- **PID-Based Window Detection & CDP Navigation (`run.py`, `core/window_helper.py`)**: Resolved windows directly by browser Process ID and automatically navigated active tabs to `https://sunflower-land.com/play/` via Chrome DevTools Protocol when newly opened tabs are detected.
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
