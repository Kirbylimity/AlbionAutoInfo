# AlbionAutoInfo

Prototype Python pour lire une liste Google Sheets, appliquer trois filtres dans le marché Albion et extraire par OCR les prix et quantités affichés. Paramètres par défaut : tier, enchantement et qualité. Aucun achat ni vente automatique.

## Parcours conseillé : deux passages et profit

Utiliser **run_scan.py** pour lire et mettre à jour automatiquement la feuille avec le compte de service. Il lit la **première offre affichée** ; le choix du passage détermine uniquement la colonne de destination. Vous préparez vous-même le marché, le type d'offres et le tri avant chaque lancement.

Créer ces en-têtes dans le même onglet (les quatre premiers peuvent être renommés via `columns` dans config.json) :

```text
nom | tier | enchantement | qualité | prix_black_market | prix_marche | profit_brut
```

Après l'installation Python, Tesseract et la calibration décrites ci-dessous, installer également le module Google :

```powershell
.venv\Scripts\python -m pip install -r requirements-google.txt
```

Activer l'API Google Sheets, créer un compte de service et télécharger sa clé JSON sur votre PC, hors du dépôt. Partager la feuille avec l'adresse de ce compte en rôle **Éditeur**. Aucun partage public n'est nécessaire pour ce parcours : le compte lit et écrit directement. Ne pas envoyer la clé dans le chat.

Vérifier l'accès et les colonnes sans piloter le jeu ni modifier la feuille :

```powershell
.venv\Scripts\python run_scan.py --phase black --spreadsheet-id IDENTIFIANT --worksheet "Feuille 1" --credentials "C:\cles\service-account.json" --dry-run
```

1. Aller au Black Market et afficher les offres d'achat, prix décroissant, en haut de la liste. Revenir au terminal, avec Albion comme fenêtre précédente, puis lancer :

```powershell
.venv\Scripts\python run_scan.py --phase black --spreadsheet-id IDENTIFIANT --worksheet "Feuille 1" --credentials "C:\cles\service-account.json"
```

2. Aller au marché d'achat choisi et afficher les offres de vente, prix croissant, en haut de la liste. Revenir au terminal et relancer :

```powershell
.venv\Scripts\python run_scan.py --phase market --spreadsheet-id IDENTIFIANT --worksheet "Feuille 1" --credentials "C:\cles\service-account.json"
```

Chaque commande collecte toute la liste, conserve un CSV et les captures, puis écrit automatiquement les prix dans la colonne du passage. La collecte doit terminer sans erreur avant l'écriture ; les captures et résultats partiels restent sur disque en cas d'arrêt. La configuration doit correspondre à l'interface du marché actuel : utiliser `--config autre-config.json` si les coordonnées diffèrent entre les marchés.

Le profit brut par unité est calculé dès que les deux prix sont disponibles : **prix_black_market − prix_marche**. Une perte reste négative. Si l'autre prix est vide, le profit est vidé. Taxes, frais, transport, volumes disponibles et évolution des cours ne sont pas inclus. Le résultat est un écart entre deux relevés, pas un gain garanti. À chaque nouveau passage, la colonne du marché et le profit des objets scannés sont actualisés ; l'autre prix peut dater d'un passage précédent. Ce calcul écrit des nombres, pas des formules : une modification manuelle ultérieure nécessite un nouveau passage pour recalculer.

Ne pas trier ni modifier la feuille pendant le scan ou l'écriture. Vérifier le premier essai sur un seul objet : un prix OCR incorrect mais numérique peut être écrit. La calibration et l'authentification réelles ne peuvent pas être vérifiées depuis le cloud sans votre session de jeu et votre compte de service.

Les sections suivantes décrivent la calibration et les outils CSV séparés, qui restent disponibles.

## Installation sur le PC du jeu (Windows)

Python 3.12 recommandé. Installer aussi **Tesseract OCR** (moteur externe, non fourni par pip). Depuis ce dossier :

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

Si Tesseract n'est pas dans PATH, ajouter dans config.json une propriété `tesseract_cmd` contenant son chemin complet (les antislashs JSON doivent être doublés).

## Tableau

En-têtes par défaut : `nom,tier,enchantement,qualité`. Adapter `columns` pour vos intitulés. Les lignes incomplètes sont refusées. Exemple dans `example.csv`.

Pour une feuille partagée en lecture publique, utiliser l'URL suivante, avec son identifiant et son onglet :

```text
https://docs.google.com/spreadsheets/d/IDENTIFIANT/export?format=csv&gid=0
```

Pour une feuille privée, télécharger son onglet au format CSV et utiliser le fichier local. L'authentification Google privée automatique n'est pas implémentée. Ne pas rendre public un tableau confidentiel.

```powershell
.venv\Scripts\python albion_info.py --source example.csv --dry-run
```

## Calibration obligatoire sur le PC

Le cloud ne voit pas le jeu. Le script n'identifie pas automatiquement les éléments du marché. Utiliser une résolution, une échelle d'affichage et une disposition de fenêtre fixes, idéalement en mode fenêtré. Les coordonnées sont absolues, en pixels. Pour afficher la position du pointeur :

```powershell
.venv\Scripts\python -c "import pyautogui; pyautogui.displayMousePosition()"
```

Dans `config.json` :

