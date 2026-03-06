from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance: routers decorate with it, main.py registers the
# 429 handler. Per-IP keying is enough at demo scale.
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)  # adds Retry-After on 429
