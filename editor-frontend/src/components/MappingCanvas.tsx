import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  type Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ColumnNode } from './nodes/ColumnNode';
import { SubjectNode } from './nodes/SubjectNode';
import type {
  ColumnSchema,
  ExtractedSchema,
  MappingDocument,
  OntologyClass,
  OntologyProperty,
  SubjectMapping,
} from '../types';

const NODE_TYPES: NodeTypes = {
  columnNode: ColumnNode,
  subjectNode: SubjectNode,
};

// ─── schema helpers ───────────────────────────────────────────────────────

function effectiveColumns(schema: ExtractedSchema | null): ColumnSchema[] {
  if (!schema) return [];
  return schema.columns.length > 0 ? schema.columns : schema.inferred_fields;
}

// For document schemas (MongoDB), inferred fields are named "Entity.field".
// Values live in record.properties[field] when record.schema === entity.
// Falls back to direct lookup for flat schemas.
function getExampleValue(colName: string, record: Record<string, unknown>): string | undefined {
  const val = record[colName];
  if (val !== undefined) return formatSampleValue(val);

  const dot = colName.indexOf('.');
  if (dot !== -1) {
    const entity = colName.slice(0, dot);
    const field = colName.slice(dot + 1);
    if (record['schema'] === entity) {
      const props = record['properties'];
      if (props && typeof props === 'object' && !Array.isArray(props)) {
        return formatSampleValue((props as Record<string, unknown>)[field]);
      }
    }
  }
  return undefined;
}

function formatSampleValue(v: unknown): string | undefined {
  if (v === undefined || v === null) return undefined;
  if (Array.isArray(v)) return v.length > 0 ? String(v[0]) : undefined;
  return String(v);
}

// ─── layout constants ──────────────────────────────────────────────────────
const COL_NODE_X = 20;
const SUBJ_NODE_X = 540;
const COL_ROW_H = 80;
const SUBJ_HEADER_H = 52;
const SUBJ_SUBJECT_H = 74;
const SUBJ_PROP_H = 90;  // taller rows with transforms + iri controls
const SUBJ_FOOTER_H = 36;
const SUBJ_GAP = 20;

function subjectNodeHeight(sm: SubjectMapping) {
  return SUBJ_HEADER_H + SUBJ_SUBJECT_H + sm.property_mappings.length * SUBJ_PROP_H + SUBJ_FOOTER_H;
}

// ─── node builder ──────────────────────────────────────────────────────────

interface SubjectHandlers {
  onUpdate: (si: number, updated: SubjectMapping) => void;
  onRemove: (si: number) => void;
  onAddProperty: (si: number) => void;
  onEditInlineObject: (si: number, pi: number) => void;
}

function resolveCompactUri(compact: string, namespaces: Record<string, string>): string {
  const colon = compact.indexOf(':');
  if (colon === -1) return compact;
  const ns = namespaces[compact.slice(0, colon)];
  return ns ? ns + compact.slice(colon + 1) : compact;
}

function ancestorLabelsFor(classUri: string, mapping: MappingDocument, classes: OntologyClass[]): string[] {
  const fullUri = resolveCompactUri(classUri, mapping.namespaces);
  const byUri = new Map(classes.map((c) => [c.uri, c]));
  const labels: string[] = [];
  const seen = new Set<string>();
  const queue = [...(byUri.get(fullUri)?.subclass_of ?? [])];
  while (queue.length > 0) {
    const uri = queue.shift()!;
    if (seen.has(uri)) continue;
    seen.add(uri);
    const cls = byUri.get(uri);
    if (cls) labels.push(cls.label);
    cls?.subclass_of.forEach((p) => queue.push(p));
  }
  return labels;
}

function buildNodes(
  schema: ExtractedSchema | null,
  mapping: MappingDocument,
  classes: OntologyClass[],
  properties: OntologyProperty[],
  handlers: SubjectHandlers,
  connectedColumns: Set<string>,
  sampleRecord: Record<string, unknown>,
): Node[] {
  const nodes: Node[] = [];

  const cols = effectiveColumns(schema);

  cols.forEach((col, i) => {
    nodes.push({
      id: `col-${col.name}`,
      type: 'columnNode',
      position: { x: COL_NODE_X, y: i * COL_ROW_H },
      data: {
        name: col.name,
        dataType: col.data_type,
        isPrimaryKey: col.is_primary_key,
        isNullable: col.is_nullable,
        isConnected: connectedColumns.has(col.name),
        exampleValue: getExampleValue(col.name, sampleRecord),
      },
    });
  });

  let yOffset = 0;
  mapping.subject_mappings.forEach((sm, si) => {
    nodes.push({
      id: `subject-${si}`,
      type: 'subjectNode',
      dragHandle: '.subject-drag-handle',
      position: { x: SUBJ_NODE_X, y: yOffset },
      data: {
        subjectIndex: si,
        mapping: sm,
        columns: cols,
        properties,
        sampleRecord,
        subjectMappings: mapping.subject_mappings,
        ancestorLabels: ancestorLabelsFor(sm.type_mappings?.[0]?.class_uri ?? '', mapping, classes),
        ...handlers,
      },
    });

    yOffset += subjectNodeHeight(sm) + SUBJ_GAP;
  });

  return nodes;
}

