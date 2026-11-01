import unicodedata


def sort_key(text: str) -> str:
    """Text without case and accents: sorts "Älplermagronen" next to "Apfelwähe" (not after "Zopf"), and lets a
    search for "alpler" find it."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))
