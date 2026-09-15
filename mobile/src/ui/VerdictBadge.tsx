import { Text, View } from 'react-native';

/**
 * The relevance checker's verdict, shown read-only beside the human's.
 *
 * Never writable. `make_confirmed` and `year_confirmed` are written in exactly
 * one place server-side (CarImageSearchService, via MakeRelevanceChecker), and
 * human review lives in `review_status` precisely so the machine-versus-human
 * comparison stays answerable. A client that could write these would destroy
 * the only record of what the machine thought.
 */
type Verdict = 'matched' | 'not matched' | 'unknown';

/*
 * Two maps rather than one combined string, for the reason StatusBadge already
 * documents: the background belongs to the pill and the colour to the label,
 * and applying one combined class to both paints a second background behind
 * the text.
 */
const SHELL: Record<Verdict, string> = {
  matched: 'bg-success/15',
  'not matched': 'bg-danger/15',
  unknown: 'bg-surface-sunken',
};

const LABEL: Record<Verdict, string> = {
  matched: 'text-success-text',
  'not matched': 'text-danger-text',
  unknown: 'text-text-secondary',
};

export function VerdictBadge({ kind, value }: { kind: 'make' | 'year'; value: boolean | null }) {
  // null is not false: it means the checker never reached a conclusion.
  const verdict: Verdict = value === null ? 'unknown' : value ? 'matched' : 'not matched';

  return (
    <View className={`self-start rounded-pill px-2 py-0.5 ${SHELL[verdict]}`}>
      <Text className={`text-micro ${LABEL[verdict]}`}>{`${kind} ${verdict}`}</Text>
    </View>
  );
}
