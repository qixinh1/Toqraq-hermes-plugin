"""Hermes entry resolved inside the host-assigned plugin package namespace."""

from collections.abc import Callable
from importlib import import_module
from typing import cast

if not __package__:
    raise RuntimeError("Toqraq must be loaded as a Hermes plugin package")

_registration = import_module(f"{__package__}.toqraq.hermes.registration")
register = cast(Callable[..., None], _registration.register)
