# Conversation rapide et bulletins préparés

Le routage automatique utilise désormais les réponses enregistrées et le cache, puis ElevenLabs pour un texte inédit si la voix cloud est activée. Un échec cloud n'entraîne plus une génération Chatterbox lente : la voix système prend le relais si `system_fallback` est activé, avec un avertissement. Le mode **Local uniquement** reste un test explicite de Chatterbox.

Dans **Voix et enregistrements**, renseigne ton Voice ID, choisis le modèle et active ElevenLabs. Ces choix sont conservés dans `data/voice/live-settings.json`, hors Git. La connexion officielle crée la clé dans `.env.elevenlabs` ; la mise à jour transmet séparément ce fichier privé et le choix local de voix au Debian, puis redémarre le service. Une clé déjà définie dans le `.env` Debian reste compatible. Voir [ELEVENLABS_INTEGRATION.md](ELEVENLABS_INTEGRATION.md). Les plafonds existants de caractères restent appliqués. Aucun appel payant n'a été lancé pendant le développement.

## Bulletin de 6 h, lecture à la demande

1. Lance `MAJ_BENDER.ps1` sur Windows pour installer l'application et le service Debian.
2. Dans **Voix et enregistrements**, colle les URL RSS de ton choix (une par ligne, six maximum).
3. Choisis **06:00**, fuseau **Europe/Paris**, et une référence Chatterbox déjà activée, par exemple **Énergique**.
4. Coche la préparation quotidienne et enregistre.
5. **Préparer maintenant** permet un premier essai. Le worker prend la demande au prochain passage du minuteur, environ une minute plus tard.
6. L'atelier affiche **En attente**, **Préparation**, le nombre de passages terminés, puis **Prêt** ou une erreur.
7. À 8 h 30, 9 h ou plus tard, clique sur **Lire le bulletin prêt** ou demande **Lis-moi les infos** au cerveau / via le micro. L'audio et sa timeline de bouche sont rejoués sans nouvelle synthèse ni requête GPT.

Le bulletin lit les titres et courts résumés fournis par les flux, avec attribution. Il n'effectue pas une synthèse journalistique avec GPT. Les sources sont conservées. Les articles datés de plus de 24 heures sont exclus ; un article sans date est identifié dans l'atelier. Aucun flux n'est activé par défaut.

Le contrôle de l'horaire se fait chaque minute, en Europe/Paris, y compris après un redémarrage. Un seul bulletin est produit par jour. Si Bender était arrêté à 6 h, il démarre la préparation à son retour ; l'audio n'est donc pas garanti prêt immédiatement. La lecture automatique à 8 h 30 n'est pas activée : tu la demandes.

Le worker est un processus séparé, de priorité basse et avec deux threads de calcul. Il génère des passages courts pour conserver l'avancement. La génération utilise exclusivement Chatterbox : aucun repli facturé vers ElevenLabs. Un échec partiel n'est jamais annoncé comme prêt, et un bulletin d'hier n'est jamais servi comme celui d'aujourd'hui. Corriger puis relancer manuellement une préparation échouée. Les audios déjà en cache sont réutilisés.

Les réglages et l'état restent dans `data/voice/bulletins/`, hors Git. L'heure, les flux, la sélection de voix et les états sont conservés par les mises à jour. Le traitement D des essais de voix reste indépendant ; ce changement ne l'applique pas automatiquement aux synthèses.

## Diagnostic Debian

```bash
systemctl status bender-bulletins.timer --no-pager
systemctl status bender-bulletins.service --no-pager
journalctl -u bender-bulletins.service -n 40 --no-pager
```

La collecte RSS demande Internet ; la lecture d'un bulletin terminé fonctionne hors ligne. Les conversations nouvelles nécessitent l'API ElevenLabs. La rapidité de l'API dépend du modèle et du réseau ; le lecteur actuel attend l'audio complet, sans streaming audio.
