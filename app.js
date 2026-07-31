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
  particleCtx: null,
  particles: [],
  mouseX: 0,
  mouseY: 0,
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
  if (!samples || !samples.length) return 0;
  let total = 0;
  for (let i = 0; i < samples.length; i++) {
    total += samples[i] * samples[i];
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
    for (let i = 0; i < value.length; i++) {
      view.setUint8(offset + i, value.charCodeAt(i));
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
  for (let i = 0; i < samples.length; i++) {
    const value = clamp(samples[i], -1, 1);
    view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true);
    offset += bytesPerSample;
  }
  return buffer;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const slice = bytes.subarray(i, i + chunkSize);
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
  if (!response.ok) throw new Error(`GET ${path} failed`);
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

function setFridayMode(mode) {
  document.body.setAttribute("data-friday-mode", mode);
  if (mode === "listening") {
    setEnergy(0.85);
  } else if (mode === "speaking") {
    setEnergy(0.65);
  } else if (mode === "thinking") {
    setEnergy(0.5);
  } else {
    setEnergy(0.34);
  }
}

function setBootProgress(percent) {
  document.documentElement.style.setProperty("--boot-progress", `${percent}%`);
  if (els.bootBar) els.bootBar.style.width = `${percent}%`;
}

function showToast(title, message, type = "info") {
  if (!els.toastStack) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
  els.toastStack.prepend(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(16px) scale(0.95)";
    setTimeout(() => toast.remove(), 300);
  }, 3800);
}

function showError(message) {
  showToast("Error", message, "error");
  const orb = document.querySelector(".orb-panel");
  if (orb) {
    orb.classList.add("error-shake");
    setTimeout(() => orb.classList.remove("error-shake"), 600);
  }
}

function showSuccess(title, message) {
  showToast(title, message, "success");
}

