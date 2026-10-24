"""Un passage complet : lecture du Sheet, collecte locale et prix/profit dans le Sheet."""
import argparse
import csv
import io
import json
import time
from pathlib import Path
from albion_info import collect, read_items, validate
from write_prices import prepare_comparison_updates


def sheet_items(values, columns):
    buffer = io.StringIO(newline='')
    csv.writer(buffer).writerows(values)
    return read_items(buffer.getvalue(), columns)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['black', 'market'], help='Choisit la colonne de destination, pas le tri')
    parser.add_argument('--spreadsheet-id', required=True)
    parser.add_argument('--worksheet', required=True)
    parser.add_argument('--credentials', required=True, help='Fichier JSON local du compte de service')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output', default=time.strftime('captures-%Y%m%d-%H%M%S'))
    parser.add_argument('--dry-run', action='store_true', help='Lire et valider le tableau sans clic ni écriture')
    args = parser.parse_args()
    import gspread
    client = gspread.service_account(filename=args.credentials)
    worksheet = client.open_by_key(args.spreadsheet_id).worksheet(args.worksheet)
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    snapshot = worksheet.get_all_values()
    items = sheet_items(snapshot, config['columns'])
    if not items:
        raise ValueError('Aucun objet dans le tableau')
    # Vérifier les colonnes avant de manipuler le jeu.
    placeholder = [{**item, 'price': '1'} for item in items]
    prepare_comparison_updates(placeholder, snapshot, config['columns'], args.phase)
    if args.dry_run:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    validate(config, items)
    # Le joueur prépare le tri : lire la première offre, quel que soit le marché.
    collect(config, items, args.output, 'first')
    with (Path(args.output) / 'results.csv').open(encoding='utf-8-sig', newline='') as handle:
        results = list(csv.DictReader(handle))
    # Relecture pour éviter d'écrire dans une ligne déplacée pendant la collecte.
    current = worksheet.get_all_values()
    updates = prepare_comparison_updates(results, current, config['columns'], args.phase)
    worksheet.batch_update(updates, value_input_option='RAW')
    print(f'{len(results)} prix enregistrés (passage {args.phase}). Profit brut actualisé si les deux prix sont présents.')


if __name__ == '__main__':
    main()
