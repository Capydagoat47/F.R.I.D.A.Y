const state = {
  view: "conversation",
  data: null,
  metrics: null,
  listening: false,
  wakeArmed: true,
  ambient: false,
  speaking: false,
  bootComplete: false,
  energy: 0.34,
  audioLevel: 0,
  transcript: "",
  voices: [],
  selectedVoice: null,
  recognition: null,
  micStream: null,
  micContext: null,
  micSource: null,
  micAnalyser: null,
  micProcessor: null,
  voiceResumeAfterSpeech: false,
  voiceFallbackActive: false,
  transcribing: false,
  finalizingVoiceCapture: false,
  recordedChunks: [],
  recordingSampleRate: 0,
  recordingStartedAt: 0,
  recordingLastVoiceAt: 0,
  recordingHeardVoice: false,
  ambientContext: null,
  ambientNodes: [],
  weather: null,
  weatherRequested: false,
  lastEventIds: new Set(),
  modelIndex: 0,
  three: null,
  renderer: null,
  scene: null,
  camera: null,
  threeGroup: null,
  threeOrb: null,
  lastVoiceDispatchAt: 0,
  reducedMotion: window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches || false,
};

const QUICK_COMMANDS = [
  { title: "Natural command", text: "Open browser and search the internet for Friday voice tech", detail: "Try a multi-step command." },
  { title: "Search web", text: "Search the internet for the latest FRIDAY voice tech", detail: "Open a browser search." },
  { title: "Open web app", text: "Open YouTube", detail: "Launch an approved web link." },
  { title: "Power down", text: "Power down", detail: "Put the HUD in standby." },
  { title: "Start timer", text: "Start timer for 5 minutes", detail: "Set a quick countdown." },
  { title: "Screenshot", text: "Take a screenshot", detail: "Capture the desktop." },
  { title: "Download MP4", text: "Download MP4 from https://example.com/video.mp4", detail: "Direct-link downloader." },
  { title: "Add note", text: "Note: cinematic HUD layout", detail: "Store a memory entry." },
  { title: "Security mode", text: "Security mode shield", detail: "Tighten FRIDAY controls." },
  { title: "Call contact", text: "Call Kenan on 5551234", detail: "Launch a phone action." },
  { title: "Summarize file", text: "Summarize file C:\\\\Users\\\\forho\\\\Documents\\\\report.txt", detail: "Read a document." },
  { title: "Switch model", text: "Use model gpt-4o", detail: "Change the active model." },
  { title: "Clear memory", text: "Clear memory", detail: "Reset notes, tasks, and history." },
];

const els = {
  boot: id("boot"),
  bootLog: id("bootLog"),
  bootBar: id("bootBar"),
  shell: id("shell"),
  leftTabs: id("leftTabs"),
  leftPanel: id("leftPanel"),
  rightPanel: id("rightPanel"),
  commandInput: id("commandInput"),
  sendBtn: id("sendBtn"),
  voiceBtn: id("voiceBtn"),
  wakeBtn: id("wakeBtn"),
  ambientBtn: id("ambientBtn"),
  fullBtn: id("fullBtn"),
  clearBtn: id("clearBtn"),
  cloudChip: id("cloudChip"),
  modelChip: id("modelChip"),
  wakeChip: id("wakeChip"),
  ownerChip: id("ownerChip"),
  voiceChip: id("voiceChip"),
  listenChip: id("listenChip"),
  telemetryChip: id("telemetryChip"),
  memoryChip: id("memoryChip"),
  powerChip: id("powerChip"),
  securityChip: id("securityChip"),
  timeChip: id("timeChip"),
  statusLine: id("statusLine"),
  subLine: id("subLine"),
  transcriptLine: id("transcriptLine"),
  memorySummary: id("memorySummary"),
  metricsSummary: id("metricsSummary"),
  voiceSummary: id("voiceSummary"),
  quickSummary: id("quickSummary"),
  toastStack: id("toastStack"),
  waveCanvas: id("waveCanvas"),
  threeStage: id("threeStage"),
  protocolBtn: document.getElementById("protocolBtn"),
protocolMenu: document.getElementById("protocolMenu"),
};

const MODEL_ORDER = [
  "gemini-2.5-flash",
  "gemini-2.5-pro"
];

function id(name) {
  return document.getElementById(name);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function computeRms(samples) {
  if (!samples || !samples.length) {
    return 0;
  }
  let total = 0;
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index];
    total += value * value;
  }
  return Math.sqrt(total / samples.length);
}

function concatFloat32Arrays(chunks) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

function encodeWavBuffer(samples, sampleRate) {
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);

  const writeString = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = 44;
  for (let index = 0; index < samples.length; index += 1) {
    const value = clamp(samples[index], -1, 1);
    view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true);
    offset += bytesPerSample;
  }
  return buffer;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    const slice = bytes.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`GET ${path} failed`);
  }
  return response.json();
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error || data.message || `POST ${path} failed`;
    throw new Error(error);
  }
  return data;
}

function setEnergy(value) {
  state.energy = clamp(value, 0.12, 1);
  document.documentElement.style.setProperty("--energy", state.energy.toFixed(2));
}

function setBootProgress(percent) {
  document.documentElement.style.setProperty("--boot-progress", `${percent}%`);
  if (els.bootBar) {
    els.bootBar.style.width = `${percent}%`;
  }
}

function showToast(title, message) {
  if (!els.toastStack) {
    return;
  }
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
  els.toastStack.prepend(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(12px)";
    setTimeout(() => toast.remove(), 220);
  }, 3200);
}

