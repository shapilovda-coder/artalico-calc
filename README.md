# StekloRoll product feed

Publishes the existing Yandex goods feed at https://stekloroll-feed.onrender.com/stekloroll.xml.
Render serves `public/` from `main` automatically; the repository name is historical.

`feed-products.json` preserves the four existing offer identities and canonical URLs and adds the two owner-approved compact 900×1000 mm shutter variants. Their prices exclude delivery and installation.
New size variants may be added as separate entries with their own stable ID, SKU and canonical URL; the four retained offers must remain. New entries require confirmed manufacturing sizes, prices and sale conditions on live product pages before this repository can publish them.
`scripts/refresh_feed.py` verifies the live Product JSON-LD, canonical URL, SKU, positive price and accessible images before atomically updating the XML. Failures retain the previous file.
The GitHub workflow validates changes and refreshes the feed daily at 04:15 UTC (07:15 Moscow); verified commits trigger the existing Render auto-deploy.

Run `python3 -m unittest discover -s tests -v`, then `python3 scripts/refresh_feed.py`.
Never refresh only the timestamp of unverified old product data. Changes to assortment or sale conditions require the owner's instruction.
Yandex processing and actual impressions must be checked separately after publication.
