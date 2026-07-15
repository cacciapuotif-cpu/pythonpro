"""Prompt versionati per gli agenti LLM.

Ogni modulo espone PROMPT_VERSION, SYSTEM_PROMPT e build_user_prompt(...).
La versione viene registrata nei risultati (es. DocumentResult.prompt_version)
e nel log strutturato delle chiamate LLM.
"""
