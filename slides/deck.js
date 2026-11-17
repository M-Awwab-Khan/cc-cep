(() => {
  const stage = document.getElementById('stage');
  const slides = [...document.querySelectorAll('.slide')];
  const notesEl = document.getElementById('notes');
  const counter = document.getElementById('counter');
  const progress = document.getElementById('progress');
  let idx = 0;

  /* ---- scale the fixed 1920x1080 stage to the window ---- */
  stage.style.position = 'absolute'; stage.style.left = '50%'; stage.style.top = '50%';
  function fit() {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    stage.style.transform = `translate(-50%,-50%) scale(${s})`;
  }
  addEventListener('resize', fit); fit();

  /* ---- data (from results/curated/final-study-summary.json and followup-table.tex) ---- */
  const CONDS = [
    { k: 'abort32', label: 'abort · 32 req/s' }, { k: 'abort64', label: 'abort · 64 req/s' },
    { k: 'delay32', label: 'delay · 32 req/s' }, { k: 'delay64', label: 'delay · 64 req/s' }
  ];
  const DATA = {
    abort32: { static: [4.6, 16.03], threshold: [0, 0.26], 'open-loop': [0, 13.42], 'closed-loop': [0, 4.46], paced: [1.0, 15.41] },
    abort64: { static: [21.6, 15.42], threshold: [0, 0.26], 'open-loop': [0, 13.40], 'closed-loop': [0, 4.21], paced: [1.6, 15.09] },
    delay32: { static: [9.6, 15.25], threshold: [0, 0.82], 'open-loop': [0, 13.24], 'closed-loop': [0.4, 14.05], paced: [1.0, 15.03] },
    delay64: { static: [16.2, 15.08], threshold: [0, 0.86], 'open-loop': [0, 13.25], 'closed-loop': [0, 14.05], paced: [0.8, 14.81] }
  };
  const NAMES = { static: 'Static', threshold: 'Threshold', 'open-loop': 'Open-loop', 'closed-loop': 'Closed-loop', paced: 'Paced' };
  const SUBS = { static: 'fixed 10%', threshold: 'stop at burn ≥ 2', 'open-loop': 'plan once', 'closed-loop': 'burn-rate loop', paced: 'follow-up' };

  function explorer(suffix, policies) {
    const tabs = document.getElementById('tabs-' + suffix);
    const over = document.getElementById('bars-over-' + suffix);
    const exp = document.getElementById('bars-exp-' + suffix);
    let cur = 'abort32';
    function draw() {
      const rows = (which, max, fmt, cls) => policies.map(p => {
        const v = DATA[cur][p][which], hatch = p === 'paced';
        return `<div class="brow"><div class="nm">${NAMES[p]}<small>${SUBS[p]}</small></div>
          <div class="btrack"><i class="${hatch ? 'hatch' : cls}" data-w="${Math.max(v / max * 100, v > 0 ? 0.8 : 0)}"></i></div>
          <div class="bval ${hatch ? 'lime' : ''}">${fmt(v)}</div></div>`;
      }).join('');
      over.innerHTML = rows(0, 24, v => v.toFixed(1), 'co');
      exp.innerHTML = rows(1, 30, v => v.toFixed(2), '');
      requestAnimationFrame(() => requestAnimationFrame(() => {
        [...over.querySelectorAll('i'), ...exp.querySelectorAll('i')].forEach(el => el.style.width = el.dataset.w + '%');
      }));
      [...tabs.children].forEach(t => t.classList.toggle('on', t.dataset.k === cur));
    }
    tabs.innerHTML = CONDS.map(c => `<button class="tab" data-k="${c.k}">${c.label}</button>`).join('');
    tabs.addEventListener('click', e => { const b = e.target.closest('.tab'); if (b) { cur = b.dataset.k; draw(); } });
    return { redraw: () => { cur = 'abort32'; draw(); } };
  }
  const exMain = explorer('main', ['static', 'threshold', 'open-loop', 'closed-loop']);
  const exPaced = explorer('paced', ['static', 'threshold', 'open-loop', 'closed-loop', 'paced']);

  /* ---- decorative builders ---- */
  const dots = document.getElementById('dots');
  dots.innerHTML = '<i></i>'.repeat(100);
  let dotTimer;
  function dotsRun() {
    clearInterval(dotTimer);
    const all = [...dots.children];
    all.forEach(d => d.className = '');
    dotTimer = setInterval(() => {
      all.forEach(d => d.className = '');
      const n = 18 + Math.floor(Math.random() * 12);
      const picks = [...all.keys()].sort(() => Math.random() - .5).slice(0, n);
      picks.forEach((i, j) => { all[i].classList.add('fault'); if (j === 0 || (j < 3 && Math.random() < .35)) all[i].className = 'bad'; });
    }, 1100);
  }
  const track = document.getElementById('track');
  if (track) {
    let h = '';
    for (let s = 0; s < 40; s++) {
      const v = 18 + Math.round(60 * Math.abs(Math.sin(s * 0.7) * Math.cos(s * 0.23)) + (s > 29 ? 40 : 0));
      h += `<i class="tick" style="left:${s * 37.5 + 8}px;height:${v}px"></i>`;
    }
    track.insertAdjacentHTML('afterbegin', h);
  }

  /* ---- counters ---- */
  function runCounters(slide) {
    slide.querySelectorAll('[data-count]').forEach(el => {
      const end = +el.dataset.count, t0 = performance.now(), dur = 1400;
      const tick = t => { const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = Math.round(end * e); if (p < 1) requestAnimationFrame(tick); };
      el.textContent = 0; requestAnimationFrame(tick);
      setTimeout(() => { el.textContent = end; }, dur + 150); /* guarantee the final value even if frames are dropped */
    });
  }

  /* ---- fragments ---- */
  function frags(slide) { return [...slide.querySelectorAll('.frag')]; }
  function setFrags(slide, all) { frags(slide).forEach(f => f.classList.toggle('on', all)); }
  function revealNext() {
    const f = frags(slides[idx]).find(x => !x.classList.contains('on'));
    if (f) { f.classList.add('on'); return true; } return false;
  }
  function hidePrev() {
    const on = frags(slides[idx]).filter(x => x.classList.contains('on'));
    if (on.length) { on[on.length - 1].classList.remove('on'); return true; } return false;
  }

  /* ---- navigation ---- */
  function show(n, back) {
    n = Math.max(0, Math.min(slides.length - 1, n));
    slides[idx].classList.remove('active');
    idx = n;
    const s = slides[idx];
    setFrags(s, !!back);
    s.classList.add('active');
    counter.textContent = String(idx + 1).padStart(2, '0') + ' / ' + String(slides.length).padStart(2, '0');
    progress.style.width = ((idx + 1) / slides.length * 100) + '%';
    const nt = s.querySelector('.notes');
    notesEl.innerHTML = nt ? nt.innerHTML : '';
    document.title = (s.dataset.title || 'Slide') + ' · CEP';
    history.replaceState(null, '', '#' + (idx + 1));
    runCounters(s);
    if (s.dataset.title === 'The problem') dotsRun(); else clearInterval(dotTimer);
    if (s.dataset.title === 'Main results') exMain.redraw();
    if (s.dataset.title === 'Paced vs the four') exPaced.redraw();
  }
  const next = () => { if (!revealNext()) show(idx + 1); };
  const prev = () => { if (!hidePrev()) show(idx - 1, true); };

  addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    switch (e.key) {
      case 'ArrowRight': case 'ArrowDown': case 'PageDown': case ' ': case 'Enter': e.preventDefault(); next(); break;
      case 'ArrowLeft': case 'ArrowUp': case 'PageUp': case 'Backspace': e.preventDefault(); prev(); break;
      case 'Home': show(0); break;
      case 'End': show(slides.length - 1, true); break;
      case 'n': case 'N': notesEl.classList.toggle('show'); break;
      case 'f': case 'F': document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); break;
    }
  });
  let tx = null;
  addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, { passive: true });
  addEventListener('touchend', e => { if (tx === null) return; const d = e.changedTouches[0].clientX - tx; if (Math.abs(d) > 60) (d < 0 ? next : prev)(); tx = null; });
  addEventListener('click', e => {
    if (e.target.closest('.tab,.tabs')) return;
    const x = e.clientX / innerWidth; if (x > .85) next(); else if (x < .08) prev();
  });

  setTimeout(() => { const h = document.getElementById('hint'); if (h) h.style.opacity = 0; }, 7000);
  const start = parseInt(location.hash.slice(1), 10);
  show(Number.isFinite(start) ? start - 1 : 0);
})();