function formatClock(date = new Date()) {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDate(date = new Date()) {
  return date.toLocaleDateString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

function formatBytes(mb) {
  if (mb === null || mb === undefined) {
    return "—";
  }
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${mb.toFixed(1)} MB`;
}

function formatMetricPercent(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${Math.round(Number(value))}%`;
}

function currentState() {
  return state.data || {};
}

function memorySummary() {
  return currentState().memory_summary || "No stored memory yet.";
}

function updateChips() {
  const data = currentState();
  const cloud = data.cloud_ready ? "Cloud ready" : "Cloud offline";
  els.cloudChip.textContent = cloud;
  els.modelChip.textContent = data.model || "gpt-5";
  els.wakeChip.textContent = state.wakeArmed ? "FRIDAY" : "Direct";
  const ownerName = data.owner_name || data.owner_profile?.name || "Kenan Novruzov";
  const ownerTitle = data.owner_title || data.owner_profile?.title || "Boss";
  if (els.ownerChip) {
    els.ownerChip.textContent = `${ownerTitle}: ${ownerName}`;
  }
  els.voiceChip.textContent = state.speaking ? "Speaking" : state.listening ? "Listening" : "Voice idle";
  els.listenChip.textContent = state.wakeArmed ? "Wake word armed" : "Direct capture";
  els.telemetryChip.textContent = "Telemetry live";
  els.memoryChip.textContent = `${(data.notes || []).length} notes`;
  if (els.powerChip) {
    els.powerChip.textContent = `Power ${data.power_state || "online"}`;
  }
  if (els.securityChip) {
    els.securityChip.textContent = `Security ${data.security_mode || "normal"}`;
  }
  els.timeChip.textContent = formatClock();
  els.memorySummary.textContent = memorySummary();
  els.metricsSummary.textContent = summarizeMetrics(state.metrics);
  els.voiceSummary.textContent = voiceSummaryText();
  els.quickSummary.textContent = "Natural-language requests, safe web links, web search, timers, memory, telemetry, power states, and simulated HUD security.";
  els.statusLine.textContent = state.speaking
    ? "FRIDAY is speaking."
    : state.listening
      ? "FRIDAY is listening."
      : "FRIDAY online.";
  els.subLine.textContent = memorySummary();
}

function summarizeMetrics(metrics) {
  if (!metrics) {
    return "Telemetry is warming up.";
  }
  const parts = [];
  if (metrics.cpu_percent !== null && metrics.cpu_percent !== undefined) {
    parts.push(`CPU ${formatMetricPercent(metrics.cpu_percent)}`);
  }
  const ram = metrics.ram || {};
  if (ram.used_gb !== null && ram.total_gb !== null && ram.used_gb !== undefined && ram.total_gb !== undefined) {
    parts.push(`RAM ${formatNumber(ram.used_gb)} / ${formatNumber(ram.total_gb)} GB`);
  }
  const gpu = metrics.gpu || {};
  if (gpu.name) {
    parts.push(gpu.utilization !== null && gpu.utilization !== undefined ? `GPU ${gpu.name} ${formatMetricPercent(gpu.utilization)}` : `GPU ${gpu.name}`);
  }
  const battery = metrics.battery || {};
  if (battery.percent !== null && battery.percent !== undefined) {
    parts.push(`Battery ${formatMetricPercent(battery.percent)}`);
  }
  const network = metrics.network || {};
  if (network.name) {
    parts.push(`Network ${network.name}`);
  }
  return parts.join(" • ") || "Telemetry is warming up.";
}

function voiceSummaryText() {
  if (!("speechSynthesis" in window)) {
    return "Speech synthesis unavailable in this browser.";
  }
  const ownerName = currentState().owner_name || currentState().owner_profile?.name || "Kenan Novruzov";
  const voice = state.selectedVoice ? `Selected voice: ${state.selectedVoice.name}` : "Browser voice ready.";
  const capture = state.listening
    ? state.transcribing
      ? "Transcribing microphone input."
      : "Microphone capture armed."
    : "Microphone capture ready.";
  return `${voice} ${capture} Boss profile: ${ownerName}.`;
}

function eventLabel(item) {
  return `${item.kind || "event"} • ${new Date(item.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function renderLeftPanel() {
  const data = currentState();
  const view = state.view;
  const notes = data.notes || [];
  const tasks = data.tasks || [];
  const history = data.history || [];
  const events = data.events || [];

  if (view === "commands") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Quick Commands</div>
        <div class="command-grid">
          ${QUICK_COMMANDS.map((item) => `
            <button class="command-card" type="button" data-command="${escapeHtml(item.text)}">
              <strong>${escapeHtml(item.title)}</strong>
              <span>${escapeHtml(item.detail)}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
    return;
  }

  if (view === "notes") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Notes</div>
        ${notes.length ? notes.map((item) => `
          <article class="card message-card">
            <div class="message-role">Note</div>
            <div class="message-text">${escapeHtml(item.text)}</div>
            <div class="message-time">${escapeHtml(new Date(item.created_at).toLocaleString())}</div>
          </article>
        `).join("") : '<div class="empty-state">No notes stored yet. Use the command bar to add one.</div>'}
      </div>
    `;
    return;
  }

  if (view === "tasks") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Tasks</div>
        ${tasks.length ? tasks.map((item) => `
          <label class="card task-row ${item.done ? "done" : ""}">
            <input type="checkbox" data-task-id="${escapeHtml(item.id)}" ${item.done ? "checked" : ""}>
            <span class="message-text">${escapeHtml(item.text)}</span>
            <span class="message-time">${escapeHtml(new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</span>
          </label>
        `).join("") : '<div class="empty-state">No tasks active. Say "task ..." to create one.</div>'}
      </div>
    `;
    return;
  }

  if (view === "history") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Timeline</div>
        ${events.length ? events.slice().reverse().map((item) => `
          <article class="card event-row">
            <strong>${escapeHtml(item.text)}</strong>
            <span class="meta-row">${escapeHtml(eventLabel(item))}</span>
          </article>
        `).join("") : '<div class="empty-state">No events recorded yet.</div>'}
      </div>
    `;
    return;
  }

  els.leftPanel.innerHTML = `
    <div class="stack">
      <div class="stack-title">Live Conversation</div>
      ${history.length ? history.map((item) => `
        <article class="card message-card ${item.role === "user" ? "user" : "friday"}">
          <div class="message-role">${escapeHtml(item.role === "user" ? "You" : "FRIDAY")}</div>
          <div class="message-text">${escapeHtml(item.text)}</div>
          <div class="message-time">${escapeHtml(new Date(item.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</div>
        </article>
      `).join("") : '<div class="empty-state">Say something to begin the conversation.</div>'}
    </div>
  `;
  requestAnimationFrame(() => {
    els.leftPanel.scrollTop = els.leftPanel.scrollHeight;
  });
}

function renderRightPanel() {
  const metrics = state.metrics || {};
  const data = currentState();
  const ram = metrics.ram || {};
  const battery = metrics.battery || {};
  const gpu = metrics.gpu || {};
  const network = metrics.network || {};
  const vision = data.camera_status || {};
  const processes = metrics.processes || [];
  const weather = state.weather;
  const uptime = metrics.uptime || "—";

  els.rightPanel.innerHTML = `
    <div class="stack">
      <div class="stack-title">Telemetry Snapshot</div>
      <div class="metric-grid">
        <article class="card metric-card">
          <strong>CPU</strong>
          <span>${formatMetricPercent(metrics.cpu_percent)}</span>
          <div class="metric-value">${formatMetricPercent(metrics.cpu_percent)}</div>
          <div class="metric-bar"><span style="--metric-width:${metrics.cpu_percent ?? 0}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>RAM</strong>
          <span>${ram.used_gb !== undefined && ram.used_gb !== null ? `${formatNumber(ram.used_gb)} / ${formatNumber(ram.total_gb)} GB` : "—"}</span>
          <div class="metric-value">${ram.percent !== undefined && ram.percent !== null ? formatMetricPercent(ram.percent) : "—"}</div>
          <div class="metric-bar"><span style="--metric-width:${ram.percent ?? 0}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>GPU</strong>
          <span>${gpu.name || "—"}</span>
          <div class="metric-value">${gpu.utilization !== undefined && gpu.utilization !== null ? formatMetricPercent(gpu.utilization) : "Telemetry only"}</div>
          <div class="metric-bar"><span style="--metric-width:${gpu.utilization ?? 18}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>Battery</strong>
          <span>${battery.status !== undefined && battery.status !== null ? `Status ${battery.status}` : "—"}</span>
          <div class="metric-value">${battery.percent !== undefined && battery.percent !== null ? formatMetricPercent(battery.percent) : "—"}</div>
          <div class="metric-bar"><span style="--metric-width:${battery.percent ?? 0}%"></span></div>
        </article>
      </div>

      <article class="card">
        <div class="section-title">Network</div>
        <div class="metric-value">${network.name ? `${network.name} • ${network.speed || "active"}` : "No active adapter detected."}</div>
        <div class="meta-row">${network.received_mb !== undefined && network.received_mb !== null ? `Received ${formatNumber(network.received_mb)} MB • Sent ${formatNumber(network.sent_mb)} MB` : ""}</div>
      </article>

      <article class="card">
        <div class="section-title">Weather</div>
        <div class="metric-value">${weather?.label || "Weather sync pending."}</div>
        <div class="meta-row">${weather?.detail || "Click the weather card to fetch local conditions."}</div>
        <button type="button" class="weather-button" data-action="weather">Sync weather</button>
      </article>

      <article class="card">
        <div class="section-title">Vision</div>
        <div class="metric-value">Camera ${vision.camera || "idle"}</div>
        <div class="meta-row">Face ${vision.face || "idle"} • Voice planner ready</div>
      </article>

      <article class="card">
        <div class="section-title">System Time</div>
        <div class="metric-value">${formatDate()} • ${formatClock()}</div>
        <div class="meta-row">Uptime ${uptime}</div>
      </article>

      <article class="card">
        <div class="section-title">Active Processes</div>
        <div class="process-list">
          ${processes.length ? processes.map((item) => `
            <div class="process-card">
              <strong>${escapeHtml(item.Name || item.name || "Process")}</strong>
              <span>${item.Id || item.id ? `PID ${item.Id ?? item.id}` : ""} ${item.WorkingSetMB !== undefined ? `• ${item.WorkingSetMB} MB` : ""}</span>
              <div class="bar"><span style="--bar-width:${Math.min(100, Math.max(10, Number(item.CPU || item.cpu || 0) * 5))}%"></span></div>
            </div>
          `).join("") : '<div class="empty-state">No process data yet.</div>'}
        </div>
      </article>

      <article class="card">
        <div class="section-title">Modules</div>
        <div class="list-stack">
          ${(data.modules || []).map((item) => `
            <div class="event-card">
              <strong>${escapeHtml(item.name)}</strong>
              <span>${escapeHtml(item.status)} • ${escapeHtml(item.detail)}</span>
            </div>
          `).join("")}
        </div>
      </article>
    </div>
  `;
}

function renderCenterSummary() {
  const data = currentState();
  els.memorySummary.textContent = data.memory_summary || "No stored memory yet.";
  els.metricsSummary.textContent = summarizeMetrics(state.metrics);
  els.voiceSummary.textContent = voiceSummaryText();
  els.quickSummary.textContent = "Natural-language requests, multi-step planning, screenshots, downloads, contacts, power, and security.";
}

function renderAll() {
  updateChips();
  renderLeftPanel();
  renderRightPanel();
  renderCenterSummary();
}

function updateTranscript(text, emphasis = false) {
  state.transcript = text || "";
  els.transcriptLine.textContent = state.transcript || "Transcript will appear here.";
  els.transcriptLine.classList.toggle("blink", emphasis);
}

function setModeEnergy(mode) {
  const base = {
    idle: 0.28,
    listening: 0.58,
    speaking: 0.76,
    thinking: 0.44,
    boot: 0.32,
  }[mode] ?? 0.35;
  setEnergy(base);
}

function syncEventToasts(payload) {
  const events = (payload?.state?.events) || [];
  if (!events.length) {
    return;
  }
  for (const item of events) {
    if (state.lastEventIds.has(item.id)) {
      continue;
    }
    state.lastEventIds.add(item.id);
    showToast(item.kind || "Event", item.text);
  }
  while (state.lastEventIds.size > 80) {
    const first = state.lastEventIds.values().next().value;
    if (first) {
      state.lastEventIds.delete(first);
    } else {
      break;
    }
  }
}

async function loadState() {
  const payload = await apiGet("/api/state");
  state.data = payload;
  state.lastEventIds = new Set((payload.events || []).map((item) => item.id));
  if (payload.model) {
    const index = MODEL_ORDER.indexOf(payload.model);
    state.modelIndex = index >= 0 ? index : 0;
  }
  syncEventToasts({ state: payload });
  renderAll();
}

async function loadMetrics() {
  try {
    state.metrics = await apiGet("/api/metrics");
    renderRightPanel();
    renderCenterSummary();
  } catch {
    state.metrics = state.metrics || null;
  }
}

async function refreshWeather() {
  if (!navigator.geolocation) {
    state.weather = {
      label: "Weather unavailable",
      detail: "Geolocation is not supported in this browser.",
    };
    renderRightPanel();
    return;
  }
  state.weatherRequested = true;
  navigator.geolocation.getCurrentPosition(
    async (position) => {
      try {
        const { latitude, longitude } = position.coords;
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=auto`;
        const payload = await fetch(url, { cache: "no-store" }).then((response) => response.json());
        const current = payload.current || {};
        state.weather = {
          label: `${current.temperature_2m ?? "—"}°C`,
          detail: `Feels ${current.apparent_temperature ?? "—"}°C • Wind ${current.wind_speed_10m ?? "—"} km/h`,
        };
        renderRightPanel();
      } catch {
        state.weather = {
          label: "Weather sync failed",
          detail: "The local weather endpoint could not be reached.",
        };
        renderRightPanel();
      }
    },
    () => {
      state.weather = {
        label: "Location unavailable",
        detail: "Grant location access to sync weather.",
      };
      renderRightPanel();
    },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 900000 },
  );
}

function chooseVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) {
    return null;
  }
  const preferred = voices.find((voice) => /samantha|serena|victoria|zira|ava|aria|female/i.test(voice.name));
  return preferred || voices.find((voice) => /en-us|en-gb/i.test(voice.lang)) || voices[0];
}

function playTone(frequency = 760, duration = 0.08, type = "sine", gainValue = 0.03) {
  try {
    const context = state.ambientContext || new (window.AudioContext || window.webkitAudioContext)();
    if (!state.ambientContext) {
      state.ambientContext = context;
    }
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = type;
    oscillator.frequency.value = frequency;
    gain.gain.value = gainValue;
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + duration);
  } catch {
    // ignored
  }
}

function startAmbientTone() {
  if (state.ambient) {
    return;
  }
  try {
    const context = state.ambientContext || new (window.AudioContext || window.webkitAudioContext)();
    state.ambientContext = context;
    const oscillatorA = context.createOscillator();
    const oscillatorB = context.createOscillator();
    const gain = context.createGain();
    oscillatorA.type = "sine";
    oscillatorB.type = "triangle";
    oscillatorA.frequency.value = 54;
    oscillatorB.frequency.value = 68;
    gain.gain.value = 0.008;
    oscillatorA.connect(gain);
    oscillatorB.connect(gain);
    gain.connect(context.destination);
    oscillatorA.start();
    oscillatorB.start();
    state.ambientNodes = [oscillatorA, oscillatorB, gain];
    state.ambient = true;
    els.ambientBtn.textContent = "Ambient on";
    showToast("Ambient", "Low-frequency hum activated.");
  } catch {
    showToast("Ambient", "Ambient audio is not available.");
  }
}

