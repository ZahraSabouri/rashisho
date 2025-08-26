from typing import Any

from django.core.cache import cache


class Cache:
    @staticmethod
    def get_cache(key: Any) -> Any:
        value = cache.get(key=key)
        cache.close()
        return value

    @staticmethod
    def set_cache(key: Any, value: Any, timeout: int | None = None) -> None:
        cache.set(key, value=value, timeout=timeout)
        cache.close()
