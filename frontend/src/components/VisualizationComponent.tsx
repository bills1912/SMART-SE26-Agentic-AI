import React from 'react';
import ReactECharts from 'echarts-for-react';
import { VisualizationData } from '../types/chat';

interface VisualizationComponentProps {
  visualization: VisualizationData;
}

const VisualizationComponent: React.FC<VisualizationComponentProps> = ({ visualization }) => {
  return (
    <div className="p-6 bg-white dark:bg-gray-700 border border-orange-200 dark:border-gray-600 shadow-lg rounded-xl">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white">{visualization.title}</h3>
      </div>
      <div className="w-full">
        <ReactECharts
          option={visualization.config}
          style={{ height: '400px', width: '100%' }}
          opts={{ renderer: 'svg' }}
        />
      </div>
    </div>
  );
};

export default VisualizationComponent;