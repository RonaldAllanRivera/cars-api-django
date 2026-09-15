import { fireEvent, render, screen } from '@testing-library/react-native';

import { CoveragePanel } from '../CoveragePanel';

const coverage = {
  total: 58,
  searched: 35,
  not_run: 23,
  failed: 2,
  with_images: 30,
  no_images: 5,
};

describe('<CoveragePanel />', () => {
  it('shows what ran and found nothing separately from what never ran', () => {
    // The whole point of coverage: `status` cannot tell these apart, because
    // a search that ran and found nothing is `completed` exactly like one
    // that found five images.
    render(<CoveragePanel coverage={coverage} selected={null} onSelect={jest.fn()} />);

    expect(screen.getByLabelText(/23 not run/i)).toBeTruthy();
    expect(screen.getByLabelText(/5 ran and found nothing/i)).toBeTruthy();
  });

  it('reports which slice was tapped', () => {
    const onSelect = jest.fn();
    render(<CoveragePanel coverage={coverage} selected={null} onSelect={onSelect} />);

    fireEvent.press(screen.getByLabelText(/23 not run/i));

    expect(onSelect).toHaveBeenCalledWith('not_run');
  });

  it('clears the filter when the selected slice is tapped again', () => {
    // Otherwise the only way back to the full list is a back-and-forward, and
    // the chip looks stuck.
    const onSelect = jest.fn();
    render(<CoveragePanel coverage={coverage} selected="not_run" onSelect={onSelect} />);

    fireEvent.press(screen.getByLabelText(/23 not run/i));

    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it('renders nothing when there is no coverage', () => {
    // Null means the import has no searches. Six zeroes would read as a broken
    // import rather than an empty one.
    render(<CoveragePanel coverage={null} selected={null} onSelect={jest.fn()} />);

    expect(screen.queryByLabelText(/not run/i)).toBeNull();
  });

  it('does not offer a filter for slices that have no query', () => {
    // total, searched and failed have no coverage filter behind them, so a
    // tappable tile would promise a list the API cannot return.
    render(<CoveragePanel coverage={coverage} selected={null} onSelect={jest.fn()} />);

    expect(screen.getByLabelText(/58 queries/i).props.accessibilityRole).not.toBe('button');
  });
});
