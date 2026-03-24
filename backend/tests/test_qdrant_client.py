from app.qdrant_client import get_qdrant_client


def test_get_qdrant_client_reuses_singleton_instance(mocker):
    mocked_client = mocker.sentinel.qdrant_client
    constructor = mocker.patch(
        "app.qdrant_client.QdrantClient",
        return_value=mocked_client,
    )

    get_qdrant_client.cache_clear()
    try:
        first = get_qdrant_client()
        second = get_qdrant_client()
    finally:
        get_qdrant_client.cache_clear()

    assert first is mocked_client
    assert second is mocked_client
    constructor.assert_called_once()
