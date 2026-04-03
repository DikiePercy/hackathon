from fastapi import APIRouter, HTTPException, status

from app.schemas import Item, ItemCreate

api_router = APIRouter()

_items: list[Item] = []
_next_id = 1


@api_router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/items", response_model=list[Item], tags=["items"])
def list_items() -> list[Item]:
    return _items


@api_router.get("/items/{item_id}", response_model=Item, tags=["items"])
def get_item(item_id: int) -> Item:
    for item in _items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")


@api_router.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED, tags=["items"])
def create_item(payload: ItemCreate) -> Item:
    global _next_id

    item = Item(id=_next_id, **payload.model_dump())
    _items.append(item)
    _next_id += 1
    return item
