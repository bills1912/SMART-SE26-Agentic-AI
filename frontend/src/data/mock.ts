import { ChatMessage, VisualizationData, PolicyRecommendation } from '../types/chat';

export const mockVisualizations: VisualizationData[] = [
  {
    id: '1',
    type: 'chart',
    title: 'Policy Impact Analysis',
    config: {
      title: {
        text: 'Policy Implementation Impact',
        left: 'center',
        textStyle: {
          color: '#e74c3c',
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis'
      },
      legend: {
        data: ['Economic Impact', 'Social Impact', 'Environmental Impact'],
        bottom: 10,
        textStyle: {
          color: '#333'
        }
      },
      xAxis: {
        type: 'category',
        data: ['Q1 2024', 'Q2 2024', 'Q3 2024', 'Q4 2024'],
        axisLabel: {
          color: '#666'
        }
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#666'
        }
      },
      series: [
        {
          name: 'Economic Impact',
          type: 'bar',
          data: [85, 92, 78, 95],
          itemStyle: {
            color: '#e74c3c'
          }
        },
        {
          name: 'Social Impact',
          type: 'bar',
          data: [76, 88, 85, 90],
          itemStyle: {
            color: '#ff6b35'
          }
        },
        {
          name: 'Environmental Impact',
          type: 'bar',
          data: [68, 72, 88, 82],
          itemStyle: {
            color: '#ff8c42'
          }
        }
      ]
    },
    data: {}
  },
  {
    id: '2',
    type: 'chart',
    title: 'Stakeholder Analysis',
    config: {
      title: {
        text: 'Stakeholder Support Distribution',
        left: 'center',
        textStyle: {
          color: '#e74c3c',
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'item'
      },
      series: [
        {
          name: 'Support Level',
          type: 'pie',
          radius: '50%',
          data: [
            { value: 35, name: 'Strong Support', itemStyle: { color: '#e74c3c' } },
            { value: 25, name: 'Moderate Support', itemStyle: { color: '#ff6b35' } },
            { value: 20, name: 'Neutral', itemStyle: { color: '#ff8c42' } },
            { value: 15, name: 'Opposition', itemStyle: { color: '#ffad73' } },
            { value: 5, name: 'Strong Opposition', itemStyle: { color: '#ffd4a3' } }
          ],
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    },
    data: {}
  }
];

export const mockPolicyRecommendations: PolicyRecommendation[] = [
  {
    id: '1',
    title: 'Digital Infrastructure Investment',
    description: 'Increase funding for digital infrastructure to support economic growth and innovation.',
    priority: 'high',
    category: 'Economic Policy',
    impact: 'High potential for job creation and productivity gains',
    implementation: [
      'Allocate $2B over 3 years for broadband expansion',
      'Establish public-private partnerships for 5G deployment',
      'Create digital skills training programs',
      'Implement regulatory framework for digital services'
    ]
  },
  {
    id: '2',
    title: 'Climate Resilience Framework',
    description: 'Develop comprehensive climate adaptation and mitigation strategies.',
    priority: 'high',
    category: 'Environmental Policy',
    impact: 'Critical for long-term sustainability and economic stability',
    implementation: [
      'Establish carbon pricing mechanism',
      'Invest in renewable energy infrastructure',
      'Develop climate risk assessment protocols',
      'Create green job transition programs'
    ]
  },
  {
    id: '3',
    title: 'Healthcare Access Initiative',
    description: 'Improve healthcare accessibility and affordability across all demographic groups.',
    priority: 'medium',
    category: 'Social Policy',
    impact: 'Significant improvement in public health outcomes',
    implementation: [
      'Expand community health centers',
      'Implement telemedicine infrastructure',
      'Reduce prescription drug costs',
      'Increase healthcare workforce training'
    ]
  }
];

export const mockInsights: string[] = [
  'Analysis shows strong correlation between digital infrastructure investment and economic growth metrics.',
  'Stakeholder surveys indicate majority support for climate resilience initiatives across all demographic groups.',
  'Cost-benefit analysis suggests healthcare access improvements would generate 3.2:1 ROI over 5 years.',
  'Implementation timeline suggests optimal policy rollout would begin with digital infrastructure, followed by climate and healthcare initiatives.',
  'Risk assessment indicates minimal political opposition to proposed healthcare reforms.'
];

export const mockChatMessages: ChatMessage[] = [
  {
    id: '1',
    session_id: 'mock_session',
    sender: 'ai',
    content: 'Hello! I\'m your AI Policy Analyst. I can help you analyze policy scenarios, generate insights, and create visualizations. What policy area would you like to explore today?',
    timestamp: new Date(Date.now() - 5 * 60 * 1000),
  },
  {
    id: '2',
    session_id: 'mock_session',
    sender: 'user',
    content: 'I need to analyze the potential impact of new digital infrastructure policies on economic growth.',
    timestamp: new Date(Date.now() - 4 * 60 * 1000),
  },
  {
    id: '3',
    session_id: 'mock_session',
    sender: 'ai',
    content: 'I\'ve analyzed the digital infrastructure policy impacts. Based on economic modeling and stakeholder analysis, here are the key findings:',
    timestamp: new Date(Date.now() - 3 * 60 * 1000),
    visualizations: mockVisualizations,
    insights: mockInsights,
    policies: mockPolicyRecommendations,
  }
];

export const generateMockResponse = (userMessage: string): ChatMessage => {
  const responseTexts = [
    'Based on your query, I\'ve generated a comprehensive policy analysis with key insights and recommendations.',
    'Here\'s my analysis of the policy scenario with supporting visualizations and strategic recommendations.',
    'I\'ve processed your request and identified several critical policy considerations with data-driven insights.',
  ];

  return {
    id: Math.random().toString(36).substr(2, 9),
    sender: 'ai',
    content: responseTexts[Math.floor(Math.random() * responseTexts.length)],
    timestamp: new Date(),
    visualizations: Math.random() > 0.5 ? mockVisualizations : undefined,
    insights: Math.random() > 0.3 ? mockInsights : undefined,
    policies: Math.random() > 0.4 ? mockPolicyRecommendations : undefined,
  };
};