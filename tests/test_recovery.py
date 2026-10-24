import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from albion_info import collect, read_market_result
from write_prices import prepare_comparison_updates

COLUMNS = dict(name='nom', tier='tier', enchantment='enchantement', quality='qualité')
HEADERS = ['nom','tier','enchantement','qualité','prix_black_market','prix_marche','profit_brut']
ITEM = dict(name='Sac', tier='4', enchantment='0', quality='Normal', sheet_row=2)

class RecoveryTests(unittest.TestCase):
    def test_no_offer_requires_explicit_message(self):
        image = Image.new('RGB', (300,100))
        config = {'no_offers_region':[0,0,100,30], 'rows':[{'price':[100,0,100,30]}]}
        self.assertEqual(read_market_result(image, config, Mock(return_value='No offers found.'), 'first')['status'], 'no_offer')
        with self.assertRaises(ValueError):
            read_market_result(image, config, Mock(side_effect=['garbage', '———)']), 'first')

    def test_absence_clears_price_and_profit_only(self):
        result = {**ITEM, 'status':'no_offer', 'price':''}
        sheet = [HEADERS, ['Sac','4','0','Normal','100','80','20']]
        self.assertEqual(prepare_comparison_updates([result], sheet, COLUMNS, 'black'),
                         [{'range':'E2','values':[['']]}, {'range':'G2','values':[['']]}])

    def test_ocr_error_preserves_existing_values(self):
        sheet = [HEADERS, ['Sac','4','0','Normal','100','80','20']]
        self.assertEqual(prepare_comparison_updates([{**ITEM,'status':'ocr_error','price':''}], sheet, COLUMNS, 'black'), [])

    def test_scan_continues_and_flushes_before_each_callback(self):
        gui = Mock()
        gui.screenshot.return_value = Image.new('RGB', (300,100))
        tesseract = Mock()
        outcomes = [dict(status='ok',price=100,visible_quantity='',error=''),
                    dict(status='no_offer',price='',visible_quantity='',error=''),
                    ValueError('bad OCR'), ValueError('bad OCR'),
                    dict(status='ok',price=200,visible_quantity='',error='')]
        items = [{**ITEM, 'sheet_row': i+2} for i in range(4)]
        config = {'search':[10,10], 'rows':[{'price':[1,1,20,20]}],
                  'filters':{key:{'open':[10,10], 'options':{ITEM[key]:[20,20]}}
                             for key in ('tier','enchantment','quality')}}
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)/'scan'
            seen = []
            def callback(result):
                with (destination/'results.csv').open(encoding='utf-8-sig',newline='') as handle:
                    saved = list(csv.DictReader(handle))
                self.assertEqual(saved[-1]['status'], result['status'])
                seen.append(result['status'])
            with patch.dict('sys.modules', {'pyautogui':gui, 'pyperclip':Mock(), 'pytesseract':tesseract}), \
                 patch('albion_info.time.sleep'), patch('albion_info.read_market_result', side_effect=outcomes):
                collect(config, items, destination, 'first', callback)
            self.assertEqual(seen, ['ok','no_offer','ocr_error','ok'])

    def test_old_csv_without_status_remains_importable(self):
        sheet = [HEADERS, ['Sac','4','0','Normal','','80','']]
        updates = prepare_comparison_updates([{**ITEM,'price':'100'}], sheet, COLUMNS, 'black')
        self.assertEqual(updates[-1]['values'], [[20]])
