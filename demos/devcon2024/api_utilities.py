# Functions sourced from: https://github.com/ethereum-optimism/op-analytics/tree/main/packages/op-coreutils/src/op_coreutils

import concurrent.futures
from typing import Any, Callable
import urllib3
from urllib3.util.retry import Retry
import time


DEFAULT_RETRY_STRATEGY = Retry(
    total=5,  # Total number of retries
    backoff_factor=1,  # The backoff factor (1 second, then 2, 4, 8...)
    status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
)

def new_session():
    http = urllib3.PoolManager(retries=DEFAULT_RETRY_STRATEGY)

    return http

def get_data(session, url):
    """Helper function to reuse an existing HTTP session to fetch data from a URL."""
    start = time.time()
    resp = session.request(
        method="GET",
        url=url,
        headers={"Content-Type": "application/json"},
    ).json()
    print(f"Fetched from {url}: {time.time() - start:.2f} seconds")
    return resp


def run_concurrently(
    function: Callable,
    targets: dict[str, Any] | list[Any],
    max_workers: int | None = None,
) -> dict[Any, Any]:
    """Concurrently call function on the provided targets.

    "targets" is a dictionary from key to function parameters. The key is used to identify the result in
    the results dictionary.
    """

    max_workers = max_workers or 4
    results = {}

    if isinstance(targets, list):
        targets = {k: k for k in targets}

    if max_workers == -1:
        return run_serially(function, targets)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for key, target in targets.items():
            future = executor.submit(function, target)
            futures[future] = key

        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception:
                print(f"Failed to run thread for {key}")
                raise

    return results


def run_serially(function: Callable, targets: dict[str, Any]) -> dict[str, Any]:
    results = {}
    for key, target in targets.items():
        results[key] = function(target)
    return results
