from .client import PJSKClient

clients: dict[str, PJSKClient] = {}


async def set_client(region: str, client: PJSKClient):
    if clients.get(region):
        try:
            await clients["en"].close()
        except:
            pass
    clients[region] = client
