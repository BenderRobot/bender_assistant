# ElevenLabs dans Bender

La génération vocale utilise le SDK Python officiel et la méthode `convert_with_timestamps`. Le MP3 est converti pour le lecteur existant ; les horaires de caractères sont conservés dans les métadonnées de synchronisation. Ce ne sont pas des phonèmes reconnus. Le lecteur attend encore la génération complète : cette intégration n'ajoute pas de lecture en streaming.

## Connexion sur Windows

Depuis le dépôt, le CLI officiel permet de connecter le compte sans coller une clé dans le chat :

```powershell
cd "$env:USERPROFILE\Documents\bender_main\bender_assistant"
npx.cmd -y @elevenlabs/cli@latest onboard connect --env-path .env.elevenlabs
npx.cmd -y @elevenlabs/cli@latest onboard check --answered --env-path .env.elevenlabs
```

Le fichier `.env.elevenlabs` reste privé et ignoré par Git. Ne jamais afficher son contenu, le partager ou le joindre à une archive. Le serveur et la commande `python -m bender_voice` le chargent automatiquement, puis chargent `.env` pour les autres réglages. Une variable définie directement dans le processus reste prioritaire.

## Mise à jour du Debian

Lancer le script habituel :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\bender_main\MAJ_BENDER.ps1" -Message "Integration SDK ElevenLabs"
```

S'il existe, `.env.elevenlabs` est transmis séparément par SSH, dans un dossier distant privé, puis installé avec les droits `600`. Il ne passe ni dans le commit ni dans l'archive Git. Les services Debian chargent ce fichier après leur `.env` existant. Le choix local de voix dans `data/voice/live-settings.json`, s'il existe, est lui aussi transmis séparément et appliqué après validation. Son empreinte permet de ne l'appliquer à nouveau que si ce choix local change : les ajustements faits ensuite dans l'atelier Debian survivent aux mises à jour suivantes. Sans ces fichiers locaux, le script conserve la configuration distante.

## Choisir la voix

Dans l'atelier **Voix et enregistrements → Conversation rapide · ElevenLabs**, renseigner le Voice ID de la voix créée dans le compte, choisir le modèle, activer la voix puis enregistrer. Le Voice ID identifie une voix ; ce n'est pas une clé API. Le modèle Flash v2.5 est proposé pour les conversations ; le modèle reste au choix dans l'atelier.

La clé seule n'active pas les générations. Les réglages publics sont conservés dans `data/voice/live-settings.json`. Aucune clé n'est envoyée au navigateur.

## Routage et budget

- Les enregistrements et le cache compatibles sont prioritaires.
- Les réponses inédites en mode automatique utilisent ElevenLabs quand il est activé.
- Les bulletins préparés utilisent Chatterbox en arrière-plan.
- Un échec cloud ne déclenche pas une génération Chatterbox lente ; la voix système sert de secours si elle est autorisée.
- Les plafonds de caractères existants s'appliquent avant chaque génération. Le SDK ne réessaie pas une requête échouée, même en cas de limitation ou d'erreur serveur.

Les tests automatisés utilisent des réponses simulées, sans dépenser de crédits. Un essai vocal réel demande une autorisation distincte et consomme les crédits du compte.

Références : [SDK officiel](https://github.com/elevenlabs/elevenlabs-python), [audio avec horaires](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps).
