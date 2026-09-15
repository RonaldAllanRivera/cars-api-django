import { reactive, readonly } from 'vue';

export type ToastTone = 'success' | 'error' | 'info';

export interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
  action?: { label: string; href: string };
}

const toasts = reactive<Toast[]>([]);
let nextId = 1;

export function dismissToast(id: number): void {
  const index = toasts.findIndex((toast) => toast.id === id);
  if (index !== -1) toasts.splice(index, 1);
}

export function showToast(
  message: string,
  tone: ToastTone = 'success',
  options: { action?: Toast['action']; duration?: number } = {},
): number {
  const id = nextId++;
  toasts.push({ id, tone, message, action: options.action });

  // Errors and toasts carrying a link stay longer: both need reading, and the
  // link needs time to be clicked.
  const duration = options.duration ?? (tone === 'error' || options.action ? 8000 : 4000);
  setTimeout(() => dismissToast(id), duration);

  // Three is enough to read; older ones make way.
  while (toasts.length > 3) toasts.shift();

  return id;
}

export function useToasts() {
  return { toasts: readonly(toasts), dismiss: dismissToast, show: showToast };
}

export function clearToastsForTests(): void {
  toasts.splice(0, toasts.length);
}
