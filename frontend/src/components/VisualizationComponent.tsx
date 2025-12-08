import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { VisualizationData } from '../types/chat';

interface VisualizationComponentProps {
  visualization: VisualizationData;
}

const VisualizationComponent: React.FC<VisualizationComponentProps> = ({ visualization }) => {
  // Detect dark mode
  const isDarkMode = document.documentElement.classList.contains('dark');
  
  // Enhanced config with better text visibility
  const enhancedConfig = useMemo(() => {
    const config = { ...visualization.config };
    
    // Text colors for dark mode
    const textColor = isDarkMode ? '#E5E7EB' : '#374151';
    const subtextColor = isDarkMode ? '#9CA3AF' : '#6B7280';
    const lineColor = isDarkMode ? '#4B5563' : '#D1D5DB';
    
    // Update title colors
    if (config.title) {
      config.title = {
        ...config.title,
        textStyle: {
          ...config.title.textStyle,
          color: textColor,
          fontWeight: 600
        },
        subtextStyle: {
          ...config.title.subtextStyle,
          color: subtextColor
        }
      };
    }
    
    // Update legend colors
    if (config.legend) {
      config.legend = {
        ...config.legend,
        textStyle: {
          ...config.legend.textStyle,
          color: textColor
        }
      };
    }
    
    // Update axis colors (for line/bar charts)
    if (config.xAxis) {
      if (Array.isArray(config.xAxis)) {
        config.xAxis = config.xAxis.map((axis: any) => ({
          ...axis,
          axisLabel: {
            ...axis.axisLabel,
            color: textColor,
            fontSize: 12
          },
          axisLine: {
            ...axis.axisLine,
            lineStyle: {
              ...axis.axisLine?.lineStyle,
              color: lineColor
            }
          },
          splitLine: {
            ...axis.splitLine,
            lineStyle: {
              ...axis.splitLine?.lineStyle,
              color: lineColor,
              opacity: 0.3
            }
          }
        }));
      } else {
        config.xAxis = {
          ...config.xAxis,
          axisLabel: {
            ...config.xAxis.axisLabel,
            color: textColor,
            fontSize: 12
          },
          axisLine: {
            ...config.xAxis.axisLine,
            lineStyle: {
              ...config.xAxis.axisLine?.lineStyle,
              color: lineColor
            }
          },
          splitLine: {
            ...config.xAxis.splitLine,
            lineStyle: {
              ...config.xAxis.splitLine?.lineStyle,
              color: lineColor,
              opacity: 0.3
            }
          }
        };
      }
    }
    
    if (config.yAxis) {
      if (Array.isArray(config.yAxis)) {
        config.yAxis = config.yAxis.map((axis: any) => ({
          ...axis,
          axisLabel: {
            ...axis.axisLabel,
            color: textColor,
            fontSize: 12
          },
          axisLine: {
            ...axis.axisLine,
            lineStyle: {
              ...axis.axisLine?.lineStyle,
              color: lineColor
            }
          },
          splitLine: {
            ...axis.splitLine,
            lineStyle: {
              ...axis.splitLine?.lineStyle,
              color: lineColor,
              opacity: 0.3
            }
          }
        }));
      } else {
        config.yAxis = {
          ...config.yAxis,
          axisLabel: {
            ...config.yAxis.axisLabel,
            color: textColor,
            fontSize: 12
          },
          axisLine: {
            ...config.yAxis.axisLine,
            lineStyle: {
              ...config.yAxis.axisLine?.lineStyle,
              color: lineColor
            }
          },
          splitLine: {
            ...config.yAxis.splitLine,
            lineStyle: {
              ...config.yAxis.splitLine?.lineStyle,
              color: lineColor,
              opacity: 0.3
            }
          }
        };
      }
    }
    
    // Update tooltip
    if (config.tooltip) {
      config.tooltip = {
        ...config.tooltip,
        backgroundColor: isDarkMode ? 'rgba(31, 41, 55, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        borderColor: isDarkMode ? '#4B5563' : '#E5E7EB',
        textStyle: {
          ...config.tooltip.textStyle,
          color: textColor
        }
      };
    }
    
    // Set background transparent
    config.backgroundColor = 'transparent';
    
    return config;
  }, [visualization.config, isDarkMode]);
  
  return (
    <div className="p-6 bg-white dark:bg-gray-700 border border-orange-200 dark:border-gray-600 shadow-lg rounded-xl">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white">{visualization.title}</h3>
      </div>
      <div className="w-full">
        <ReactECharts
          option={enhancedConfig}
          style={{ height: '400px', width: '100%' }}
          opts={{ renderer: 'svg' }}
        />
      </div>
    </div>
  );
};

export default VisualizationComponent;