function stopAmbientTone() {
  if (!state.ambient) {
    return;
  }
  for (const node of state.ambientNodes) {
    try {
      if (node.stop) {
        node.stop();
      }
      if (node.disconnect) {
        node.disconnect();
      }
    } catch {
      // ignored
    }
  }
  state.ambientNodes = [];
  state.ambient = false;
  els.ambientBtn.textContent = "Ambient off";
  showToast("Ambient", "Low-frequency hum disabled.");
}

function updateVoiceState(label, mode = "idle") {
  els.voiceChip.textContent = label;
  document.body.dataset.fridayMode = mode;
  setModeEnergy(mode);
}

function clearVoiceRecording() {
  state.recordedChunks = [];
  state.recordingSampleRate = 0;
  state.recordingStartedAt = 0;
  state.recordingLastVoiceAt = 0;
  state.recordingHeardVoice = false;
}

async function startMicAnalysis({ captureAudio = false } = {}) {
  stopMicAnalysis();
  try {
    state.micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    state.micContext = new (window.AudioContext || window.webkitAudioContext)();
    state.micSource = state.micContext.createMediaStreamSource(state.micStream);
    state.micAnalyser = state.micContext.createAnalyser();
    state.micAnalyser.fftSize = 256;
    state.micSource.connect(state.micAnalyser);

    clearVoiceRecording();
    state.voiceFallbackActive = captureAudio;
    if (captureAudio) {
      state.recordingSampleRate = state.micContext.sampleRate || 44100;
      state.recordingStartedAt = Date.now();
      state.micProcessor = state.micContext.createScriptProcessor(4096, 1, 1);
      state.micProcessor.onaudioprocess = (event) => {
        if (!state.listening || state.transcribing || state.finalizingVoiceCapture) {
          return;
        }
        const input = event.inputBuffer.getChannelData(0);
        const chunk = new Float32Array(input.length);
        chunk.set(input);
        state.recordedChunks.push(chunk);
        const rms = computeRms(chunk);
        state.audioLevel = clamp(Math.max(state.audioLevel * 0.72, rms * 3.5), 0.04, 1);
        if (rms > 0.018) {
          state.recordingHeardVoice = true;
          state.recordingLastVoiceAt = Date.now();
        }
        const totalFor = Date.now() - state.recordingStartedAt;
        if (state.recordingHeardVoice && !state.finalizingVoiceCapture) {
          const silenceFor = Date.now() - state.recordingLastVoiceAt;
          if (silenceFor > 1100 && totalFor > 1300) {
            void finalizeVoiceCapture("silence");
          } else if (totalFor > 15000) {
            void finalizeVoiceCapture("timeout");
          }
        }
        try {
          const output = event.outputBuffer.getChannelData(0);
          output.fill(0);
        } catch {
          // ignored
        }
      };
      state.micSource.connect(state.micProcessor);
      state.micProcessor.connect(state.micContext.destination);
    }
    if (state.micContext.resume) {
      await state.micContext.resume().catch(() => {});
    }
  } catch (error) {
    stopMicAnalysis();
    throw error;
  }
}

function stopMicAnalysis() {
  try {
    if (state.micProcessor) {
      state.micProcessor.disconnect();
    }
    if (state.micStream) {
      state.micStream.getTracks().forEach((track) => track.stop());
    }
    if (state.micSource) {
      state.micSource.disconnect();
    }
    if (state.micAnalyser) {
      state.micAnalyser.disconnect();
    }
    if (state.micContext) {
      state.micContext.close();
    }
  } catch {
    // ignored
  }
  state.micProcessor = null;
  state.micStream = null;
  state.micContext = null;
  state.micSource = null;
  state.micAnalyser = null;
  state.audioLevel = 0;
}

