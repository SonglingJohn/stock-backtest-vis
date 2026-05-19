# A Share Backtest Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable local A-share backtest storyboard workbench with AKShare-backed data, a pure tested engine, and animated frontend playback.

**Architecture:** Keep calculation pure and testable in `backend/backtest.py`, isolate AKShare and caching in `backend/data_source.py`, expose a small local HTTP API from `backend/server.py`, and serve static frontend files from `frontend/`.

**Tech Stack:** Python standard library backend server, optional AKShare dependency for live data, vanilla HTML/CSS/JavaScript frontend, `unittest` tests.

---

### Task 1: Pure Backtest Engine

**Files:**
- Create: `backend/backtest.py`
- Create: `tests/test_backtest.py`

- [ ] Write unit tests for one-time buy, annual fixed investment, allocation defaults, and summary metrics.
- [ ] Run `python -m unittest tests.test_backtest -v` and verify tests fail because `backend.backtest` is missing.
- [ ] Implement `backend/backtest.py` with pure functions and dataclasses.
- [ ] Run `python -m unittest tests.test_backtest -v` and verify tests pass.

### Task 2: Data Source Adapter

**Files:**
- Create: `backend/data_source.py`
- Create: `requirements.txt`

- [ ] Implement AKShare import, `stock_zh_a_hist` call with `adjust="qfq"`, and local JSON cache.
- [ ] Return normalized price rows shaped like `{"date": "YYYY-MM-DD", "close": 12.34}`.
- [ ] Raise clear runtime errors for missing dependency or empty data.

### Task 3: Local HTTP API

**Files:**
- Create: `backend/server.py`
- Create: `backend/__init__.py`

- [ ] Serve `frontend/index.html` and static assets.
- [ ] Add `POST /api/backtest` to validate input, fetch data, run the engine, and return JSON.
- [ ] Add `GET /api/health`.

### Task 4: Playback Frontend

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/styles.css`
- Create: `frontend/app.js`

- [ ] Build stock row editor with stock code, percent, add, and remove.
- [ ] Build buying method, amount, and year range controls.
- [ ] Render the top story sentence with dynamic year.
- [ ] Collapse the parameter panel during playback and allow expanding it again.
- [ ] Animate SVG valuation curves year by year and support direct result mode.

### Task 5: Verification

**Files:**
- Modify as needed based on verification findings.

- [ ] Run unit tests.
- [ ] Run a static syntax check with `python -m py_compile backend/*.py`.
- [ ] Start the local server and confirm the health endpoint responds.
