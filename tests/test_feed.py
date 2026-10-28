"""Atom configuration, metadata, and incremental output ownership."""

import json
from xml.etree import ElementTree as ET

import pytest

NS = {"a": "http://www.w3.org/2005/Atom"}


def configure(put, **options):
    put("md2html.json", json.dumps({
        "input": "site", "output": "public", "math": "raw", "feed": True,
        "site": {"url": "https://example.test", "baseurl": "/blog"}, **options,
    }))


@pytest.mark.parametrize("mode", ["site", "jekyll", "pages", "jekyll-markdown"])
def test_feed_is_opt_in_and_only_generated_for_sites(cli, put, tmp_path, mode):
    put("site/page.md", "---\ntitle: Page\n---\nPage")
    configure(put, feed=False, output_mode=mode)
    cli()
    assert not (tmp_path / "public/feed.xml").exists()
    configure(put, output_mode=mode)
    cli()
    assert (tmp_path / "public/feed.xml").exists() == (mode in {"site", "jekyll"})


@pytest.mark.parametrize("value", ["true", 1, {}, None])
def test_feed_option_requires_boolean(cli, put, value):
    configure(put, feed=value)
    assert "feed must be true or false" in cli(ok=False).stderr


@pytest.mark.parametrize("url", ["", "/blog", "example.test", "ftp://example.test", "https://example.test/?q=1"])
def test_generated_feed_requires_site_url_before_writing(cli, put, tmp_path, url):
    put("site/index.md", "Hello")
    configure(put, site={"url": url})
    assert "feed generation requires an absolute http(s) site.url" in cli(ok=False).stderr
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("mode", ["site", "jekyll"])
@pytest.mark.parametrize("enabled", [False, True])
def test_authored_feed_takes_precedence(cli, put, tmp_path, mode, enabled):
    content = '<?xml version="1.0"?><feed>Author content</feed>'
    put("site/feed.xml", content)
    configure(put, output_mode=mode, feed=enabled, site={})
    cli()
    assert (tmp_path / "public/feed.xml").read_text() == content


@pytest.mark.parametrize("modified", [False, True])
def test_disabling_feed_cleans_only_unchanged_generated_output(cli, put, tmp_path, modified):
    put("site/index.md", "Hello")
    configure(put)
    cli()
    feed = tmp_path / "public/feed.xml"
    before = feed.stat().st_mtime_ns
    cli()
    assert feed.stat().st_mtime_ns == before
    if modified:
        feed.write_text("Author replacement")
    configure(put, feed=False)
    cli()
    assert feed.exists() == modified
    if modified:
        assert feed.read_text() == "Author replacement"


def test_feed_sorts_instants_and_uses_latest_update(cli, put, tmp_path):
    put("site/_posts/2026-01-01-a.md", "---\ntitle: Later instant\ndate: '2026-01-01T23:30:00-02:00'\n---\nA")
    put("site/_posts/2026-01-02-b.md", "---\ntitle: Earlier instant\ndate: '2026-01-02T00:30:00+02:00'\n"
        "updated: '2026-02-01T01:00:00+03:00'\npermalink: /a space/\n---\nB")
    configure(put, site={"url": "https://example.test", "baseurl": "/blog", "title": "A & <B>",
                         "author": {"name": "Ada & Bob", "email": "a@example.test"}})
    cli()
    feed = ET.parse(tmp_path / "public/feed.xml").getroot()
    entries = feed.findall("a:entry", NS)
    assert [entry.findtext("a:title", namespaces=NS) for entry in entries] == ["Later instant", "Earlier instant"]
    assert feed.findtext("a:updated", namespaces=NS) == "2026-02-01T01:00:00+03:00"
    assert feed.findtext("a:title", namespaces=NS) == "A & <B>"
    assert feed.findtext("a:author/a:name", namespaces=NS) == "Ada & Bob"
    assert feed.findtext("a:id", namespaces=NS) == "https://example.test/blog/feed.xml"
    assert feed.find("a:link[@rel='self']", NS).get("type") == "application/atom+xml"
    assert entries[1].findtext("a:id", namespaces=NS) == "https://example.test/blog/a%20space/"
    assert entries[0].findtext("a:published", namespaces=NS) == "2026-01-01T23:30:00-02:00"
    assert entries[0].find("a:link[@rel='alternate']", NS) is not None


def test_empty_feed_is_stable_and_valid_xml(cli, put, tmp_path):
    (tmp_path / "site").mkdir()
    configure(put, site={"url": "https://example.test", "title": "A\x01B"})
    cli()
    path = tmp_path / "public/feed.xml"
    feed = ET.parse(path).getroot()
    assert feed.findtext("a:updated", namespaces=NS) == "1970-01-01T00:00:00+00:00"
    assert feed.findtext("a:title", namespaces=NS) == "A\ufffdB"
    assert not feed.findall("a:entry", NS)
    before = path.read_bytes()
    cli()
    assert path.read_bytes() == before


@pytest.mark.parametrize("date", ["not-a-date", "2026-02-30", "2026-01-01T00:00:00+00:00:30"])
def test_invalid_feed_dates_are_actionable(cli, put, tmp_path, date):
    put("site/_posts/2026-01-01-a.md", f"---\ndate: '{date}'\n---\nA")
    configure(put)
    result = cli(ok=False)
    assert "invalid feed date" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "public").exists()
