import re2


def check_password(password: str) -> bool:
    if len(password) < 8 or len(password) > 50:
        return False
    if not re2.search(r"[A-Z]", password):
        return False
    if not re2.search(r"[a-z]", password):
        return False
    if not re2.search(r"[0-9]", password):
        return False
    if not re2.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", password):
        return False
    return True


def check_username(username: str) -> bool:
    if len(username) <= 3 or len(username) >= 20:
        return False
    if not re2.fullmatch(r"[a-z0-9_]+", username):
        return False
    return True


def check_display_name(display_name: str) -> bool:
    if len(display_name) <= 1 or len(display_name) >= 30:
        return False
    return True
