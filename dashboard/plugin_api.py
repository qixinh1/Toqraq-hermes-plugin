"""API-only Dashboard mount for the Toqraq Desktop backend."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import cast

from fastapi.routing import APIRouter

if not __package__:
    raise RuntimeError("Toqraq Dashboard must be loaded as a Hermes plugin package")

_plugin_package = __package__.rsplit(".", 1)[0]
_api = import_module(f"{_plugin_package}.toqraq.api")
_containers = import_module(f"{_plugin_package}.toqraq.services.container")
build_router = cast(Callable[[object], APIRouter], _api.build_router)
get_container = cast(Callable[[], object], _containers.get_container)

router: APIRouter = build_router(get_container())
