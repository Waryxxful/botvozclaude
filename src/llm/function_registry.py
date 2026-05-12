from .tools.base_tool import BaseTool
from .tools.save_customer_data import SaveCustomerDataTool
from .tools.transfer_call import TransferCallTool
from .tools.lookup_customer import LookupCustomerTool

_ALL_TOOLS: dict[str, BaseTool] = {
    "save_customer_data": SaveCustomerDataTool(),
    "transfer_call": TransferCallTool(),
    "lookup_customer": LookupCustomerTool(),
}


def get_tools_for_profile(enabled_tool_names: list[str]) -> list[BaseTool]:
    """Retorna instancias de herramientas habilitadas para el perfil actual."""
    return [_ALL_TOOLS[name] for name in enabled_tool_names if name in _ALL_TOOLS]


def get_gemini_function_declarations(tools: list[BaseTool]) -> list[dict]:
    """Convierte herramientas al formato de function declarations para Gemini."""
    return [tool.to_gemini_function() for tool in tools]
