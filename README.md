# Agentic MTG System

A local development project for building, storing, searching, pricing, and analyzing Magic: The Gathering decks.

The main AI feature is the **General Chat agent**. It can answer broad MTG questions, discuss your saved decks, analyze deck direction, help uncover useful cards, and suggest ideas to explore. Around that AI layer, the project also includes a normal card/deck database, semantic card search, Commander-focused deck tools, price refreshes, and a browser frontend.

This is a hobby/development system, not a production-ready web app. It currently has no authentication, no user accounts, and no production migration setup.

## What the project does

### Main AI feature: General Chat

The General Chat endpoint is the central agentic/LLM feature of the system.

It is intended for questions like:

- “What is this deck trying to do?”
- “What are the weak points in my Lathiel deck?”
- “What kind of cards should I look for next?”
- “Give me ideas for a Commander deck around this theme.”
- “Analyze these decks and compare their game plans.”

When requested, the chat endpoint can include deck context from the local database, so the AI can reason over saved decklists instead of only answering generic MTG questions.

### Other notable functionality

The rest of the app supports the AI/chat workflow and is useful on its own:

- Search MTG cards by name, text, color identity, and mana value.
- Run semantic card search through Qdrant vector search.
- Store cards and decks in PostgreSQL.
- Create, list, inspect, import, export, and modify decks.
- Mark and clear a Commander for Commander decks.
- Check basic Commander/deck-building rules.
- Generate deterministic deck analysis, diagnosis, and card suggestions.
- Refresh and store Scryfall card prices locally.
- Estimate deck prices from locally stored price data.
- Use a Vite/TypeScript frontend on top of the FastAPI backend.

### Note about deck coaching

Deck coaching is **not the main AI feature**. In the current setup, the deck coaching flow is mostly deterministic: it runs analysis, rules checks, diagnosis logic, semantic suggestions, and then builds a structured report.

There is an optional LLM enhancement path in the code, but it is disabled by default and should be treated as secondary. The main intended AI interaction is still **General Chat**.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Frontend:** Vite, TypeScript, CSS
- **Relational database:** PostgreSQL
- **Vector database:** Qdrant
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` by default
- **Card data:** MTGJSON `AtomicCards.json`
- **Price data:** Scryfall bulk/default card data
- **Containers:** Docker Compose
- **LLM integration:** currently intended for non-local/OpenAI-compatible use; local LLM support may require code/config changes

## Repository structure

The exact structure may change as the project develops, but the current project is broadly organized like this:

```text
.
├── api/
│   ├── app/
│   │   ├── main.py                    # FastAPI app setup, startup hooks, router registration
│   │   ├── db.py                      # SQLAlchemy engine/session setup
│   │   ├── models.py                  # Database models
│   │   ├── schemas.py                 # Pydantic request/response schemas
│   │   ├── ingest_atomic_cards.py     # Imports MTGJSON cards into PostgreSQL
│   │   ├── index_cards.py             # Builds/rebuilds Qdrant vector index
│   │   ├── vector.py                  # Embedding and Qdrant utilities
│   │   ├── routers/
│   │   │   ├── cards.py               # Card search and semantic search endpoints
│   │   │   ├── decks.py               # Deck CRUD, import/export, analysis, rules, suggestions
│   │   │   ├── prices.py              # Price status, refresh, card/deck price lookup
│   │   │   └── agent.py               # General Chat and deck-coach endpoints
│   │   ├── services/                  # Deterministic deck, theme, price, and business logic
│   │   ├── agents/                    # Deck-coach graph/tool orchestration
│   │   ├── llm/                       # LLM provider abstraction and prompts
│   │   └── core/                      # App settings/config
│   ├── .env.example                   # Runtime/LLM configuration template
│   └── Dockerfile
├── frontend/                          # Browser UI
├── data/                              # Local data mount; put AtomicCards.json here
├── docker-compose.yml                 # PostgreSQL + Qdrant + API + frontend
└── README.md
```

## Data sources

The project uses public MTG data sources:

- [MTGJSON](https://mtgjson.com/) for card data.
- [Scryfall API/card data](https://scryfall.com/docs/api/cards) for price-related card data.
- [Scryfall price FAQ](https://scryfall.com/docs/faqs/where-do-scryfall-prices-come-from-7) for context on where Scryfall prices come from.

For setup, the most important file is:

```text
AtomicCards.json
```

The ingestion script expects this file to be available inside the API container at:

```text
/data/AtomicCards.json
```

With the Docker setup, that means the file should be placed locally at:

```text
./data/AtomicCards.json
```

## Setup

These steps assume Docker Desktop is installed and running.

### 1. Clone the repository

```bash
git clone https://github.com/Paxic23/Agentic-MTG-System.git
cd Agentic-MTG-System
```

If you are working from the refactored branch:

```bash
git checkout Better-File-Structure
```

### 2. Add the card dataset

Create a local data folder:

```bash
mkdir -p data
```

Download MTGJSON `AtomicCards.json` and place it here:

```text
./data/AtomicCards.json
```

### 3. Configure environment variables

Copy the example environment file:

```bash
cp api/.env.example api/.env
```

On Windows PowerShell:

```powershell
Copy-Item api/.env.example api/.env
```

For a basic setup without LLM features, keep the provider disabled:

```env
LLM_PROVIDER=none
LLM_ENABLE_DECK_COACH=false
```

For the main AI functionality, configure a non-local/OpenAI-compatible provider in `api/.env`, for example:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your_api_key_here
LLM_TEMPERATURE=0.2
LLM_TIMEOUT_SECONDS=30
LLM_MAX_OUTPUT_TOKENS=900
LLM_ENABLE_DECK_COACH=false
```

