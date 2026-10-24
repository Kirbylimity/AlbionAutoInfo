"""Lecture Google Sheets et collecte du marché via une interface calibrée."""
import argparse
import csv
import io
import json
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path


QUALITIES = {'normal': 'Normal', 'good': 'Good', 'outstanding': 'Outstanding',
             'outstangin': 'Outstanding', 'excellent': 'Excellent', 'masterpiece': 'Masterpiece'}


def normalize_item(item):
    for key, low, high in [('tier', 1, 8), ('enchantment', 0, 4)]:
        if item[key] not in {str(n) for n in range(low, high + 1)}:
            raise ValueError(f'{key} doit être compris entre {low} et {high}')
    quality = item['quality'].casefold()
    if quality not in QUALITIES:
        raise ValueError(f"Qualité inconnue : {item['quality']}")
    return {**item, 'quality': QUALITIES[quality]}


def select_price(totals, market):
    if market not in {'black', 'classic', 'first'}:
        raise ValueError('Marché attendu : black ou classic')
    if not totals:
        raise ValueError('Aucune offre lisible')
    if market == 'first':
        return next(iter(totals))
    return max(totals) if market == 'black' else min(totals)


def read_items(text, columns):
    reader = csv.DictReader(io.StringIO(text))
    missing = set(columns.values()) - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Colonnes absentes : {', '.join(sorted(missing))}")
    items = []
    for number, row in enumerate(reader, 2):
        if not any((row.get(column) or '').strip() for column in columns.values()):
            continue
        item = {key: (row.get(column) or '').strip() for key, column in columns.items()}
        if not all(item.values()):
            raise ValueError(f'Ligne {number} incomplète')
        items.append({**normalize_item(item), 'sheet_row': number})
    return items


def load_items(source, columns):
    if source.startswith('https://'):
        # Ne télécharger que les exports Google Sheets, sans identifiants dans le code.
        if not re.fullmatch(r'https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+/export\?format=csv&gid=\d+', source):
            raise ValueError('Utiliser une URL Google Sheets export?format=csv&gid=0')
        with urllib.request.urlopen(source, timeout=30) as response:
            text = response.read().decode('utf-8-sig')
        if text.lstrip().lower().startswith(('<!doctype', '<html')):
            raise ValueError('Google a renvoyé une page HTML : vérifier le partage du document')
    else:
        text = Path(source).read_text(encoding='utf-8-sig')
    return read_items(text, columns)


def parse_integer(text):
    # Rejeter une lecture ambiguë plutôt que créer un prix vraisemblable mais faux.
    text = text.strip()
    if not re.fullmatch(r'(?:\d+|\d{1,3}(?:[ ,\.\u00a0\u202f]\d{3})+)', text):
        raise ValueError(f'Nombre OCR ambigu : {text!r}')
    value = int(re.sub(r'\D', '', text))
    if value <= 0:
        raise ValueError('Prix et quantité doivent être positifs')
    return value


def read_offers(screenshot, rows, ocr):
    totals = Counter()
    quantities = all(row.get('quantity') is not None for row in rows)
    for row in rows:
        values = {}
        for field in ('price', 'quantity') if quantities else ('price',):
            x, y, width, height = row[field]
            crop = screenshot.crop((x, y, x + width, y + height))
            text = ocr(crop.resize((width * 3, height * 3)), config='--psm 7')
            values[field] = parse_integer(text)
        # Une quantité inconnue reste vide dans le CSV, jamais inventée.
        totals[values['price']] += values.get('quantity', 0)
    return totals, quantities


def validate(config, items):
    if set(config['columns']) != {'name', 'tier', 'enchantment', 'quality'}:
        raise ValueError('Configurer name, tier, enchantment, quality')
    if not config.get('rows'):
        raise ValueError('Configurer au moins une ligne de prix/quantité')
    for key in ('tier', 'enchantment', 'quality'):
        for item in items:
            if item[key] not in config['filters'][key]['options']:
                raise ValueError(f"Option {key} non calibrée : {item[key]}")
    if config.get('wait_seconds', 2) < 1:
        raise ValueError('wait_seconds doit être >= 1')


def collect(config, items, output, market):
    import pyautogui as gui
    import pyperclip
    import pytesseract

    if config.get('tesseract_cmd'):
        pytesseract.pytesseract.tesseract_cmd = config['tesseract_cmd']
    pytesseract.get_tesseract_version()
    gui.FAILSAFE = True
    gui.PAUSE = 0.3
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    print('Ouvrir le marché Albion puis revenir ici. Démarrage dans 5 secondes. Coin haut gauche = arrêt.')
    time.sleep(5)
    gui.hotkey('alt', 'tab')
    time.sleep(2)
    with (destination / 'results.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=['sheet_row', 'name', 'tier', 'enchantment', 'quality', 'market', 'price', 'visible_quantity', 'captured_at'])
        writer.writeheader()
        for index, item in enumerate(items):
            gui.click(*config['search'])
            gui.hotkey('ctrl', 'a')
            pyperclip.copy(item['name'])
            gui.hotkey('ctrl', 'v')
            gui.press('enter')
            for key in ('tier', 'enchantment', 'quality'):
                control = config['filters'][key]
                gui.click(*control['open'])
                gui.click(*control['options'][item[key]])
            time.sleep(config.get('wait_seconds', 2))
            if config.get('results_click'):
                gui.click(*config['results_click'])
                time.sleep(config.get('wait_seconds', 2))
            screenshot = gui.screenshot()
            screenshot.save(destination / f'{index:04d}.png')
            try:
                totals, quantities = read_offers(screenshot, config['rows'], pytesseract.image_to_string)
            except ValueError as error:
                raise ValueError(f"Lecture arrêtée pour {item['name']}. Vérifier {index:04d}.png : {error}") from error
            price = select_price(totals, market)
            writer.writerow({**item, 'market': market, 'price': price,
                             'visible_quantity': totals[price] if quantities else '',
                             'captured_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')})
            handle.flush()
            if config.get('back_click'):
                gui.click(*config['back_click'])
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--source', required=True, help='Fichier CSV ou URL export Google Sheets')
    parser.add_argument('--output', default=time.strftime('captures-%Y%m%d-%H%M%S'))
    parser.add_argument('--market', choices=['black', 'classic', 'first'], default='classic', help='black = maximal ; classic = minimal ; first = première offre selon votre tri')
    parser.add_argument('--dry-run', action='store_true', help='Valider les données sans piloter le jeu')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    items = load_items(args.source, config['columns'])
    if not items:
        raise ValueError('Aucun objet dans le tableau')
    if args.dry_run:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        validate(config, items)
        collect(config, items, args.output, args.market)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error))
