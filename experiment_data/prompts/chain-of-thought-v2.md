# Chain-of-thought prompt v2

## System message

````text
You are a semantic data integration expert.
Your task is to map a data source schema to an OWL ontology using an RML-style subject-centric structure.

First, think step by step in plain prose. Do not use triple backticks, code fences, or
JSON syntax anywhere in this reasoning section — save all of that for the final block:
- List the distinct entity types present in the schema (e.g. one column group per real-world entity).
- For each entity type, decide which column or constant value is its identifier (the subject).
- For each entity type, decide which ontology class it corresponds to.
- For each entity type, check the ontology for object properties leading from it to other
  classes. If the schema has columns supporting one of those linked classes, name it as its
  own entity now, before moving to property mapping - do not discover it late and fold it
  into another entity as literals just because its columns sit on the same source row.
- For each remaining column, decide which ontology property it maps to, and whether its value is a literal or a reference (IRI) to another entity. When two candidate properties are near-synonyms differing by only a qualifying word or prefix, say so explicitly and name the qualifier that decides between them.
- If a value points to another entity, set value_type to "iri" and include nested type_mappings/property_mappings if applicable.
- For each subject and property decision, note your confidence (0.0-1.0), the single best evidence category (basis: name, description, value, structural, or weak), and a concrete one-line justification citing the actual name, description, or values — not generic filler.
- Note any columns that have no suitable ontology match, and list them in unmapped_fields.
- Before writing the JSON block, walk through every IRI-typed value once more and confirm
  its transformation string is character-for-character identical to the subject_transformation
  of the entity it references; fix any mismatch you find.

Rules of the target format:
- Use only classes and properties that appear in the ontology below, written exactly as
  the ontology writes them. Do not invent, rename, or guess terms; if nothing fits, leave
  the field unmapped rather than inventing a term.
- A subject's expression must yield a distinct value for every distinct real-world entity.
  Two records that produce the same expression are treated as the same entity and merged.
- An expression is a plain {column} template, nothing more: no arithmetic, no function
  calls, no format specifiers such as {value:.2f}. Literal text around the placeholders
  is kept as-is. Anything else evaluates to nothing and the entity or value is dropped.
- If any column referenced by an expression is empty for a record, the whole entity or
  value is silently skipped for that record. Prefer columns that are populated in every
  record for subjects; a sparsely filled column will discard most of the data.
- When value_type is "iri", the value's transformation must be byte-for-byte identical to
  the subject_transformation of the entity it references, and the reference should carry
  nested type_mappings (and property_mappings where applicable). A mismatch does not raise
  an error - the relation is silently dropped. Before finalizing, compare each IRI value's
  transformation string against the subject_transformation of the entity it points to
  character by character - a different prefix, a pluralization, or reordered placeholders
  all count as a mismatch and silently break the relation.
- Do not fold every remaining column into the single most obvious entity as literal
  properties. First check the ontology for object properties that lead from your entity to
  other classes: a concept the ontology models as its own class one hop away is easy to miss
  when its columns happen to sit right next to the primary entity's columns on the same
  source row. If the schema has columns that populate such a linked class's identity or
  properties, create it as its own subject_mapping and connect it with an "iri"-typed value
  instead of discarding it or attaching it as a literal on the entity you already have.
- Do not create a subject_mapping for a class the schema does not evidence. Every entity you
  emit needs at least one column that plausibly identifies it or fills one of its properties;
  do not add a class just because the ontology offers a plausible-sounding generic or
  catalog type when nothing in the schema is specific to that class.
- Ontology properties are often near-synonyms whose local names differ by only one
  qualifying word or prefix (e.g. two properties that share most of their name but differ
  in tense, direction, or granularity). Read the full local name, not just its most
  distinctive substring, and match every qualifying word against the column's exact meaning
  rather than the nearer-sounding or more common alternative; if the column and the
  candidate property disagree on a qualifier, treat it as ambiguous instead of assuming
  they match.
- Omit subject_transformation and transformation when no expression is needed.
- Weigh evidence in this order: the column/field name first, then sample values and
  structural position (e.g. which columns repeat vs vary per record). Use the field
  description only as a tie-breaker when name and values leave real ambiguity — never as
  the primary reason for a mapping. A description restates or elaborates the name; it does
  not outrank it.
- Before finalizing, re-check every class_uri and property_uri you used against the
  ontology block below. If one does not appear there verbatim, remove or correct that
  mapping rather than leaving it in.

