"""
Prompt templates for MCP tools.

Keep prompt text and message construction centralized so `server.py` stays focused
on tool logic.
"""
from typing import List, Optional

from mcp.server.fastmcp.prompts import base

from .app import mcp
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


@mcp.prompt(title="Collection Research")
def collection_research_prompt(
    research_topic: str, focus_area: Optional[str] = None
) -> List[base.Message]:
    """
    Help users conduct research using Smithsonian collections.

    This prompt provides structured guidance for exploring collections on
    a specific research topic with scholarly depth.

    Args:
        research_topic: Main topic or theme to research
        focus_area: Optional specific aspect to focus on
    """
    focus_text = f" with particular attention to {focus_area}" if focus_area else ""

    return [
        base.Message(
            role="user",
            content=f"I want to conduct scholarly research on '{research_topic}'{focus_text} "
            f"using the Smithsonian collections. Please help me by:\n\n"
            f"1. Searching for relevant objects and artworks related to this topic\n"
            f"2. Identifying which Smithsonian museums have the most relevant materials\n"
            f"3. Suggesting related topics or themes I should also explore\n"
            f"4. Highlighting any objects with high-quality images or 3D models\n"
            f"5. Noting any objects that are CC0 licensed for potential publication use\n\n"
            f"Please provide detailed information about the most significant objects you find, "
            f"including their historical context and scholarly significance.",
        )
    ]


@mcp.prompt(title="Object Analysis")
def object_analysis_prompt(object_id: str) -> List[base.Message]:
    """
    Analyze a specific Smithsonian collection object in detail.

    This prompt helps users get comprehensive analysis of cultural objects
    including historical context, artistic significance, and research applications.

    Args:
        object_id: Unique identifier of the object to analyze
    """
    return [
        base.Message(
            role="user",
            content=f"Please provide a detailed analysis of Smithsonian object ID: {object_id}. "
            f"Include:\n\n"
            f"1. Complete object details and metadata\n"
            f"2. Historical and cultural context\n"
            f"3. Artistic or scientific significance\n"
            f"4. Information about the creator/maker when available\n"
            f"5. Materials, techniques, and physical characteristics\n"
            f"6. Provenance and acquisition history if available\n"
            f"7. Related objects or collections that would be relevant for comparison\n"
            f"8. Potential research applications or scholarly uses\n\n"
            f"If the object has associated images, describe what they show and note "
            f"their quality and licensing status.",
        )
    ]


@mcp.prompt(title="Exhibition Planning")
def exhibition_planning_prompt(
    exhibition_theme: str, target_audience: str = "general public", size: str = "medium"
) -> List[base.Message]:
    """
    Plan an exhibition using Smithsonian collections.

    This prompt helps curators and educators plan exhibitions by finding
    suitable objects and organizing them thematically.

    Args:
        exhibition_theme: Main theme or topic for the exhibition
        target_audience: Intended audience (e.g., "children", "scholars", "general public")
        size: Exhibition size ("small", "medium", "large")
    """
    return exhibition_planning_message(exhibition_theme, target_audience, size)


@mcp.prompt(title="Educational Content")
def educational_content_prompt(
    subject: str,
    grade_level: str = "middle school",
    learning_goals: Optional[str] = None,
) -> List[base.Message]:
    """
    Create educational content using Smithsonian collections.

    This prompt helps educators develop lesson plans, activities, and
    educational materials using museum objects.

    Args:
        subject: Subject area (e.g., "American History", "Art", "Science")
        grade_level: Target grade level or age group
        learning_goals: Optional specific learning objectives
    """
    goals_text = (
        f"\nSpecific learning goals: {learning_goals}" if learning_goals else ""
    )

    return [
        base.Message(
            role="user",
            content=f"Help me create educational content about '{subject}' "
            f"for {grade_level} students using Smithsonian collections.{goals_text}\n\n"
            f"Please:\n\n"
            f"1. Find age-appropriate objects that illustrate key concepts\n"
            f"2. Suggest hands-on activities or discussion questions\n"
            f"3. Provide historical context suitable for the grade level\n"
            f"4. Include objects with clear, high-quality images for visual learning\n"
            f"5. Consider diverse perspectives and inclusive representation\n"
            f"6. Suggest cross-curricular connections when relevant\n"
            f"7. Identify objects that could inspire creative projects\n"
            f"8. Note any 3D models that could enhance digital learning\n\n"
            f"Structure this as a practical lesson plan with clear learning outcomes "
            f"and explain how each selected object supports educational objectives.",
        )
    ]
