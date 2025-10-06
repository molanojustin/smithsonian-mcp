# Smithsonian Open Access API - JSON Content Format

## {json} content

### Schema Structure

```json
{
  "id": {string},
  "title": {string},
  "unitCode": {string},
  "linkedId": {string},
  "type": {string},
  "url": {string},
  "content": {json},
  "hash": {string},
  "docSignature": {string},
  "timestamp": {long},
  "lastTimeUpdated": {long},
  "status": {int},
  "version": {string},
  "publicSearch": {boolean},
  "extensions": {json}
}
```

### Example

```json
{
  "id": "trl-1495830301960-1495830309009-0",
  "title": "lunar module",
  "unitCode": "NASM",
  "linkedId": "trl-1495830301960-1495830123123-0",
  "type": "model",
  "url": "model:lunar_module",
  "content": {json},
  "hash": "4da218220fd604fbd568c0326398abbc4d342822",
  "docSignature": "52b3092190f50814e1e06c41533eb1d1f5dfab36",
  "timestamp": 1507906511,
  "lastTimeUpdated": 1507908776,
  "status": 0,
  "version": "trl-1495830301960-1495830309009-0",
  "publicSearch": true,
  "extensions": {
    "mask": {
      "title": "lunar part #12303"
    }
  }
}
```

## Definitions

**id**: Persistent identifier. This system was derived from twitter's Snowflake which is a network service for generating unique ID numbers at high scale with some simple guarantees. The full ID is composed of a timestamp, a worker number, and a sequence number.

**title**: Simple string value identifying content

**unitCode**: Used for management of content

**linkedId**: Applicable for data models with parent, child relationships. This is not the only link that can be made. Some data types have inherit parent child relationships, such as transcription assets to transcription projects.

**type**: The registered type in the repository. This type defines characteristics about the data and offers configuration for re-use.

**url**: The normalizing name into this asset which is unique to the repository. In most cases url is a match key used for external system's unique identifiers.

**content**: A structured json object that adhere's to the schema type registered. This is the meat of the record.

**hash**: The SHA1d 40 character conversion of pertinent core fields.

**docSignature**: The SHA1d 40 character conversion of pertinent core fields including content which can signal deltas.

**timestamp**: The number of seconds that have elapsed since January 1, 1970 (midnight UTC/GMT). Marks timestamp of record entry.

**lastTimeUpdated**: The number of seconds that have elapsed since January 1, 1970 (midnight UTC/GMT). Marks timestamp of record modification.

**status**: -1|[0][1-100] integer reserved for publishing control. -1 is reserved as it suppresses the record from any view. Note no records are ever deleted from the repository unless express need is made. A status flag of 0 is published. Any level about it at the author's, consumer's discretion.

**version**: All content can opt for version control in which a versioned copy is archived. This identifier is of the same format as the id.

**publicSearch**: boolean flag for release of this record to the search consumers. Future expansion of field with most likely be necessary to accommodate more outlets.

**extensions**: Additional json directives to overlay, append or mask data.

## Metadata

The primary content in the repository at this time is collection data which we type as edanmdm. You can read more about the schema and evolution of this model [here](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf). This content type is comprised of three major sections: descriptiveNonRepeating, indexedStructured and freetext. You'll find basic information in descriptiveNonRepeating, more authorized content in indexedStructured and much more content in freetext.

## APIs

API documentation can be found at http://edan.si.edu/openaccess/apidocs/

## Authentication

The Open Access Initiative API requires an API KEY issued by api.data.gov.

Signup information can be found at https://api.data.gov/signup

---

**Support**: Support for the edan content repository, services and the Open Access Initiative API are provided by the Office of the Chief Information Officer at the Smithsonian.