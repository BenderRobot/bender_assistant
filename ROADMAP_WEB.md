# Roadmap web

Ouvrir `/roadmap` sur le serveur Bender. Un lien est également présent en haut du banc d'essai.

La page présente neuf étapes et 54 actions avec leur détail, les domaines concernés et le critère de passage. Les cases sont réversibles. Elle affiche la progression globale, celle de l'étape, la prochaine action et un filtre pour masquer les actions terminées. Le bouton d'export télécharge un état JSON du plan et de la progression.

Chaque action propose un volet « Comment accomplir cette tâche » : endroit où agir, procédure pas à pas, résultat permettant de cocher la tâche et éléments à noter dans le suivi. Les commandes utiles précisent leur environnement Windows ou Debian et restent à exécuter manuellement. Ouvrir ou fermer un volet ne modifie pas la case ni la progression.

Les acquis confirmés sont précochés dans le plan initial. Les cases ne déclenchent aucune commande matérielle et ne constituent pas une validation automatique.

## Notes et Kanban

Chaque étape propose une note libre (8 000 caractères maximum) et un statut indépendant des cases. Écrire puis cliquer sur « Enregistrer la note » ; un message confirme la sauvegarde. Les brouillons sont gardés lorsqu'on change d'étape dans la page, et une alerte prévient avant de quitter avec des notes non enregistrées.

La page `/kanban` classe les neuf étapes dans « À faire », « En progrès », « À tester » et « Validé ». Déplacer une tuile par la poignée ou le menu « Déplacer vers ». Le menu permet aussi l'utilisation au clavier et sur mobile. Le numéro et la couleur d'une tuile restent liés à son étape. Le titre ouvre le détail de la roadmap ; la note peut être modifiée depuis les deux vues.

Le statut Kanban est déclaré manuellement : déplacer vers Validé ne coche pas les actions, et cocher toutes les actions ne déplace pas automatiquement la tuile. Le compteur de validation des étapes suit ces statuts ; le pourcentage général continue de compter les actions cochées.

Pour l'étape mécanique, une note initiale consigne la tête validée en CAO et l'attente des composants. Elle ne remplace pas une note que l'utilisateur a déjà enregistrée. Les notes, statuts et cases partagent la base `data/roadmap.sqlite3`. L'évolution de la base préserve les cases existantes ; l'export de la roadmap inclut aussi les notes et statuts.

## Conservation

Le contenu éditorial est dans `roadmap-plan.json`. Garder les identifiants des actions stables pour préserver le sens des cases déjà cochées. La progression vit par défaut dans `data/roadmap.sqlite3`, hors Git et des archives de code. Elle est conservée lors des mises à jour par le déploiement actuel et partagée entre les navigateurs après rechargement.

Inclure ce fichier dans les sauvegardes des données personnelles du projet. L'export JSON est un relevé lisible ; cette version ne propose pas d'import automatique.

Le paramètre d'environnement `BENDER_ROADMAP_DB` permet de changer le fichier de stockage. Aucun token matériel n'est requis pour cette checklist sur le réseau de Bender. Les écritures venant d'une autre origine web sont refusées.

## Installation depuis Windows

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\benjamin.laurens\Documents\bender_main\MAJ_BENDER.ps1" -Message "Ajout de la roadmap interactive"
```

Après succès, ouvrir http://192.168.1.41:8000/roadmap et actualiser si nécessaire.

## Validation

27 tests logiciels passent, dont cinq tests de roadmap : persistance après recréation de l'application, migration des anciennes cases, notes/statuts indépendants des actions et refus des identifiants/valeurs invalides ou écritures d'une autre origine. L'aperçu local utilise une base distincte ; ses données de test ne sont pas déployées.
