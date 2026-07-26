import { useState, useMemo } from 'react';
import type { MappingDocument, ExtractedSchema, OntologyProperty } from '../types';
import { previewMapping, shortenUri, type PreviewSubject, type SamplePreview } from '../lib/previewMapping';

// ─── subject card ─────────────────────────────────────────────────────────

function SubjectCard({ subject, namespaces }: { subject: PreviewSubject; namespaces: Record<string, string> }) {
  const displayUri = subject.uri ? shortenUri(subject.uri, namespaces) : null;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* header */}
      <div className="bg-indigo-600 px-3 py-2">
        <div className="flex items-center gap-2 flex-wrap">
          {subject.typeLabels.map((t) => (
            <span key={t} className="text-[11px] bg-indigo-500 text-indigo-100 rounded px-1.5 py-0.5 font-mono">
              {t}
            </span>
          ))}
        </div>
        <div className="mt-1">
          {subject.uri ? (
            <span className="text-xs text-white font-mono break-all">{subject.uri}</span>
          ) : (
            <span className="text-xs text-indigo-300 italic">
              {subject.uriExpr ? `${subject.uriExpr} → (unresolved)` : '(no subject URI)'}
            </span>
          )}
          {displayUri && displayUri !== subject.uri && (
            <span className="text-[10px] text-indigo-300 ml-2 font-mono">≡ {displayUri}</span>
          )}
        </div>
      </div>

      {/* triples */}
      {subject.triples.length === 0 ? (
        <div className="px-3 py-2 text-xs text-gray-400 italic">No property mappings</div>
      ) : (
        <div className="divide-y divide-gray-100">
          {subject.triples.map((t, i) => (
            <div key={i} className={`flex items-start gap-2 px-3 py-1.5 text-xs ${t.missing ? 'opacity-40' : ''}`}>
              <span className="text-gray-500 font-medium flex-shrink-0 min-w-[120px] truncate" title={t.predicateUri}>
                {t.predicateLabel}
              </span>
              <span className="text-gray-300 flex-shrink-0">→</span>
              {t.missing ? (
                <span className="text-gray-400 italic">not in this sample</span>
              ) : t.isIri ? (
                <span className="text-violet-700 font-mono break-all">{t.value}</span>
              ) : (
                <span className="text-emerald-700 font-mono break-all">"{t.value}"</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── sample panel ─────────────────────────────────────────────────────────

function SamplePanel({ preview, namespaces }: { preview: SamplePreview; namespaces: Record<string, string> }) {
  if (preview.subjects.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
        No subject mappings defined yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {preview.subjects.map((s) => (
        <SubjectCard key={s.subjectIndex} subject={s} namespaces={namespaces} />
      ))}
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────

interface Props {
  mapping: MappingDocument;
  schema: ExtractedSchema | null;
  properties: OntologyProperty[];
}

export function MappingPreview({ mapping, schema, properties }: Props) {
  const [activeTab, setActiveTab] = useState(0);

  const previews = useMemo(
    () => previewMapping(mapping, schema, properties),
    [mapping, schema, properties],
  );

  if (!schema || schema.sample_records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
        <div className="text-4xl">📋</div>
        <div className="text-sm">No sample records in this schema.</div>
        <div className="text-xs text-gray-400">Add sample data when editing the source to see a preview here.</div>
      </div>
    );
  }

  const current = previews[activeTab] ?? previews[0];

  return (
    <div className="flex flex-col h-full">
      {/* tab bar */}
      <div className="flex items-center gap-1 px-4 py-2 bg-white border-b border-gray-200 overflow-x-auto flex-shrink-0">
        <span className="text-xs text-gray-400 whitespace-nowrap mr-2">Sample:</span>
        {previews.map((p, i) => (
          <button
            key={i}
            onClick={() => setActiveTab(i)}
            className={`px-3 py-1 text-xs rounded-full whitespace-nowrap transition-colors flex-shrink-0 ${
              activeTab === i
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <span className="opacity-60 mr-1">#{i + 1}</span>
            <span className="max-w-[140px] truncate inline-block align-bottom">{p.sampleId}</span>
          </button>
        ))}
      </div>

      {/* content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-3xl mx-auto">
          <div className="mb-3 text-xs text-gray-400">
            Sample {activeTab + 1} of {previews.length} —{' '}
            <span className="font-mono text-gray-500">{current.sampleId}</span>
          </div>
          <SamplePanel preview={current} namespaces={mapping.namespaces} />
        </div>
      </div>
    </div>
  );
}
