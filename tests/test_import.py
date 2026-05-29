"""Phase 0: prove the package and its modules import."""

import ai_dev_orchestrator
from ai_dev_orchestrator.config import Settings, load_settings


def test_package_has_version():
    assert isinstance(ai_dev_orchestrator.__version__, str)
    assert ai_dev_orchestrator.__version__


def test_settings_default_external_providers_disabled():
    # External paid AI providers must be off by default.
    assert Settings().enable_external_providers is False


def test_load_settings_returns_settings():
    assert isinstance(load_settings(), Settings)