- `search` : position du champ de recherche.
- Pour chaque filtre, `open` ouvre la liste et `options` associe chaque valeur du tableau à la position de son option. Toutes les valeurs utilisées doivent être calibrées. Les options doivent rester visibles au même emplacement, sans défilement nécessaire.
- `results_click` : clic facultatif pour ouvrir le détail du premier résultat après filtrage. `back_click` revient à la recherche après chaque objet. Utiliser `null` si inutile.
- `rows` : rectangles des cellules numériques pour chaque ligne d'offre visible. Exemple de structure : `[{"price": [100, 200, 80, 22], "quantity": [200, 200, 60, 22]}]`. Remplacer ces coordonnées par les vraies. Ne cadrer que les chiffres, sans icônes ni intitulés. Ne sélectionner que des lignes remplies.
- `wait_seconds` : délai après filtrage et ouverture du détail ; augmenter si le marché charge lentement.

Ouvrir le marché, revenir au terminal puis lancer :

```powershell
.venv\Scripts\python albion_info.py --source "https://docs.google.com/spreadsheets/d/IDENTIFIANT/export?format=csv&gid=0"
```

Après cinq secondes, le programme fait Alt+Tab une seule fois : Albion doit être la fenêtre précédente. Ne pas manipuler les fenêtres pendant la collecte. Pour arrêter, déplacer la souris dans le coin supérieur gauche de l'écran (sécurité PyAutoGUI), ou Ctrl+C dans le terminal.

## Résultats et limites

Chaque exécution crée un dossier `captures-*` avec `results.csv` et une capture PNG par objet. Les quantités des lignes **visibles et calibrées** au même prix sont additionnées. Ce n'est pas le stock total du marché : pagination et défilement ne sont pas implémentés. Vérifier que le premier résultat est le bon objet ; les noms ambigus peuvent sélectionner un autre objet.

L'OCR peut se tromper même si les nombres semblent valides. Comparer les premières captures avec le CSV avant d'utiliser les résultats. Une cellule vide ou un nombre ambigu arrête la collecte et conserve les résultats précédents. Le presse-papiers est utilisé pour saisir les noms. Le focus et les filtres ne sont pas vérifiés automatiquement : effectuer le premier essai sur un seul objet. Le fonctionnement réel dans Albion reste à valider localement.

## Développement cloud

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python albion_info.py --config config.example.json --source example.csv --dry-run
```

Les tests et le mode dry-run fonctionnent sans écran ni Tesseract. La collecte nécessite une session graphique locale, Tesseract et le jeu ouvert. Aucun service cloud à démarrer.

## Choisir le prix selon le marché

Le choix s'applique à toute l'exécution : `--market black` sélectionne le prix maximal lu, `--market classic` (par défaut) sélectionne le prix minimal lu. Le CSV contient désormais une seule ligne par objet et son numéro de ligne source `sheet_row`.

```powershell
.venv\Scripts\python albion_info.py --source example.csv --market black
```

Avant de lancer : au Black Market, afficher les **offres d'achat** triées du prix le plus élevé au plus bas ; au marché classique, afficher les **offres de vente** triées du prix le plus bas au plus élevé. Revenir au début des offres. Le programme ne configure ni ne vérifie ce tri. Sans cette préparation, le prix sélectionné est seulement le meilleur des lignes capturées, pas nécessairement le meilleur du marché. Ne pas changer de marché pendant une exécution. Aucun résultat n'est généré pour une offre vide ou illisible : la collecte s'arrête.

Les tiers acceptés vont de 1 à 8, les enchantements de 0 à 4. Qualités : Normal, Good, Outstanding, Excellent, Masterpiece (insensibles à la casse ; `outstangin` est accepté comme Outstanding).

## Renseigner la colonne prix dans Google Sheets (facultatif)

Un lien public en lecture seule ne donne **aucun droit d'écriture**. Sans autorisation supplémentaire, utiliser le CSV de résultats. Pour écrire depuis Python :

1. Activer l'API Google Sheets dans votre projet Google Cloud, créer un compte de service puis son fichier de clé JSON.
2. Garder ce fichier sur votre PC, hors du dépôt ; ne pas le transmettre dans le chat. Partager uniquement le tableau concerné avec l'adresse du compte de service, en rôle Éditeur.
3. Ajouter une colonne nommée `prix` (ou préciser `--price-column`). Installer le module facultatif :

```powershell
.venv\Scripts\python -m pip install -r requirements-google.txt
```

Après avoir vérifié les captures et le CSV, préparer la mise à jour :

```powershell
.venv\Scripts\python write_prices.py --results captures-YYYYMMDD-HHMMSS/results.csv --spreadsheet-id IDENTIFIANT --worksheet "Feuille 1" --credentials "C:\cles\service-account.json"
```

Cette commande affiche les cellules proposées sans les modifier. Relancer avec `--apply` pour inscrire les prix. Seule la cellule de prix de chaque ligne collectée est modifiée ; les autres colonnes sont conservées. L'outil relit les noms et paramètres du tableau et annule l'ensemble de l'écriture si une ligne ne correspond plus. Utiliser le même onglet et les mêmes intitulés de colonnes que pour la collecte. Ne pas modifier ni trier le tableau pendant l'écriture : la vérification et la mise à jour ne constituent pas une transaction atomique.

L'accès Google réel et la collecte Windows doivent être validés avec votre tableau et votre jeu ; aucun identifiant ni écran de jeu n'est disponible dans cet environnement cloud. Le programme ne détecte pas automatiquement le marché ou la fenêtre active.