For another OpenAI-compatible API, use:

```env
LLM_PROVIDER=openai_compatible
LLM_MODEL=your_model_name
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your_api_key_here
LLM_TEMPERATURE=0.2
LLM_TIMEOUT_SECONDS=30
LLM_MAX_OUTPUT_TOKENS=900
LLM_ENABLE_DECK_COACH=false
```

### Local LLM note

The code has some provider hooks for local/Ollama-style usage, but the current system should be treated as set up primarily for non-local AI providers. Running a local LLM agentically may require additional code/config changes, especially if the local model behaves differently from OpenAI-compatible chat completions.

### 4. Start the app stack

```bash
docker compose up --build
```

This starts the full local development stack:

| Service | Purpose | Default local URL |
|---|---|---|
| PostgreSQL | Stores cards, decks, deck cards, and price metadata | `localhost:5432` |
| Qdrant | Stores semantic card-search vectors | `localhost:6333` |
| API | FastAPI backend | `http://localhost:8000` |
| Frontend | Vite frontend | `http://localhost:5173` |

Useful pages:

- Frontend: `http://localhost:5173`
- API health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

### 5. Fill PostgreSQL with card data

After the containers are running and `AtomicCards.json` is in `./data`, run:

```bash
docker compose exec api python -m app.ingest_atomic_cards
```

This imports card records into PostgreSQL.

### 6. Build the vector database

After the card database is populated, build the Qdrant index:

```bash
docker compose exec api python -m app.index_cards
```

This creates embeddings for cards and stores them in Qdrant. Re-run this when you change the embedding model, vector size, collection name, or card text representation.

### 7. Refresh price data

Prices are stored locally and can be refreshed from Scryfall bulk data:

```bash
curl -X POST "http://localhost:8000/prices/refresh?force=true"
```

On Windows PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/prices/refresh?force=true"
```

The project also includes startup logic for price refreshes, gated by a refresh interval so restarts do not constantly hit Scryfall.

### 8. Verify the setup

Health check:

```bash
curl http://localhost:8000/health
```

Normal card search:

```bash
curl "http://localhost:8000/cards?name=sol%20ring&limit=5"
```

Semantic search, after Qdrant has been indexed:

```bash
curl -X POST "http://localhost:8000/cards/semantic-search" \
  -H "Content-Type: application/json" \
  -d '{"query":"cheap ramp for commander","limit":10}'
```

General Chat, after an LLM provider is configured:

```bash
curl -X POST "http://localhost:8000/agent/general-chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What weaknesses should I look for in my Commander decks?"}
    ],
    "include_deck_context": true,
    "deck_ids": []
  }'
