import { useMemo, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { OntologyClassNode, type OntologyClassNodeData } from './nodes/OntologyClassNode';
import { OntologyCoveragePanel } from './panels/OntologyCoveragePanel';
import type { MappingDocument, OntologyClass, OntologyProperty } from '../types';
import { collectMappedUris, computeAncestors, computeDepths, computeLeafClasses, layoutClasses, type MappedUris } from '../lib/ontologyGraph';

const NODE_TYPES: NodeTypes = {
  ontologyClassNode: OntologyClassNode,
};

// ─── builders ──────────────────────────────────────────────────────────────

function buildNodes(
  classes: OntologyClass[],
  properties: OntologyProperty[],
  positions: Map<string, { x: number; y: number }>,
  mapped: MappedUris,
  leafClasses: Set<string>,
  selectedUri: string | null,
  onSelect: (uri: string) => void,
): Node[] {
  return classes.map((cls) => {
    const ancestors = computeAncestors(cls.uri, classes);
    const domainProps = properties.filter((p) => p.domain.length === 0 || p.domain.some((d) => ancestors.has(d)));
    const mappedPropCount = domainProps.filter((p) => mapped.properties.has(p.uri)).length;

    const data: OntologyClassNodeData = {
      cls,
      isMapped: mapped.classes.has(cls.uri),
      isLeaf: leafClasses.has(cls.uri),
      mappedPropCount,
      totalPropCount: domainProps.length,
      isSelected: selectedUri === cls.uri,
      onSelect: () => onSelect(cls.uri),
    };

    return {
      id: `cls-${cls.uri}`,
      type: 'ontologyClassNode',
      position: positions.get(cls.uri) ?? { x: 0, y: 0 },
      data,
    };
  });
}

function buildEdges(classes: OntologyClass[], properties: OntologyProperty[], mapped: MappedUris): Edge[] {
  const known = new Set(classes.map((c) => c.uri));
  const edges: Edge[] = [];

  classes.forEach((cls) => {
    cls.subclass_of.forEach((parentUri) => {
      if (!known.has(parentUri)) return;
      edges.push({
        id: `sub-${parentUri}-${cls.uri}`,
        source: `cls-${parentUri}`,
        target: `cls-${cls.uri}`,
        sourceHandle: 'out',
        targetHandle: 'in',
        type: 'smoothstep',
        label: 'subclass of',
        labelStyle: { fontSize: 9, fill: '#94a3b8' },
        labelBgStyle: { fill: '#f9fafb', fillOpacity: 0.9 },
        style: { stroke: '#cbd5e1', strokeWidth: 1.5, strokeDasharray: '4 3' },
      });
    });
  });

  properties
    .filter((p) => p.is_object_property)
    .forEach((p) => {
      const isMapped = mapped.properties.has(p.uri);
      p.domain.forEach((domainUri) => {
        if (!known.has(domainUri)) return;
        p.range_.forEach((rangeUri) => {
          if (!known.has(rangeUri)) return;
          edges.push({
            id: `prop-${p.uri}-${domainUri}-${rangeUri}`,
            source: `cls-${domainUri}`,
            target: `cls-${rangeUri}`,
            sourceHandle: 'out',
            targetHandle: 'in',
            label: p.label,
            labelStyle: { fontSize: 9, fill: isMapped ? '#4f46e5' : '#cbd5e1' },
            labelBgStyle: { fill: '#f9fafb', fillOpacity: 0.9 },
            style: {
              stroke: isMapped ? '#6366f1' : '#e2e8f0',
              strokeWidth: isMapped ? 1.75 : 1,
            },
            animated: isMapped,
          });
        });
      });
    });

  return edges;
}

// ─── legend ────────────────────────────────────────────────────────────────

function Legend() {
  return (
    <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur rounded-lg shadow border border-gray-200 px-3 py-2 text-[10px] text-gray-500 space-y-1 z-10">
      <div className="font-semibold text-gray-600 mb-1">Legend</div>
      <div className="flex items-center gap-1.5">
        <span className="w-8 h-4 rounded border border-gray-300 bg-white inline-flex items-center justify-center">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
        </span>
        Leaf class (concrete)
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-8 h-4 rounded border border-dashed border-gray-300 bg-white inline-flex items-center justify-center">
          <span className="w-1.5 h-1.5 rounded-full border border-gray-400" />
        </span>
        Abstract class
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-8 h-4 rounded border border-emerald-300 bg-emerald-50 inline-block" />
        Used in mapping
      </div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-4 border-t-2 border-indigo-400" /> Mapped object property</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-4 border-t-2 border-gray-200" /> Unmapped object property</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-4 border-t border-dashed border-gray-300" /> Subclass relation</div>
    </div>
  );
}

// ─── component ─────────────────────────────────────────────────────────────

interface Props {
  classes: OntologyClass[];
  properties: OntologyProperty[];
  mapping: MappingDocument | null;
}

export function OntologyGraphView({ classes, properties, mapping }: Props) {
  const [selectedUri, setSelectedUri] = useState<string | null>(null);

  const mapped = useMemo(
    () => (mapping ? collectMappedUris(mapping) : { classes: new Set<string>(), properties: new Set<string>() }),
    [mapping],
  );

  const positions = useMemo(() => {
    const depths = computeDepths(classes);
    return layoutClasses(classes, depths);
  }, [classes]);

  const leafClasses = useMemo(() => computeLeafClasses(classes), [classes]);

  const nodes = useMemo(
    () => buildNodes(classes, properties, positions, mapped, leafClasses, selectedUri, setSelectedUri),
    [classes, properties, positions, mapped, leafClasses, selectedUri],
  );
  const edges = useMemo(() => buildEdges(classes, properties, mapped), [classes, properties, mapped]);

  const selectedClass = classes.find((c) => c.uri === selectedUri) ?? null;

  return (
    <div className="flex h-full w-full min-h-0">
      <div className="flex-1 min-w-0 relative">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.1}
            maxZoom={2}
            nodesDraggable={false}
            nodesConnectable={false}
            onPaneClick={() => setSelectedUri(null)}
          >
            <Background color="#e5e7eb" gap={20} />
            <Controls showInteractive={false} />
            <MiniMap
              nodeStrokeColor={(n) => ((n.data as OntologyClassNodeData).isMapped ? '#10b981' : '#9ca3af')}
              nodeColor={(n) => ((n.data as OntologyClassNodeData).isMapped ? '#d1fae5' : '#f9fafb')}
              maskColor="rgba(255,255,255,0.7)"
            />
          </ReactFlow>
        </ReactFlowProvider>
        <Legend />
        {!mapping && (
          <div className="absolute top-4 left-4 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-lg px-3 py-1.5 shadow-sm z-10">
            No mapping loaded — showing ontology structure only. Select a mapping to see coverage.
          </div>
        )}
      </div>

      {selectedClass && (
        <OntologyCoveragePanel
          selectedClass={selectedClass}
          classes={classes}
          properties={properties}
          mapping={mapping}
          onClose={() => setSelectedUri(null)}
        />
      )}
    </div>
  );
}
