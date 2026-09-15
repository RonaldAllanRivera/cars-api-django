import { render, screen } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { ActivityIndicator, Text } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import AppLayout from '../_layout';

jest.mock('@/auth/AuthContext', () => ({ useAuth: jest.fn() }));

// `Tabs` needs a navigator context this test deliberately does not build:
// what is under test is the guard in front of it, not react-navigation. The
// stand-ins render each tab's title, so the authenticated case can still show
// that all four tabs were handed over, and invoke each tab's `tabBarIcon` so
// the icons can be counted.
//
// Function declarations, `Mock`-prefixed: jest lifts the factory above the
// imports, so it runs while `../_layout` is still resolving expo-router.
// Only hoisted bindings exist by then, and jest only lets a factory reach an
// out-of-scope name that starts with `mock` (case-insensitive). Building the
// elements inside the factory instead is what does not work - Nativewind's
// Babel transform rewrites them through an out-of-scope import.
function MockTabs({ children }: { children?: ReactNode }) {
  return <>{children}</>;
}

interface MockScreenOptions {
  title?: string;
  tabBarIcon?: (props: { color: string; focused: boolean; size: number }) => ReactNode;
}

function MockTabsScreen({ options }: { options?: MockScreenOptions }) {
  return (
    <>
      <Text>{options?.title ?? ''}</Text>
      {options?.tabBarIcon?.({ color: '#ffffff', focused: false, size: 24 })}
    </>
  );
}

MockTabs.Screen = MockTabsScreen;

function MockRedirect({ href }: { href: string }) {
  return <Text>{`redirect:${href}`}</Text>;
}

jest.mock('expo-router', () => ({ Tabs: MockTabs, Redirect: MockRedirect }));

const mockUseAuth = jest.mocked(useAuth);

const signedIn = (status: 'loading' | 'authenticated' | 'anonymous') => {
  mockUseAuth.mockReturnValue({ status, user: null, signIn: jest.fn(), signOut: jest.fn() });
};

describe('<AppLayout />', () => {
  it('sends an anonymous visitor to the login screen', () => {
    // This layout is the only thing between an anonymous visitor and every
    // authenticated screen behind it.
    signedIn('anonymous');

    render(<AppLayout />);

    expect(screen.getByText('redirect:/login')).toBeTruthy();
    expect(screen.queryByText('Search')).toBeNull();
  });

  it('waits rather than redirecting while the stored token is being checked', () => {
    // Redirecting on 'loading' would bounce a returning user who holds a
    // perfectly good token out to /login before the token is even read.
    signedIn('loading');

    render(<AppLayout />);

    expect(screen.UNSAFE_getByType(ActivityIndicator)).toBeTruthy();
    expect(screen.queryByText('redirect:/login')).toBeNull();
    expect(screen.queryByText('Search')).toBeNull();
  });

  it('renders the tabs once the session is confirmed', () => {
    signedIn('authenticated');

    render(<AppLayout />);

    expect(screen.queryByText('redirect:/login')).toBeNull();
    for (const tab of ['Search', 'Library', 'Pipeline', 'Review', 'Health']) {
      expect(screen.getByText(tab)).toBeTruthy();
    }
  });

  it('gives every tab an icon', () => {
    // The live build shipped placeholder glyphs because Tabs.Screen carried
    // only a title. A tab bar of four unlabelled triangles is the first thing
    // a visitor sees after signing in.
    signedIn('authenticated');

    render(<AppLayout />);

    expect(screen.getAllByTestId('tab-icon')).toHaveLength(5);
  });
});