// ─── edge builder ──────────────────────────────────────────────────────────

// Find which subject a value's source was copied from, by matching both class
// URI and the actual source column/constant. Class-only matching breaks when
// two subjects share the same class (e.g. two actors).
function findRefSubject(
  mapping: MappingDocument,
  currentSi: number,
  refClass: string,
  valSource: { source: string; column_name?: string; constant_value?: string },
): number {
  return mapping.subject_mappings.findIndex((other, oi) => {
    if (oi === currentSi) return false;
    if (other.type_mappings?.[0]?.class_uri !== refClass) return false;
    if (valSource.source === 'column' && other.subject.source === 'column')
      return valSource.column_name === other.subject.column_name;
    if (valSource.source === 'constant' && other.subject.source === 'constant')
      return valSource.constant_value === other.subject.constant_value;
    return true; // expr/row_index: fall back to class match
  });
}

function buildEdges(mapping: MappingDocument): Edge[] {
  const edges: Edge[] = [];

  mapping.subject_mappings.forEach((sm, si) => {
    if (sm.subject.source === 'column' && sm.subject.column_name) {
      edges.push({
        id: `e-subj-${si}`,
        source: `col-${sm.subject.column_name}`,
        sourceHandle: 'right',
        target: `subject-${si}`,
        targetHandle: 'subject',
        style: { stroke: '#f59e0b', strokeWidth: 2 },
        animated: true,
      });
    }

    sm.property_mappings.forEach((pm, pi) => {
      pm.values.forEach((val, vi) => {
        const refClass = val.value_type.type === 'iri' ? val.value_type.type_mappings?.[0]?.class_uri : undefined;

        // subject → subject IRI reference: match by class AND source column
        if (refClass) {
          const refSi = findRefSubject(mapping, si, refClass, val.value_source);
          if (refSi !== -1) {
            edges.push({
              id: `e-ref-${refSi}-${si}-${pi}-${vi}`,
              source: `subject-${refSi}`,
              sourceHandle: 'right',
              target: `subject-${si}`,
              targetHandle: `prop-${pi}`,
              style: { stroke: '#7c3aed', strokeWidth: 2 },
              animated: true,
            });
            return; // don't also draw the column edge for this value
          }
        }

        if (val.value_source.source === 'column' && val.value_source.column_name) {
          edges.push({
            id: `e-${si}-${pi}`,
            source: `col-${val.value_source.column_name}`,
            sourceHandle: 'right',
            target: `subject-${si}`,
            targetHandle: `prop-${pi}`,
            style: {
              stroke: val.value_type.type === 'iri' ? '#7c3aed' : '#6366f1',
              strokeWidth: 1.5,
              strokeDasharray: val.value_type.type === 'iri' ? '5 3' : undefined,
            },
          });
        }
      });
    });
  });

  return edges;
}

function connectedColumnsSet(mapping: MappingDocument): Set<string> {
  const s = new Set<string>();
  mapping.subject_mappings.forEach((sm) => {
    if (sm.subject.column_name) s.add(sm.subject.column_name);
    sm.property_mappings.forEach((pm) =>
      pm.values.forEach((v) => { if (v.value_source.column_name) s.add(v.value_source.column_name); }),
    );
  });
  return s;
}

// ─── Component ─────────────────────────────────────────────────────────────

interface Props {
  schema: ExtractedSchema | null;
  mapping: MappingDocument;
  classes: OntologyClass[];
  properties: OntologyProperty[];
  sampleRecord: Record<string, unknown>;
  onMappingChange: (m: MappingDocument) => void;
  onRequestAddProperty: (subjectIndex: number, classUri: string) => void;
  onRequestEditInlineObject: (subjectIndex: number, propIndex: number) => void;
}

