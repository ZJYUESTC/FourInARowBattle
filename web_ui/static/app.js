const boardEl = document.getElementById("board");
const statusLineEl = document.getElementById("statusLine");
const messageLineEl = document.getElementById("messageLine");
const thinkingPanelEl = document.getElementById("thinkingPanel");

const langEl = document.getElementById("lang");
const matchModeEl = document.getElementById("matchMode");
const loadModelsBtn = document.getElementById("loadModelsBtn");
const modelLoadInfoEl = document.getElementById("modelLoadInfo");

const humanVsAiPanel = document.getElementById("humanVsAiPanel");
const aiVsAiPanel = document.getElementById("aiVsAiPanel");

const humanSideEl = document.getElementById("humanSide");
const humanAiKindEl = document.getElementById("humanAiKind");
const humanAiModelEl = document.getElementById("humanAiModel");
const ai1KindEl = document.getElementById("ai1Kind");
const ai1ModelEl = document.getElementById("ai1Model");
const ai2KindEl = document.getElementById("ai2Kind");
const ai2ModelEl = document.getElementById("ai2Model");

const newGameBtn = document.getElementById("newGameBtn");
const undoBtn = document.getElementById("undoBtn");
const aiStepBtn = document.getElementById("aiStepBtn");
const autoPlayBtn = document.getElementById("autoPlayBtn");
const stopAutoBtn = document.getElementById("stopAutoBtn");

let state = null;
let busy = false;
let autoPlayActive = false;
let currentLang = "zh";

const I18N = {
  zh: {
    title: "四子棋对战平台",
    subtitle: "支持人机对战与机机对战，支持 AlphaZero 与 API 大模型。",
    langLabel: "语言 / Language",
    matchModeLabel: "对战模式",
    modeHumanVsAi: "人机对战",
    modeAiVsAi: "机机对战",
    apiSourceLabel: "API 来源",
    apiSourceText: "DashScope Compatible API（默认后端密钥）",
    loadModelsBtn: "加载 API 模型列表",
    humanVsAiTitle: "人机对战设置",
    humanSideLabel: "人类执子",
    humanSideBlack: "黑棋先手",
    humanSideWhite: "白棋后手",
    humanSideRandom: "随机",
    humanAiKindLabel: "机器人类型",
    aiModelLabel: "模型名（LLM）",
    aiVsAiTitle: "机机对战设置",
    p1Title: "玩家1（黑棋）",
    p2Title: "玩家2（白棋）",
    agentKindLabel: "类型",
    agentAlpha: "AlphaZero",
    agentLlm: "LLM API",
    newGame: "新对局",
    undo: "悔棋",
    aiStep: "AI 走一步",
    autoPlay: "自动对弈",
    stopAuto: "停止自动",
    notesTitle: "说明",
    note1: "AlphaZero 会显示 Top5 候选落子与置信度。",
    note2: "LLM 会显示原始输出全文；若有 reasoning/deep-thinking 字段也会显示。",
    note3: "当前棋盘固定为 6x6，胜利条件为 4 连。",
    thinkingTitle: "机器思考过程",
    statusTurn: "当前行动方",
    statusMode: "模式",
    statusFinished: "对局结束",
    modeHumanVsAiShort: "人机",
    modeAiVsAiShort: "机机",
    errNewGame: "新对局失败",
    errMove: "落子失败",
    errUndo: "悔棋失败",
    errAiStep: "AI 走子失败",
    modelsLoaded: "模型列表已更新",
    modelsLoadFail: "模型列表加载失败",
    alphaTop5: "AlphaZero Top5",
    confidence: "置信度",
    selectedMove: "选中落子",
    llmOutput: "LLM 输出全文",
    llmReasoning: "LLM 深度思考",
    fallback: "回退",
    fallbackYes: "是",
    fallbackNo: "否",
    noThinking: "暂无机器思考记录。",
    liveThinking: "实时思考中"
  },
  en: {
    title: "Gomoku Battle Console",
    subtitle: "Human-vs-AI and AI-vs-AI with AlphaZero or API LLM agents.",
    langLabel: "Language / 语言",
    matchModeLabel: "Match Mode",
    modeHumanVsAi: "Human vs AI",
    modeAiVsAi: "AI vs AI",
    apiSourceLabel: "API Source",
    apiSourceText: "DashScope Compatible API (server default key)",
    loadModelsBtn: "Load API Models",
    humanVsAiTitle: "Human vs AI Settings",
    humanSideLabel: "Human Side",
    humanSideBlack: "Black first",
    humanSideWhite: "White second",
    humanSideRandom: "Random",
    humanAiKindLabel: "AI Type",
    aiModelLabel: "Model Name (LLM)",
    aiVsAiTitle: "AI vs AI Settings",
    p1Title: "Player 1 (Black)",
    p2Title: "Player 2 (White)",
    agentKindLabel: "Type",
    agentAlpha: "AlphaZero",
    agentLlm: "LLM API",
    newGame: "New Game",
    undo: "Undo",
    aiStep: "AI Step",
    autoPlay: "Auto Play",
    stopAuto: "Stop",
    notesTitle: "Notes",
    note1: "AlphaZero displays Top-5 candidates and confidence.",
    note2: "LLM shows full raw output and reasoning/deep-thinking if available.",
    note3: "Board is fixed to 6x6 with 4-in-a-row win condition.",
    thinkingTitle: "Model Thinking Process",
    statusTurn: "Turn",
    statusMode: "Mode",
    statusFinished: "Game Finished",
    modeHumanVsAiShort: "Human-AI",
    modeAiVsAiShort: "AI-AI",
    errNewGame: "Failed to start new game",
    errMove: "Move failed",
    errUndo: "Undo failed",
    errAiStep: "AI step failed",
    modelsLoaded: "Model list updated",
    modelsLoadFail: "Failed to load model list",
    alphaTop5: "AlphaZero Top-5",
    confidence: "Confidence",
    selectedMove: "Selected Move",
    llmOutput: "LLM Full Output",
    llmReasoning: "LLM Reasoning",
    fallback: "Fallback",
    fallbackYes: "Yes",
    fallbackNo: "No",
    noThinking: "No AI thinking records yet.",
    liveThinking: "Live Thinking"
  }
};

