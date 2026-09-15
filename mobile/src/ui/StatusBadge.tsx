import { Text, View } from 'react-native';

interface Tone {
  bg: string;
  text: string;
}

const NEUTRAL: Tone = { bg: 'bg-surface-sunken', text: 'text-text-secondary' };
const GOOD: Tone = { bg: 'bg-success/15', text: 'text-success-text' };
const BUSY: Tone = { bg: 'bg-info/15', text: 'text-info-text' };
const BAD: Tone = { bg: 'bg-danger/15', text: 'text-danger-text' };

/**
 * Keyed by both review_status and download_status - they never collide.
 *
 * No status is ever amber. Amber is the primary-action colour, so a badge in
 * it would compete with every button on the screen and blur the line between
 * "this is what happened" and "this is what you can do".
 */
const TONE: Record<string, Tone> = {
  completed: GOOD,
  approved: GOOD,
  downloaded: GOOD,
  running: BUSY,
  downloading: BUSY,
  pending: NEUTRAL,
  not_downloaded: NEUTRAL,
  failed: BAD,
  rejected: BAD,
};

export function StatusBadge({ status }: { status: string }) {
  // The background belongs to the pill and the colour to the label; applying
  // one combined string to both paints a second background behind the text.
  const tone = TONE[status] ?? NEUTRAL;

  return (
    <View className={`self-start rounded-pill px-2 py-0.5 ${tone.bg}`}>
      <Text className={`text-micro ${tone.text}`}>{status.replace(/_/g, ' ')}</Text>
    </View>
  );
}
