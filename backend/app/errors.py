class Refused(Exception):
    """A rule said no, anywhere: also outside a request (the importer runs in a thread of its own), so this knows
    nothing of HTTP. `code` names the text the person sees (errors.<code> in the locales), `params` the values it
    needs; `status` is only how an API request answers it (see main.py)."""

    status = 400

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


class NotFound(Refused):
    status = 404


def detail(code: str, **params) -> str | dict:
    """The answer's `detail`: the code alone, or with the values the text needs as extra fields."""
    return {"code": code, **params} if params else code
