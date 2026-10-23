# Roadmap web

Ouvrir `/roadmap` sur le serveur Bender. Un lien est également présent en haut du banc d'essai.

La page présente neuf étapes et 54 actions avec leur détail, les domaines concernés et le critère de passage. Les cases sont réversibles. Elle affiche la progression globale, celle de l'étape, la prochaine action et un filtre pour masquer les actions terminées. Le bouton d'export télécharge un état JSON du plan et de la progression.

Chaque action propose un volet « Comment accomplir cette tâche » : endroit où agir, procédure pas à pas, résultat permettant de cocher la tâche et éléments à noter dans le suivi. Les commandes utiles précisent leur environnement Windows ou Debian et restent à exécuter manuellement. Ouvrir ou fermer un volet ne modifie pas la case ni la progression.

Les acquis confirmés sont précochés dans le plan initial. Les cases ne déclenchent aucune commande matérielle et ne constituent pas une validation automatique.

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

25 tests logiciels passent, dont trois tests de roadmap : persistance après recréation de l'application, indépendance des changements et refus des identifiants/valeurs invalides ou écritures d'une autre origine. L'aperçu local utilise une base distincte ; les coches de test ne sont pas déployées.
