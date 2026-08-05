"""
Provider Exceptions
======================
Uniform error types every provider adapter raises, so `ProviderRouter`
can react the same way (retry vs. skip straight to fallback)
regardless of which underlying SDK (anthropic, openai, requests...)
threw the original exception.

- ProviderError: generic failure (bad response, API error, auth issue).
  Worth retrying a couple of times — could be transient.
- ProviderTimeoutError: the request took too long. Worth retrying.
- ProviderUnavailableError: the provider is unreachable/not configured
  at all (missing API key, connection refused). Retrying immediately
  won't help — the Router skips straight to the next provider.
"""


class ProviderError(Exception):
    """Generic provider failure."""


class ProviderTimeoutError(ProviderError):
    """Provider did not respond within the configured timeout."""


class ProviderUnavailableError(ProviderError):
    """Provider is unreachable or not configured (e.g. missing API key)."""