function t(key) {
  return I18N[currentLang][key] || I18N.en[key] || key;
}

function setBusy(v) {
  busy = !!v;
  newGameBtn.disabled = busy;
  undoBtn.disabled = busy;
  aiStepBtn.disabled = busy;
  autoPlayBtn.disabled = busy || autoPlayActive;
}

function setAutoPlaying(active) {
  autoPlayActive = !!active;
  autoPlayBtn.disabled = autoPlayActive || busy;
  stopAutoBtn.disabled = !autoPlayActive;
}

function updateVisibilityByMode() {
  const isHumanVsAi = matchModeEl.value === "human_vs_ai";
  humanVsAiPanel.classList.toggle("hidden", !isHumanVsAi);
  aiVsAiPanel.classList.toggle("hidden", isHumanVsAi);
}

function updateModelInputEnabled() {
  humanAiModelEl.disabled = humanAiKindEl.value !== "llm";
  ai1ModelEl.disabled = ai1KindEl.value !== "llm";
  ai2ModelEl.disabled = ai2KindEl.value !== "llm";
}

function applyStaticI18n() {
  document.title = t("title");
  document.getElementById("titleText").textContent = t("title");
  document.getElementById("subtitleText").textContent = t("subtitle");

  document.getElementById("langLabel").textContent = t("langLabel");
  document.getElementById("matchModeLabel").textContent = t("matchModeLabel");
  document.getElementById("modeHumanVsAiOpt").textContent = t("modeHumanVsAi");
  document.getElementById("modeAiVsAiOpt").textContent = t("modeAiVsAi");
  document.getElementById("apiSourceLabel").textContent = t("apiSourceLabel");
  document.getElementById("apiSourceText").textContent = t("apiSourceText");
  loadModelsBtn.textContent = t("loadModelsBtn");

  document.getElementById("humanVsAiTitle").textContent = t("humanVsAiTitle");
  document.getElementById("humanSideLabel").textContent = t("humanSideLabel");
  document.getElementById("humanSideBlackOpt").textContent = t("humanSideBlack");
  document.getElementById("humanSideWhiteOpt").textContent = t("humanSideWhite");
  document.getElementById("humanSideRandomOpt").textContent = t("humanSideRandom");
  document.getElementById("humanAiKindLabel").textContent = t("humanAiKindLabel");
  document.getElementById("humanAiModelLabel").textContent = t("aiModelLabel");

  document.getElementById("aiVsAiTitle").textContent = t("aiVsAiTitle");
  document.getElementById("p1Title").textContent = t("p1Title");
  document.getElementById("p2Title").textContent = t("p2Title");
  document.getElementById("ai1KindLabel").textContent = t("agentKindLabel");
  document.getElementById("ai1ModelLabel").textContent = t("aiModelLabel");
  document.getElementById("ai2KindLabel").textContent = t("agentKindLabel");
  document.getElementById("ai2ModelLabel").textContent = t("aiModelLabel");

  document.getElementById("agentAlphaOpt1").textContent = t("agentAlpha");
  document.getElementById("agentLlmOpt1").textContent = t("agentLlm");
  document.getElementById("agentAlphaOpt2").textContent = t("agentAlpha");
  document.getElementById("agentLlmOpt2").textContent = t("agentLlm");
  document.getElementById("agentAlphaOpt3").textContent = t("agentAlpha");
  document.getElementById("agentLlmOpt3").textContent = t("agentLlm");

  newGameBtn.textContent = t("newGame");
  undoBtn.textContent = t("undo");
  aiStepBtn.textContent = t("aiStep");
  autoPlayBtn.textContent = t("autoPlay");
  stopAutoBtn.textContent = t("stopAuto");

  document.getElementById("thinkingTitle").textContent = t("thinkingTitle");
  document.getElementById("notesTitle").textContent = t("notesTitle");
  document.getElementById("note1").textContent = t("note1");
  document.getElementById("note2").textContent = t("note2");
  document.getElementById("note3").textContent = t("note3");
}

