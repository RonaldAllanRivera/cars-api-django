import { fireEvent, render, screen } from '@testing-library/react-native';

import { Button } from '../Button';

describe('<Button />', () => {
  it('renders its label and calls onPress', () => {
    const onPress = jest.fn();
    render(<Button label="Approve" onPress={onPress} />);

    fireEvent.press(screen.getByText('Approve'));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('swallows presses while pending', () => {
    // A double-tapped Approve would fire two mutations for one image. The
    // pending flag has to disable the press, not merely swap the label.
    const onPress = jest.fn();
    render(<Button label="Approve" onPress={onPress} pending />);

    fireEvent.press(screen.getByLabelText('Approve'));

    expect(onPress).not.toHaveBeenCalled();
  });

  it('keeps the label readable to assistive tech while pending', () => {
    render(<Button label="Approve" onPress={jest.fn()} pending />);

    // The visible label is replaced by a spinner, so the accessible name is
    // the only thing left naming the control.
    expect(screen.getByLabelText('Approve')).toBeTruthy();
  });

  it('marks a disabled button as disabled for assistive tech', () => {
    render(<Button label="Approve" onPress={jest.fn()} disabled />);

    expect(screen.getByLabelText('Approve').props.accessibilityState.disabled).toBe(true);
  });
});
