#!/usr/bin/env python
"""Build declaration for the Toqraq Godot bridge module."""

from __future__ import annotations

import re

_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_SYMBOLIC_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def can_build(env, platform):
    """Build only for the current certified platform with WebSocket support."""
    env.module_add_dependencies("toqraq", ["websocket"])
    return platform == "windows"


def get_opts(platform):
    """Declare the two required intrinsic distribution identity inputs."""
    return [
        ("toqraq_build_id", "Unique opaque Toqraq candidate build identity.", ""),
        (
            "toqraq_distribution_id",
            "Certified symbolic Toqraq distribution identity.",
            "",
        ),
    ]


def _quoted_define(value):
    """Return a compiler string token after identifier validation removed escapes."""
    return f'\\"{value}\\"'


def configure(env):
    """Reject identity-free builds and compile reviewed values into the module."""
    build_id = env["toqraq_build_id"]
    distribution_id = env["toqraq_distribution_id"]
    if not isinstance(build_id, str) or _OPAQUE_ID.fullmatch(build_id) is None:
        raise ValueError("toqraq_build_id must be one valid opaque identifier")
    if (
        not isinstance(distribution_id, str)
        or len(distribution_id) > 128
        or _SYMBOLIC_ID.fullmatch(distribution_id) is None
    ):
        raise ValueError("toqraq_distribution_id must be one valid symbolic identifier")
    env.Append(
        CPPDEFINES=[
            ("TOQRAQ_BUILD_ID", _quoted_define(build_id)),
            ("TOQRAQ_DISTRIBUTION_ID", _quoted_define(distribution_id)),
        ]
    )


def get_doc_classes():
    """The module exposes no script-facing classes."""
    return []


def get_doc_path():
    """No documentation XML is shipped."""
    return ""
