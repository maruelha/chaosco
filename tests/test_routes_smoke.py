"""Route smoke test (refactoring step 2).

Every parameterless GET route must respond 200 (or a redirect). This is the
cheap tripwire for the monolith split: if a blueprint move breaks a route or
a template, this fails immediately.

Runs against the app as configured (GET only — no route here mutates data).
Parameterized routes (detail pages, downloads with <id>) are exercised by
feature tests instead.
"""
import pytest

from app.web import app


def _parameterless_get_rules():
    rules = []
    for rule in app.url_map.iter_rules():
        if rule.arguments:                 # needs an <id>/<filename> — skip here
            continue
        if "GET" not in (rule.methods or set()):
            continue
        if rule.rule == "/static/<path:filename>":
            continue
        rules.append(rule.rule)
    return sorted(rules)


@pytest.mark.parametrize("url", _parameterless_get_rules())
def test_get_route_responds(url):
    with app.test_client() as client:
        resp = client.get(url)
        assert resp.status_code in (200, 302), f"{url} -> {resp.status_code}"


def test_route_inventory_is_not_empty():
    # sanity: the parametrize above actually covered a meaningful set
    assert len(_parameterless_get_rules()) >= 25
