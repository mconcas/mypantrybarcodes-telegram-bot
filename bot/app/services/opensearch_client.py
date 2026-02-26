"""OpenSearch client for pantry item storage."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from opensearchpy import OpenSearch, NotFoundError

logger = logging.getLogger(__name__)

# ── Index definitions ────────────────────────────────────────────────

ITEMS_INDEX = "pantry_items"

ITEMS_INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "owner_id": {"type": "long"},
            "barcode": {"type": "keyword"},
            "product_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "category": {"type": "keyword"},
            "quantity": {"type": "integer"},
            "added_at": {"type": "date"},
            "expiry_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
            "product_info": {"type": "object", "enabled": False},
            "verified": {"type": "boolean"},
        }
    },
}

CATEGORIES_INDEX = "pantry_categories"

CATEGORIES_INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "owner_id": {"type": "long"},
            "name": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    },
}

# Cache product lookups so repeated scans of the same barcode are instant
PRODUCTS_CACHE_INDEX = "pantry_product_cache"

PRODUCTS_CACHE_INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "barcode": {"type": "keyword"},
            "product_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "brand": {"type": "keyword"},
            "image_url": {"type": "keyword", "index": False},
            "raw": {"type": "object", "enabled": False},
            "fetched_at": {"type": "date"},
        }
    },
}


class OpenSearchClient:
    """Thin wrapper around the OpenSearch Python client for pantry management."""

    def __init__(self, host: str, port: int) -> None:
        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=30,
        )

    # ------------------------------------------------------------------
    # Cluster / index management
    # ------------------------------------------------------------------

    def wait_for_cluster(self, retries: int = 30, delay: float = 2.0) -> None:
        """Block until the cluster is reachable."""
        for attempt in range(retries):
            try:
                info = self.client.info()
                logger.info("Connected to OpenSearch %s", info["version"]["number"])
                return
            except Exception:
                logger.warning(
                    "OpenSearch not ready (attempt %d/%d), retrying in %.0fs …",
                    attempt + 1,
                    retries,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("Could not connect to OpenSearch")

    def init_indices(self) -> None:
        """Create all required indices if they do not exist."""
        for name, body in [
            (ITEMS_INDEX, ITEMS_INDEX_BODY),
            (CATEGORIES_INDEX, CATEGORIES_INDEX_BODY),
            (PRODUCTS_CACHE_INDEX, PRODUCTS_CACHE_INDEX_BODY),
        ]:
            if not self.client.indices.exists(name):
                self.client.indices.create(name, body=body)
                logger.info("Created index '%s'", name)
            else:
                logger.info("Index '%s' already exists", name)

    # ------------------------------------------------------------------
    # Pantry items CRUD
    # ------------------------------------------------------------------

    def add_item(
        self,
        owner_id: int,
        barcode: str,
        product_name: str,
        category: str,
        quantity: int = 1,
        expiry_date: str | None = None,
        product_info: dict | None = None,
        verified: bool = False,
    ) -> str:
        """Add a pantry item, return its document id."""
        doc: dict = {
            "owner_id": owner_id,
            "barcode": barcode,
            "product_name": product_name,
            "category": category,
            "quantity": quantity,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "verified": verified,
        }
        if expiry_date:
            doc["expiry_date"] = expiry_date
        if product_info:
            doc["product_info"] = product_info
        resp = self.client.index(index=ITEMS_INDEX, body=doc, refresh="wait_for")
        return resp["_id"]

    def get_items(
        self,
        owner_id: int,
        category: str | None = None,
        size: int = 200,
    ) -> list[dict]:
        """Return pantry items for *owner_id*, optionally filtered by category."""
        musts: list[dict] = [{"term": {"owner_id": owner_id}}]
        if category:
            musts.append({"term": {"category": category}})
        body = {
            "query": {"bool": {"must": musts}},
            "sort": [{"added_at": {"order": "desc"}}],
            "size": size,
        }
        resp = self.client.search(index=ITEMS_INDEX, body=body)
        return [{"id": h["_id"], **h["_source"]} for h in resp["hits"]["hits"]]

    def get_item(self, item_id: str) -> dict | None:
        """Fetch a single item by id."""
        try:
            resp = self.client.get(index=ITEMS_INDEX, id=item_id)
            return {"id": resp["_id"], **resp["_source"]}
        except NotFoundError:
            return None

    def find_items_by_barcode(
        self, owner_id: int, barcode: str, category: str | None = None
    ) -> list[dict]:
        """Find items matching a barcode for an owner."""
        musts: list[dict] = [
            {"term": {"owner_id": owner_id}},
            {"term": {"barcode": barcode}},
        ]
        if category:
            musts.append({"term": {"category": category}})
        body = {
            "query": {"bool": {"must": musts}},
            "sort": [{"added_at": {"order": "asc"}}],
            "size": 50,
        }
        resp = self.client.search(index=ITEMS_INDEX, body=body)
        return [{"id": h["_id"], **h["_source"]} for h in resp["hits"]["hits"]]

    def update_item(self, item_id: str, **fields: object) -> bool:
        """Partial update of an item."""
        try:
            self.client.update(
                index=ITEMS_INDEX,
                id=item_id,
                body={"doc": fields},
                refresh="wait_for",
            )
            return True
        except NotFoundError:
            return False

    def delete_item(self, item_id: str, owner_id: int) -> bool:
        """Delete an item only if it belongs to *owner_id*."""
        item = self.get_item(item_id)
        if item and item["owner_id"] == owner_id:
            self.client.delete(index=ITEMS_INDEX, id=item_id, refresh="wait_for")
            return True
        return False

    def delete_items_by_barcode(
        self, owner_id: int, barcode: str, category: str | None = None, limit: int = 1
    ) -> int:
        """Delete up to *limit* items matching barcode (oldest first). Returns count deleted."""
        items = self.find_items_by_barcode(owner_id, barcode, category)
        deleted = 0
        for item in items[:limit]:
            self.client.delete(index=ITEMS_INDEX, id=item["id"], refresh="wait_for")
            deleted += 1
        return deleted

    def search_items(self, owner_id: int, query_text: str) -> list[dict]:
        """Full-text search over product names for an owner."""
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"owner_id": owner_id}},
                        {"match": {"product_name": query_text}},
                    ]
                }
            },
            "size": 30,
        }
        resp = self.client.search(index=ITEMS_INDEX, body=body)
        return [{"id": h["_id"], **h["_source"]} for h in resp["hits"]["hits"]]

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def get_categories(self, owner_id: int) -> list[str]:
        """Return category names for an owner."""
        body = {
            "query": {"term": {"owner_id": owner_id}},
            "sort": [{"created_at": {"order": "asc"}}],
            "size": 50,
        }
        resp = self.client.search(index=CATEGORIES_INDEX, body=body)
        return [h["_source"]["name"] for h in resp["hits"]["hits"]]

    def ensure_categories(self, owner_id: int, names: list[str]) -> None:
        """Create categories that don't already exist for an owner."""
        existing = set(self.get_categories(owner_id))
        for name in names:
            if name not in existing:
                self.client.index(
                    index=CATEGORIES_INDEX,
                    body={
                        "owner_id": owner_id,
                        "name": name,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                    refresh="wait_for",
                )

    def add_category(self, owner_id: int, name: str) -> bool:
        """Add a single category. Returns False if it already exists."""
        existing = set(self.get_categories(owner_id))
        if name in existing:
            return False
        self.client.index(
            index=CATEGORIES_INDEX,
            body={
                "owner_id": owner_id,
                "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            refresh="wait_for",
        )
        return True

    def delete_category(self, owner_id: int, name: str) -> bool:
        """Delete a category by name. Returns True if found and deleted."""
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"owner_id": owner_id}},
                        {"term": {"name": name}},
                    ]
                }
            }
        }
        resp = self.client.search(index=CATEGORIES_INDEX, body=body)
        hits = resp["hits"]["hits"]
        if not hits:
            return False
        self.client.delete(index=CATEGORIES_INDEX, id=hits[0]["_id"], refresh="wait_for")
        return True

    # ------------------------------------------------------------------
    # Product cache
    # ------------------------------------------------------------------

    def get_cached_product(self, barcode: str) -> dict | None:
        """Look up a previously fetched product by barcode."""
        body = {
            "query": {"term": {"barcode": barcode}},
            "size": 1,
        }
        resp = self.client.search(index=PRODUCTS_CACHE_INDEX, body=body)
        hits = resp["hits"]["hits"]
        if hits:
            return {"id": hits[0]["_id"], **hits[0]["_source"]}
        return None

    def cache_product(
        self,
        barcode: str,
        product_name: str,
        brand: str = "",
        image_url: str = "",
        raw: dict | None = None,
    ) -> str:
        """Store a product lookup result. Updates existing entry if present."""
        existing = self.get_cached_product(barcode)
        doc = {
            "barcode": barcode,
            "product_name": product_name,
            "brand": brand,
            "image_url": image_url,
            "raw": raw or {},
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing:
            self.client.index(
                index=PRODUCTS_CACHE_INDEX, id=existing["id"], body=doc, refresh="wait_for"
            )
            return existing["id"]
        resp = self.client.index(index=PRODUCTS_CACHE_INDEX, body=doc, refresh="wait_for")
        return resp["_id"]

    # ------------------------------------------------------------------
    # Review helpers
    # ------------------------------------------------------------------

    def get_unverified_items(self, owner_id: int, size: int = 20) -> list[dict]:
        """Return items that haven't been verified by the user."""
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"owner_id": owner_id}},
                        {"term": {"verified": False}},
                    ]
                }
            },
            "sort": [{"added_at": {"order": "desc"}}],
            "size": size,
            # Collapse on barcode so each product appears only once
            "collapse": {"field": "barcode"},
        }
        resp = self.client.search(index=ITEMS_INDEX, body=body)
        return [{"id": h["_id"], **h["_source"]} for h in resp["hits"]["hits"]]

    def verify_items_by_barcode(
        self, owner_id: int, barcode: str, new_name: str | None = None
    ) -> int:
        """Mark all items with this barcode as verified. Optionally rename."""
        items = self.find_items_by_barcode(owner_id, barcode)
        count = 0
        for item in items:
            fields: dict = {"verified": True}
            if new_name:
                fields["product_name"] = new_name
            self.update_item(item["id"], **fields)
            count += 1
        return count
