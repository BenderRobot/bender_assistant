# Étape 03 — enrichir la voix et la personnalité

## Ton parcours habituel

1. Sur ton PC Windows, dépose tes nouveaux sons et vidéos dans `C:\Users\benjamin.laurens\Documents\bender_main\02_VOIX_ET_ANIMATIONS\a_importer`.
2. Lance le script de mise à jour habituel :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\bender_main\MAJ_BENDER.ps1" -Message "Nouveaux samples Bender"
```

3. Ouvre `http://192.168.1.41:8000/#samples`, renseigne la clé de contrôle du Dell puis clique sur **Charger / actualiser mes samples**.
4. Les analyses démarrent en arrière-plan après le déploiement et au démarrage du Debian si l’option automatique est activée. La liste distingue **En attente**, **Analyse en cours**, **À vérifier**, **Sélections validées** et **À reprendre**.
5. Choisis un sample, vérifie la transcription, regarde les images et écoute un passage. Les propositions de GPT restent des suggestions. Choisis le début et la fin du passage puis valide son usage.

Le dossier de dépôt reste sur ton PC. Deux fichiers identiques, même renommés, ne sont transférés qu’une fois. Un fichier modifié est un nouveau sample. Une mise à jour suivante conserve les classements, corrections et validations du Debian. Les sons et vidéos voyagent séparément du code, hors GitHub.

## Ce qui est automatique

L’import calcule l’empreinte SHA-256 de chaque fichier et compare les contenus avec le catalogue du Debian. Il transfère uniquement les nouveautés, vérifie l’intégrité à l’arrivée, puis les ajoute à la file d’analyse.

FFmpeg prépare une piste WAV mono, mesure son niveau et son écrêtage, et prélève au plus huit images pour une vidéo. Vosk produit une transcription française estimée et des horaires de mots. GPT reçoit le texte, ces mesures et les images horodatées pour proposer :

- Un titre et un résumé pour retrouver le sample.
- Des thèmes, mots déclencheurs et une humeur supposée.
- Des passages intéressants pour une réplique ou une référence vocale candidate.
- Des descriptions des bouches et des yeux visibles, avec une proposition de pose existante lorsqu’elle paraît pertinente.

Cette analyse est séparée des conversations courantes de Bender et ne modifie pas leur historique. Les noms proposés sont des titres dans le catalogue ; les fichiers source restent identifiés par leur empreinte.

## Trois usages après validation

**Réplique contextuelle.** Choisis un passage de 30 secondes maximum, vérifie son texte exact, ses mots déclencheurs et son humeur, puis confirme que seul Bender parle. La réplique rejoint la bibliothèque de voix existante et apparaît dans **Voix et enregistrements** après actualisation. Son utilisation contextuelle suit les options existantes : autorisation des répliques, probabilité et délais entre lectures. La synchronisation produite pour un nouvel extrait reste acoustique ; les anciens calages visuels sont conservés.

**Référence vocale candidate.** Choisis 3 à 30 secondes de voix propre. Le WAV découpé est exporté dans `data/voice/references/` et son chemin apparaît dans le catalogue. Il peut ensuite être sélectionné dans `reference_by_mood` de `voice.json` pour un essai Chatterbox. L’import n’entraîne pas un modèle et ne remplace pas la référence active. Des voix tierces ou de la musique gênante rendent la sélection impropre à cet usage ; la vérification se fait à l’écoute.

**Repère bouche / yeux.** Choisis un intervalle contenant une image prélevée et donne-lui un nom. Le catalogue conserve ce repère et les descriptions proposées pour affiner ensuite les poses et la synchronisation. Les poses validées de l’éditeur ne sont pas modifiées automatiquement.

## Limites utiles à connaître

La connexion actuelle Sign in with ChatGPT accepte le texte et les images, mais pas l’entrée audio/vidéo ni l’API de transcription. Le son reste traité localement ; GPT **n’écoute pas le timbre**, ne sépare pas les locuteurs et ne juge pas directement l’émotion de la voix. L’humeur est suggérée à partir du texte et des images. La transcription Vosk peut être corrigée dans l’atelier avant une nouvelle analyse. [Limites officielles de cette connexion](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).

Les images sont échantillonnées : cette étape ne constitue pas un calage labial image par image ou une reconnaissance exacte des phonèmes. Une sélection de référence vocale n’est pas un apprentissage cumulatif de Chatterbox. Le classement aide à préparer des références propres et des répliques utilisables.

Les traitements consomment le quota ChatGPT du compte autorisé. Une erreur GPT arrête la file pour éviter d’enchaîner des échecs. Le fichier concerné passe à **À reprendre** ; les autres restent en attente. Clique sur **Reprendre les analyses en attente** pour continuer, ou relance explicitement un fichier après correction. Décoche l’option automatique pour arrêter après le fichier en cours. Aucun téléchargement de modèle n’est déclenché par l’import.

## Formats et stockage

- Formats : WAV, MP3, MP4, M4A, FLAC, OGG, WEBM, MOV et MKV.
- Extraits : 0,1 à 180 secondes, 100 Mo maximum chacun. Un transfert accepte au plus 100 fichiers nouveaux et 500 Mo.
- Choisis de préférence des extraits courts, avec une voix française audible et la bouche visible pour les vidéos.
- Données : `<data_dir>/media/catalog.sqlite3`, `originals/`, `derived/` et `approved/`.
- Répliques validées : bibliothèque existante `<data_dir>/library/`.
- Candidats pour la voix : `<data_dir>/references/`.
- Les données restent exclues de Git ; les transcriptions, les images et les pistes audio de l’atelier nécessitent la clé de contrôle. Les répliques publiées dans la bibliothèque suivent les accès existants du lecteur Bender.

Sur Debian, les journaux de traitement sont disponibles avec :

```bash
sudo journalctl -u bender-media.service -n 50 --no-pager
```

Le worker utilise une seule file et un verrou entre processus. Il reprend les analyses interrompues après redémarrage. Les archives sont contrôlées avant import (formats, chemins, taille, empreintes et absence de liens). Les tests couvrent l’import, les erreurs et l’intégration avec des réponses GPT simulées et des médias audio/vidéo synthétiques. Le premier classement réel de tes extraits reste à vérifier après déploiement.
