"""
Tests for translating CollectionSearchFilter into the search ``q`` parameter.

The API has no filter parameter, so every filter must be a fielded term in ``q``.
"""

import re

import pytest

from smithsonian_mcp.api_client import (
    SmithsonianAPIClient,
    build_search_query,
    date_clause,
    maker_clause,
    normalize_free_text_query,
    vocabulary_clause,
    vocabulary_variants,
)
from smithsonian_mcp.models import CollectionSearchFilter

_FIELD_PREFIX_RE = re.compile(r"(?<![\\\w])(?:name|object_type|topic):")
_TERM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|((?:[^\s()"\\*]|\\.)+)\*')


def q(**kwargs) -> str:
    """Build the q parameter for the given filter fields."""
    return build_search_query(CollectionSearchFilter(**kwargs))


def _clause_matches(clause: str, value: str) -> bool:
    """
    Evaluate a clause of exact phrases and prefix wildcards against one index value.

    String fields match a phrase exactly and a wildcard term by literal prefix.
    """
    body = _FIELD_PREFIX_RE.sub("", clause)
    for match in _TERM_RE.finditer(body):
        phrase, prefix = match.groups()
        if phrase is not None and re.sub(r"\\(.)", r"\1", phrase) == value:
            return True
        if prefix is not None and value.startswith(re.sub(r"\\(.)", r"\1", prefix)):
            return True
    return False


class TestFreeText:
    """Free-text query handling."""

    @pytest.mark.parametrize("query", [None, "", "   ", "*", "AND OR NOT"])
    def test_empty_query_becomes_match_all(self, query):
        assert q(query=query) == "*"
        assert q(query=query, unit_code="NMAH") == "* AND unit_code:NMAH"

    def test_single_term_is_unchanged(self):
        assert q(query="landscape") == "landscape"

    def test_query_is_wrapped_when_filters_follow(self):
        assert q(query="muppet", unit_code="NMAH", on_view=True) == (
            '(muppet) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
        )

    def test_boolean_query_keeps_working_with_filters(self):
        assert q(
            query='muppet OR muppets OR henson OR "sesame street"',
            unit_code="NMAH",
            on_view=True,
        ) == (
            '(muppet OR muppets OR henson OR "sesame street") '
            'AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
        )

    def test_implicit_and_is_made_explicit(self):
        # Inside parentheses the API treats whitespace as OR
        assert q(query="bert puppet", unit_code="NMAH") == (
            "(bert AND puppet) AND unit_code:NMAH"
        )

    def test_and_binds_tighter_than_or(self):
        assert normalize_free_text_query("bert puppet OR muppet") == (
            "(bert AND puppet) OR muppet"
        )
        assert normalize_free_text_query("jim AND (henson OR muppet)") == (
            "jim AND (henson OR muppet)"
        )

    def test_top_level_or_without_filters_is_grouped(self):
        # A bare top-level OR is applied as AND by the API
        assert q(query="muppet OR henson") == "(muppet OR henson) AND *"

    def test_not_and_prefix_operators(self):
        assert normalize_free_text_query("dinosaur NOT bone") == "dinosaur AND NOT bone"
        assert normalize_free_text_query("dinosaur -bone") == "dinosaur AND -bone"
        assert normalize_free_text_query("NOT bone") == "NOT bone"

    def test_phrases_fields_and_ranges_are_kept(self):
        assert (
            normalize_free_text_query(
                'name:"Henson, Jim" topic:(Puppets Toys) date:[1950 TO 1960]'
            )
            == 'name:"Henson, Jim" AND topic:(Puppets AND Toys) AND date:[1950 TO 1960]'
        )

    def test_malformed_input_cannot_escape_the_group(self):
        query = q(query="x) OR (*", unit_code="NMAH")
        assert query == "(x AND *) AND unit_code:NMAH"
        assert normalize_free_text_query('unbalanced "quote (paren') == (
            "unbalanced AND quote AND paren"
        )
        assert normalize_free_text_query("muppet AND") == "muppet"
        assert normalize_free_text_query("[sic] item") == r"\[sic\] AND item"

    @pytest.mark.parametrize(
        "query,expected",
        [
            # Words without letters or digits would be required terms matching nothing
            ("Lewis & Clark", "Lewis AND Clark"),
            ("rock & roll", "rock AND roll"),
            ("Procter & Gamble", "Procter AND Gamble"),
            ("Kermit — Muppets", "Kermit AND Muppets"),
            # A colon followed by a space is punctuation, not a field or a term
            ("Star Wars : A New Hope", "Star AND Wars AND A AND New AND Hope"),
            ("Star Wars: A New Hope", "Star AND Wars AND A AND New AND Hope"),
            # "?" is a single-character wildcard, so "Diamond?" matches nothing
            (
                "What is the Hope Diamond?",
                r"What AND is AND the AND Hope AND Diamond\?",
            ),
            (
                "Who made the Star Spangled Banner?",
                r"Who AND made AND the AND Star AND Spangled AND Banner\?",
            ),
            ("hello!", r"hello\!"),
            ("& — : ?", None),
        ],
    )
    def test_punctuation(self, query, expected):
        assert normalize_free_text_query(query) == expected

    def test_punctuation_keeps_terms_with_letters_or_digits(self):
        assert (
            normalize_free_text_query("AT&T R2-D2 50% *")
            == "AT&T AND R2-D2 AND 50% AND *"
        )
        assert normalize_free_text_query("*:*") == "*:*"
        assert normalize_free_text_query("name:Henson:") == "name:Henson"
        assert q(query="Lewis & Clark", unit_code="NMAH") == (
            "(Lewis AND Clark) AND unit_code:NMAH"
        )


class TestFilters:
    """Each CollectionSearchFilter field maps to a fielded clause."""

    def test_unit_code(self):
        assert q(unit_code="SAAM") == "* AND unit_code:SAAM"

    def test_unit_code_nmnh_wildcard(self):
        assert q(query="dinosaur", unit_code="NMNH") == (
            "(dinosaur) AND unit_code:NMNH*"
        )

    def test_unit_code_legacy_and_case(self):
        assert q(unit_code="FSG") == "* AND unit_code:NMAA"
        assert q(unit_code="NMAFA") == "* AND unit_code:NMAfA"

    def test_object_type_variants(self):
        assert vocabulary_variants("Paintings")[:2] == ["Paintings", "Painting"]
        assert "Certified Proof" in vocabulary_variants("certified proof")
        assert "Bodies" in vocabulary_variants("body")
        assert vocabulary_clause("object_type", "puppet") == (
            'object_type:("puppet" OR "puppets" OR "Puppet" OR "Puppets"'
            r" OR puppet\ \(* OR puppet\,* OR puppet;* OR puppet\/* OR puppet\ \/*"
            r" OR puppet\:* OR puppets\ \(* OR puppets\,* OR puppets;* OR puppets\/*"
            r" OR puppets\ \/* OR puppets\:* OR Puppet\ \(* OR Puppet\,* OR Puppet;*"
            r" OR Puppet\/* OR Puppet\ \/* OR Puppet\:* OR Puppets\ \(* OR Puppets\,*"
            r" OR Puppets;* OR Puppets\/* OR Puppets\ \/* OR Puppets\:*)"
        )
        assert vocabulary_clause("object_type", "  ") is None

    @pytest.mark.parametrize(
        "value,matches,rejects",
        [
            # Index terms are qualified; the exact value alone matched nothing
            (
                "dress",
                ["Dresses (garments)", "Dress, 1-Piece"],
                ["Dressers", "dress silk"],
            ),
            ("coin", ["Coins (money)", "coin; proof"], ["Coin purse", "Coinage"]),
            ("painting", ["Paintings", "Painting/Drawing/Print"], ["Painting tool"]),
            (
                "camera",
                ["Cameras (photographic equipment)", "Camera; Rollfilm"],
                ["Camera Back"],
            ),
            ("hat", ["Hats", "Hat, Straw", "Hat/cap"], ["Hatchets", "Hatpins"]),
            ("letter", ["Letters (correspondence)", "Letter; Navy"], ["Letterpress"]),
            ("cup", ["Cups", "Cup/Mug", "Cup, Coffee"], ["Cupboards", "Cup Plate"]),
            ("art", ["Art, Indic"], ["Articles", "Artist files", "Artifacts"]),
        ],
    )
    def test_object_type_matches_qualified_terms_only(self, value, matches, rejects):
        clause = vocabulary_clause("object_type", value)
        for term in matches:
            assert _clause_matches(clause, term), term
        for term in rejects:
            assert not _clause_matches(clause, term), term

    def test_maker(self):
        assert maker_clause("Winslow Homer") == (
            '(name:"Winslow Homer" OR name:"Homer, Winslow"'
            r" OR name:Winslow\ Homer\ * OR name:Winslow\ Homer\,*"
            r" OR name:Winslow\ Homer\-* OR name:Winslow\ Homer\/*"
            r" OR name:Winslow\ Homer's* OR name:Homer\,\ Winslow\ *"
            r" OR name:Homer\,\ Winslow\,*)"
        )
        assert maker_clause("Homer, Winslow") == (
            r'(name:"Homer, Winslow" OR name:Homer\,\ Winslow\ *'
            r" OR name:Homer\,\ Winslow\,*)"
        )
        assert maker_clause("  ") is None

    @pytest.mark.parametrize(
        "maker,matches,rejects",
        [
            (
                "Alma Thomas",
                ["Thomas, Alma", "Thomas, Alma Woodsey"],
                ["Thomas, Almanzo"],
            ),
            ("alma thomas", ["Thomas, Alma"], []),
            (
                "Martin Luther King Jr.",
                ["King, Martin Luther", "King, Martin Luther, Jr."],
                [],
            ),
            (
                "Wright Brothers",
                ["Wright Brothers, Dayton, Ohio"],
                ["Wright Brothersville"],
            ),
            (
                "Lockheed",
                ["Lockheed Aircraft Corporation", "Lockheed-Georgia Company"],
                ["Lockheedia"],
            ),
            ("Smith", ["Smith, A. C.", "Smith Corona"], ["Smithsonian Institution"]),
            ("Colt", ["Colt, Samuel", "Colt's Patent Firearms"], ["Coltrane, John"]),
            ("Mathew Brady", ["Brady, Mathew B.", "Mathew Brady Studio"], []),
            ("Jim Henson", ["Henson, Jim", "Jim Henson Company"], ["Henson, Jane"]),
        ],
    )
    def test_maker_matches(self, maker, matches, rejects):
        clause = maker_clause(maker)
        for name in matches:
            assert _clause_matches(clause, name), name
        for name in rejects:
            assert not _clause_matches(clause, name), name

    def test_maker_suffixes_are_dropped_before_inverting(self):
        for suffix in ("Jr.", "Jr", "Sr.", "II", "III", "IV", ", Jr."):
            clause = maker_clause(f"Martin Luther King {suffix}")
            assert 'name:"King, Martin Luther"' in clause, suffix

    def test_topic(self):
        clause = vocabulary_clause("topic", "civil war", narrower=True)
        assert q(topic="civil war") == f"* AND {clause}"
        for term in [
            "Civil War",
            "Civil War, 1861-1865",
            "Civil War and Reconstruction (1860-1877)",
        ]:
            assert _clause_matches(clause, term), term
        african_american = vocabulary_clause("topic", "African American", narrower=True)
        assert _clause_matches(african_american, "African American women")
        war = vocabulary_clause("topic", "war", narrower=True)
        assert _clause_matches(war, "War of 1812")
        assert not _clause_matches(war, "Warships")
        assert _clause_matches(
            vocabulary_clause("topic", "dinosaur", narrower=True), "Dinosaurs"
        )

    def test_material(self):
        assert q(material="oil on canvas") == (
            '* AND physicalDescription:"oil on canvas"'
        )

    def test_dates(self):
        # Decades are listed explicitly: date ranges compare text, so
        # ["1860s" TO *] also matched "300s" and "BCE" values
        decades = 'date:("1940s" OR "1950s" OR "1960s")'
        assert date_clause("1943", "1967") == decades
        assert date_clause("1967-05-01", "c. 1943") == decades
        assert q(date_start="1950", date_end="1959") == '* AND date:"1950s"'
        assert date_clause(None, None) is None
        assert date_clause("", "  ") is None

    def test_open_date_ranges_are_clamped(self, monkeypatch):
        import smithsonian_mcp.api_client as api_client

        class FixedDatetime(api_client.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 1, tzinfo=tz)

        monkeypatch.setattr(api_client, "datetime", FixedDatetime)
        assert (
            date_clause("1990", None)
            == 'date:("1990s" OR "2000s" OR "2010s" OR "2020s")'
        )
        assert date_clause("2900", None) == 'date:"2900s"'
        start_open = date_clause(None, "1030")
        assert start_open == 'date:("1000s" OR "1010s" OR "1020s" OR "1030s")'
        widest = date_clause("1000", None)
        assert widest.count(" OR ") == 102 and widest.endswith('"2020s")')
        assert len(widest) < 1200

    @pytest.mark.parametrize(
        "date_start,date_end",
        [
            ("19th century", None),
            ("500", None),
            (None, "500 BC"),
            ("1900", "3000"),
            ("circa", None),
        ],
    )
    def test_invalid_dates_raise(self, date_start, date_end):
        with pytest.raises(ValueError, match="four-digit year between 1000 and 2999"):
            date_clause(date_start, date_end)
        with pytest.raises(ValueError):
            q(date_start=date_start, date_end=date_end)

    def test_boolean_filters(self):
        assert q(has_images=True) == '* AND online_media_type:"Images"'
        assert q(is_cc0=True) == '* AND media_usage:"CC0"'
        assert q(on_view=True) == '* AND onPhysicalExhibit:"Yes"'
        assert q(on_view=False) == '* AND (* NOT onPhysicalExhibit:"Yes")'
        # False means "no filter" for images and CC0
        assert q(has_images=False, is_cc0=False) == "*"

    def test_all_filters_combined(self):
        query = q(
            query="portrait",
            unit_code="NPG",
            object_type="Paintings",
            maker="Homer, Winslow",
            topic="Portraits",
            material="oil",
            date_start="1880",
            date_end="1890",
            has_images=True,
            is_cc0=True,
            on_view=True,
        )
        assert query == " AND ".join(
            [
                "(portrait)",
                "unit_code:NPG",
                vocabulary_clause("object_type", "Paintings"),
                maker_clause("Homer, Winslow"),
                vocabulary_clause("topic", "Portraits", narrower=True),
                'physicalDescription:"oil"',
                date_clause("1880", "1890"),
                'online_media_type:"Images"',
                'media_usage:"CC0"',
                'onPhysicalExhibit:"Yes"',
            ]
        )
        # Every filter combined still makes a short enough URL
        assert len(query) < 2500


class TestEscaping:
    """User input cannot break out of quoted filter values."""

    def test_quotes_and_backslashes_are_escaped(self):
        clause = vocabulary_clause("object_type", 'Paint"ings')
        assert clause.startswith(r'object_type:("Paint\"ings" OR "Paint\"ing"')
        assert r"Paint\"ings\ \(*" in clause
        # Every unescaped quote is paired, so the value cannot end a phrase early
        assert re.sub(r"\\.", "", clause).count('"') % 2 == 0
        assert q(material="a\\b") == r'* AND physicalDescription:"a\\b"'

    def test_injection_attempt_stays_inside_phrase(self):
        clause = maker_clause('Homer" OR unit_code:"SAAM')
        assert clause == (
            r'(name:"Homer\" OR unit_code:\"SAAM" OR name:"Homer\" OR Unit_code:\"SAAM")'
        )

    def test_whitespace_is_collapsed(self):
        assert q(material="  oil \n on\tcanvas ") == (
            '* AND physicalDescription:"oil on canvas"'
        )


class TestSearchParams:
    """Pagination parameters."""

    @pytest.mark.parametrize(
        "limit,rows",
        [(20, 20), (1000, 1000), (1001, 1000), (5000, 1000), (0, 0), (-5, 0)],
    )
    def test_rows_are_clamped(self, limit, rows):
        client = SmithsonianAPIClient(api_key="test")
        params = client._build_search_params(CollectionSearchFilter(limit=limit))
        assert params["rows"] == rows

    def test_negative_offset_becomes_zero(self):
        client = SmithsonianAPIClient(api_key="test")
        params = client._build_search_params(CollectionSearchFilter(offset=-3))
        assert params["start"] == 0

    def test_no_fq_and_no_key_in_params(self):
        client = SmithsonianAPIClient(api_key="test")
        params = client._build_search_params(
            CollectionSearchFilter(query="x", object_type="Paintings", on_view=True)
        )
        assert set(params) == {"q", "start", "rows"}

    @pytest.mark.parametrize(
        "sort,expected", [(None, None), ("relevancy", None), ("random", "random")]
    )
    def test_sort_is_sent_only_when_not_default(self, sort, expected):
        client = SmithsonianAPIClient(api_key="test")
        params = client._build_search_params(CollectionSearchFilter(sort=sort))
        assert params.get("sort") == expected

    def test_unknown_sort_is_rejected(self):
        with pytest.raises(ValueError):
            CollectionSearchFilter(sort="title")
