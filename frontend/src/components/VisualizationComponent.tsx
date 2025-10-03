import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Card } from './ui/card.jsx';
import { VisualizationData } from '../types/chat';

interface VisualizationComponentProps {
  visualization: VisualizationData;
}

const VisualizationComponent: React.FC<VisualizationComponentProps> = ({ visualization }) => {
  return (
    <Card className="p-6 bg-white border-orange-200 shadow-lg">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800">{visualization.title}</h3>
      </div>
      <div className="w-full">
        <ReactECharts
          option={visualization.config}
          style={{ height: '400px', width: '100%' }}
          opts={{ renderer: 'svg' }}
        />
      </div>
    </Card>
  );
};

export default VisualizationComponent;