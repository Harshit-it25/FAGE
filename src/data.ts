import { Alert, SHAPDriver, AnalystNote, FraudCluster, OutlierEvent } from './types';

export const initialAlerts: Alert[] = [
  {
    id: 'ALT-9842-X',
    accountNumber: '4992-XXXX-8211',
    type: 'Rapid Fund Transfer (Mule)',
    riskScore: 98,
    confidence: 'High (92%)',
    confidenceVal: 92.4,
    status: 'Escalated',
    timestamp: '10 mins ago',
    holderName: 'Robert P. Jenkins',
    ssn: '***-**-8921',
    dateOpened: '2023-10-14',
    balance: 42.50,
    ytdInflows: 145200.00,
    ytdOutflows: 145157.50,
    prio: 'P1 - Immediate'
  },
  {
    id: 'ALT-9841-M',
    accountNumber: '3319-XXXX-1032',
    type: 'Suspicious Network Link',
    riskScore: 85,
    confidence: 'Medium (74%)',
    confidenceVal: 74.0,
    status: 'Open',
    timestamp: '45 mins ago',
    holderName: 'Sarah L. Connor',
    ssn: '***-**-3312',
    dateOpened: '2022-04-18',
    balance: 8940.00,
    ytdInflows: 84100.00,
    ytdOutflows: 75160.00,
    prio: 'P2 - Review'
  },
  {
    id: 'ALT-9839-K',
    accountNumber: '7721-XXXX-4566',
    type: 'High Velocity Deposits',
    riskScore: 62,
    confidence: 'Low (45%)',
    confidenceVal: 45.2,
    status: 'Open',
    timestamp: '2 hours ago',
    holderName: 'Michael J. Fox',
    ssn: '***-**-5219',
    dateOpened: '2021-09-05',
    balance: 24500.20,
    ytdInflows: 12100.00,
    ytdOutflows: 4500.00,
    prio: 'P3 - Monitor'
  },
  {
    id: 'ALT-9835-Z',
    accountNumber: '1094-XXXX-3345',
    type: 'Smurfing Inflow Structure',
    riskScore: 88,
    confidence: 'High (89%)',
    confidenceVal: 89.1,
    status: 'Closed',
    timestamp: '5 hours ago',
    holderName: 'Amanda S. Todd',
    ssn: '***-**-1094',
    dateOpened: '2023-11-01',
    balance: 1420.50,
    ytdInflows: 219000.00,
    ytdOutflows: 217580.00,
    prio: 'P2 - Review'
  },
  {
    id: 'ALT-9831-C',
    accountNumber: '8921-XXXX-9902',
    type: 'Synthetic Proxy Layer',
    riskScore: 95,
    confidence: 'High (96%)',
    confidenceVal: 96.0,
    status: 'Open',
    timestamp: 'Yesterday',
    holderName: 'David K. Miller',
    ssn: '***-**-4458',
    dateOpened: '2024-01-15',
    balance: 310.00,
    ytdInflows: 48900.00,
    ytdOutflows: 48590.00,
    prio: 'P1 - Immediate'
  },
  {
    id: 'ALT-9828-A',
    accountNumber: '2411-XXXX-0941',
    type: 'High Velocity Depositor',
    riskScore: 82,
    confidence: 'High (91%)',
    confidenceVal: 91.0,
    status: 'Open',
    timestamp: '1 day ago',
    holderName: 'Elena V. Petrova',
    ssn: '***-**-6021',
    dateOpened: '2023-08-30',
    balance: 1205.10,
    ytdInflows: 94500.00,
    ytdOutflows: 93295.00,
    prio: 'P2 - Review'
  },
  {
    id: 'ALT-9822-R',
    accountNumber: '1105-XXXX-7142',
    type: 'Crypto Transit Account',
    riskScore: 91,
    confidence: 'High (94%)',
    confidenceVal: 94.2,
    status: 'Investigating',
    timestamp: '2 days ago',
    holderName: 'Charles E. Xavier',
    ssn: '***-**-0071',
    dateOpened: '2023-02-14',
    balance: 95.80,
    ytdInflows: 310400.00,
    ytdOutflows: 310304.20,
    prio: 'P1 - Immediate'
  },
  {
    id: 'ALT-9815-H',
    accountNumber: '9082-XXXX-1144',
    type: 'Multi-ID IP Cluster',
    riskScore: 12,
    confidence: 'Low (45%)',
    confidenceVal: 45.2,
    status: 'Closed',
    timestamp: '3 days ago',
    holderName: 'Nate D. Arch',
    ssn: '***-**-1140',
    dateOpened: '2020-07-22',
    balance: 55420.00,
    ytdInflows: 7500.00,
    ytdOutflows: 8200.00,
    prio: 'Routine'
  }
];

