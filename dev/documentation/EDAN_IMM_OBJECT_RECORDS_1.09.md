# EDAN Phase 1 - SDLCM Documentation
## Index Metadata Model For Objects

**Collections Systems & Digital Assets Division,**  
**Office of the Chief Information Officer**

**Version 1.09**  
**December 18, 2019**

---

## 1. Document Purpose

This document represents the metadata model to be used by the EDAN Phase 1 [Solr-Lucene] metadata index. It has been developed as part of the Smithsonian Institution's system development life cycle management (SDLCM) processes for small to medium sized system implementation projects and should be viewed in conjunction with the EDAN Phase 1 system requirements and design documentation.

---

## 2. Revision History

| Version | Event | Issue Date | Responsible Party |
|---------|-------|------------|-------------------|
| 1.01 | Initial CISMC and SIRISMC accepted draft (IMM14). Approved at the TRB Requirements Review on 12/16/2008 with no changes. | 10/28/2008 | George Bowman, CISMC, SIRISMC, TRB |
| 1.02 | Cleaned up all the `<xml>` notes, updated document format. | 02/19/2009 | George Bowman |
| 1.03 | Fixed online-media-type `<xml>`. Added freetext Object Rights | 03/31/2009 | George Bowman |
| 1.04 | Added `<geoLocation>` tag for structured place terms | 09/10/2009 | George Bowman |
| 1.05 | Added `<onPhysicalExhibit>` flag. Added `<exhibition>` block for structured exhibit data. Added `<setName>` example for exhibition title. Added caption attribute for individual online_media links. Enhanced definition and examples for online_media | 08/19/2010 | George Bowman |
| 1.06 | Limit record_ID to 40 characters. Add CSDAD, OCIO footer | 02/14/2012 <br> 03/18/2015 | George Bowman |
| 1.07 | • Change `<related_record_identifier>` to a group field and add a label.<br>• Reorder fields to mirror actual xml structure.<br>• Move `<geoLocation>` examples to a separate document.<br>• Added usage_flag attribute to `<media>`<br>• Took out much of the description and justification – everybody gets it now. | 04/19/2017 | George Bowman |
| 1.08 | Add preferred_citation for both record-level and media-specific citations. Add usage_restrictions. | 08/2018 | George Bowman |
| 1.09 | Implement standard rights codes for metadata and each individual media element:<br>**Changes to `<DescriptiveNonRepeating>`:**<br>• Add standard `<metadata_usage>` block<br>• Add `<guid>` for the object<br>**Change to `<IndexedStructured>`**<br>• Remove `<online_media_rights>`<br>**Change to `<FreeText>`**<br>• Remove `<usage_restrictions>` from FreeText<br>**Changes to `<online_media>` block:**<br>• Add standard `<usage>` block to `<media>` tag<br>• Add guid attribute to `<media>` tag<br>• Remove "rights" attribute from `<media>` tag: use `<usage>` tag instead. | 12/2019 | George Bowman |

---

## 3. DescriptiveNonRepeating Fields

### Record Type
- **Description:** Object is the default. Do not use this. It is mandatory for all other types.
- **XML Tag:** `<record_type>`

### Record ID (mandatory, non-repeatable)
- **Description:** The unique system + record ID for the record in its home system. NOTE: this field is limited to 40 characters and should NOT be changed over time. It should be permanently associated with this record.
- **XML Tag:** `<record_ID>`
- **Examples:**
  - `siris_ari_1234`
  - `npm_1989.0496.10006`
  - `npg_AD/NPG.74.8`

### guid (optional, non-repeatable)
- **Description:** The DOI or ARK number associated with this object.
- **XML Tag:** `<guid>`

### Data Source (both data_source and unit_code are mandatory, non-repeatable)
- **Description:** The unit or project by whom the data was contributed.
- **XML Tags:** `<data_source>`, `<unit_code>` (just shorthand)
- **Examples:**
  - National Air and Space Museum Archives
  - Smithsonian Institution Libraries
  - `<unit_code>SIL`

### Title/Object-name (mandatory, non-repeatable; title_sort is also mandatory, non-repeatable)
- **Description:** A primary or descriptive title for the object or resource. For objects or resources which have a formal title, that would be used. For other objects or resources, some concatenation of descriptive terms should be assembled that attempts to create a unique label.
- **XML Tags:** 
  - `<title label="Title">`
  - `<title label="Object Name">`
  - `<title_sort>` normalized for sorting
