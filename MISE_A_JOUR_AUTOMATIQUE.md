# Mise a jour depuis Windows

Le script teste le code local, cree un commit si necessaire, pousse main sur GitHub,
puis transfere cette revision exacte au Debian par SSH. Il fonctionne aussi avec
l'installation Debian initiale provenant du ZIP. Aucun mot de passe n'est enregistre.

Prerequis Windows : Git, OpenSSH et Python avec les dependances du projet.
Dans le depot local :

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt -r requirements-io.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Update-Bender.ps1 -RepoPath . -Message "Amelioration de Bender"
```

Depuis un autre PC, copier le depot avec les modifications et le script, ou cloner
GitHub puis y appliquer les fichiers de mise a jour avant de lancer cette commande.
Un clone seul ne contient que les modifications deja publiees. Le parametre RepoPath
permet de selectionner ce dossier. S'il n'existe pas, le script clone le depot.

`-WhatIf` affiche l'intention sans executer le processus. `-PublishOnly` teste,
commit et pousse sans toucher Debian. Les modifications de code presentes dans
le depot sont incluses dans le commit ; verifier `git status` avant de lancer.
Le script refuse un main en retard sur GitHub : integrer les modifications avant
de relancer. Il ne force jamais un push.

SSH et SCP demandent le mot de passe Debian si aucune cle n'est configuree.
Le script ignore le fichier SSH config Windows via `-F NUL`, mais conserve la
verification des cles du serveur. GitHub utilise les identifiants Git habituels.

Sur Debian, le script demande sudo, sauvegarde le dossier (hors gros fichiers et
modeles), conserve `.env`, `voice.json`, les samples, les modeles et la memoire,
installe les dependances puis active `bender.service` au demarrage. Il reprend
le serveur Python manuel uniquement s'il tourne dans ce meme dossier. n8n et
Home Assistant ne sont pas modifies. La premiere installation peut etre longue.

Les sauvegardes sont dans `~/.local/state/bender-backups/`, protegees en lecture.
Elles contiennent potentiellement la configuration privee : ne pas les publier.
En cas d'echec, le script indique leur chemin et s'arrete. La restauration est
manuelle ; les dependances Python ne sont pas restaurees automatiquement.
Diagnostic : `sudo journalctl -u bender.service -n 60 --no-pager`.

Les fichiers prives auparavant suivis par Git sont retires du suivi, sans effacer
leur copie locale. Cela n'efface pas l'ancien historique GitHub : toute cle qui
y a ete publiee doit etre revoquee. Ne pas ajouter de secrets dans les fichiers
de code : les controles du script ne constituent pas un detecteur universel.
