# Agentic MTG System

A local development project for building, storing, searching, pricing, and analyzing Magic: The Gathering decks.

The main AI feature is the **General Chat agent**. It runs a dynamic agentic loop: the LLM decides which tools to call, executes them against the local database, and keeps going until it has enough information to answer. It can look up your decks, search cards by name or concept, find upgrade suggestions, and score a deck's power level and Commander bracket, all driven by the conversation instead of hardcoded triggers. Around that AI layer, the project also includes a normal card/deck database, semantic card search, Commander-focused deck tools, price refreshes, and a browser frontend.

This is a hobby/development system, not a production-ready web app. It currently has no authentication, no user accounts, and no production migration setup.

## What the project does

### Main AI feature: General Chat

The General Chat endpoint is the central agentic/LLM feature of the system.

It uses a dynamic tool-calling loop: the LLM reads the conversation, decides which tool to call (if any), gets the result, and repeats until it is ready to respond. That means it can chain multiple lookups in a single reply, for example listing your decks, fetching the full card list of one of them, and then finding upgrades, all without you specifying those steps.

**Available tools:**

| Tool | What it does |
|---|---|
| `list_decks` | Lists all saved decks with id, name, and format. |
| `get_deck_details` | Fetches the full card list and stats for a specific deck. |
| `search_cards` | Filters the card database by name, oracle text, color identity, and mana value. |
| `search_cards_semantic` | AI-powered semantic search via Qdrant, best for conceptual queries like "cheap green ramp" or "sacrifice outlets in black". |
| `find_upgrades` | Suggests cards to add to a specific deck based on its themes and a stated goal. |
| `get_power_level` | Scores a Commander deck on [edhpowerlevel.com](https://edhpowerlevel.com): power level, bracket, game changers, combos, mana odds, and optionally per-card impact. |

It is intended for questions like:

- "What is this deck trying to do?"
- "What are the weak points in my Lathiel deck?"
- "What kind of cards should I look for next?"
- "Give me ideas for a Commander deck around this theme."
- "Analyze these decks and compare their game plans."
- "Find me some cheap blue card draw spells."
- "What bracket is my Atraxa deck, and which game changers is it running?"

The `include_deck_context` flag preloads a summary of your saved decks into the system prompt. The LLM can then call `get_deck_details` for any deck it wants to inspect in full.

### Other notable functionality

The rest of the app supports the AI/chat workflow and is useful on its own:

- Search MTG cards by name, text, color identity, and mana value.
- Run semantic card search through Qdrant vector search, optionally filtered by card type (e.g. only creatures, or no lands).
- Store cards and decks in PostgreSQL.
- Create, list, inspect, import, export, and modify decks.
- Resolve unknown names during decklist import through Scryfall (alternate/Universes Beyond printed names and minor typos).
- Score Commander decks for power level and bracket via edhpowerlevel.com (headless browser, cached locally).
- Mark and clear a Commander for Commander decks.
- Check basic Commander/deck-building rules.
- Generate deterministic deck analysis, diagnosis, and card suggestions.
- Refresh and store Scryfall card prices locally.
- Estimate deck prices from locally stored price data.
- Use a Vite/TypeScript frontend on top of the FastAPI backend.

### Note about deck coaching

Deck coaching is **not the main AI feature**. In the current setup, the deck coaching flow is mostly deterministic: it runs analysis, rules checks, diagnosis logic, power-level scoring, semantic suggestions, and then builds a structured report.

There is an optional LLM enhancement path in the code, but it is disabled by default and should be treated as secondary. The main intended AI interaction is still **General Chat**.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Agent orchestration:** LangGraph (state graphs for both the General Chat loop and the deck-coach pipeline)
- **Frontend:** Vite, TypeScript, CSS
- **Relational database:** PostgreSQL
- **Vector database:** Qdrant
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` by default
- **Card data:** MTGJSON `AtomicCards.json`
- **Price data:** Scryfall bulk/default card data
- **Power level data:** edhpowerlevel.com, scraped with Playwright + headless Chromium
- **Containers:** Docker Compose
- **LLM integration:** OpenAI and OpenAI-compatible APIs; requires tool/function calling support

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
│   │   ├── services/                  # Deterministic deck, theme, price, power-level, and business logic
│   │   │   ├── edh_powerlevel_service.py  # Playwright scraper for edhpowerlevel.com (also a CLI)
│   │   │   └── power_score_service.py     # Turns deck rows into a decklist and scores it
│   │   ├── agents/                    # General Chat agentic loop and deck-coach graph/tool orchestration
│   │   │   └── tool_log.py            # Trace log of agent runs and tool calls
│   │   ├── llm/                       # LLM provider abstraction, tool-calling interface, and prompts
│   │   └── core/                      # App settings/config
│   ├── .env.example                   # Runtime/LLM configuration template
│   └── Dockerfile
├── frontend/                          # Browser UI
├── data/                              # Local data mount (gitignored): AtomicCards.json, power-level cache, agent tool log
├── docker-compose.yml                 # PostgreSQL + Qdrant + API + frontend
└── README.md
```

## Data sources

The project uses public MTG data sources:

- [MTGJSON](https://mtgjson.com/) for card data.
- [Scryfall API/card data](https://scryfall.com/docs/api/cards) for price-related card data.
- [Scryfall price FAQ](https://scryfall.com/docs/faqs/where-do-scryfall-prices-come-from-7) for context on where Scryfall prices come from.
- [Scryfall `/cards/named`](https://scryfall.com/docs/api/cards/named) for resolving unknown card names during decklist import (rate-limited to ~10 requests/second, results cached in memory).
- [edhpowerlevel.com](https://edhpowerlevel.com) for Commander power level and bracket scoring. The site does all scoring client-side, so the API drives a headless Chromium to read the results.

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
LLM_MAX_OUTPUT_TOKENS=2000
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
LLM_MAX_OUTPUT_TOKENS=2000
LLM_ENABLE_DECK_COACH=false
```

### Local LLM note

The code has some provider hooks for local/Ollama-style usage, but the current system should be treated as set up primarily for non-local AI providers. Running a local LLM agentically may require additional code/config changes, especially if the local model behaves differently from OpenAI-compatible chat completions.

### 4. Start the app stack

```bash
docker compose up --build
```

The first build takes a while longer than you might expect: the API image installs Playwright's headless Chromium and its system libraries (used for power-level scoring). If you pulled these changes into an existing checkout, rebuild with `--build` so the browser gets installed.

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
  -d '{"query":"cheap ramp for commander","limit":10,"exclude_types":["Land"]}'
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
api/app/agents/general_chat.py
api/app/agents/graphs/general_chat_graph.py
api/app/llm/client.py
api/app/core/config.py
```

Customize these if you want to change:

- Which provider/model is used.
- The system prompt that guides the LLM's tool-calling behavior (`initialize_node` in `general_chat_graph.py`).
- Which tools are available and what they do (`CHAT_TOOLS` and `_execute_tool` in `general_chat_graph.py`).
- How many tool-call iterations the loop allows before forcing a final response (`MAX_ITERATIONS`).
- How deck context is preloaded into the system prompt.
- Temperature, timeout, and max-output settings.

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
- How card suggestions are generated from the deck's current themes.
- Commander legality and singleton checks.
- The structured deck-coach report.

This is also where you would improve cases where the system overstates small themes, such as tagging a deck as "graveyard synergy" or "sacrifice synergy" when those elements are only barely present.

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

- Which card types the type filter recognizes (`CARD_TYPES`).

If you change the embedding model, make sure the configured vector size matches the model output dimension, then rebuild the Qdrant collection/index.

### Power level scoring

Relevant files:

```text
api/app/services/edh_powerlevel_service.py
api/app/services/power_score_service.py
```

Power level comes from [edhpowerlevel.com](https://edhpowerlevel.com). The site computes everything in the browser, so the service encodes the decklist into the site's `?d=` URL, loads it in headless Chromium, waits until the numbers stop changing, and parses the result. Results are cached on disk, keyed by the normalized decklist.

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `EDHPL_CACHE_DIR` | `data/edhpowerlevel_cache` | Where scored decklists are cached. |
| `EDHPL_CACHE_TTL_SECONDS` | `604800` (7 days) | How long a cached score stays valid. |
| `EDHPL_MAX_CONCURRENT_PAGES` | `2` | Parallel page loads against the site. |

The scraper can also be run on its own for debugging (from the `api` directory, or inside the API container):

```bash
python -m app.services.edh_powerlevel_service deck.txt
python -m app.services.edh_powerlevel_service deck.txt --no-cache --headful --cards
python -m app.services.edh_powerlevel_service deck.txt --url-only
```

The decklist should be in Moxfield export format with the commander(s) in a trailing `COMMANDER` section.

This depends on the third-party site's page layout. If the site changes, scoring fails gracefully (the deck coach and chat report the error instead of crashing), but the parsing in `edh_powerlevel_service.py` will need updating.

### Agent tool log

Relevant file:

```text
api/app/agents/tool_log.py
```

Every General Chat / Deck Coach run and every tool call (with its arguments) is printed to stdout and appended to `data/agent_tool_log.txt` (`/data/agent_tool_log.txt` in Docker). Set `AGENT_TOOL_LOG_FILE` to change the path, or to an empty string to disable file logging. Useful for seeing what the agent actually decided to do:

```bash
docker compose logs -f api
```

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
  "max_mana_value": 5,
  "include_types": ["Creature", "Enchantment"],
  "exclude_types": ["Land"]
}
```

`include_types` keeps cards that have **any** of the listed types; `exclude_types` drops cards that have any of them (so excluding `Creature` also drops artifact creatures). Recognized types are Artifact, Battle, Creature, Enchantment, Instant, Land, Planeswalker, and Sorcery; anything else is ignored. The filter runs inside Qdrant, so excluding a common type doesn't shrink the result pool.

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

#### Decklist import

Example import body:

```json
{
  "decklist": "1 Sol Ring\n1 Arcane Signet\n1 Golbez, Clad in Darkness",
  "replace_existing": false,
  "assign_first_card_as_commander": true
}
```

- Names not found in the local database are looked up on Scryfall (exact, then fuzzy) and mapped to their Oracle name. This covers Universes Beyond / Secret Lair printed names (e.g. "Golbez, Clad in Darkness" → "Syr Konrad, the Grim") and small typos. Those entries come back with a `resolved_from` field, and the response includes a `resolved_count`.
- `assign_first_card_as_commander` marks the first card as commander for Commander decks. Moxfield exports are still detected automatically.

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
| `POST` | `/agent/general-chat` | Main LLM-powered chat endpoint with dynamic tool-calling loop. |
| `POST` | `/agent/deck-coach` | Structured deck-coach report. Primarily deterministic with optional LLM enhancement. |

#### General Chat

The LLM reads the conversation, calls tools as needed, and loops until it has enough to respond. Tools available to it:

| Tool | Triggered when |
|---|---|
| `list_decks` | User asks about their collection or which decks they have. |
| `get_deck_details` | User references a specific deck by name or id. |
| `search_cards` | User wants to look up cards by name, text, or filter. |
| `search_cards_semantic` | User describes cards conceptually ("cheap green ramp", "sacrifice outlets"). |
| `find_upgrades` | User asks what to add to a deck or how to improve it. |
| `get_power_level` | User asks how strong a deck is, what bracket it belongs in, or about game changers/combos. Per-card impact scores are only included when asked for. |

Example request body:

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

If `deck_ids` is empty and `include_deck_context` is `true`, all saved decks are preloaded into the system prompt. The agent can then call `get_deck_details` for any deck it wants to inspect in full.

#### Deck Coach

Runs a fixed LangGraph pipeline, not a dynamic loop. Each step runs in order:

1. **Load deck**: fetches the deck and all its cards from the database.
2. **Analyze**: mana curve, card type distribution, color identity breakdown.
3. **Rules check**: format legality, commander color identity, singleton violations, card count.
4. **Diagnose**: detects weaknesses like low ramp, low card draw, insufficient removal, high mana curve, etc.
5. **Score power level**: power level, bracket, game changers, combos, and mana screw/flood odds from edhpowerlevel.com. If scoring fails, the report notes it and the pipeline continues.
6. **Choose goal**: resolves the coaching focus from the `goal` field (or uses a default).
7. **Suggest cards**: semantic vector search for cards that fit the deck's themes and goal.
8. **Build report**: assembles a deterministic Markdown report from all of the above, including a "Power Level" section.
9. **Enhance with LLM** *(optional, off by default)*: rewrites the report using the configured LLM if `LLM_ENABLE_DECK_COACH=true`.

The response also includes the raw `power_score` object alongside the other tool payloads.

Example request body:

```json
{
  "deck_id": 1,
  "goal": "more ramp and card draw",
  "suggestion_limit": 5,
  "max_mana_value": 4,
  "include_tool_payloads": true,
  "ignore_categories": []
}
```

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

That is expected to need more work. The current setup should be treated as primarily configured for non-local/OpenAI-compatible AI providers. Local LLM use may require adjustments to provider configuration, model behavior, request formatting, and timeout settings.

In particular, the General Chat agent relies on **tool/function calling** support in the model. Many local LLMs either do not support this or behave inconsistently with the OpenAI tool-calling format. If your local model does not support tool calling, the agentic loop will not work as intended.

### Prices are missing

Run a manual refresh:

```bash
curl -X POST "http://localhost:8000/prices/refresh?force=true"
```

Some cards or printings may still have missing prices depending on the Scryfall data available.

### Power level is unavailable

The deck coach report shows "Could not get a power level from edhpowerlevel.com: ..." or the chat agent says it couldn't score the deck. Common causes:

- **Chromium is missing.** The API image was built before Playwright was added. Rebuild with `docker compose up --build`.
- **The site is down or slow.** Page loads time out after 45 seconds. Try again later, or run the CLI with `--headful` (outside Docker) to watch what happens.
- **The site changed its layout.** The parser in `edh_powerlevel_service.py` needs updating.
- **The deck has no commander set.** The score will be less meaningful; mark a commander first.

The first score for a decklist takes several seconds. Repeat calls are served from `data/edhpowerlevel_cache` until the cache expires or the decklist changes.

### Imported card names don't match

Unknown names are resolved through Scryfall. If Scryfall can't be reached, those cards are reported as unmatched instead. Re-import once you're back online. Network failures aren't cached, so retrying works.

### Deck themes look overstated

Theme detection currently uses simple heuristics over card text. If a card mentions "graveyard" or "sacrifice," the system may count that as a theme even when it is not central to the deck.

The relevant logic lives in the deck service, especially role/theme detection and diagnosis thresholds. Improving this weighting is one of the most useful next development steps.

## Notes

- PostgreSQL is the source of truth for imported cards, saved decks, deck cards, and stored prices.
- Qdrant is used for semantic search, not as the primary card database.
- General Chat is the main AI interface.
- Deck coaching is primarily deterministic unless optional LLM enhancement is explicitly enabled.
- Price values are imported snapshots, not guaranteed real-time market prices.
- Power level and bracket come from a third-party site (edhpowerlevel.com) and depend on its scoring and page layout.
- For serious schema changes, adding Alembic or another migration tool would be a good future improvement.
