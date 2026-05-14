"""Shim — loads BotProfileSchema from BOT_VOZ by file path to avoid package name conflicts."""

import importlib.util
import sys
from pathlib import Path

_f = Path(__file__).resolve().parent.parent.parent.parent / "config" / "bot_profiles" / "schema.py"
_spec = importlib.util.spec_from_file_location("config.bot_profiles.schema", str(_f))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["config.bot_profiles.schema"] = _mod
_spec.loader.exec_module(_mod)

BotProfileSchema = _mod.BotProfileSchema
GuardrailConfig = _mod.GuardrailConfig
MemoryConfig = _mod.MemoryConfig
ToolsConfig = _mod.ToolsConfig
