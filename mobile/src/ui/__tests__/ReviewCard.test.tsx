import { fireEvent, render, screen } from '@testing-library/react-native';

import type { Image as CarImage } from '@/api/schemas';
import { ReviewCard } from '../ReviewCard';

const image: CarImage = {
  id: 1,
  car_search_id: 2,
  make: 'Audi',
  model: 'A4 Avant quattro',
  year: 2001,
  color: null,
  title: 'File:2001 Audi RS4 B5 Avant - Flickr - The Car Spy (3).jpg',
  description: null,
  source_url: 'https://upload.wikimedia.org/a.jpg',
  thumbnail_url: null,
  width: 800,
  height: 600,
  license: 'CC BY 2.0',
  attribution: 'The Car Spy',
  make_confirmed: true,
  year_confirmed: null,
  review_status: 'pending',
  reviewed_by: null,
  reviewed_at: null,
  download_status: 'not_downloaded',
  created_at: '2026-09-01T00:00:00+00:00',
};

describe('<ReviewCard />', () => {
  it("shows the machine's verdict so the human can disagree with it", () => {
    // The reason review_status is a separate column is that the two verdicts
    // stay comparable. A reviewer who cannot see the machine's answer is not
    // comparing anything.
    render(<ReviewCard image={image} onApprove={jest.fn()} onReject={jest.fn()} />);

    expect(screen.getByText('make matched')).toBeTruthy();
    expect(screen.getByText('year unknown')).toBeTruthy();
  });

  it('shows a cleaned title, never raw Commons syntax', () => {
    render(<ReviewCard image={image} onApprove={jest.fn()} onReject={jest.fn()} />);

    expect(screen.queryByText(/^File:/)).toBeNull();
    expect(screen.getByText('2001 Audi A4 Avant quattro')).toBeTruthy();
  });

  it('reports each verdict', () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    render(<ReviewCard image={image} onApprove={onApprove} onReject={onReject} />);

    fireEvent.press(screen.getByLabelText('Approve'));
    expect(onApprove).toHaveBeenCalledTimes(1);

    fireEvent.press(screen.getByLabelText('Reject'));
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it('locks both verdicts while one is in flight', () => {
    // A double tap must not fire two mutations for one image, and rejecting
    // an image whose approval is already in flight would race the cache.
    const onApprove = jest.fn();
    const onReject = jest.fn();
    render(
      <ReviewCard image={image} onApprove={onApprove} onReject={onReject} pending />,
    );

    fireEvent.press(screen.getByLabelText('Approve'));
    fireEvent.press(screen.getByLabelText('Reject'));

    expect(onApprove).not.toHaveBeenCalled();
    expect(onReject).not.toHaveBeenCalled();
  });
});
