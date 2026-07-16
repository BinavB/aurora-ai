"""AURORA application package (AEGIS architecture).

Layered per ``ARCHITECTURE.md``. Dependencies flow strictly downward:
``api → services → agents → tools → providers``, with ``core`` and ``config``
as shared foundations depended upon by everything above them.
"""