function statusText(stateData) {
  if (stateData.finished) {
    return `${t("statusFinished")}: ${stateData.winner_text}`;
  }
  const modeText = stateData.match_mode === "ai_vs_ai" ? t("modeAiVsAiShort") : t("modeHumanVsAiShort");
  const turnPlayer = stateData.current_player;
  const turnLabel = stateData.players && stateData.players[String(turnPlayer)]
    ? stateData.players[String(turnPlayer)].label
    : `P${turnPlayer}`;
  let extra = "";
  if (stateData.ai_task_running) {
    extra = ` | ${t("liveThinking")} P${stateData.ai_task_player} ${Number(stateData.ai_task_elapsed_sec || 0).toFixed(1)}s`;
  }
  return `${t("statusMode")}: ${modeText} | ${t("statusTurn")}: P${turnPlayer} (${turnLabel})${extra}`;
}

function renderBoard(stateData) {
  boardEl.innerHTML = "";
  for (let r = 0; r < stateData.height; r += 1) {
    for (let c = 0; c < stateData.width; c += 1) {
      const cell = document.createElement("button");
      cell.className = "cell";
      cell.type = "button";
      const v = stateData.board[r][c];
      if (v === 1 || v === 2) {
        cell.classList.add(v === 1 ? "black" : "white");
        const stone = document.createElement("span");
        stone.className = "stone " + (v === 1 ? "black" : "white");
        cell.appendChild(stone);
      } else {
        cell.classList.add("empty");
      }

      if (
        stateData.last_ai_move &&
        stateData.last_ai_move.row === r &&
        stateData.last_ai_move.col === c
      ) {
        cell.classList.add("last-ai");
      }

      if (!stateData.finished && v === 0 && stateData.is_human_turn && !stateData.ai_task_running) {
        cell.addEventListener("click", () => onCellClick(r, c));
      } else {
        cell.disabled = true;
      }
      boardEl.appendChild(cell);
    }
  }
}