async function transcribeRecordedVoice() {
  if (state.transcribing || !state.recordedChunks.length) {
    return "";
  }
  const sampleRate = state.recordingSampleRate || 44100;
  const samples = concatFloat32Arrays(state.recordedChunks);
  if (samples.length < sampleRate * 0.45) {
    clearVoiceRecording();
    return "";
  }
  state.transcribing = true;
  updateVoiceState("Transcribing", "thinking");
  try {
    const wavBuffer = encodeWavBuffer(samples, sampleRate);
    const payload = await apiPost("/api/transcribe", {
      audio_base64: arrayBufferToBase64(wavBuffer),
      model: "gemini-2.5-flash",
    });
    return String(payload.text || "").trim();
  } finally {
    state.transcribing = false;
    clearVoiceRecording();
  }
}

async function pauseVoiceRuntime() {
  if (!state.listening) {
    return;
  }
  state.voiceResumeAfterSpeech = true;
  try {
    if (state.recognition) {
      state.recognition.stop();
    }
  } catch {
    // ignored
  }
  stopMicAnalysis();
}

async function resumeVoiceRuntime() {
  if (!state.listening) {
    state.voiceResumeAfterSpeech = false;
    return;
  }
  state.voiceResumeAfterSpeech = false;
  state.recognition = state.recognition || initRecognition();
  if (state.recognition) {
    try {
      state.voiceFallbackActive = false;
      await startMicAnalysis({ captureAudio: false });
      state.recognition.start();
      updateVoiceState("Listening", "listening");
      return;
    } catch {
      try {
        state.recognition.stop();
      } catch {
        // ignored
      }
    }
  }
  state.voiceFallbackActive = true;
  try {
    await startMicAnalysis({ captureAudio: true });
    updateVoiceState("Listening", "listening");
  } catch {
    state.voiceFallbackActive = true;
    try {
      await startMicAnalysis({ captureAudio: true });
      updateVoiceState("Listening", "listening");
      showToast("Voice", "Microphone capture restored.");
    } catch {
      state.voiceFallbackActive = false;
      updateVoiceState("Voice idle", "idle");
      showToast("Voice", "Unable to restart microphone capture.");
    }
  }
}

async function finalizeVoiceCapture(reason = "silence") {
  if (state.finalizingVoiceCapture) {
    return;
  }
  state.finalizingVoiceCapture = true;
  try {
    const transcript = await transcribeRecordedVoice();
    if (!transcript) {
      if (reason !== "manual") {
        showToast("Voice", "I couldn't hear that clearly.");
      }
      if (state.listening) {
        await resumeVoiceRuntime();
      }
      return;
    }
    const cleaned = stripWakeWord(transcript);
    updateTranscript(transcript, true);
    if (state.wakeArmed && !isWakeWordDetected(transcript)) {
      showToast("Wake word", "Say FRIDAY, then the command.");
      if (state.listening) {
        await resumeVoiceRuntime();
      }
      return;
    }
    if (!cleaned) {
      showToast("Wake word", "Wake word detected. Listening for your command.");
      updateVoiceState("Listening", "listening");
      await resumeVoiceRuntime();
      return;
    }
    await sendCommand(cleaned, "voice");
  } catch (error) {
    showToast("Voice", error instanceof Error ? error.message : "Transcription failed.");
    if (state.listening) {
      await resumeVoiceRuntime();
    }
  } finally {
    state.finalizingVoiceCapture = false;
  }
}

