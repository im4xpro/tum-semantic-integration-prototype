import { useState, useMemo } from 'react';
import { Modal } from './Modal';
import type { OntologyProperty, OntologyClass } from '../../types';
import { computeDomainProps, resolveUri as resolveFullUri } from '../../lib/ontologyGraph';
import type { ApplicableProp } from '../../lib/ontologyGraph';

interface Props {
  open: boolean;
  subjectClassUri: string;
  classes: OntologyClass[];
  properties: OntologyProperty[];
  namespaces: Record<string, string>;
  onSelect: (prop: OntologyProperty) => void;
  onClose: () => void;
}

function PropRow({ prop, onPick }: { prop: ApplicableProp; onPick: () => void }) {
  return (
    <button
      className="w-full text-left px-4 py-2.5 hover:bg-indigo-50 transition-colors"
      onClick={onPick}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-medium text-gray-800 text-sm">{prop.label}</span>
        <span
          className={`text-[10px] px-1 rounded flex-shrink-0 ${
            prop.is_object_property
              ? 'bg-violet-100 text-violet-700'
              : 'bg-green-100 text-green-700'
          }`}
        >
          {prop.is_object_property ? 'object' : 'data'}
        </span>
        {prop.inheritedFrom && (
          <span className="text-[10px] bg-slate-100 text-slate-500 rounded px-1 flex-shrink-0">
            ⊂ {prop.inheritedFrom}
          </span>
        )}
        {prop.is_extension && (
          <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1 flex-shrink-0">ext</span>
        )}
      </div>
      <div className="text-xs text-gray-400 font-mono truncate">{prop.uri}</div>
      {prop.comment && (
        <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">{prop.comment}</div>
      )}
    </button>
  );
}

export function AddPropertyDialog({
  open,
  subjectClassUri,
  classes,
  properties,
  namespaces,
  onSelect,
  onClose,
}: Props) {
  const [query, setQuery] = useState('');
  const [showAll, setShowAll] = useState(false);

  const fullClassUri = useMemo(
    () => resolveFullUri(subjectClassUri, namespaces),
    [subjectClassUri, namespaces],
  );

  // Properties scoped to this class with inheritedFrom annotation
  const domainProps = useMemo(
    () => computeDomainProps(fullClassUri, classes, properties),
    [fullClassUri, classes, properties],
  );

  // For "show all", wrap every property with inheritedFrom derived from domainProps
  const allProps = useMemo((): ApplicableProp[] => {
    const domainMap = new Map(domainProps.map((p) => [p.uri, p.inheritedFrom]));
    return properties.map((p) => ({
      ...p,
      inheritedFrom: domainMap.has(p.uri) ? (domainMap.get(p.uri) ?? null) : null,
    }));
  }, [properties, domainProps]);

  const source = showAll ? allProps : domainProps;

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    if (!q) return source;
    return source.filter(
      (p) =>
        p.label.toLowerCase().includes(q) ||
        p.uri.toLowerCase().includes(q) ||
        (p.comment ?? '').toLowerCase().includes(q),
    );
  }, [source, query]);

  const pick = (prop: OntologyProperty) => {
    onSelect(prop);
    onClose();
    setQuery('');
    setShowAll(false);
  };

  // When no search query, split into direct / inherited groups for clarity
  const showGrouped = !query;
  const direct = showGrouped ? filtered.filter((p) => p.inheritedFrom === null) : [];
  const inherited = showGrouped ? filtered.filter((p) => p.inheritedFrom !== null) : [];

  return (
    <Modal open={open} title="Add Property" onClose={onClose} width="max-w-xl">
      <div className="flex items-center gap-2 mb-2">
        <input
          autoFocus
          type="text"
          placeholder="Search properties…"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="flex items-center gap-1 text-xs text-gray-500 whitespace-nowrap cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
            className="accent-indigo-500"
          />
          Show all
        </label>
      </div>

      {!showAll && !query && (
        <p className="text-xs text-gray-400 mb-2">
          {domainProps.length} properties for{' '}
          <span className="font-mono">{subjectClassUri || '(no class)'}</span>
          {' '}— {direct.length} direct, {inherited.length} inherited
        </p>
      )}

      <div className="overflow-y-auto max-h-96 divide-y divide-gray-100 border border-gray-200 rounded-lg">
        {filtered.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-8">No properties found</div>
        ) : showGrouped ? (
          <>
            {direct.length > 0 && (
              <>
                <div className="px-4 py-1.5 bg-gray-50 text-[10px] font-semibold text-gray-500 uppercase tracking-wide sticky top-0">
                  Direct ({direct.length})
                </div>
                {direct.map((p) => <PropRow key={p.uri} prop={p} onPick={() => pick(p)} />)}
              </>
            )}
            {inherited.length > 0 && (
              <>
                <div className="px-4 py-1.5 bg-gray-50 text-[10px] font-semibold text-gray-500 uppercase tracking-wide sticky top-0">
                  Inherited ({inherited.length})
                </div>
                {inherited.map((p) => <PropRow key={p.uri} prop={p} onPick={() => pick(p)} />)}
              </>
            )}
          </>
        ) : (
          filtered.map((p) => <PropRow key={p.uri} prop={p} onPick={() => pick(p)} />)
        )}
      </div>
    </Modal>
  );
}
