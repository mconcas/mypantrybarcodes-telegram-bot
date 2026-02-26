# Pantry Bot

A Telegram bot that tracks what's in your pantry. Scan grocery barcodes
when you come home, and scan them again when you use items up. Product
names are auto-detected via [Open Food Facts](https://world.openfoodfacts.org/).

## Features

- **Continuous barcode scanning** via an in-app camera scanner (Mini App) — supports EAN-13, Code 128, QR Code
- **Add & Remove modes** — toggle between stocking up and using items
- **Batch scanning** — scan multiple items in one session, review the queue, then send
- **Auto product lookup** — barcodes are resolved to product names via Open Food Facts
- **Review interface** — verify or correct auto-detected names (expect false positives!)
- **Multi-category lists** — Pantry, Fridge, Freezer, or create your own
- **Groups & private chats** — deep-links to private chat for scanning, pantry works everywhere
- **Timestamps** — every item records when it was added, useful for expiry tracking

## Stack

| Component | Technology |
|-----------|------------|
| Bot | Python 3.12, python-telegram-bot |
| Storage | OpenSearch 2.11 |
| Scanner webapp | Vue 3 + Vuetify 3 + html5-qrcode |
| Product lookup | Open Food Facts API (free, no key needed) |
| Hosting | Docker Compose (bot + OpenSearch), GitHub Pages (webapp) |

## Quick start

```bash
cp .env.example .env
# Edit .env and set TELEGRAM_BOT_TOKEN (from @BotFather)
docker compose up -d
```

The bot will connect to OpenSearch, create the indices, and start polling
for updates.

### Scanner webapp

The webapp is deployed automatically to GitHub Pages on push to `master`
(see `.github/workflows/deploy-webapp.yml`). Set `WEBAPP_URL` in `.env`
to the Pages URL.

To run locally:

```bash
cd webapp
npm install
npm run dev
```

## Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Show main menu |
| `/pantry` | View pantry items by category |
| `/categories` | Manage categories (add/delete) |
| `/review` | Review auto-detected product names |
| `/cancel` | Cancel current operation |

## How it works

1. **Come home from groceries** → open the scanner, set mode to **Add**
2. Scan all your items continuously — they queue up in the webapp
3. Hit **Send** → choose a category (Pantry / Fridge / Freezer)
4. The bot looks up each barcode on Open Food Facts and saves the items
5. **Use something up** → switch to **Remove** mode, scan, send
6. Use `/review` to verify any product names marked with ❓

## Project structure

```
├── bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # Entry point
│       ├── config.py            # Environment config
│       ├── handlers/
│       │   ├── start.py         # /start, menu navigation
│       │   ├── pantry.py        # Pantry CRUD + category view
│       │   ├── scan.py          # WebApp scan flow
│       │   ├── categories.py    # Category management
│       │   └── review.py        # Product name review
│       └── services/
│           ├── opensearch_client.py  # Data layer
│           └── product_lookup.py     # Open Food Facts API
├── webapp/                      # Vue Mini App (GitHub Pages)
│   ├── src/
│   │   ├── App.vue
│   │   └── components/
│   │       ├── ScanView.vue
│   │       ├── BarcodeScanner.vue
│   │       ├── ScanQueue.vue
│   │       └── ModeSelector.vue
│   └── vite.config.js
├── docker-compose.yml
└── .env.example
```

## License

MIT