function addKeyValueLine(parent, key, value) {
  const row = document.createElement("div");
  row.className = "kv-line";
  const k = document.createElement("span");
  k.className = "kv-key";
  k.textContent = `${key}:`;
  const v = document.createElement("span");
  v.className = "kv-value";
  v.textContent = value == null ? "-" : String(value);
  row.appendChild(k);
  row.appendChild(v);
  parent.appendChild(row);
}

function stickToBottom(el) {
  if (!el) return;
  const run = () => {
    el.scrollTop = el.scrollHeight;
  };
  run();
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(run);
  }
}

function renderAlphaTop5(container, top5) {
  const title = document.createElement("div");
  title.className = "sub-title";
  title.textContent = t("alphaTop5");
  container.appendChild(title);
  const table = document.createElement("table");
  table.className = "top5-table";
  table.innerHTML = "<thead><tr><th>#</th><th>Move</th><th>" + t("confidence") + "</th></tr></thead>";
  const body = document.createElement("tbody");
  (top5 || []).forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${it.rank}</td><td>[${it.row}, ${it.col}]</td><td>${Number(it.confidence || 0).toFixed(4)}</td>`;
    body.appendChild(tr);
  });
  table.appendChild(body);
  container.appendChild(table);
}

function renderThinkingLog(stateData) {
  thinkingPanelEl.innerHTML = "";

  if (stateData.ai_task_running) {
    const liveCard = document.createElement("article");
    liveCard.className = "think-card";
    const title = document.createElement("div");
    title.className = "think-header";
    title.textContent = `${t("liveThinking")} | P${stateData.ai_task_player}`;
    liveCard.appendChild(title);
    const preOut = document.createElement("pre");
    preOut.className = "llm-output";
    preOut.textContent = stateData.ai_live_output || "";
    liveCard.appendChild(preOut);
    stickToBottom(preOut);
    if (stateData.ai_live_reasoning) {
      const reasonTitle = document.createElement("div");
      reasonTitle.className = "sub-title";
      reasonTitle.textContent = t("llmReasoning");
      liveCard.appendChild(reasonTitle);
      const preR = document.createElement("pre");
      preR.className = "llm-output";
      preR.textContent = stateData.ai_live_reasoning;
      liveCard.appendChild(preR);
      stickToBottom(preR);
    }
    thinkingPanelEl.appendChild(liveCard);
  }

  const logs = stateData.decision_log || [];
  if (!logs.length && !stateData.ai_task_running) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = t("noThinking");
    thinkingPanelEl.appendChild(empty);
    return;
  }

  [...logs].reverse().forEach((entry) => {
    const card = document.createElement("article");
    card.className = "think-card";
    const header = document.createElement("div");
    header.className = "think-header";
    header.textContent = `#${entry.step} | P${entry.player} ${entry.agent_label} | ${t("selectedMove")}: [${entry.move.row}, ${entry.move.col}]`;
    card.appendChild(header);

    const info = document.createElement("div");
    info.className = "think-info";
    addKeyValueLine(info, "Time", entry.timestamp || "-");
    addKeyValueLine(info, "Agent", entry.agent_kind || "-");
    if (entry.agent_model) addKeyValueLine(info, "Model", entry.agent_model);
    card.appendChild(info);

    const analysis = entry.analysis || {};
    if (analysis.agent_kind === "alphazero") {
      addKeyValueLine(info, t("confidence"), analysis.selected_confidence == null ? "-" : Number(analysis.selected_confidence).toFixed(4));
      renderAlphaTop5(card, analysis.top5 || []);
    } else {
      if (analysis.latency_sec != null) addKeyValueLine(info, "Latency(s)", Number(analysis.latency_sec).toFixed(2));

      const outTitle = document.createElement("div");
      outTitle.className = "sub-title";
      outTitle.textContent = t("llmOutput");
      card.appendChild(outTitle);
      const outPre = document.createElement("pre");
      outPre.className = "llm-output";
      outPre.textContent = analysis.llm_output || "";
      card.appendChild(outPre);
      stickToBottom(outPre);

      if (analysis.llm_reasoning) {
        const reasonTitle = document.createElement("div");
        reasonTitle.className = "sub-title";
        reasonTitle.textContent = t("llmReasoning");
        card.appendChild(reasonTitle);
        const reasonPre = document.createElement("pre");
        reasonPre.className = "llm-output";
        reasonPre.textContent = analysis.llm_reasoning;
        card.appendChild(reasonPre);
        stickToBottom(reasonPre);
      }
    }
    thinkingPanelEl.appendChild(card);
  });
}

