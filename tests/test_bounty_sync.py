"""اختبار وحدة جالب برامج المكافآت (بلا شبكة)."""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent_os import bounty_sync


def test_selftest_parsers_all_platform_shapes():
    res = bounty_sync.selftest()
    for k in ("parser_bugcrowd", "parser_hackerone", "parser_intigriti",
              "parser_yeswehack", "parser_immunefi"):
        assert res[k] is True
    assert res["all"] is True


def test_normalize_rejects_wildcard_and_ip_actors():
    rec = {
        "name": "X", "url": "https://bugcrowd.com/x",
        "targets": {
            "in_scope": [
                {"type": "api", "target": "*.everything.example.com"},
                {"type": "ip", "target": "10.0.0.0/8"},
                {"type": "code", "target": "https://github.com/ex/x"},
                {"type": "website", "target": "app.example.com"},
            ]
        }}
    r = bounty_sync.normalize_record("bugcrowd", rec)
    assert r is not None
    ids = [t[0] for t in r["targets"]]
    assert "*.everything.example.com" not in ids
    assert "10.0.0.0/8" not in ids
    assert "app.example.com" in ids


def test_feeds_registry():
    assert "bugcrowd" in bounty_sync.FEEDS
    assert "hackerone" in bounty_sync.FEEDS
    assert "intigriti" in bounty_sync.FEEDS
    assert "yeswehack" in bounty_sync.FEEDS
    assert "federacy" in bounty_sync.FEEDS
    assert "immunefi" in bounty_sync.FEEDS


def test_immunefi_keeps_contract_assets():
    rec = {
        "project": "DAO", "slug": "dao", "maxBounty": 100000,
        "assets": [
            {"url": "https://app.dao.example/", "type": "websites_and_applications"},
            {"url": "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B", "type": "smart_contract"},
        ]}
    r = bounty_sync.normalize_record("immunefi", rec)
    ids = [t[0] for t in r["targets"]]
    assert "https://app.dao.example/" in ids
    assert "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B" in ids
    assert r["max_payout"] == 100000