"""
Active fuzzing and reverse-engineering routines for ShadowScout.
"""

from shadowscout.fuzzer.header_pruner import prune_request_headers
from shadowscout.fuzzer.pagination import detect_pagination_strategy

__all__ = ["prune_request_headers", "detect_pagination_strategy"]
