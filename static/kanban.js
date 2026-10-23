'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let model, dragged = null;
  const moving = new Set();
  const colors = ['#ccf08b', '#9ad4e8', '#b5b0f4', '#f1bbd3', '#edc285', '#82d1be', '#c7b092', '#9cc1f3', '#c2d59a'];
  const openNotes = new Set();
  function error(message) { $('boardError').textContent = message; $('boardError').hidden = false; }
  function rememberNotes() {
    $('board').querySelectorAll('details[data-step]').forEach(details => {
      if (details.open) openNotes.add(details.dataset.step); else openNotes.delete(details.dataset.step);
    });
  }
  async function move(step, status) {
    if (moving.has(step.id) || status === model.steps[step.id].status) return;
    moving.add(step.id); $('boardError').hidden = true;
    $('boardStatus').textContent = 'Enregistrement du déplacement…';
    const select = document.getElementById(`move-${step.id}`);
    if (select) select.disabled = true;
    try {
      await BenderStages.save(model, step.id, {status});
      rememberNotes(); render();
      $('boardStatus').textContent = `Étape ${step.number} déplacée vers « ${BenderStages.labels[status]} ».`;
      document.getElementById(`move-${step.id}`)?.focus();
    } catch (failure) {
      if (select) select.value = model.steps[step.id].status;
      error(failure.message); $('boardStatus').textContent = 'Déplacement non enregistré.';
    } finally { moving.delete(step.id); document.getElementById(`move-${step.id}`)?.removeAttribute('disabled'); }
  }
  function card(step) {
    const state = model.steps[step.id];
    const card = document.createElement('article'); card.className = 'kanban-card'; card.style.setProperty('--step-color', colors[step.number]);
    const top = document.createElement('div'); top.className = 'card-top';
    const number = document.createElement('span'); number.className = 'card-number'; number.textContent = `ÉTAPE ${String(step.number).padStart(2, '0')}`;
    const handle = document.createElement('span'); handle.className = 'drag-handle'; handle.textContent = '⠿'; handle.draggable = true;
    handle.title = 'Glisser cette tuile, ou utiliser Déplacer vers'; handle.setAttribute('aria-hidden', 'true');
    handle.addEventListener('dragstart', event => {
      if (moving.has(step.id)) { event.preventDefault(); return; }
      dragged = step.id; event.dataTransfer.setData('text/plain', step.id); event.dataTransfer.effectAllowed = 'move'; card.classList.add('dragging');
    });
    handle.addEventListener('dragend', () => {
      dragged = null; card.classList.remove('dragging'); document.querySelectorAll('.drop-ready').forEach(c => c.classList.remove('drop-ready'));
    });
    top.append(number, handle);
    const title = document.createElement('h2'); const link = document.createElement('a'); link.href = `/roadmap#${step.id}`; link.textContent = step.title; title.append(link);
    const domains = document.createElement('p'); domains.className = 'card-domains'; domains.textContent = step.domains.join(' · ');
    const checked = step.tasks.filter(task => model.progress[task.id].done).length;
    const progress = document.createElement('p'); progress.className = 'card-checks'; progress.textContent = `${checked} / ${step.tasks.length} actions cochées`;
    const note = document.createElement('p'); note.className = 'card-note'; note.textContent = state.notes || 'Aucune note. Ajoute le contexte, une attente ou la prochaine action.';
    const selectLabel = document.createElement('label'); selectLabel.className = 'card-move'; selectLabel.textContent = 'Déplacer vers';
    const select = document.createElement('select'); select.id = `move-${step.id}`;
    select.setAttribute('aria-label', `Déplacer l’étape ${step.number} : ${step.title}`);
    Object.entries(BenderStages.labels).forEach(([value, text]) => {
      const option = document.createElement('option'); option.value = value; option.textContent = text; select.append(option);
    });
    select.value = state.status; select.disabled = moving.has(step.id);
    select.addEventListener('change', () => move(step, select.value)); selectLabel.append(select);
    const details = document.createElement('details'); details.className = 'card-editor'; details.dataset.step = step.id; details.open = openNotes.has(step.id);
    const summary = document.createElement('summary'); summary.textContent = 'Modifier la note';
    details.append(summary, BenderStages.editor(model, step, {notesOnly: true, onChange: () => {
      note.textContent = model.steps[step.id].notes || 'Aucune note pour cette étape.';
      $('boardStatus').textContent = `Note de l’étape ${step.number} enregistrée.`;
    }}));
    card.append(top, title, domains, progress, note, selectLabel, details); return card;
  }
  function render() {
    $('board').replaceChildren(...Object.entries(BenderStages.labels).map(([status, text]) => {
      const column = document.createElement('section'); column.className = `kanban-column column-${status}`;
      column.setAttribute('aria-label', text);
      const steps = model.plan.steps.filter(step => model.steps[step.id].status === status);
      const heading = document.createElement('h2'); heading.className = 'column-heading';
      const label = document.createElement('span'); label.textContent = text;
      const count = document.createElement('span'); count.className = 'column-count'; count.textContent = steps.length; heading.append(label, count);
      column.append(heading, ...steps.map(card));
      if (!steps.length) { const empty = document.createElement('p'); empty.className = 'column-empty'; empty.textContent = 'Dépose une étape ici'; column.append(empty); }
      column.addEventListener('dragover', event => { if (dragged) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; column.classList.add('drop-ready'); } });
      column.addEventListener('dragleave', event => { if (!column.contains(event.relatedTarget)) column.classList.remove('drop-ready'); });
      column.addEventListener('drop', event => {
        event.preventDefault(); column.classList.remove('drop-ready');
        const id = event.dataTransfer.getData('text/plain');
        const step = model.plan.steps.find(item => item.id === id);
        if (step && dragged === id) move(step, status);
      });
      return column;
    }));
    $('boardCount').textContent = `${model.plan.steps.filter(s => model.steps[s.id].status === 'validated').length} / ${model.plan.steps.length} étapes validées`;
  }
  async function load() {
    $('boardRetry').hidden = true; $('boardError').hidden = true;
    try {
      const response = await fetch('/api/roadmap', {cache: 'no-store'});
      if (!response.ok) throw new Error('Chargement impossible');
      model = await response.json(); render(); $('boardStatus').textContent = '✓ Tableau chargé depuis Bender.';
    } catch (_) { error('Impossible de charger le tableau. Vérifie la connexion à Bender.'); $('boardRetry').hidden = false; $('boardStatus').textContent = 'Connexion indisponible.'; }
  }
  $('boardRetry').addEventListener('click', load); load();
})();
