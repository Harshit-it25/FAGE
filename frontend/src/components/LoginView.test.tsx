import { vi, describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import LoginView from './LoginView';
import { useAuth } from '../context/AuthContext';

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('LoginView', () => {
  const mockLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      login: mockLogin,
    });
  });

  it('renders login form correctly', () => {
    const { container } = render(<LoginView />);

        expect(screen.getByText('FAGE Workbench')).toBeInTheDocument();
    expect(screen.getByText('Sign in to continue')).toBeInTheDocument();

    const usernameInput = container.querySelector('input:not([type="password"])');
    const passwordInput = container.querySelector('input[type="password"]');

        expect(usernameInput).toHaveValue('admin');
    expect(passwordInput).toHaveValue('admin123');
    expect(screen.getByRole('button', { name: /Sign in/i })).toBeInTheDocument();
  });

  it('submitting the form calls login with provided credentials', async () => {
    const user = userEvent.setup();
    const { container } = render(<LoginView />);

        const usernameInput = container.querySelector('input:not([type="password"])') as HTMLInputElement;
    const passwordInput = container.querySelector('input[type="password"]') as HTMLInputElement;
    const submitBtn = screen.getByRole('button', { name: /Sign in/i });

    await user.clear(usernameInput);
    await user.type(usernameInput, 'testuser');
    await user.clear(passwordInput);
    await user.type(passwordInput, 'testpass');

        await act(async () => {
      await user.click(submitBtn);
    });

    expect(mockLogin).toHaveBeenCalledWith('testuser', 'testpass');
  });

  it('displays error message on login failure', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));

        render(<LoginView />);

        const submitBtn = screen.getByRole('button', { name: /Sign in/i });

        await act(async () => {
      await user.click(submitBtn);
    });

    expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
  });
});