function render(stateData) {
  state = stateData;
  statusLineEl.textContent = statusText(stateData);
  messageLineEl.textContent = stateData.message || "";
  renderBoard(stateData);
  renderThinkingLog(stateData);
}

async function apiGet(url) {
  const resp = await fetch(url, { method: "GET" });
  return resp.json();
}

async function apiPost(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {})
  });
  const data = await resp.json();
  return { ok: resp.ok, data };
}

function ensureModelOption(selectEl, value) {
  if (!value) return;
  const exists = Array.from(selectEl.options).some((opt) => opt.value === value);
  if (!exists) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    selectEl.appendChild(opt);
  }
}

function updateModelOptions(models) {
  const picks = [humanAiModelEl.value, ai1ModelEl.value, ai2ModelEl.value].filter(Boolean);
  const arr = Array.isArray(models) ? models : [];
  const preferred = ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-v3", "deepseek-r1", "qwen3.5-flash"];
  const merged = [...preferred.filter((m) => arr.includes(m)), ...arr.filter((m) => !preferred.includes(m))];
  const finalModels = merged.length ? merged : ["deepseek-v4-pro", "deepseek-v4-flash"];

  [humanAiModelEl, ai1ModelEl, ai2ModelEl].forEach((el, idx) => {
    const cur = picks[idx] || finalModels[0];
    el.innerHTML = "";
    finalModels.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      el.appendChild(opt);
    });
    ensureModelOption(el, cur);
    el.value = cur;
  });
}

async function loadModels() {
  if (busy) return;
  setBusy(true);
  try {
    const out = await apiPost("/api/models", {});
    if (!out.ok || !out.data.ok) {
      const msg = out.data && out.data.error ? out.data.error : t("modelsLoadFail");
      modelLoadInfoEl.textContent = `${t("modelsLoadFail")}: ${msg}`;
      modelLoadInfoEl.classList.add("error-text");
      return;
    }
    updateModelOptions(out.data.models || []);
    modelLoadInfoEl.textContent = `${t("modelsLoaded")} (${(out.data.models || []).length})`;
    modelLoadInfoEl.classList.remove("error-text");
  } finally {
    setBusy(false);
    updateModelInputEnabled();
  }
}

async function refreshState() {
  const out = await apiGet("/api/state");
  if (out.ok) render(out.state);
}

