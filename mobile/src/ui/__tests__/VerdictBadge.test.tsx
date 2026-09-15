import { render, screen } from '@testing-library/react-native';

import { VerdictBadge } from '../VerdictBadge';

describe('<VerdictBadge />', () => {
  it('reads true as a match', () => {
    render(<VerdictBadge kind="make" value={true} />);
    expect(screen.getByText('make matched')).toBeTruthy();
  });

  it('reads false as no match', () => {
    render(<VerdictBadge kind="make" value={false} />);
    expect(screen.getByText('make not matched')).toBeTruthy();
  });

  it('distinguishes unknown from not-matched', () => {
    // null is "the checker never ran", which is a different fact from "the
    // checker ran and said no". Collapsing them would misreport the machine.
    render(<VerdictBadge kind="year" value={null} />);
    expect(screen.getByText('year unknown')).toBeTruthy();
  });

  it('names the year kind', () => {
    render(<VerdictBadge kind="year" value={true} />);
    expect(screen.getByText('year matched')).toBeTruthy();
  });
});