- **Examples:**
  - Einstein's Brier Pipe
  - Postage stamp plate block
  - Jan Matulka papers, 1923-1960

### Record Link (non-repeatable)
- **Description:** Link to this record in its home system
- **XML Tag:** `<record_link>`
- **Example:** `http://npgportraits.si.edu/eMuseum...`

### Metadata Usage
- **Description:** Usage rights statement for the metadata of this record. Presumably it would be CC0. This is not to be confused with an analogous block under online media.
- **XML Structure:**
```xml
<metadata_usage>
  <access>…</access>
  <codes>…</codes>
  <codes>…</codes>
  <text>…</text>
</metadata_usage>
```
- **Fields:**
  - usage (optional)
    - access (required)
    - codes (optional/repeatable)
    - text (optional)
- **usage.access standard list of access codes:**
  - CC0
  - Usage conditions apply
- **Note:** Each occurrence of usage.codes should have ONE of the controlled list of SD609 codes
- **usage.text:** the public readable statement
- **Example:** In almost all cases this would look like this:
```xml
<metadata_usage>
  <access>CC0</access>
</metadata_usage>
```

### Online Media Group (non-repeatable)
- **Description:** Any associated online media URLs
- **XML Structure:**
```xml
<online_media mediaCount="[how many <media> tags]">
  <media type="…"
         thumbnail="[thumbnail link]"
         caption="…"
         usage_flag="…"
         preferred_citation="…"
         guid="…">
    <usage>
      <access>…</access>
      <codes>…</codes>
      <codes>…</codes>
      <text>…</text>
    </usage>
    [link to media]
  </media>
  <media type="…"
         thumbnail="[thumbnail link]"
         caption="…"
         usage_flag="…"
         preferred_citation="…"
         guid="…">
    <usage>
      <access>…</access>
      <codes>…</codes>
      <codes>…</codes>
      <text>…</text>
    </usage>
    [link to media]
  </media>
  …
</online_media>
```

- **Required/Optional Fields:**
  - type (required)
  - thumbnail (required)
  - preferred_citation (optional)
  - usage_flag (optional)
  - guid (optional)
  - usage (optional)
    - access (required)
    - codes (optional/repeatable)
    - text (optional)

- **usage.access standard list of access codes:**
  - CC0
  - Usage conditions apply

- **Note:** Each occurrence of usage.codes should have ONE of the controlled list of SD609 codes
- **usage.text:** the public readable statement
- **Note:** If the preferred_citation in the media element is absent the record_level preferred_citation will be shown in its place.
- **Important:** With the exception of "Exhibition Website" where the link points to an online exhibition in which this object is included, this link must point to a resource ABOUT THIS OBJECT, not a larger group of objects. For example, an audio-tour for an entire exhibit would not be appropriate unless it has a position marker for the discussion of this object.
- **usage_flag:** for local information about how this media file can be used, for example, whether it has text that is transcribable or not.

- **Link Examples:**
  - Image: `http://sirismm.si.edu/siahistory/imagedb/76-7008.16.jpg`
  - Finding aid: `http://siarchives.si.edu/findingaids/FARU0347.htm`
  - Exhibit website: `http://wintercounts.si.edu/`
  - Section of an audio tour: `http://audio-file-link#marker`
  - Section of a video tour: `http://video-file-link#marker`

- **Type Examples:**
  - Images
  - Finding aids
  - Transcripts
  - Sound recordings
  - Online exhibits
  - Online publications
  - Online collections
  - Exhibit website
  - Video files

---

## 4. indexedStructured (facets)

Facet fields are access points from authorized vocabulary lists. The point is that they overlap across records and ideally record types. The content may be repeated in the freetext portion to display on the record.

### Online Media Type
- **Description:** Any types of associated online media associated with this record, using authorized terms. This is included to enable users to scope searches only to records with a specified kind of online media.
- **XML Tag:** `<online_media_type>`
- **Examples:**
  - Images
  - Finding aids
  - Transcripts
  - Sound recordings
  - Online exhibits
  - Online publications
  - Online collections

### Rights for Online Media File
- **Description:** Ideally we will have standard terms. This is included to enable users to scope searches only to images without copyright restrictions.
- **XML Tag:** `<online_media_rights>`
- **Examples:**
  - No Restrictions
  - Restrictions May Exist
  - Restrictions Exist

### Usage Flag
- **Description:** Short codes to group records into project sets so an external applications can be locked down to specific sets of records.
- **XML Tag:** `<usage_flag>`
- **Examples:**
  - SPI
  - LVM

