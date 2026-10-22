# Vérifications de la livraison

- 22 tests automatisés passent : cache, changement d'identité vocale, réservations quotidiennes/mensuelles, redémarrage, concurrence, repli, absence de double appel, imports, réponses exactes, répliques contextuelles, API, WebSocket et contrats des adaptateurs.
- Syntaxe Python compilée ; JavaScript vérifié avec Node ; script Debian vérifié avec `bash -n`.
- Serveur FastAPI lancé localement ; lecture dans le navigateur d'un WAV fourni par l'utilisateur depuis une bibliothèque temporaire, avec animation de bouche et yeux indépendants. Aucun média de cet essai n'est dans l'archive.
- Allosaurus réellement exécuté dans le nouveau module : 24 sons estimés sur le WAV converti, timeline valide. L'animation reste expérimentale.
- Archive contrôlée : absence de `.env`, bases mémoire, dossier `.git`, médias, modèles et caches ; fichier d'exemple avec clés vides ; script shell en LF.

Environnement de ces vérifications : Windows, tests du service sous Python 3.14, reconnaissance phonétique sous Python 3.12. Le fonctionnement du script d'installation sur Debian et la sortie son du Dell restent à vérifier sur place.

Pas de synthèse payante ElevenLabs, pas de requête Gemini, pas de commande domotique exécutée. Les adaptateurs vocaux sont testés avec des doubles contrôlés ; Chatterbox nécessite encore son installation, ses modèles et une référence vocale pour un essai réel. Le pilote matériel HUB75/MatrixPortal S3 n'est pas inclus.

V2 : huit tests ajoutés pour les périphériques (captures, clé, rétention des photos, arrêt et diffusion du lecteur ALSA). Vosk 0.3.45 et son petit modèle français officiel ont été réellement téléchargés et exécutés sur un WAV fourni. Une transcription non vide mais imparfaite a été produite ; cela valide le chargement et le traitement, pas une précision garantie. Les opérations matérielles sont simulées sur Windows et doivent être confirmées sur le Dell.
