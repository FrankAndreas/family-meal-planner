"""Turning an inbox item into a recipe draft (filled in by the processing pipeline)."""


def start(item_id: int, user_id: int) -> None:
    """Process the item in the background."""
