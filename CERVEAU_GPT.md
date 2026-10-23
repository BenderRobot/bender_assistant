# Cerveau GPT de Bender

La chaîne est : **micro du Dell → Vosk local → texte → GPT via le compte ChatGPT → voix hybride → bouche synchronisée**. La LifeCam peut aussi fournir une photo à GPT lorsque tu demandes une analyse. La voix et les enregistrements restent indépendants du cerveau.

Cette intégration suit le parcours officiel [Sign in with ChatGPT pour applications personnelles et open source](https://developers.openai.com/siwc/token-sharing-open-source). Elle utilise les limites du forfait autorisé, selon l’éligibilité du compte. Elle nécessite Internet. Elle ne convertit pas l’abonnement en crédits d’API et n’utilise aucune clé d’API payante en secours.

## 1. Déployer depuis ton PC Windows

Dans PowerShell :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\bender_main\MAJ_BENDER.ps1" -Message "Cerveau GPT avec compte ChatGPT"
```

Le déploiement installe PyJWT et sa dépendance cryptographique dans le venv Debian. Les clés Gemini précédentes ne sont plus utilisées par le cerveau. Aucun changement de clé n’est nécessaire dans `.env`.

## 2. Continuer avec ChatGPT

Après la mise à jour, depuis Windows :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\bender_main\CONNECTER_CHATGPT.ps1"
```

Le script maintient un tunnel SSH local vers le Debian et affiche une URL officielle `https://auth.openai.com/...`. Ouvre-la dans ton navigateur, connecte-toi à ton compte et autorise **Bender Jarvis**. Ne ferme pas le terminal avant la confirmation. La redirection vers `http://127.0.0.1:1455/auth/callback` est normale : le tunnel ramène cette réponse au Debian. Si ce port est déjà occupé, ajoute `-Port 1456` au script.

Le script ne demande aucun mot de passe ChatGPT dans le terminal. Il réutilise la clé SSH existante ; une clé avec phrase secrète doit être chargée dans ton ssh-agent comme pour les mises à jour.

Alternative directement dans une session graphique du Debian :

```bash
cd ~/applications/bender_assistant
.venv/bin/python -m bender_brain login
```

Pour une session SSH seule, utiliser le script Windows : le port de retour doit être transféré, il ne suffit pas d’ouvrir le lien sans tunnel.

## 3. Tester le cerveau

Ouvre `http://192.168.1.41:8000/#cerveau`. Actualise le statut, puis renseigne la clé de contrôle dans « Connexion au Dell ». Le bouton « Afficher mes comptes » affiche les comptes enregistrés. Charge les modèles, choisis celui que ton compte propose et clique sur « Utiliser ce modèle ». Si tu n’en choisis pas, le premier modèle visible du catalogue sera utilisé lors du premier message.

Commence par « Tester GPT · réponse texte ». Puis utilise « Voix et enregistrements → Demander au cerveau GPT » ou « Reconnaissance vocale → Parler à Bender ». La transcription Vosk reste locale ; le texte de la question et les derniers échanges du compte actif sont envoyés à OpenAI. Une photo n’est envoyée qu’avec le bouton d’analyse. Un modèle peut refuser les images : dans ce cas, choisis un modèle compatible dans le catalogue.

Les réponses ne sont mémorisées ni prononcées avant la confirmation de fin du flux. Une connexion coupée ou un quota atteint produit une erreur explicite, sans lire de réponse partielle.

## Comptes et déconnexion

Pour ajouter un autre compte ou espace ChatGPT, relance le script Windows avec `-NewAccount`. Chaque inscription possède son identifiant, son modèle et son historique séparés, même si l’adresse e-mail est identique. L’onglet permet de sélectionner un compte déjà enregistré. Pour le réautoriser, sélectionne-le avant de relancer le script sans `-NewAccount`.

« Déconnecter le compte actif » tente la révocation distante, efface les jetons locaux et conserve l’identité de l’inscription pour une future connexion. Si Internet est indisponible, le banc signale que la révocation n’est pas confirmée ; vérifier alors les applications connectées dans ChatGPT.

## Données et limites actuelles

- `data/brain/chatgpt.json` contient les autorisations privées et l’identifiant stable de cet hôte ; sous Debian, dossier 700 et fichier 600. Ne pas partager ce fichier ou le copier vers une autre machine. Il est exclu de Git et du paquet de déploiement. Le renouvellement des jetons est automatique et verrouillé entre les processus.
- `data/brain/history.sqlite3` contient les dix derniers échanges utilisés comme contexte par compte (les échanges plus anciens restent enregistrés localement). Les anciennes conversations Gemini restent dans leur base d’origine ; elles ne sont pas injectées dans GPT.
- Le cerveau sait répondre et analyser une image. La domotique, les minuteurs et les actualités en direct ne sont pas raccordés aux outils GPT dans cette version. Il ne prétend pas avoir effectué ces actions.
- La validation automatique couvre le protocole, les erreurs, les autorisations et le flux avec des serveurs simulés. La validation réelle du compte et d’une réponse nécessite ta connexion personnelle.

Références : [connexion](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), [modèles et inférence](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [comptes et sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions).
