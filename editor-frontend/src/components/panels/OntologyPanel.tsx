import { useState, useMemo } from 'react';
import type { OntologyClass, OntologyProperty } from '../../types';
import { computeAncestors, computeDomainProps, computeLeafClasses } from '../../lib/ontologyGraph';

interface Props {
  classes: OntologyClass[];
  properties: OntologyProperty[];
  onAddSubject: (cls: OntologyClass) => void;
}

export function OntologyPanel({ classes, properties, onAddSubject }: Props) {
  const [query, setQuery] = useState('');
  const [expandedClass, setExpandedClass] = useState<string | null>(null);
  const [tab, setTab] = useState<'classes' | 'properties'>('classes');

  const leafClasses = useMemo(() => computeLeafClasses(classes), [classes]);

  const filteredClasses = useMemo(() => {
    const q = query.toLowerCase();
    return classes.filter(
      (c) => c.label.toLowerCase().includes(q) || c.uri.toLowerCase().includes(q),
    );
  }, [classes, query]);

  const filteredProperties = useMemo(() => {
    const q = query.toLowerCase();
    return properties.filter(
      (p) => p.label.toLowerCase().includes(q) || p.uri.toLowerCase().includes(q),
    );
  }, [properties, query]);

  const expandedProps = useMemo(
    () => (expandedClass ? computeDomainProps(expandedClass, classes, properties) : []),
    [expandedClass, classes, properties],
  );

  const expandedCls = useMemo(
    () => classes.find((c) => c.uri === expandedClass) ?? null,
    [classes, expandedClass],
  );

  return (
    <div className="flex flex-col h-full bg-gray-50 border-l border-gray-200">
      {/* ── Header ── */}
      <div className="px-3 py-2 border-b border-gray-200 bg-white">
        <div className="text-xs font-bold text-gray-600 uppercase tracking-wide mb-2">
          Ontology Browser
        </div>
        <input
          type="text"
          placeholder="Filter…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full border border-gray-300 rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-300"
        />
        <div className="flex mt-2 gap-1">
          {(['classes', 'properties'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 text-xs py-1 rounded font-medium transition-colors ${
                tab === t ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {t === 'classes'
                ? `Classes (${classes.length})`
                : `Props (${properties.length})`}
            </button>
          ))}
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'classes' ? (
          <div className="divide-y divide-gray-100">
            {filteredClasses.map((cls) => {
              const isLeaf = leafClasses.has(cls.uri);
              const isExpanded = expandedClass === cls.uri;
              return (
                <div key={cls.uri}>
                  <div
                    className="px-3 py-2 hover:bg-white cursor-pointer flex items-start gap-2 group"
                    onClick={() => setExpandedClass(isExpanded ? null : cls.uri)}
                  >
                    <span className="text-gray-400 text-xs mt-0.5 flex-shrink-0">
                      {isExpanded ? '▾' : '▸'}
                    </span>

                    {/* leaf/abstract indicator dot */}
                    <span
                      className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 border ${
                        isLeaf
                          ? 'bg-emerald-400 border-emerald-500'
                          : 'bg-transparent border-gray-400'
                      }`}
                      title={isLeaf ? 'Leaf class — can be instantiated' : 'Abstract class — has subclasses'}
                    />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1 flex-wrap">
                        <span
                          className={`text-xs font-medium truncate ${
                            isLeaf ? 'text-gray-800' : 'text-gray-500'
                          }`}
                        >
                          {cls.label}
                        </span>
                        {!isLeaf && (
                          <span className="text-[9px] bg-gray-100 text-gray-500 rounded px-0.5 flex-shrink-0">
                            abstract
                          </span>
                        )}
                        {cls.is_extension && (
                          <span className="text-[9px] bg-amber-100 text-amber-600 rounded px-0.5 flex-shrink-0">ext</span>
                        )}
                      </div>
                      <div className="text-[10px] text-gray-400 font-mono truncate">
                        {cls.uri.split(/[#/]/).pop()}
                      </div>
                    </div>

                    <button
                      className={`text-[10px] font-medium opacity-0 group-hover:opacity-100 flex-shrink-0 whitespace-nowrap ${
                        isLeaf
                          ? 'text-indigo-500 hover:text-indigo-700'
                          : 'text-amber-500 hover:text-amber-700'
                      }`}
                      onClick={(e) => { e.stopPropagation(); onAddSubject(cls); }}
                      title={
                        isLeaf
                          ? 'Add as subject mapping'
                          : 'Abstract class — consider using a more specific subclass'
                      }
                    >
                      {isLeaf ? '+ add' : '⚠ add'}
                    </button>
                  </div>

                  {/* Expanded property list */}
                  {isExpanded && (
                    <div className="bg-indigo-50 border-y border-indigo-100">
                      {expandedCls?.comment && (
                        <p className="px-4 py-1.5 text-[10px] text-gray-500 italic border-b border-indigo-100">
                          {expandedCls.comment}
                        </p>
                      )}

                      {/* Ancestors breadcrumb */}
                      {(() => {
                        const ancestors = computeAncestors(cls.uri, classes);
                        ancestors.delete(cls.uri);
                        const chain = [...ancestors]
                          .map((a) => classes.find((c) => c.uri === a)?.label ?? a.split(/[#/]/).pop() ?? a)
                          .join(' ⊃ ');
                        return chain ? (
                          <p className="px-4 py-1 text-[10px] text-gray-400 border-b border-indigo-100">
                            ⊂ {chain}
                          </p>
                        ) : null;
                      })()}

                      {expandedProps.length === 0 ? (
                        <p className="px-4 py-2 text-[10px] text-gray-400">No properties declared</p>
                      ) : (
                        expandedProps.map((prop) => (
                          <div
                            key={prop.uri}
                            className={`px-4 py-1.5 flex items-start gap-2 border-b border-indigo-50 last:border-0 ${
                              prop.inheritedFrom ? 'opacity-75' : ''
                            }`}
                          >
                            <span
                              className={`text-[9px] rounded px-0.5 mt-0.5 flex-shrink-0 ${
                                prop.is_object_property
                                  ? 'bg-violet-100 text-violet-600'
                                  : 'bg-green-100 text-green-600'
                              }`}
                            >
                              {prop.is_object_property ? 'obj' : 'data'}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-1 flex-wrap">
                                <span className="text-[11px] font-medium text-gray-700">{prop.label}</span>
                                {prop.inheritedFrom && (
                                  <span className="text-[9px] bg-slate-100 text-slate-500 rounded px-1 flex-shrink-0 whitespace-nowrap">
                                    ⊂ {prop.inheritedFrom}
                                  </span>
                                )}
                              </div>
                              {prop.comment && (
                                <div className="text-[9px] text-gray-400 line-clamp-1">{prop.comment}</div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredProperties.map((prop) => (
              <div key={prop.uri} className="px-3 py-2">
                <div className="flex items-center gap-1 mb-0.5">
                  <span className="text-xs font-medium text-gray-800">{prop.label}</span>
                  <span
                    className={`text-[9px] rounded px-0.5 ${
                      prop.is_object_property
                        ? 'bg-violet-100 text-violet-600'
                        : 'bg-green-100 text-green-600'
                    }`}
                  >
                    {prop.is_object_property ? 'obj' : 'data'}
                  </span>
                </div>
                <div className="text-[10px] text-gray-400 font-mono truncate">
                  {prop.uri.split(/[#/]/).pop()}
                </div>
                {prop.comment && (
                  <div className="text-[10px] text-gray-400 line-clamp-1">{prop.comment}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