async function waitAiTaskFinished() {
  while (true) {
    await refreshState();
    if (!state || !state.ai_task_running) {
      return;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
}

function buildNewGamePayload() {
  return {
    ui_lang: currentLang,
    match_mode: matchModeEl.value,
    human_side: humanSideEl.value,
    human_ai_kind: humanAiKindEl.value,
    human_ai_model: humanAiModelEl.value,
    ai1_kind: ai1KindEl.value,
    ai1_model: ai1ModelEl.value,
    ai2_kind: ai2KindEl.value,
    ai2_model: ai2ModelEl.value
  };
}

async function newGame() {
  setAutoPlaying(false);
  setBusy(true);
  try {
    const out = await apiPost("/api/new_game", buildNewGamePayload());
    if (!out.ok || !out.data.ok) {
      alert(out.data && out.data.error ? out.data.error : t("errNewGame"));
      if (out.data && out.data.state) render(out.data.state);
      return;
    }
    render(out.data.state);
    if (state && state.ai_task_running) {
      await waitAiTaskFinished();
      await refreshState();
    }
  } finally {
    setBusy(false);
  }
}

async function undo() {
  setAutoPlaying(false);
  setBusy(true);
  try {
    const out = await apiPost("/api/undo", {});
    if (!out.ok || !out.data.ok) {
      alert(out.data && out.data.error ? out.data.error : t("errUndo"));
    }
    if (out.data && out.data.state) render(out.data.state);
  } finally {
    setBusy(false);
  }
}

async function onCellClick(row, col) {
  if (busy) return;
  setBusy(true);
  try {
    const out = await apiPost("/api/move", { row, col, ui_lang: currentLang });
    if (!out.ok || !out.data.ok) {
      alert(out.data && out.data.error ? out.data.error : t("errMove"));
      if (out.data && out.data.state) render(out.data.state);
      return;
    }
    render(out.data.state);
    if (state && state.ai_task_running) {
      await waitAiTaskFinished();
      await refreshState();
    }
  } finally {
    setBusy(false);
  }
}

async function aiStep() {
  if (busy) return false;
  setBusy(true);
  try {
    const out = await apiPost("/api/ai_step", { ui_lang: currentLang });
    if (!out.ok || !out.data.ok) {
      alert(out.data && out.data.error ? out.data.error : t("errAiStep"));
      if (out.data && out.data.state) render(out.data.state);
      return false;
    }
    render(out.data.state);
    if (state && state.ai_task_running) {
      await waitAiTaskFinished();
      await refreshState();
    }
    return true;
  } finally {
    setBusy(false);
  }
}

async function autoPlayLoop() {
  while (autoPlayActive) {
    await refreshState();
    if (!state || state.finished || !state.is_ai_turn) {
      break;
    }
    const ok = await aiStep();
    if (!ok) break;
    await new Promise((r) => setTimeout(r, 120));
  }
  setAutoPlaying(false);
}

function startAutoPlay() {
  if (busy) return;
  if (!state || state.finished || !state.is_ai_turn) return;
  setAutoPlaying(true);
  autoPlayLoop();
}

function bindEvents() {
  langEl.addEventListener("change", () => {
    currentLang = langEl.value === "en" ? "en" : "zh";
    applyStaticI18n();
    if (state) render(state);
  });
  matchModeEl.addEventListener("change", updateVisibilityByMode);
  humanAiKindEl.addEventListener("change", updateModelInputEnabled);
  ai1KindEl.addEventListener("change", updateModelInputEnabled);
  ai2KindEl.addEventListener("change", updateModelInputEnabled);
  loadModelsBtn.addEventListener("click", loadModels);
  newGameBtn.addEventListener("click", newGame);
  undoBtn.addEventListener("click", undo);
  aiStepBtn.addEventListener("click", aiStep);
  autoPlayBtn.addEventListener("click", startAutoPlay);
  stopAutoBtn.addEventListener("click", () => setAutoPlaying(false));
}

async function bootstrap() {
  currentLang = langEl.value === "en" ? "en" : "zh";
  applyStaticI18n();
  updateVisibilityByMode();
  updateModelInputEnabled();
  setAutoPlaying(false);
  bindEvents();
  updateModelOptions([]);
  await loadModels();
  await refreshState();
}

bootstrap();
