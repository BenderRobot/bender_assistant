# Ma voix ElevenLabs dans Bender

Tu as déjà créé ta voix. Le prochain résultat à obtenir est un **WAV propre**, puis une première phrase nouvelle générée avec cette référence par Chatterbox.

La voix enregistrée dans ton compte ElevenLabs et le modèle local Chatterbox sont deux systèmes distincts. Notre passerelle transmet un extrait sonore : Chatterbox s’en sert comme référence de voix. Le résultat doit être comparé à l’écoute ; ce n’est ni un transfert du modèle ElevenLabs ni un entraînement cumulatif. Le Voice ID sert aux appels cloud ElevenLabs, pas au moteur local.

## 1. Télécharger ton premier extrait

Dans ElevenLabs, ouvre **Text to Speech**, sélectionne ta voix, puis génère un texte français naturel. Pour ce premier essai, vise environ **10 à 20 secondes**, avec un ton neutre, une seule voix et aucun effet ajouté de bruit ou de réverbération.

Texte d’essai possible :

> Salut, c’est Bender. Les lumières sont allumées et les circuits sont prêts. Je peux te donner la météo, lire les nouvelles ou discuter avec toi. Alors, qu’est-ce qu’on fait aujourd’hui ?

Écoute la génération. Dans le panneau **History / Historique**, utilise l’icône de téléchargement et choisis **WAV**. Sur un écran étroit, l’historique peut être accessible par une icône au-dessus du bouton de génération. [Instructions officielles de téléchargement](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-do-i-download-wav-m4a-and-flac-files).

Nom conseillé : `Bender_ElevenLabs_neutre.wav`. Conserve aussi le texte et les réglages utilisés. La génération chez ElevenLabs utilise les crédits de ton offre ; les futures phrases produites localement par Chatterbox n’appellent pas cette API.

## 2. Transférer l’extrait vers le Dell

Place le WAV dans :

```text
C:\Users\benjamin.laurens\Documents\bender_main\02_VOIX_ET_ANIMATIONS\a_importer
```

Puis lance ta mise à jour habituelle depuis PowerShell :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\bender_main\MAJ_BENDER.ps1" -Message "Reference voix ElevenLabs"
```

Ouvre [Samples et personnalité sur Bender](http://192.168.1.41:8000/#samples), renseigne la clé de contrôle puis charge la bibliothèque. Après analyse, sélectionne ton WAV, corrige la transcription si nécessaire et choisis **Référence vocale candidate**, humeur **Neutre**. Sélectionne un passage continu de 3 à 30 secondes, écoute-le et valide le passage après la vérification demandée.

Le WAV est converti en mono 24 kHz dans `data/voice/references/`. Les fichiers audio et les paramètres personnels restent hors de GitHub.

## 3. Installer le moteur local, si nécessaire

Sur Debian en SSH, exécute ces commandes une par une :

```bash
cd ~/applications/bender_assistant
.venv/bin/python -m pip install -r requirements-chatterbox.txt
.venv/bin/python -m bender_voice --config voice.json download-models chatterbox
sudo systemctl restart bender.service
```

Cette préparation nécessite Internet et peut télécharger plusieurs Go. Le projet utilise **Chatterbox Multilingual**, avec `language_id=fr`, chargé depuis les fichiers locaux. Le Dell utilise le processeur : la latence reste à mesurer sur ce matériel. La présence du WAV seule ne suffit pas si les dépendances ou modèles manquent. [Documentation Chatterbox](https://github.com/resemble-ai/chatterbox).

## 4. Activer ta référence et essayer une phrase nouvelle

Dans la fiche du sample, sous **Passages validés**, clique sur **Utiliser cette voix avec Chatterbox · neutral**. Le bouton devient **Référence Chatterbox active**.

Dans **Voix et enregistrements**, choisis le routage **Local**, la référence **Neutre** et une phrase différente du WAV, par exemple : « La température du salon est de vingt-deux degrés. Je peux allumer la lumière si tu veux. » Fais parler Bender, puis contrôle le champ **Source** : il doit indiquer **chatterbox**. Si la source est **system**, la voix générique a pris le relais ; lire l’avertissement et corriger l’installation avant de juger la ressemblance.

Le choix est conservé dans `data/voice/reference-settings.json`, distinct de `voice.json`. Il est appliqué immédiatement dans le service et rechargé après redémarrage. Les mises à jour conservent ce fichier. La référence modifie l’identité du cache Chatterbox : une nouvelle génération locale peut donc être comparée aux anciens sons. En mode automatique, un enregistrement déjà disponible peut être rejoué avant toute synthèse ; commence le test en **Local** avec un texte inédit.

Les références restent des candidats tant que tu n’as pas cliqué sur le bouton d’activation. L’activation n’entraîne aucun modèle et ne génère pas de son facturé.

## 5. Ajouter d’autres tons plus tard

Quand la voix neutre convient, tu peux générer un autre WAV avec **la même voix** pour un ton sarcastique, énergique, agacé ou triste. Refaire import, validation puis activation avec l’humeur correspondante. Une humeur sans référence dédiée utilise la référence neutre. Compare plusieurs phrases et garde seulement les extraits qui donnent un résultat utile.

## 6. Garder ElevenLabs pour le mode cloud

Tu n’as pas besoin de clé API ElevenLabs pour transmettre un WAV téléchargé à Chatterbox. Pour utiliser ensuite ElevenLabs directement depuis Bender :

1. Dans **My Voices**, menu **… / More actions → Copy voice ID**, récupère l’identifiant de ta voix. [Aide officielle](https://elevenlabs.io/docs/help-center/technical/how-do-i-find-the-voice-id-of-my-voices-via-the-website-and-api).
2. Connecte le compte avec le CLI officiel et garde la clé dans `.env.elevenlabs`, hors Git. La mise à jour la transmet au Debian par SSH. La variable `ELEVENLABS_API_KEY` d'un `.env` Debian existant reste aussi compatible. Voir [ELEVENLABS_INTEGRATION.md](ELEVENLABS_INTEGRATION.md).
3. Dans l'atelier **Voix et enregistrements**, renseigne le Voice ID, choisis le modèle et active ElevenLabs. Fixe tes plafonds de caractères dans `voice.json`. Flash v2.5 est proposé pour la conversation rapide.
4. Redémarre `bender.service`. Teste une phrase inédite en mode **Cloud** et vérifie **Source : elevenlabs** ; un avertissement peut signaler un repli local si l’appel échoue.

Le routage automatique utilise les enregistrements et le cache, puis ElevenLabs pour les conversations nouvelles si tu l'actives. Chatterbox sert aux préparations en arrière-plan ; une panne cloud ne déclenche plus une génération locale lente. Voir [VOIX_CONVERSATION_ET_BULLETINS.md](VOIX_CONVERSATION_ET_BULLETINS.md) pour le bulletin RSS de 6 h et les réglages dans l'atelier. Les plafonds Bender sont des limites de caractères applicatives, pas le solde exact des crédits du compte ElevenLabs.

Retrouve toutes ces actions avec cases à cocher dans [l’étape 03 de la roadmap](http://192.168.1.41:8000/roadmap#step-3). La création de ta voix est déjà cochée ; import, installation, activation et tests restent à valider sur ton Dell.
