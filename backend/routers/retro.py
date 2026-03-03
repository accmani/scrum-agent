from fastapi import APIRouter, HTTPException

from models import RetroItemCreate
import database

router = APIRouter(prefix="/api/retro", tags=["Retro"])


@router.get("")
async def list_retro():
    items = await database.list_retro_items()
    return {"items": items}


@router.post("", status_code=201)
async def add_retro_item(req: RetroItemCreate):
    return await database.add_retro_item(req.category, req.text)


@router.delete("/{item_id}", status_code=204)
async def remove_retro_item(item_id: str):
    deleted = await database.delete_retro_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