### Object Type
- **Description:** The categories of the object or resource. This includes Form/Genre and Type Specimen Status.
- **XML Tag:** `<object_type>`
- **Examples:**
  - book
  - painting
  - diary
  - artificial heart
  - artifacts
  - holotype

### Language
- **Description:** Any languages from vocabulary lists.
- **XML Tag:** `<language>`
- **Examples:**
  - French
  - Chinese
  - Hindi
  - Navajo

### Topic
- **Description:** Any topics from vocabulary lists.
- **XML Tag:** `<topic>`
- **Examples:**
  - Federal aid to the arts
  - Airplanes, Military
  - African American history
  - Mother & Child
  - World War, 1939-1945
  - 1876: A Centennial Exhibition

### Place
- **Description:** Any places from vocabulary lists. Separate elements for each term.
- **XML Tag:** `<place>`
- **Examples:**
  - Africa
  - India
  - Red Sea
  - Maryland
  - Baltimore
  - Silver Spring

### Date
- **Description:** Any dates in a normalized form.
- **XML Tag:** `<date>`
- **Examples:**
  - 1870s
  - 1910s
  - 1950s

### Name
- **Description:** Any people, groups (except cultures), titled presentations (exhibitions, expeditions) associated with the object or resource, from vocabulary lists.
- **XML Tag:** `<name>`
- **Examples:**
  - Calder, Alexander
  - Washington, George
  - Apple Computer
  - Hyde Exploring Expedition

### Culture
- **Description:** Any culture terms from vocabulary lists.
- **XML Tag:** `<culture>`
- **Examples:**
  - Dogon (African people)
  - Limba (African people)
  - Kiowa Indians
  - Cheyenne Indians

### geoLocation
- **Description:** One geoLocation per place, with as many levels filled in as possible. Fill in coordinates if available. This is redundant to the `<place>` element, but in a form to support a hierarchical display in the form of a map.
- **XML Structure:**
```xml
<geoLocation>
  <L1 type=[Continent | Ocean]>
  <L2 type=[Country | Nation | Sea | Gulf | Bay | Sound]>
  <L3 type=[State | Province | Department | Country | District | Republic | Sea | Gulf | Bay]>
  <L4 type=[County | Island]>
  <L5 type=[City | Town]>
  <Other type=[anything: examples = Neighborhood, Street, Desert, Park, etc.]>
  <points label=[text] dates="yyyy-yyyy">
    <point>
      <latitude type=[decimal | degrees]>
      <longitude type=[decimal | degrees]>
    </point>
    <point>
      <latitude type=[decimal | degrees]>
      <longitude type=[decimal | degrees]>
    </point>
    <point>
      <latitude type=[decimal | degrees]>
      <longitude type=[decimal | degrees]>
    </point>
  </points>
</geoLocation>
```

- **Note:** The geoLocation processor will attempt to fill in missing levels by matching as many pieces as possible to geoNames. If you really don't know what you have, just submit `<geoLocation><Other>Where am I</Other></geoLocation>`

- **Examples:**
```xml
<geoLocation>
  <L1 type="Continent">North America</L1>
  <L2 type="Country">United States</L2>
  <L3 type="District">District of Columbia</L3>
  <L5 type="City">Washington</L5>
  <Other type="Neighborhood">Adams Morgan</Other>
</geoLocation>

<geoLocation>
  <L1 type="Ocean">Pacific</L1>
  <L2 type="Country">United States</L2>
  <L3 type="State">Hawaii</L3>
  <L4 type="Island">Hawaii</L4>
  <Other type="Park">Volcanoes National Park</Other>
</geoLocation>
```

See appendix for examples

### On Physical Exhibit
- **Description:** An indication that the object is currently on display for the public.
- **XML Tag:** `<onPhysicalExhibit>`
- **Example:** Yes

### Exhibition
- **Description:** Structured data about this object in an exhibit. Most of this will not be display in collections.si.edu [use freetext for display], however it will be output with the `<exhibition>` block for other applications using the Metadata Delivery Service, potentially for something like a virtual gallery tour. NOTE: this is not a historical record. Current and future exhibitions only!
- **XML Structure:**
```xml
<exhibition>
  <exhibitionTitle>
  <exhibitionType>
  <building>
  <room>
  <displayUnit>
  <externalLink type="audio, etc.">
  <exhibitionCurator>
  <exhibitionOrganizer>
  <exhibitionSponsor>
  <exhibitionLabel>
</exhibition>
```

