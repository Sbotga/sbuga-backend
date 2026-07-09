from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
import unicodedata
import re


def _is_invisible(ch: str) -> bool:
    """Zero-width / control / bidi format chars (Cc, Cf), the Tags block (the U+E0000
    tag space some clients inject — unassigned/Cn, so the category check alone misses
    it) and variation selectors. Without stripping these, two identical-looking
    aliases are different strings and both get stored."""
    if unicodedata.category(ch) in ("Cc", "Cf"):
        return True
    o = ord(ch)
    return (
        0xE0000 <= o <= 0xE007F  # Tags
        or 0xFE00 <= o <= 0xFE0F  # variation selectors
        or 0xE0100 <= o <= 0xE01EF  # variation selectors supplement
    )


def preprocess(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if not _is_invisible(c))
    text = text.lower().strip()

    STAR_LIKE = (
        r"[\u2600-\u26FF"
        r"\U0001F300-\U0001F5FF"
        r"\U0001F600-\U0001F64F"
        r"\U0001F680-\U0001F6FF]"
    )  # NOTE: re2 doesn't support unicode patterns.... WHYYY
    text = re.sub(STAR_LIKE, " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fuzzy_match_to_dict_key_partial(
    input_str: str, dictionary: dict, sensitivity: float = 0.6
) -> str | None:
    """
    Fuzzy match input_str to the closest key in the dictionary, prioritizing partial matches and small edit distances.

    Args:
        input_str (str): The string to match.
        dictionary (dict): The dictionary to match against.
        sensitivity (float): Minimum score threshold for a valid match (0-1).

    Returns:
        str | None: Best match key if score >= sensitivity, otherwise None.
    """
    if not dictionary:
        return None

    sensitivity = sensitivity * 100
    input_str = preprocess(input_str)
    preprocessed_keys = {key: preprocess(key) for key in dictionary.keys()}

    best_match = None
    best_score = 0
    best_distance = 10**9

    for original_key, preprocessed_key in preprocessed_keys.items():
        similarity = fuzz.token_set_ratio(input_str, preprocessed_key)
        edit_distance = Levenshtein.distance(input_str, preprocessed_key)

        if edit_distance > 5:
            similarity -= (edit_distance - 5) * 5

        if similarity > best_score or (
            similarity == best_score and edit_distance < best_distance
        ):
            if similarity >= sensitivity:
                best_match = original_key
                best_score = similarity
                best_distance = edit_distance

    return best_match


def fuzzy_match_to_dict_key(
    input_str, dictionary, sensitivity: float = 0.6, ratio: bool = True
):
    """
    Fuzzy match input_str to the closest key in the dictionary.

    Args:
        input_str (str): The string to match.
        dictionary (dict): The dictionary to match against.
        sensitivity (float): Minimum score threshold for a valid match (0-1).
        ratio (bool): Use default ratio? If False, uses weighted ratio.

    Returns:
        str | None: Best match key if score >= sensitivity, otherwise None.
    """
    sensitivity = sensitivity * 100
    if not dictionary:
        return None

    input_str = preprocess(input_str)
    keys = [preprocess(key) for key in dictionary.keys()]

    result = process.extractOne(
        input_str,
        keys,
        scorer=fuzz.ratio if ratio else fuzz.WRatio,
        processor=None,
    )

    if result and result[1] >= sensitivity:
        matched_index = keys.index(result[0])
        return list(dictionary.keys())[matched_index]

    return None


def fuzzy_match_multi(
    input_str: str,
    dictionary: dict,
    sensitivity: float = 0.65,
    limit: int = 10,
) -> list[str]:
    """
    Fuzzy match input_str against dictionary keys, returning up to `limit` best matching keys
    sorted by score descending. Uses token_set_ratio with Levenshtein penalty.

    Args:
        input_str (str): The string to match.
        dictionary (dict): The dictionary to match against.
        sensitivity (float): Minimum score threshold (0-1).
        limit (int): Maximum number of results to return.

    Returns:
        list[str]: List of matching original keys sorted by score descending.
    """
    if not dictionary:
        return []

    sensitivity = sensitivity * 100
    input_str = preprocess(input_str)
    preprocessed_keys = {key: preprocess(key) for key in dictionary.keys()}

    scores: list[tuple[str, float, int]] = []

    for original_key, preprocessed_key in preprocessed_keys.items():
        similarity = fuzz.token_set_ratio(input_str, preprocessed_key)
        edit_distance = Levenshtein.distance(input_str, preprocessed_key)

        if edit_distance > 5:
            similarity -= (edit_distance - 5) * 5

        if similarity >= sensitivity:
            scores.append((original_key, similarity, edit_distance))

    # token_set_ratio gives 100 to token-subset matches ("meru" vs "meru to"),
    # so ties are broken by edit distance: exact/closest keys win.
    scores.sort(key=lambda x: (-x[1], x[2]))
    return [key for key, _, _ in scores[:limit]]
