"""
Prompt templates for common research tasks with the Smithsonian collections.

Each prompt describes a task and names the tools to use for it; the tools
themselves are documented in the server instructions and tool descriptions.
"""

from typing import Annotated, List, Literal, Optional

from fastmcp import FastMCP
from fastmcp.prompts import Message
from pydantic import Field

from .constants import (
    MINUTES_PER_OBJECT,
    SESSION_MAX_MINUTES,
    SESSION_MIN_MINUTES,
    SESSION_OVERHEAD_MINUTES,
    SIZE_GUIDELINES,
)
from .tools import summary_of


def collection_research(
    research_topic: str, focus_area: Optional[str] = None
) -> List[Message]:
    """
    Research a topic across the Smithsonian collections.

    Args:
        research_topic: Main topic or theme to research.
        focus_area: Optional aspect to focus on.

    Returns:
        List[Message]: The prompt messages.
    """
    focus = f", focusing on {focus_area}" if focus_area else ""
    return [
        Message(
            f"I want to research '{research_topic}'{focus} using the Smithsonian "
            "Open Access collections. Please:\n\n"
            "1. Use explore_topic to see which museums and object types hold "
            "relevant material.\n"
            "2. Use search_objects with a few distinctive keywords and filters "
            "(museum, object_type, maker, date_from/date_to) to find the most "
            "relevant objects.\n"
            "3. Use get_object on the most significant finds for descriptions, "
            "provenance and images.\n"
            "4. Note which objects have CC0 media that can be reused.\n\n"
            "Summarize the key objects with their historical context and "
            "significance, and link each one with its web_url."
        )
    ]


def object_analysis(object_id: str) -> List[Message]:
    """
    Analyze one collection object in depth.

    Args:
        object_id: Id of the object, from search results.

    Returns:
        List[Message]: The prompt messages.
    """
    return [
        Message(
            f"Use get_object with object_id '{object_id}' and give a detailed "
            "analysis of the object:\n\n"
            "1. What it is, who made it, when and where.\n"
            "2. Historical and cultural context.\n"
            "3. Artistic, technical or scientific significance.\n"
            "4. Materials, techniques and physical characteristics.\n"
            "5. Provenance and credit line, where available.\n"
            "6. What its images show, and whether they are CC0.\n"
            "7. Related objects worth comparing; find them with search_objects "
            "(for example by maker or topic).\n\n"
            "Link the object with its web_url."
        )
    ]


def exhibition_planning(
    exhibition_theme: str,
    target_audience: str = "general public",
    size: Literal["small", "medium", "large"] = "medium",
) -> List[Message]:
    """
    Plan an exhibition from Smithsonian objects.

    Args:
        exhibition_theme: Main theme or topic of the exhibition.
        target_audience: Intended audience, e.g. "children" or "scholars".
        size: "small" (15-25 objects), "medium" (30-50) or "large" (60+).

    Returns:
        List[Message]: The prompt messages.
    """
    object_count = SIZE_GUIDELINES[size]
    return [
        Message(
            f"Help me plan a {size} exhibition on '{exhibition_theme}' for "
            f"{target_audience}, with about {object_count}. Please:\n\n"
            "1. Use explore_topic to survey the theme across museums, then "
            "search_objects (with has_images=true) to find candidate objects.\n"
            "2. Organize the objects into thematic sections with a narrative "
            "flow.\n"
            "3. Pick highlights and centerpieces, and use get_object for their "
            "details and images.\n"
            "4. Include diverse perspectives where the collections allow.\n"
            "5. Flag objects with CC0 media for marketing materials.\n"
            "6. Note which objects are already on view (on_view) and where.\n\n"
            "Explain why each key object suits the exhibition, and link it with "
            "its web_url."
        )
    ]


def _lesson_object_count(session_minutes: int) -> str:
    """
    How many objects a teaching session has time for, such as "2-3 objects".

    Args:
        session_minutes: Length of the session in minutes.

    Returns:
        str: The object count, as text.
    """
    teaching = max(session_minutes - SESSION_OVERHEAD_MINUTES, 0)
    quickest, slowest = MINUTES_PER_OBJECT
    fewest = max(1, teaching // slowest)
    most = max(1, teaching // quickest)
    if most == 1:
        return "1 object"
    if fewest == most:
        return f"{most} objects"
    return f"{fewest}-{most} objects"


def educational_content(
    subject: str,
    grade_level: str = "middle school",
    learning_goals: Optional[str] = None,
    session_minutes: Optional[
        Annotated[int, Field(ge=SESSION_MIN_MINUTES, le=SESSION_MAX_MINUTES)]
    ] = None,
) -> List[Message]:
    """
    Create a lesson built around Smithsonian objects.

    Args:
        subject: Subject area, e.g. "American History", "Art" or "Science".
        grade_level: Target grade level or age group.
        learning_goals: Optional learning objectives.
        session_minutes: Optional session length in minutes; sets the object count.

    Returns:
        List[Message]: The prompt messages.
    """
    goals = f"\nLearning goals: {learning_goals}" if learning_goals else ""
    timing = ""
    agenda = ""
    if session_minutes is not None:
        timing = (
            f"\nThe session lasts {session_minutes} minutes, so feature about "
            f"{_lesson_object_count(session_minutes)}, the ones that best "
            "illustrate the key concepts, and leave time for an introduction and "
            "wrap-up."
        )
        agenda = f" and a timed agenda for the {session_minutes} minutes"
    return [
        Message(
            f"Help me create educational content about '{subject}' for "
            f"{grade_level} students using Smithsonian collections.{goals}"
            f"{timing}\n\n"
            "1. Use explore_topic and search_objects (has_images=true) to find "
            "age-appropriate objects that illustrate key concepts.\n"
            "2. Use get_object for the context of the objects you choose.\n"
            "3. Suggest activities and open-ended discussion questions.\n"
            "4. Add cross-curricular connections and creative projects.\n"
            "5. Prefer objects with CC0 images for classroom handouts.\n\n"
            f"Structure it as a lesson plan with clear learning outcomes{agenda}, "
            "and link each object with its web_url."
        )
    ]


def museum_on_view(museum: str, topic: Optional[str] = None) -> List[Message]:
    """
    Find out what is on display at a museum now.

    Args:
        museum: Museum name or unit code, e.g. "American History" or "NMAH".
        topic: Optional topic to narrow the objects.

    Returns:
        List[Message]: The prompt messages.
    """
    about = f" about {topic}" if topic else ""
    query = f" and query='{topic}'" if topic else ""
    return [
        Message(
            f"What is on view at {museum}{about}? Use search_objects with "
            f"museum='{museum}' and on_view=true{query}, and follow next_offset "
            "if there are more results. Group the objects by exhibition_title, "
            "say where each exhibition is (exhibition_location), and link the "
            "objects with their web_url. If the tool returns a note, explain it."
        )
    ]


PROMPTS = (
    (collection_research, "Collection Research"),
    (object_analysis, "Object Analysis"),
    (exhibition_planning, "Exhibition Planning"),
    (educational_content, "Educational Content"),
    (museum_on_view, "Museum On View"),
)


def register_prompts(server: FastMCP) -> None:
    """
    Register the prompt templates on a server.

    Args:
        server: The FastMCP server.
    """
    for function, title in PROMPTS:
        server.prompt(function, title=title, description=summary_of(function))
