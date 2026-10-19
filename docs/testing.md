# Testing Strategy & Verification Guide

This document specifies the testing strategy, test suite architecture, execution commands, and verification procedures for `sfl_extension` / `sfland auto`.

---

## 1. Test Suite Architecture

The test suite is built on Python's standard `unittest` framework and located in `tests/`:

| Test Module | Coverage Scope | Determinism / Mocking |
| :--- | :--- | :--- |
| **`test_gpm_api.py`** | GpmAPI REST calls, profile start/stop, profile name resolution, CDP evaluation, and live GPM connectivity. | Mock HTTP sessions for unit tests; conditional live test if GPM is running. |
| **`test_ai_validation.py`** | Vision output sanitization, out-of-bounds screen coordinate removal, schema type coercion, and CaptchaGuard fail-safe mode. | 100% deterministic, offline mock fixtures. |
| **`test_behavioral_engine.py`** | Persona generation, persistence immutability, time-slot clustering, and SmartCropSelector logic. | Isolated temporary JSON files (`tempfile.TemporaryDirectory`). |
| **`test_scenario_engine_evaluation.py`** | Archetype diversification (all 6 archetypes), WFH vs. office occupation weights, fatigue accumulation, and episodic recall. | 100% deterministic, synthetic scenario seeds. |
| **`test_fitts_law.py`** | Human mouse kinematics, Fitts' law travel duration, overshoot deceleration, and Bézier curvature bounds. | Pure numerical computation without OS window dependency. |
| **`test_audit_and_verification.py`** | Closed-loop pre/post verification logic, decoupled `execution_status` vs `verification_status`, perception fail-safe, and cleanup error retention. | Offline JSON validation and mock fixtures. |
| **`test_farm_memory_concurrency.py`** | Concurrent multi-instance writes without lost updates, dead PID stale-lock recovery, active PID lock respect, atomic tmp cleanup, and working tree secret hygiene. | Multi-instance tempfile testing with process lock validation. |
| **`test_evidence_engine.py`** | Branch 1: POMDP Bayesian belief fusion, conflict penalty, abstention policy (Captcha/Sync/Uncertainty), and OSWorld post-condition verification. | 100% deterministic, offline mock fixtures. |
| **`test_goal_tracker.py`** | Branch 2: ACT-R goal hierarchy lifecycle, checkpoint problem state persistence, and discrepancy-based task resumption (Memory for Goals). | 100% deterministic, isolated temporary memory fixtures. |

---

## 2. Test Execution Commands

### Running All Tests
Execute the full discovery suite from the project root:
```powershell
python -m unittest discover tests -v
```

### Running Specific Test Modules
```powershell
# GPM API connector tests (Mock & Live)
python -m unittest tests/test_gpm_api.py -v

# AI Vision validation & Captcha Guard tests
python -m unittest tests/test_ai_validation.py -v

# Behavioral engine & Scenario evaluation
python -m unittest tests/test_behavioral_engine.py -v
python -m unittest tests/test_scenario_engine_evaluation.py -v

# Human mouse kinematics & Fitts' law
python -m unittest tests/test_fitts_law.py -v

# Audit trail, closed-loop verification & perception fail-safe
python -m unittest tests/test_audit_and_verification.py -v

# Concurrency, PID-aware lock & secret hygiene
python -m unittest tests/test_farm_memory_concurrency.py -v

# Branch 1: Evidence Engine (POMDP Belief & OSWorld Verification)
python -m unittest tests/test_evidence_engine.py -v

# Branch 2: Goal Tracker (ACT-R & Memory for Goals Resumption)
python -m unittest tests/test_goal_tracker.py -v

# Secret scanner execution (Rule F)
python scripts/scan_secrets.py
```

### Bytecode Compilation & Syntax Check
Verify that all modules compile without syntax or indentation errors:
```powershell
python -m compileall core scheduler tasks tests run.py gpm_ui.py
```

### Running with PyTest (Optional)
If `pytest` is installed from `requirements-dev.txt`:
```powershell
pytest tests/ -v
```

---

## 3. Mock vs. Live Testing Guidelines

### Offline Mock Tests (Default & Mandatory)
* All unit tests executed during CI or routine checks must run **offline without external dependencies**.
* External HTTP calls to GPM Local API (`http://127.0.0.1:19995`) or OpenAI endpoints must be mocked using `unittest.mock.MagicMock` or `unittest.mock.patch`.
* Tests must never assert that real secrets exist in configuration files.

### Live Integration Tests
* Live tests (such as `TestGpmAPILive` in `test_gpm_api.py`) automatically detect whether GPM-Login is active on `127.0.0.1:19995`.
* If GPM-Login is running, the test connects and verifies real profile retrieval.
* If GPM-Login is not active, the test safely calls `self.skipTest()` instead of failing the build.

---

## 4. End-to-End Automated Diagnostic

The core GPM connector includes an automated 8-step live diagnostic script:
```powershell
python core/gpm_api.py
```
This diagnostic performs the following sequence on an active GPM-Login installation:
1. `GET /v2/profiles`: Verify local API connectivity.
2. `GET /v2/create`: Create temporary profile `__DIAGNOSTIC_TEST__`.
3. `GET /v2/update-note`: Update profile note.
4. `GET /v2/start`: Launch the browser profile.
5. `WebSocket Runtime.evaluate`: Test CDP JavaScript evaluation.
6. `WebSocket Page.captureScreenshot`: Test CDP core screenshot capture.
7. `GET /v2/stop`: Close the browser instance cleanly.
8. `GET /v2/delete`: Clean up and delete the test profile.

---

## 5. Known Coverage Gaps & Limitations

1. **Active Game Window Interactions**: Full end-to-end clicks into Sunflower Land require an active display session (interactive desktop session ID 1). They cannot be fully validated in headless CI runners without a virtual display or RDP session.
2. **Vision API Live Quotas**: Tests validate schema parser and fallback heuristics; live LLM vision calls require an active API key (`AI_VISION_API_KEY`) and are not part of routine automated test suites to avoid costs and latency.
