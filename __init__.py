"""
LocalPasswordVault — package metadata only.

Runtime entry is flat: ``python app.py`` or the PyInstaller binary.
Do not import ``.app`` here; that breaks one-file bundling (sibling modules
like ``config`` must stay top-level for ``from config import …``).
"""

__all__: list[str] = []
