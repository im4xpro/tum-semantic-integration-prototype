import { useState, useMemo } from 'react';
import { Modal } from './Modal';
import { AddPropertyDialog } from './AddPropertyDialog';
import type { ValueType, PropertyMapping, PropertySource, ColumnSchema, OntologyClass, OntologyProperty } from '../../types';

// ─── preview helper ────────────────────────────────────────────────────────
function previewExpr(expr: string, sample: Record<string, unknown>): string {
  return expr.replace(/\{(\w+)\}/g, (_, k) => String(sample[k] ?? `{${k}}`));
}

// ─── SourceSelector (standalone, no ReactFlow) ────────────────────────────
function SourceSelector({
  src,
  columns,
  onChange,
}: {
  src: PropertySource;
  columns: ColumnSchema[];
  onChange: (s: PropertySource) => void;
}) {
  return (
    <div className="flex items-center gap-1 min-w-0 flex-1">
      <select
        className="border border-gray-300 rounded px-1.5 py-0.5 bg-white text-xs flex-shrink-0"
        value={src.source}
        onChange={(e) => onChange({ source: e.target.value as PropertySource['source'] })}
      >
        <option value="column">column</option>
        <option value="constant">constant</option>
        <option value="row_index">row index</option>
      </select>
      {src.source === 'column' && (
        <select
          className="flex-1 border border-gray-300 rounded px-1.5 py-0.5 bg-white text-xs min-w-0"
          value={src.column_name ?? ''}
          onChange={(e) => onChange({ source: 'column', column_name: e.target.value || undefined })}
        >
          <option value="">-- column --</option>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>{c.name}</option>
          ))}
        </select>
      )}
      {src.source === 'constant' && (
        <input
          type="text"
          className="flex-1 border border-gray-300 rounded px-1.5 py-0.5 bg-white text-xs min-w-0"
          placeholder="constant value…"
          value={src.constant_value ?? ''}
          onChange={(e) => onChange({ source: 'constant', constant_value: e.target.value })}
        />
      )}
      {src.source === 'row_index' && (
        <span className="text-xs text-gray-400 italic">auto row index</span>
      )}
    </div>
  );
}

// ─── PropertyEditor ────────────────────────────────────────────────────────

interface PropertyEditorProps {
  pm: PropertyMapping;
  classes: OntologyClass[];
  properties: OntologyProperty[];
  columns: ColumnSchema[];
  namespaces: Record<string, string>;
  sampleRecord: Record<string, unknown>;
  onUpdate: (pm: PropertyMapping) => void;
  onRemove: () => void;
  depth: number;
}