```

## Things you can customize

### General Chat AI behavior

Relevant files:

```text
api/app/routers/agent.py
api/app/llm/
api/app/llm/prompts/general_chat.py
api/app/core/config.py
```

Customize these if you want to change:

- Which provider/model is used.
- The general chat prompt.
- How deck context is included.
- How many decks are passed into context.
- Temperature, timeout, and max-output settings.
- How strongly the AI is guided toward analytics, card discovery, deck comparison, or general MTG help.

### LLM provider setup

Relevant files:

```text
api/.env.example
api/app/core/config.py
api/app/llm/factory.py
```

Current practical path:

- Use `LLM_PROVIDER=openai` for OpenAI.
- Use `LLM_PROVIDER=openai_compatible` for a non-local provider with an OpenAI-compatible API.
- Treat local LLM/Ollama use as experimental until the system is adjusted and tested for it.

### Deck analysis, diagnosis, and suggestions

Relevant files:

```text
api/app/services/deck_service.py
api/app/agents/
```

Customize these if you want to change:

- Role detection such as ramp, card draw, sacrifice synergy, graveyard synergy, removal, and win conditions.
- Commander thresholds for lands, ramp, card draw, removal, and board wipes.
- How strongly minor synergies should be weighted.
- How card suggestions are generated from the deck’s current themes.
- Commander legality and singleton checks.
- The structured deck-coach report.

This is also where you would improve cases where the system overstates small themes, such as tagging a deck as “graveyard synergy” or “sacrifice synergy” when those elements are only barely present.

### Card ingestion

Relevant file:

```text
api/app/ingest_atomic_cards.py
```

Customize this if you want to change:

- The input path for `AtomicCards.json`.
- Which MTGJSON fields are stored locally.
- How duplicate names or alternate faces are handled.
- Whether ingestion is limited for testing.

### Semantic search / vector database

Relevant files:

```text
api/app/vector.py
api/app/index_cards.py
```

Customize this if you want to change:

- Qdrant URL.
- Qdrant collection name.
- Embedding model.
- Vector size.
- What text is embedded for each card.
- Indexing batch size.

If you change the embedding model, make sure the configured vector size matches the model output dimension, then rebuild the Qdrant collection/index.

### Price behavior

Relevant files:

```text
api/app/services/price_service.py
api/app/core/config.py
```

Customize this if you want to change:

- Whether prices refresh on startup.
- Refresh interval.
- Scryfall bulk data type.
- Which price fields are stored.
- Whether deck pricing prefers USD, EUR, TIX, foil, or other values.

### Frontend behavior

Relevant folder:

```text
frontend/
```

Customize this if you want to change:

- Layout and styling.
- Deck display.
- Commander highlighting.
- Commander `X/100` card count display.
- Right-side panel behavior.
- Search result presentation.
- API calls from the browser.

### Docker/service configuration

Relevant file:

```text
docker-compose.yml
```

Customize this if you want to change:

- Exposed ports.
- PostgreSQL credentials/database name.
- Mounted volumes.
- Frontend API URL.
- Container names.
- Development commands.

## API endpoints

The backend is a FastAPI app. The interactive documentation is available at:

```text
http://localhost:8000/docs
```

### Health

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Basic API health check. |

### Cards

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/cards` | Search cards with ordinary filters such as `name`, `text`, `color`, `max_mana_value`, and `limit`. |
| `GET` | `/cards/{card_id}` | Fetch one card by database ID. |
| `POST` | `/cards/semantic-search` | Search cards semantically through Qdrant embeddings. |

Example semantic-search body:

```json
{
  "query": "lifegain payoff for commander",
  "limit": 10,
  "color": "W",
  "max_mana_value": 5
}
```

### Decks

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/decks` | Create a new deck. |
| `GET` | `/decks` | List decks. |
| `GET` | `/decks/{deck_id}` | Get one deck with its cards. |
| `POST` | `/decks/{deck_id}/cards` | Add a card to a deck, or increment it if already present. |
| `DELETE` | `/decks/{deck_id}/cards/{card_id}` | Remove a card from a deck. |
| `GET` | `/decks/{deck_id}/analysis` | Get deck-level statistics such as card count, land count, mana curve, type counts, and colors. |
| `POST` | `/decks/{deck_id}/suggestions` | Generate deterministic/vector-based card suggestions for a deck. |
| `POST` | `/decks/{deck_id}/import` | Import a text decklist into an existing deck. |
| `GET` | `/decks/{deck_id}/export` | Export a decklist as text. |
| `PATCH` | `/decks/{deck_id}/cards/{card_id}/commander` | Mark a deck card as the commander. |
| `DELETE` | `/decks/{deck_id}/commander` | Clear the current commander. |
| `GET` | `/decks/{deck_id}/rules-check` | Check basic deck/Commander rules. |
| `GET` | `/decks/{deck_id}/diagnosis` | Get a deterministic deck diagnosis. |

### Prices

All price endpoints are under `/prices`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/prices/status` | Check price-refresh status and metadata. |
| `POST` | `/prices/refresh` | Refresh local card prices from Scryfall bulk data. Supports `force=true`. |
| `GET` | `/prices/cards/{card_id}` | Get price data for one card by database ID. |
| `GET` | `/prices/cards` | Search card prices by `name` with optional `limit`. |
| `POST` | `/prices/cards/search` | Search prices for multiple card names or IDs in one request. |
| `GET` | `/prices/decks/{deck_id}` | Estimate a deck price. Supports a `price` query value such as `usd`, `eur`, or `tix`. |

### Agent / AI

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/agent/general-chat` | Main LLM-powered chat endpoint. Can include deck context for deck analysis, broad MTG questions, card discovery, and strategy discussion. |
| `POST` | `/agent/deck-coach` | Structured deck-coach report. Primarily deterministic; optional LLM enhancement may be enabled separately. |

Example General Chat body:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Analyze my current Commander deck and suggest what type of cards I should search for next."
    }
  ],
  "include_deck_context": true,
  "deck_ids": [1]
}
```

