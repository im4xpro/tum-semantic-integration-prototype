import { useState, useMemo } from 'react';
import { Modal } from './Modal';
import type { OntologyClass } from '../../types';

interface Props {
  open: boolean;
  classes: OntologyClass[];
  onSelect: (cls: OntologyClass) => void;
  onClose: () => void;
}

export function AddSubjectDialog({ open, classes, onSelect, onClose }: Props) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return classes.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.uri.toLowerCase().includes(q) ||
        (c.comment ?? '').toLowerCase().includes(q),
    );
  }, [classes, query]);

  return (
    <Modal open={open} title="Select Ontology Class" onClose={onClose} width="max-w-xl">
      <input
        autoFocus
        type="text"
        placeholder="Search classes…"
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 outline-none focus:ring-2 focus:ring-indigo-300"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="overflow-y-auto max-h-96 divide-y divide-gray-100 border border-gray-200 rounded-lg">
        {filtered.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-8">No classes found</div>
        ) : (
          filtered.map((cls) => (
            <button
              key={cls.uri}
              className="w-full text-left px-4 py-2.5 hover:bg-indigo-50 transition-colors"
              onClick={() => { onSelect(cls); onClose(); setQuery(''); }}
            >
              <div className="font-medium text-gray-800 text-sm">{cls.label}</div>
              <div className="text-xs text-gray-400 font-mono truncate">{cls.uri}</div>
              {cls.comment && (
                <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">{cls.comment}</div>
              )}
              {cls.is_extension && (
                <span className="inline-block mt-0.5 text-[10px] bg-amber-100 text-amber-700 rounded px-1">
                  extension
                </span>
              )}
            </button>
          ))
        )}
      </div>
    </Modal>
  );
}
