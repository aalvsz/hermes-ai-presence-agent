from datetime import datetime, timezone

from tools.news_scout import balanced_limit, parse_feed


def test_parse_atom_feed():
    payload = b"""<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Useful result</title><link href='https://example.com/paper'/><updated>2026-08-14T10:00:00Z</updated><summary>Concrete &amp; checked</summary></entry></feed>"""
    items = parse_feed(payload, {"name": "fixture", "category": "papers"})
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/paper"
    assert items[0]["published_at"] == datetime(2026, 8, 14, 10, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_balanced_limit_prevents_one_source_from_crowding_out_others():
    items = [
        {"source": "arXiv", "published_at": f"2026-08-14T10:0{i}:00Z"}
        for i in range(5)
    ] + [{"source": "Raschka", "published_at": "2026-08-14T09:00:00Z"}]
    selected = balanced_limit(items, per_source=2, total=4)
    assert [item["source"] for item in selected] == ["arXiv", "arXiv", "Raschka"]
