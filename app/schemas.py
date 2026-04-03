from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class Item(ItemCreate):
    id: int
