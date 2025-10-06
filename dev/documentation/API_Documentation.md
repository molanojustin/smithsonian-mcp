# Smithsonian Institution Open Access API

API documentation

## Using the Services

The Open Access API requires an API key to access the endpoints. Please register with https://api.data.gov/signup/ to get a key.

## General Information

More information about the data repository and how to use the API can be found at https://edan.si.edu/openaccess/docs/

Click here to learn more about the [Open Access Initiative at the Smithsonian](https://www.si.edu/openaccess)

---

## content

### content

Fetches content based on id/url of an object.

**GET** `https://api.si.edu/openaccess/api/v1.0/content/:id`

#### Parameters

| Field | Type | Description |
|-------|------|-------------|
| id | String | Row id, url. |
| api_key | String | the API KEY you received from https://api.data.gov/signup/ |

#### Success Response

**HTTP/1.1 200 OK**

```json
{
  "status": 200,
  "responseCode": 1,
  "response": {
    "id": "edanmdm-nmaahc_2012.36.4ab",
    "title": "Drumsticks used by Art Blakey",
    "unitCode": "NMAAHC",
    "linkedId": "",
    "type": "edanmdm",
    "url": "edanmdm:nmaahc_2012.36.4ab",
    "content": { "......[see schema documentation for type]...." },
    "hash": "b4c4a61ab9b71eb8777e50b5745c4ab0c75d1999",
    "docSignature": "32081c6289db2620a3d2e61f453ad9330d071335_08dc8e60c5b2eeb3e60dcd71f40072f5",
    "timestamp": 1578947538,
    "lastTimeUpdated": 1578947529,
    "version": "123-1559922770904-1559922814561-0"
  },
  "message": "content found"
}
```

#### Error Response

**HTTP/1.1 404 Not Found**

```json
{
  "status": 404,
  "responseCode": 0,
  "response": {
    "error": "not found: the resource you were acting on could not be found"
  },
  "timestamp": "Fri Jun 07 09:23:09 EDT 2019"
}
```

**HTTP/1.1 400 Bad Request**

```json
{
  "status": 400,
  "responseCode": 0,
  "response": {
    "error": "bad request: one of your params did not pass validation"
  },
  "timestamp": "Fri Jun 07 09:23:09 EDT 2019"
}
```

---

## metrics

### stats

Fetches stats for CC0 objects/media

**GET** `https://api.si.edu/openaccess/api/v1.0/stats`

#### Parameters

| Field | Type | Description |
|-------|------|-------------|
| api_key | String | the API KEY you received from https://api.data.gov/signup/ |

---

## search

### category_search

Fetches content based on a query against a category: art_design, history_culture or science_technology.

**GET** `https://api.si.edu/openaccess/api/v1.0/category/:cat/search`

**Permission:** edan

#### Parameters

| Field | Type | Description |
|-------|------|-------------|
| q | String | the query you would like to issue. query field accepts boolean operators [AND\|OR] as well as fielded searches [topic:Gastropoda]. See terms for more field types. |
| start *(optional)* | int | the start row of your query<br>**Default:** `0` |
| rows *(optional)* | int | size of array to be returned.<br>**Default:** `10`<br>**Size range:** `0..1000` |
| sort *(optional)* | String | The sort of the row response set. Default is relevancy. newest is sort rows by timestamp of record in descending order. updated is sort rows by lastTimeUpdated of record in descending order.<br>**Default:** `relevancy`<br>**Allowed values:** `id`, `newest`, `updated`, `random` |
| api_key | String | the API KEY you received from https://api.data.gov/signup/ |
| :cat | String | the category you are filtering against.<br>**Allowed values:** `art_design`, `history_culture`, `science_technology` |

---

### search

Fetches content based on a query

**GET** `https://api.si.edu/openaccess/api/v1.0/search`

**Permission:** edan

#### Parameters

| Field | Type | Description |
|-------|------|-------------|
| q | String | the query you would like to issue. query field accepts boolean operators [AND\|OR] as well as fielded searches [topic:Gastropoda]. See terms for more field types. |
| start *(optional)* | int | the start row of your query<br>**Default:** `0` |
| rows *(optional)* | int | size of array to be returned.<br>**Default:** `10`<br>**Size range:** `0..1000` |
| sort *(optional)* | String | The sort of the row response set. Default is relevancy. newest is sort rows by timestamp of record in descending order. updated is sort rows by lastTimeUpdated of record in descending order.<br>**Default:** `relevancy`<br>**Allowed values:** `id`, `newest`, `updated`, `random` |
| type *(optional)* | String | The type of row object. Each type will conform to a published schema.<br>**Default:** `edanmdm`<br>**Allowed values:** `edanmdm`, `ead_collection`, `ead_component`, `all` |
| row_group *(optional)* | String | The designated set of row types you are filtering against. Objects refers to objects, artifacts, specimens. Archives are all archives collection and item records.<br>**Default:** `objects`<br>**Allowed values:** `objects`, `archives` |
| api_key | String | the API KEY you received from https://api.data.gov/signup/ |

#### Success Response

**HTTP/1.1 200 OK**

```json
{
  "status": 200,
  "responseCode": 1,
  "response": {
    "rows": [{
      "id": "edanmdm-nmaahc_2012.36.4ab",
      "title": "Drumsticks used by Art Blakey",
      "unitCode": "NMAAHC",
      "linkedId": "",
      "type": "edanmdm",
      "url": "edanmdm:nmaahc_2012.36.4ab",
      "content": { "......[see schema documentation for type]...." },
      "hash": "b4c4a61ab9b71eb8777e50b5745c4ab0c75d1999",
      "docSignature": "32081c6289db2620a3d2e61f453ad9330d071335_08dc8e60c5b2eeb3e60dcd71f40072f5",
      "timestamp": 1578947538,
      "lastTimeUpdated": 1578947529,
      "version": "123-1559922770904-1559922814561-0"
    }],
    "rowCount": 1,
    "message": "content found"
  }
}
```

#### Error Response

**HTTP/1.1 404 Not Found**

```json
{
  "status": 404,
  "responseCode": 0,
  "response": {
    "error": "not found: the resource you were acting on could not be found"
  },
  "timestamp": "Fri Jun 07 09:23:09 EDT 2019"
}
```

**HTTP/1.1 400 Bad Request**

```json
{
  "status": 400,
  "responseCode": 0,
  "response": {
    "error": "bad request: one of your params did not pass validation"
  },
  "timestamp": "Fri Jun 07 09:23:09 EDT 2019"
}
```

---

### terms

Fetches an array of terms based on term category

**GET** `https://api.si.edu/openaccess/api/v1.0/terms/:category`

**Permission:** edan

#### Parameters

| Field | Type | Description |
|-------|------|-------------|
| :category | String | the term category<br>**Allowed values:** `culture`, `data_source`, `date`, `object_type`, `online_media_type`, `place`, `topic`, `unit_code` |
| starts_with *(optional)* | String | the optional string prefix filter. |
| api_key | String | the API KEY you received from https://api.data.gov/signup/ |

---

## Smithsonian Institution Office of the Chief Information Officer

[Terms of Use](https://www.si.edu/termsofuse)