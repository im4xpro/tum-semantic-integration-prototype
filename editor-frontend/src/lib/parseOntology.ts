import { Parser, Store } from 'n3';
import type { OntologyClass, OntologyProperty } from '../types';

// ── URIs ──────────────────────────────────────────────────────────────────────

const RDF_TYPE       = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
const OWL_CLASS      = 'http://www.w3.org/2002/07/owl#Class';
const OWL_OBJ_PROP   = 'http://www.w3.org/2002/07/owl#ObjectProperty';
const OWL_DATA_PROP  = 'http://www.w3.org/2002/07/owl#DatatypeProperty';
const OWL_ANN_PROP   = 'http://www.w3.org/2002/07/owl#AnnotationProperty';
const RDFS_CLASS     = 'http://www.w3.org/2000/01/rdf-schema#Class';
const RDFS_LABEL     = 'http://www.w3.org/2000/01/rdf-schema#label';
const RDFS_COMMENT   = 'http://www.w3.org/2000/01/rdf-schema#comment';
const RDFS_SUBCLASS  = 'http://www.w3.org/2000/01/rdf-schema#subClassOf';
const RDFS_DOMAIN    = 'http://www.w3.org/2000/01/rdf-schema#domain';
const RDFS_RANGE     = 'http://www.w3.org/2000/01/rdf-schema#range';

// ── Helpers ───────────────────────────────────────────────────────────────────

function localName(uri: string): string {
  const h = uri.lastIndexOf('#');
  if (h >= 0) return uri.slice(h + 1);
  const s = uri.lastIndexOf('/');
  return s >= 0 ? uri.slice(s + 1) : uri;
}

// Returns the first rdfs:label literal, preferring English if available.
function firstLabel(store: Store, subject: string): string | undefined {
  const objs = store.getObjects(subject, RDFS_LABEL, null);
  const en = objs.find((o) => o.termType === 'Literal' && o.value && (o as { language?: string }).language?.startsWith('en'));
  const any = objs.find((o) => o.termType === 'Literal');
  return (en ?? any)?.value || undefined;
}

function firstComment(store: Store, subject: string): string | undefined {
  const objs = store.getObjects(subject, RDFS_COMMENT, null);
  const en = objs.find((o) => o.termType === 'Literal' && (o as { language?: string }).language?.startsWith('en'));
  const any = objs.find((o) => o.termType === 'Literal');
  return (en ?? any)?.value || undefined;
}

function namedObjects(store: Store, subject: string, predicate: string): string[] {
  return store
    .getObjects(subject, predicate, null)
    .filter((o) => o.termType === 'NamedNode')
    .map((o) => o.value);
}

// ── Parser ────────────────────────────────────────────────────────────────────

export function parseTurtleOntology(
  ttlText: string,
): { classes: OntologyClass[]; properties: OntologyProperty[] } {
  const quads = new Parser().parse(ttlText);
  const store = new Store(quads);

  // ── Classes ─────────────────────────────────────────────────────────────────
  const classUris = new Set<string>();
  for (const typeUri of [OWL_CLASS, RDFS_CLASS]) {
    store
      .getSubjects(RDF_TYPE, typeUri, null)
      .filter((s) => s.termType === 'NamedNode')
      .forEach((s) => classUris.add(s.value));
  }

  const classes: OntologyClass[] = [...classUris].map((uri) => ({
    uri,
    label: firstLabel(store, uri) ?? localName(uri),
    comment: firstComment(store, uri),
    subclass_of: namedObjects(store, uri, RDFS_SUBCLASS),
    is_extension: false,
  }));

  // ── Properties ──────────────────────────────────────────────────────────────
  const propsSeen = new Set<string>();
  const propEntries: { uri: string; isObj: boolean }[] = [];

  for (const [typeUri, isObj] of [
    [OWL_OBJ_PROP,  true ],
    [OWL_DATA_PROP, false],
    [OWL_ANN_PROP,  false],
  ] as [string, boolean][]) {
    store
      .getSubjects(RDF_TYPE, typeUri, null)
      .filter((s) => s.termType === 'NamedNode' && !propsSeen.has(s.value))
      .forEach((s) => {
        propsSeen.add(s.value);
        propEntries.push({ uri: s.value, isObj });
      });
  }

  const properties: OntologyProperty[] = propEntries.map(({ uri, isObj }) => ({
    uri,
    label: firstLabel(store, uri) ?? localName(uri),
    comment: firstComment(store, uri),
    domain: namedObjects(store, uri, RDFS_DOMAIN),
    range_: namedObjects(store, uri, RDFS_RANGE),
    is_object_property: isObj,
    is_extension: false,
  }));

  return { classes, properties };
}
