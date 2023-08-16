import re


normalize_char_map = {
    ord("ä"): "ae",
    ord("Â"): "Ae",
    ord("ö"): "oe",
    ord("Ô"): "Oe",
    ord("ü"): "ue",
    ord("Û"): "Ue",
    ord("ß"): "ss",
    ord("á"): "a",
    ord("Á"): "A",
    ord("é"): "e",
    ord("É"): "E",
    ord("ó"): "o",
    ord("à"): "a",
    ord("À"): "A",
    ord("è"): "e",
    ord("È"): "E",
    ord("ò"): "o",
    ord("Ò"): "O",
}


def normalize_for_filename(text: str) -> str:
    """
    Normalizes a given string for use within a filename. The returned value
    meets the following requirements:
    - Lowercase.
    - Most in Germany used umlauts, diacritics and similar special characters
      are replaced by an ASCII character.
    - Spaces (everything matching `\r` in a regular expression) are replaced
      with a dash.
    - Every other char which doesn't fulfill the regex `[a-zA-Z0-9-_]` is
      removed.
    """
    text = text.lower()
    text = re.sub(r"\s+", "-", text)
    text = text.translate(normalize_char_map)
    text = re.sub(r"[^a-zA-Z0-9-_]", "", text)
    return text