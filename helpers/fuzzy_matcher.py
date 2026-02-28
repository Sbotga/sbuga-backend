from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
import unicodedata
import re2


def preprocess(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()

    STAR_LIKE = (
        r"[\u2600-\u26FF]"
        r"|[\U0001F300-\U0001F5FF]"
        r"|[\U0001F600-\U0001F64F]"
        r"|[\U0001F680-\U0001F6FF]"
    )
    text = re2.sub(STAR_LIKE, " ", text)
    text = re2.sub(r"\s+", " ", text).strip()
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

    for original_key, preprocessed_key in preprocessed_keys.items():
        similarity = fuzz.token_set_ratio(input_str, preprocessed_key)
        edit_distance = Levenshtein.distance(input_str, preprocessed_key)

        if edit_distance > 5:
            similarity -= (edit_distance - 5) * 5

        if similarity > best_score or (
            similarity == best_score
            and edit_distance < Levenshtein.distance(input_str, best_match or "")
        ):
            if similarity >= sensitivity:
                best_match = original_key
                best_score = similarity

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

    scores: list[tuple[str, float]] = []

    for original_key, preprocessed_key in preprocessed_keys.items():
        similarity = fuzz.token_set_ratio(input_str, preprocessed_key)
        edit_distance = Levenshtein.distance(input_str, preprocessed_key)

        if edit_distance > 5:
            similarity -= (edit_distance - 5) * 5

        if similarity >= sensitivity:
            scores.append((original_key, similarity))

    scores.sort(key=lambda x: x[1], reverse=True)
    return [key for key, _ in scores[:limit]]
