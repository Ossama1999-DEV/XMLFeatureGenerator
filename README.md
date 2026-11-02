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
