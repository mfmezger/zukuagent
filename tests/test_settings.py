from zukuagent.core.settings import Settings


def test_csv_list_parsing():
    settings = Settings(
        telegram_allowed_chat_ids="1, 2,3",
        telegram_allowed_pairing_devices="dev-a, dev-b",
        identity_files="IDENTITY.md,SOUL.md",
        openlit_enabled="true",
    )

    assert settings.telegram_allowed_chat_ids == [1, 2, 3]
    assert settings.telegram_allowed_pairing_devices == ["dev-a", "dev-b"]
    assert settings.identity_files == ["IDENTITY.md", "SOUL.md"]
    assert settings.openlit_enabled is True


def test_list_inputs_are_preserved():
    settings = Settings(
        telegram_allowed_chat_ids=[10, 20],
        telegram_allowed_pairing_devices=["dev-1", "dev-2"],
        identity_files=["IDENTITY.md"],
        telegram_require_pairing=False,
    )

    assert settings.telegram_allowed_chat_ids == [10, 20]
    assert settings.telegram_allowed_pairing_devices == ["dev-1", "dev-2"]
    assert settings.identity_files == ["IDENTITY.md"]
    assert settings.telegram_require_pairing is False