function PropertyEditor({
  pm,
  classes,
  properties,
  columns,
  namespaces,
  sampleRecord,
  onUpdate,
  onRemove,
  depth,
}: PropertyEditorProps) {
  const [nestedOpen, setNestedOpen] = useState(false);

  const vd = pm.values[0];
  if (!vd) return null;
  const vt = vd.value_type;

  const updVd = (patch: Partial<typeof vd>) =>
    onUpdate({ ...pm, values: [{ ...vd, ...patch }, ...pm.values.slice(1)] });

  const updVt = (patch: Partial<ValueType>) =>
    updVd({ value_type: { ...vt, ...patch } });

  const iriClass = vt.type === 'iri' ? (vt.type_mappings[0]?.class_uri ?? '') : '';
  const transformPreview = vd.transformation?.expression
    ? previewExpr(vd.transformation.expression, sampleRecord)
    : undefined;

  const propLabel =
    properties.find((p) => {
      const short = p.uri.split('#').pop() ?? '';
      return p.uri === pm.property_uri || `bsm:${short}` === pm.property_uri || short === pm.property_uri.split(':').pop();
    })?.label ?? pm.property_uri.split(':').pop() ?? pm.property_uri;

  return (
    <div className="border border-gray-200 rounded-lg p-3 space-y-2">
      {/* Property URI + remove */}
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-gray-800 text-sm truncate" title={pm.property_uri}>
          {propLabel}
        </span>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className={`text-[10px] rounded px-1 ${vt.type === 'iri' ? 'bg-violet-100 text-violet-700' : 'bg-green-100 text-green-700'}`}>
            {vt.type}
          </span>
          <button className="text-red-400 hover:text-red-600 text-sm leading-none" onClick={onRemove}>×</button>
        </div>
      </div>

      {/* Source + type */}
      <div className="flex items-center gap-2">
        <SourceSelector src={vd.value_source} columns={columns} onChange={(s) => updVd({ value_source: s })} />
        <select
          className="border border-gray-300 rounded px-1.5 py-0.5 bg-white text-xs flex-shrink-0"
          value={vt.type}
          onChange={(e) => updVt({ type: e.target.value as 'literal' | 'iri' })}
        >
          <option value="literal">literal</option>
          <option value="iri">iri</option>
        </select>
      </div>

      {/* Transform expression */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-400 flex-shrink-0">template:</span>
        <input
          type="text"
          className="flex-1 border border-gray-200 rounded px-1.5 py-0.5 bg-white text-xs font-mono"
          placeholder="e.g. obj_{col}"
          value={vd.transformation?.expression ?? ''}
          onChange={(e) =>
            updVd({ transformation: e.target.value ? { expression: e.target.value } : undefined })
          }
        />
        {transformPreview && transformPreview !== vd.transformation?.expression && (
          <span className="text-xs text-indigo-400 flex-shrink-0 max-w-[120px] truncate font-mono" title={transformPreview}>
            → {transformPreview}
          </span>
        )}
      </div>

      {/* IRI class + nested object button */}
      {vt.type === 'iri' && (
        <div className="flex items-center gap-2 pt-1 border-t border-violet-100">
          <span className="text-xs text-violet-600 font-medium flex-shrink-0">class:</span>
          <input
            type="text"
            className="flex-1 border border-violet-200 rounded px-1.5 py-0.5 bg-violet-50 text-xs font-mono"
            placeholder="bsm:ClassName"
            value={iriClass}
            onChange={(e) => updVt({ type_mappings: e.target.value ? [{ class_uri: e.target.value }] : [] })}
          />
          {depth < 4 && (
            <button
              className="text-xs bg-violet-600 text-white rounded px-2 py-0.5 hover:bg-violet-700 font-medium flex-shrink-0 whitespace-nowrap"
              onClick={() => setNestedOpen(true)}
            >
              Edit Object ✏
            </button>
          )}
        </div>
      )}

      {/* Nested InlineObjectDialog (recursive) */}
      {nestedOpen && vt.type === 'iri' && (
        <InlineObjectDialog
          open={nestedOpen}
          valueType={vt}
          classes={classes}
          properties={properties}
          columns={columns}
          namespaces={namespaces}
          sampleRecord={sampleRecord}
          depth={depth + 1}
          onChange={(updated) => updVd({ value_type: updated })}
          onClose={() => setNestedOpen(false)}
        />
      )}
    </div>
  );
}

// ─── InlineObjectDialog ────────────────────────────────────────────────────

interface Props {
  open: boolean;
  valueType: ValueType;
  classes: OntologyClass[];
  properties: OntologyProperty[];
  columns: ColumnSchema[];
  namespaces: Record<string, string>;
  sampleRecord: Record<string, unknown>;
  onChange: (vt: ValueType) => void;
  onClose: () => void;
  depth?: number;
}

export function InlineObjectDialog({
  open,
  valueType,
  classes,
  properties,
  columns,
  namespaces,
  sampleRecord,
  onChange,
  onClose,
  depth = 0,
}: Props) {
  const [addPropOpen, setAddPropOpen] = useState(false);

  const vt = valueType;
  const classUri = vt.type_mappings[0]?.class_uri ?? '';

  const updVt = (patch: Partial<ValueType>) => onChange({ ...vt, ...patch });

  const updateProperty = (pi: number, updated: PropertyMapping) => {
    const pms = vt.property_mappings.map((p, i) => (i === pi ? updated : p));
    updVt({ property_mappings: pms });
  };

  const removeProperty = (pi: number) => {
    updVt({ property_mappings: vt.property_mappings.filter((_, i) => i !== pi) });
  };

  const addProperty = (prop: OntologyProperty) => {
    const short = prop.uri.split('#').pop() ?? prop.uri;
    const prefixed = namespaces.bsm ? `bsm:${short}` : prop.uri;
    const newPm: PropertyMapping = {
      property_uri: prefixed,
      values: [
        {
          value_source: { source: 'column' },
          value_type: { type: 'literal', type_mappings: [], property_mappings: [] },
        },
      ],
    };
    updVt({ property_mappings: [...vt.property_mappings, newPm] });
  };

  const title = depth === 0
    ? `Inline Object: ${classUri || '(no class)'}`
    : `Nested Object (level ${depth + 1}): ${classUri || '(no class)'}`;

  // Resolve class label for display
  const classObj = useMemo(() => {
    for (const cls of classes) {
      if (cls.uri === classUri) return cls;
      for (const [prefix, ns] of Object.entries(namespaces)) {
        if (`${prefix}:${cls.uri.replace(ns, '')}` === classUri) return cls;
      }
    }
    return null;
  }, [classUri, classes, namespaces]);

  return (
    <Modal open={open} title={title} onClose={onClose} width="max-w-2xl">
      <div className="space-y-4">

        {/* Type selection */}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-700">Type:</label>
          <div className="flex gap-2">
            {(['literal', 'iri'] as const).map((t) => (
              <label key={t} className="flex items-center gap-1 text-sm cursor-pointer">
                <input
                  type="radio"
                  name={`vt-type-${depth}`}
                  value={t}
                  checked={vt.type === t}
                  onChange={() => updVt({ type: t })}
                  className="accent-indigo-600"
                />
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${t === 'iri' ? 'bg-violet-100 text-violet-700' : 'bg-green-100 text-green-700'}`}>{t}</span>
              </label>
            ))}
          </div>
          {vt.type === 'iri' && classObj && (
            <span className="text-sm text-indigo-600 font-medium">{classObj.label}</span>
          )}
        </div>

        {/* Class URI (for iri type) */}
        {vt.type === 'iri' && (
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700 flex-shrink-0">Class URI:</label>
            <input
              type="text"
              className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-indigo-300"
              placeholder="bsm:ClassName"
              value={classUri}
              onChange={(e) => updVt({ type_mappings: e.target.value ? [{ class_uri: e.target.value }] : [] })}
            />
            {/* Quick-pick from ontology */}
            <select
              className="border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:outline-none"
              value=""
              onChange={(e) => {
                if (e.target.value) updVt({ type_mappings: [{ class_uri: e.target.value }] });
              }}
            >
              <option value="">pick class…</option>
              {classes.map((c) => (
                <option key={c.uri} value={`bsm:${c.uri.split('#').pop()}`}>{c.label}</option>
              ))}
            </select>
          </div>
        )}

        {/* Nested property list */}
        {vt.type === 'iri' && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-gray-700">
                Properties of inline {classObj?.label ?? 'object'}
              </h4>
              <button
                className="text-xs bg-indigo-600 text-white rounded px-2 py-1 hover:bg-indigo-700 font-medium"
                onClick={() => setAddPropOpen(true)}
              >
                + Add Property
              </button>
            </div>

            {vt.property_mappings.length === 0 ? (
              <div className="text-center text-gray-400 text-sm py-6 border border-dashed border-gray-200 rounded-lg">
                No properties defined for this inline object.
                <br />
                <button className="text-indigo-500 hover:underline mt-1" onClick={() => setAddPropOpen(true)}>
                  Add one
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {vt.property_mappings.map((pm, pi) => (
                  <PropertyEditor
                    key={pi}
                    pm={pm}
                    classes={classes}
                    properties={properties}
                    columns={columns}
                    namespaces={namespaces}
                    sampleRecord={sampleRecord}
                    depth={depth}
                    onUpdate={(updated) => updateProperty(pi, updated)}
                    onRemove={() => removeProperty(pi)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {vt.type === 'literal' && (
          <div className="text-sm text-gray-500 bg-gray-50 rounded-lg p-4">
            Literal type — no nested object to configure.
          </div>
        )}

        <div className="flex justify-end pt-2 border-t border-gray-100">
          <button
            className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 font-medium"
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </div>

      {/* Add property dialog */}
      <AddPropertyDialog
        open={addPropOpen}
        subjectClassUri={classUri}
        classes={classes}
        properties={properties}
        namespaces={namespaces}
        onSelect={(prop) => { addProperty(prop); setAddPropOpen(false); }}
        onClose={() => setAddPropOpen(false)}
      />
    </Modal>
  );
}