- **Note:** The external Link is for THIS OBJECT IN THIS EXHIBIT. To include an audio- or video-tour link on an object record, the link MUST point to a position marker in the audio/video file where this object is discussed.
- **Example:** `<externalLink type="audio">http://audio-file-link#marker`

- **Field Examples:**
  - **exhibitionTitle:** A Brave New World, August 9, 2010 – August 29, 2010 (use dates as appropriate)
  - **exhibitionType (controlled list):**
    - Online Exhibit
    - Smithsonian exhibition
    - Traveling exhibition
    - Loan
  - **building:** Sackler Gallery
  - **room:** Gallery 13
  - **displayUnit:** Case 10
  - **externalLink (controlled list):**
    - exhibitWebsite
    - audio
    - video
    - image
    - URL

### Related Record
- **Description:** For 'redirecting' to the related record(s) with the matching identifier. This could be used for:
  - Taxonomy → Specimen
  - Art Inventories → SAAM objects
  - Parts → Whole
  - Illustrations → Objects
  - Bibliographies → Books & Articles
  - Collection descriptions → Finding Aids

  The blurb will describe the relationship in readable terms. The thumbnail and title are copied from the related record, for expedience. For anything else the related record will need to be searched.

- **XML Structure:**
```xml
<related_record label="xxx">
  <blurb>
  <related_record_ID>
</related_record>
```

- **Examples:**
```xml
<related_record label="Related record">
  <blurb>Copied from</blurb>
  <related_record_ID>SAAM_123</related_record_ID>
</related_record>

<related_record label="Freer's purchases">
  <blurb>Purchased on X date</blurb>
  <related_record_ID>fsg_F1907.283</related_record_ID>
</related_record>
```

### Taxonomic Fields

#### Taxon-Kingdom
- **Description:** Taxonomic terms for Kingdom
- **XML Tag:** `<tax_kingdom>`
- **Examples:** Animalia, Plantae, Fungi, Protista, Archaea, Eubacteria

#### Taxon-Phylum
- **Description:** Taxonomic terms for Phylum
- **XML Tag:** `<tax_phylum>`
- **Examples:** Chordata, Arthropoda

#### Taxon-Division
- **Description:** Taxonomic terms for Division
- **XML Tag:** `<tax_division>`
- **Example:** Magnoliophyta

#### Taxon-Class
- **Description:** Taxonomic terms for Class
- **XML Tag:** `<tax_class>`
- **Examples:** Chondrichthyes, Aves, Malacostraca

#### Taxon-Order
- **Description:** Taxonomic terms for Order
- **XML Tag:** `<tax_order>`
- **Examples:** Orectolobiformes, Lamniformes, Passeriformes, Decapoda

#### Taxon-Family
- **Description:** Taxonomic terms for Family
- **XML Tag:** `<tax_family>`
- **Examples:** Rhincodontidae, Cetorhinidae, Vireonidae

#### Taxon-Sub-Family
- **Description:** Taxonomic terms for sub-family if one exists
- **XML Tag:** `<tax_sub-family>`
- **Examples:** Bambusoideae, Etmopterinae, Imbricariinae

#### Scientific_name
- **Description:** Taxonomic terms for genus and species
- **XML Tag:** `<scientific_name>`
- **Examples:** Rhincodon typus, Cetorhinus maximus, Vireo philadelphicus

#### Common name
- **Description:** Common names
- **XML Tag:** `<common_name>`
- **Examples:** basking shark, blue crab, Philadelphia Vireo

### Geological Age Fields

#### Geo-age-Era
- **Description:** Geological Age Era
- **XML Tag:** `<geo_age-era>`
- **Examples:** Archean, Cenozoic, Mesozoic, Proterozoic

#### Geo-Age-System
- **Description:** Geological Age System
- **XML Tag:** `<geo_age-system>`
- **Examples:** Eoarchean, Mesoarchean, Neoarchean

#### Geo-Age-Series
- **Description:** Geological Age Series
- **XML Tag:** `<geo_age-series>`
- **Examples:** Holocene, Miocene, Pleistocene, Plio-Pleistocene

#### Geo-Age-Stage
- **Description:** Geological Age Stage
- **XML Tag:** `<geo_age-stage>`
- **Examples:** Aptian, Changhsingian, Norian

### Stratigraphy Fields

