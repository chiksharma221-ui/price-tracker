import time
from concurrent.futures import ThreadPoolExecutor

from price_tracker.ratelimit import LocalDomainRateLimiter, domain_of


def test_same_domain_requests_are_spaced_across_threads():
    limiter = LocalDomainRateLimiter(interval=0.1)
    stamps = []

    def hit(_):
        limiter.acquire("amazon.in")
        stamps.append(time.monotonic())

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(hit, range(4)))
    stamps.sort()
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert all(g >= 0.09 for g in gaps)


def test_different_domains_do_not_block_each_other():
    limiter = LocalDomainRateLimiter(interval=5)
    limiter.acquire("amazon.in")
    start = time.monotonic()
    limiter.acquire("flipkart.com")
    assert time.monotonic() - start < 0.1


def test_domain_of_groups_subdomains():
    assert domain_of("https://www.amazon.in/dp/X") == "amazon.in"
    assert domain_of("https://m.flipkart.com/p") == "flipkart.com"
    assert domain_of("https://shop.example.co.uk/x") == "example.co.uk"
