# forge/web/api/limiter.py
"""
Rate limiter — defined here (not in main.py) so auth.py and main.py
can both import it without creating a circular import.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)