#### Strat-Group
- **Description:** Stratigraphy Group
- **XML Tag:** `<strat_group>`
- **Examples:** Absaroka Volcanic Super Group, Admire Group, Allegheny Group

#### Strat-Formation
- **Description:** Stratigraphy Formation
- **XML Tag:** `<strat_formation>`
- **Examples:** Harpersville Fm, Inferior Oolite Fm, Pottsville Fm

#### Strat-Member
- **Description:** Stratigraphy Member
- **XML Tag:** `<strat_member>`
- **Examples:** Francis Creek Sh Mbr, Black Creek Coal Bed, Jefferson Coal Bed

---

## 5. FreeText Fields

### Identifier
- **Description:** Any ID_numbers, etc., necessary to identify the object or resource
- **XML Tags:**
  - `<freetext category="identifier" label="Accession #">`
  - `<freetext category="identifier" label="Catalog #">`
- **Example:** 1989.0496.10006

### Physical Description
- **Description:** A description of the way the object or resource looks, its physical characteristics, how it was prepared, etc., and the manner in which the described materials are subdivided into smaller units. This includes:
  - Orientation/arrangement
  - Physical Description
    - Format/Extent
    - Sex/Age/Weight/Size
    - Processes & Techniques
    - Storage medium/regime
    - Dimensions

- **XML Tags:**
  - `<freetext category="physicalDescription" label="Physical description">`
  - `<freetext category="physicalDescription" label="Dimensions">`
  - `<freetext category="physicalDescription" label="Medium">`

- **Examples:**
  - 3.37 cu. ft. (3 document boxes) (1 12x17 box) (4 5x8 boxes)
  - 1 photonegative: glass; 5 x 7 in
  - 4 linear meters and 5 microfilm reels
  - Carpet is of Kilim type
  - 3 adult male skulls
  - Preparation: Alcohol (Ethanol)
  - New Coccine (or Crocein Scarlet) dye
  - Autochrome process
  - Blueprint process
  - Cibachrome ™
  - 5 x 7 in
  - metal: Bronze
  - Pencil and india ink on board
  - Paper, ink, gum

### Gallery Label
- **Description:** Text of Exhibition label
- **XML Tags:**
  - `<freetext category="galleryLabel" label="Gallery Label">`
  - `<freetext category="galleryLabel" label="Tombstone">`

### Notes
- **Description:** A textual description of the object or resource, including abstracts in the case of document-like objects or content descriptions in the case of visual resources. This includes any other information to account for the complexity of the object, such as:
  - Style
  - Iconography
  - Original citation of type specimen
  - Biographical & Historical Context

  This also includes any non-controlled terms for any other element, such as:
  - Ecological info
  - Ocean Depth
  - Era

  This may also include a description of a current or future exhibit containing this object, including title, dates if appropriate, location, curator, organizer, sponsor, etc. NOTE: this is not a historical record – current and future exhibitions only!

- **XML Tags:**
  - `<freetext category="notes" label="Notes">`
  - `<freetext category="notes" label="Summary">`
  - `<freetext category="notes" label="Iconographic analysis">`
  - `<freetext category="notes" label="Exhibition Details">`

- **Examples:**
  - Wooden baseball bat used by Stan Musial during the 1957-1958 baseball season and used to break the 3000 hit goal.
  - Soon after the first federal duck stamp appeared in 1934, states began issuing their own hunting stamps.

### Publisher
- **Description:** For publications: the name of the publisher or distributor and any qualifying terms, such as an indication of function.
- **XML Tags:**
  - `<freetext category="publisher" label="Publisher">`
  - `<freetext category="publisher" label="Distribution">`
  - `<freetext category="publisher" label="Location">`
- **Examples:**
  - Rand McNally
  - U.S. Dept. of Agriculture, Forest Service
  - Gauthier-Villars (distributor)

### Object Type
- **Description:** The categories of the object or resource.
- **XML Tag:** `<freetext category="objectType" label="Type">`
- **Examples:**
  - book
  - painting
  - diary
  - holotype
  - Dead letter office materials

### Taxonomic Name
- **Description:** Any taxonomic terms associated with the object or resource.
- **XML Tag:** `<freetext category="taxonomicName" label="Taxonomy">`
- **Examples:**
  - Cephalopoda—Sepiidae—Sepia-officinalis
  - Cetacea
  - Cephalopoda—Ommastephidae—Dosidicus—gigas

### Language
- **Description:** Any languages represented by the object or resource.
- **XML Tag:** `<freetext category="language" label="Language">`
- **Examples:**
  - French
  - Chinese
  - Hindi
  - Navajo
  - Forward in French with indexes in French and German

