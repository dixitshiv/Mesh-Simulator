let selectedMode = 'l4';
let nodes = [];
let ws;

async function init() {
  const res = await fetch('/api/services');
  const data = await res.json();
  const services = data.services;

  const sourceEl = document.getElementById('source');
  const destEl = document.getElementById('destination');
  const algoServiceEl = document.getElementById('algo-service');

  services.forEach(s => {
    sourceEl.innerHTML += `<option value="${s}">${s}</option>`;
    destEl.innerHTML += `<option value="${s}">${s}</option>`;
    algoServiceEl.innerHTML += `<option value="${s}">${s}</option>`;
  });

  destEl.selectedIndex = 1;

  await refreshNodes();
  connectWS();
}

async function refreshNodes() {
  const res = await fetch('/api/nodes');
  const data = await res.json();
  nodes = data.nodes;
  renderNodes();
}

function renderNodes() {
  const grid = document.getElementById('nodes-grid');
  grid.innerHTML = '';
  nodes.forEach(node => {
    const card = document.createElement('div');
    card.className = 'node-card' + (node.healthy ? '' : ' down');
    card.innerHTML = `
      <div class="node-name">${node.node_id}</div>
      <div class="node-status">
        <span class="dot ${node.healthy ? 'up' : 'down'}"></span>
        ${node.healthy ? 'healthy' : 'down'}
      </div>
      <div class="node-latency">${node.base_latency_ms}ms base</div>
      <div class="node-conns">${node.active_connections} conn</div>
    `;
    card.onclick = () => toggleNode(node.node_id, node.healthy);
    grid.appendChild(card);
  });
}

async function toggleNode(nodeId, currentlyHealthy) {
  await fetch('/api/node/health', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId, healthy: !currentlyHealthy })
  });
  await refreshNodes();
}

function setMode(mode) {
  selectedMode = mode;
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
}

async function sendRequest() {
  const source = document.getElementById('source').value;
  const destination = document.getElementById('destination').value;

  const res = await fetch('/api/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, destination, mode: selectedMode })
  });

  const data = await res.json();
  renderTrace(data);
  addLog(data, source, destination);
  await refreshNodes();
}

async function sendBurst() {
  for (let i = 0; i < 10; i++) {
    await sendRequest();
  }
}

function renderTrace(data) {
  const box = document.getElementById('trace-box');

  if (data.error && (!data.trace || data.trace.spans.length === 0)) {
    box.innerHTML = `<div class="error-msg">✗ ${data.error}</div>`;
    return;
  }

  const spans = data.trace.spans;
  const maxMs = Math.max(...spans.map(s => s.duration_ms || 1));

  let html = `<div class="trace-id">trace id: ${data.trace.trace_id} · mode: ${data.mode.toUpperCase()}</div>`;

  spans.forEach(span => {
    const ms = span.duration_ms || 0;
    const pct = Math.max(4, (ms / maxMs) * 100);
    const isError = span.status !== 'ok';
    html += `
      <div class="span-row">
        <div class="span-label">${span.service}</div>
        <div class="span-bar-wrap">
          <div class="span-bar ${isError ? 'error' : ''}" style="width:${pct}%"></div>
        </div>
        <div class="span-ms">${ms}ms</div>
        <div class="span-status ${isError ? 'status-error' : 'status-ok'}">${span.status}</div>
      </div>
    `;
  });

  html += `<div class="total-ms">total: ${data.trace.total_ms}ms</div>`;

  if (data.error) {
    html += `<div class="error-msg">✗ ${data.error}</div>`;
  }

  box.innerHTML = html;
}

function addLog(data, source, destination) {
  const box = document.getElementById('log-box');
  const time = new Date().toLocaleTimeString();
  const ok = !data.error;
  const ms = data.trace ? data.trace.total_ms : '—';
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `<span style="color:#484f58">${time}</span> ${source} → ${destination} [${data.mode.toUpperCase()}] <span class="${ok ? 'ok' : 'err'}">${ok ? '✓' : '✗'} ${ok ? ms + 'ms' : data.error}</span>`;
  box.prepend(entry);
}

function connectWS() {
  ws = new WebSocket(`ws://${location.host}/ws/metrics`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    nodes = data.nodes;
    renderNodes();
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
}

async function setAlgorithm() {
  const service = document.getElementById('algo-service').value;
  const algorithm = document.getElementById('algo-select').value;
  await fetch('/api/algorithm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ service, algorithm })
  });
  const fb = document.getElementById('algo-feedback');
  fb.textContent = `✓ ${service} set to ${algorithm.replace('_', ' ')}`;
  setTimeout(() => fb.textContent = '', 2000);
}

init();