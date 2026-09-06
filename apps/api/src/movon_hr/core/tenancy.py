"""In-process tenant registry with request-scoped isolation.

Business logic still uses an in-memory store per tenant. Persistence writes
each tenant's rows with ``tenant_id`` so companies never share records.
"""

from __future__ import annotations

from contextvars import ContextVar

DEMO_TENANT_ID = "pt-movon-solusi-kreatif"
DEMO_TENANT_NAME = "PT Movon Solusi Kreatif"
DEMO_TENANT_SLUG = "pt-movon-solusi-kreatif"

_active_tenant_id: ContextVar[str] = ContextVar("active_tenant_id", default=DEMO_TENANT_ID)
_stores: dict = {}


def bind_tenant(tenant_id: str) -> None:
    _active_tenant_id.set(tenant_id)


def current_tenant_id() -> str:
    return _active_tenant_id.get()


def get_store(tenant_id: str | None = None):
    from movon_hr.modules.api import DemoStore

    tid = tenant_id or current_tenant_id()
    store = _stores.get(tid)
    if store is None:
        store = DemoStore(tenant_id=tid)
        _stores[tid] = store
    return store


def put_store(store) -> None:
    _stores[store.tenant_id] = store


def iter_stores():
    return list(_stores.values())


def clear_registry() -> None:
    _stores.clear()
    bind_tenant(DEMO_TENANT_ID)


class StoreFacade:
    """Attribute proxy so existing ``store.employees`` code stays tenant-scoped."""

    def _raw(self):
        return get_store()

    def __getattr__(self, name):
        return getattr(self._raw(), name)

    def __setattr__(self, name, value):
        setattr(self._raw(), name, value)


store = StoreFacade()
