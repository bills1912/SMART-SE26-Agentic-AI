import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface VisualizationConfig {
  id: string;
  type: string;
  title: string;
  config: any;
  data?: any;
}

interface DataVisualizationProps {
  visualizations: VisualizationConfig[];
}

const DataVisualization: React.FC<DataVisualizationProps> = ({ visualizations }) => {
  if (!visualizations || visualizations.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <p>Tidak ada visualisasi data untuk ditampilkan.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {visualizations.map((viz, index) => (
        <ChartComponent key={viz.id || index} config={viz.config} title={viz.title} />
      ))}
    </div>
  );
};

interface ChartComponentProps {
  config: any;
  title: string;
}

const ChartComponent: React.FC<ChartComponentProps> = ({ config, title }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current || !config) return;

    // Initialize chart
    chartInstance.current = echarts.init(chartRef.current, 'dark');
    
    // Set options
    chartInstance.current.setOption(config);

    // Handle resize
    const handleResize = () => {
      chartInstance.current?.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
    };
  }, [config]);

  return (
    <div className="bg-gray-700 rounded-xl p-4">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div ref={chartRef} className="w-full h-80" />
    </div>
  );
};

export default DataVisualization;
