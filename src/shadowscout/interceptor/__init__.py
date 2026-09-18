"""
Network interception and browser automation module for ShadowScout.
"""

from shadowscout.interceptor.filters import is_noise_request
from shadowscout.interceptor.har_stream import HarStream
from shadowscout.interceptor.browser import PlaywrightInterceptor

__all__ = ["is_noise_request", "HarStream", "PlaywrightInterceptor"]
