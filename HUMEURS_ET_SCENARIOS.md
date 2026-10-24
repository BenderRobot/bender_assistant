# Humeurs, intensités et scénarios

Dans **Atelier → Samples et personnalité → Versions de Bender**, ouvrir
**Scénarios d’humeur · phrases et expressions des yeux**. Renseigner la clé de
contrôle, puis charger les scénarios.

Les modèles de départ contiennent **45 variantes** : cinq humeurs, trois
intensités et trois scénarios par combinaison. Aucun son n'est généré lors du
chargement. Les phrases sont des réactions proposées pour le robot, pas des
répliques attribuées au dessin animé.

| Commande écrite ou reconnue par le micro | Résultat |
| --- | --- |
| `Bender, sois triste` | Triste, intensité 2 |
| `Sois un peu triste` | Triste, intensité 1 |
| `Sois très triste` | Triste, intensité 3 |
| `Sois sarcastique niveau 1` | Sarcastique, intensité 1 |
| `Sois très joyeux` | Énergique, intensité 3 |
| `Passe en mode calme` | Neutre, intensité 2 |
| `Sois en colère niveau 3` | Agacé, intensité 3 |

Une commande d'humeur explicite est reconnue localement et ne nécessite pas de
réponse GPT. Les questions ordinaires et les phrases comme « pourquoi es-tu
triste ? » ou « ne sois pas triste » continuent d'être traitées normalement.
Cette commande joue une réaction ; elle n'impose pas une humeur permanente aux
réponses futures et ne déduit pas l'émotion de l'utilisateur.

## Composer les variantes

Choisir l'humeur, l'intensité et le scénario. Modifier sa phrase, ses yeux, son
nom ou son activation. **Enregistrer une nouvelle variante** conserve le scénario
source et ajoute une variante au même groupe. Les éditions utilisent une
révision : une modification ancienne est refusée si un autre écran a enregistré
entre-temps. On peut désactiver une variante sans la supprimer.

Les yeux peuvent être une expression intégrée ou une création de l'éditeur.
Une création est copiée dans le scénario à l'enregistrement, pour conserver son
rendu même si la création d'origine évolue. Recharger et sélectionner à nouveau
la création pour importer ses changements.

Le tirage est aléatoire parmi les scénarios actifs du niveau demandé. Quand
plusieurs variantes existent, le scénario précédent de ce groupe est exclu du
tirage suivant dans ce processus. Le suivi des derniers tirages repart au
redémarrage ; la configuration des scénarios, elle, est persistante. Un groupe
entièrement désactivé donne un message explicite, pas une humeur de remplacement.

## Voix et yeux synchronisés

- **Faire prononcer le texte** utilise le routage de voix sélectionné. Un nouvel
  audio ElevenLabs peut consommer des crédits ; un audio compatible déjà en cache
  est réutilisé en mode automatique. Chatterbox reste lent sur le CPU du Dell.
- **Réplique enregistrée** utilise le WAV publié dans la bibliothèque. Le texte
  réellement enregistré accompagne sa lecture ; aucune synthèse n'est demandée.
- Les yeux du scénario sont transmis avec les segments audio, dans le navigateur
  comme sur le Dell. Ils prennent le pas sur une sélection manuelle des yeux pour
  cette lecture. Les timelines, poses de bouche et fichiers en cache ne sont pas
  réécrits pour changer les yeux.
- Le bouton **Jouer un scénario au hasard** est un test explicite avec la sortie
  audio de l'atelier. Aucun test réel ElevenLabs n'est lancé par l'installation.

L'intensité change la sélection de phrase et d'yeux. Elle ne garantit pas à elle
seule une intonation vocale : le rendu dépend du moteur et, pour Chatterbox, de
la référence active de l'humeur. Les références, les scénarios et les répliques
restent trois objets distincts.

## Stockage et prochaine mise à jour

Les modèles de départ sont dans `bender_voice/mood-scenarios.json`. Après une
première édition, la configuration est sauvegardée dans
`<data_dir>/mood-scenarios.json`, hors Git. Les données Debian existantes sont
conservées à la mise à jour. Les modèles de départ ne remplacent pas un catalogue
personnalisé déjà enregistré.

Les médias Windows sont maintenant regroupés sous
`02_VOIX_ET_ANIMATIONS/a_importer/sons_originaux`, `videos_originales` et
`voix_elevenlabs`. La mise à jour transfère les nouveaux contenus de ces trois
sous-dossiers. Les validations existantes restent attachées aux empreintes des
fichiers. Le rangement et son manifeste sont décrits dans
`02_VOIX_ET_ANIMATIONS/MEDIATHEQUE.md` à la racine du projet.
