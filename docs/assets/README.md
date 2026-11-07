# README visual assets

These images document the running local demo. They are not production evidence.

## Screenshots

- Captured on 2026-11-07 from the Next.js app using Playwright, at 1440 × 960 desktop and
  390 × 844 mobile viewports. The Auto Router card is an element screenshot.
- The UI used an isolated, newly migrated SQLite database with the repository's demo seed.
  Browser API requests were forwarded to a separate local API process using that database;
  the existing development database was not used.
- One sample Chat request was sent to the seeded Mock inference backend. Displayed prices,
  balances, model/replica counts, and ledger metrics are demo values, not business results.
- No real GPU, customer account, private endpoint, usable API key, or real payment appears.
- English and Chinese screenshots share the same demo data; seeded data fields may remain Chinese.
- JPEG assets are direct browser captures. No AI-generated UI or fabricated metric overlays are used.

## Diagrams

`product-flow.svg` explains the two product paths and their shared state.
`architecture.svg` separates the control plane, local demo defaults, production topology,
and external adapter boundaries. Both are hand-authored SVGs using the product's visual tokens.

To refresh the images, start a new isolated demo database, use only Mock providers, wait for data
to load, capture the same views in both locales, and inspect the captures for sensitive data.
Store selected public images here; leave raw browser output under the ignored `output/` directory.
