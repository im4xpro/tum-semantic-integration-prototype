import { Handle, Position, type NodeProps } from '@xyflow/react';

export interface ColumnNodeData {
  name: string;
  dataType: string;
  isPrimaryKey: boolean;
  isNullable: boolean;
  isConnected: boolean;
  exampleValue?: string;
  [key: string]: unknown;
}

export function ColumnNode({ data }: NodeProps) {
  const d = data as ColumnNodeData;
  return (
    <div
      className={`rounded-lg border shadow-sm px-3 py-2 text-xs min-w-[160px] transition-colors ${
        d.isConnected
          ? 'bg-blue-50 border-blue-300'
          : 'bg-white border-gray-300'
      }`}
    >
      <div className="font-semibold text-gray-800 truncate max-w-[180px]" title={d.name}>
        {d.name}
      </div>
      <div className="text-gray-400 flex items-center gap-1 mt-0.5">
        <span>{d.dataType}</span>
        {d.isPrimaryKey && (
          <span className="text-amber-500 font-medium">PK</span>
        )}
        {!d.isNullable && (
          <span className="text-red-400">NN</span>
        )}
      </div>
      {d.exampleValue !== undefined && d.exampleValue !== '' && (
        <div className="text-gray-400 italic font-mono truncate max-w-[180px] mt-0.5" title={String(d.exampleValue)}>
          {String(d.exampleValue)}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        style={{ background: d.isConnected ? '#3b82f6' : '#9ca3af', width: 8, height: 8 }}
      />
    </div>
  );
}