function formatClock(date = new Date()) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDate(date = new Date()) {
  return date.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

function formatBytes(mb) {
  if (mb === null || mb === undefined) return "—";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb.toFixed(1)} MB`;
}

function formatMetricPercent(value) {
  if (value === null || value === undefined) return "—";
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
  if (els.ownerChip) els.ownerChip.textContent = `${ownerTitle}: ${ownerName}`;
  els.voiceChip.textContent = state.speaking ? "Speaking" : state.listening ? "Listening" : "Voice idle";
  els.listenChip.textContent = state.wakeArmed ? "Wake word armed" : "Direct capture";
  els.telemetryChip.textContent = "Telemetry live";
  els.memoryChip.textContent = `${(data.notes || []).length} notes`;
  if (els.powerChip) els.powerChip.textContent = `Power ${data.power_state || "online"}`;
  if (els.securityChip) els.securityChip.textContent = `Security ${data.security_mode || "normal"}`;
  els.timeChip.textContent = formatClock();
  els.memorySummary.textContent = memorySummary();
  els.metricsSummary.textContent = summarizeMetrics(state.metrics);
  els.voiceSummary.textContent = voiceSummaryText();
  els.quickSummary.textContent = "Natural-language requests, safe web links, web search, timers, memory, telemetry, power states, and simulated HUD security.";
  els.statusLine.textContent = state.speaking ? "FRIDAY is speaking." : state.listening ? "FRIDAY is listening." : "FRIDAY online.";
  els.subLine.textContent = memorySummary();
}

function summarizeMetrics(metrics) {
  if (!metrics) return "Telemetry is warming up.";
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
  if (!("speechSynthesis" in window)) return "Speech synthesis unavailable in this browser.";
  const ownerName = currentState().owner_name || currentState().owner_profile?.name || "Kenan Novruzov";
  const voice = state.selectedVoice ? `Selected voice: ${state.selectedVoice.name}` : "Browser voice ready.";
  const capture = state.listening
    ? state.transcribing ? "Transcribing microphone input." : "Microphone capture armed."
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
  if (state.threeOrb && state.threeScene) {
    try {
      state.threeOrb.material.color.set(primary);
      state.threeScene.ring.material.color.set(secondary);
      state.threeScene.points.material.color.set(primary);
    } catch {
      // ignore
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
    // ignore
  }
}

async function switchProtocol(name) {
  try {
    const data = await apiPost("/api/protocol", { protocol: name });
    if (data.ok && data.protocol && data.protocol.colors) {
      applyProtocolColors(data.protocol.colors);
      showSuccess("Protocol", `${data.protocol.name} protocol engaged.`);
      const protocolVoice = data.protocol.voice || `${data.protocol.name} protocol engaged.`;
      updateTranscript(protocolVoice, false);
      finalizeSpeech(protocolVoice, { mood: { tone: "neutral", rate: 0.95, pitch: 0.86, volume: 1 } });
    } else {
      showError("Failed to switch protocol.");
    }
  } catch (err) {
    showError(err instanceof Error ? err.message : "Protocol switch failed.");
  }
}

/* ─── PARTICLE SYSTEM ─── */
function initParticles() {
  const canvas = document.createElement("canvas");
  canvas.className = "particle-canvas";
  const shell = document.querySelector(".orb-shell");
  if (!shell || state.reducedMotion) return;
  shell.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  state.particleCtx = ctx;

  function resize() {
    const rect = shell.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
  }
  resize();
  window.addEventListener("resize", resize);

  const particleCount = 40;
  state.particles = [];
  for (let i = 0; i < particleCount; i++) {
    state.particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2 + 0.5,
      opacity: Math.random() * 0.5 + 0.1,
      pulse: Math.random() * Math.PI * 2,
    });
  }

  function animate() {
    if (!state.particleCtx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const energy = state.energy;
    const rgb = getComputedStyle(document.documentElement).getPropertyValue("--cyan-rgb").trim() || "89, 230, 255";

    state.particles.forEach((p, i) => {
      p.x += p.vx * (1 + energy);
      p.y += p.vy * (1 + energy);
      p.pulse += 0.02 + energy * 0.03;

      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      const pulseOpacity = p.opacity * (0.7 + 0.3 * Math.sin(p.pulse));
      const size = p.size * (1 + energy * 0.5);

      ctx.beginPath();
      ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb}, ${pulseOpacity})`;
      ctx.fill();

      // Connect nearby particles
      for (let j = i + 1; j < state.particles.length; j++) {
        const p2 = state.particles[j];
        const dx = p.x - p2.x;
        const dy = p.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 80 * energy + 40) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(${rgb}, ${0.08 * energy})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    });
    requestAnimationFrame(animate);
  }
  animate();
}

/* ─── MOUSE PARALLAX ─── */
function initMouseParallax() {
  if (state.reducedMotion) return;
  document.addEventListener("mousemove", (e) => {
    state.mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    state.mouseY = (e.clientY / window.innerHeight - 0.5) * 2;

    const orbShell = document.querySelector(".orb-shell");
    if (orbShell) {
      const moveX = state.mouseX * 8;
      const moveY = state.mouseY * 8;
      orbShell.style.transform = `perspective(1000px) rotateY(${moveX * 0.3}deg) rotateX(${-moveY * 0.3}deg)`;
    }
  });
}

