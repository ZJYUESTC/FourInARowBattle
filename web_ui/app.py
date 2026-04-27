from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as url_error
from urllib import request as url_request

import torch
from flask import Flask, jsonify, render_template, request

# Runtime root that works for both source run and PyInstaller frozen run.
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
    ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from game import Board  # noqa: E402
from mcts_alphaZero import MCTSPlayer  # noqa: E402
from policy_value_net_pytorch import PolicyValueNet  # noqa: E402

BOARD_WIDTH = 6
BOARD_HEIGHT = 6
N_IN_ROW = 4
TOP_K = 5
DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_LLM_MODEL = "deepseek-v4-flash"
DEFAULT_API_KEY = os.environ.get(
    "GOMOKU_DEFAULT_API_KEY",
    "",
).strip()

def resolve_default_model_path() -> Path:
    candidates = [
        ROOT_DIR / "weights_synced" / "best_policy_cpu.model",
        ROOT_DIR / "weights_synced" / "best_policy.model",
        ROOT_DIR / "weights_synced" / "best_policy_6_6_4_torch.model",
        ROOT_DIR / "best_policy.model",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def ui_to_move(row: int, col: int) -> int:
    h = BOARD_HEIGHT - 1 - int(row)
    return h * BOARD_WIDTH + int(col)


def move_to_ui(move: int) -> Tuple[int, int]:
    h = int(move) // BOARD_WIDTH
    col = int(move) % BOARD_WIDTH
    row = BOARD_HEIGHT - 1 - h
    return row, col


def board_to_ui_matrix(board: Board) -> List[List[int]]:
    matrix = [[0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
    for mv, p in board.states.items():
        row, col = move_to_ui(int(mv))
        matrix[row][col] = int(p)
    return matrix


def board_to_text(board: Board, current_player: int) -> str:
    lines: List[str] = []
    header = "    " + " ".join(str(c) for c in range(BOARD_WIDTH))
    lines.append(header)
    for row in range(BOARD_HEIGHT):
        tokens: List[str] = []
        for col in range(BOARD_WIDTH):
            mv = ui_to_move(row, col)
            stone = board.states.get(mv)
            if stone is None:
                tokens.append(".")
            elif int(stone) == int(current_player):
                tokens.append("X")
            else:
                tokens.append("O")
        lines.append(f"{row:<3} " + " ".join(tokens))
    return "\n".join(lines)


def legal_moves_ui(board: Board) -> List[Tuple[int, int]]:
    coords = [move_to_ui(int(mv)) for mv in board.availables]
    coords.sort(key=lambda x: (x[0], x[1]))
    return coords


def fetch_models_from_api(timeout: int = 20) -> List[str]:
    base = DEFAULT_API_BASE.strip().rstrip("/")
    if not base:
        base = DEFAULT_API_BASE
    if not DEFAULT_API_KEY:
        raise RuntimeError("Missing default API key")

    req = url_request.Request(url=base + "/models", method="GET")
    req.add_header("Authorization", f"Bearer {DEFAULT_API_KEY}")
    req.add_header("Content-Type", "application/json")

    try:
        with url_request.urlopen(req, timeout=int(timeout)) as resp:
            body = resp.read().decode("utf-8", "ignore")
    except url_error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "ignore")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {detail[:240]}")
    except Exception as exc:
        raise RuntimeError(f"Request failed: {exc}")

    try:
        obj = json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"Invalid model list response: {exc}")

    raw = obj.get("data", [])
    models: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                mid = str(item.get("id", "")).strip()
                if mid:
                    models.append(mid)
    models = sorted(set(models))
    return models


@dataclass
class AgentSpec:
    kind: str  # human / alphazero / llm
    model: str


class AlphaZeroEngine:
    def __init__(
        self,
        model_path: Path,
        board_width: int,
        board_height: int,
        n_playout: int = 200,
        c_puct: float = 5.0,
    ) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"model not found: {model_path}")

        use_gpu = bool(torch.cuda.is_available())
        self.policy_value_net = PolicyValueNet(
            board_width,
            board_height,
            model_file=str(model_path),
            use_gpu=use_gpu,
        )
        self.player = MCTSPlayer(
            self.policy_value_net.policy_value_fn,
            c_puct=float(c_puct),
            n_playout=int(n_playout),
            is_selfplay=0,
            history_len=1,
        )

    def choose_with_analysis(self, board: Board) -> Tuple[int, Dict[str, Any]]:
        move, move_probs = self.player.get_action(board, temp=1e-3, return_prob=1)
        move = int(move)

        ranked = sorted(
            [(int(mv), float(move_probs[mv])) for mv in board.availables],
            key=lambda x: x[1],
            reverse=True,
        )
        top = ranked[:TOP_K]
        top5 = []
        for idx, (mv, prob) in enumerate(top, start=1):
            row, col = move_to_ui(mv)
            top5.append(
                {
                    "rank": idx,
                    "move": mv,
                    "row": row,
                    "col": col,
                    "confidence": prob,
                }
            )

        selected_row, selected_col = move_to_ui(move)
        selected_conf = float(move_probs[move]) if move < len(move_probs) else 0.0
        analysis = {
            "agent_kind": "alphazero",
            "selected_confidence": selected_conf,
            "selected_row": selected_row,
            "selected_col": selected_col,
            "top5": top5,
        }
        return move, analysis