function detectVoiceMood(text) {
  const normalized = String(text || "").toLowerCase();
  if (/(sorry|apolog|worry|concern|danger|problem|error|critical|unable|can't|cannot|fail|issue)/.test(normalized)) {
    return { rate: 0.84, pitch: 0.74, volume: 0.96, tone: "concerned" };
  }
  if (/(great|awesome|excellent|happy|glad|joy|delight|perfect|success|done|ready)/.test(normalized)) {
    return { rate: 1.03, pitch: 1.02, volume: 0.98, tone: "joyful" };
  }
  if (/(question|what|who|when|where|why|how|curious)/.test(normalized)) {
    return { rate: 0.94, pitch: 0.9, volume: 0.95, tone: "curious" };
  }
  if (/(warning|alert|attention|careful|cautious)/.test(normalized)) {
    return { rate: 0.88, pitch: 0.8, volume: 0.97, tone: "alert" };
  }
  return { rate: 0.95, pitch: 0.84, volume: 1, tone: "neutral" };
}

function finalizeSpeech(text) {
  if (!("speechSynthesis" in window) || !text) {
    return false;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const mood = detectVoiceMood(text);
  utterance.rate = mood.rate;
  utterance.pitch = mood.pitch;
  utterance.volume = mood.volume;
  utterance.lang = "en-US";
  const voice = state.selectedVoice || chooseVoice();
  if (voice) {
    utterance.voice = voice;
    state.selectedVoice = voice;
  }
  utterance.onstart = () => {
    state.speaking = true;
    updateVoiceState("Speaking", "speaking");
    const toneMap = {
      concerned: [660, 0.08, "sawtooth", 0.03],
      joyful: [980, 0.06, "triangle", 0.03],
      curious: [760, 0.06, "sine", 0.028],
      alert: [720, 0.07, "square", 0.032],
    };
    const tone = toneMap[mood.tone] || [880, 0.06, "sine", 0.035];
    playTone(tone[0], tone[1], tone[2], tone[3]);
  };
  utterance.onend = () => {
    state.speaking = false;
    playTone(520, 0.05, "triangle", 0.025);
    if (state.listening) {
      void resumeVoiceRuntime();
    } else {
      updateVoiceState("Voice idle", "idle");
      renderAll();
    }
  };
  window.speechSynthesis.speak(utterance);
  return true;
}

function stripWakeWord(text) {
  let cleaned = String(text || "").trim();
  const lower = cleaned.toLowerCase();
  if (lower.startsWith("hey friday")) {
    cleaned = cleaned.slice(10).trim();
  } else if (lower.startsWith("friday")) {
    cleaned = cleaned.slice(6).trim();
  }
  return cleaned.replace(/^[,!.:\-\s]+/, "").trim();
}

function looksLikeDirectCommand(text) {
  const cleaned = String(text || "").toLowerCase().replace(/['’]/g, " ");
  return /\b(tell|open|search|find|note|remember|task|timer|remind|status|calculate|compute|kids?|students?|children|jurnal|uşaq|usaq|şagird|sagird)\b/.test(cleaned);
}

function isWakeWordDetected(text) {
  return /\b(?:hey\s+)?friday\b/i.test(String(text || ""));
}

function dispatchVoiceText(finalText) {
  const spoken = String(finalText || "").trim();
  if (!spoken) {
    return;
  }
  const now = Date.now();
  if (now - state.lastVoiceDispatchAt < 900) {
    return;
  }
  const cleaned = stripWakeWord(spoken);
  if (state.wakeArmed) {
    if (isWakeWordDetected(spoken)) {
      state.lastVoiceDispatchAt = now;
      updateVoiceState("Wake word detected", "listening");
      document.body.classList.add("wake-flash");
      setTimeout(() => document.body.classList.remove("wake-flash"), 950);
      playTone(920, 0.08, "sine", 0.04);
      if (cleaned) {
        sendCommand(cleaned, "voice");
      } else {
        updateTranscript("FRIDAY wake word detected. Listening...", true);
      }
    }
    return;
  }
  if (cleaned || looksLikeDirectCommand(spoken)) {
    state.lastVoiceDispatchAt = now;
    sendCommand(cleaned || spoken, "voice");
  }
}

async function sendCommand(textOverride = null, source = "typed") {
  const input = (textOverride ?? els.commandInput.value).trim();
  if (!input) {
    showToast("FRIDAY", "Give me a command first.");
    return;
  }
  els.commandInput.value = "";
  await pauseVoiceRuntime();
  updateVoiceState("Thinking", "thinking");
  updateTranscript("Processing command...", true);
  try {
    const payload = await apiPost("/api/chat", { text: input, source });
    const previousIds = new Set(state.lastEventIds);
    state.data = payload.state || state.data;
    syncEventToasts(payload);
    state.lastEventIds = new Set([...(state.data?.events || []).map((item) => item.id), ...previousIds]);
    renderAll();
    const reply = payload.reply || "FRIDAY is ready.";
    updateTranscript(reply, false);
    if (payload.kind === "document") {
      showToast("Document", "Summary ready.");
    }
    if (payload.kind === "metrics") {
      await loadMetrics();
    }
    if (payload.kind === "model") {
      showToast("Model", reply);
    }
    const spoken = finalizeSpeech(reply);
    if (!spoken) {
      state.speaking = false;
      updateVoiceState(state.listening ? "Listening" : "Voice idle", state.listening ? "listening" : "idle");
      if (state.listening) {
        void resumeVoiceRuntime();
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Command failed.";
    updateTranscript(message, false);
    showToast("FRIDAY", message);
    state.speaking = false;
    updateVoiceState(state.listening ? "Listening" : "Voice idle", state.listening ? "listening" : "idle");
    if (state.listening) {
      void resumeVoiceRuntime();
    }
  }
}

function initRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    return null;
  }
  const recognition = new Recognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = navigator.language || "en-US";
  recognition.onresult = (event) => {
    let transcript = "";
    let finalText = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const segment = event.results[i][0].transcript;
      transcript += segment;
      if (event.results[i].isFinal) {
        finalText += segment;
      }
    }
    transcript = transcript.trim();
    if (transcript) {
      updateTranscript(transcript, true);
    }
    if (finalText) {
      dispatchVoiceText(finalText);
    }
  };
  recognition.onerror = async () => {
    if (!state.listening || state.voiceResumeAfterSpeech) {
      return;
    }
    showToast("Voice", "Browser speech recognition paused. Switching to microphone capture.");
    state.voiceFallbackActive = true;
    try {
      await startMicAnalysis({ captureAudio: true });
    } catch {
      updateVoiceState("Voice idle", "idle");
      showToast("Voice", "Microphone capture is unavailable.");
    }
  };
  recognition.onend = () => {
    if (state.listening && !state.voiceResumeAfterSpeech && !state.voiceFallbackActive) {
      try {
        recognition.start();
      } catch {
        state.voiceFallbackActive = true;
        void startMicAnalysis({ captureAudio: true }).catch(() => {});
      }
    }
  };
  return recognition;
}

async function toggleVoice() {
  if (!state.listening) {
    state.listening = true;
    state.voiceFallbackActive = false;
    updateVoiceState("Listening", "listening");
    updateTranscript("Listening for your command...", true);
    playTone(760, 0.07, "sine", 0.03);
    state.recognition = state.recognition || initRecognition();
    if (state.recognition) {
      try {
        await startMicAnalysis({ captureAudio: false });
        state.recognition.start();
        showToast("Voice", state.wakeArmed ? "Wake-word listening activated." : "Direct voice recognition activated.");
        return;
      } catch {
        try {
          state.recognition.stop();
        } catch {
          // ignored
        }
      }
    }
    state.voiceFallbackActive = true;
    try {
      await startMicAnalysis({ captureAudio: true });
      showToast("Voice", "Microphone capture activated.");
    } catch {
      try {
        await startMicAnalysis({ captureAudio: true });
        showToast("Voice", "Using microphone capture instead.");
      } catch (error) {
        state.listening = false;
        state.voiceFallbackActive = false;
        updateVoiceState("Voice idle", "idle");
        showToast("Voice", error instanceof Error ? error.message : "Microphone access failed.");
        return;
      }
    }
  } else {
    const shouldFinalize = state.recordedChunks.length > 0;
    state.listening = false;
    state.voiceResumeAfterSpeech = false;
    state.voiceFallbackActive = false;
    updateVoiceState("Voice idle", "idle");
    try {
      if (state.recognition) {
        state.recognition.stop();
      }
    } catch {
      // ignored
    }
    stopMicAnalysis();
    if (shouldFinalize) {
      await finalizeVoiceCapture("manual");
    } else {
      updateTranscript("Voice listening paused.", false);
    }
    playTone(480, 0.05, "triangle", 0.025);
    showToast("Voice", "Microphone capture paused.");
  }
}

function toggleWakeArmed() {
  state.wakeArmed = !state.wakeArmed;
  els.listenChip.textContent = state.wakeArmed ? "Wake word armed" : "Direct capture";
  els.wakeChip.textContent = state.wakeArmed ? "FRIDAY" : "Direct";
  showToast("Wake word", state.wakeArmed ? "FRIDAY is armed." : "Direct capture enabled.");
  renderCenterSummary();
}

function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {});
    return;
  }
  document.documentElement.requestFullscreen?.().catch(() => {});
}

