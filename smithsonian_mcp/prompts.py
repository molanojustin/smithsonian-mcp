"""
Prompt templates for MCP tools.

Keep prompt text and message construction centralized so `server.py` stays focused
on tool logic.
"""
from typing import List
from mcp.server.fastmcp.prompts import base
from .constants import SIZE_GUIDELINES


def exhibition_planning_message(
    exhibition_theme: str, target_audience: str = "general public", size: str = "medium"
) -> List[base.Message]:
    """
    Build the exhibition planning prompt message(s).
    """
    content = (
        "Help me plan a %s exhibition on '%s' for %s. "
        "I need approximately %s objects. Please:\n\n"
        "1. Search for relevant objects across different Smithsonian museums\n"
        "2. Organize findings into thematic sections or galleries\n"
        "3. Prioritize objects with high-quality images for exhibition materials\n"
        "4. Include diverse perspectives and representations when possible\n"
        "5. Suggest a logical flow or narrative structure\n"
        "6. Note any objects that could serve as highlights or centerpieces\n"
        "7. Consider educational value appropriate for the target audience\n"
        "8. Identify objects that are CC0 licensed for marketing materials\n\n"
        "Provide detailed information about key objects and explain why they "
        "would be effective for this exhibition concept."
    ) % (size, exhibition_theme, target_audience, SIZE_GUIDELINES.get(size, "30-50"))

    return [base.Message(role="user", content=content)]
