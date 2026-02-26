"""Product lookup via Open Food Facts API."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OFF_USER_AGENT = "PantryBot/1.0 (Telegram Bot; github.com/mconcas/mybarcodes-telegram-bot)"

# Fields we care about — keeps the response small
OFF_FIELDS = "product_name,brands,image_front_small_url,categories_tags,quantity"


async def lookup_barcode(barcode: str) -> dict | None:
    """Query Open Food Facts for a barcode.

    Returns a dict with ``product_name``, ``brand``, ``image_url``, and
    ``raw`` (the full product object), or *None* if not found or on error.
    """
    url = OFF_API_URL.format(barcode=barcode)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                url,
                params={"fields": OFF_FIELDS},
                headers={"User-Agent": OFF_USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.warning("Open Food Facts lookup failed for %s", barcode, exc_info=True)
        return None

    if data.get("status") != 1:
        logger.info("No Open Food Facts hit for barcode %s", barcode)
        return None

    product = data.get("product", {})
    name = product.get("product_name", "").strip()
    brand = product.get("brands", "").strip()
    image = product.get("image_front_small_url", "")

    if not name:
        return None

    display_name = f"{name} ({brand})" if brand else name

    return {
        "product_name": display_name,
        "brand": brand,
        "image_url": image,
        "raw": product,
    }
