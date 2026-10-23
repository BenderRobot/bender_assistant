# Conversation et micro manuel

Dans l’atelier, ouvre **Reconnaissance vocale** (`/#reconnaissance`). La capture utilise la LifeCam du Debian, même si la page est ouverte sur un autre PC.

1. Renseigne la clé de contrôle dans « Connexion au Dell ».
2. Clique sur **Démarrer le micro du Dell** et parle.
3. Clique sur **Pause et transcrire** quand tu as fini. La capture s’arrête et Vosk transcrit l’enregistrement localement.
4. Lis **Ce que Bender a compris**. Si « Répondre automatiquement après la transcription » est coché, ce texte est envoyé à GPT puis Bender répond avec la sortie vocale choisie. Son texte s’affiche aussi dans **Dernière réponse de Bender** et dans le journal commun à tous les onglets.

Pour corriger le texte avant l’envoi, décoche la réponse automatique avant de terminer l’écoute. Modifie la transcription puis clique sur **Envoyer cette transcription à Bender**. Aucun texte n’est envoyé à GPT si aucune parole n’est reconnue. **Annuler l’écoute** coupe la capture et abandonne le texte sans l’envoyer au cerveau.

Le micro reste en pause pendant la réponse. Une nouvelle prise nécessite un nouveau clic sur Démarrer. Le journal conserve les vingt derniers échanges de la page ouverte ; il est effacé lors d’un rechargement. Les échanges effectivement terminés avec GPT gardent leur historique habituel sur le serveur. Le texte de réponse reste visible si la voix ne fonctionne pas.

La durée choisie (15, 30 ou 60 secondes) borne automatiquement une prise si tu oublies de la terminer. La fermeture de la page tente aussi de l’annuler ; même si le réseau est coupé, la capture côté serveur est bornée. Le fichier sonore temporaire est supprimé après traitement ou annulation. La capture brute PCM est encapsulée dans un WAV par le serveur pour rester lisible après un arrêt manuel.

Le micro et la caméra partagent un verrou de capture. La lecture sur le Dell est arrêtée avant d’ouvrir le micro ; l’atelier empêche de relancer la voix pendant une prise. Les commandes du micro et la consultation des transcriptions nécessitent la clé de contrôle.

Les tests simulent ALSA/Vosk et vérifient le parcours web (démarrage, pause, annulation, correction, silence, erreurs et exclusion des captures parallèles). Un essai réel de la LifeCam et de la voix reste à effectuer sur le Debian après déploiement.
