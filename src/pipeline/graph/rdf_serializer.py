import re
from typing import cast

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDFS
from rdflib.namespace import XSD as _XSD

from pipeline.extraction.models import ExtractionResult
from pipeline.mapping.models import MappingDocument

# ── Built-in namespace prefixes rdflib already knows ─────────────────────────
_BUILTIN: dict[str, Namespace] = {
    "rdf":  cast(Namespace, RDF),
    "rdfs": cast(Namespace, RDFS),
    "owl":  cast(Namespace, OWL),
    "xsd":  cast(Namespace, _XSD),
}

# ── XSD datatypes mapped from ontology range URIs ────────────────────────────
# Covers the most common OWL/XSD range declarations.
_RANGE_TO_XSD: dict[str, URIRef] = {
    str(_XSD.string):      _XSD.string,
    str(_XSD.integer):     _XSD.integer,
    str(_XSD.int):         _XSD.integer,
    str(_XSD.long):        _XSD.integer,
    str(_XSD.boolean):     _XSD.boolean,
    str(_XSD.dateTime):    _XSD.dateTime,
    str(_XSD.date):        _XSD.date,
    str(_XSD.anyURI):      _XSD.anyURI,
    # Map float/double → decimal so rdflib preserves the original string
    # representation (e.g. "9.0300" stays "9.0300", not "9.03e+00").
    str(_XSD.decimal):     _XSD.decimal,
    str(_XSD.float):       _XSD.decimal,
    str(_XSD.double):      _XSD.decimal,
    "http://www.w3.org/2001/XMLSchema#string":   _XSD.string,
    "http://www.w3.org/2001/XMLSchema#integer":  _XSD.integer,
    "http://www.w3.org/2001/XMLSchema#decimal":  _XSD.decimal,
    "http://www.w3.org/2001/XMLSchema#float":    _XSD.decimal,
    "http://www.w3.org/2001/XMLSchema#double":   _XSD.decimal,
    "http://www.w3.org/2001/XMLSchema#dateTime": _XSD.dateTime,
    "http://www.w3.org/2001/XMLSchema#date":     _XSD.date,
    "http://www.w3.org/2001/XMLSchema#boolean":  _XSD.boolean,
}

# ── Value-string heuristics (fallback when no range declared) ─────────────────
_INT_RE      = re.compile(r'^-?\d+$')
_DECIMAL_RE  = re.compile(r'^-?\d*\.\d+$')
_DATETIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
_DATE_RE     = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_BOOL_MAP    = {"true": True, "false": False, "1": True, "0": False}


def infer_literal(value: str, xsd_type: URIRef | None = None) -> Literal:
    """
    Build an rdflib Literal with the best available datatype.
    If xsd_type is provided (from ontology range), use it directly.
    Otherwise fall back to value-string pattern matching.
    """
    if xsd_type is not None:
        if xsd_type == _XSD.integer:
            try:
                return Literal(int(value), datatype=_XSD.integer)
            except ValueError:
                pass
        if xsd_type in (_XSD.decimal, _XSD.float, _XSD.double):
            try:
                float(value)  # validate; keep original string to avoid 9.03e+00 etc.
                return Literal(value, datatype=xsd_type)
            except ValueError:
                pass
        if xsd_type == _XSD.boolean:
            b = _BOOL_MAP.get(value.lower())
            if b is not None:
                return Literal(b, datatype=_XSD.boolean)
        return Literal(value, datatype=xsd_type)

    # Heuristic fallback
    if _DATETIME_RE.match(value):
        return Literal(value, datatype=_XSD.dateTime)
    if _DATE_RE.match(value):
        return Literal(value, datatype=_XSD.date)
    if _INT_RE.match(value):
        return Literal(int(value), datatype=_XSD.integer)
    if _DECIMAL_RE.match(value):
        # Keep original string to preserve trailing zeros / precision
        return Literal(value, datatype=_XSD.decimal)
    return Literal(value, datatype=_XSD.string)


