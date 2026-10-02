# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - Unreleased

Version 2.0 replaces the 28 tools of 1.x with 5. Tool names and output shapes change, so prompts, scripts and saved workflows that call 1.x tools need updating. See [Migrating from 1.x](README.md#migrating-from-1x).

### Changed

- The server exposes 5 tools, 2 resources and 5 prompts in place of 28 overlapping tools and 11 prompts:
  - `search_objects`: search with filters, including what is on view now, over objects or, with `record_type="archives"`, archive records.
  - `get_object`: the full record for one object, with images and its web page.
  - `list_museums`: the contributing units with their codes, record types and accepted names.
  - `explore_topic`: a varied sample of a topic for open-ended browsing.
  - `get_collection_stats`: counts of what search can return, for the whole collection or one museum.
  - Resources `smithsonian://museums` and `smithsonian://objects/{object_id}`.
- Results are compact. A search returns 10 short summaries by default instead of full records, object records are capped at 10 images with long text trimmed, and empty fields are left out. Every object carries a `web_url` for its page on the museum website.
- Results carry a `note` that explains empty or doubtful results, such as a query that reads like a sentence or an on-view search that cannot include Natural History, and an object search limited to an archive-only museum returns an error that points to `record_type="archives"`.
- `museum` accepts a museum name or a unit code, and search results report the code that was used. Every distinctive word of a name must match, and "Smithsonian" means every museum.
- The prompts `collection_research`, `object_analysis`, `exhibition_planning`, `educational_content` and `museum_on_view` drop the `_prompt` suffix from their names and use the new tools.
- Asian Art is unit code `NMAA`. `FSG` and names such as "Freer" or "Sackler" are still accepted and map to `NMAA`.
- `is_cc0` on an object means the object has CC0 media that can be reused. Records with CC0 text but restricted or no media are no longer reported as CC0.
- Collection statistics are exact search counts instead of estimates from sampling, so they agree with search results. They take four requests and are cached for 6 hours. The API's statistics endpoint is not used, because its per-museum totals disagree with search by up to 2,000 times.

### Added

- Archive records: the 14 archive-only units, such as the Archives of American Art, and archive records at units such as the Smithsonian Institution Archives can be searched with `record_type="archives"`. Results name the archival collection.
- `explore_topic` prefers objects whose title, type or subjects name the topic and spreads its sample across museums in proportion to their matches.
- Exhibition locations name the building and place, such as the Steven F. Udvar-Hazy Center in Chantilly, VA, instead of a code.
- Images link to a screen-sized image that browsers display, with the full-resolution file as `download_url`.
- `date_from` and `date_to` accept decades such as `"1860s"`, and lowercase `or` and `and` between words work as operators.

### Removed

- All 28 tools from 1.x. The [migration table](README.md#removed-tools) maps each one to its replacement: `search_collections`, `simple_search`, `search_by_unit`, `get_search_context`, `summarize_search_results`, `get_object_ids`, `get_first_object_id`, `find_and_describe`, `search_and_get_first_details`, `search_and_get_details`, `get_object_details`, `get_object_context`, `validate_object_id`, `get_object_url`, `search_and_get_first_url`, `get_smithsonian_units`, `get_units_context`, `resolve_museum_name`, `get_objects_on_view`, `find_on_view_items`, `get_museum_highlights_on_view`, `get_on_view_context`, `simple_explore`, `continue_explore`, `get_collection_statistics`, `get_stats_context`, `get_museum_collection_types` and `check_museum_has_object_type`.
- The prompts `get_object_url_prompt`, `quick_object_lookup_prompt`, `find_object_url_prompt`, `museum_object_search_prompt`, `search_and_get_url_prompt` and `resolve_museum_prompt`, which only restated how to call tools.
- Settings that had no effect: `API_DATA_GOV_BASE_URL`, `ENABLE_CACHE`, `CACHE_TTL_SECONDS`, `DEFAULT_RATE_LIMIT`, `MAX_IMAGE_SIZE_MB` and `SERVER_VERSION`.

### Fixed

- Search filters work. Every filter except the museum was silently ignored, so searches by object type, maker, topic, material, date, images, CC0 status or on-view status returned unfiltered results.
- Asian Art searches use the current code `NMAA`. The retired code `FSG` matched no records.
- Natural History searches cover every department (Botany, Paleobiology, Mineral Sciences and the others). The code `NMNH` on its own matched no records.
- On-view searches are reliable. They used to scan a sample of objects and filter it locally, which missed objects; they now use the API's exhibit field and report each object's exhibition title.
- Object dates, makers, credit lines, rights, dimensions and museum names were always empty. They are now filled in. Makers come from the creator roles a record names, such as artist, manufacturer, photographer, performer or publisher, and leave out sitters, donors and collectors.
- Date filters match by decade. A date without a four-digit year from 1000 to 2999, such as "19th century", is rejected with a message that names the accepted format.
- Titles no longer contain HTML markup.
- A query blocked by the API firewall is reported as a query problem instead of an API key error.
- `python -m smithsonian_mcp.server` exited immediately without serving. The `smithsonian-mcp` command is now the entry point for every install method, and the module entry points start the same server.
- The npm wrapper wrote diagnostics to stdout, which corrupted the MCP stream.
- The server reports its own version to MCP clients instead of the FastMCP version.

### Security

- The API key is sent only in the `X-Api-Key` header. It was sent as a query-string parameter, so request URLs that included it could be written to logs.
- Files the setup scripts generate with the API key in them (`mcpo-config.json`, `.env` backups and variants) are ignored by git.

## [1.2.9]

The last 1.x release, with 28 tools. Earlier changes are not recorded in this file; see the git history.

[2.0.0]: https://github.com/molanojustin/smithsonian-mcp/compare/v1.2.9...HEAD
[1.2.9]: https://github.com/molanojustin/smithsonian-mcp/releases/tag/v1.2.9