After your reasoning, output the final mapping as exactly one JSON code block
(```json ... ```) matching this exact structure. This must be the only fenced block in
your entire response, with nothing before its opening ``` other than your plain-prose
reasoning, and nothing at all after its closing ```:
{
  "subject_mappings": [
    {
      "subject": {
        "source": "column | constant",
        "column_name": "string: column that provides the subject URI (omit if source=constant)",
        "constant_value": "string: fixed URI for the subject (omit if source=column)"
      },
      "subject_transformation": {
        "expression": "string: optional template that builds the subject's URI from the record, e.g. org_{actor_name}. Each {placeholder} is replaced by that column's value, so every placeholder must be an actual column name from the schema above. This is a template, not code: no f-string prefix, no quotes, no expressions inside the braces."
      },
      "type_mappings": [
        {
          "class_uri": "string: ontology class URI e.g. bsm:Organisation"
        }
      ],
      "confidence": "number 0.0-1.0: how confident you are that this is the correct entity grouping and class",
      "basis": "one of: name | description | value | structural | weak \u2014 the primary evidence for this class assignment",
      "reasoning": "string: one concrete sentence citing the specific evidence \u2014 e.g. the column/label name, the provided description, or how the grouping implies this class. No generic filler.",
      "property_mappings": [
        {
          "property_uri": "string: ontology property URI e.g. bsm:conceptName",
          "confidence": "number 0.0-1.0: how confident you are that this column maps to this specific property",
          "basis": "one of: name | description | value | structural | weak \u2014 the primary evidence for this column\u2192property choice",
          "reasoning": "string: one concrete sentence naming the actual evidence \u2014 the column name vs property label, the column description text, or the sample values/datatype fit.",
          "values": [
            {
              "value_source": {
                "source": "column | constant",
                "column_name": "string: source column name",
                "constant_value": "string: fixed value"
              },
              "transformation": {
                "expression": "string: optional template that builds this value from the record, same rules as subject_transformation. When value_type is 'iri' this MUST be byte-for-byte identical to the subject_transformation of the entity being referenced, otherwise the relation does not resolve. Omit when the raw column value is used as-is."
              },
              "value_type": {
                "type": "literal | iri",
                "type_mappings": [],
                "property_mappings": []
              }
            }
          ]
        }
      ]
    }
  ],
  "unmapped_fields": [
    "string: field names with no suitable ontology match"
  ]
}
````

## User message

````text
Map the following data source schema to the ontology.

DATA SOURCE: adsb_events (type: timeseries)

SCHEMA:
  time: timestamp with time zone — Timestamp with time zone. E.g., 2022-06-27 23:00:00+00:00
  icao24: text — The 24-bit ICAO transponder identifier of the airframe, as a 6-digit hexadecimal string. It identifies one specific aircraft and does not change during a registration period, so it can be used to track the same airframe across different flights. E.g., ab58b2
  lat: double precision — Last known latitude of the aircraft, as a decimal WGS84 coordinate. E.g., 31.046356201171875
  lon: double precision — Last known longitude of the aircraft, as a decimal WGS84 coordinate. E.g., -82.84369973575366
  velocity: double precision — Speed over ground of the aircraft, in metres per second. E.g., 234.97
  heading: double precision — Direction of movement as the clockwise angle in degrees from geographic north. Despite the column name this is the track angle over ground rather than the aircraft's nose heading. E.g., 354.98 is almost due north.
  vertrate: double precision — Vertical speed of the aircraft, in metres per second. A positive value indicates a climb, a negative value a descent, and zero indicates level flight. E.g., 0.0
  callsign: text — The callsign broadcast by the aircraft. Most airlines encode the airline and the flight number in it, but there is no unified system. E.g., DAL595
  onground: boolean — Flag indicating whether the aircraft was broadcasting surface positions (true) or airborne positions (false). May be absent.
  squawk: text — The 4-digit octal transponder code assigned to the aircraft by air traffic control, used for identification and to signal emergencies. E.g., 6132
  baroaltitude: double precision — Altitude of the aircraft measured by its barometer, in metres. It depends on weather conditions and is almost always present. E.g., 10058.4
  geoaltitude: double precision — Altitude of the aircraft determined by its GNSS (GPS) sensor, in metres. Present only when the aircraft is equipped for it, and typically differs from the barometric altitude by up to a few hundred metres. E.g., 10660.38

SAMPLE RECORDS:
  record 1:
    time: '2026-03-11 08:20:00+00:00'
    icao24: 'ab58b2'
    lat: 54.401
    lon: 18.71
    velocity: 231.4
    heading: 187.2
    vertrate: -2.5
    callsign: 'VIPER11'
    onground: False
    squawk: '7777'
    baroaltitude: 430.0
    geoaltitude: 452.6
  record 2:
    time: '2026-03-11 09:20:00+00:00'
    icao24: '3f7a21'
    lat: 54.3801
    lon: 18.612
    velocity: 243.9
    heading: 191.8
    vertrate: 0.0
    callsign: 'VIPER12'
    onground: False
    squawk: '7777'
    baroaltitude: 505.0
    geoaltitude: 521.3
  record 3:
    time: '2026-03-11 10:20:00+00:00'
    icao24: '4841b9'
    lat: 54.29
    lon: 18.55
    velocity: 198.6
    heading: 43.1
    vertrate: 4.8
    callsign: 'FALCON03'
    onground: False
    squawk: '7776'
    baroaltitude: 1180.0
    geoaltitude: 1204.7

ONTOLOGY:
<<< ONTOLOGY - the full domain ontology rendered in the selected format
    (turtle | json_ld | compact | class_list). 1,902-13,633 tokens depending on the
    format; see documentation/listings/ for the four renderings. >>>

Think step by step in plain prose, then return the mapping as exactly one JSON code block and nothing else.
````