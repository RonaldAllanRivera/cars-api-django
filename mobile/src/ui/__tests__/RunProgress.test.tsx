import { render, screen } from '@testing-library/react-native';

import { RunProgress } from '../RunProgress';

const base = {
  status: 'running' as const,
  processed: 10,
  failed: 2,
  total: 58,
  secondsRemaining: 92,
  blocked: null,
  onPause: jest.fn(),
  onResume: jest.fn(),
};

describe('<RunProgress />', () => {
  it('shows progress against the total', () => {
    render(<RunProgress {...base} />);

    expect(screen.getByText(/12 of 58/)).toBeTruthy();
  });

  it('counts failures separately rather than hiding them in the total', () => {
    render(<RunProgress {...base} />);

    expect(screen.getByText(/2 failed/)).toBeTruthy();
  });

  it('warns that leaving the app stops the run', () => {
    // The single most surprising thing about the feature: backgrounding an
    // Expo app suspends JS timers, so the run does not slow down - it stops.
    render(<RunProgress {...base} />);

    expect(screen.getByText(/keep this screen open/i)).toBeTruthy();
  });

  it('says pause takes effect between batches', () => {
    // The server cannot be interrupted; a chunk already running will finish.
    render(<RunProgress {...base} />);

    expect(screen.getByText(/finishes the current batch/i)).toBeTruthy();
  });

  it('shows the retry window when blocked', () => {
    render(
      <RunProgress {...base} status="blocked" blocked={{ status: 429, retry_after_seconds: 600 }} />,
    );

    expect(screen.getByText(/wikimedia/i)).toBeTruthy();
    expect(screen.getByText(/10m/)).toBeTruthy();
  });

  it('says a block is resumable', () => {
    // Matching the panel's callout: wait for the window, then run again to
    // pick up where this left off.
    render(
      <RunProgress {...base} status="blocked" blocked={{ status: 429, retry_after_seconds: 600 }} />,
    );

    expect(screen.getByText(/pick up where/i)).toBeTruthy();
  });

  it('copes with a block that carries no retry window', () => {
    // Wikimedia does not always send Retry-After.
    render(
      <RunProgress {...base} status="blocked" blocked={{ status: 403, retry_after_seconds: null }} />,
    );

    expect(screen.getByText(/wikimedia/i)).toBeTruthy();
  });

  it('offers pause while running and resume while paused', () => {
    const { rerender } = render(<RunProgress {...base} />);
    expect(screen.getByLabelText('Pause')).toBeTruthy();

    rerender(<RunProgress {...base} status="paused" />);
    expect(screen.getByLabelText('Resume')).toBeTruthy();
  });

  it('renders nothing when idle', () => {
    render(<RunProgress {...base} status="idle" />);

    expect(screen.queryByText(/of 58/)).toBeNull();
  });
});
