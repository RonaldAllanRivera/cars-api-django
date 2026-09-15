import { beforeEach, describe, expect, it } from 'vitest';

import { setSessionForTests } from '@/auth/auth';
import { mockApi } from '@/test/http';
import { mountAt, waitFor } from '@/test/mount';

import image from '../../api/__fixtures__/image.json';
import me from '../../api/__fixtures__/me.json';

describe('image page', () => {
  beforeEach(() => setSessionForTests(me.data));

  it('shows the image with its badges, cleaned title, licence and source', async () => {
    mockApi({ 'GET /images/1': { body: image }, 'GET /images/count': { body: { count: 0 } } });
    const { wrapper } = await mountAt('/library/1');

    await waitFor(() => expect(wrapper.find('h1').text()).toBe('Toyota RAV4 1997'));
    const text = wrapper.text();
    expect(text).toContain('Toyota RAV4 1997 front');
    expect(text).not.toContain('File:');
    expect(text).toContain('CC BY-SA 4.0');
    expect(text).toContain('Photo by A. Person, CC BY-SA 4.0');
    expect(text).toContain('800 × 600 px');
    expect(text).toContain('Approved');
    expect(text).toContain('Downloaded');
    expect(wrapper.get('a[href="https://upload.wikimedia.org/fixture-a.jpg"]').attributes('rel')).toContain('noopener');
  });

  it('says so when the image cannot be loaded', async () => {
    mockApi({ 'GET /images/1': { status: 404, body: { message: 'Not found.' } }, 'GET /images/count': { body: { count: 0 } } });
    const { wrapper } = await mountAt('/library/1');

    await waitFor(() => expect(wrapper.get('[role="alert"]').text()).toContain('Not found.'));
  });
});
