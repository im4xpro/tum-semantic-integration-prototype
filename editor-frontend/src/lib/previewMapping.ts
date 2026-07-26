import type {
  MappingDocument,
  ExtractedSchema,
  OntologyProperty,
  PropertySource,
  CodeTransformation,
} from '../types';

// ─── helpers ────────────────────────────────────────────────────────────────

function resolveCompact(uri: string, namespaces: Record<string, string>): string {
  const colon = uri.indexOf(':');
  if (colon === -1) return uri;
  const prefix = uri.slice(0, colon);
  const ns = namespaces[prefix];
  return ns ? ns + uri.slice(colon + 1) : uri;
}

export function shortenUri(uri: string, namespaces: Record<string, string>): string {
  for (const [prefix, ns] of Object.entries(namespaces)) {
    if (uri.startsWith(ns)) return `${prefix}:${uri.slice(ns.length)}`;
  }
  return uri;
}

// Handles flat column names and dotted document-schema names like "Person.name"
function getRecordValue(key: string, record: Record<string, unknown>): string | undefined {
  const direct = record[key];
  if (direct !== undefined && direct !== null) {
    if (Array.isArray(direct)) return direct.length > 0 ? String(direct[0]) : undefined;
    return String(direct);
  }
  const dot = key.indexOf('.');
  if (dot !== -1) {
    const entity = key.slice(0, dot);
    const field = key.slice(dot + 1);
    if (record['schema'] === entity) {
      const props = record['properties'];
      if (props && typeof props === 'object' && !Array.isArray(props)) {
        const val = (props as Record<string, unknown>)[field];
        if (val !== undefined && val !== null) {
          if (Array.isArray(val)) return val.length > 0 ? String(val[0]) : undefined;
          return String(val);
        }
      }
    }
  }
  return undefined;
}

function evaluate(
  source: PropertySource,
  transformation: CodeTransformation | undefined,
  record: Record<string, unknown>,
): string | null {
  if (transformation?.expression) {
    return transformation.expression.replace(
      /\{([\w.]+)\}/g,
      (_, k) => getRecordValue(k, record) ?? `{${k}}`,
    );
  }
  switch (source.source) {
    case 'column':
      if (!source.column_name) return null;
      return getRecordValue(source.column_name, record) ?? null;
    case 'constant':
      return source.constant_value ?? null;
    case 'row_index':
      return '(row index)';
  }
}

// ─── output types ────────────────────────────────────────────────────────────

export interface PreviewTriple {
  predicateLabel: string;
  predicateUri: string;
  value: string;
  isIri: boolean;
  missing: boolean;
}

export interface PreviewSubject {
  subjectIndex: number;
  uriExpr: string;
  uri: string | null;
  typeLabels: string[];
  triples: PreviewTriple[];
}

export interface SamplePreview {
  sampleIndex: number;
  sampleId: string;
  subjects: PreviewSubject[];
}

// ─── main ────────────────────────────────────────────────────────────────────

export function previewMapping(
  mapping: MappingDocument,
  schema: ExtractedSchema | null,
  properties: OntologyProperty[],
): SamplePreview[] {
  const ns = mapping.namespaces;
  const samples = schema?.sample_records ?? [];

  const propLabelFor = (uri: string): string => {
    const full = resolveCompact(uri, ns);
    return (
      properties.find((p) => p.uri === full)?.label ??
      uri.split(/[#/:]/).pop() ??
      uri
    );
  };

  return samples.map((record, sampleIndex) => {
    // Pass 1: resolve all subject URIs so IRI cross-references can be looked up
    const subjectUris: (string | null)[] = mapping.subject_mappings.map((sm) =>
      evaluate(sm.subject, sm.subject_transformation, record),
    );

    const subjects: PreviewSubject[] = mapping.subject_mappings.map((sm, si) => {
      const uri = subjectUris[si];

      const uriExpr =
        sm.subject_transformation?.expression ??
        (sm.subject.source === 'column'
          ? `{${sm.subject.column_name ?? ''}}`
          : sm.subject.constant_value ?? '');

      const typeLabels = (sm.type_mappings ?? []).map((tm) =>
        shortenUri(resolveCompact(tm.class_uri, ns), ns),
      );

      const triples: PreviewTriple[] = (sm.property_mappings ?? []).flatMap((pm) =>
        (pm.values ?? []).map((vd) => {
          const isIri = vd.value_type.type === 'iri';
          let value: string | null = null;

          // IRI cross-reference: resolve to the other subject's URI
          if (isIri) {
            const refClass = vd.value_type.type_mappings?.[0]?.class_uri;
            if (refClass) {
              const refSi = mapping.subject_mappings.findIndex((other, oi) => {
                if (oi === si) return false;
                if (other.type_mappings?.[0]?.class_uri !== refClass) return false;
                if (vd.value_source.source === 'column' && other.subject.source === 'column')
                  return vd.value_source.column_name === other.subject.column_name;
                if (vd.value_source.source === 'constant' && other.subject.source === 'constant')
                  return vd.value_source.constant_value === other.subject.constant_value;
                return true;
              });
              if (refSi !== -1) value = subjectUris[refSi];
            }
          }

          if (value === null) {
            value = evaluate(vd.value_source, vd.transformation, record);
          }

          const missing = value === null || value === '';
          return {
            predicateLabel: propLabelFor(pm.property_uri),
            predicateUri: resolveCompact(pm.property_uri, ns),
            value: missing ? '—' : value!,
            isIri,
            missing,
          };
        }),
      );

      return { subjectIndex: si, uriExpr, uri, typeLabels, triples };
    });

    const sampleId = String(
      record['id'] ?? record['_id'] ?? record['caption'] ??
      record['event_id'] ?? record['name'] ?? `#${sampleIndex + 1}`,
    );

    return { sampleIndex, sampleId, subjects };
  });
}
