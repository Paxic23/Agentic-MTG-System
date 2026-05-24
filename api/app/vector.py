import os
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from app.models import Card


QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "mtg_cards"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384


@lru_cache
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, timeout=60)


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    vector = model.encode(text)
    return vector.tolist()


def build_card_embedding_text(card: Card) -> str:
    colors = ", ".join(card.colors or [])
    color_identity = ", ".join(card.color_identity or [])
    keywords = ", ".join(card.keywords or [])

    return f"""
Name: {card.name}
Mana cost: {card.mana_cost or ""}
Mana value: {card.mana_value or ""}
Type: {card.type_line or ""}
Oracle text: {card.oracle_text or ""}
Colors: {colors}
Color identity: {color_identity}
Keywords: {keywords}
""".strip()


def ensure_collection(recreate: bool = False) -> None:
    client = get_qdrant_client()

    existing_collections = client.get_collections().collections
    exists = any(collection.name == COLLECTION_NAME for collection in existing_collections)

    if recreate and exists:
        client.delete_collection(collection_name=COLLECTION_NAME)
        exists = False

    if not exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )


def upsert_cards(cards: list[Card]) -> None:
    client = get_qdrant_client()

    points: list[PointStruct] = []

    for card in cards:
        embedding_text = build_card_embedding_text(card)
        vector = embed_text(embedding_text)

        points.append(
            PointStruct(
                id=card.id,
                vector=vector,
                payload={
                    "card_id": card.id,
                    "name": card.name,
                    "type_line": card.type_line,
                    "mana_value": card.mana_value,
                    "color_identity": card.color_identity or [],
                },
            )
        )

    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )


def semantic_search_cards(query: str, limit: int = 10):
    client = get_qdrant_client()
    query_vector = embed_text(query)

    result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )

    return result.points