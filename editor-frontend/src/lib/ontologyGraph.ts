import type { MappingDocument, OntologyClass, OntologyProperty, PropertyMapping, SubjectMapping } from '../types';

// ─── URI resolution ─────────────────────────────────────────────────────────

export function resolveUri(uri: string, namespaces: Record<string, string>): string {
  const idx = uri.indexOf(':');
  if (idx === -1) return uri;
  const prefix = uri.slice(0, idx);
  const ns = namespaces[prefix];
  return ns ? ns + uri.slice(idx + 1) : uri;
}

// ─── mapping coverage ───────────────────────────────────────────────────────

export interface MappedUris {
  classes: Set<string>;
  properties: Set<string>;
}

export function collectMappedUris(mapping: MappingDocument): MappedUris {
  const namespaces = mapping.namespaces;
  const classes = new Set<string>();
  const properties = new Set<string>();

  function walkProperty(pm: PropertyMapping) {
    properties.add(resolveUri(pm.property_uri, namespaces));
    (pm.values ?? []).forEach((v) => {
      (v.value_type.type_mappings ?? []).forEach((tm) => classes.add(resolveUri(tm.class_uri, namespaces)));
      (v.value_type.property_mappings ?? []).forEach(walkProperty);
    });
  }

  function walkSubject(sm: SubjectMapping) {
    (sm.type_mappings ?? []).forEach((tm) => classes.add(resolveUri(tm.class_uri, namespaces)));
    (sm.property_mappings ?? []).forEach(walkProperty);
  }

  (mapping.subject_mappings ?? []).forEach(walkSubject);
  return { classes, properties };
}

// ─── ancestor resolution ────────────────────────────────────────────────────

export function computeAncestors(classUri: string, classes: OntologyClass[]): Set<string> {
  const byUri = new Map(classes.map((c) => [c.uri, c]));
  const visited = new Set<string>();
  const queue = [classUri];
  while (queue.length > 0) {
    const uri = queue.shift()!;
    if (visited.has(uri)) continue;
    visited.add(uri);
    byUri.get(uri)?.subclass_of.forEach((p) => queue.push(p));
  }
  return visited;
}

// ─── leaf class detection ───────────────────────────────────────────────────
// A class is a "leaf" if no other class in the loaded ontology lists it as a
// parent. Leaf classes are the concrete, instantiable ones (e.g. Person,
// Organisation). Non-leaf (abstract) classes are meant to be subclassed, not
// used directly as subject mappings (e.g. Actor).

export function computeLeafClasses(classes: OntologyClass[]): Set<string> {
  const known = new Set(classes.map((c) => c.uri));
  const hasChildren = new Set<string>();
  classes.forEach((c) =>
    c.subclass_of.filter((p) => known.has(p)).forEach((p) => hasChildren.add(p)),
  );
  return new Set(classes.filter((c) => !hasChildren.has(c.uri)).map((c) => c.uri));
}

// ─── applicable properties (direct + inherited) ──────────────────────────────

export interface ApplicableProp extends OntologyProperty {
  /** Human-readable label of the class the property is inherited from.
   *  null  = declared directly on this class (or domain is universal).  */
  inheritedFrom: string | null;
}

export function computeDomainProps(
  classUri: string,
  classes: OntologyClass[],
  properties: OntologyProperty[],
): ApplicableProp[] {
  const ancestors = computeAncestors(classUri, classes);
  const byUri = new Map(classes.map((c) => [c.uri, c]));

  return properties
    .filter((p) => p.domain.length === 0 || p.domain.some((d) => ancestors.has(d)))
    .map((p) => {
      const isDirect = p.domain.length === 0 || p.domain.includes(classUri);
      if (isDirect) return { ...p, inheritedFrom: null };
      const parentUri = p.domain.find((d) => ancestors.has(d) && d !== classUri);
      const parentLabel = parentUri
        ? (byUri.get(parentUri)?.label ?? parentUri.split(/[#/]/).pop() ?? parentUri)
        : null;
      return { ...p, inheritedFrom: parentLabel };
    })
    .sort((a, b) => {
      if ((a.inheritedFrom === null) !== (b.inheritedFrom === null))
        return a.inheritedFrom === null ? -1 : 1;
      return a.label.localeCompare(b.label);
    });
}

// ─── hierarchy layout ───────────────────────────────────────────────────────
// Recursive tree layout: leaves are placed first at equal vertical intervals;
// each parent is then centred over the y-range of its children. This preserves
// parent–child alignment far better than the old column-then-alphabetical sort.

export function computeDepths(classes: OntologyClass[]): Map<string, number> {
  const byUri = new Map(classes.map((c) => [c.uri, c]));
  const depths = new Map<string, number>();

  function depth(uri: string, stack: Set<string>): number {
    if (depths.has(uri)) return depths.get(uri)!;
    if (stack.has(uri)) return 0;
    const cls = byUri.get(uri);
    const parents = cls?.subclass_of.filter((p) => byUri.has(p)) ?? [];
    if (parents.length === 0) { depths.set(uri, 0); return 0; }
    const next = new Set(stack); next.add(uri);
    const d = 1 + Math.max(...parents.map((p) => depth(p, next)));
    depths.set(uri, d);
    return d;
  }

  classes.forEach((c) => depth(c.uri, new Set()));
  return depths;
}

const COL_WIDTH = 300;
const ROW_HEIGHT = 120;

export function layoutClasses(
  classes: OntologyClass[],
  depths: Map<string, number>,
): Map<string, { x: number; y: number }> {
  const known = new Set(classes.map((c) => c.uri));

  // children of each class (only within the loaded set)
  const childrenOf = new Map<string, string[]>();
  classes.forEach((c) => {
    c.subclass_of.filter((p) => known.has(p)).forEach((parentUri) => {
      if (!childrenOf.has(parentUri)) childrenOf.set(parentUri, []);
      childrenOf.get(parentUri)!.push(c.uri);
    });
  });
  // sort children alphabetically for deterministic output
  childrenOf.forEach((ch) => ch.sort());

  // roots = classes with no known parent
  const roots = classes
    .filter((c) => !c.subclass_of.some((p) => known.has(p)))
    .sort((a, b) => a.label.localeCompare(b.label));

  const positions = new Map<string, { x: number; y: number }>();
  let leafIndex = 0;

  function assign(uri: string): number {
    // Guard against being placed twice (diamond inheritance)
    if (positions.has(uri)) return positions.get(uri)!.y;

    const depth = depths.get(uri) ?? 0;
    const children = childrenOf.get(uri) ?? [];

    if (children.length === 0) {
      const y = leafIndex * ROW_HEIGHT;
      leafIndex++;
      positions.set(uri, { x: depth * COL_WIDTH, y });
      return y;
    }

    const childYs = children.map((c) => assign(c));
    const centerY = (Math.min(...childYs) + Math.max(...childYs)) / 2;
    positions.set(uri, { x: depth * COL_WIDTH, y: centerY });
    return centerY;
  }

  roots.forEach((r) => assign(r.uri));

  // Place any class not reachable via tree traversal (disconnected or orphaned)
  classes.forEach((c) => {
    if (!positions.has(c.uri)) {
      const depth = depths.get(c.uri) ?? 0;
      positions.set(c.uri, { x: depth * COL_WIDTH, y: leafIndex * ROW_HEIGHT });
      leafIndex++;
    }
  });

  return positions;
}
