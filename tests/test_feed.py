import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh_feed', ROOT / 'scripts/refresh_feed.py')
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.items = json.loads((ROOT / 'feed-products.json').read_text())

    def html(self, item, price='108000', sku=None):
        product = {'@type': 'Product', 'sku': sku or item['sku'], 'name': 'Изделие',
                   'description': 'Описание', 'image': ['https://stekloroll.ru/catalog/assets/item.webp'],
                   'offers': {'url': item['url'], 'price': price, 'priceCurrency': 'RUB'}}
        return '<link rel="canonical" href="' + item['url'] + '"><script type="application/ld+json">' + json.dumps(product) + '</script>'

    def test_publishes_retained_ids_and_live_price_in_yml_currency(self):
        by_url = {item['url']: self.html(item, price='123456.78') for item in self.items}
        tree = feed.build(self.items, fetch=by_url.__getitem__)
        offers = tree.findall('.//offer')
        self.assertEqual([offer.get('id') for offer in offers], [item['id'] for item in self.items])
        self.assertTrue(all(offer.findtext('price') == '123456.78' for offer in offers))
        self.assertTrue(all(offer.findtext('currencyId') == 'RUR' for offer in offers))

    def test_does_not_rename_or_substitute_products(self):
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            feed.product_from_page(self.items[0], self.html(self.items[0], sku='OTHER-PRODUCT'))

    def test_rejects_invalid_prices_and_external_images(self):
        item = self.items[0]
        for price in ['0', '-10', 'NaN', 'Infinity', 'not-a-price']:
            with self.subTest(price=price), self.assertRaises(ValueError):
                feed.product_from_page(item, self.html(item, price=price))
        with self.assertRaisesRegex(ValueError, 'origin'):
            feed.product_from_page(item, self.html(item).replace('https://stekloroll.ru/catalog/assets/item.webp', 'https://example.org/item.webp'))

    def test_rejects_duplicate_ids_and_fetch_errors(self):
        items = copy.deepcopy(self.items)
        items[1]['id'] = items[0]['id']
        with self.assertRaisesRegex(ValueError, 'unique'):
            feed.build(items)
        def failed(_):
            raise OSError('source is unavailable')
        with self.assertRaises(OSError):
            feed.build(self.items, fetch=failed)

    def test_adds_distinct_size_without_replacing_existing_offers(self):
        items = copy.deepcopy(self.items)
        compact = copy.deepcopy(items[-1])
        compact.update(id='SR-RS-1100x1000-MAN', sku='SR-RS-1100x1000-MAN',
                       url='https://stekloroll.ru/catalog/prozrachnye-rolstavni-1100x1000/')
        items.append(compact)
        pages = {item['url']: self.html(item) for item in items}
        tree = feed.build(items, fetch=pages.__getitem__)
        self.assertEqual(len(tree.findall('.//offer')), 7)
        self.assertEqual(tree.findall('.//offer')[-1].get('id'), compact['id'])
        for field in ('sku', 'url'):
            duplicate = copy.deepcopy(items)
            duplicate[-1][field] = duplicate[0][field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'unique'):
                feed.build(duplicate)

    def test_cannot_drop_a_retained_offer_during_expansion(self):
        with self.assertRaisesRegex(ValueError, 'retained'):
            feed.build(self.items[1:])


if __name__ == '__main__':
    unittest.main()
