from app import main as main_module


def test_local_rate_limit_fallback_evicts_oldest_entries(monkeypatch):
    monkeypatch.setattr(main_module, "MAX_RATE_LIMIT_FALLBACK_ENTRIES", 2)
    with main_module._rate_limit_lock:
        main_module._rate_limit_fallback.clear()

    try:
        main_module._check_local_rate_limit("client-1")
        main_module._check_local_rate_limit("client-2")
        main_module._check_local_rate_limit("client-3")

        with main_module._rate_limit_lock:
            keys = list(main_module._rate_limit_fallback.keys())
    finally:
        with main_module._rate_limit_lock:
            main_module._rate_limit_fallback.clear()

    assert keys == ["client-2", "client-3"]
