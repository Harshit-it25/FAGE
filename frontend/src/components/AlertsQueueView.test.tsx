import { vi, describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import AlertsQueueView from './AlertsQueueView';
import { Alert } from '../types';

const mockAlerts: Alert[] = [
  {
    id: 'ALT-123',
    accountNumber: 'ACC-RECEIVER',
    receiverAccountId: 'ACC-RECEIVER',
    type: 'Suspicious Transfer',
    riskScore: 90,
    alertSeverity: 'High',
    confidence: 'High',
    confidenceVal: 95,
    status: 'Open',
    timestamp: '2023-01-01T12:00:00Z',
    transactionAmount: 50000,
    prio: 'High',
    assignedTo: 'Unassigned',
    reason: 'Suspicious transaction',
    logs: [],
    keyRiskDrivers: [],
    confidenceInterval: null,
    evasionResistance: null,
    triageDecision: null,
    hasRealExplainability: false,
  },
];

describe('AlertsQueueView', () => {
  const mockOnSelectAlert = vi.fn();
  const mockOnUpdateStatus = vi.fn();
  const mockOnUpdateAssignment = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly with an empty queue', () => {
    render(
      <AlertsQueueView
        alerts={[]}
        onSelectAlert={mockOnSelectAlert}
        onUpdateStatus={mockOnUpdateStatus}
        theme="analytics"
      />
    );

    expect(screen.getByText('No matching accounts in active queue.')).toBeInTheDocument();
    expect(screen.getByText('Total Pending').nextSibling?.textContent).toBe('0');
  });

  it('renders a list of alerts', () => {
    render(
      <AlertsQueueView
        alerts={mockAlerts}
        onSelectAlert={mockOnSelectAlert}
        onUpdateStatus={mockOnUpdateStatus}
        theme="analytics"
      />
    );

    expect(screen.getByText('ALT-123')).toBeInTheDocument();
    expect(screen.getByText('ACC-RECEIVER')).toBeInTheDocument();
    expect(screen.getByText('90')).toBeInTheDocument();
    expect(screen.getAllByText('Open').length).toBeGreaterThan(0);
  });

  it('triggers onUpdateStatus when escalating an alert', async () => {
    const user = userEvent.setup();
    render(
      <AlertsQueueView
        alerts={mockAlerts}
        onSelectAlert={mockOnSelectAlert}
        onUpdateStatus={mockOnUpdateStatus}
        theme="analytics"
      />
    );

    const escalateBtn = screen.getByTitle('Escalate');

        await act(async () => {
      await user.click(escalateBtn);
    });

    expect(mockOnUpdateStatus).toHaveBeenCalledWith('ALT-123', 'Escalated');
  });

  it('triggers onSelectAlert when clicking Review', async () => {
    const user = userEvent.setup();
    render(
      <AlertsQueueView
        alerts={mockAlerts}
        onSelectAlert={mockOnSelectAlert}
        onUpdateStatus={mockOnUpdateStatus}
        theme="analytics"
      />
    );

    const reviewBtn = screen.getByRole('button', { name: /Review/i });

        await act(async () => {
      await user.click(reviewBtn);
    });

    expect(mockOnSelectAlert).toHaveBeenCalledWith('ALT-123');
  });
});