function toggleAmbient() {
  if (state.ambient) {
    stopAmbientTone();
  } else {
    startAmbientTone();
  }
}

async function clearMemory() {
  try {
    const payload = await apiPost("/api/clear", {});
    state.data = payload.state || state.data;
    state.lastEventIds = new Set();
    updateTranscript("Memory cleared.", false);
    showToast("Memory", "History, notes, and tasks cleared.");
    renderAll();
    await loadMetrics();
  } catch (error) {
    showToast("Memory", error instanceof Error ? error.message : "Unable to clear memory.");
  }
}

async function cycleModel() {
  const models = currentState().supported_models || MODEL_ORDER;
  const current = currentState().model || MODEL_ORDER[0];
  const index = Math.max(0, models.indexOf(current));
  const next = models[(index + 1) % models.length];
  try {
    const payload = await apiPost("/api/model", { model: next });
    state.data = payload.state || state.data;
    showToast("Model", `Preferred model set to ${payload.model}.`);
    renderAll();
  } catch (error) {
    showToast("Model", error instanceof Error ? error.message : "Could not change model.");
  }
}

function bindStaticActions() {
  els.sendBtn.addEventListener("click", () => sendCommand());
  els.commandInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendCommand();
    }
  });
  els.voiceBtn.addEventListener("click", toggleVoice);
  els.wakeBtn.addEventListener("click", toggleWakeArmed);
  els.ambientBtn.addEventListener("click", toggleAmbient);
  els.fullBtn.addEventListener("click", toggleFullscreen);
  els.clearBtn.addEventListener("click", clearMemory);
  els.modelChip.addEventListener("click", cycleModel);
  els.cloudChip.addEventListener("click", () => loadState().catch(() => {}));
  els.wakeChip.addEventListener("click", toggleWakeArmed);
  els.leftTabs.addEventListener("click", (event) => {
    const target = event.target.closest("[data-view]");
    if (!target) {
      return;
    }
    state.view = target.dataset.view || "conversation";
    els.leftTabs.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab === target));
    renderLeftPanel();
  });
  els.leftPanel.addEventListener("click", (event) => {
    const commandCard = event.target.closest("[data-command]");
    if (commandCard) {
      const text = commandCard.dataset.command || "";
      els.commandInput.value = text;
      sendCommand(text);
      return;
    }
  });
  els.leftPanel.addEventListener("change", async (event) => {
    const checkbox = event.target.closest("[data-task-id]");
    if (!checkbox) {
      return;
    }
    const idValue = checkbox.dataset.taskId;
    if (!idValue) {
      return;
    }
    const target = currentState().tasks?.find((item) => item.id === idValue);
    if (!target) {
      return;
    }
    if (checkbox.checked && !target.done) {
      try {
        const payload = await apiPost("/api/task/complete", { target: idValue });
        state.data = payload.state || state.data;
        renderAll();
        showToast("Tasks", payload.reply || "Task updated.");
      } catch (error) {
        showToast("Tasks", error instanceof Error ? error.message : "Could not update task.");
      }
    }
  });
  els.rightPanel.addEventListener("click", (event) => {
    const weatherButton = event.target.closest("[data-action='weather']");
    if (weatherButton) {
      refreshWeather();
    }
  });
  window.addEventListener("resize", resizeVisuals);
  window.speechSynthesis?.addEventListener?.("voiceschanged", () => {
    state.voices = window.speechSynthesis.getVoices();
    state.selectedVoice = chooseVoice();
    renderCenterSummary();
  });
}

