import { useState, useCallback, useMemo } from 'react';
import { Modal } from './Modal';
import type { ExtractedSchema, ColumnSchema } from '../../types';

interface Props {
  open: boolean;
  onSave: (schema: ExtractedSchema) => void;
  onClose: () => void;
}

const DATA_TYPES = ['text', 'integer', 'float', 'boolean', 'date', 'timestamp', 'json', 'unknown'];
const SOURCE_TYPES = ['csv', 'json', 'sql', 'api', 'manual'];

interface DraftColumn {
  name: string;
  data_type: string;
  is_primary_key: boolean;
  is_nullable: boolean;
}

function emptyColumn(): DraftColumn {
  return { name: '', data_type: 'text', is_primary_key: false, is_nullable: true };
}

export function AddSourceDialog({ open, onSave, onClose }: Props) {
  const [sourceName, setSourceName] = useState('');
  const [sourceType, setSourceType] = useState('manual');
  const [columns, setColumns] = useState<DraftColumn[]>([emptyColumn()]);
  // Each row is a map of column-name → value string
  const [samples, setSamples] = useState<Record<string, string>[]>([{}]);
  const [error, setError] = useState('');

  const validColumnNames = useMemo(
    () => columns.map((c) => c.name.trim()).filter(Boolean),
    [columns],
  );

  const resetForm = useCallback(() => {
    setSourceName('');
    setSourceType('manual');
    setColumns([emptyColumn()]);
    setSamples([{}]);
    setError('');
  }, []);

  const handleClose = useCallback(() => { resetForm(); onClose(); }, [resetForm, onClose]);

  // ── column ops ─────────────────────────────────────────────────────────────
  const addColumn = useCallback(() => setColumns((p) => [...p, emptyColumn()]), []);
  const removeColumn = useCallback((idx: number) => setColumns((p) => p.filter((_, i) => i !== idx)), []);
  const updateColumn = useCallback((idx: number, patch: Partial<DraftColumn>) =>
    setColumns((p) => p.map((c, i) => i === idx ? { ...c, ...patch } : c)), []);

  // ── sample ops ─────────────────────────────────────────────────────────────
  const addSampleRow = useCallback(() => setSamples((p) => [...p, {}]), []);
  const removeSampleRow = useCallback((idx: number) => setSamples((p) => p.filter((_, i) => i !== idx)), []);
  const updateSampleCell = useCallback((rowIdx: number, colName: string, value: string) => {
    setSamples((p) => p.map((row, i) => i === rowIdx ? { ...row, [colName]: value } : row));
  }, []);

  // ── save ───────────────────────────────────────────────────────────────────
  const handleSave = useCallback(() => {
    const name = sourceName.trim();
    if (!name) { setError('Source name is required.'); return; }
    if (!/^[\w\-]+$/.test(name)) {
      setError('Source name may only contain letters, numbers, hyphens and underscores.');
      return;
    }
    const validColumns = columns.filter((c) => c.name.trim() !== '');
    if (validColumns.length === 0) { setError('Add at least one column.'); return; }
    const colNames = validColumns.map((c) => c.name.trim());
    if (new Set(colNames).size !== colNames.length) { setError('Column names must be unique.'); return; }

    const sampleRecords = samples
      .map((row) => {
        const out: Record<string, unknown> = {};
        for (const col of colNames) { if (row[col]?.trim()) out[col] = row[col].trim(); }
        return out;
      })
      .filter((row) => Object.keys(row).length > 0);

    const schema: ExtractedSchema = {
      source_name: name,
      source_type: sourceType,
      columns: validColumns.map((c): ColumnSchema => ({
        name: c.name.trim(),
        data_type: c.data_type,
        is_primary_key: c.is_primary_key,
        is_nullable: c.is_nullable,
      })),
      inferred_fields: [],
      sample_records: sampleRecords,
    };

    onSave(schema);
    resetForm();
  }, [sourceName, sourceType, columns, samples, onSave, resetForm]);

  return (
    <Modal open={open} onClose={handleClose} title="Add Data Source" width="max-w-3xl">
      <div className="space-y-5">

        {/* source name + type */}
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Source name</label>
            <input
              type="text"
              value={sourceName}
              onChange={(e) => { setSourceName(e.target.value); setError(''); }}
              placeholder="e.g. customers"
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300"
            />
          </div>
          <div className="w-36">
            <label className="block text-xs text-gray-500 mb-1">Source type</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300"
            >
              {SOURCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        {/* column schema */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-gray-500 font-medium">Columns</label>
            <button onClick={addColumn} className="text-xs text-indigo-600 hover:text-indigo-800 font-medium">
              + Add column
            </button>
          </div>
          <div className="border border-gray-200 rounded overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-2 py-1.5 font-medium text-gray-600 w-[44%]">Name</th>
                  <th className="text-left px-2 py-1.5 font-medium text-gray-600 w-[30%]">Data type</th>
                  <th className="text-center px-2 py-1.5 font-medium text-gray-600 w-[10%]">PK</th>
                  <th className="text-center px-2 py-1.5 font-medium text-gray-600 w-[10%]">Nullable</th>
                  <th className="w-[6%]" />
                </tr>
              </thead>
              <tbody>
                {columns.map((col, idx) => (
                  <tr key={idx} className="border-t border-gray-100">
                    <td className="px-2 py-1">
                      <input
                        type="text"
                        value={col.name}
                        onChange={(e) => { updateColumn(idx, { name: e.target.value }); setError(''); }}
                        placeholder="column_name"
                        className="w-full border border-gray-200 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-300"
                      />
                    </td>
                    <td className="px-2 py-1">
                      <select
                        value={col.data_type}
                        onChange={(e) => updateColumn(idx, { data_type: e.target.value })}
                        className="w-full border border-gray-200 rounded px-1 py-0.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300"
                      >
                        {DATA_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-1 text-center">
                      <input type="checkbox" checked={col.is_primary_key}
                        onChange={(e) => updateColumn(idx, { is_primary_key: e.target.checked })} />
                    </td>
                    <td className="px-2 py-1 text-center">
                      <input type="checkbox" checked={col.is_nullable}
                        onChange={(e) => updateColumn(idx, { is_nullable: e.target.checked })} />
                    </td>
                    <td className="px-2 py-1 text-center">
                      <button onClick={() => removeColumn(idx)} disabled={columns.length === 1}
                        className="text-gray-400 hover:text-red-500 disabled:opacity-20 text-base leading-none"
                        title="Remove column">&times;</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* sample data */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-gray-500 font-medium">
              Sample data <span className="text-gray-400 font-normal">(optional — used for previews in the canvas)</span>
            </label>
            <button onClick={addSampleRow} className="text-xs text-indigo-600 hover:text-indigo-800 font-medium">
              + Add row
            </button>
          </div>

          {validColumnNames.length === 0 ? (
            <p className="text-xs text-gray-400 italic">Define at least one column to enter sample data.</p>
          ) : (
            <div className="border border-gray-200 rounded overflow-auto max-h-48">
              <table className="text-xs min-w-full">
                <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
                  <tr>
                    <th className="text-left px-2 py-1.5 font-medium text-gray-400 w-8">#</th>
                    {validColumnNames.map((n) => (
                      <th key={n} className="text-left px-2 py-1.5 font-medium text-gray-600 whitespace-nowrap">{n}</th>
                    ))}
                    <th className="w-6" />
                  </tr>
                </thead>
                <tbody>
                  {samples.map((row, ri) => (
                    <tr key={ri} className="border-t border-gray-100">
                      <td className="px-2 py-1 text-gray-400 text-center">{ri + 1}</td>
                      {validColumnNames.map((colName) => (
                        <td key={colName} className="px-2 py-1">
                          <input
                            type="text"
                            value={row[colName] ?? ''}
                            onChange={(e) => updateSampleCell(ri, colName, e.target.value)}
                            placeholder="—"
                            className="w-full min-w-[80px] border border-gray-200 rounded px-1.5 py-0.5 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-300"
                          />
                        </td>
                      ))}
                      <td className="px-1 py-1 text-center">
                        <button
                          onClick={() => removeSampleRow(ri)}
                          disabled={samples.length === 1}
                          className="text-gray-400 hover:text-red-500 disabled:opacity-20 text-base leading-none"
                          title="Remove row"
                        >&times;</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={handleClose}
            className="px-3 py-1.5 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50">
            Cancel
          </button>
          <button onClick={handleSave}
            className="px-3 py-1.5 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700">
            Save source
          </button>
        </div>

      </div>
    </Modal>
  );
}