def build_namespaces(mapping: MappingDocument) -> dict[str, Namespace]:
    """Merge rdflib's built-in prefixes (rdf/rdfs/owl/xsd) with a mapping's declared namespaces."""
    namespaces: dict[str, Namespace] = dict(_BUILTIN)
    for prefix, uri in mapping.namespaces.items():
        namespaces[prefix] = Namespace(uri)
    return namespaces


def resolve_uri(compact: str, namespaces: dict[str, Namespace]) -> URIRef:
    """
    Expand a compact URI (bsm:Action, owl:Thing) to a full URIRef using the
    given prefix -> Namespace map. Falls through to URIRef(uri) if no matching
    prefix is found, which also handles already-expanded full URIs.
    """
    colon = compact.find(':')
    if colon == -1:
        return URIRef(compact)
    prefix, local = compact[:colon], compact[colon + 1:]
    ns = namespaces.get(prefix)
    if ns is not None:
        return ns[local]
    return URIRef(compact)


class RDFSerializer:
    """
    Converts ExtractionResult(s) → rdflib.Graph.

    Usage:
        serializer = RDFSerializer(mapping)
        graph = serializer.serialize(result)
        turtle = graph.serialize(format="turtle")

    Optionally pass a property_ranges dict (predicate_full_uri → xsd_datatype_uri)
    built from the loaded ontology to get accurate literal datatypes.
    """

    def __init__(
        self,
        mapping: MappingDocument,
        property_ranges: dict[str, URIRef] | None = None,
    ):
        self.mapping = mapping
        self._ns: dict[str, Namespace] = build_namespaces(mapping)
        # predicate full-URI → xsd datatype URIRef
        self._property_ranges: dict[str, URIRef] = property_ranges or {}

    # ── Public API ────────────────────────────────────────────────────────────

    def serialize(self, result: ExtractionResult) -> Graph:
        """Serialize one extraction result into a new Graph."""
        g = self._new_graph()
        self._add_result(g, result)
        return g

    def serialize_all(self, results: list[ExtractionResult]) -> Graph:
        """Merge all extraction results into a single Graph (for batch upload)."""
        g = self._new_graph()
        for result in results:
            self._add_result(g, result)
        return g

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _new_graph(self) -> Graph:
        g = Graph()
        for prefix, ns in self._ns.items():
            if prefix not in _BUILTIN:
                g.bind(prefix, ns)
        return g

    def _add_result(self, g: Graph, result: ExtractionResult) -> None:
        entity_uri: dict[str, URIRef] = {}

        for entity in result.entities:
            uri = URIRef(entity.subject_uri)
            entity_uri[entity.temp_id] = uri

            # rdf:type
            g.add((uri, RDF.type, self._resolve(entity.class_uri)))

            # literal properties
            for pred_compact, values in entity.properties.items():
                pred = self._resolve(pred_compact)
                xsd_type = self._property_ranges.get(str(pred))
                for val in values:
                    g.add((uri, pred, infer_literal(str(val), xsd_type)))

        # object-property triples (IRI → IRI)
        for rel in result.relations:
            subj = entity_uri.get(rel.subject_temp_id)
            obj  = entity_uri.get(rel.object_temp_id)
            if subj and obj:
                g.add((subj, self._resolve(rel.predicate_uri), obj))

    def _resolve(self, uri: str) -> URIRef:
        return resolve_uri(uri, self._ns)


# ── Convenience: build property_ranges from a loaded OntologyModel ────────────

def build_property_ranges(ontology) -> dict[str, URIRef]:
    """
    Build a predicate_uri → xsd_datatype map from an OntologyModel
    so the serializer can apply correct datatypes to literal properties.

    Pass the result to RDFSerializer(mapping, property_ranges=...).
    """
    ranges: dict[str, URIRef] = {}
    for prop in ontology.properties:
        if prop.is_object_property:
            continue
        for range_uri in prop.range_:
            xsd = _RANGE_TO_XSD.get(range_uri)
            if xsd is not None:
                ranges[prop.uri] = xsd
                break
    return ranges
