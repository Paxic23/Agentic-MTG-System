from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, SessionLocal, engine
from app.routers.agent import router as agent_router
from app.routers.cards import router as cards_router
from app.routers.decks import router as decks_router
from app.routers.prices import router as prices_router
from app.services.price_service import ensure_card_price_schema, maybe_refresh_card_prices_on_startup

app = FastAPI(title="MTG Deck Lab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_card_price_schema(db)
    finally:
        db.close()
    maybe_refresh_card_prices_on_startup()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(cards_router)
app.include_router(decks_router)
app.include_router(agent_router)
app.include_router(prices_router)