function resizeWaveCanvas() {
  const canvas = els.waveCanvas;
  if (!canvas) {
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const mobile = window.matchMedia?.("(max-width: 780px)")?.matches;
  const dpr = Math.min(window.devicePixelRatio || 1, mobile ? 1.35 : 2);
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  const context = canvas.getContext("2d");
  if (context) {
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
}

function resizeThree() {
  if (!state.renderer || !state.camera || !state.threeStage) {
    return;
  }
  const width = state.threeStage.clientWidth;
  const height = state.threeStage.clientHeight;
  if (width === 0 || height === 0) {
    return;
  }
  state.renderer.setSize(width, height, false);
  state.camera.aspect = width / height;
  state.camera.updateProjectionMatrix();
}

function resizeVisuals() {
  resizeWaveCanvas();
  resizeThree();
}

function drawWaveform() {
  const canvas = els.waveCanvas;
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  ctx.clearRect(0, 0, width, height);
  const bars = window.matchMedia?.("(max-width: 780px)")?.matches ? 40 : 64;
  const barWidth = width / bars;
  const level = state.audioLevel || state.energy;
  for (let i = 0; i < bars; i += 1) {
    const phase = (performance.now() * 0.0012) + i * 0.45;
    const wave = Math.sin(phase) * 0.22 + Math.sin(phase * 1.7) * 0.14;
    const pulse = clamp(level * 0.75 + 0.18 + wave, 0.08, 0.98);
    const barHeight = pulse * (height * 0.34);
    const x = i * barWidth + barWidth * 0.22;
    const y = height * 0.72 - barHeight;
    ctx.fillStyle = `rgba(89, 230, 255, ${0.18 + pulse * 0.42})`;
    ctx.fillRect(x, y, barWidth * 0.56, barHeight);
    ctx.fillStyle = `rgba(55, 141, 255, ${0.12 + pulse * 0.26})`;
    ctx.fillRect(x + 2, y + 2, barWidth * 0.36, Math.max(8, barHeight - 6));
  }
  ctx.strokeStyle = "rgba(89, 230, 255, 0.28)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= width; i += 8) {
    const wave = Math.sin(i * 0.018 + performance.now() * 0.0015) * 10 * (0.35 + level);
    const y = height * 0.74 + wave;
    if (i === 0) {
      ctx.moveTo(i, y);
    } else {
      ctx.lineTo(i, y);
    }
  }
  ctx.stroke();
}

function drawFallbackParticles() {
  const canvas = els.waveCanvas;
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = "rgba(2, 4, 10, 0.18)";
  ctx.fillRect(0, 0, width, height);
}

function initThree() {
  if (!window.THREE || !els.threeStage || state.reducedMotion) {
    return;
  }
  const THREE = window.THREE;
  const width = els.threeStage.clientWidth;
  const height = els.threeStage.clientHeight;
  if (!width || !height) {
    return;
  }
  const mobile = window.matchMedia?.("(max-width: 780px)")?.matches;
  state.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: !mobile, powerPreference: "high-performance" });
  state.renderer.setSize(width, height, false);
  state.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, mobile ? 1.35 : 2));
  state.threeStage.innerHTML = "";
  state.threeStage.appendChild(state.renderer.domElement);
  state.scene = new THREE.Scene();
  state.camera = new THREE.PerspectiveCamera(46, width / height, 0.1, 100);
  state.camera.position.z = 6.6;
  state.threeGroup = new THREE.Group();
  state.scene.add(state.threeGroup);

  const orbGeometry = new THREE.IcosahedronGeometry(0.95, 4);
  const orbMaterial = new THREE.MeshBasicMaterial({
    color: 0x63f0ff,
    wireframe: true,
    transparent: true,
    opacity: 0.95,
  });
  state.threeOrb = new THREE.Mesh(orbGeometry, orbMaterial);
  state.threeGroup.add(state.threeOrb);

  const ringGeometry = new THREE.TorusGeometry(1.75, 0.045, 18, 180);
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: 0x3f8dff,
    transparent: true,
    opacity: 0.36,
  });
  const ring = new THREE.Mesh(ringGeometry, ringMaterial);
  ring.rotation.x = Math.PI / 2;
  state.threeGroup.add(ring);

  const pointsGeometry = new THREE.BufferGeometry();
  const pointsCount = 360;
  const positions = new Float32Array(pointsCount * 3);
  for (let i = 0; i < pointsCount; i += 1) {
    const angle = (i / pointsCount) * Math.PI * 2;
    const radius = 2.9 + (i % 7) * 0.03;
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = Math.sin(angle * 2.2) * 0.6;
    positions[i * 3 + 2] = Math.sin(angle) * radius * 0.48;
  }
  pointsGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const pointsMaterial = new THREE.PointsMaterial({
    color: 0x8ef7ff,
    size: 0.028,
    transparent: true,
    opacity: 0.66,
  });
  const points = new THREE.Points(pointsGeometry, pointsMaterial);
  state.threeGroup.add(points);

  state.threeScene = { ring, points };
}

function updateThree() {
  if (!state.renderer || !state.scene || !state.camera || !state.threeGroup || !state.threeOrb) {
    return;
  }
  const tick = performance.now() * 0.0005;
  state.threeGroup.rotation.y = tick * 0.7;
  state.threeGroup.rotation.x = Math.sin(tick * 0.6) * 0.12;
  state.threeOrb.scale.setScalar(1 + state.energy * 0.12 + state.audioLevel * 0.08);
  state.renderer.render(state.scene, state.camera);
}

function animate() {
  state.audioLevel = 0;
  if (state.micAnalyser) {
    const data = new Uint8Array(state.micAnalyser.frequencyBinCount);
    state.micAnalyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const deviation = (data[i] - 128) / 128;
      sum += Math.abs(deviation);
    }
    state.audioLevel = clamp(sum / data.length * 1.8, 0, 1);
  }
  drawWaveform();
  updateThree();
  requestAnimationFrame(animate);
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });
}

async function bootSequence() {
  const lines = [
    "Powering FRIDAY core...",
    "Loading holographic interface...",
    "Synchronizing memory graph...",
    "Arming wake word: Hey Friday...",
    "Calibrating voice and telemetry...",
    "Starting live system stream...",
    "FRIDAY online.",
  ];
  let progress = 5;
  setBootProgress(progress);
  els.bootLog.innerHTML = "";
  for (const line of lines) {
    const row = document.createElement("div");
    row.className = "boot-line";
    row.textContent = line;
    els.bootLog.appendChild(row);
    progress = clamp(progress + 12 + Math.random() * 8, 5, 96);
    setBootProgress(progress);
    await sleep(250);
  }
  await sleep(220);
  setBootProgress(100);
  await sleep(250);
  els.boot.classList.add("hidden");
  document.body.classList.add("ready");
  state.bootComplete = true;
  setEnergy(0.34);
}

async function pollState() {
  try {
    const payload = await apiGet("/api/state");
    state.data = payload;
    if (payload.events?.length) {
      for (const item of payload.events) {
        if (!state.lastEventIds.has(item.id)) {
          state.lastEventIds.add(item.id);
          showToast(item.kind || "Event", item.text);
        }
      }
    }
    if (payload.model) {
      const index = MODEL_ORDER.indexOf(payload.model);
      state.modelIndex = index >= 0 ? index : state.modelIndex;
    }
    renderAll();
  } catch {
    // ignored
  }
}

async function beginWeatherSync() {
  if (state.weatherRequested) {
    return;
  }
  state.weatherRequested = true;
  await refreshWeather();
}

async function initWeatherButtonHint() {
  state.weather = {
    label: "Weather pending",
    detail: "Click the weather card to sync local conditions.",
  };
  renderRightPanel();
}

async function initApp() {
  registerServiceWorker();
  bindStaticActions();
  resizeVisuals();
  state.selectedVoice = chooseVoice();
  state.voices = window.speechSynthesis?.getVoices?.() || [];
  await bootSequence();
  initThree();
  await loadState();
  await loadMetrics();
  await initWeatherButtonHint();
  renderAll();
  showToast("FRIDAY", "Cinematic core online.");
  animate();
  setInterval(() => {
    els.timeChip.textContent = formatClock();
    renderCenterSummary();
  }, 1000);
  setInterval(loadMetrics, 2500);
  setInterval(pollState, 5000);
  setInterval(renderCenterSummary, 4000);
  setTimeout(beginWeatherSync, 1400);
  updateTranscript("FRIDAY is ready.", false);
}

document.addEventListener("DOMContentLoaded", () => {
  initApp().catch((error) => {
    console.error(error);
    showToast("FRIDAY", "Startup failed.");
  });
});
els.protocolBtn.addEventListener("click", () => {

    els.protocolMenu.classList.toggle("hidden");

});