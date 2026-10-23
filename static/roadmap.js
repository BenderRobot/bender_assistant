'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let model, selected = 0;
  const saving = new Set();
  const controls = new Map();
  function count(step) {
    return step.tasks.filter(task => model.progress[task.id].done).length;
  }
  function fail(message) { $('error').textContent = message; $('error').hidden = false; }
  function stats() {
    const steps = model.plan.steps;
    const total = steps.reduce((n, step) => n + step.tasks.length, 0);
    const done = steps.reduce((n, step) => n + count(step), 0);
    const percent = Math.round(100 * done / total);
    $('percent').textContent = `${percent} %`;
    $('ring').style.setProperty('--progress', `${percent}%`);
    $('totalLabel').textContent = `${done} actions accomplies sur ${total}`;
    $('phaseLabel').textContent = `${steps.filter(s => model.steps[s.id].status === 'validated').length} étapes validées sur ${steps.length}`;
    steps.forEach((step, index) => {
      const button = $(`nav-${index}`);
      button.classList.toggle('finished', model.steps[step.id].status === 'validated');
      button.querySelector('.nav-fraction').textContent = `${count(step)}/${step.tasks.length}`;
      if (index === selected) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    const step = steps[selected], doneHere = count(step);
    $('stepFill').style.width = `${100 * doneHere / step.tasks.length}%`;
    $('stepCount').textContent = `${doneHere} / ${step.tasks.length}`;
    $('stepBadge').textContent = BenderStages.labels[model.steps[step.id].status];
    $('nextTask').textContent = step.tasks.find(t => !model.progress[t.id].done)?.title || 'Toutes les actions sont cochées. Vérifie le critère de validation de l’étape.';
    filterTasks();
  }
  function filterTasks() {
    if (!model) return;
    let visible = 0;
    model.plan.steps[selected].tasks.forEach(task => {
      const row = controls.get(task.id).row;
      row.classList.toggle('done', model.progress[task.id].done);
      row.hidden = $('remainingOnly').checked && model.progress[task.id].done;
      if (!row.hidden) visible++;
    });
    $('empty').hidden = visible > 0;
  }
  async function saveTask(task, checkbox) {
    const previous = model.progress[task.id];
    const wanted = checkbox.checked;
    saving.add(task.id); checkbox.disabled = true;
    $('error').hidden = true;
    $('saveStatus').textContent = 'Enregistrement…';
    try {
      const response = await fetch(`/api/roadmap/tasks/${task.id}`, {
        method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({done: wanted})
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      model.progress[task.id] = await response.json();
      const current = controls.get(task.id);
      if (current) current.checkbox.checked = wanted;
      stats();
    } catch (_) {
      checkbox.checked = previous.done;
      const current = controls.get(task.id);
      if (current) current.checkbox.checked = previous.done;
      fail('Cette modification n’a pas été sauvegardée. Vérifie la connexion à Bender puis réessaie.');
    } finally {
      saving.delete(task.id); checkbox.disabled = false;
      const current = controls.get(task.id);
      if (current) current.checkbox.disabled = false;
      $('saveStatus').textContent = saving.size ? 'Enregistrement…' : $('error').hidden ? '✓ Progression sauvegardée sur Bender' : 'Modification non enregistrée';
    }
  }
  function renderStep(index) {
    selected = index; controls.clear();
    const step = model.plan.steps[index];
    $('stepNumber').textContent = `ÉTAPE ${String(step.number).padStart(2, '0')} / 08`;
    $('stepTitle').textContent = step.title;
    $('stepDescription').textContent = step.description;
    $('stepGate').textContent = step.gate;
    $('stageEditor').replaceChildren(BenderStages.editor(model, step, {onChange: stats}));
    $('tags').replaceChildren(...step.domains.map(domain => {
      const tag = document.createElement('span'); tag.className = 'tag'; tag.textContent = domain; return tag;
    }));
    $('tasks').replaceChildren(...step.tasks.map(task => {
      const row = document.createElement('div'); row.className = 'task';
      const label = document.createElement('label'); label.className = 'task-check';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
      checkbox.checked = model.progress[task.id].done; checkbox.disabled = saving.has(task.id);
      checkbox.addEventListener('change', () => saveTask(task, checkbox));
      const copy = document.createElement('span');
      const title = document.createElement('strong'); title.textContent = task.title;
      const detail = document.createElement('small'); detail.textContent = task.detail;
      copy.append(title, detail); label.append(checkbox, copy); row.append(label);
      if (task.guide) {
        const dropdown = document.createElement('details'); dropdown.className = 'task-guide';
        const summary = document.createElement('summary'); summary.textContent = 'Comment accomplir cette tâche';
        const content = document.createElement('div'); content.className = 'guide-content';
        const where = document.createElement('p');
        const whereLabel = document.createElement('strong'); whereLabel.textContent = 'Où agir';
        const whereText = document.createElement('span'); whereText.textContent = task.guide.where;
        where.append(whereLabel, whereText);
        const instructions = document.createElement('ol');
        task.guide.steps.forEach(instruction => {
          const item = document.createElement('li'); item.textContent = instruction; instructions.append(item);
        });
        const expected = document.createElement('div'); expected.className = 'guide-expected';
        const expectedLabel = document.createElement('strong'); expectedLabel.textContent = 'Tu peux cocher quand…';
        const expectedText = document.createElement('p'); expectedText.textContent = task.guide.expected;
        expected.append(expectedLabel, expectedText);
        content.append(where, instructions, expected);
        if (task.guide.commands?.length) {
          const commandsLabel = document.createElement('p'); commandsLabel.className = 'commands-label';
          commandsLabel.textContent = 'Commandes à lancer manuellement — ' + task.guide.command_context;
          content.append(commandsLabel);
          task.guide.commands.forEach(command => {
            const pre = document.createElement('pre'); const code = document.createElement('code'); code.textContent = command;
            pre.append(code); content.append(pre);
          });
        }
        const record = document.createElement('p'); record.className = 'guide-record';
        record.textContent = 'À noter : ' + task.guide.record;
        content.append(record); dropdown.append(summary, content); row.append(dropdown);
      }
      controls.set(task.id, {row, checkbox}); return row;
    }));
    $('previous').disabled = index === 0;
    $('next').disabled = index === model.plan.steps.length - 1;
    stats();
    history.replaceState(null, '', `#${step.id}`);
  }
  async function load() {
    $('retry').disabled = true; $('error').hidden = true; $('loadFailure').hidden = true;
    try {
      const response = await fetch('/api/roadmap', {cache: 'no-store'});
      if (!response.ok) throw new Error('Chargement impossible');
      model = await response.json();
      $('steps').replaceChildren(...model.plan.steps.map((step, i) => {
        const button = document.createElement('button'); button.id = `nav-${i}`; button.className = 'step-link';
        const number = document.createElement('span'); number.className = 'step-index'; number.textContent = String(i).padStart(2, '0');
        const copy = document.createElement('span');
        const title = document.createElement('strong'); title.textContent = step.title;
        const domain = document.createElement('small'); domain.textContent = step.domains.join(' · ');
        const fraction = document.createElement('span'); fraction.className = 'nav-fraction';
        copy.append(title, domain); button.append(number, copy, fraction);
        button.addEventListener('click', () => renderStep(i)); return button;
      }));
      const requested = model.plan.steps.findIndex(s => `#${s.id}` === location.hash);
      const firstIncomplete = model.plan.steps.findIndex(s => count(s) < s.tasks.length);
      renderStep(requested >= 0 ? requested : Math.max(0, firstIncomplete));
      $('workspace').hidden = false;
      $('saveStatus').textContent = '✓ Progression sauvegardée sur Bender';
    } catch (_) {
      fail('Impossible de charger la roadmap. Vérifie que Bender est accessible puis réessaie.');
      $('saveStatus').textContent = 'Connexion indisponible'; $('loadFailure').hidden = false;
    } finally { $('retry').disabled = false; }
  }
  $('remainingOnly').addEventListener('change', filterTasks);
  $('previous').addEventListener('click', () => renderStep(Math.max(0, selected - 1)));
  $('next').addEventListener('click', () => renderStep(Math.min(model.plan.steps.length - 1, selected + 1)));
  $('retry').addEventListener('click', load);
  $('export').addEventListener('click', () => {
    const data = {exported_at: new Date().toISOString(), ...model};
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'bender-roadmap-progression.json';
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  load();
})();
