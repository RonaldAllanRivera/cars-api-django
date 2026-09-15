import { fireEvent, render, screen } from '@testing-library/react-native';

import { ExportPanel } from '../ExportPanel';

const base = { count: 63, zipCap: 100, pending: null, onExport: jest.fn() };

describe('<ExportPanel />', () => {
  beforeEach(() => base.onExport.mockClear());

  it('states what it will export before anything is pressed', () => {
    render(<ExportPanel {...base} />);

    expect(screen.getByText(/63 images match/)).toBeTruthy();
  });

  it('exports in the chosen format', () => {
    render(<ExportPanel {...base} />);

    fireEvent.press(screen.getByLabelText('Export CSV'));
    expect(base.onExport).toHaveBeenCalledWith('csv');

    fireEvent.press(screen.getByLabelText('Export ZIP'));
    expect(base.onExport).toHaveBeenCalledWith('zip');
  });

  it('disables a ZIP over the cap and says why', () => {
    // Not left pressable so the server can say no - the reason belongs beside
    // the button before it is pressed.
    render(<ExportPanel {...base} count={140} />);

    expect(screen.getByLabelText('Export ZIP').props.accessibilityState.disabled).toBe(true);
    expect(screen.getByText(/limited to 100/)).toBeTruthy();
  });

  it('leaves the CSV available over the ZIP cap', () => {
    // The cap bounds Wikimedia fetches; a CSV fetches nothing.
    render(<ExportPanel {...base} count={140} />);

    expect(screen.getByLabelText('Export CSV').props.accessibilityState.disabled).toBe(false);
  });

  it('warns that a ZIP leaves the app for the browser', () => {
    render(<ExportPanel {...base} count={10} />);

    expect(screen.getByText(/browser/i)).toBeTruthy();
  });

  it('offers nothing to export when nothing matches', () => {
    render(<ExportPanel {...base} count={0} />);

    expect(screen.getByLabelText('Export CSV').props.accessibilityState.disabled).toBe(true);
    expect(screen.getByLabelText('Export ZIP').props.accessibilityState.disabled).toBe(true);
  });

  it('locks both while one export is being minted', () => {
    // A second tap would mint a second link - and for a ZIP, a second nonce and
    // a second hundred Wikimedia fetches.
    render(<ExportPanel {...base} pending="zip" />);

    fireEvent.press(screen.getByLabelText('Export CSV'));

    expect(base.onExport).not.toHaveBeenCalled();
  });

  it('renders nothing while the count is still unknown', () => {
    // A button reading "0 images match" before the count arrives would briefly
    // tell the user there is nothing to export.
    render(<ExportPanel {...base} count={undefined} />);

    expect(screen.queryByLabelText('Export CSV')).toBeNull();
  });
});
