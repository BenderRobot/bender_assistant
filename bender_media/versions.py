"""The owner's approved selections, grouped by mood without generating speech."""
from pathlib import Path

from bender_voice.config import inside

MOODS = (('neutral', 'Neutre'), ('sarcastic', 'Sarcastique'), ('angry', 'Agacé'),
         ('excited', 'Énergique'), ('sad', 'Triste'))


def audio_path(selection, voice, library=None):
    """Resolve only published library clips or approved reference files."""
    if selection.get('use') == 'quote':
        entries = voice.store.library() if library is None else library
        entry = next((item for item in entries if item['id'] == selection.get('library_id')), None)
        if not entry:
            raise ValueError('Réplique absente de la bibliothèque.')
        return inside(voice.store.root / 'library', entry['audio']), bool(entry.get('enabled', True))
    if selection.get('use') == 'voice_reference' and selection.get('reference_file'):
        path = Path(selection['reference_file'])
        if len(path.parts) != 2 or path.parts[0] != 'references' or path.suffix.lower() != '.wav':
            raise ValueError('Référence vocale invalide.')
        return inside(voice.store.root, str(path)), True
    raise ValueError('Ce passage ne contient pas de sélection audio publiée.')


def overview(catalog, voice, samples=None):
    samples = catalog.list() if samples is None else samples
    warnings = []
    try:
        library = voice.store.library()
    except (OSError, ValueError):
        library = []
        warnings.append('Catalogue des répliques illisible ; actualise après la publication du passage.')
    references = voice.config.get('reference_by_mood', {})
    selections = []
    moods = {key: dict(id=key, label=label, quotes=0, references=0, active_references=0, expressions=0)
             for key, label in MOODS}
    for sample in samples:
        for entry in sample['approved']:
            use, mood = entry.get('use'), entry.get('mood', 'neutral')
            if mood not in moods or use not in ('quote', 'voice_reference', 'expression'):
                continue
            identifier, selection_id = sample['id'], entry['selection_id']
            item = dict(id=f'{identifier}:{selection_id}', sample_id=identifier, selection_id=selection_id,
                        title=entry.get('title') or sample['original_name'], source_name=sample['original_name'],
                        mood=mood, use=use, text=entry.get('text', ''), triggers=entry.get('triggers', []),
                        start=entry['start'], end=entry['end'], available=False, ready_for_response=False,
                        active=False, audio_url=None, frame_url=None, library_id=None, reason='')
            if use == 'expression':
                frame = next((frame for frame in sample['media'].get('frames', [])
                              if entry['start'] <= frame['time'] <= entry['end']
                              and (catalog.root / 'derived' / identifier / f"frame-{frame['index']}.jpg").is_file()), None)
                item['available'] = frame is not None
                if frame:
                    item['frame_url'] = f"/api/media/{identifier}/frames/{frame['index']}"
                    moods[mood]['expressions'] += 1
                item['reason'] = ('Repère à associer aux poses ; ne pilote pas encore une réponse.' if frame
                                  else 'Image du repère introuvable.')
            else:
                try:
                    path, enabled = audio_path(entry, voice, library)
                    item['available'] = path.is_file()
                    if not item['available']:
                        item['reason'] = 'Fichier audio introuvable.'
                    elif use == 'quote':
                        item['ready_for_response'] = enabled
                        item['library_id'] = entry.get('library_id')
                        item['reason'] = ('Réplique enregistrée ; son emploi automatique dépend des mots déclencheurs '
                                          'et des réglages de réponses.' if enabled else 'Réplique désactivée dans la bibliothèque.')
                        moods[mood]['quotes'] += int(enabled)
                    else:
                        item['active'] = references.get(mood) == entry.get('reference_file')
                        item['reason'] = ('Référence Chatterbox active pour cette humeur.' if item['active']
                                          else 'Référence disponible à tester et à activer avec Chatterbox.')
                        moods[mood]['references'] += 1
                        moods[mood]['active_references'] += int(item['active'])
                    if item['available']:
                        item['audio_url'] = f'/api/media/{identifier}/selections/{selection_id}/audio'
                except (ValueError, KeyError, OSError):
                    item['reason'] = 'Sélection publiée introuvable ou chemin invalide.'
            selections.append(item)
    return dict(moods=list(moods.values()), selections=selections,
                total=len(selections), ready_quotes=sum(item['ready_for_response'] for item in selections), warnings=warnings)
