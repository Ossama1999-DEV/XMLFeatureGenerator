# Houston XML Feature Generator

Petit éditeur graphique Windows pour générer des fichiers `feature_type` XML à partir du modèle Houston fourni.

## Démarrer

1. Installer Python 3.9+ si nécessaire (sur Windows, avec Tkinter).
2. Double-cliquer sur `lancer_generateur.bat`, ou dans PowerShell : `py -3 .\houston_xml_generator.py`.
3. Choisir un modèle, modifier ses champs, vérifier l'aperçu et cliquer sur **Générer XML…**.
4. Optionnel : **Importer une ligne HTML** pour préremplir les champs depuis `<tr>...</tr>`.
5. **Enregistrer preset** conserve le formulaire dans `presets.json` (créé automatiquement).
6. **Générer tous les presets…** exporte tous les modèles sauvegardés ou intégrés.

Aucune bibliothèque `pip` n'est requise. La GUI utilise `tkinter` et la génération utilise `xml.etree.ElementTree`.

## Règles importantes

- Le fichier créé a le même modèle de balises et attributs que les trois XML de référence : `feature_type`, `feature_type_properties`, `descriptions`, `size`, `feature_type_state_type`, `object_parameters`, `feature_type_icon`, `feature_type_vision`.
- Les champs *width*, *height* et *depth* sont **en mètres**. Les valeurs `x.x` sont laissées inchangées si aucune dimension n'est connue. L'import HTML extrait la valeur `m` et non les inches.
- Le `constant_name` est construit comme `FETY_` + nom technique en majuscules, conformément aux exemples.
- Les abréviations XML existantes ne sont pas toujours identiques à celles du tableau HTML (`WS_NC` dans le XML de référence contre `WSNC` dans le HTML). La valeur est modifiable ; **vérifier la convention auprès de l'équipe avant intégration**.
- Les dimensions renseignées par analogie (`OM2-2V`, `R5-10c`, `OM3`, etc.) ne sont **pas validées pour Houston**. Elles sont annotées dans le champ *Notes internes*, qui n'est pas inclus dans le XML.
- Les fichiers PNG SMALL/BIG et le fichier `.node` sont **référencés**, mais pas créés par cet outil. Il faut les déposer aux chemins attendus.
- La génération produit un XML syntaxiquement bien formé ; elle ne garantit pas sa compatibilité avec le schéma, le moteur ou le pipeline d'OKTAL. Tester sur une copie et valider avec l'équipe avant commit SVN.
- Les paramètres *State* et *Virtual* sont conservés comme dans les exemples.

## Exemple

Pour `Signal_US_WS_FloodZone`, le nom produit `Signal_US_WS_FloodZone.xml`, les icônes sont recherchées sous `Icons/Signal_US_WS_FloodZone/` et le node sous `Signal_US_WS_FloodZone.node`.

## Nouveau : automatisation complète du registre des layers

Lancer `lancer_pipeline.bat` (ou `py -3 houston_pipeline.py`).
Choisir : (1) catalogue HTML complet, (2) dossier des XML `feature_type`, (3) XML `config` avec la couche `<layer id="351" name="Signs">`.

- Analyse toutes les lignes HTML `Signal_US_WS_*` et construit des `feature_type` XML à partir de leurs colonnes.
- Crée **uniquement** les XML manquants ; si un XML existe et diffère, signale un **conflit bloquant**, sans l'écraser.
- Référence automatiquement les types dans la couche Signs **sans toucher aux autres layers**.
- Montre un aperçu `diff`, crée un backup horodaté `.bak` avant toute édition de la config, et tente de restaurer sur erreur.
- Conserve le HTML original et tous les fichiers existants.
- Le programme ne génère pas les PNG, les `.node` ni les autres ressources référencées.

**Important** : la configuration XML est modifiée chirurgicalement, mais une absence de perte ne peut être garantie pour des modifications concurrentes ou une intégration non testée au moteur. Travailler dans une copie SVN verrouillée / branche de test, relire `svn diff` et valider dans le simulateur.

### Pourquoi l'outil est prudent ?
Le catalogue HTML contient parfois des dimensions hypothétiques ou `x.x` : le générateur les reprend sans inventer de dimensions. Des abréviations peuvent différer des XML historiques (par exemple `WSNC` et `WS_NC`) : quand un fichier existant diffère, le programme refuse l'écrasement pour éviter de perdre l'information d'origine.
