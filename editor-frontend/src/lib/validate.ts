import type { MappingDocument, ExtractedSchema, ValidationResult } from '../types';

export function validateMapping(
  mapping: MappingDocument,
  schema: ExtractedSchema | null,
): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!mapping.base_uri) warnings.push('No base URI configured');
  if (mapping.subject_mappings.length === 0) warnings.push('No subject mappings defined');

  // Build the set of valid column names.
  // For document schemas (columns empty), use inferred_fields as the primary set,
  // then supplement with every key seen in sample records (catches top-level fields
  // like "id", "_id", "caption" that are real but not listed in inferred_fields).
  const cols = schema
    ? (schema.columns.length > 0 ? schema.columns : schema.inferred_fields)
    : [];
  const columnNames = new Set(cols.map((c) => c.name));

  if (schema) {
    for (const record of schema.sample_records) {
      for (const key of Object.keys(record)) columnNames.add(key);
    }
  }

  // Pre-build the set of class URIs that have their own subject mapping, so we
  // can detect IRI cross-references and skip column validation for them.
  const subjectClassUris = new Set(
    mapping.subject_mappings.flatMap((sm) =>
      (sm.type_mappings ?? []).map((tm) => tm.class_uri),
    ),
  );

  function isIriCrossRef(v: { value_type: { type: string; type_mappings: { class_uri: string }[] } }): boolean {
    return (
      v.value_type.type === 'iri' &&
      v.value_type.type_mappings.some((tm) => subjectClassUris.has(tm.class_uri))
    );
  }

  for (const [si, sm] of mapping.subject_mappings.entries()) {
    const label = sm.label || `Subject ${si + 1}`;

    if (sm.type_mappings.length === 0) {
      errors.push(`${label}: no type mappings (class) assigned`);
    }

    // If a subject_transformation expression is present it drives URI generation,
    // so the raw source/column_name is irrelevant — skip column validation.
    if (sm.subject.source === 'column' && !sm.subject_transformation?.expression) {
      if (!sm.subject.column_name) {
        errors.push(`${label}: subject column not specified`);
      } else if (schema && !columnNames.has(sm.subject.column_name)) {
        errors.push(`${label}: subject references unknown column "${sm.subject.column_name}"`);
      }
    }

    for (const pm of sm.property_mappings) {
      for (const v of pm.values) {
        // IRI values that reference another subject mapping are cross-references:
        // their value_source is derived from the linked subject, not a raw column
        // read, so column validation doesn't apply.
        if (isIriCrossRef(v)) continue;
        if (v.transformation?.expression) continue;

        if (v.value_source.source === 'column') {
          if (!v.value_source.column_name) {
            warnings.push(`${label} / ${pm.property_uri}: value column not specified`);
          } else if (schema && !columnNames.has(v.value_source.column_name)) {
            errors.push(
              `${label} / ${pm.property_uri}: references unknown column "${v.value_source.column_name}"`,
            );
          }
        }
      }
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}