If `deck_ids` is empty and `include_deck_context` is true, the endpoint may use the available saved decks as context.

## Helpers / reminders

These commands are not all required for first setup, but they are useful during development.

### Docker basics

```bash
# Start everything and rebuild images
docker compose up --build

# Start everything in the background
docker compose up --build -d

# Show running services
docker compose ps

# Stop containers, keeping database/vector volumes
docker compose down

# Stop containers and delete database/vector volumes
docker compose down -v
```

Warning: `docker compose down -v` deletes the PostgreSQL and Qdrant volumes. After that, you need to re-run card ingestion, vector indexing, and price refresh.

### Logs

```bash
# Watch all logs
docker compose logs -f

# Watch API logs only
docker compose logs -f api

# Watch frontend logs only
docker compose logs -f frontend

# Watch database logs only
docker compose logs -f db

# Watch Qdrant logs only
docker compose logs -f qdrant
```

### Rebuild/restart specific services

```bash
# Rebuild only the API image
docker compose build api

# Restart only the API container
docker compose restart api

# Restart only the frontend container
docker compose restart frontend
```

### Run commands inside containers

```bash
# Open a shell inside the API container
docker compose exec api bash

# Import cards
docker compose exec api python -m app.ingest_atomic_cards

# Build/rebuild Qdrant card index
docker compose exec api python -m app.index_cards
```

### Quick API checks

```bash
# API health
curl http://localhost:8000/health

# API docs are in the browser
# http://localhost:8000/docs

# Check Qdrant collections
curl http://localhost:6333/collections

# Search for a card
curl "http://localhost:8000/cards?name=sol%20ring&limit=5"

# Force price refresh
curl -X POST "http://localhost:8000/prices/refresh?force=true"
```

PowerShell equivalents:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:6333/collections"
Invoke-RestMethod -Uri "http://localhost:8000/cards?name=sol%20ring&limit=5"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/prices/refresh?force=true"
```

### When things seem stale

```bash
# Restart API after backend code/config changes
docker compose restart api

# Restart frontend after frontend dependency/config weirdness
docker compose restart frontend

# Rebuild after changing requirements.txt or Dockerfile
docker compose up --build

# Re-index after changing embeddings/vector code
docker compose exec api python -m app.index_cards
```

## Typical first-run checklist

1. Clone the repository.
2. Check out the intended branch.
3. Put `AtomicCards.json` in `./data/AtomicCards.json`.
4. Copy `api/.env.example` to `api/.env`.
5. Configure the LLM provider if you want General Chat.
6. Start services with `docker compose up --build`.
7. Run `docker compose exec api python -m app.ingest_atomic_cards`.
8. Run `docker compose exec api python -m app.index_cards`.
9. Run `POST /prices/refresh?force=true`.
10. Open the frontend at `http://localhost:5173` or the API docs at `http://localhost:8000/docs`.

## Troubleshooting

### `AtomicCards.json` is missing

Make sure the file exists locally at:

```text
./data/AtomicCards.json
```

The API container sees that file as:

```text
/data/AtomicCards.json
```

### Card search works, but semantic search fails

This usually means PostgreSQL has been filled, but Qdrant has not been indexed yet.

Run:

```bash
docker compose exec api python -m app.index_cards
```

Also check Qdrant:

```bash
curl http://localhost:6333/collections
```

### General Chat says it is disabled

Check `api/.env`.

This disables the LLM:

```env
LLM_PROVIDER=none
```

To enable General Chat, configure a provider and model, then restart the API:

```bash
docker compose restart api
```

### Local LLM does not work

That is expected to need more work. The current setup should be treated as primarily configured for non-local/OpenAI-compatible AI providers. Local LLM use may require adjustments to provider configuration, model behavior, request formatting, timeout settings, and possibly the agent/prompt layer.

### Prices are missing

Run a manual refresh:

```bash
curl -X POST "http://localhost:8000/prices/refresh?force=true"
```

Some cards or printings may still have missing prices depending on the Scryfall data available.

### Deck themes look overstated

Theme detection currently uses simple heuristics over card text. If a card mentions “graveyard” or “sacrifice,” the system may count that as a theme even when it is not central to the deck.

The relevant logic lives in the deck service, especially role/theme detection and diagnosis thresholds. Improving this weighting is one of the most useful next development steps.

## Notes

- PostgreSQL is the source of truth for imported cards, saved decks, deck cards, and stored prices.
- Qdrant is used for semantic search, not as the primary card database.
- General Chat is the main AI interface.
- Deck coaching is primarily deterministic unless optional LLM enhancement is explicitly enabled.
- Price values are imported snapshots, not guaranteed real-time market prices.
- For serious schema changes, adding Alembic or another migration tool would be a good future improvement.
