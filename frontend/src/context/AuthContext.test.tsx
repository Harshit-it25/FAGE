import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import React from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import * as authService from '../services/auth';

vi.mock('../services/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/auth')>();
  return {
    ...actual,
    loginRequest: vi.fn(),
    clearSession: vi.fn(),
  };
});

const TestComponent = () => {
  const auth = useAuth();
  
  return (
    <div>
      <div data-testid="auth-status">{auth.isAuthenticated ? 'Authenticated' : 'Unauthenticated'}</div>
      <div data-testid="username">{auth.user?.username || 'none'}</div>
      <button data-testid="login-btn" onClick={() => auth.login('testuser', 'password')}>
        Login
      </button>
      <button data-testid="logout-btn" onClick={() => auth.logout()}>
        Logout
      </button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('should be unauthenticated initially when no stored token exists', () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status').textContent).toBe('Unauthenticated');
    expect(screen.getByTestId('username').textContent).toBe('none');
  });

  it('should be authenticated initially when stored token and user exist', () => {
    localStorage.setItem('fage_access_token', 'test-token');
    localStorage.setItem(
      'fage_user',
      JSON.stringify({ username: 'storeduser', role: 'admin', display_name: 'Stored User' })
    );

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status').textContent).toBe('Authenticated');
    expect(screen.getByTestId('username').textContent).toBe('storeduser');
  });

  it('login function should update the user state and status', async () => {
    (authService.loginRequest as any).mockResolvedValueOnce({
      access_token: 'new-token',
      user: { username: 'loggeduser', role: 'analyst', display_name: 'Logged User' },
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status').textContent).toBe('Unauthenticated');

    await act(async () => {
      screen.getByTestId('login-btn').click();
    });

    expect(authService.loginRequest).toHaveBeenCalledWith('testuser', 'password');
    expect(screen.getByTestId('auth-status').textContent).toBe('Authenticated');
    expect(screen.getByTestId('username').textContent).toBe('loggeduser');
  });

  it('logout function should reset the user state and call clearSession', () => {
    localStorage.setItem('fage_access_token', 'test-token');
    localStorage.setItem(
      'fage_user',
      JSON.stringify({ username: 'storeduser', role: 'admin', display_name: 'Stored User' })
    );

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status').textContent).toBe('Authenticated');

    act(() => {
      screen.getByTestId('logout-btn').click();
    });

    expect(authService.clearSession).toHaveBeenCalled();
    expect(screen.getByTestId('auth-status').textContent).toBe('Unauthenticated');
    expect(screen.getByTestId('username').textContent).toBe('none');
  });

  it('useAuth hook should throw an error when used outside AuthProvider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    
    expect(() => {
      render(<TestComponent />);
    }).toThrow('useAuth must be used within AuthProvider');
    
    consoleError.mockRestore();
  });
});