/* ─── MAGNETIC BUTTONS ─── */
function initMagneticButtons() {
  if (window.matchMedia("(pointer: coarse)").matches) return;
  document.querySelectorAll("button").forEach(btn => {
    btn.classList.add("magnetic");
    btn.addEventListener("mousemove", (e) => {
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      btn.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px) translateY(-2px) scale(1.03)`;
    });
    btn.addEventListener("mouseleave", () => {
      btn.style.transform = "";
    });
  });
}

/* ─── TEXT SCRAMBLE ─── */
class TextScramble {
  constructor(el) {
    this.el = el;
    this.chars = "!<>-_\\/[]{}—=+*^?#________";
    this.update = this.update.bind(this);
  }
  setText(newText) {
    const oldText = this.el.innerText;
    const length = Math.max(oldText.length, newText.length);
    const promise = new Promise((resolve) => this.resolve = resolve);
    this.queue = [];
    for (let i = 0; i < length; i++) {
      const from = oldText[i] || "";
      const to = newText[i] || "";
      const start = Math.floor(Math.random() * 20);
      const end = start + Math.floor(Math.random() * 20);
      this.queue.push({ from, to, start, end });
    }
    cancelAnimationFrame(this.frameRequest);
    this.frame = 0;
    this.update();
    return promise;
  }
  update() {
    let output = "";
    let complete = 0;
    for (let i = 0, n = this.queue.length; i < n; i++) {
      let { from, to, start, end, char } = this.queue[i];
      if (this.frame >= end) {
        complete++;
        output += to;
      } else if (this.frame >= start) {
        if (!char || Math.random() < 0.28) {
          char = this.randomChar();
          this.queue[i].char = char;
        }
        output += `<span style="color: rgba(var(--cyan-rgb), 0.6)">${char}</span>`;
      } else {
        output += from;
      }
    }
    this.el.innerHTML = output;
    if (complete === this.queue.length) {
      this.resolve();
    } else {
      this.frameRequest = requestAnimationFrame(this.update);
      this.frame++;
    }
  }
  randomChar() {
    return this.chars[Math.floor(Math.random() * this.chars.length)];
  }
}

/* ─── RENDER FUNCTIONS ─── */
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
  const uptime = metrics.uptime || "—";
  const ramUsedText = ram.used_gb !== undefined && ram.total_gb !== undefined
    ? `${formatNumber(ram.used_gb)} / ${formatNumber(ram.total_gb)} GB`
    : "—";
  const ramPercent = ram.used_gb !== undefined && ram.total_gb ? Math.round((ram.used_gb / ram.total_gb) * 100) : 0;
  const batteryPercent = battery.percent ?? 0;
  const gpuUtil = gpu.utilization ?? 0;
  const networkName = network.name || "Offline";
  const cameraStatus = vision.status || "Inactive";
  const weatherSummary = state.weather
    ? (state.weather.condition || state.weather.summary || (state.weather.temperature !== undefined ? `${formatNumber(state.weather.temperature)}°` : "Unknown"))
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

/* ─── ENHANCED AUDIO WAVE VISUALIZATION ─── */
function drawWaveform() {
  const canvas = els.waveCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.height;
  const centerY = height / 2;

  let time = 0;

  function draw() {
    ctx.clearRect(0, 0, width, height);
    const energy = state.energy;
    const rgb = getComputedStyle(document.documentElement).getPropertyValue("--cyan-rgb").trim() || "89, 230, 255";

    if (state.listening || state.speaking || energy > 0.5) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${rgb}, ${0.3 + energy * 0.4})`;
      ctx.lineWidth = 2;

      for (let x = 0; x < width; x += 2) {
        const normalizedX = x / width;
        const wave1 = Math.sin(normalizedX * Math.PI * 8 + time) * (energy * 20);
        const wave2 = Math.sin(normalizedX * Math.PI * 14 + time * 1.5) * (energy * 12);
        const wave3 = Math.sin(normalizedX * Math.PI * 4 + time * 0.7) * (energy * 8);
        const y = centerY + wave1 + wave2 + wave3;

        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Second mirrored wave
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${rgb}, ${0.15 + energy * 0.2})`;
      ctx.lineWidth = 1.5;
      for (let x = 0; x < width; x += 2) {
        const normalizedX = x / width;
        const wave1 = Math.sin(normalizedX * Math.PI * 6 + time + 1) * (energy * 15);
        const wave2 = Math.sin(normalizedX * Math.PI * 10 + time * 1.2) * (energy * 10);
        const y = centerY - wave1 - wave2;

        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    time += 0.05 + energy * 0.08;
    requestAnimationFrame(draw);
  }
  draw();
}

/* ─── BOOT SEQUENCE ─── */
async function runBootSequence() {
  const logs = [
    "Initializing FRIDAY core systems...",
    "Loading neural interface modules...",
    "Calibrating optical sensors...",
    "Syncing memory banks...",
    "Establishing secure connection...",
    "Loading protocol definitions...",
    "Voice synthesis engine ready...",
    "Telemetry systems online...",
    "Wake word detection armed...",
    "Boss profile loaded: Kenan Novruzov",
    "FRIDAY is online.",
  ];

  for (let i = 0; i < logs.length; i++) {
    const line = document.createElement("div");
    line.className = "boot-line";
    line.style.animationDelay = "0ms";
    line.textContent = logs[i];
    els.bootLog.appendChild(line);
    setBootProgress(Math.round(((i + 1) / logs.length) * 100));
    await sleep(180 + Math.random() * 150);
  }

  await sleep(400);
  els.boot.classList.add("hidden");
  document.body.classList.add("ready");
  state.bootComplete = true;

  // Initialize effects after boot
  initParticles();
  initMouseParallax();
  setTimeout(initMagneticButtons, 500);
  drawWaveform();
}

/* ─── EVENT LISTENERS ─── */
function initEventListeners() {
  // Tab switching
  els.leftTabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    state.view = tab.dataset.view;

    // Animate panel transition
    els.leftPanel.style.opacity = "0";
    els.leftPanel.style.transform = "translateX(-10px)";
    setTimeout(() => {
      renderLeftPanel();
      els.leftPanel.style.transition = "opacity 300ms ease, transform 300ms ease";
      els.leftPanel.style.opacity = "1";
      els.leftPanel.style.transform = "translateX(0)";
    }, 150);
  });

  // Command input
  els.commandInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  els.sendBtn.addEventListener("click", sendMessage);

  // Voice button
  els.voiceBtn.addEventListener("click", toggleVoice);

  // Protocol button
  if (els.protocolBtn && els.protocolMenu) {
    els.protocolBtn.addEventListener("click", () => {
      els.protocolMenu.classList.toggle("hidden");
    });

    els.protocolMenu.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-protocol]");
      if (!btn) return;
      switchProtocol(btn.dataset.protocol);
      els.protocolMenu.classList.add("hidden");
    });

    document.addEventListener("click", (e) => {
      if (!els.protocolMenu.contains(e.target) && e.target !== els.protocolBtn) {
        els.protocolMenu.classList.add("hidden");
      }
    });
  }

  // Wake button
  els.wakeBtn.addEventListener("click", () => {
    state.wakeArmed = !state.wakeArmed;
    updateChips();
    showToast("Wake Word", state.wakeArmed ? "Wake word armed." : "Direct capture mode.");
  });

  // Fullscreen
  els.fullBtn.addEventListener("click", () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen();
    }
  });

  // Clear
  els.clearBtn.addEventListener("click", async () => {
    try {
      await apiPost("/api/clear");
      state.data = null;
      await syncState();
      showSuccess("Memory", "Memory cleared successfully.");
    } catch (err) {
      showError("Failed to clear memory.");
    }
  });

  // Left panel click delegation
  els.leftPanel.addEventListener("click", (e) => {
    const cmdCard = e.target.closest(".command-card");
    if (cmdCard) {
      const command = cmdCard.dataset.command;
      if (command) {
        els.commandInput.value = command;
        sendMessage();
      }
      return;
    }

    const checkbox = e.target.closest('input[type="checkbox"][data-task-id]');
    if (checkbox) {
      const taskId = checkbox.dataset.taskId;
      apiPost("/api/task/complete", { target: taskId })
        .then(() => syncState())
        .catch(() => showError("Failed to update task."));
    }
  });
}

/* ─── MESSAGE HANDLING ─── */
async function sendMessage() {
  const text = els.commandInput.value.trim();
  if (!text) return;
  els.commandInput.value = "";

  setFridayMode("thinking");

  try {
    const result = await apiPost("/api/chat", { text, source: "typed" });
    if (result.state) state.data = result.state;

    renderLeftPanel();
    renderRightPanel();
    updateChips();

    if (result.reply) {
      updateTranscript(result.reply, false);
      if (state.speaking) {
        finalizeSpeech(result.reply, { mood: { tone: "neutral", rate: 0.95, pitch: 0.9, volume: 1 } });
      }
    }

    setFridayMode("idle");
  } catch (err) {
    showError(err instanceof Error ? err.message : "Message failed.");
    setFridayMode("idle");
  }
}

function updateTranscript(text, isInterim) {
  els.transcriptLine.textContent = text;
  if (!isInterim) {
    els.transcriptLine.style.animation = "none";
    els.transcriptLine.offsetHeight; // trigger reflow
    els.transcriptLine.style.animation = "boot-fade 400ms ease";
  }
}

function finalizeSpeech(text, options) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = options?.mood?.rate ?? 0.95;
  utterance.pitch = options?.mood?.pitch ?? 0.9;
  utterance.volume = options?.mood?.volume ?? 1;
  if (state.selectedVoice) utterance.voice = state.selectedVoice;

  utterance.onstart = () => {
    state.speaking = true;
    setFridayMode("speaking");
    updateChips();
  };

  utterance.onend = () => {
    state.speaking = false;
    setFridayMode("idle");
    updateChips();
  };

  window.speechSynthesis.speak(utterance);
}

/* ─── VOICE ─── */
async function toggleVoice() {
  if (state.listening) {
    stopListening();
  } else {
    startListening();
  }
}

function startListening() {
  state.listening = true;
  setFridayMode("listening");
  updateChips();
  showToast("Voice", "Listening... Speak now.");

  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    state.recognition = new SpeechRecognition();
    state.recognition.continuous = true;
    state.recognition.interimResults = true;
    state.recognition.lang = "en-US";

    state.recognition.onresult = (e) => {
      let final = "";
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      if (interim) updateTranscript(interim, true);
      if (final) {
        updateTranscript(final, false);
        handleVoiceInput(final);
      }
    };

    state.recognition.onerror = () => {
      stopListening();
    };

    state.recognition.onend = () => {
      if (state.listening) {
        try { state.recognition.start(); } catch { stopListening(); }
      }
    };

    try { state.recognition.start(); } catch { stopListening(); }
  }
}

function stopListening() {
  state.listening = false;
  setFridayMode("idle");
  updateChips();
  if (state.recognition) {
    try { state.recognition.stop(); } catch {}
    state.recognition = null;
  }
}

async function handleVoiceInput(text) {
  setFridayMode("thinking");
  try {
    const result = await apiPost("/api/chat", { text, source: "voice" });
    if (result.state) state.data = result.state;
    renderLeftPanel();
    renderRightPanel();
    updateChips();
    if (result.reply) {
      finalizeSpeech(result.reply, { mood: { tone: "neutral", rate: 0.95, pitch: 0.9, volume: 1 } });
    }
  } catch (err) {
    showError("Voice command failed.");
  }
  setFridayMode(state.listening ? "listening" : "idle");
}

/* ─── SYNC ─── */
async function syncState() {
  try {
    const data = await apiGet("/api/state");
    state.data = data;
    renderLeftPanel();
    renderRightPanel();
    updateChips();
    if (data.protocol?.colors) applyProtocolColors(data.protocol.colors);
  } catch {
    // silent fail
  }
}

async function syncMetrics() {
  try {
    const data = await apiGet("/api/metrics");
    state.metrics = data;
    renderRightPanel();
    updateChips();
  } catch {
    // silent fail
  }
}

/* ─── CLOCK ─── */
function startClock() {
  setInterval(() => {
    els.timeChip.textContent = formatClock();
  }, 1000);
}

/* ─── INIT ─── */
async function init() {
  await syncState();
  await syncMetrics();
  initEventListeners();
  startClock();
  runBootSequence();

  // Periodic sync
  setInterval(syncMetrics, 5000);
  setInterval(syncState, 10000);

  // Load voices
  if ("speechSynthesis" in window) {
    const loadVoices = () => {
      state.voices = window.speechSynthesis.getVoices();
      const preferred = state.voices.find(v => v.name.includes("Google US English") || v.name.includes("Samantha"));
      if (preferred) state.selectedVoice = preferred;
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  // Load protocol
  loadProtocol();
}

// Start when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
