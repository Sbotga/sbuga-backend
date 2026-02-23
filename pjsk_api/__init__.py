from .client import PJSKClient

clients: dict[str, PJSKClient] = {}


async def set_client(region: str, client: PJSKClient | None):
    if clients.get(region):
        try:
            await clients[region].close()
        except:
            pass
    if client == None:
        clients.pop(region, None)
    else:
        clients[region] = client
