from zukuagent.settings import Settings


def test_telegram_csv_parsing():
    settings = Settings(
        telegram_allowed_chat_ids="1, 2,3",
        telegram_allowed_pairing_devices="dev-a, dev-b",
    )

    assert settings.telegram_allowed_chat_ids == [1, 2, 3]
    assert settings.telegram_allowed_pairing_devices == ["dev-a", "dev-b"]
