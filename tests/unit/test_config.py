from atlas_ml_platform.config import Settings


def test_defualt_settings():
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.APP_NAME == "Atlas ML Platform"
    assert settings.APP_ENV == "development"
    assert settings.DEBUG is False


def test_custom_settings():
    settings = Settings(_env_file=None, APP_ENV="testing", DEBUG=False)  # pyright: ignore[reportCallIssue]

    assert settings.APP_ENV == "testing"
    assert settings.DEBUG is False
