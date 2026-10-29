"""Locate checked-out or wheel-bundled study assets, without parent repos."""

from pathlib import Path


def asset_root():
    package = Path(__file__).resolve().parent
    for candidate in (package.parent, package):
        if (candidate / 'configs/agents/current.json').is_file():
            return candidate
    raise FileNotFoundError('Agent configuration assets are missing from this installation')
