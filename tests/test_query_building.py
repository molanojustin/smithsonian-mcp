"""
Tests for translating CollectionSearchFilter into the search ``q`` parameter.

The API has no filter parameter, so every filter must be a fielded term in ``q``.
"""

import pytest

from smithsonian_mcp.api_client import (
    SmithsonianAPIClient,
    build_search_query,
    date_clause,
    maker_clause,
    normalize_free_text_query,
    vocabulary_variants,
)
from smithsonian_mcp.models import CollectionSearchFilter


def q(**kwargs) -> str:
    """Build the q parameter for the given filter fields."""
    return build_search_query(CollectionSearchFilter(**kwargs))


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
        assert q(query="landscape", object_type="painting") == (
            '(landscape) AND object_type:("painting" OR "paintings" '
            'OR "Painting" OR "Paintings")'
        )
        assert vocabulary_variants("Paintings")[:2] == ["Paintings", "Painting"]
        assert "Certified Proof" in vocabulary_variants("certified proof")
        assert "Bodies" in vocabulary_variants("body")

    def test_maker(self):
        assert maker_clause("Winslow Homer") == (
            '(name:"Winslow Homer" OR name:"Homer, Winslow" '
            r"OR name:Homer\,\ Winslow*)"
        )
        assert maker_clause("alma thomas") == (
            '(name:"alma thomas" OR name:"Alma Thomas" OR name:"Thomas, Alma" '
            r'OR name:"thomas, alma" OR name:Thomas\,\ Alma*)'
        )
        assert maker_clause("Homer, Winslow") == (
            r'(name:"Homer, Winslow" OR name:Homer\,\ Winslow*)'
        )
        assert maker_clause("Rembrandt") == (r'(name:"Rembrandt" OR name:Rembrandt\,*)')
        assert maker_clause("  ") is None

    def test_topic(self):
        assert q(topic="Puppets") == (
            '* AND topic:("Puppets" OR "Puppet" OR "puppets" OR "puppet")'
        )

    def test_material(self):
        assert q(material="oil on canvas") == (
            '* AND physicalDescription:"oil on canvas"'
        )

    def test_dates(self):
        assert date_clause("1943", "1967") == 'date:["1940s" TO "1960s"]'
        assert date_clause("1967-05-01", "c. 1943") == 'date:["1940s" TO "1960s"]'
        assert date_clause("1900", None) == 'date:["1900s" TO *]'
        assert date_clause(None, "1800s") == 'date:[* TO "1800s"]'
        assert date_clause("500 BC", None) is None
        assert date_clause(None, None) is None
        assert (
            q(date_start="1950", date_end="1959") == '* AND date:["1950s" TO "1950s"]'
        )

    def test_boolean_filters(self):
        assert q(has_images=True) == '* AND online_media_type:"Images"'
        assert q(is_cc0=True) == '* AND media_usage:"CC0"'
        assert q(on_view=True) == '* AND onPhysicalExhibit:"Yes"'
        assert q(on_view=False) == '* AND (* NOT onPhysicalExhibit:"Yes")'
        # False means "no filter" for images and CC0
        assert q(has_images=False, is_cc0=False) == "*"

    def test_all_filters_combined(self):
        assert q(
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
        ) == (
            "(portrait) AND unit_code:NPG"
            ' AND object_type:("Paintings" OR "Painting" OR "paintings" OR "painting")'
            r' AND (name:"Homer, Winslow" OR name:Homer\,\ Winslow*)'
            ' AND topic:("Portraits" OR "Portrait" OR "portraits" OR "portrait")'
            ' AND physicalDescription:"oil"'
            ' AND date:["1880s" TO "1890s"]'
            ' AND online_media_type:"Images" AND media_usage:"CC0"'
            ' AND onPhysicalExhibit:"Yes"'
        )


class TestEscaping:
    """User input cannot break out of quoted filter values."""

    def test_quotes_and_backslashes_are_escaped(self):
        assert q(object_type='Paint"ings') == (
            r'* AND object_type:("Paint\"ings" OR "Paint\"ing" '
            r'OR "paint\"ings" OR "paint\"ing")'
        )
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
