# StekloRoll product feed

This repository's historical name is artalico-calc, but its current Render service is stekloroll-feed.
- Public feed: https://stekloroll-feed.onrender.com/stekloroll.xml.
- Render service: srv-d7lrhq1kh4rs73ahrpvg, confirmed workspace tea-d4ljeqchg0os73baqu9g.
- Main branch auto-deploys public/ to the existing Render static site. Do not create another storefront or change its URL.
- Keep the four retained offer IDs in feed-products.json. Do not restore the six excluded products.
- Refresh names, prices and images from the canonical product pages. Fail without overwriting the last good XML when identity, price, URL or image validation fails.
- YML uses RUR; Schema.org source pages use RUB. Do not confuse the two formats.
- Run python3 -m unittest discover -s tests -v and python3 scripts/refresh_feed.py before publishing changes.
- Before claiming completion, confirm Render deployed the exact commit and the public XML contains four offers with a current timezone-qualified timestamp.
- A successful deploy does not prove Yandex accepted or displayed the offers; verify those separately in the merchant account.
