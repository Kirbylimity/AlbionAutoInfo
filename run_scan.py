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
    parser.add_argument('--limit', type=int, help='Limiter le test aux N premiers objets')
    parser.add_argument('--no-write', action='store_true', help='Collecter sans modifier Google Sheets')
    parser.add_argument('--import-results', help='Importer un CSV existant sans piloter le jeu')
    parser.add_argument('--start-row', type=int, default=2, help='Reprendre depuis cette ligne Google Sheets incluse')
    args = parser.parse_args()
    if args.start_row < 2:
        parser.error('--start-row doit être >= 2')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit doit être positif')
    import gspread
    client = gspread.service_account(filename=args.credentials)
    worksheet = client.open_by_key(args.spreadsheet_id).worksheet(args.worksheet)
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    snapshot = worksheet.get_all_values()
    items = sheet_items(snapshot, config['columns'])
    items = [item for item in items if item['sheet_row'] >= args.start_row]
    if args.limit is not None:
        items = items[:args.limit]
    if not items:
        raise ValueError('Aucun objet dans le tableau')
    # Vérifier les colonnes avant de manipuler le jeu.
    placeholder = [{**item, 'price': '1'} for item in items]
    prepare_comparison_updates(placeholder, snapshot, config['columns'], args.phase)
    if args.dry_run:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    def persist(results):
        if args.no_write:
            return
        current = worksheet.get_all_values()
        updates = prepare_comparison_updates(results, current, config['columns'], args.phase)
        if updates:
            worksheet.batch_update(updates, value_input_option='RAW')
            print(f'{len(results)} résultat(s) traité(s), Google Sheets mis à jour.')

    if args.import_results:
        with Path(args.import_results).open(encoding='utf-8-sig', newline='') as handle:
            results = list(csv.DictReader(handle))
        # Une erreur de ligne bloque le lot entier avant toute écriture.
        updates = prepare_comparison_updates(results, snapshot, config['columns'], args.phase)
        if args.no_write:
            print(json.dumps(updates, ensure_ascii=False, indent=2))
        else:
            persist(results)
        return
    validate(config, items)
    collect(config, items, args.output, 'first',
            on_result=None if args.no_write else lambda result: persist([result]))
    print(f'Terminé. Résultats locaux : {args.output}/results.csv')
    if args.no_write:
        print('Aucune écriture Google Sheets.')


if __name__ == '__main__':
    main()
