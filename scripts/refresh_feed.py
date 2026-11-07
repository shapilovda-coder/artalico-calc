"""Refresh the existing StekloRoll YML from verified public product pages."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json
import os
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://stekloroll.ru'
CATEGORIES = {'frameless': ('1', 'Безрамное остекление'),
              'partitions': ('2', 'Стеклянные перегородки'),
              'shutters': ('3', 'Прозрачные рольставни')}
RETAINED_IDS = {'221295256522', '957708253232', '327594126102', '337219104302'}


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.current = []
        self.blocks = []
        self.canonicals = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.active = True
            self.current = []
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs.get('href'))

    def handle_data(self, data):
        if self.active:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.blocks.append(json.loads(''.join(self.current)))
            self.active = False


def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'stekloroll.ru' or parsed.fragment:
        raise ValueError('Unexpected product or image origin')
    return url


def fetch_page(url):
    request = Request(public_url(url), headers={'User-Agent': 'StekloRoll-Feed-Refresh/1.0'})
    with urlopen(request, timeout=30) as response:
        if response.status != 200 or response.url != url:
            raise ValueError('Product page is unavailable or redirects: ' + url)
        return response.read().decode('utf-8')


def product_from_page(item, html):
    page = Metadata()
    page.feed(html)
    if page.canonicals != [item['url']]:
        raise ValueError('Product canonical mismatch: ' + item['id'])
    nodes = []
    for block in page.blocks:
        if isinstance(block, dict):
            nodes.extend(block.get('@graph', [block]))
        elif isinstance(block, list):
            nodes.extend(block)
    products = [n for n in nodes if isinstance(n, dict) and n.get('@type') == 'Product']
    if len(products) != 1:
        raise ValueError('Expected exactly one Product: ' + item['id'])
    product = products[0]
    offer = product.get('offers', {})
    if product.get('sku') != item['sku'] or offer.get('url') != item['url']:
        raise ValueError('Product identity mismatch: ' + item['id'])
    if offer.get('priceCurrency') != 'RUB':
        raise ValueError('Unexpected source currency')
    try:
        price = Decimal(str(offer['price']))
    except (InvalidOperation, KeyError) as error:
        raise ValueError('Missing or invalid price') from error
    if not price.is_finite() or price <= 0:
        raise ValueError('Price must be positive and finite')
    images = product.get('image', [])
    if isinstance(images, str):
        images = [images]
    if not images or not product.get('name') or not product.get('description'):
        raise ValueError('Incomplete product content')
    for image in images:
        public_url(image)
    return product, format(price, 'f'), images


def build(items, fetch=fetch_page, now=None):
    identities = [item['id'] for item in items]
    if len(set(identities)) != len(identities):
        raise ValueError('Expected unique offer IDs')
    if not RETAINED_IDS.issubset(identities):
        raise ValueError('The four retained offer IDs must remain in this feed')
    for field in ('sku', 'url'):
        values = [item[field] for item in items]
        if len(set(values)) != len(values):
            raise ValueError('Expected unique product ' + field)
    if any(item['category'] not in CATEGORIES for item in items):
        raise ValueError('Unexpected product category')
    root = ET.Element('yml_catalog', date=(now or datetime.now(timezone.utc)).isoformat(timespec='seconds'))
    shop = ET.SubElement(root, 'shop')
    for key, value in [('name', 'StekloRoll'), ('company', 'ИП Карцев Артём Александрович'), ('url', ORIGIN + '/')]:
        ET.SubElement(shop, key).text = value
    currencies = ET.SubElement(shop, 'currencies')
    ET.SubElement(currencies, 'currency', id='RUR', rate='1')
    categories = ET.SubElement(shop, 'categories')
    for category, (ident, name) in CATEGORIES.items():
        if any(item['category'] == category for item in items):
            ET.SubElement(categories, 'category', id=ident).text = name
    offers = ET.SubElement(shop, 'offers')
    for item in items:
        public_url(item['url'])
        product, price, images = product_from_page(item, fetch(item['url']))
        offer = ET.SubElement(offers, 'offer', id=item['id'])
        fields = [('name', product['name']), ('vendor', 'StekloRoll'),
                  ('vendorCode', item['sku']), ('url', item['url']), ('price', price),
                  ('currencyId', 'RUR'), ('categoryId', CATEGORIES[item['category']][0])]
        for key, value in fields:
            ET.SubElement(offer, key).text = value
        for image in images:
            ET.SubElement(offer, 'picture').text = image
        ET.SubElement(offer, 'description').text = product['description']
        ET.SubElement(offer, 'sales_notes').text = item.get('sales_notes', 'Предоплата; самовывоз; доставка по согласованию. Цена без монтажа.')
        for parameter in item.get('parameters', []):
            ET.SubElement(offer, 'param', name=parameter['title']).text = parameter['value']
        ET.SubElement(offer, 'param', name='is_checkout_enabled').text = 'false'
    ET.indent(root)
    return ET.ElementTree(root)


def verify_images(tree):
    def verify(url):
        with urlopen(Request(public_url(url), method='HEAD'), timeout=30) as response:
            if response.status != 200 or response.url != url or not response.headers.get('Content-Type', '').startswith('image/'):
                raise ValueError('Image is unavailable: ' + url)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(verify, sorted({image.text for image in tree.findall('.//picture')})))


def main():
    items = json.loads((ROOT / 'feed-products.json').read_text())
    started = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = dict(zip([item['url'] for item in items], pool.map(fetch_page, [item['url'] for item in items])))
    tree = build(items, fetch=pages.__getitem__, now=started)
    verify_images(tree)
    destination = ROOT / 'public/stekloroll.xml'
    temporary = destination.with_suffix('.xml.tmp')
    tree.write(temporary, encoding='utf-8', xml_declaration=True)
    os.replace(temporary, destination)
    print(f'Verified {len(items)} product identities, current prices and images; feed refreshed.')


if __name__ == '__main__':
    main()