### Topic
- **Description:** The topical access points of the object or resource.
- **XML Tag:** `<freetext category="topic" label="Topic">`
- **Examples:**
  - Federal aid to the arts
  - Airplanes, Military
  - African American history
  - Mother & Child
  - World War, 1939-1945
  - 1876: A Centennial Exhibition

### Place
- **Description:** Any places associated with the object or resource.
- **XML Tags:**
  - `<freetext category="place" label="Place">`
  - `<freetext category="place" label="Country">`
  - `<freetext category="place" label="Site">`
- **Examples:**
  - Africa
  - India
  - Red Sea
  - Maryland
  - Baltimore, Maryland
  - Maryland--Silver Spring
  - Site 16 IV 149 -- archeology

### Date
- **Description:** Any dates associated with the object or resource.
- **XML Tag:** `<freetext category="date" label="Date">`
- **Examples:**
  - 1870-1873
  - June 10, 1910
  - Installed, May 2, 1952

### Name
- **Description:** Any people, groups (except cultures), titled presentations (exhibitions, expeditions) associated with the object or resource.
- **XML Tags:**
  - `<freetext category="name" label="Author">`
  - `<freetext category="name" label="Creator">`
  - `<freetext category="name" label="Artist">`
  - `<freetext category="name" label="Maker">`
  - `<freetext category="name" label="Sitter" role="sitter">`
- **Examples:**
  - Calder, Alexander, 1898-1976, painter
  - Washington, George, 1732-1799, sitter
  - Apple Computer
  - Hyde Exploring Expedition

### Culture
- **Description:** Any cultures represented by the object or resource.
- **XML Tags:**
  - `<freetext category="culture" label="Culture">`
  - `<freetext category="culture" label="Nationality">`
- **Examples:**
  - Dogon (African people)
  - Limba (African people)
  - Kiowa Indians
  - Cheyenne Indians

### Set Name
- **Description:** Any collection names or set name of logical group of object or resource. Consistency is important: This may be used to search for all items in the same collection, i.e., with an exact text match.
- **XML Tags:**
  - `<freetext category="setName" label="See more items in">`
  - `<freetext category="setName" label="On exhibit">`
- **Examples:**
  - Ivory Soap Advertising Collection 1883-1998.
  - Garden Club of America Collection.
  - (An exhibition) A Brave New World, August 9, 2010 – April 24, 2011

### Data Source
- **Description:** The unit or project by whom the data was contributed.
- **XML Tag:** `<freetext category="dataSource" label="Data Source">`
- **Examples:**
  - National Air and Space Museum Archives
  - Smithsonian Institution Libraries

### Credit Line
- **Description:** A brief statement indicating how the work came into the current collection.
- **XML Tag:** `<freetext category="creditLine" label="Credit line">`
- **Example:**
  - National Portrait Gallery, Smithsonian Institution; acquired as a gift to the nation through the generosity of the Donald W. Reynolds Foundation.

### Preferred Citation
- **Description:** The preferred citation to be shown with media files lacking a file-specific preferred_citation.
- **XML Structure:**
```xml
<preferred_citation>
  <label>Cite as</label>
  <content>xxxxx</content>
</preferred_citation>
```
- **Example:** Metropolitan Museum of Art, 2014

### Usage Restrictions
- **Description:** A statement regarding the usage of any media files, ideally including SI contact information.
- **XML Structure:**
```xml
<usage_restrictions>
  <label>Terms & Restrictions</label>
  <content>xxxxx</content>
</usage_restrictions>
```
- **Examples:**
  - Reproduction and/or publication is forbidden. To be used for study purposes only. Contact: Archives of American Art, Smithsonian Institution, Washington, D.C. 20560
  - Most items available for reproduction. Contact: Smithsonian Institution, National Museum of American History : Archives Center. P.O. Box 37012, Suite 1100, MRC 601, Constitution Ave., between 12th and 14th Sts., N.W., Washington, D.C. 20013-7012. Call 202-633-3270 for appointment. Fax: 202-786-2453.
  - Authorization to publish, quote or reproduce must be obtained from: Thomas W. Brunk, 2954 Burns, Detroit, Michigan 48214

### Object Rights
- **Description:** A brief statement describing rights applicable to the object, not the digital file.
- **XML Tag:** `<freetext category="objectRights" label="Rights">`
- **Example:** (c) Edward Smith, 1957.