export const shapDrivers: SHAPDriver[] = [
  {
    featureId: 'F3889',
    name: 'Velocity of Incoming Transfers (24h)',
    type: 'Behavioral',
    shapValue: 0.42,
    importanceScore: 0.842,
    value: '14 txns'
  },
  {
    featureId: 'F670',
    name: 'Ratio of External Transfers',
    type: 'Network',
    shapValue: 0.31,
    importanceScore: 0.715,
    value: '0.95'
  },
  {
    featureId: 'F115',
    name: 'Age of Account',
    type: 'Profile',
    shapValue: 0.28,
    importanceScore: 0.638,
    value: '4 days'
  },
  {
    featureId: 'F527',
    name: 'Device IP Risk Score',
    type: 'Technical',
    shapValue: -0.12,
    importanceScore: 0.571,
    value: '0.12'
  },
  {
    featureId: 'F321',
    name: 'Distance from Typical Location',
    type: 'Network',
    shapValue: -0.05,
    importanceScore: 0.412,
    value: '12 km'
  },
  {
    featureId: 'F2082',
    name: 'Count of Linked Accounts',
    type: 'Profile',
    shapValue: 0.15,
    importanceScore: 0.345,
    value: '5 profiles'
  }
];

export const rfDrivers: SHAPDriver[] = [
  {
    featureId: 'F5112',
    name: 'Cross-Border Volume Ratio',
    type: 'Network',
    shapValue: 0.48,
    importanceScore: 0.891,
    value: '0.85'
  },
  {
    featureId: 'F233',
    name: 'Velocity Change Ratio (7d)',
    type: 'Behavioral',
    shapValue: 0.35,
    importanceScore: 0.760,
    value: '+220%'
  },
  {
    featureId: 'F881',
    name: 'Account Open Tenure',
    type: 'Profile',
    shapValue: -0.18,
    importanceScore: 0.620,
    value: '12 days'
  },
  {
    featureId: 'F1054',
    name: 'High Risk Host ASN Match',
    type: 'Technical',
    shapValue: 0.29,
    importanceScore: 0.518,
    value: 'ASN 44510'
  }
];

export const initialNotes: Record<string, AnalystNote[]> = {
  'ALT-9842-X': [
    {
      id: 'N-1',
      author: 'System Auto-Note',
      timestamp: 'Oct 24, 14:32 UTC',
      content: 'Flagged by Ensemble Model v4.2. IP mismatch detected during login attempt from known high-risk ASN.',
      isSystem: true
    }
  ],
  'ALT-9841-M': [
    {
      id: 'N-2',
      author: 'System Auto-Note',
      timestamp: 'Oct 25, 09:12 UTC',
      content: 'Linked structure found. Multi-hop sender correlates with previously tagged fraud ring CTR-551.',
      isSystem: true
    }
  ]
};

export const fraudClusters: FraudCluster[] = [
  {
    id: 'Cluster A-104',
    name: 'Rapid Cross-Border Transfers',
    description: 'Rapid cross-border transfers matching known mule typologies.',
    severity: 'Critical',
    entitiesCount: 24,
    score: 0.98
  },
  {
    id: 'Cluster C-992',
    name: 'Dormant Reactivation Layering',
    description: 'Dormant accounts suddenly receiving layered deposits from alternative sources.',
    severity: 'High',
    entitiesCount: 12,
    score: 0.85
  },
  {
    id: 'Cluster B-450',
    name: 'Crypto Funneling Synchronicity',
    description: 'Crypto exchange funneling with synchronized deposit-to-withdraw timing patterns.',
    severity: 'High',
    entitiesCount: 8,
    score: 0.82
  }
];

export const outlierEvents: OutlierEvent[] = [
  {
    id: 'EVT-9901',
    timestamp: '2023-10-27 14:32:01',
    patternType: 'Velocity Spike',
    severity: 'Critical'
  },
  {
    id: 'EVT-9900',
    timestamp: '2023-10-27 13:15:44',
    patternType: 'Structuring',
    severity: 'High'
  },
  {
    id: 'EVT-9899',
    timestamp: '2023-10-27 11:05:20',
    patternType: 'Geographic Anomaly',
    severity: 'Medium'
  }
];
