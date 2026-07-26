import { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { Spinner } from '../Spinner';
import type { MappingStrategy, OntologyFormat } from '../../types';

export type NewMappingResult =
  | { mode: 'manual'; name: string }
  | { mode: 'ai'; name: string; strategy: MappingStrategy; ontology_format: OntologyFormat };

interface Props {
  open: boolean;
  sourceName: string;
  aiEnabled: boolean;
  generating: boolean;
  onConfirm: (result: NewMappingResult) => void;
  onClose: () => void;
}

const STRATEGIES: { value: MappingStrategy; label: string }[] = [
  { value: 'zero_shot', label: 'Zero-shot' },
  { value: 'few_shot', label: 'Few-shot' },
  { value: 'chain_of_thought', label: 'Chain-of-thought' },
];

const ONTOLOGY_FORMATS: OntologyFormat[] = ['turtle', 'compact', 'class_list'];

export function NewMappingDialog({ open, sourceName, aiEnabled, generating, onConfirm, onClose }: Props) {
  const [name, setName] = useState('');
  const [mode, setMode] = useState<'manual' | 'ai'>('manual');
  const [strategy, setStrategy] = useState<MappingStrategy>('zero_shot');
  const [ontologyFormat, setOntologyFormat] = useState<OntologyFormat>('turtle');

  useEffect(() => {
    if (open) {
      setName('');
      setMode('manual');
      setStrategy('zero_shot');
      setOntologyFormat('turtle');
    }
  }, [open]);

  const effectiveMode = aiEnabled ? mode : 'manual';

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (generating) return;
    if (effectiveMode === 'ai') {
      onConfirm({ mode: 'ai', name: name.trim(), strategy, ontology_format: ontologyFormat });
    } else {
      onConfirm({ mode: 'manual', name: name.trim() });
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="New Mapping" width="max-w-sm">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <div className="text-xs text-gray-500 mb-3">
            Source: <span className="font-medium text-gray-700">{sourceName}</span>
          </div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Mapping name
          </label>
          <input
            autoFocus
            type="text"
            placeholder="e.g. ACLED event mapping v1"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <div className="text-[10px] text-gray-400 mt-1">
            Leave blank to use an auto-generated name.
          </div>
        </div>

        {aiEnabled && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Creation mode</label>
            <div className="flex rounded overflow-hidden border border-gray-300 text-xs">
              {(['manual', 'ai'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex-1 px-3 py-1.5 font-medium transition-colors ${
                    mode === m ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {m === 'manual' ? 'Manual' : 'AI-assisted'}
                </button>
              ))}
            </div>
          </div>
        )}

        {effectiveMode === 'ai' && (
          <div className="flex flex-col gap-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Prompt strategy</label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as MappingStrategy)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-300"
              >
                {STRATEGIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Ontology format</label>
              <select
                value={ontologyFormat}
                onChange={(e) => setOntologyFormat(e.target.value as OntologyFormat)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-300"
              >
                {ONTOLOGY_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <p className="text-[10px] text-gray-500 leading-snug">
              The LLM suggests a mapping you can review and edit in the canvas before saving —
              nothing is saved automatically.
            </p>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={generating}
            className="px-3 py-1.5 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={generating}
            className="px-4 py-1.5 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 font-medium disabled:opacity-60 flex items-center gap-1.5"
          >
            {generating && <Spinner />}
            {effectiveMode === 'ai' ? (generating ? 'Generating…' : 'Generate') : 'Create'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
