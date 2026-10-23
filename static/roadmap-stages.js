'use strict';
window.BenderStages = (() => {
  const labels = {todo: 'À faire', in_progress: 'En progrès', testing: 'À tester', validated: 'Validé'};
  const drafts = new Map();
  window.addEventListener('beforeunload', event => {
    if (drafts.size) { event.preventDefault(); event.returnValue = ''; }
  });
  async function save(model, id, changes) {
    const response = await fetch(`/api/roadmap/steps/${id}`, {
      method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(changes)
    });
    if (!response.ok) throw new Error('Enregistrement impossible. Vérifie la connexion à Bender puis réessaie.');
    const result = await response.json();
    // Only merge the requested fields: a parallel notes/status save must not revert the other field.
    Object.keys(changes).forEach(key => { model.steps[id][key] = result[key]; });
    model.steps[id].updated_at = result.updated_at;
    return result;
  }
  function statusSelect(model, step, onChange, report) {
    const select = document.createElement('select'); select.className = 'stage-status';
    select.setAttribute('aria-label', `Statut de l’étape ${step.number} : ${step.title}`);
    Object.entries(labels).forEach(([value, text]) => {
      const option = document.createElement('option'); option.value = value; option.textContent = text; select.append(option);
    });
    select.value = model.steps[step.id].status;
    select.addEventListener('change', async () => {
      const previous = model.steps[step.id].status, wanted = select.value;
      select.disabled = true; report('Enregistrement du statut…');
      try { await save(model, step.id, {status: wanted}); report('Statut enregistré.'); onChange(); }
      catch (error) { select.value = previous; report(error.message, true); }
      finally { select.disabled = false; }
    });
    return select;
  }
  function editor(model, step, {onChange = () => {}, notesOnly = false} = {}) {
    const panel = document.createElement('section'); panel.className = 'stage-editor';
    const heading = document.createElement('h3'); heading.textContent = 'Notes d’avancement';
    const help = document.createElement('p'); help.className = 'editor-help';
    help.textContent = 'Ce qui est fait, ce qui attend, et pourquoi. Le statut reste indépendant des cases à cocher.';
    const result = document.createElement('p'); result.className = 'editor-result'; result.setAttribute('role', 'status');
    const report = (message, failed = false) => { result.textContent = message; result.classList.toggle('failed', failed); };
    if (!notesOnly) {
      const status = document.createElement('label'); status.className = 'editor-status';
      const caption = document.createElement('span'); caption.textContent = 'Statut de cette étape';
      status.append(caption, statusSelect(model, step, onChange, report)); panel.append(status);
    }
    const textarea = document.createElement('textarea'); textarea.rows = 5; textarea.maxLength = 8000;
    textarea.setAttribute('aria-label', `Notes d’avancement de l’étape ${step.number} : ${step.title}`);
    textarea.placeholder = 'Ex. : tête validée en CAO. En attente des composants pour vérifier les dimensions et le montage réel.';
    textarea.value = drafts.get(step.id) ?? model.steps[step.id].notes;
    const saveButton = document.createElement('button'); saveButton.className = 'save-note'; saveButton.textContent = 'Enregistrer la note';
    saveButton.disabled = !drafts.has(step.id);
    if (drafts.has(step.id)) report('Brouillon non enregistré.');
    else if (model.steps[step.id].updated_at) report('Dernière modification : ' + new Date(model.steps[step.id].updated_at).toLocaleString('fr-FR'));
    textarea.addEventListener('input', () => {
      if (textarea.value === model.steps[step.id].notes) drafts.delete(step.id);
      else drafts.set(step.id, textarea.value);
      saveButton.disabled = !drafts.has(step.id);
      report(drafts.has(step.id) ? 'Brouillon non enregistré.' : 'Note inchangée.');
    });
    saveButton.addEventListener('click', async () => {
      const note = textarea.value;
      saveButton.disabled = true; textarea.disabled = true; report('Enregistrement de la note…');
      try {
        await save(model, step.id, {notes: note}); drafts.delete(step.id);
        report('✓ Note enregistrée sur Bender.'); onChange();
      } catch (error) { report(error.message, true); }
      finally { textarea.disabled = false; saveButton.disabled = !drafts.has(step.id); }
    });
    panel.append(heading, help, textarea, saveButton, result); return panel;
  }
  return {labels, save, editor, statusSelect};
})();