class LLMEngine:
    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str,
        timeout: Optional[float] = None,
        max_tokens: int = 1200,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_base = (api_base or DEFAULT_API_BASE).strip()
        self.model = (model or DEFAULT_LLM_MODEL).strip()
        self.timeout: Optional[float] = None
        if timeout is not None:
            timeout_val = float(timeout)
            if timeout_val > 0:
                self.timeout = timeout_val
        self.max_tokens = int(max_tokens)

    def _build_prompt(self, board: Board, current_player: int, prompt_lang: str = "zh") -> str:
        legal = legal_moves_ui(board)
        legal_text = ", ".join(f"[{r},{c}]" for r, c in legal)
        lang = "en" if str(prompt_lang or "").strip().lower().startswith("en") else "zh"
        if lang == "en":
            return (
                "You are a Four-in-a-Row master.\n"
                "Please reason using common techniques for this game.\n"
                "Board size: 6x6. Win condition: 4 in a row (NOT 5).\n"
                "Symbols: X=current player, O=opponent, .=empty.\n"
                "You must choose ONE legal move from the legal move list.\n\n"
                "Current board:\n"
                f"{board_to_text(board, current_player)}\n\n"
                f"Legal moves: {legal_text}\n\n"
                "Please provide your full analysis in plain text first.\n"
                "Then in the final line, output exactly this format:\n"
                "FINAL_MOVE: [row,col]\n"
                "Do not output an illegal move."
            )
        return (
            "你是四子棋大师。\n"
            "请根据这个游戏的常见技巧进行分析并选择落子。\n"
            "棋盘大小：6x6。胜利条件：四连（不是五连）。\n"
            "符号说明：X=当前玩家，O=对手，.=空位。\n"
            "你必须只从给出的合法落子列表里选择一步。\n\n"
            "当前棋盘：\n"
            f"{board_to_text(board, current_player)}\n\n"
            f"合法落子：{legal_text}\n\n"
            "请先输出完整分析。\n"
            "最后一行严格输出以下格式：\n"
            "FINAL_MOVE: [row,col]\n"
            "不要输出非法落子。"
        )

    @staticmethod
    def _extract_reasoning_from_msg(msg: Dict[str, Any]) -> str:
        parts: List[str] = []
        for key in ("reasoning_content", "reasoning", "thinking"):
            val = msg.get(key)
            if not val:
                continue
            if isinstance(val, str):
                parts.append(val.strip())
            elif isinstance(val, (list, dict)):
                parts.append(json.dumps(val, ensure_ascii=False))
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _parse_move_from_text(text: str, legal_moves: set[int]) -> Tuple[Optional[int], str]:
        if not text:
            return None, "empty_output"

        patterns = [
            r"FINAL_MOVE\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]",
            r"\[\s*(\d+)\s*,\s*(\d+)\s*\]",
            r"\(\s*(\d+)\s*,\s*(\d+)\s*\)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                row = int(m.group(1))
                col = int(m.group(2))
                if row < 0 or row >= BOARD_HEIGHT or col < 0 or col >= BOARD_WIDTH:
                    continue
                move = ui_to_move(row, col)
                if move in legal_moves:
                    return move, f"parsed_by:{pat}"
        return None, "no_legal_move_found"

    @staticmethod
    def _append_delta_text(dst: str, delta_val: Any) -> str:
        if delta_val is None:
            return dst
        if isinstance(delta_val, str):
            return dst + delta_val
        if isinstance(delta_val, list):
            buf = []
            for it in delta_val:
                if isinstance(it, dict):
                    buf.append(str(it.get("text", "")))
                else:
                    buf.append(str(it))
            return dst + "".join(buf)
        return dst + str(delta_val)

    def _stream_chat_completion(
        self,
        prompt: str,
        progress_cb: Optional[Any] = None,
    ) -> Tuple[str, str]:
        url = self.api_base.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        req = url_request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")

        full_text = ""
        full_reasoning = ""

        if self.timeout is None:
            resp_ctx = url_request.urlopen(req)
        else:
            resp_ctx = url_request.urlopen(req, timeout=self.timeout)
        with resp_ctx as resp:
            ctype = str(resp.headers.get("Content-Type", "")).lower()
            # Non-stream fallback (provider may ignore stream=true)
            if "text/event-stream" not in ctype:
                body = resp.read().decode("utf-8", "ignore")
                obj = json.loads(body)
                msg = obj.get("choices", [{}])[0].get("message", {})
                full_text = str(msg.get("content", ""))
                full_reasoning = self._extract_reasoning_from_msg(msg)
                if callable(progress_cb):
                    progress_cb(full_text, full_reasoning)
                return full_text, full_reasoning

            while True:
                line = resp.readline()
                if not line:
                    break
                s = line.decode("utf-8", "ignore").strip()
                if not s or not s.startswith("data:"):
                    continue
                data_str = s[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                except Exception:
                    continue
                delta = evt.get("choices", [{}])[0].get("delta", {})
                full_text = self._append_delta_text(full_text, delta.get("content"))
                full_reasoning = self._append_delta_text(
                    full_reasoning,
                    delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking"),
                )
                if callable(progress_cb):
                    progress_cb(full_text, full_reasoning)

        return full_text, full_reasoning

    def choose_with_analysis(
        self,
        board: Board,
        current_player: int,
        prompt_lang: str = "zh",
        progress_cb: Optional[Any] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        legal_set = set(int(mv) for mv in board.availables)
        used_lang = "en" if str(prompt_lang or "").strip().lower().startswith("en") else "zh"
        prompt = self._build_prompt(board, current_player=current_player, prompt_lang=used_lang)
        t0 = time.time()

        llm_output = ""
        llm_reasoning = ""
        parse_note = ""
        move: Optional[int] = None
        err_text = ""

        llm_output, llm_reasoning = self._stream_chat_completion(prompt, progress_cb=progress_cb)
        move, parse_note = self._parse_move_from_text(llm_output, legal_set)
        if move is None:
            err_text = f"parse_failed:{parse_note}"
            raise RuntimeError(err_text)

        latency = time.time() - t0
        move = int(move)
        row, col = move_to_ui(move)
        analysis = {
            "agent_kind": "llm",
            "llm_model": self.model,
            "api_base": self.api_base,
            "latency_sec": float(latency),
            "llm_output": llm_output,
            "llm_reasoning": llm_reasoning,
            "prompt_lang": used_lang,
            "parse_note": parse_note,
            "error": err_text,
            "fallback_used": False,
            "fallback_reason": "",
            "selected_row": row,
            "selected_col": col,
            "selected_confidence": None,
            "alpha_fallback_top5": [],
        }
        return move, analysis


class MatchSession:
    def __init__(self, alpha_engine: AlphaZeroEngine) -> None:
        self.alpha_engine = alpha_engine
        self.lock = threading.Lock()
        self.board = Board(width=BOARD_WIDTH, height=BOARD_HEIGHT, n_in_row=N_IN_ROW)
        self.history: List[int] = []
        self.decision_log: List[Dict[str, Any]] = []
        self.last_ai_move: Optional[Tuple[int, int]] = None
        self.start_player_index = 0

        self.mode = "human_vs_ai"  # human_vs_ai / ai_vs_ai
        self.human_player: Optional[int] = 1
        self.api_key = DEFAULT_API_KEY
        self.api_base = DEFAULT_API_BASE
        self.players: Dict[int, AgentSpec] = {
            1: AgentSpec(kind="human", model="Human"),
            2: AgentSpec(kind="alphazero", model="AlphaZero"),
        }
        self.message = "Ready."
        self.ui_lang = "zh"
        self._llm_cache: Dict[Tuple[str, str, str], LLMEngine] = {}
        self.ai_task_running = False
        self.ai_task_error = ""
        self.ai_task_player: Optional[int] = None
        self.ai_live_output = ""
        self.ai_live_reasoning = ""
        self.ai_task_started_at = 0.0

        self._reset_board(start_player_index=0)

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        k = (kind or "").strip().lower()
        if k == "llm":
            return "llm"
        if k == "human":
            return "human"
        return "alphazero"

    def _agent_label(self, player: int) -> str:
        spec = self.players.get(player, AgentSpec(kind="alphazero", model="AlphaZero"))
        if spec.kind == "human":
            return "Human"
        if spec.kind == "llm":
            return f"LLM ({spec.model or DEFAULT_LLM_MODEL})"
        return "AlphaZero"

    def _reset_board(self, start_player_index: int = 0) -> None:
        self.start_player_index = int(start_player_index)
        self.board = Board(width=BOARD_WIDTH, height=BOARD_HEIGHT, n_in_row=N_IN_ROW)
        self.board.init_board(start_player=self.start_player_index)
        self.history = []
        self.decision_log = []
        self.last_ai_move = None
        self.ai_task_running = False
        self.ai_task_error = ""
        self.ai_task_player = None
        self.ai_live_output = ""
        self.ai_live_reasoning = ""
        self.ai_task_started_at = 0.0

    def _current_is_human(self) -> bool:
        if self.mode != "human_vs_ai":
            return False
        if self.human_player is None:
            return False
        return int(self.board.get_current_player()) == int(self.human_player)

    def _winner_text(self, winner: int) -> str:
        if winner == -1:
            return "Draw"
        return f"Player {winner} wins ({self._agent_label(winner)})"

    def _llm_engine_for(self, model: str) -> LLMEngine:
        model_name = (model or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
        key = (self.api_base.strip(), self.api_key.strip(), model_name)
        engine = self._llm_cache.get(key)
        if engine is None:
            if not self.api_key.strip():
                raise RuntimeError("LLM API key is required when using LLM agent")
            engine = LLMEngine(
                api_key=self.api_key,
                api_base=self.api_base,
                model=model_name,
            )
            self._llm_cache[key] = engine
        return engine

    def _append_decision_locked(
        self,
        current_player: int,
        spec: AgentSpec,
        move: int,
        analysis: Dict[str, Any],
    ) -> None:
        self.board.do_move(int(move))
        self.history.append(int(move))
        self.last_ai_move = move_to_ui(int(move))

        row, col = move_to_ui(int(move))
        self.decision_log.append(
            {
                "step": len(self.history),
                "player": current_player,
                "agent_kind": spec.kind,
                "agent_model": spec.model,
                "agent_label": self._agent_label(current_player),
                "move": {"row": row, "col": col, "id": int(move)},
                "analysis": analysis,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self.decision_log = self.decision_log[-40:]

    def _start_ai_task_locked(self) -> None:
        ended, _ = self.board.game_end()
        if ended:
            raise ValueError("Game already ended.")
        if self.ai_task_running:
            raise ValueError("AI is already thinking.")
        if self._current_is_human():
            raise ValueError("It is human turn now.")

        player = int(self.board.get_current_player())
        spec = self.players.get(player, AgentSpec(kind="alphazero", model="AlphaZero"))
        if spec.kind == "human":
            raise ValueError("Current player is human.")

        board_snapshot = copy.deepcopy(self.board)
        self.ai_task_running = True
        self.ai_task_error = ""
        self.ai_task_player = player
        self.ai_live_output = ""
        self.ai_live_reasoning = ""
        self.ai_task_started_at = time.time()
        self.message = f"P{player} ({self._agent_label(player)}) is thinking..."

        def _worker() -> None:
            try:
                if spec.kind == "llm":
                    def _progress_cb(out_text: str, reason_text: str) -> None:
                        with self.lock:
                            self.ai_live_output = out_text[-12000:]
                            self.ai_live_reasoning = reason_text[-12000:]
                    move, analysis = self._llm_engine_for(spec.model).choose_with_analysis(
                        board=board_snapshot,
                        current_player=player,
                        prompt_lang=self.ui_lang,
                        progress_cb=_progress_cb,
                    )
                else:
                    move, analysis = self.alpha_engine.choose_with_analysis(board_snapshot)

                with self.lock:
                    if not self.ai_task_running:
                        return
                    if int(self.board.get_current_player()) != player:
                        self.ai_task_running = False
                        self.ai_task_error = "board state changed during AI thinking"
                        self.ai_task_player = None
                        self.message = self.ai_task_error
                        return
                    if int(move) not in self.board.availables:
                        self.ai_task_running = False
                        self.ai_task_error = "AI returned illegal move (no fallback)"
                        self.ai_task_player = None
                        self.message = self.ai_task_error
                        return
                    self._append_decision_locked(player, spec, int(move), analysis)
                    ended, winner = self.board.game_end()
                    if ended:
                        self.message = self._winner_text(winner)
                    else:
                        self.message = "AI step executed."
                    self.ai_task_running = False
                    self.ai_task_player = None
            except Exception as exc:
                with self.lock:
                    self.ai_task_running = False
                    self.ai_task_error = str(exc)
                    self.ai_task_player = None
                    self.message = f"AI error: {exc}"

        threading.Thread(target=_worker, daemon=True).start()

    def _payload_players(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for p in (1, 2):
            spec = self.players.get(p, AgentSpec(kind="alphazero", model="AlphaZero"))
            out[str(p)] = {
                "kind": spec.kind,
                "model": spec.model,
                "label": self._agent_label(p),
            }
        return out

    def state_payload(self) -> Dict[str, Any]:
        ended, winner = self.board.game_end()
        current_player = int(self.board.get_current_player())
        is_human_turn = (not ended) and self._current_is_human()
        return {
            "board": board_to_ui_matrix(self.board),
            "width": BOARD_WIDTH,
            "height": BOARD_HEIGHT,
            "n_in_row": N_IN_ROW,
            "match_mode": self.mode,
            "players": self._payload_players(),
            "human_player": self.human_player,
            "current_player": current_player,
            "is_human_turn": bool(is_human_turn),
            "is_ai_turn": bool((not ended) and (not is_human_turn)),
            "finished": bool(ended),
            "winner": int(winner),
            "winner_text": self._winner_text(int(winner)),
            "history_len": len(self.history),
            "start_player_index": int(self.start_player_index),
            "last_ai_move": (
                {"row": self.last_ai_move[0], "col": self.last_ai_move[1]}
                if self.last_ai_move is not None
                else None
            ),
            "message": self.message,
            "ui_lang": self.ui_lang,
            "api_base": self.api_base,
            "decision_log": self.decision_log[-30:],
            "ai_task_running": bool(self.ai_task_running),
            "ai_task_error": self.ai_task_error,
            "ai_task_player": self.ai_task_player,
            "ai_live_output": self.ai_live_output,
            "ai_live_reasoning": self.ai_live_reasoning,
            "ai_task_elapsed_sec": (
                float(time.time() - self.ai_task_started_at)
                if self.ai_task_running and self.ai_task_started_at > 0
                else 0.0
            ),
        }

    def new_game(
        self,
        match_mode: str,
        human_side: str,
        ui_lang: str,
        api_key: str,
        api_base: str,
        human_ai_kind: str,
        human_ai_model: str,
        ai1_kind: str,
        ai1_model: str,
        ai2_kind: str,
        ai2_model: str,
    ) -> Dict[str, Any]:
        with self.lock:
            self.mode = "ai_vs_ai" if match_mode == "ai_vs_ai" else "human_vs_ai"
            self.ui_lang = "en" if str(ui_lang or "").strip().lower().startswith("en") else "zh"
            # API credentials are fixed by server defaults as requested.
            self.api_key = DEFAULT_API_KEY
            self.api_base = DEFAULT_API_BASE
            self._llm_cache = {}

            if self.mode == "human_vs_ai":
                side = (human_side or "black").strip().lower()
                if side not in ("black", "white", "random"):
                    side = "random"
                if side == "black":
                    self.human_player = 1
                elif side == "white":
                    self.human_player = 2
                else:
                    self.human_player = random.choice([1, 2])

                ai_player = 2 if self.human_player == 1 else 1
                ai_kind = self._normalize_kind(human_ai_kind)
                ai_model = (human_ai_model or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL

                self.players = {
                    int(self.human_player): AgentSpec(kind="human", model="Human"),
                    ai_player: AgentSpec(kind=ai_kind, model=ai_model if ai_kind == "llm" else "AlphaZero"),
                }
            else:
                self.human_player = None
                p1_kind = self._normalize_kind(ai1_kind)
                p2_kind = self._normalize_kind(ai2_kind)
                p1_model = (ai1_model or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
                p2_model = (ai2_model or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
                self.players = {
                    1: AgentSpec(kind=p1_kind, model=p1_model if p1_kind == "llm" else "AlphaZero"),
                    2: AgentSpec(kind=p2_kind, model=p2_model if p2_kind == "llm" else "AlphaZero"),
                }

            self._reset_board(start_player_index=0)
            self.message = "New game started."

            # If human-vs-AI and AI is first, start AI task automatically.
            if self.mode == "human_vs_ai" and (not self._current_is_human()):
                self._start_ai_task_locked()
            elif self.mode == "ai_vs_ai":
                self.message = "AI vs AI ready. Use AI Step or Auto Play."
            else:
                self.message = "Your turn."

            return self.state_payload()

    def play_human_move(self, row: int, col: int, ui_lang: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            if ui_lang is not None:
                self.ui_lang = "en" if str(ui_lang).strip().lower().startswith("en") else "zh"
            ended, _ = self.board.game_end()
            if ended:
                raise ValueError("Game already ended. Please start a new game.")
            if self.mode != "human_vs_ai":
                raise ValueError("Current mode is AI vs AI. Human moves are disabled.")
            if not self._current_is_human():
                raise ValueError("Not human turn.")
            if row < 0 or row >= BOARD_HEIGHT or col < 0 or col >= BOARD_WIDTH:
                raise ValueError("Move out of board.")

            move = ui_to_move(row, col)
            if move not in self.board.availables:
                raise ValueError("Cell already occupied.")

            self.board.do_move(move)
            self.history.append(move)

            ended, winner = self.board.game_end()
            if ended:
                self.message = self._winner_text(winner)
                return self.state_payload()

            # Start AI thinking asynchronously so the frontend can show live output.
            self._start_ai_task_locked()
            return self.state_payload()

    def ai_step(self, ui_lang: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            if ui_lang is not None:
                self.ui_lang = "en" if str(ui_lang).strip().lower().startswith("en") else "zh"
            self._start_ai_task_locked()
            return self.state_payload()

    def auto_play(self, max_steps: int = 200, ui_lang: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            if ui_lang is not None:
                self.ui_lang = "en" if str(ui_lang).strip().lower().startswith("en") else "zh"
            self._start_ai_task_locked()
            payload = self.state_payload()
            payload["auto_steps"] = 1
            return payload

    def undo(self) -> Dict[str, Any]:
        with self.lock:
            if self.ai_task_running:
                raise ValueError("AI is thinking. Stop and wait before undo.")
            if not self.history:
                raise ValueError("No moves to undo.")

            if self.mode == "human_vs_ai" and len(self.history) >= 2:
                remove_steps = 2
            else:
                remove_steps = 1

            replay = list(self.history[:-remove_steps])
            self._reset_board(start_player_index=self.start_player_index)
            for mv in replay:
                if mv in self.board.availables:
                    self.board.do_move(mv)
                    self.history.append(mv)

            self.decision_log = []
            self.last_ai_move = None
            self.ai_live_output = ""
            self.ai_live_reasoning = ""
            self.ai_task_error = ""
            self.message = "Undid move(s). Thinking log cleared."
            return self.state_payload()


def create_app() -> Flask:
    model_path = Path(os.environ.get("GOMOKU_MODEL_PATH", str(resolve_default_model_path())))
    alpha_engine = AlphaZeroEngine(
        model_path=model_path,
        board_width=BOARD_WIDTH,
        board_height=BOARD_HEIGHT,
        n_playout=int(os.environ.get("GOMOKU_N_PLAYOUT", "200")),
        c_puct=float(os.environ.get("GOMOKU_C_PUCT", "5.0")),
    )
    session = MatchSession(alpha_engine=alpha_engine)

    web_ui_dir = ROOT_DIR / "web_ui"
    if not web_ui_dir.exists():
        web_ui_dir = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(web_ui_dir / "templates"),
        static_folder=str(web_ui_dir / "static"),
    )

    @app.get("/")
    def index() -> Any:
        return render_template("index.html")

    @app.get("/api/health")
    def health() -> Any:
        return jsonify(
            {
                "ok": True,
                "model_path": str(model_path),
                "board_width": BOARD_WIDTH,
                "board_height": BOARD_HEIGHT,
                "n_in_row": N_IN_ROW,
                "default_api_base": DEFAULT_API_BASE,
                "default_llm_model": DEFAULT_LLM_MODEL,
                "has_default_api_key": bool(DEFAULT_API_KEY),
            }
        )

    @app.get("/api/state")
    def state() -> Any:
        return jsonify({"ok": True, "state": session.state_payload()})

    @app.post("/api/models")
    def models() -> Any:
        try:
            model_ids = fetch_models_from_api(timeout=20)
            return jsonify({"ok": True, "models": model_ids})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "models": []}), 400

    @app.post("/api/new_game")
    def new_game() -> Any:
        data = request.get_json(silent=True) or {}
        try:
            state_data = session.new_game(
                match_mode=str(data.get("match_mode", "human_vs_ai")).strip().lower(),
                human_side=str(data.get("human_side", "black")).strip().lower(),
                ui_lang=str(data.get("ui_lang", "zh")).strip().lower(),
                api_key="",
                api_base=DEFAULT_API_BASE,
                human_ai_kind=str(data.get("human_ai_kind", "alphazero")),
                human_ai_model=str(data.get("human_ai_model", DEFAULT_LLM_MODEL)),
                ai1_kind=str(data.get("ai1_kind", "alphazero")),
                ai1_model=str(data.get("ai1_model", DEFAULT_LLM_MODEL)),
                ai2_kind=str(data.get("ai2_kind", "alphazero")),
                ai2_model=str(data.get("ai2_model", DEFAULT_LLM_MODEL)),
            )
            return jsonify({"ok": True, "state": state_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "state": session.state_payload()}), 400

    @app.post("/api/move")
    def move() -> Any:
        data = request.get_json(silent=True) or {}
        if "row" not in data or "col" not in data:
            return jsonify({"ok": False, "error": "Missing row/col"}), 400
        try:
            row = int(data["row"])
            col = int(data["col"])
            state_data = session.play_human_move(
                row=row,
                col=col,
                ui_lang=str(data.get("ui_lang", "")).strip().lower() or None,
            )
            return jsonify({"ok": True, "state": state_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "state": session.state_payload()}), 400

    @app.post("/api/ai_step")
    def ai_step() -> Any:
        data = request.get_json(silent=True) or {}
        try:
            state_data = session.ai_step(ui_lang=str(data.get("ui_lang", "")).strip().lower() or None)
            return jsonify({"ok": True, "state": state_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "state": session.state_payload()}), 400

    @app.post("/api/auto_play")
    def auto_play() -> Any:
        data = request.get_json(silent=True) or {}
        max_steps = int(data.get("max_steps", 200))
        try:
            state_data = session.auto_play(
                max_steps=max_steps,
                ui_lang=str(data.get("ui_lang", "")).strip().lower() or None,
            )
            return jsonify({"ok": True, "state": state_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "state": session.state_payload()}), 400

    @app.post("/api/undo")
    def undo() -> Any:
        try:
            state_data = session.undo()
            return jsonify({"ok": True, "state": state_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "state": session.state_payload()}), 400

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7860, debug=False)
