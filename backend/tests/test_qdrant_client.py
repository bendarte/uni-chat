import dataclasses
from types import SimpleNamespace

import pytest

from app.config import settings
from app.qdrant_client import (
    IndexShrinkRefused,
    get_qdrant_client,
    publish_program_collection,
)


def _client_with_counts(mocker, counts):
    client = mocker.Mock()
    client.count.side_effect = lambda collection_name, exact: SimpleNamespace(
        count=counts[collection_name]
    )
    mocker.patch("app.qdrant_client.get_qdrant_client", return_value=client)
    mocker.patch("app.qdrant_client._collection_exists", return_value=True)
    return client


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


def test_publish_refuses_to_replace_the_live_index_with_a_much_smaller_one(mocker):
    client = _client_with_counts(
        mocker,
        {"programs_active": 3560, "programs_capped": 387},
    )

    with pytest.raises(IndexShrinkRefused) as excinfo:
        publish_program_collection("programs_capped")

    assert "387" in str(excinfo.value)
    assert "3560" in str(excinfo.value)
    client.update_collection_aliases.assert_not_called()


def test_publish_allows_a_slightly_smaller_index(mocker):
    client = _client_with_counts(
        mocker,
        {"programs_active": 3560, "programs_fresh": 3400},
    )

    publish_program_collection("programs_fresh")

    client.update_collection_aliases.assert_called_once()


def test_publish_allows_shrinking_when_explicitly_permitted(mocker):
    mocker.patch(
        "app.qdrant_client.settings",
        dataclasses.replace(settings, allow_index_shrink=True),
    )
    client = _client_with_counts(
        mocker,
        {"programs_active": 3560, "programs_capped": 387},
    )

    publish_program_collection("programs_capped")

    client.update_collection_aliases.assert_called_once()
    client.count.assert_not_called()


def test_publish_proceeds_when_the_live_index_is_empty(mocker):
    client = _client_with_counts(
        mocker,
        {"programs_active": 0, "programs_first_ingest": 12},
    )

    publish_program_collection("programs_first_ingest")

    client.update_collection_aliases.assert_called_once()
