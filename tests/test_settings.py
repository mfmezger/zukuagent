from zukuagent.core.settings import Settings


def test_csv_list_parsing():
    settings = Settings(
        telegram_allowed_chat_ids="1, 2,3",
        telegram_allowed_pairing_devices="dev-a, dev-b",
        identity_files="IDENTITY.md,SOUL.md",
    )

    assert settings.telegram_allowed_chat_ids == [1, 2, 3]
    assert settings.telegram_allowed_pairing_devices == ["dev-a", "dev-b"]
    assert settings.identity_files == ["IDENTITY.md", "SOUL.md"]
