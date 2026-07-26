import { useMemo } from 'react';
import type {
  MappingDocument,
  OntologyClass,
  OntologyProperty,
  PropertySource,
  ValueType,
} from '../../types';
import { resolveUri, computeDomainProps } from '../../lib/ontologyGraph';

function describeSource(src: PropertySource): string {
  if (src.source === 'column') return src.column_name ? `column "${src.column_name}"` : 'column (unset)';
  if (src.source === 'constant') return src.constant_value ? `constant "${src.constant_value}"` : 'constant (unset)';
  return 'row index';
}

interface SubjectUsage {
  subjectIndex: number;
  subject: PropertySource;
  propertySources: Map<string, { source: PropertySource; valueType: ValueType }[]>;
}

function findSubjectUsages(mapping: MappingDocument, classUri: string): SubjectUsage[] {
  const namespaces = mapping.namespaces;
  const usages: SubjectUsage[] = [];

  (mapping.subject_mappings ?? []).forEach((sm, si) => {
    const matches = (sm.type_mappings ?? []).some((tm) => resolveUri(tm.class_uri, namespaces) === classUri);
    if (!matches) return;

    const propertySources = new Map<string, { source: PropertySource; valueType: ValueType }[]>();
    (sm.property_mappings ?? []).forEach((pm) => {
      const uri = resolveUri(pm.property_uri, namespaces);
      const list = propertySources.get(uri) ?? [];
      (pm.values ?? []).forEach((v) => list.push({ source: v.value_source, valueType: v.value_type }));
      propertySources.set(uri, list);
    });

    usages.push({ subjectIndex: si, subject: sm.subject, propertySources });
  });

  return usages;
}

interface Props {
  selectedClass: OntologyClass;
  classes: OntologyClass[];
  properties: OntologyProperty[];
  mapping: MappingDocument | null;
  onClose: () => void;
}

export function OntologyCoveragePanel({ selectedClass, classes, properties, mapping, onClose }: Props) {
  const domainProps = useMemo(
    () => computeDomainProps(selectedClass.uri, classes, properties),
    [selectedClass, classes, properties],
  );

  const usages = useMemo(
    () => (mapping ? findSubjectUsages(mapping, selectedClass.uri) : []),
    [mapping, selectedClass],
  );

  return (
    <div className="w-80 flex-shrink-0 bg-gray-50 border-l border-gray-200 flex flex-col h-full overflow-y-auto">
      <div className="px-3 py-2 border-b border-gray-200 bg-white flex items-start justify-between sticky top-0 z-10">
        <div className="min-w-0">
          <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Class</div>
          <div className="text-sm font-semibold text-gray-800 truncate" title={selectedClass.label}>
            {selectedClass.label}
          </div>
          <div className="text-[10px] text-gray-400 font-mono truncate" title={selectedClass.uri}>
            {selectedClass.uri}
          </div>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-lg flex-shrink-0 ml-2">&times;</button>
      </div>

      {selectedClass.comment && (
        <p className="px-3 py-2 text-xs text-gray-500 italic border-b border-gray-200 bg-white">{selectedClass.comment}</p>
      )}

      <div className="px-3 py-3">
        {!mapping ? (
          <div className="text-xs text-gray-400 italic">Load a mapping to see coverage details.</div>
        ) : usages.length === 0 ? (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
            ✖ Not used as a subject in the loaded mapping.
          </div>
        ) : (
          usages.map((u) => (
            <div key={u.subjectIndex} className="mb-3 border border-gray-200 rounded-md bg-white overflow-hidden last:mb-0">
              <div className="px-2 py-1.5 bg-indigo-50 text-[11px] font-medium text-indigo-700 border-b border-indigo-100">
                Subject mapping #{u.subjectIndex + 1} — subject from {describeSource(u.subject)}
              </div>
              <div className="divide-y divide-gray-100">
                {domainProps.map((p) => {
                  const sources = u.propertySources.get(p.uri) ?? [];
                  return (
                    <div key={p.uri} className={`px-2 py-1.5 flex items-start gap-1.5 ${p.inheritedFrom ? 'bg-gray-50/60' : ''}`}>
                      <span className={`mt-0.5 text-[10px] flex-shrink-0 ${sources.length ? 'text-emerald-500' : 'text-gray-300'}`}>
                        {sources.length ? '✓' : '○'}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1 flex-wrap">
                          <span className="text-[11px] font-medium text-gray-700 truncate" title={p.label}>{p.label}</span>
                          {p.inheritedFrom && (
                            <span className="text-[9px] bg-slate-100 text-slate-500 rounded px-1 flex-shrink-0 whitespace-nowrap">
                              ⊂ {p.inheritedFrom}
                            </span>
                          )}
                        </div>
                        {sources.length > 0 ? (
                          sources.map((s, i) => (
                            <div key={i} className="text-[10px] text-gray-400 truncate">
                              ← {describeSource(s.source)} ({s.valueType.type})
                            </div>
                          ))
                        ) : (
                          <div className="text-[10px] text-gray-300 italic">not mapped</div>
                        )}
                      </div>
                    </div>
                  );
                })}
                {domainProps.length === 0 && (
                  <div className="px-2 py-1.5 text-[10px] text-gray-400">No declared properties for this class.</div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
