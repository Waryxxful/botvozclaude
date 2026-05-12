"""Test that GeminiClient uses the model from settings (not a hardcoded string)."""

import sys
import types
from unittest.mock import MagicMock, patch


def _install_stub_modules():
    """Stub out all heavy GCP/vertexai modules so gemini_client can be imported."""
    stubs = [
        "structlog",
        "vertexai",
        "vertexai.generative_models",
        "google",
        "google.cloud",
        "google.cloud.firestore",
        "google.cloud.firestore_v1",
        "google.cloud.pubsub_v1",
        "google.cloud.speech",
        "google.cloud.texttospeech",
    ]
    for name in stubs:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # vertexai needs .init callable
    sys.modules["vertexai"].init = MagicMock()

    # vertexai.generative_models needs several classes
    gen_models = sys.modules["vertexai.generative_models"]
    for cls_name in ("GenerativeModel", "GenerationConfig", "Content", "Part", "Tool", "FunctionDeclaration"):
        setattr(gen_models, cls_name, MagicMock())

    # structlog needs get_logger
    sys.modules["structlog"].get_logger = MagicMock(return_value=MagicMock())


def test_gemini_client_uses_configured_model():
    """GeminiClient.__init__ stores the model from settings, not a hardcoded constant."""
    _install_stub_modules()

    # Remove cached module so it reimports cleanly with our stubs
    for mod in list(sys.modules.keys()):
        if "gemini_client" in mod or "function_registry" in mod or "prompt_builder" in mod:
            del sys.modules[mod]

    # Also stub session_state so prompt_builder import works
    session_state_mod = types.ModuleType("src.session.session_state")
    session_state_mod.SessionState = MagicMock()
    sys.modules["src.session"] = types.ModuleType("src.session")
    sys.modules["src.session.session_state"] = session_state_mod

    # Stub function_registry used by gemini_client
    func_reg_mod = types.ModuleType("src.llm.function_registry")
    func_reg_mod.get_tools_for_profile = MagicMock(return_value=[])
    func_reg_mod.get_gemini_function_declarations = MagicMock(return_value=[])
    sys.modules["src.llm.function_registry"] = func_reg_mod

    from config.settings import get_settings
    from src.llm.gemini_client import GeminiClient

    client = GeminiClient()
    assert client._model_id == get_settings().gemini_model
    assert client._model_id == "gemini-2.5-pro"


def test_gemini_client_model_id_from_settings_not_hardcoded():
    """The model id stored in the client matches settings, not the old hardcoded value."""
    _install_stub_modules()

    for mod in list(sys.modules.keys()):
        if "gemini_client" in mod:
            del sys.modules[mod]

    func_reg_mod = types.ModuleType("src.llm.function_registry")
    func_reg_mod.get_tools_for_profile = MagicMock(return_value=[])
    func_reg_mod.get_gemini_function_declarations = MagicMock(return_value=[])
    sys.modules["src.llm.function_registry"] = func_reg_mod

    from config.settings import get_settings
    from src.llm.gemini_client import GeminiClient

    client = GeminiClient()
    # Must NOT be the old hardcoded value
    assert client._model_id != "gemini-2.0-flash-001"
    # Must match what settings says
    assert client._model_id == get_settings().gemini_model
