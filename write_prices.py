"""Écrire un CSV de résultats vérifié dans une colonne Google Sheets existante."""
import argparse
import csv
import json
from pathlib import Path
from albion_info import normalize_item, parse_integer


def column_letter(index):
    result = ''
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(65 + digit) + result
    return result


def prepare_updates(results, sheet, columns, price_column):
    if not sheet:
        raise ValueError('Feuille vide')
    headers = sheet[0]
    required = list(columns.values()) + [price_column]
    if price_column in columns.values():
        raise ValueError('La colonne prix doit être distincte des colonnes source')
    for header in required:
        if headers.count(header) != 1:
            raise ValueError(f'En-tête absent ou ambigu : {header}')
    indexes = {key: headers.index(value) for key, value in columns.items()}
    target = column_letter(headers.index(price_column) + 1)
    updates, seen = [], set()
    for result in results:
        row = int(result['sheet_row'])
        if row < 2 or row > len(sheet) or row in seen:
            raise ValueError(f'Ligne invalide ou dupliquée : {row}')
        seen.add(row)
        current = sheet[row - 1]
        identity = {key: str(current[index]).strip() if index < len(current) else '' for key, index in indexes.items()}
        identity = normalize_item(identity)
        if identity != {key: result[key] for key in columns}:
            raise ValueError(f'Ligne {row} modifiée depuis la collecte ; écriture annulée')
        value = '' if result.get('status') == 'no_offer' else parse_integer(result['price'])
        updates.append({'range': f'{target}{row}', 'values': [[value]]})
    if not updates:
        raise ValueError('Aucun prix à écrire')
    return updates



def prepare_comparison_updates(results, sheet, columns, phase,
                               black_column='prix_black_market',
                               market_column='prix_marche', profit_column='profit_brut'):
    results = [r for r in results if r.get('status', 'ok') in {'ok', 'no_offer'}]
    if not results:
        return []
    if phase not in {'black', 'market'}:
        raise ValueError('Passage attendu : black ou market')
    names = [black_column, market_column, profit_column]
    if len(set(names)) != 3 or set(names) & set(columns.values()):
        raise ValueError('Les colonnes de prix et profit doivent être distinctes des sources')
    headers = sheet[0] if sheet else []
    for name in names:
        if headers.count(name) != 1:
            raise ValueError(f'En-tête absent ou ambigu : {name}')
    target = black_column if phase == 'black' else market_column
    updates = prepare_updates(results, sheet, columns, target)
    other = market_column if phase == 'black' else black_column
    other_index = headers.index(other)
    profit_letter = column_letter(headers.index(profit_column) + 1)
    for result in results:
        row = int(result['sheet_row'])
        cells = sheet[row - 1]
        previous = str(cells[other_index]).strip() if other_index < len(cells) else ''
        profit = ''
        if previous and result.get('status') != 'no_offer':
            # Les valeurs non numériques sont refusées avant toute écriture.
            other_price = parse_integer(previous)
            price = parse_integer(result['price'])
            profit = price - other_price if phase == 'black' else other_price - price
        updates.append({'range': f'{profit_letter}{row}', 'values': [[profit]]})
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True)
    parser.add_argument('--spreadsheet-id', required=True)
    parser.add_argument('--worksheet', required=True, help="Nom exact de l'onglet")
    parser.add_argument('--credentials', required=True, help='Chemin JSON du compte de service, conservé sur votre PC')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--price-column', default='prix')
    parser.add_argument('--apply', action='store_true', help='Sans cette option, afficher uniquement les cellules proposées')
    args = parser.parse_args()
    import gspread
    client = gspread.service_account(filename=args.credentials)
    worksheet = client.open_by_key(args.spreadsheet_id).worksheet(args.worksheet)
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    with open(args.results, encoding='utf-8-sig', newline='') as handle:
        results = list(csv.DictReader(handle))
    updates = prepare_updates(results, worksheet.get_all_values(), config['columns'], args.price_column)
    if args.apply:
        worksheet.batch_update(updates, value_input_option='RAW')
        print(f'{len(updates)} prix écrits dans la colonne {args.price_column}')
    else:
        print(json.dumps(updates, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
