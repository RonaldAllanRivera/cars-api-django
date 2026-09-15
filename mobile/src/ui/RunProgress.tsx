import { Text, View } from 'react-native';

import type { RunChunkResponse } from '@/api/schemas';
import type { RunStatus } from '@/api/hooks/useBulkRun';
import { Button } from './Button';

interface Props {
  status: RunStatus;
  processed: number;
  failed: number;
  total: number;
  secondsRemaining: number;
  blocked: RunChunkResponse['blocked'];
  onPause: () => void;
  onResume: () => void;
}

/** "10m 0s" rather than "600s": minutes are how a wait is actually judged. */
function humanSeconds(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;

  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

/**
 * Presentational. The run itself lives in useBulkRun, which is where the
 * behaviour worth testing is.
 */
export function RunProgress({
  status,
  processed,
  failed,
  total,
  secondsRemaining,
  blocked,
  onPause,
  onResume,
}: Props) {
  const done = processed + failed;
  const percent = total > 0 ? Math.round((100 * done) / total) : 0;

  if (status === 'idle') return null;

  const isBlocked = status === 'blocked';

  return (
    <View
      className={`mb-6 gap-3 rounded-surface border p-3 ${
        isBlocked ? 'border-danger/40 bg-danger/10' : 'border-border-strong bg-surface-raised'
      }`}
    >
      <View className="flex-row items-baseline justify-between">
        <Text className="text-section text-text">
          {done} of {total}
        </Text>
        {status === 'running' ? (
          <Text className="text-meta text-text-secondary">
            about {humanSeconds(secondsRemaining)} left
          </Text>
        ) : null}
      </View>

      {failed > 0 ? (
        <Text className="text-meta text-danger-text">
          {failed} failed — they stay runnable and are picked up next time
        </Text>
      ) : null}

      <View
        accessibilityRole="progressbar"
        accessibilityValue={{ min: 0, max: 100, now: percent }}
        className="h-1.5 overflow-hidden rounded-pill bg-surface-sunken"
      >
        {/* Not animated. The bar advances once per chunk - roughly every ten
            seconds - and easing a step that rare is decoration. The design
            spends its one motion moment on the review card's exit. */}
        <View
          style={{ width: `${percent}%` }}
          className={`h-full rounded-pill ${isBlocked ? 'bg-danger' : 'bg-accent'}`}
        />
      </View>

      {isBlocked ? (
        <Text className="text-meta text-danger-text">
          Wikimedia is rate-limiting this server (HTTP {blocked?.status}).
          {blocked?.retry_after_seconds
            ? ` Wait about ${humanSeconds(blocked.retry_after_seconds)},`
            : ' Wait a while,'}{' '}
          then run again to pick up where this left off.
        </Text>
      ) : (
        <>
          {/* Not buried in help text. An Expo app's JS timers are suspended
              when it is backgrounded, so the run does not slow down if the
              user switches away - it stops. */}
          <Text className="text-meta text-text-secondary">
            Keep this screen open — the run stops if you leave the app.
          </Text>

          <View className="flex-row items-center gap-3">
            {status === 'running' ? (
              <Button label="Pause" variant="secondary" onPress={onPause} />
            ) : (
              <Button label="Resume" variant="secondary" onPress={onResume} />
            )}
            <Text className="flex-1 text-micro text-text-muted">
              Pause finishes the current batch first.
            </Text>
          </View>
        </>
      )}
    </View>
  );
}
