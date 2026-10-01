# Smithsonian Open Access MCP Server

[![npm version](https://badge.fury.io/js/%40molanojustin%2Fsmithsonian-mcp.svg)](https://badge.fury.io/js/%40molanojustin%2Fsmithsonian-mcp)
[![NPM Downloads](https://img.shields.io/npm/dm/%40molanojustin%2Fsmithsonian-mcp)](https://www.npmjs.com/package/@molanojustin%2Fsmithsonian-mcp)
[![Docker](https://img.shields.io/docker/pulls/justinmol/smithsonian-mcp?logo=docker&label=Docker)](https://hub.docker.com/r/justinmol/smithsonian-mcp)

A Model Context Protocol (MCP) server for the Smithsonian Institution's Open Access collections. It lets AI assistants such as Claude Desktop search more than 14 million records from Smithsonian museums, libraries and research centers, find out what is on display now, and fetch full object records with images and links to the museum websites.

Ask, for example:

> Which Muppets are on display right now at the National Museum of American History?

The assistant calls `search_objects(query="muppet", museum="American History", on_view=true)` and finds the objects currently on view, such as:

| Objects | Exhibition |
|---|---|
| Elmo, Fozzie Bear, Oscar the Grouch and Rosita puppets | Entertainment Nation |
| Oscar the Grouch's trash can and Mr. Hooper's costume from Sesame Street | Entertainment Nation |
| The Muppets lunch box (1979) | Taking America To Lunch |

Version 2.0 replaces the 28 tools of version 1.x with 5. See [Migrating from 1.x](#migrating-from-1x) and the [changelog](CHANGELOG.md).

## Contents

- [Quick Start](#quick-start)
- [Tools](#tools)
- [Resources](#resources)
- [Prompts](#prompts)
- [Search tips](#search-tips)
- [Migrating from 1.x](#migrating-from-1x)
- [Integration](#integration)
- [Requirements](#requirements)
- [Testing](#testing)
- [Service Management](#service-management)
- [Troubleshooting](#troubleshooting)

## Quick Start

You need:

- A free API key from [api.data.gov/signup](https://api.data.gov/signup/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/). uv downloads a compatible Python (3.10 or newer) if one is not already installed.

The server speaks MCP over stdio. MCP clients such as Claude Desktop start it on demand; you do not run it in the background yourself.

### Claude Desktop with uvx (recommended)

Add this to `claude_desktop_config.json`. It installs and runs the server straight from the GitHub repository, with no clone or virtual environment to manage:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/molanojustin/smithsonian-mcp",
        "smithsonian-mcp"
      ],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop, then ask "What Smithsonian museums are available?"

Notes:

- The package is not published on PyPI, so `--from` points uvx at the GitHub repository. Append `@<tag or commit>` to the URL to pin a version.
- uvx caches the build. To pick up newer commits, run `uvx --refresh --from git+https://github.com/molanojustin/smithsonian-mcp smithsonian-mcp` once in a terminal.
- If Claude Desktop reports that `uvx` cannot be found, use its absolute path as the `command` (`which uvx` on macOS/Linux, `where uvx` on Windows).

### Other ways to run the server

All of these start the same `smithsonian-mcp` command and take the API key from the same `env` block.

#### npm/npx

The npm package is a small Node.js wrapper that uses uv to install the Python dependencies on first start. It requires Node.js 16 or newer and uv:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "npx",
      "args": ["-y", "@molanojustin/smithsonian-mcp"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

You can also install it globally with `npm install -g @molanojustin/smithsonian-mcp` and run `smithsonian-mcp`. Run `smithsonian-mcp --test` to check your API key and connection.

The wrapper keeps the Python environment in a per-user cache directory, one per package version: `~/Library/Caches/smithsonian-mcp` on macOS, `~/.cache/smithsonian-mcp` (or `$XDG_CACHE_HOME`) on Linux, and `%LOCALAPPDATA%\smithsonian-mcp` on Windows. Set `UV_PROJECT_ENVIRONMENT` to use a different location. Older versions' environments there can be deleted safely.

#### From a local clone

```bash
git clone https://github.com/molanojustin/smithsonian-mcp.git
cd smithsonian-mcp
uv sync
```

`uv sync` creates `.venv` from `uv.lock` and installs the `smithsonian-mcp` command into it. Point Claude Desktop at the clone:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/smithsonian-mcp", "run", "smithsonian-mcp"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

Alternatively, use the installed command directly as `"command": "/absolute/path/to/smithsonian-mcp/.venv/bin/smithsonian-mcp"` (on Windows, `.venv\Scripts\smithsonian-mcp.exe`) with no `args`.

#### Python virtual environment without uv

Requires Python 3.10 or newer:

```bash
git clone https://github.com/molanojustin/smithsonian-mcp.git
cd smithsonian-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

Then use `/absolute/path/to/smithsonian-mcp/.venv/bin/smithsonian-mcp` as the `command`. This installs the newest compatible dependencies rather than the versions pinned in `uv.lock`.

#### Docker

Build the image from a clone. The `-i` flag keeps stdin open for the stdio transport, and `-e SMITHSONIAN_API_KEY` passes the key from the `env` block into the container:

```bash
docker build -t smithsonian-mcp .
```

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "SMITHSONIAN_API_KEY", "smithsonian-mcp"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Automated Setup Scripts

For a local clone, the setup scripts install dependencies (with `uv sync` when uv is available, otherwise a Python 3.10+ virtual environment and pip), validate your API key and save it to `.env`, and can optionally add the server to your Claude Desktop config, generate an mcpo config and run a health check.

**macOS/Linux:**

```bash
chmod +x config/setup.sh
config/setup.sh
```

**Windows:**

```powershell
config\setup.ps1
```

### API Key in `.env`

When you run the server from a clone, it also reads `SMITHSONIAN_API_KEY` from a `.env` file in the project root. Copy `.env.example` to `.env` and set your key. A key set in the MCP client's `env` block takes precedence.

### Verify Setup

Check an installation from a clone:

```bash
uv run python examples/test-api-connection.py
uv run python scripts/verify-setup.py
```

## Tools

All five tools are read-only.

| Tool | Use it to |
|---|---|
| [`search_objects`](#search_objects) | Find objects by keyword and filters, including what is on view now |
| [`get_object`](#get_object) | Get the full record, images and web page of one object |
| [`list_museums`](#list_museums) | See which museums contribute, with their codes and record counts |
| [`explore_topic`](#explore_topic) | Browse a varied sample of a topic across museums |
| [`get_collection_stats`](#get_collection_stats) | Get collection totals and per-museum counts |

A typical session calls `search_objects`, then `get_object` for the objects worth a closer look. Results leave out empty fields rather than listing them as `null`. Problems you can fix, such as an unknown museum name, a year outside 1000 to 2999 or an object id that does not exist, come back as an error message that says what to change.

### search_objects

Search the collections, with optional filters.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | `""` | Keywords. Every word must match. `AND`, `OR` and quoted phrases are allowed. Empty matches everything. |
| `museum` | string | none | Museum name or unit code, such as `"American History"`, `"NMAH"`, `"Asian Art"`, `"NMAA"` or `"Natural History"`. |
| `object_type` | string | none | Object type, such as `"Paintings"` or `"Puppets"`. Case and singular or plural forms are matched. |
| `maker` | string | none | Creator, such as `"Winslow Homer"`, `"Homer, Winslow"` or an organization name. |
| `topic` | string | none | Subject, such as `"Civil War"`. |
| `material` | string | none | Material or medium, such as `"bronze"`. |
| `date_from` | integer | none | Earliest year, with decade precision. |
| `date_to` | integer | none | Latest year, with decade precision. |
| `has_images` | boolean | `false` | Only objects with online images. |
| `cc0_only` | boolean | `false` | Only objects with CC0 (public domain) media. |
| `on_view` | boolean | none | `true`: only objects on physical exhibit now. `false`: only objects not on exhibit. |
| `limit` | integer | `10` | Objects per page, 1 to 50. |
| `offset` | integer | `0` | Position of the first object. Pass `next_offset` to get the next page. |

Output:

| Field | Description |
|---|---|
| `total_count` | Number of matching objects. |
| `returned` | Number of objects in this page. |
| `offset` | Offset of this page. |
| `next_offset` | Offset of the next page. Always present; `null` when there are no more results. |
| `museum` | `{code, name}` of the museum filter, when one was given. |
| `note` | Present when a search finds nothing or the offset is past the end. It explains why, for example that every word in `query` must match, or that Natural History has no exhibit data. |
| `objects` | Object summaries, described below. |

Each object summary has:

| Field | Description |
|---|---|
| `id` | Object id, for `get_object`. |
| `title` | Title, without HTML markup. |
| `maker` | Up to 3 makers. Makers are the creator roles a record names, such as artist, manufacturer, photographer or performer. |
| `date` | Date as the museum records it, such as `"1984"` or `"ca 1995 - 1999"`. |
| `museum_code`, `museum_name` | The museum that holds the object. |
| `object_type` | Object type as the museum records it. |
| `on_view` | Whether the object is on physical exhibit now. Always present. |
| `exhibition_title`, `exhibition_location` | The exhibition and the building it is in, when the object is on view. |
| `thumbnail_url` | Small image, when the record has one. |
| `web_url` | The object's page on the museum website: the record's own link, else the museum's URL pattern for the record id, else the record's persistent ark link, else its `url` field. Use it as given. |

Example:

```text
search_objects(query="muppet", museum="American History", on_view=true)
```

At the time of writing this finds 12 objects. The first page holds 10, of which two are shown, and `offset=10` returns the last two:

```json
{
  "total_count": 12,
  "returned": 10,
  "offset": 0,
  "next_offset": 10,
  "museum": {
    "code": "NMAH",
    "name": "National Museum of American History"
  },
  "objects": [
    {
      "id": "ld1-1643398912743-1643398932982-0",
      "title": "Elmo Puppet",
      "maker": ["Clash, Kevin", "Dillon, Ryan", "Henson, Jim"],
      "date": "1984",
      "museum_code": "NMAH",
      "museum_name": "National Museum of American History",
      "object_type": "puppet",
      "on_view": true,
      "exhibition_title": "Entertainment Nation",
      "exhibition_location": "National Museum of American History",
      "web_url": "https://americanhistory.si.edu/collections/object/nmah_1444757"
    },
    {
      "id": "ld1-1643399134763-1643399177676-0",
      "title": "The Muppets Lunch Box",
      "maker": ["King Seeley Thermos", "Thermos"],
      "date": "1979",
      "museum_code": "NMAH",
      "museum_name": "National Museum of American History",
      "object_type": "lunch box",
      "on_view": true,
      "exhibition_title": "Taking America To Lunch",
      "exhibition_location": "National Museum of American History",
      "web_url": "https://americanhistory.si.edu/collections/object/nmah_1182905"
    }
  ]
}
```

These records have no images in Open Access, so they have no `thumbnail_url`. The other objects are the Fozzie Bear, Oscar the Grouch and Rosita puppets, Oscar's trash can and pieces of Mr. Hooper's costume from Sesame Street, all in "Entertainment Nation". Elmo's makers are the performers Kevin Clash and Ryan Dillon, and Jim Henson. Without `on_view`, the same search finds about 70 Muppet-related objects.

### get_object

Get the full record for one object.

| Parameter | Type | Description |
|---|---|---|
| `object_id` | string | The `id` of an object from `search_objects` or `explore_topic`. A record id such as `nmah_1444757` also works. |

Output: every field of an object summary, with up to 10 makers instead of 3, plus:

| Field | Description |
|---|---|
| `record_id` | The museum's record identifier, such as `nmah_1444757`. |
| `description` | Description, trimmed to 1,500 characters. |
| `summary` | Summary, trimmed to 800 characters. |
| `notes` | Further notes that do not repeat the description, trimmed to 1,000 characters. |
| `dimensions` | Physical dimensions. |
| `materials`, `topics`, `place` | Materials, subjects and places, up to 12 of each. |
| `credit_line` | How the museum acquired the object. |
| `rights` | Rights or usage statement. |
| `is_cc0` | Whether the object has CC0 media that can be reused freely. Always present. |
| `images` | Up to 10 images, each with `url`, `thumbnail_url`, `iiif_url`, `caption` and `is_cc0`. |
| `image_count` | Total number of images, given only when there are more than 10. |

As in search results, empty fields are left out. An id that does not exist returns an error.

Example, for the Elmo puppet found above:

```text
get_object(object_id="ld1-1643398912743-1643398932982-0")
```

Returns, with the description and notes shortened here:

```json
{
  "id": "ld1-1643398912743-1643398932982-0",
  "title": "Elmo Puppet",
  "maker": ["Clash, Kevin", "Dillon, Ryan", "Henson, Jim"],
  "date": "1984",
  "museum_code": "NMAH",
  "museum_name": "National Museum of American History",
  "object_type": "puppet",
  "on_view": true,
  "exhibition_title": "Entertainment Nation",
  "exhibition_location": "National Museum of American History",
  "web_url": "https://americanhistory.si.edu/collections/object/nmah_1444757",
  "record_id": "nmah_1444757",
  "description": "This Elmo puppet was used on Sesame Street from about 1984 until the early 2000s. ...",
  "notes": "Designed by the nonprofit Children's Television Workshop to teach basic reading, math, and life skills ...",
  "dimensions": "overall: 14 in x 16 in x 11 in; 35.56 cm x 40.64 cm x 27.94 cm",
  "materials": [
    "plastic (overall material)",
    "synthetic fur (overall material)",
    "foam (overall material)"
  ],
  "topics": [
    "Jim Henson",
    "Amusements",
    "Sesame Street",
    "Puppets",
    "Children's television programs",
    "Television broadcasts",
    "In Pursuit of Life, Liberty, and Happiness"
  ],
  "place": ["New York", "Queens", "United States"],
  "credit_line": "A Gift from the Family of Jim Henson: Lisa Henson, Cheryl Henson, Brian Henson, John Henson and Heather Henson",
  "is_cc0": false
}
```

The museum website shows photos of Elmo under usage conditions, but Open Access publishes none, so the record has no `images` or `thumbnail_url` and `is_cc0` is `false`. Many other objects, such as the Asian Art tea bowls in [Search tips](#search-tips), have CC0 images.

### list_museums

List the Smithsonian units that contribute to Open Access. It takes no parameters.

Output: a list with one entry per unit:

| Field | Description |
|---|---|
| `code` | Unit code, accepted by `museum`. |
| `name` | Unit name. |
| `object_count` | Records in the unit, including archival records. |
| `archival_only` | `true` for units that publish only archival records, which object searches do not return. Left out for other units. |
| `aliases` | Lowercase names that `museum` accepts for the unit. Left out when the only alias would repeat the name. |

The list has 49 entries: the unit codes in the search index, plus `NMNH`, which covers every Natural History department (`NMNHPALEO`, `NMNHBOTANY` and the others). The retired code `FSG` is counted under `NMAA`. Counts come from the API's statistics, cached for 6 hours and shared with `get_collection_stats`. Clients that read structured tool output receive the list wrapped as `{"result": [...]}`.

Example: `list_museums()` returns entries such as these (counts as of October 2026):

```json
[
  {"code": "AAA", "name": "Archives of American Art", "object_count": 5338883, "archival_only": true},
  {"code": "NMAA", "name": "National Museum of Asian Art", "object_count": 4843911, "aliases": ["freer", "sackler", "asian art"]},
  {"code": "NMAH", "name": "National Museum of American History", "object_count": 2950147, "aliases": ["american history"]},
  {"code": "NMNH", "name": "National Museum of Natural History", "object_count": 11605868, "aliases": ["natural history"]}
]
```

### explore_topic

Get a varied random sample of objects on a topic, for open-ended browsing.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `topic` | string | required | Topic keywords, such as `"quilts"`. As in `query`, every word must match. |
| `museum` | string | none | Museum name or code, to explore one museum. |
| `limit` | integer | `12` | Number of objects, 1 to 30. |

Output: the same fields as `search_objects`, plus `facets`:

| Field | Description |
|---|---|
| `facets.museums` | Objects in the sampled pool by unit code, such as `{"NMAH": 22}`. |
| `facets.object_types` | The 10 most common object types in the pool. |

The tool draws a random pool of 60 matching objects with images, adds objects without images only when fewer than `limit` come back, and picks objects in rotation across museums and object types. `total_count` counts the matches with images, or all matches when objects without images were added; `next_offset` is always `null`, and `note` describes the pool. Each call returns a different sample; use `search_objects` for a complete, paged list.

Example: in one run, `explore_topic(topic="quilts")` returned 12 objects from nine Smithsonian units, including quilts from American History and the Anacostia Community Museum, fiber art from American Art, and printed textiles from Cooper Hewitt and the National Museum of African American History and Culture. Its facets were:

```json
{
  "museums": {"NMAH": 22, "NMAAHC": 9, "NMAI": 9, "SAAM": 5, "CHNDM": 5, "SIA": 4, "NMNHANTHRO": 3, "NPM": 2, "ACM": 1},
  "object_types": {
    "Quilt": 13,
    "Furnishings (home)": 8,
    "Decorative arts-fiber": 5,
    "Color transparencies": 4,
    "Embroidery & stitching": 3,
    "Quilt block": 3,
    "Textiles": 2,
    "Printed, dyed & painted textiles": 2,
    "Petticoat": 2,
    "Employee gear": 2
  }
}
```

### get_collection_stats

Get collection totals and per-museum counts. It takes no parameters.

| Field | Description |
|---|---|
| `total_objects` | All records, including archival records. |
| `cc0` | CC0 records. |
| `with_images` | Searchable objects that have images. |
| `as_of` | Month of the statistics, such as `"2026-10"`. |
| `museums` | `code`, `name`, `object_count` and `cc0` for each unit, largest first. Natural History is listed by department. |
| `note` | Where the figures come from. |

The figures come from the API's statistics and one count query, cached for 6 hours and shared with `list_museums`. The totals include archival records, which object searches do not return, so they are larger than search counts.

Example: `get_collection_stats()` returns, trimmed to two museums:

```json
{
  "total_objects": 42812606,
  "cc0": 17447826,
  "with_images": 7495314,
  "as_of": "2026-10",
  "museums": [
    {"code": "AAA", "name": "Archives of American Art", "object_count": 5338883, "cc0": 489524},
    {"code": "NMAA", "name": "National Museum of Asian Art", "object_count": 4843911, "cc0": 49437}
  ],
  "note": "Counts are from the API /stats endpoint and include archival records; with_images counts searchable objects that have images."
}
```

## Resources

| URI | Content |
|---|---|
| `smithsonian://museums` | The museum list from `list_museums`, as JSON. |
| `smithsonian://objects/{object_id}` | The record from `get_object` for that id, as JSON. |

Clients that support resources can attach these to a conversation without a tool call.

## Prompts

| Prompt | Arguments | Purpose |
|---|---|---|
| `collection_research` | `research_topic`, `focus_area` (optional) | Research a topic across the collections. |
| `object_analysis` | `object_id` | Analyze one object in depth. |
| `exhibition_planning` | `exhibition_theme`, `target_audience` (optional), `size` (optional: `small`, `medium` or `large`) | Plan an exhibition from collection objects. |
| `educational_content` | `subject`, `grade_level` (optional), `learning_goals` (optional) | Build a lesson around collection objects. |
| `museum_on_view` | `museum`, `topic` (optional) | Find out what is on view at a museum. |

## Search tips

- Every word in `query` must match, so use 1 to 4 distinctive keywords and leave out questions and stop words. "Which Muppets are on display right now" finds nothing, and the result's `note` says why; `query="muppet"` with `on_view=true` finds the 12 objects above.
- Use `OR` for alternatives, as in `query="quilt OR coverlet"`.
- Put names in `maker`, not `query`. `maker="Winslow Homer"` also matches the indexed form "Homer, Winslow", and `search_objects(maker="Winslow Homer", object_type="Paintings")` returns works such as "Girl Shelling Peas" and "White Mountain Wagon" from Cooper Hewitt. Art is well covered: `object_type="Paintings"` alone matches thousands of records.
- `museum` accepts names or codes. "Asian Art", "Freer", `NMAA` and the retired code `FSG` all search the National Museum of Asian Art, and "Natural History" or `NMNH` searches every Natural History department.
- Dates have decade precision, so `date_from=1863` starts at 1860. `search_objects(query="Lincoln", museum="American History", date_from=1860, date_to=1869)` returns items such as a Lincoln campaign flag from 1864 and a parade axe from 1860. Years must be from 1000 to 2999.
- `on_view=true` returns objects on physical exhibit now, with exhibition titles. Natural History publishes no exhibit data, so `on_view=true` with Natural History always returns nothing, and the result's `note` says so.
- 14 units, such as the Archives of American Art, publish only archival records, which object searches do not return. `list_museums` marks them `archival_only`, and a search limited to one of them returns an error that says so.
- `cc0_only=true` keeps objects whose media can be reused freely. `search_objects(query="tea bowl", museum="Asian Art", cc0_only=true)` returns Hagi and Raku ware tea bowls with CC0 images.
- Never construct Smithsonian URLs; use `web_url`. URL formats differ by museum and are case-sensitive.

## Migrating from 1.x

Version 2.0 replaces all 28 tools of 1.x with 5. Calls to a 1.x tool name fail, so update any prompts, scripts or mcpo endpoint URLs that use them.

### Removed tools

| Removed | Use instead |
|---|---|
| `search_collections`, `simple_search`, `search_by_unit`, `get_search_context` | `search_objects` |
| `summarize_search_results`, `get_object_ids`, `get_first_object_id` | No replacement needed; results are already compact |
| `find_and_describe`, `search_and_get_first_details`, `search_and_get_details` | `search_objects`, then `get_object` |
| `get_object_details`, `get_object_context`, `validate_object_id`, `get_object_url`, `search_and_get_first_url` | `get_object` |
| `get_smithsonian_units`, `get_units_context`, `resolve_museum_name` | `list_museums`; `search_objects` also accepts museum names |
| `get_objects_on_view`, `find_on_view_items`, `get_museum_highlights_on_view`, `get_on_view_context` | `search_objects(on_view=true)` |
| `simple_explore`, `continue_explore` | `explore_topic` |
| `get_collection_statistics`, `get_stats_context` | `get_collection_stats` |
| `get_museum_collection_types`, `check_museum_has_object_type` | `search_objects(object_type=..., museum=..., limit=1)`; `total_count` answers it |

### Breaking changes

- Tool names: every 1.x tool is gone, as listed above. Through mcpo the endpoints change too, so `/smithsonian_open_access/get_smithsonian_units` becomes `/smithsonian_open_access/list_museums`.
- Output shapes: searches return compact summaries instead of full records, and fields are renamed. `unit_code` is now `museum_code`, `unit_name` is `museum_name`, `is_on_view` is `on_view` and `returned_count` is `returned`. `has_more` is gone; `next_offset` is `null` on the last page. Links to object pages are in `web_url`. Empty fields are left out instead of being returned as `null`.
- Parameters: `museum` takes names or codes and replaces `unit_code`. The `is_cc0` filter is now `cc0_only`, `limit` defaults to 10 with a maximum of 50 (it was 500), and `date_from` and `date_to` filter by date.
- Asian Art is unit code `NMAA`. `FSG` is still accepted as an alias, but results report `NMAA`.
- `is_cc0` on an object now means the object has CC0 media. Records with CC0 text but restricted or no media, such as copyrighted objects at the National Museum of African American History and Culture, are no longer reported as CC0.
- Prompts drop the `_prompt` suffix from their names, and six prompts that only restated tool usage are removed. See the [changelog](CHANGELOG.md).

## Integration

### Claude Desktop

See [Quick Start](#quick-start) for Claude Desktop configurations using uvx, npm/npx, a local clone, a virtual environment or Docker. A ready-to-copy example is in `examples/claude-desktop-config.json`.

### mcpo Integration (MCP Orchestrator)

**mcpo** is an MCP orchestrator that converts multiple MCP servers into OpenAPI/HTTP endpoints, ideal for combining multiple services into a single systemd service.

#### Installation

```bash
# Install mcpo as a uv tool
uv tool install mcpo

# Or run it without installing
uvx mcpo --help
```

#### Configuration

Copy `examples/mcpo-config.json` to `mcpo-config.json` in the project root and fill in your paths and API key, or let `config/setup.sh` generate it. The generated file contains your API key, so do not commit it. A minimal configuration:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/molanojustin/smithsonian-mcp",
        "smithsonian-mcp"
      ],
      "env": {
        "SMITHSONIAN_API_KEY": "your_api_key_here"
      }
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time", "--local-timezone=America/New_York"]
    }
  }
}
```

#### Running with mcpo

```bash
# Start mcpo with hot-reload
mcpo --config mcpo-config.json --port 8000 --hot-reload

# With API key authentication
mcpo --config mcpo-config.json --port 8000 --api-key "your_secret_key"

# Access endpoints:
# - Smithsonian: http://localhost:8000/smithsonian_open_access
# - Memory: http://localhost:8000/memory
# - Time: http://localhost:8000/time
# - API docs: http://localhost:8000/docs
```

#### Systemd Service

Create `/etc/systemd/system/mcpo.service`:

```ini
[Unit]
Description=MCP Orchestrator Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/your/config
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/mcpo --config mcpo-config.json --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable mcpo
sudo systemctl start mcpo
sudo systemctl status mcpo
```

#### Troubleshooting mcpo

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed mcpo troubleshooting, including:
- ModuleNotFoundError solutions
- Connection closed errors
- Port conflicts
- Path configuration issues

### VS Code

Open the clone with `code .`. After `uv sync --group dev`, `.vscode/tasks.json` provides tasks to start the server, run the tests, format and lint the code, and open the MCP Inspector, and `.vscode/launch.json` provides debugger configurations for the server and the tests.

## Requirements

### For uvx or a local clone:

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.10 or newer if needed
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

### For npm/npx installation:

- Node.js 16.0 or higher
- uv (the wrapper uses it to install the Python dependencies)
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

### For a virtual environment without uv:

- Python 3.10 or higher (CI tests 3.10 through 3.14)
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

## Testing

### Using npm/npx:

```bash
# Test API connection
smithsonian-mcp --test

# Run MCP server
smithsonian-mcp

# Show help
smithsonian-mcp --help
```

### From a local clone:

```bash
# Install runtime and development dependencies
uv sync --group dev

# Test API connection
uv run python examples/test-api-connection.py

# Run MCP server (stdio; normally your MCP client starts it)
uv run smithsonian-mcp

# Explore the server interactively with the MCP Inspector
npx @modelcontextprotocol/inspector .venv/bin/smithsonian-mcp

# Run test suite
uv run pytest tests/

# Run on-view functionality tests
uv run pytest tests/test_on_view.py -v

# Run basic tests
uv run pytest tests/test_basic.py -v

# Run the tool tests (offline, against a fake API)
uv run pytest tests/test_tools.py -v

# Run the opt-in live tests (they use your API key and its rate limit)
SMITHSONIAN_LIVE_TESTS=1 uv run pytest tests/test_live.py tests/test_tools_live.py -v

# Verify complete setup
uv run python scripts/verify-setup.py
```

## Service Management

The setup scripts can register the server as a background service. Because the server uses the stdio transport, it exits as soon as no client is attached, so a standalone service is rarely useful. To expose the tools as a long-running HTTP service, run them behind [mcpo](#mcpo-integration-mcp-orchestrator) instead.

### Linux (systemd)

```bash
# Start service
systemctl --user start smithsonian-mcp

# Stop service
systemctl --user stop smithsonian-mcp

# Check status
systemctl --user status smithsonian-mcp

# Enable on boot
systemctl --user enable smithsonian-mcp
```

### macOS (launchd)

```bash
# Load service
launchctl load ~/Library/LaunchAgents/com.smithsonian.mcp.plist

# Unload service
launchctl unload ~/Library/LaunchAgents/com.smithsonian.mcp.plist

# Check status
launchctl list | grep com.smithsonian.mcp
```

### Windows

```powershell
# Start service
Start-Service SmithsonianMCP

# Stop service
Stop-Service SmithsonianMCP

# Check status
Get-Service SmithsonianMCP
```

## Troubleshooting

[TROUBLESHOOTING.md](TROUBLESHOOTING.md) covers:

- API key and rate limit errors
- Searches that return nothing, including on-view searches at Natural History
- Old 1.x tool names that no longer work
- Claude Desktop connection and server startup problems
- Module import errors and mcpo setup

## Documentation

- [README.md](README.md): setup and tool reference (this file)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): common problems and fixes
- [CHANGELOG.md](CHANGELOG.md): changes between versions
- `examples/`: Claude Desktop and mcpo configurations and an API connection test
- `scripts/`: setup verification

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License. See [LICENSE.md](LICENSE.md).

## Acknowledgments

- Smithsonian Institution for the Open Access collections
- api.data.gov for the API infrastructure
- The FastMCP team for the MCP framework
- The Model Context Protocol community
