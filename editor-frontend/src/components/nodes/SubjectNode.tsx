import { useRef, useState } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { SubjectMapping, PropertySource, ColumnSchema, OntologyProperty, ValueType, PropertyMapping, ValueDefinition, MappingBasis } from '../../types';

// ─── LocalInput ────────────────────────────────────────────────────────────
// Buffers text locally so cursor position is preserved during fast typing.
// Commits to parent only on blur or Enter.

function LocalInput({ value = '', onChange, className, placeholder, style }: {
  value?: string;
  onChange: (v: string) => void;
  className?: string;
  placeholder?: string;
  style?: React.CSSProperties;
}) {
  const [text, setText] = useState(value);
  const focused = useRef(false);
  // Sync from parent only when not focused (external reset)
  if (!focused.current && text !== value) setText(value);
  return (
    <input
      className={className}
      placeholder={placeholder}
      style={style}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onFocus={() => { focused.current = true; }}
      onBlur={() => { focused.current = false; onChange(text); }}
      onKeyDown={(e) => { if (e.key === 'Enter') onChange(text); }}
    />
  );
}

function confidenceClasses(c: number): string {
  if (c >= 0.8) return 'bg-green-100 text-green-700 border-green-200';
  if (c >= 0.6) return 'bg-amber-100 text-amber-700 border-amber-200';
  return 'bg-red-100 text-red-700 border-red-200';
}

function ConfidenceBadge({ confidence, reasoning, size }: {
  confidence: number;
  reasoning?: string;
  size: 'lg' | 'sm';
}) {
  const pct = Math.round(confidence * 100);
  const sizeCls = size === 'lg' ? 'text-[10px] px-1.5 py-0.5' : 'text-[9px] px-1 py-px';
  return (
    <span
      className={`rounded border font-semibold tabular-nums flex-shrink-0 ${sizeCls} ${confidenceClasses(confidence)}`}
      title={reasoning ? `Confidence ${pct}% — ${reasoning}` : `Confidence ${pct}%`}
    >
      {pct}%
    </span>
  );
}

const BASIS_CLASSES: Record<MappingBasis, string> = {
  name: 'bg-sky-100 text-sky-700 border-sky-200',
  description: 'bg-teal-100 text-teal-700 border-teal-200',
  value: 'bg-violet-100 text-violet-700 border-violet-200',
  structural: 'bg-slate-100 text-slate-700 border-slate-200',
  weak: 'bg-rose-100 text-rose-700 border-rose-200',
};

function BasisPill({ basis }: { basis: MappingBasis }) {
  return (
    <span className={`rounded border px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide ${BASIS_CLASSES[basis]}`}>
      {basis}
    </span>
  );
}

function hasJustification(j: { reasoning?: string; basis?: MappingBasis }): boolean {
  return j.reasoning != null || j.basis != null;
}

function JustificationToggle({ open, onToggle, tone = 'default' }: {
  open: boolean;
  onToggle: () => void;
  tone?: 'default' | 'onDark';
}) {
  const toneCls = tone === 'onDark'
    ? (open ? 'text-white bg-white/20' : 'text-indigo-200 hover:text-white')
    : (open ? 'text-indigo-600 bg-indigo-50' : 'text-gray-400 hover:text-indigo-600');
  return (
    <button
      type="button"
      aria-expanded={open}
      title={open ? 'Hide justification' : 'Show justification'}
      onClick={onToggle}
      className={`flex-shrink-0 leading-none rounded px-1 text-[10px] transition-colors ${toneCls}`}
    >
      {open ? '▾' : 'ⓘ'}
    </button>
  );
}

function JustificationPanel({ basis, reasoning }: { basis?: MappingBasis; reasoning?: string }) {
  return (
    <div className="mt-1.5 rounded border border-gray-200 bg-gray-50 px-2 py-1.5 space-y-1">
      {basis && (
        <div>
          <BasisPill basis={basis} />
        </div>
      )}
      {reasoning ? (
        <p className="text-[11px] text-gray-600 leading-snug whitespace-pre-line">{reasoning}</p>
      ) : (
        <p className="text-[11px] text-gray-400 italic">No justification recorded</p>
      )}
    </div>
  );
}

