from fastapi import Request


def get_ip(request: Request) -> str | None:
    headers = [
        "CF-Connecting-IP",
        "X-Real-IP",
        "X-Forwarded-For",
        "X-Client-IP",
        "X-Cluster-Client-IP",
        "X-Forwarded",
        "Forwarded-For",
        "Forwarded",
    ]

    for header in headers:
        value = request.headers.get(header)
        if value:
            # X-Forwarded-For can be comma separated, take first value for client
            ip = value.split(",")[0].strip()
            if ip:
                return ip

    if request.client:
        return request.client.host

    return None