export function MappingCanvas({
  schema,
  mapping,
  classes,
  properties,
  sampleRecord,
  onMappingChange,
  onRequestAddProperty,
  onRequestEditInlineObject,
}: Props) {
  const updateSubjects = useCallback(
    (subjects: SubjectMapping[]) => onMappingChange({ ...mapping, subject_mappings: subjects }),
    [mapping, onMappingChange],
  );

  const onUpdate = useCallback(
    (si: number, updated: SubjectMapping) =>
      updateSubjects(mapping.subject_mappings.map((sm, i) => (i === si ? updated : sm))),
    [mapping, updateSubjects],
  );

  const onRemove = useCallback(
    (si: number) => updateSubjects(mapping.subject_mappings.filter((_, i) => i !== si)),
    [mapping, updateSubjects],
  );

  const onAddProperty = useCallback(
    (si: number) => {
      const classUri = mapping.subject_mappings[si]?.type_mappings[0]?.class_uri ?? '';
      onRequestAddProperty(si, classUri);
    },
    [mapping, onRequestAddProperty],
  );

  const onEditInlineObject = useCallback(
    (si: number, pi: number) => onRequestEditInlineObject(si, pi),
    [onRequestEditInlineObject],
  );

  const handlers: SubjectHandlers = useMemo(
    () => ({ onUpdate, onRemove, onAddProperty, onEditInlineObject }),
    [onUpdate, onRemove, onAddProperty, onEditInlineObject],
  );

  const connected = useMemo(() => connectedColumnsSet(mapping), [mapping]);

  const [nodes, setNodes, onNodesChange] = useNodesState(
    buildNodes(schema, mapping, classes, properties, handlers, connected, sampleRecord),
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(buildEdges(mapping));

  useEffect(() => {
    setNodes(buildNodes(schema, mapping, classes, properties, handlers, connected, sampleRecord));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapping, schema, properties, sampleRecord]);

  useEffect(() => {
    setEdges(buildEdges(mapping));
  }, [mapping, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      const { source, target, targetHandle } = params;
      if (!source || !target || !targetHandle) return;

      // ── column → subject ──────────────────────────────────────────
      if (source.startsWith('col-')) {
        const colName = source.replace('col-', '');
        const si = parseInt(target.replace('subject-', ''), 10);
        if (isNaN(si)) return;
        const sm = mapping.subject_mappings[si];
        if (!sm) return;

        if (targetHandle === 'subject') {
          onUpdate(si, { ...sm, subject: { source: 'column', column_name: colName } });
        } else if (targetHandle.startsWith('prop-')) {
          const pi = parseInt(targetHandle.replace('prop-', ''), 10);
          if (!isNaN(pi)) {
            const pms = sm.property_mappings.map((pm, j) => {
              if (j !== pi) return pm;
              return {
                ...pm,
                values: pm.values.map((v, vi) =>
                  vi === 0 ? { ...v, value_source: { source: 'column' as const, column_name: colName } } : v,
                ),
              };
            });
            onUpdate(si, { ...sm, property_mappings: pms });
          }
        }
        return;
      }

      // ── subject → subject (IRI reference) ────────────────────────
      if (source.startsWith('subject-') && target.startsWith('subject-') && targetHandle.startsWith('prop-')) {
        const srcSi = parseInt(source.replace('subject-', ''), 10);
        const tgtSi = parseInt(target.replace('subject-', ''), 10);
        const pi = parseInt(targetHandle.replace('prop-', ''), 10);
        if (isNaN(srcSi) || isNaN(tgtSi) || isNaN(pi) || srcSi === tgtSi) return;

        const srcSm = mapping.subject_mappings[srcSi];
        const tgtSm = mapping.subject_mappings[tgtSi];
        if (!srcSm || !tgtSm) return;

        const refClass = srcSm.type_mappings?.[0]?.class_uri;
        const newValue = {
          value_source: srcSm.subject,
          transformation: srcSm.subject_transformation,
          value_type: {
            type: 'iri' as const,
            type_mappings: refClass ? [{ class_uri: refClass }] : [],
            property_mappings: [],
          },
        };
        const pms = tgtSm.property_mappings.map((pm, j) => {
          if (j !== pi) return pm;
          // If the first value already has a column set, append; otherwise replace it
          const firstHasSource = !!(pm.values[0]?.value_source.column_name ?? pm.values[0]?.value_source.constant_value);
          return {
            ...pm,
            values: firstHasSource ? [...pm.values, newValue] : [newValue, ...pm.values.slice(1)],
          };
        });
        onUpdate(tgtSi, { ...tgtSm, property_mappings: pms });
      }
    },
    [mapping, onUpdate],
  );

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.1 }}
        minZoom={0.15}
        maxZoom={2}
        deleteKeyCode={null}
      >
        <Background color="#e5e7eb" gap={20} />
        <Controls />
        <MiniMap
          nodeStrokeColor={(n) => (n.type === 'subjectNode' ? '#6366f1' : '#9ca3af')}
          nodeColor={(n) => (n.type === 'subjectNode' ? '#eef2ff' : '#f9fafb')}
          maskColor="rgba(255,255,255,0.7)"
        />
      </ReactFlow>
    </div>
  );
}
