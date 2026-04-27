# FourInARowBattle

A minimal standalone web project for 6x6 Four-in-a-Row (Connect Four style) Human/AI and AI/AI battles.

## Quick Start

1. Double-click `run.bat`
2. Open [http://127.0.0.1:7860](http://127.0.0.1:7860)

## Environment Setup

- OS: Windows (project includes `run.bat`)
- Python: 3.11 recommended
- Core dependencies: Flask, PyTorch, NumPy

Create and install environment:

- `py -3.11 -m venv .venv`
- `.venv\Scripts\python -m pip install -U pip`
- `.venv\Scripts\python -m pip install -r requirements.txt`

Set environment variables (PowerShell example):

- `$env:GOMOKU_DEFAULT_API_KEY="your_dashscope_api_key"` (required when using LLM agent)
- `$env:GOMOKU_MODEL_PATH="D:\FourInARowBattle_share\weights_synced\best_policy_cpu.model"` (optional)
- `$env:GOMOKU_HOST="127.0.0.1"` (optional, default `127.0.0.1`)
- `$env:GOMOKU_PORT="7860"` (optional, default `7860`)
- `$env:GOMOKU_N_PLAYOUT="200"` (optional, AlphaZero search count)
- `$env:GOMOKU_C_PUCT="5.0"` (optional, AlphaZero exploration weight)

Start manually (optional):

- `.venv\Scripts\python -m web_ui.launcher`

## Notes

- Default model weight: `weights_synced/best_policy_cpu.model`
- Fill your own Aliyun DashScope API key in `web_ui/app.py` at:
  - `DEFAULT_API_KEY = os.environ.get("GOMOKU_DEFAULT_API_KEY", "")`
- Recommended: set environment variable `GOMOKU_DEFAULT_API_KEY` instead of hardcoding.
- If `.venv` does not exist, create it and install dependencies:
  - `py -3.11 -m venv .venv`
  - `.venv\Scripts\python -m pip install -U pip`
  - `.venv\Scripts\python -m pip install -r requirements.txt`

