import { fireEvent, render, screen } from '@testing-library/react-native';

import { Field } from '../Field';

describe('<Field />', () => {
  it('keeps the label visible after the placeholder is gone', () => {
    // The whole point of the component: a placeholder-as-label vanishes on
    // the first keystroke and the user loses what the box was for.
    const { rerender } = render(
      <Field label="Make" value="" onChangeText={jest.fn()} placeholder="e.g. Toyota" />,
    );
    expect(screen.getByText('Make')).toBeTruthy();

    rerender(
      <Field label="Make" value="Toyota" onChangeText={jest.fn()} placeholder="e.g. Toyota" />,
    );

    expect(screen.getByText('Make')).toBeTruthy();
    expect(screen.queryByText('e.g. Toyota')).toBeNull();
  });

  it('reports changes', () => {
    const onChangeText = jest.fn();
    render(<Field label="Make" value="" onChangeText={onChangeText} />);

    fireEvent.changeText(screen.getByLabelText('Make'), 'Audi');

    expect(onChangeText).toHaveBeenCalledWith('Audi');
  });

  it('shows the error instead of the hint when both are given', () => {
    // Two lines of small print under one input is noise; the error is the one
    // that needs reading.
    render(
      <Field
        label="From year"
        value="18"
        onChangeText={jest.fn()}
        hint="Four digits"
        error="Enter a four-digit year."
      />,
    );

    expect(screen.getByText('Enter a four-digit year.')).toBeTruthy();
    expect(screen.queryByText('Four digits')).toBeNull();
  });
});
