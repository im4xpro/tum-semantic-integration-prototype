import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { OntologyClass } from '../../types';

export interface OntologyClassNodeData {
  cls: OntologyClass;
  isMapped: boolean;
  isLeaf: boolean;
  mappedPropCount: number;
  totalPropCount: number;
  isSelected: boolean;
  onSelect: () => void;
  [key: string]: unknown;
}

export function OntologyClassNode({ data }: NodeProps) {
  const d = data as OntologyClassNodeData;
  const { cls } = d;

  const borderStyle = d.isLeaf
    ? (d.isMapped ? 'border-emerald-300' : 'border-gray-300')
    : (d.isMapped ? 'border-emerald-300 border-dashed' : 'border-gray-300 border-dashed');

  return (
    <div
      onClick={d.onSelect}
      className={`rounded-lg border shadow-sm px-3 py-2 text-xs min-w-[180px] cursor-pointer transition-colors ${
        d.isSelected ? 'ring-2 ring-indigo-400' : ''
      } ${d.isMapped ? 'bg-emerald-50' : 'bg-white'} ${borderStyle}`}
    >
      <Handle type="target" position={Position.Left} id="in" style={{ background: '#9ca3af', width: 8, height: 8 }} />

      <div className="flex items-center gap-1.5 min-w-0">
        {d.isLeaf ? (
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${d.isMapped ? 'bg-emerald-500' : 'bg-gray-300'}`} />
        ) : (
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 border ${d.isMapped ? 'border-emerald-500' : 'border-gray-400'}`} />
        )}
        <span className={`font-semibold truncate ${d.isLeaf ? 'text-gray-800' : 'text-gray-500'}`} title={cls.label}>{cls.label}</span>
        {!d.isLeaf && (
          <span className="text-[9px] bg-gray-100 text-gray-400 rounded px-0.5 flex-shrink-0">abstract</span>
        )}
        {cls.is_extension && (
          <span className="text-[9px] bg-amber-100 text-amber-600 rounded px-0.5 flex-shrink-0">ext</span>
        )}
      </div>
      <div className="text-[10px] text-gray-400 font-mono truncate">{cls.uri.split(/[#/]/).pop()}</div>

      {d.totalPropCount > 0 && (
        <div
          className={`text-[10px] mt-1 font-medium ${
            d.mappedPropCount === 0
              ? 'text-gray-400'
              : d.mappedPropCount === d.totalPropCount
              ? 'text-emerald-600'
              : 'text-amber-600'
          }`}
        >
          {d.mappedPropCount}/{d.totalPropCount} properties mapped
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        id="out"
        style={{ background: d.isMapped ? '#10b981' : '#9ca3af', width: 8, height: 8 }}
      />
    </div>
  );
}
