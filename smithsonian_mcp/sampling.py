"""
Sampling for explore_topic.

The most relevant matches of a topic are ranked by whether their title, type or
subjects name the topic, then picked across museums in proportion to their share
of the pool and across object types within each museum.
"""

import random
import re
from collections import Counter, deque
from typing import Deque, Dict, List, Tuple

from .models import SmithsonianObject, TopicFacets

# Words of a topic that do not identify it.
_TOPIC_STOP_WORDS = frozenset(
    {"and", "or", "not", "the", "of", "in", "on", "for", "with", "from", "a", "an"}
)
EXPLORE_MAX_TYPE_FACETS = 10


def _type_key(obj: SmithsonianObject) -> str:
    """Case-insensitive object type of an object, for grouping."""
    return (obj.object_type or "").strip().lower()


def _interleave_types(objects: List[SmithsonianObject]) -> Deque[SmithsonianObject]:
    """
    Order objects so that consecutive picks differ in object type.

    Args:
        objects: Objects of one museum, in pool order.

    Returns:
        Deque[SmithsonianObject]: Round-robin order across object types.
    """
    buckets: Dict[str, Deque[SmithsonianObject]] = {}
    for obj in objects:
        buckets.setdefault(_type_key(obj), deque()).append(obj)
    ordered: Deque[SmithsonianObject] = deque()
    while buckets:
        for key in list(buckets):
            ordered.append(buckets[key].popleft())
            if not buckets[key]:
                del buckets[key]
    return ordered


def allocate(groups: Dict[str, List[SmithsonianObject]], limit: int) -> Dict[str, int]:
    """
    Picks per museum, in proportion to its share of the pool, at least one each.

    Museums are served largest first, so when there are more museums than
    picks the smallest get none. Largest remainders settle the rounding.

    Args:
        groups: Pool objects by museum, largest groups first.
        limit: Number of picks.

    Returns:
        Dict[str, int]: Picks per museum.
    """
    total = sum(len(group) for group in groups.values()) or 1
    quota = {code: 0 for code in groups}
    for code in list(groups)[:limit]:
        quota[code] = 1
    remaining = limit - sum(quota.values())
    while remaining > 0:
        open_codes = [code for code in groups if quota[code] < len(groups[code])]
        if not open_codes:
            break
        code = max(
            open_codes,
            key=lambda c: len(groups[c]) / total * limit - quota[c],
        )
        quota[code] += 1
        remaining -= 1
    return quota


def diverse_sample(
    pool: List[SmithsonianObject], limit: int
) -> List[SmithsonianObject]:
    """
    Pick objects across museums in proportion to their share of the pool.

    Within a museum, consecutive picks differ in object type where possible,
    and the pool order (relevance) is kept within each type. The picks are
    then interleaved across museums.

    Args:
        pool: Candidate objects, most relevant first.
        limit: Number of objects to pick.

    Returns:
        List[SmithsonianObject]: The sample.
    """
    groups: Dict[str, List[SmithsonianObject]] = {}
    for obj in pool:
        groups.setdefault(obj.unit_code or "", []).append(obj)
    groups = dict(sorted(groups.items(), key=lambda item: -len(item[1])))
    quota = allocate(groups, limit)
    queues = [
        deque(list(_interleave_types(group))[: quota[code]])
        for code, group in groups.items()
        if quota[code]
    ]
    picks: List[SmithsonianObject] = []
    while any(queues):
        for queue in queues:
            if queue:
                picks.append(queue.popleft())
    return picks[:limit]


def facets(pool: List[SmithsonianObject]) -> TopicFacets:
    """
    Counts by museum and by object type over the sampled pool.

    Args:
        pool: The sampled objects.

    Returns:
        TopicFacets: Museum counts by unit code and the most common types.
    """
    museums = Counter(obj.unit_code for obj in pool if obj.unit_code)
    labels: Dict[str, str] = {}
    types: Counter = Counter()
    for obj in pool:
        key = _type_key(obj)
        if key:
            labels.setdefault(key, obj.object_type.strip()[:1].upper() + key[1:])
            types[key] += 1
    return TopicFacets(
        museums=dict(museums.most_common()),
        object_types={
            labels[key]: count
            for key, count in types.most_common(EXPLORE_MAX_TYPE_FACETS)
        },
    )


def topic_stems(topic: str) -> List[str]:
    """
    Lowercase stems of the words that identify a topic.

    Args:
        topic: Topic keywords, e.g. "space exploration".

    Returns:
        List[str]: Stems such as ["space", "exploration"]; plural "s" dropped.
    """
    stems = []
    for word in re.findall(r"[a-z0-9]+", topic.lower()):
        if word in _TOPIC_STOP_WORDS or len(word) < 3:
            continue
        stems.append(word[:-1] if len(word) > 4 and word.endswith("s") else word)
    return stems


def _topic_score(obj: SmithsonianObject, stems: List[str]) -> int:
    """
    How many topic stems name the object in its title, type or subject topics.

    Free-text search also matches words in places, notes and citations (a
    lichen collected at Dinosaur National Monument matches "dinosaurs"), so
    objects that name the topic in these fields are preferred.

    Args:
        obj: Candidate object.
        stems: Stems from topic_stems.

    Returns:
        int: Number of stems found; stems of four or more letters also match
        longer words ("space" matches "Spacecraft").
    """
    text = " ".join([obj.title or "", obj.object_type or "", *(obj.topics or [])])
    words = re.findall(r"[a-z0-9]+", text.lower())
    return sum(
        1
        for stem in stems
        if any(
            word == stem or (len(stem) >= 4 and word.startswith(stem)) for word in words
        )
    )


def rank_pool(
    pool: List[SmithsonianObject], topic: str
) -> Tuple[List[SmithsonianObject], List[SmithsonianObject]]:
    """
    Split a relevance-ordered pool into objects that name the topic and the rest.

    Objects naming more topic words come first; ties are shuffled so repeated
    calls vary. The rest keep the API's relevance order.

    Args:
        pool: Search results, most relevant first.
        topic: The topic.

    Returns:
        Tuple: (objects naming the topic, other objects).
    """
    stems = topic_stems(topic)
    scored: Dict[int, List[SmithsonianObject]] = {}
    for obj in pool:
        scored.setdefault(_topic_score(obj, stems), []).append(obj)
    named: List[SmithsonianObject] = []
    for score in sorted((score for score in scored if score), reverse=True):
        tier = scored[score]
        random.shuffle(tier)
        named += tier
    return named, scored.get(0, [])
