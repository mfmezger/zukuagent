from zukuagent.pairing import PairingRegistry


def test_pairing_rejects_device_not_in_allowlist(tmp_path):
    registry = PairingRegistry(
        storage_path=str(tmp_path / "pairings.json"),
        allowed_devices=["allowed-1"],
    )

    ok, message = registry.pair(chat_id=1, device_id="blocked-1")

    assert ok is False
    assert "not in the allowed pairing list" in message


def test_pairing_allows_only_one_chat_per_device(tmp_path):
    registry = PairingRegistry(
        storage_path=str(tmp_path / "pairings.json"),
        allowed_devices=["device-1"],
    )

    ok_first, _ = registry.pair(chat_id=1, device_id="device-1")
    ok_second, message_second = registry.pair(chat_id=2, device_id="device-1")

    assert ok_first is True
    assert ok_second is False
    assert "already paired to another chat" in message_second


def test_pairing_persists_to_disk(tmp_path):
    file_path = str(tmp_path / "pairings.json")
    registry = PairingRegistry(storage_path=file_path, allowed_devices=["device-1"])
    registry.pair(chat_id=42, device_id="device-1")

    loaded = PairingRegistry(storage_path=file_path, allowed_devices=["device-1"])
    assert loaded.get_device(42) == "device-1"