// ─── source mode ───────────────────────────────────────────────────────────

type SrcMode = 'col' | 'const' | 'expr';

function deriveSrcMode(vd: ValueDefinition): SrcMode {
  // Check transformation object existence, not expression string truthiness —
  // an empty expression string is still expr mode.
  if (vd.transformation != null) return 'expr';
  if (vd.value_source.source === 'constant') return 'const';
  return 'col';
}

// ─── SubjectNode data ──────────────────────────────────────────────────────

export interface SubjectNodeData {
  subjectIndex: number;
  mapping: SubjectMapping;
  columns: ColumnSchema[];
  properties: OntologyProperty[];
  sampleRecord: Record<string, unknown>;
  subjectMappings: SubjectMapping[];
  ancestorLabels: string[];  // parent class labels in order (immediate parent first)
  onUpdate: (si: number, updated: SubjectMapping) => void;
  onRemove: (si: number) => void;
  onAddProperty: (si: number) => void;
  onEditInlineObject: (si: number, pi: number) => void;
  [key: string]: unknown;
}

// ─── preview helper ────────────────────────────────────────────────────────

function resolveSampleValue(key: string, sample: Record<string, unknown>): string {
  const direct = sample[key];
  if (direct !== undefined) {
    if (Array.isArray(direct)) return direct.length > 0 ? String(direct[0]) : `{${key}}`;
    return String(direct);
  }
  // Dotted key: "Entity.field" → sample.properties.field when sample.schema matches
  const dot = key.indexOf('.');
  if (dot !== -1) {
    const entity = key.slice(0, dot);
    const field = key.slice(dot + 1);
    if (sample['schema'] === entity) {
      const props = sample['properties'];
      if (props && typeof props === 'object' && !Array.isArray(props)) {
        const val = (props as Record<string, unknown>)[field];
        if (val !== undefined) {
          if (Array.isArray(val)) return val.length > 0 ? String(val[0]) : `{${key}}`;
          return String(val);
        }
      }
    }
  }
  return `{${key}}`;
}

function previewExpr(expr: string, sample: Record<string, unknown>): string {
  // [\w.]+ handles both plain column names and dotted names like Person.name
  return expr.replace(/\{([\w.]+)\}/g, (_, k) => resolveSampleValue(k, sample));
}

// ─── ModeToggle ────────────────────────────────────────────────────────────

