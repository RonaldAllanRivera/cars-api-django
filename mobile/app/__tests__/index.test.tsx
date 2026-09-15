import { render, screen } from '@testing-library/react-native';

import { useAuth } from '@/auth/AuthContext';
import Landing from '../index';

jest.mock('@/auth/AuthContext', () => ({ useAuth: jest.fn() }));

const mockUseAuth = jest.mocked(useAuth);

const signedIn = (status: 'loading' | 'authenticated' | 'anonymous') => {
  mockUseAuth.mockReturnValue({ status, user: null, signIn: jest.fn(), signOut: jest.fn() });
};

describe('<Landing />', () => {
  it('names the app and offers a way in', () => {
    signedIn('anonymous');

    render(<Landing />);

    expect(screen.getByText('Cars Images')).toBeTruthy();
    expect(screen.getByText('Sign in')).toBeTruthy();
  });

  it('sends an already-signed-in visitor onward instead of back through sign-in', () => {
    // Otherwise the entry point is a dead end that mints a second Sanctum
    // token under the same device name on every visit.
    signedIn('authenticated');

    render(<Landing />);

    expect(screen.getByText('Continue to the app')).toBeTruthy();
    expect(screen.queryByText('Sign in')).toBeNull();
  });

  it('offers neither route while the stored token is still being checked', () => {
    signedIn('loading');

    render(<Landing />);

    expect(screen.queryByText('Sign in')).toBeNull();
    expect(screen.queryByText('Continue to the app')).toBeNull();
  });
});
