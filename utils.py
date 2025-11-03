# utils.py
import unicodedata

def tr_norm(s: str) -> str:
    """Search-normalize Turkish strings.
       Keeps i/ı case-insensitive for matching (both → 'i'), strips accents and spaces."""
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    s = s.strip().lower()

    # split accents (so we can drop combining marks)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    # map Turkish letters to ASCII equivalents for matching
    # IMPORTANT: only single-char keys in maketrans
    s = s.translate(str.maketrans("şığöüç", "sigouc"))
    s = s.replace("ı", "i")   # dotless i -> i

    # remove spaces for forgiving search
    return s.replace(" ", "")
