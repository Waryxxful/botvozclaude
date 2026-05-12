from src.session.session_state import SessionState


def build_system_prompt(session: SessionState) -> str:
    """Construye el system prompt completo para el turno actual.

    Combina:
    - Prompt base del perfil de bot
    - Guardrails configurados
    - Contexto del cliente (si disponible)
    """
    profile = session.bot_profile
    parts = [profile.system_prompt.strip()]

    # Contexto del cliente
    if session.customer_name:
        parts.append(f"\nEl cliente se llama {session.customer_name}.")

    if session.customer_data:
        relevant = {k: v for k, v in session.customer_data.items() if v and k != "issue"}
        if relevant:
            data_str = ", ".join(f"{k}: {v}" for k, v in relevant.items())
            parts.append(f"Datos del cliente registrados: {data_str}.")

    # Guardrails explícitos
    if profile.guardrails.forbidden_topics:
        topics = ", ".join(profile.guardrails.forbidden_topics)
        parts.append(
            f"\nIMPORTANTE — Temas prohibidos: NO debes hablar sobre {topics}. "
            "Si el cliente los menciona, redirige amablemente la conversación."
        )

    return "\n".join(parts)
