"""B2 — the shared SignalResult unavailability-signal envelope."""
import pytest

from services.data_sources.result import (
    SignalResult,
    SignalStatus,
    coerce_to_signal_result,
    normalize_source_result,
)
from services import smart_data_layer


def test_missing_config_normalizes_to_unavailable():
    raw = {"source": "reddit", "status": "unavailable", "reason": "REDDIT_CLIENT_ID/SECRET not configured"}
    result = normalize_source_result("reddit", raw)
    assert result.status == SignalStatus.UNAVAILABLE
    assert result.payload is None
    assert "not configured" in result.reason


def test_not_yet_implemented_normalizes_to_unavailable():
    raw = {"source": "wellfound", "status": "unavailable", "reason": "live scraper not yet implemented"}
    result = normalize_source_result("wellfound", raw)
    assert result.status == SignalStatus.UNAVAILABLE


def test_generic_fetch_failure_normalizes_to_error():
    raw = {"source": "hacker_news", "status": "unavailable", "reason": "live fetch failed: timeout"}
    result = normalize_source_result("hacker_news", raw)
    assert result.status == SignalStatus.ERROR
    assert result.payload is None


def test_429_in_reason_normalizes_to_rate_limited():
    raw = {"source": "product_hunt", "status": "unavailable", "reason": "live fetch failed: Client error '429 Too Many Requests' for url '...'"}
    result = normalize_source_result("product_hunt", raw)
    assert result.status == SignalStatus.RATE_LIMITED


def test_exception_normalizes_to_error():
    result = normalize_source_result("google_trends", TimeoutError("boom"))
    assert result.status == SignalStatus.ERROR
    assert "boom" in result.reason
    assert result.payload is None


def test_successful_payload_normalizes_to_ok():
    raw = {"source": "reddit", "keyword": "dog walking", "post_count": 142, "sample_posts": [{"title": "x"}]}
    result = normalize_source_result("reddit", raw)
    assert result.status == SignalStatus.OK
    assert result.payload["post_count"] == 142
    assert result.reason is None


def test_zero_records_normalizes_to_empty_not_fabricated():
    """A real live fetch that genuinely finds nothing must be distinguishable
    from a source that couldn't be checked at all — never faked as 'ok'."""
    raw = {"source": "hacker_news", "keyword": "x", "hit_count": 0, "sample_posts": []}
    result = normalize_source_result("hacker_news", raw)
    assert result.status == SignalStatus.EMPTY
    assert result.payload["hit_count"] == 0


@pytest.mark.parametrize("source,raw", [
    ("google_trends", {"source": "google_trends", "keyword": "x", "raw": []}),
    ("product_hunt", {"source": "product_hunt", "keyword": "x", "launch_count": 0, "top_products": []}),
])
def test_zero_records_empty_for_other_sources(source, raw):
    result = normalize_source_result(source, raw)
    assert result.status == SignalStatus.EMPTY


def test_unexpected_output_type_normalizes_to_error():
    result = normalize_source_result("reddit", "not a dict")
    assert result.status == SignalStatus.ERROR


def test_coerce_passes_through_already_normalized_result():
    already = SignalResult(source="reddit", status=SignalStatus.OK, payload={"post_count": 5}).model_dump(mode="json")
    result = coerce_to_signal_result("reddit", already)
    assert result.status == SignalStatus.OK
    assert result.payload["post_count"] == 5


def test_coerce_normalizes_legacy_flat_dict():
    """Existing callers (and existing tests) pass a flat per-source dict
    with no status/payload/fetched_at envelope at all — must still work."""
    legacy = {"pain_frequency": "high", "post_count": 142}
    result = coerce_to_signal_result("reddit", legacy)
    assert result.status == SignalStatus.OK
    assert result.payload["post_count"] == 142


async def test_gather_signals_normalizes_every_source(monkeypatch):
    """Full smart_data_layer.gather_signals() output is SignalResult-shaped
    per source, regardless of whether the underlying source succeeded,
    was unconfigured, or raised."""
    async def _ok(keyword):
        return {"source": "hacker_news", "keyword": keyword, "hit_count": 12, "sample_posts": []}

    async def _unavailable(keyword):
        return {"source": "reddit", "status": "unavailable", "reason": "REDDIT_CLIENT_ID/SECRET not configured"}

    async def _raises(keyword):
        raise RuntimeError("network down")

    monkeypatch.setattr(smart_data_layer, "google_trends", type("M", (), {"fetch": staticmethod(_raises)}))
    monkeypatch.setattr(smart_data_layer, "reddit", type("M", (), {"fetch": staticmethod(_unavailable)}))
    monkeypatch.setattr(smart_data_layer, "hacker_news", type("M", (), {"fetch": staticmethod(_ok)}))
    monkeypatch.setattr(smart_data_layer, "product_hunt", type("M", (), {"fetch": staticmethod(_unavailable)}))
    monkeypatch.setattr(smart_data_layer, "wellfound", type("M", (), {"fetch": staticmethod(_unavailable)}))

    async def _no_cache_get(source, keyword):
        return None

    async def _no_cache_set(source, keyword, data):
        return None

    monkeypatch.setattr(smart_data_layer.cache, "get_cached", _no_cache_get)
    monkeypatch.setattr(smart_data_layer.cache, "set_cached", _no_cache_set)

    result = await smart_data_layer.gather_signals("dog walking")
    signals = result["signals"]

    assert signals["google_trends"]["status"] == "error"
    assert signals["reddit"]["status"] == "unavailable"
    assert signals["hacker_news"]["status"] == "ok"
    assert signals["hacker_news"]["payload"]["hit_count"] == 12
    assert signals["product_hunt"]["status"] == "unavailable"
    assert signals["wellfound"]["status"] == "unavailable"
    # every entry carries the shared envelope fields
    for name in ["google_trends", "reddit", "hacker_news", "product_hunt", "wellfound"]:
        assert "fetched_at" in signals[name]
