import { render, screen } from '@testing-library/react-native';

import { Skeleton, SkeletonGrid } from '../Skeleton';

describe('<Skeleton />', () => {
  it('is hidden from assistive tech', () => {
    // A screen reader announcing six empty boxes while a grid loads is worse
    // than silence; the grid's own progressbar role is what should be read.
    //
    // Asserted through the query rather than by reading the prop: RNTL's
    // default `includeHiddenElements: false` applies the same visibility rules
    // a screen reader would, so a block this query cannot see is a block the
    // reader will not announce. Checking `accessibilityElementsHidden` instead
    // would pass even if the prop stopped having that effect.
    render(<Skeleton height={40} />);

    expect(screen.queryByTestId('skeleton')).toBeNull();
    expect(screen.getByTestId('skeleton', { includeHiddenElements: true })).toBeTruthy();
  });

  it('renders one block per requested item', () => {
    render(<SkeletonGrid count={6} />);

    expect(screen.getAllByTestId('skeleton', { includeHiddenElements: true })).toHaveLength(6);
  });

  it('announces that content is loading', () => {
    render(<SkeletonGrid count={6} />);

    expect(screen.getByLabelText('Loading')).toBeTruthy();
  });
});
