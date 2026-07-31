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

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const bigint = parseInt(clean, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `${r}, ${g}, ${b}`;
}

function applyProtocolColors(colors) {
  if (!colors) return;
  const primary = colors.primary || "#59e6ff";
  const secondary = colors.secondary || "#378dff";
  const root = document.documentElement;
  root.style.setProperty("--cyan", primary);
  root.style.setProperty("--cyan-rgb", hexToRgb(primary));
  root.style.setProperty("--blue", secondary);
  root.style.setProperty("--blue-rgb", hexToRgb(secondary));
  // Update three.js orb colors if initialized
  if (state.threeOrb && state.threeScene) {
    try {
      state.threeOrb.material.color.set(primary);
      state.threeScene.ring.material.color.set(secondary);
      state.threeScene.points.material.color.set(primary);
    } catch {
      // ignore three.js color update errors
    }
  }
}

async function loadProtocol() {
  try {
    const data = await apiGet("/api/protocol");
    if (data.protocol && data.protocol.colors) {
      applyProtocolColors(data.protocol.colors);
    }
  } catch {
    // ignore protocol load errors
  }
}

async function switchProtocol(name) {
  try {
    const data = await apiPost("/api/protocol", { protocol: name });
    if (data.ok && data.protocol && data.protocol.colors) {
      applyProtocolColors(data.protocol.colors);
      showToast("Protocol", `${data.protocol.name} protocol engaged.`);
      // Update boot sequence text if needed
      const protocolVoice = data.protocol.voice || `${data.protocol.name} protocol engaged.`;
      updateTranscript(protocolVoice, false);
      finalizeSpeech(protocolVoice, { mood: { tone: "neutral", rate: 0.95, pitch: 0.86, volume: 1 } });
    } else {
      showToast("Protocol", "Failed to switch protocol.");
    }
  } catch (err) {
    showToast("Protocol", err instanceof Error ? err.message : "Protocol switch failed.");
  }
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
  const ramUsedText = ram.used_gb !== undefined && ram.total_gb !== undefined
    ? `${formatNumber(ram.used_gb)} / ${formatNumber(ram.total_gb)} GB`
    : "—";
  const ramPercent = ram.used_gb !== undefined && ram.total_gb ? Math.round((ram.used_gb / ram.total_gb) * 100) : 0;
  const batteryPercent = battery.percent ?? 0;
  const gpuUtil = gpu.utilization ?? 0;
  const networkName = network.name || "Offline";
  const cameraStatus = vision.status || "Inactive";
  const weatherSummary = weather
    ? (weather.condition || weather.summary || (weather.temperature !== undefined ? `${formatNumber(weather.temperature)}°` : "Unknown"))
    : "Unknown";

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
          <span>${ramUsedText}</span>
          <div class="metric-value">${ramUsedText}</div>
          <div class="metric-bar"><span style="--metric-width:${ramPercent}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>Battery</strong>
          <span>${battery.percent !== undefined ? formatMetricPercent(battery.percent) : "—"}</span>
          <div class="metric-value">${battery.percent !== undefined ? formatMetricPercent(battery.percent) : "—"}</div>
          <div class="metric-bar"><span style="--metric-width:${batteryPercent}%"></span></div>
        </article>
      </div>
      <div class="metric-grid">
        <article class="card metric-card">
          <strong>GPU</strong>
          <span>${gpu.name || "Unknown"}</span>
          <div class="metric-value">${gpu.utilization !== undefined ? formatMetricPercent(gpu.utilization) : "—"}</div>
          <div class="metric-bar"><span style="--metric-width:${gpuUtil}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>Network</strong>
          <span>${escapeHtml(networkName)}</span>
          <div class="metric-value">${escapeHtml(networkName)}</div>
        </article>
        <article class="card metric-card">
          <strong>Camera</strong>
          <span>${escapeHtml(cameraStatus)}</span>
          <div class="metric-value">${escapeHtml(cameraStatus)}</div>
        </article>
      </div>
      <div class="metric-grid">
        <article class="card metric-card">
          <strong>Uptime</strong>
          <span>${escapeHtml(uptime)}</span>
        </article>
        <article class="card metric-card">
          <strong>Weather</strong>
          <span>${escapeHtml(weatherSummary)}</span>
        </article>
      </div>
    </div>
  `;
}