/* Offline sprite playback. No requests, analytics, storage or application detection. */
(() => {
  'use strict';
  const states = {
    idle: { row: 0, title: '静静陪伴', text: '轻微呼吸与发梢摆动，留一点安静给思考。', times: [280,110,110,140,140,320], order: 1 },
    'running-right': { row: 1, title: '一起向右', text: '方向移动的姿态预览。桌面版拖动角色时，她会朝移动的方向迈步。', times: [120,120,120,120,120,120,120,220], order: 9 },
    'running-left': { row: 2, title: '一起向左', text: '换个位置，换一种心情。桌面版可以把星澜拖到你喜欢的角落。', times: [120,120,120,120,120,120,120,220], order: 8 },
    waving: { row: 3, title: '见到你，很开心', text: '一声轻轻的招呼。点击角色，也能让她向你招手。', times: [140,140,140,280], order: 5, once: true },
    jumping: { row: 4, title: '一点小小的雀跃', text: '给刚刚完成的小事，一次轻盈的庆祝。双击角色也可以触发。', times: [140,140,140,140,280], order: 6, once: true },
    failed: { row: 5, title: '再试一次，也没关系', text: '遇到问题时的反应动作。整理一下心情，再继续往前走。', times: [140,140,140,140,140,140,140,240], order: 7, once: true },
    waiting: { row: 6, title: '等你一个想法', text: '准备好了，就告诉她。等待的姿态，比催促更温柔一点。', times: [150,150,150,150,150,260], order: 3 },
    running: { row: 7, title: '和你一起专注', text: '认真思考、安静投入。让工作中的桌面多一点陪伴感。', times: [120,120,120,120,120,220], order: 2 },
    review: { row: 8, title: '再认真看一眼', text: '稍稍俯身，检查成果。给完成之前的最后一步，一点耐心。', times: [150,150,150,150,150,280], order: 4 }
  };
  const $ = id => document.getElementById(id);
  const stage = $('stage'), pet = $('pet'), pauseButton = $('pause-button');
  const followToggle = $('follow-toggle'), reduceToggle = $('reduce-motion');
  const buttons = [...document.querySelectorAll('[data-state]')];
  const mediaPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  let selected = 'idle', frame = 0, elapsed = 0, previousTime = null;
  let paused = false, reduced = mediaPreference.matches, gaze = null, loaded = false;
  let singleClickTimer = null, manualMotionChoice = false;
  reduceToggle.checked = reduced;

  function directionFromVector(dx, dy) {
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) return 0;
    const angle = (Math.atan2(dx, -dy) * 180 / Math.PI + 360) % 360;
    return Math.round(angle / 22.5) % 16;
  }

  function frameForDirection(index) {
    const direction = ((Math.round(index) % 16) + 16) % 16;
    return { row: 9 + Math.floor(direction / 8), column: direction % 8 };
  }

  function cancelPendingClick() {
    if (singleClickTimer !== null) window.clearTimeout(singleClickTimer);
    singleClickTimer = null;
  }

  function paint() {
    const position = gaze !== null && !paused && !reduced
      ? frameForDirection(gaze) : { row: states[selected].row, column: frame };
    pet.style.backgroundPosition = `${-position.column * 192}px ${-position.row * 208}px`;
    $('frame-label').textContent = gaze !== null && !paused && !reduced
      ? `LOOK / ${String(gaze * 22.5).padStart(3, '0')}°`
      : `${selected.toUpperCase()} / ${String(frame + 1).padStart(2, '0')}`;
  }

  function setState(name) {
    if (!Object.hasOwn(states, name)) return false;
    cancelPendingClick();
    selected = name; frame = 0; elapsed = 0; gaze = null; previousTime = null;
    const state = states[name];
    $('state-title').textContent = state.title;
    $('state-description').textContent = state.text;
    $('state-index').textContent = `${String(state.order).padStart(2, '0')} / 09`;
    pet.setAttribute('aria-label', `${state.title}的星澜`);
    for (const button of buttons) {
      const active = button.dataset.state === name;
      button.classList.toggle('selected', active);
      button.setAttribute('aria-pressed', String(active));
    }
    paint(); return true;
  }

  function updateControls() {
    pauseButton.innerHTML = paused ? '<span aria-hidden="true">▷</span> 继续动作' : '<span aria-hidden="true">Ⅱ</span> 暂停动作';
    pauseButton.setAttribute('aria-pressed', String(paused));
    pauseButton.disabled = reduced;
    followToggle.disabled = reduced;
    $('stage-hint').textContent = reduced ? '减少动态已开启 · 点击按钮查看姿态' : paused ? '动作已暂停 · 点击继续动作恢复' : '单击招手 · 双击跳跃';
    paint();
  }

  function tick(now) {
    const delta = previousTime === null ? 0 : Math.min(150, now - previousTime);
    previousTime = now;
    if (loaded && !paused && !reduced && gaze === null && !document.hidden) {
      elapsed += delta;
      const state = states[selected];
      if (elapsed >= state.times[frame]) {
        elapsed -= state.times[frame]; frame += 1;
        if (frame >= state.times.length) {
          if (state.once) setState('idle');
          else frame = 0;
        }
        paint();
      }
    }
    window.requestAnimationFrame(tick);
  }

  buttons.forEach(button => button.addEventListener('click', () => setState(button.dataset.state)));
  pauseButton.addEventListener('click', () => {
    cancelPendingClick();
    paused = !paused; gaze = null; previousTime = null; updateControls();
  });
  followToggle.addEventListener('change', () => { cancelPendingClick(); gaze = null; paint(); });
  reduceToggle.addEventListener('change', () => {
    cancelPendingClick();
    manualMotionChoice = true; reduced = reduceToggle.checked; gaze = null; frame = 0;
    elapsed = 0; previousTime = null; updateControls();
  });
  mediaPreference.addEventListener('change', event => {
    if (manualMotionChoice) return;
    reduced = event.matches; reduceToggle.checked = reduced; gaze = null; frame = 0;
    elapsed = 0; previousTime = null; updateControls();
  });
  stage.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch' || !followToggle.checked || paused || reduced || selected !== 'idle') return;
    const bounds = pet.getBoundingClientRect();
    const dx = event.clientX - (bounds.left + bounds.width / 2);
    const dy = event.clientY - (bounds.top + bounds.height * .28);
    if (Math.hypot(dx, dy) < 24) { gaze = null; paint(); return; }
    gaze = directionFromVector(dx, dy); paint();
  });
  stage.addEventListener('pointerleave', () => { gaze = null; elapsed = 0; previousTime = null; paint(); });
  pet.addEventListener('click', () => {
    cancelPendingClick();
    singleClickTimer = window.setTimeout(() => {
      singleClickTimer = null;
      setState('waving');
    }, 500);
  });
  pet.addEventListener('dblclick', event => {
    event.preventDefault(); cancelPendingClick(); setState('jumping');
  });
  document.addEventListener('visibilitychange', () => { previousTime = null; elapsed = 0; });
  const atlas = new Image();
  atlas.addEventListener('load', () => {
    loaded = atlas.naturalWidth === 1536 && atlas.naturalHeight === 2288;
    $('asset-error').hidden = loaded;
  });
  atlas.addEventListener('error', () => { $('asset-error').hidden = false; });
  atlas.src = 'media/xinglan-v2.png';
  updateControls(); paint(); window.requestAnimationFrame(tick);

  // Small API for choosing poses and validating this offline demo.
  window.XinglanDemo = Object.freeze({
    setState, directionFromVector, frameForDirection,
    getState: () => ({ selected, frame, paused, reduced, gaze, loaded }),
    states: Object.freeze(Object.fromEntries(Object.entries(states).map(([name, state]) => [name, Object.freeze({ row: state.row, frames: state.times.length })])))
  });
})();
