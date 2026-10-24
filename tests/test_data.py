import unittest
from albion_info import parse_integer, read_items, validate

COLUMNS = dict(name='nom', tier='tier', enchantment='enchantement', quality='qualité')

class DataTests(unittest.TestCase):
    def test_csv_accents_and_quoted_names(self):
        items = read_items('nom,tier,enchantement,qualité\n"Sac, ancien",4,0,Normal\n', COLUMNS)
        self.assertEqual(items[0]['name'], 'Sac, ancien')
        self.assertEqual(items[0]['tier'], '4')

    def test_incomplete_row_rejected(self):
        with self.assertRaises(ValueError):
            read_items('nom,tier,enchantement,qualité\nSac,4,,Normal\n', COLUMNS)

    def test_wrong_headers_rejected(self):
        with self.assertRaises(ValueError):
            read_items('name\nSac\n', COLUMNS)

    def test_ocr_thousands(self):
        for text in ['1234', '1,234', '1.234', '1 234', '1\u202f234']:
            self.assertEqual(parse_integer(text), 1234)

    def test_ambiguous_ocr_rejected(self):
        for text in ['', '1O0', '12.5', '-5', '0', '100\n200']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_integer(text)

    def test_uncalibrated_rows_rejected(self):
        with self.assertRaises(ValueError):
            validate({'columns': COLUMNS, 'rows': []}, [])

if __name__ == '__main__':
    unittest.main()

class MarketTests(unittest.TestCase):
    def test_market_direction(self):
        from albion_info import select_price
        self.assertEqual(select_price({900: 2, 100: 3, 500: 1}, 'black'), 900)
        self.assertEqual(select_price({900: 2, 100: 3, 500: 1}, 'classic'), 100)

    def test_ranges_and_quality(self):
        from albion_info import normalize_item
        item = dict(name='Sac', tier='8', enchantment='4', quality='outstangin')
        self.assertEqual(normalize_item(item)['quality'], 'Outstanding')
        for key, value in [('tier', '9'), ('tier', '0'), ('enchantment', '5'), ('quality', 'inconnue')]:
            with self.assertRaises(ValueError):
                normalize_item({**item, key: value})

    def test_row_identity_includes_blank_rows(self):
        items = read_items('nom,tier,enchantement,qualité\n,,,\nSac,4,0,Normal\n', COLUMNS)
        self.assertEqual(items[0]['sheet_row'], 3)

class WriteTests(unittest.TestCase):
    def test_only_correct_price_cell_updated(self):
        from write_prices import prepare_updates
        result = dict(sheet_row='2', name='Sac', tier='4', enchantment='0', quality='Normal', price='1234')
        sheet = [['nom','tier','enchantement','qualité','prix'], ['Sac','4','0','normal','99']]
        self.assertEqual(prepare_updates([result], sheet, COLUMNS, 'prix'), [{'range':'E2','values':[[1234]]}])
        sheet[1][0] = 'Épée'
        with self.assertRaises(ValueError):
            prepare_updates([result], sheet, COLUMNS, 'prix')

    def test_input_column_cannot_be_overwritten(self):
        from write_prices import prepare_updates
        with self.assertRaises(ValueError):
            prepare_updates([], [list(COLUMNS.values())], COLUMNS, 'tier')

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.headers = ['nom', 'tier', 'enchantement', 'qualité', 'prix_black_market', 'prix_marche', 'profit_brut']
        self.item = dict(sheet_row='2', name='Sac', tier='4', enchantment='0', quality='Normal', price='80')

    def test_second_pass_profit(self):
        from write_prices import prepare_comparison_updates
        sheet = [self.headers, ['Sac','4','0','Normal','100','','']]
        self.assertEqual(prepare_comparison_updates([self.item], sheet, COLUMNS, 'market'),
                         [{'range':'F2','values':[[80]]}, {'range':'G2','values':[[20]]}])

    def test_black_pass_can_be_rerun_and_loss_retained(self):
        from write_prices import prepare_comparison_updates
        sheet = [self.headers, ['Sac','4','0','Normal','100','90','10']]
        self.assertEqual(prepare_comparison_updates([self.item], sheet, COLUMNS, 'black')[-1]['values'], [[-10]])

    def test_missing_other_price_clears_profit(self):
        from write_prices import prepare_comparison_updates
        sheet = [self.headers, ['Sac','4','0','Normal','','','999']]
        self.assertEqual(prepare_comparison_updates([self.item], sheet, COLUMNS, 'market')[-1]['values'], [['']])

    def test_invalid_previous_price_aborts(self):
        from write_prices import prepare_comparison_updates
        sheet = [self.headers, ['Sac','4','0','Normal','erreur','','']]
        with self.assertRaises(ValueError):
            prepare_comparison_updates([self.item], sheet, COLUMNS, 'market')

    def test_player_sort_uses_first_offer(self):
        from albion_info import select_price
        self.assertEqual(select_price({500: 1, 900: 2, 100: 3}, 'first'), 500)

    def test_empty_source_with_old_prices_is_skipped(self):
        from run_scan import sheet_items
        items = sheet_items([self.headers, ['', '', '', '', '100', '80', '20'],
                             ['Sac','4','0','Normal']], COLUMNS)
        self.assertEqual(items[0]['sheet_row'], 3)

class OfferReadingTests(unittest.TestCase):
    def test_price_only_keeps_quantity_unknown(self):
        from albion_info import read_offers
        from PIL import Image
        totals, known = read_offers(Image.new('RGB', (200, 50)),
                                   [{'price': [0, 0, 100, 25]}],
                                   lambda *args, **kwargs: '58,046,710')
        self.assertEqual(list(totals), [58046710])
        self.assertFalse(known)

    def test_explicit_quantities_are_aggregated(self):
        from albion_info import read_offers
        from PIL import Image
        from unittest.mock import Mock
        rows = [{'price': [0,0,50,20], 'quantity': [50,0,50,20]}] * 2
        totals, known = read_offers(Image.new('RGB', (100,50)), rows,
                                   Mock(side_effect=['100', '2', '100', '3']))
        self.assertEqual(totals[100], 5)
        self.assertTrue(known)