function ModeToggle({ mode, onChange }: { mode: SrcMode; onChange: (m: SrcMode) => void }) {
  return (
    <div className="flex text-[10px] rounded overflow-hidden border border-gray-200 flex-shrink-0">
      {(['col', 'const', 'expr'] as const).map((m) => (
        <button
          key={m}
          className={`px-1.5 py-0.5 leading-tight ${
            mode === m ? 'bg-indigo-100 text-indigo-700 font-semibold' : 'bg-white text-gray-400 hover:bg-gray-50'
          }`}
          onClick={() => onChange(m)}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

// ─── SubjectSourceRow (for the Subject URI section) ────────────────────────

function SubjectSourceRow({
  src,
  transformation,
  columns,
  sample,
  onChange,
  onChangeTransform,
}: {
  src: PropertySource;
  transformation: { expression: string } | undefined;
  columns: ColumnSchema[];
  sample: Record<string, unknown>;
  onChange: (s: PropertySource) => void;
  onChangeTransform: (t: { expression: string } | undefined) => void;
}) {
  const mode: SrcMode = transformation != null ? 'expr' : src.source === 'constant' ? 'const' : 'col';

  const setMode = (m: SrcMode) => {
    if (m === 'col') {
      const col = transformation?.expression?.match(/\{(\w+)\}/)?.[1];
      onChange({ source: 'column', column_name: col });
      onChangeTransform(undefined);
    } else if (m === 'const') {
      onChange({ source: 'constant', constant_value: '' });
      onChangeTransform(undefined);
    } else {
      const col = src.column_name;
      onChange({ source: 'row_index' });
      onChangeTransform({ expression: col ? `{${col}}` : '' });
    }
  };

  const preview = transformation?.expression
    ? previewExpr(transformation.expression, sample)
    : undefined;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1">
        <ModeToggle mode={mode} onChange={setMode} />

        {mode === 'col' && (
          <select
            className="flex-1 border border-gray-200 rounded px-1 bg-white text-[11px] min-w-0"
            value={src.column_name ?? ''}
            onChange={(e) => onChange({ source: 'column', column_name: e.target.value || undefined })}
          >
            <option value="">-- column --</option>
            {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        )}
        {mode === 'const' && (
          <LocalInput
            className="flex-1 border border-gray-200 rounded px-1 bg-white text-[11px] min-w-0"
            placeholder="constant URI…"
            value={src.constant_value ?? ''}
            onChange={(v) => onChange({ source: 'constant', constant_value: v })}
          />
        )}
        {mode === 'expr' && (
          <div className="flex-1 min-w-0">
            <LocalInput
              className="w-full border border-gray-200 rounded px-1 bg-white text-[11px] font-mono"
              placeholder="e.g. bsm:action/{event_id}"
              value={transformation?.expression ?? ''}
              onChange={(v) => onChangeTransform({ expression: v })}
            />
            {preview && preview !== transformation?.expression && (
              <div className="text-[10px] text-indigo-500 mt-0.5 font-mono truncate" title={preview}>
                → {preview}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── ValueRow ──────────────────────────────────────────────────────────────

interface ValueRowProps {
  vd: ValueDefinition;
  columns: ColumnSchema[];
  sampleRecord: Record<string, unknown>;
  subjectMappings: SubjectMapping[];
  currentSi: number;
  showRemove: boolean;
  onUpdate: (vd: ValueDefinition) => void;
  onRemove: () => void;
  onEditInlineObject: () => void;
}

function ValueRow({
  vd,
  columns,
  sampleRecord,
  subjectMappings,
  currentSi,
  showRemove,
  onUpdate,
  onRemove,
  onEditInlineObject,
}: ValueRowProps) {
  const mode = deriveSrcMode(vd);
  const vt: ValueType = vd.value_type;

  const updVd = (patch: Partial<ValueDefinition>) => onUpdate({ ...vd, ...patch });
  const updVt = (patch: Partial<ValueType>) => updVd({ value_type: { ...vt, ...patch } });

  const setMode = (m: SrcMode) => {
    if (m === 'col') {
      const col = vd.transformation?.expression?.match(/\{(\w+)\}/)?.[1];
      updVd({ value_source: { source: 'column', column_name: col }, transformation: undefined });
    } else if (m === 'const') {
      updVd({ value_source: { source: 'constant', constant_value: '' }, transformation: undefined });
    } else {
      const col = vd.value_source.column_name;
      updVd({ value_source: { source: 'row_index' }, transformation: { expression: col ? `{${col}}` : '' } });
    }
  };

  const exprPreview = vd.transformation?.expression
    ? previewExpr(vd.transformation.expression, sampleRecord)
    : undefined;

  // Find which subject this IRI value is bound to.
  // Match by class URI AND source column so two subjects of the same class
  // (e.g. actor1 and actor2) resolve independently.
  const refClass = vt.type === 'iri' ? (vt.type_mappings?.[0]?.class_uri ?? '') : '';
  const linkedSi = subjectMappings.findIndex((sm, idx) => {
    if (idx === currentSi) return false;
    if ((sm.type_mappings?.[0]?.class_uri ?? '') !== refClass) return false;
    if (vd.value_source.source === 'column' && sm.subject.source === 'column')
      return vd.value_source.column_name === sm.subject.column_name;
    if (vd.value_source.source === 'constant' && sm.subject.source === 'constant')
      return vd.value_source.constant_value === sm.subject.constant_value;
    return true;
  });

  const bindToSubject = (idx: number) => {
    const sm = subjectMappings[idx];
    if (!sm) return;
    onUpdate({
      ...vd,
      value_source: sm.subject,
      transformation: sm.subject_transformation,
      value_type: { ...vt, type: 'iri', type_mappings: sm.type_mappings ?? [] },
    });
  };

  // When this value is IRI-bound to another subject, the source is derived from
  // that subject's binding — showing col/const/expr controls would be misleading.
  const isRefBound = vt.type === 'iri' && linkedSi >= 0;
  const linkedLabel = isRefBound ? deriveSubjectLabel(subjectMappings[linkedSi]) : '';

  return (
    <div className="space-y-1">
      {/* source + type + remove */}
      <div className="flex items-center gap-1">
        {isRefBound ? (
          <span
            className="flex-1 text-[11px] font-mono text-violet-700 bg-violet-50 border border-violet-200 rounded px-1.5 py-0.5 truncate min-w-0"
            title={`IRI reference → ${linkedLabel}`}
          >
            → {linkedLabel}
          </span>
        ) : (
          <>
            <ModeToggle mode={mode} onChange={setMode} />

            {mode === 'col' && (
              <select
                className="flex-1 border border-gray-200 rounded px-1 bg-white text-[11px] min-w-0"
                value={vd.value_source.column_name ?? ''}
                onChange={(e) => updVd({ value_source: { source: 'column', column_name: e.target.value || undefined } })}
              >
                <option value="">-- column --</option>
                {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
              </select>
            )}
            {mode === 'const' && (
              <LocalInput
                className="flex-1 border border-gray-200 rounded px-1 bg-white text-[11px] min-w-0"
                placeholder="constant value…"
                value={vd.value_source.constant_value ?? ''}
                onChange={(v) => updVd({ value_source: { source: 'constant', constant_value: v } })}
              />
            )}
            {mode === 'expr' && (
              <div className="flex-1 min-w-0">
                <LocalInput
                  className="w-full border border-gray-200 rounded px-1 bg-white text-[11px] font-mono"
                  placeholder="e.g. {actor1}"
                  value={vd.transformation?.expression ?? ''}
                  onChange={(v) => updVd({ transformation: { expression: v } })}
                />
                {exprPreview && exprPreview !== vd.transformation?.expression && (
                  <div className="text-[10px] text-indigo-500 mt-0.5 font-mono truncate" title={exprPreview}>
                    → {exprPreview}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        <select
          className="border border-gray-200 rounded px-1 bg-white text-[11px] flex-shrink-0"
          style={{ width: 56 }}
          value={vt.type}
          onChange={(e) => updVt({ type: e.target.value as 'literal' | 'iri' })}
        >
          <option value="literal">literal</option>
          <option value="iri">iri</option>
        </select>

        {showRemove && (
          <button className="text-red-300 hover:text-red-500 text-sm leading-none flex-shrink-0" onClick={onRemove}>×</button>
        )}
      </div>

      {/* IRI subject binding */}
      {vt.type === 'iri' && (
        <div className="flex items-center gap-1 pl-1 border-l-2 border-violet-200">
          <span className="text-[10px] text-violet-500 flex-shrink-0">→</span>
          <select
            className="flex-1 border border-violet-200 rounded px-1 bg-violet-50 text-[11px] min-w-0"
            value={linkedSi >= 0 ? String(linkedSi) : ''}
            onChange={(e) => {
              const idx = parseInt(e.target.value);
              if (!isNaN(idx)) bindToSubject(idx);
            }}
          >
            <option value="">-- bind to subject --</option>
            {subjectMappings.map((sm, idx) => {
              if (idx === currentSi) return null;
              return <option key={idx} value={idx}>{deriveSubjectLabel(sm)}</option>;
            })}
          </select>
          {linkedSi < 0 && (
            <button
              className="text-[10px] bg-violet-100 text-violet-700 border border-violet-200 rounded px-1.5 py-0.5 hover:bg-violet-200 flex-shrink-0 whitespace-nowrap"
              onClick={onEditInlineObject}
            >
              Edit ✏
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── PropertyRow ────────────────────────────────────────────────────────────

interface PropertyRowProps {
  pm: PropertyMapping;
  pi: number;
  si: number;
  columns: ColumnSchema[];
  propLabel: string;
  sampleRecord: Record<string, unknown>;
  subjectMappings: SubjectMapping[];
  onUpdate: (updated: PropertyMapping) => void;
  onRemove: () => void;
  onEditInlineObject: () => void;
}

function PropertyRow({
  pm,
  pi,
  si,
  columns,
  propLabel,
  sampleRecord,
  subjectMappings,
  onUpdate,
  onRemove,
  onEditInlineObject,
}: PropertyRowProps) {
  const [showJustification, setShowJustification] = useState(false);
  const canJustify = hasJustification(pm);

  const addValue = () => {
    const baseType = pm.values[0]?.value_type.type ?? 'literal';
    onUpdate({
      ...pm,
      values: [
        ...pm.values,
        {
          value_source: { source: 'column' },
          value_type: { type: baseType, type_mappings: [], property_mappings: [] },
        },
      ],
    });
  };

  return (
    <div className="relative border-b border-gray-100 last:border-0 px-3 py-2 text-xs">
      <Handle
        type="target"
        position={Position.Left}
        id={`prop-${pi}`}
        style={{ left: -10, top: '50%', transform: 'translateY(-50%)', background: '#6366f1', width: 8, height: 8, border: '2px solid #fff' }}
      />

      {/* header */}
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="font-medium text-gray-700 truncate flex-1 min-w-0" title={pm.property_uri}>
          {propLabel}
        </span>
        {pm.confidence != null && (
          <ConfidenceBadge confidence={pm.confidence} reasoning={pm.reasoning} size="sm" />
        )}
        {canJustify && (
          <JustificationToggle open={showJustification} onToggle={() => setShowJustification((v) => !v)} />
        )}
        <button className="text-red-300 hover:text-red-500 text-sm leading-none flex-shrink-0" onClick={onRemove}>×</button>
      </div>

      {canJustify && showJustification && (
        <JustificationPanel basis={pm.basis} reasoning={pm.reasoning} />
      )}

      {/* values */}
      <div className="space-y-2">
        {pm.values.map((vd, vi) => (
          <ValueRow
            key={vi}
            vd={vd}
            columns={columns}
            sampleRecord={sampleRecord}
            subjectMappings={subjectMappings}
            currentSi={si}
            showRemove={pm.values.length > 1}
            onUpdate={(updated) => onUpdate({ ...pm, values: pm.values.map((v, i) => i === vi ? updated : v) })}
            onRemove={() => onUpdate({ ...pm, values: pm.values.filter((_, i) => i !== vi) })}
            onEditInlineObject={onEditInlineObject}
          />
        ))}
      </div>

      <button
        className="text-[10px] text-indigo-400 hover:text-indigo-600 mt-1.5"
        onClick={addValue}
      >
        + value
      </button>
    </div>
  );
}

// ─── SubjectNode ───────────────────────────────────────────────────────────

function deriveSubjectLabel(mapping: SubjectMapping): string {
  const expr = mapping.subject_transformation?.expression;
  if (expr) return expr;
  if (mapping.subject.source === 'constant' && mapping.subject.constant_value) return mapping.subject.constant_value;
  if (mapping.subject.column_name) return `{${mapping.subject.column_name}}`;
  return mapping.type_mappings?.[0]?.class_uri ?? 'Subject';
}

export function SubjectNode({ data }: NodeProps) {
  const d = data as SubjectNodeData;
  const { subjectIndex: si, mapping, columns, properties, sampleRecord, subjectMappings, ancestorLabels } = d;

  const subjectLabel = deriveSubjectLabel(mapping);

  const [showJustification, setShowJustification] = useState(false);
  const canJustify = hasJustification(mapping);

  const upd = (patch: Partial<SubjectMapping>) => d.onUpdate(si, { ...mapping, ...patch });

  const propLabel = (uri: string) => {
    const short = uri.split(':').pop() ?? uri;
    return properties.find((p) => p.label.toLowerCase() === short.toLowerCase())?.label ?? short;
  };

  return (
    <div className="relative bg-white border-2 border-indigo-300 rounded-xl shadow-md" style={{ minWidth: 400, maxWidth: 460 }}>

      {/* Source handle — drag from here to another subject's property to create an IRI reference */}
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        style={{ right: -10, top: '50%', transform: 'translateY(-50%)', background: '#a5b4fc', width: 10, height: 10, border: '2px solid #fff' }}
      />

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="subject-drag-handle bg-indigo-600 text-white px-3 py-2 rounded-t-xl flex items-center gap-2 cursor-grab active:cursor-grabbing">
        <div className="flex-1 min-w-0">
          <div className="text-white text-sm font-semibold font-mono truncate" title={subjectLabel}>
            {subjectLabel}
          </div>
          {mapping.type_mappings?.[0]?.class_uri && (
            <div className="text-indigo-300 text-[10px] font-mono truncate" title={mapping.type_mappings[0].class_uri}>
              {mapping.type_mappings[0].class_uri}
              {ancestorLabels.length > 0 && (
                <span className="text-indigo-400/70 ml-1">
                  ⊂ {ancestorLabels.join(' ⊂ ')}
                </span>
              )}
            </div>
          )}
        </div>
        {mapping.confidence != null && (
          <ConfidenceBadge confidence={mapping.confidence} reasoning={mapping.reasoning} size="lg" />
        )}
        {canJustify && (
          <JustificationToggle
            open={showJustification}
            onToggle={() => setShowJustification((v) => !v)}
            tone="onDark"
          />
        )}
        <button
          className="text-indigo-200 hover:text-white text-lg leading-none flex-shrink-0"
          onClick={() => d.onRemove(si)}
        >×</button>
      </div>

      {canJustify && showJustification && (
        <div className="px-3 pb-2 bg-white border-b border-gray-100">
          <JustificationPanel basis={mapping.basis} reasoning={mapping.reasoning} />
        </div>
      )}

      {/* ── Subject URI ──────────────────────────────────────────── */}
      <div className="relative px-3 py-2 bg-amber-50 border-b border-amber-100">
        <Handle
          type="target"
          position={Position.Left}
          id="subject"
          style={{ left: -10, top: '50%', transform: 'translateY(-50%)', background: '#f59e0b', width: 10, height: 10, border: '2px solid #fff' }}
        />
        <div className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide mb-1">Subject URI</div>
        <SubjectSourceRow
          src={mapping.subject}
          transformation={mapping.subject_transformation}
          columns={columns}
          sample={sampleRecord}
          onChange={(s) => upd({ subject: s })}
          onChangeTransform={(t) => upd({ subject_transformation: t })}
        />
      </div>

      {/* ── Property rows ────────────────────────────────────────── */}
      {(mapping.property_mappings ?? []).map((pm, pi) => (
        <PropertyRow
          key={pi}
          pm={pm}
          pi={pi}
          si={si}
          columns={columns}
          propLabel={propLabel(pm.property_uri)}
          sampleRecord={sampleRecord}
          subjectMappings={subjectMappings}
          onUpdate={(updated) => {
            const pms = mapping.property_mappings.map((p, j) => j === pi ? updated : p);
            upd({ property_mappings: pms });
          }}
          onRemove={() => upd({ property_mappings: mapping.property_mappings.filter((_, j) => j !== pi) })}
          onEditInlineObject={() => d.onEditInlineObject(si, pi)}
        />
      ))}

      {/* ── Footer ───────────────────────────────────────────────── */}
      <div className="px-3 py-1.5 rounded-b-xl bg-gray-50 border-t border-gray-100">
        <button
          className="text-xs text-indigo-500 hover:text-indigo-700 font-semibold"
          onClick={() => d.onAddProperty(si)}
        >+ Add Property</button>
      </div>
    </div>
  );
}
