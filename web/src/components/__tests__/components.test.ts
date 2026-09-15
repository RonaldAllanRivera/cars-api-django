import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { nextTick, reactive } from 'vue';

import type { BulkRun } from '@/api/composables/useBulkRun';

import ChipGroup from '../ChipGroup.vue';
import CoveragePanel from '../CoveragePanel.vue';
import ExportPanel from '../ExportPanel.vue';
import RunProgress from '../RunProgress.vue';
import StatusBadge from '../StatusBadge.vue';
import VerdictBadge from '../VerdictBadge.vue';

const coverage = { total: 10, searched: 6, not_run: 4, failed: 1, with_images: 5, no_images: 1 };

describe('ExportPanel', () => {
  it('offers both formats under the ZIP cap', () => {
    const wrapper = mount(ExportPanel, { props: { count: 40, pending: null, zipCap: 100 } });
    const [csv, zip] = wrapper.findAll('button');

    expect(wrapper.text()).toContain('40 images match');
    expect(csv?.attributes('disabled')).toBeUndefined();
    expect(zip?.attributes('disabled')).toBeUndefined();
  });

  it('disables the ZIP over the cap and says why, leaving the CSV', async () => {
    const wrapper = mount(ExportPanel, { props: { count: 101, pending: null, zipCap: 100 } });
    const [csv, zip] = wrapper.findAll('button');

    expect(zip?.attributes('disabled')).toBeDefined();
    expect(wrapper.text()).toContain('A ZIP holds at most 100 images');

    await csv?.trigger('click');
    expect(wrapper.emitted('export')).toEqual([['csv']]);
  });

  it('offers nothing to export for zero matches', () => {
    const wrapper = mount(ExportPanel, { props: { count: 0, pending: null } });

    expect(wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined)).toBe(true);
  });
});

describe('CoveragePanel', () => {
  it('makes only the three filterable counts buttons, and toggles them', async () => {
    const wrapper = mount(CoveragePanel, { props: { coverage, selected: null } });
    const buttons = wrapper.findAll('button');

    expect(buttons).toHaveLength(3);
    await buttons[0]?.trigger('click');
    expect(wrapper.emitted('select')?.[0]).toEqual(['not_run']);

    await wrapper.setProps({ selected: 'not_run' });
    expect(wrapper.findAll('button')[0]?.attributes('aria-pressed')).toBe('true');
    await wrapper.findAll('button')[0]?.trigger('click');
    expect(wrapper.emitted('select')?.[1]).toEqual([null]);
  });
});

function runState(over: Partial<Record<keyof BulkRun, unknown>> = {}) {
  return reactive({
    status: 'running',
    processed: 3,
    failed: 1,
    total: 10,
    remaining: 6,
    done: 4,
    percent: 40,
    secondsRemaining: 90,
    feed: [{ key: '0', id: 1, make: 'Honda', model: 'Civic', from_year: 1998, outcome: 'completed' }],
    blocked: null,
    blockedAt: null,
    lastError: null,
    start: () => {},
    pause: () => {},
    resume: () => {},
    ...over,
  }) as never;
}

describe('RunProgress', () => {
  it('renders nothing before a run starts', () => {
    const wrapper = mount(RunProgress, { props: { run: runState({ status: 'idle' }) } });

    expect(wrapper.find('section').exists()).toBe(false);
  });

  it('exposes progress to assistive tech and announces it politely', () => {
    const wrapper = mount(RunProgress, { props: { run: runState() } });
    const bar = wrapper.get('[role="progressbar"]');

    expect(bar.attributes('aria-valuenow')).toBe('40');
    expect(bar.attributes('aria-valuetext')).toBe('4 of 10 queries');
    expect(wrapper.get('[aria-live="polite"]').text()).toBe('Running. 4 of 10 queries done.');
    expect(wrapper.text()).toContain('about 1m 30s left');
    expect(wrapper.text()).toContain('Honda Civic');
  });

  it('holds Resume until a blocked window has passed', async () => {
    const wrapper = mount(RunProgress, {
      props: {
        run: runState({ status: 'blocked', blocked: { status: 429, retry_after_seconds: 120 }, blockedAt: Date.now() }),
      },
    });
    await nextTick();

    const resume = wrapper.findAll('button').find((button) => button.text().startsWith('Resume'));
    expect(resume?.text()).toMatch(/Resume in 2m 0s|Resume in 1m 59s/);
    expect(resume?.attributes('disabled')).toBeDefined();
    expect(wrapper.text()).toContain('rate-limiting this server (HTTP 429)');
  });
});

describe('badges', () => {
  it('reads a status in sentence case', () => {
    expect(mount(StatusBadge, { props: { status: 'not_downloaded' } }).text()).toBe('Not downloaded');
  });

  it('keeps an unknown verdict distinct from a failed one', () => {
    expect(mount(VerdictBadge, { props: { kind: 'make', value: null } }).text()).toContain('unknown');
    expect(mount(VerdictBadge, { props: { kind: 'year', value: false } }).text()).toContain('does not match');
  });
});

describe('ChipGroup', () => {
  it('is a radio group under the chips', async () => {
    const wrapper = mount(ChipGroup, {
      props: {
        label: 'Status',
        modelValue: 'all',
        'onUpdate:modelValue': (value: string) => wrapper.setProps({ modelValue: value }),
        options: [
          { value: 'all', label: 'All' },
          { value: 'failed', label: 'Failed' },
        ],
      },
    });

    await wrapper.findAll('input[type="radio"]')[1]?.setValue();

    expect(wrapper.props('modelValue')).toBe('failed');
    expect(wrapper.get('legend').text()).toBe('Status');
  });
});

describe('LoadMore', () => {
  it('fetches the next page when it scrolls into view, and from its button', async () => {
    const LoadMore = (await import('../LoadMore.vue')).default;
    let trigger!: (entries: { isIntersecting: boolean }[]) => void;
    class FakeObserver {
      constructor(callback: typeof trigger) {
        trigger = callback;
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal('IntersectionObserver', FakeObserver);
    const fetchNextPage = vi.fn();

    const wrapper = mount(LoadMore, { props: { hasNextPage: true, isFetchingNextPage: false, fetchNextPage } });
    await nextTick();

    trigger([{ isIntersecting: true }]);
    expect(fetchNextPage).toHaveBeenCalledTimes(1);

    await wrapper.get('button').trigger('click');
    expect(fetchNextPage).toHaveBeenCalledTimes(2);

    await wrapper.setProps({ isFetchingNextPage: true });
    trigger([{ isIntersecting: true }]);
    expect(fetchNextPage).toHaveBeenCalledTimes(2);
  });
});
