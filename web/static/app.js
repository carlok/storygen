let videoWidth = 1080, videoHeight = 1920, fontSize = 48;

const tabsEl        = document.getElementById('tabs');
const blocksEl      = document.getElementById('blocks');
const btn           = document.getElementById('generate-btn');
const statusEl      = document.getElementById('status');
const downloadLink  = document.getElementById('download-link');
const emailToEl     = document.getElementById('email-to');
const sendEmailBtn  = document.getElementById('send-email-btn');
const emailStatusEl = document.getElementById('email-status');
const modalEl       = document.getElementById('modal');
const modalMsg      = document.getElementById('modal-msg');

let lastFilename = null;

function showModal(msg) {
  modalMsg.textContent = msg;
  modalEl.hidden = false;
}
function hideModal() {
  modalEl.hidden = true;
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function drawPreview(canvas, imgEl, x, y, text, align_center, center_x) {
  const displayW = canvas.parentElement.clientWidth || 200;
  const scale = displayW / videoWidth;
  canvas.width  = displayW;
  canvas.height = Math.round(videoHeight * scale);

  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (imgEl.complete && imgEl.naturalWidth) {
    const imgScale = Math.min(canvas.width / imgEl.naturalWidth, canvas.height / imgEl.naturalHeight);
    const iw = imgEl.naturalWidth * imgScale;
    const ih = imgEl.naturalHeight * imgScale;
    ctx.drawImage(imgEl, (canvas.width - iw) / 2, (canvas.height - ih) / 2, iw, ih);
  }

  const sy = y * scale;
  const fs = Math.max(7, fontSize * scale);
  const lh = fs * 1.35;

  // textBaseline='top' matches Pillow's 'la' anchor: y = top of text
  ctx.font = `bold ${fs}px system-ui, sans-serif`;
  ctx.textBaseline = 'top';

  const lines = (text || '').split('\n');
  const pad = 4;

  // Use actualBoundingBoxRight for accurate visual width (excludes trailing space pixels)
  const lineWidths = lines.map(l => {
    const m = ctx.measureText(l || ' ');
    return m.actualBoundingBoxRight ?? m.width;
  });
  const maxW = Math.max(...lineWidths);
  const totalH = lines.length * lh;

  const sx = center_x ? (canvas.width - maxW) / 2 : x * scale;

  ctx.fillStyle = 'rgba(0,0,0,0.82)';
  ctx.beginPath();
  ctx.roundRect(sx - pad, sy - pad, maxW + pad * 2, totalH + pad * 2, 5);
  ctx.fill();

  ctx.fillStyle = '#fff';
  lines.forEach((line, idx) => {
    const lw = lineWidths[idx];
    const lineX = align_center ? sx + (maxW - lw) / 2 : sx;
    ctx.fillText(line, lineX, sy + idx * lh);
  });

  if (!center_x) {
    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(sx, sy, 4, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function setupCanvas(canvas, block) {
  const i = block.index;
  const imgEl = new Image();
  imgEl.src = `/api/image/${encodeURIComponent(block.image)}`;

  const card = canvas.closest('.block-card');

  function readPos() {
    return {
      x:            parseInt(card.querySelector(`input[data-px="${i}"]`).value) || 0,
      y:            parseInt(card.querySelector(`input[data-py="${i}"]`).value) || 0,
      text:         card.querySelector(`textarea[data-index="${i}"]`).value,
      align_center: card.querySelector(`input[data-al="${i}"]`).checked,
      center_x:     card.querySelector(`input[data-cx="${i}"]`).checked,
    };
  }

  function redraw() {
    const { x, y, text, align_center, center_x } = readPos();
    const xRow = card.querySelector('.x-row');
    xRow.style.opacity       = center_x ? '0.35' : '1';
    xRow.style.pointerEvents = center_x ? 'none'  : '';
    drawPreview(canvas, imgEl, x, y, text, align_center, center_x);
  }

  function setPos(ax, ay) {
    const cx = card.querySelector(`input[data-cx="${i}"]`).checked;
    if (!cx) {
      ax = Math.max(0, Math.min(videoWidth, ax));
      card.querySelector(`input[data-px="${i}"]`).value = ax;
      card.querySelector(`span[data-vx="${i}"]`).textContent = ax;
    }
    ay = Math.max(0, Math.min(videoHeight, ay));
    card.querySelector(`input[data-py="${i}"]`).value = ay;
    card.querySelector(`span[data-vy="${i}"]`).textContent = ay;
    redraw();
  }

  function coordsFromEvent(e) {
    const r = canvas.getBoundingClientRect();
    const s = videoWidth / canvas.offsetWidth;
    return [Math.round((e.clientX - r.left) * s), Math.round((e.clientY - r.top) * s)];
  }

  // mouse drag
  let dragging = false;
  canvas.addEventListener('mousedown',  e => { dragging = true; setPos(...coordsFromEvent(e)); });
  canvas.addEventListener('mousemove',  e => { if (dragging) setPos(...coordsFromEvent(e)); });
  canvas.addEventListener('mouseup',    ()  => { dragging = false; });
  canvas.addEventListener('mouseleave', ()  => { dragging = false; });

  // touch drag
  canvas.addEventListener('touchstart', e => { e.preventDefault(); setPos(...coordsFromEvent(e.touches[0])); }, { passive: false });
  canvas.addEventListener('touchmove',  e => { e.preventDefault(); setPos(...coordsFromEvent(e.touches[0])); }, { passive: false });

  // slider → value label + canvas
  card.querySelector(`input[data-px="${i}"]`).addEventListener('input', e => {
    card.querySelector(`span[data-vx="${i}"]`).textContent = e.target.value;
    redraw();
  });
  card.querySelector(`input[data-py="${i}"]`).addEventListener('input', e => {
    card.querySelector(`span[data-vy="${i}"]`).textContent = e.target.value;
    redraw();
  });
  card.querySelector(`input[data-al="${i}"]`).addEventListener('change', redraw);
  card.querySelector(`input[data-cx="${i}"]`).addEventListener('change', redraw);
  const ta = card.querySelector(`textarea[data-index="${i}"]`);
  ta.addEventListener('input', redraw);

  imgEl.onload = redraw;

  // redraw when container resizes (tab switch reveals card, window resize)
  new ResizeObserver(redraw).observe(canvas.parentElement);
}

function switchTab(index) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', +b.dataset.tab === index));
  document.querySelectorAll('.block-card').forEach(c => c.classList.toggle('active', +c.dataset.index === index));
}

async function loadBlocks() {
  const res  = await fetch('/api/blocks');
  const data = await res.json();
  videoWidth  = data.video_width  || 1080;
  videoHeight = data.video_height || 1920;
  fontSize    = data.font_size    || 48;

  tabsEl.innerHTML   = '';
  blocksEl.innerHTML = '';

  data.blocks.forEach(b => {
    // tab button
    const tab = document.createElement('button');
    tab.className    = 'tab-btn' + (b.index === 0 ? ' active' : '');
    tab.dataset.tab  = b.index;
    tab.textContent  = `Block ${b.index + 1}`;
    tab.addEventListener('click', () => switchTab(b.index));
    tabsEl.appendChild(tab);

    // card
    const card = document.createElement('div');
    card.className     = 'block-card' + (b.index === 0 ? ' active' : '');
    card.dataset.index = b.index;
    card.innerHTML = `
      <div class="block-meta">
        <strong>${b.image}</strong> &nbsp;·&nbsp; ${b.start}s – ${b.end}s (${b.end - b.start}s)
      </div>
      <div class="card-body">
        <div class="controls">
          <textarea data-index="${b.index}">${escapeHtml(b.text)}</textarea>
          <div class="slider-row x-row">
            <div class="slider-label">X <span class="val" data-vx="${b.index}">${b.text_position[0]}</span></div>
            <input type="range" data-px="${b.index}" min="0" max="${videoWidth}"  value="${b.text_position[0]}" />
          </div>
          <div class="slider-row">
            <div class="slider-label">Y <span class="val" data-vy="${b.index}">${b.text_position[1]}</span></div>
            <input type="range" data-py="${b.index}" min="0" max="${videoHeight}" value="${b.text_position[1]}" />
          </div>
          <div class="toggles">
            <label class="toggle-label">
              <input type="checkbox" data-al="${b.index}" ${b.align_center ? 'checked' : ''} /> Align center
            </label>
            <label class="toggle-label">
              <input type="checkbox" data-cx="${b.index}" ${b.center_x    ? 'checked' : ''} /> Center X
            </label>
            <label class="toggle-label">
              <input type="checkbox" data-bw="${b.index}" ${b.bw       ? 'checked' : ''} /> B&amp;W
            </label>
            <label class="toggle-label">
              <input type="checkbox" data-fi="${b.index}" ${b.fade_in  ? 'checked' : ''} /> Fade in
            </label>
            <label class="toggle-label">
              <input type="checkbox" data-fo="${b.index}" ${b.fade_out ? 'checked' : ''} /> Fade out
            </label>
          </div>
        </div>
        <div class="preview-wrap">
          <canvas class="preview"></canvas>
          <div class="preview-hint">drag to reposition text</div>
        </div>
      </div>
    `;
    blocksEl.appendChild(card);
    setupCanvas(card.querySelector('canvas.preview'), b);
  });
}

btn.addEventListener('click', async () => {
  const updates = [...document.querySelectorAll('textarea[data-index]')].map(el => ({
    index:    parseInt(el.dataset.index, 10),
    text:     el.value,
    align_center: document.querySelector(`input[data-al="${el.dataset.index}"]`)?.checked ?? false,
    center_x:     document.querySelector(`input[data-cx="${el.dataset.index}"]`)?.checked ?? false,
    bw:       document.querySelector(`input[data-bw="${el.dataset.index}"]`)?.checked ?? false,
    fade_in:  document.querySelector(`input[data-fi="${el.dataset.index}"]`)?.checked ?? false,
    fade_out: document.querySelector(`input[data-fo="${el.dataset.index}"]`)?.checked ?? false,
    text_position: [
      parseInt(document.querySelector(`input[data-px="${el.dataset.index}"]`)?.value || 100, 10),
      parseInt(document.querySelector(`input[data-py="${el.dataset.index}"]`)?.value || 900, 10),
    ],
  }));

  btn.disabled = true;
  downloadLink.style.display = 'none';
  statusEl.className = '';
  statusEl.textContent = '';
  showModal('Generating video…');

  try {
    const res  = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Unknown error');

    statusEl.textContent = 'Done!';
    lastFilename = data.filename;
    downloadLink.href     = `/api/video?name=${encodeURIComponent(data.filename)}`;
    downloadLink.download = data.filename;
    downloadLink.style.display = 'inline-block';
    sendEmailBtn.disabled = false;
    emailStatusEl.className = '';
    emailStatusEl.textContent = '';
  } catch (err) {
    statusEl.className   = 'error';
    statusEl.textContent = 'Error: ' + err.message;
  } finally {
    hideModal();
    btn.disabled = false;
  }
});

sendEmailBtn.addEventListener('click', async () => {
  const to = emailToEl.value.trim();
  if (!to || !lastFilename) return;

  sendEmailBtn.disabled = true;
  emailStatusEl.className = '';
  emailStatusEl.textContent = '';
  showModal('Sending video…');

  try {
    const res  = await fetch('/api/send-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to, filename: lastFilename }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Send failed');
    emailStatusEl.className = 'success';
    emailStatusEl.textContent = 'Sent!';
  } catch (err) {
    emailStatusEl.className = 'error';
    emailStatusEl.textContent = 'Error: ' + err.message;
  } finally {
    hideModal();
    sendEmailBtn.disabled = false;
  }
});

loadBlocks();
