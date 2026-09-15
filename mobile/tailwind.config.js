/** @type {import('tailwindcss').Config} */
// Required, not imported: this file is evaluated by Node during the Tailwind
// build, where the `@/` alias and TS syntax do not exist. src/theme/tokens.ts
// is plain data specifically so this line works.
const { color, fontSize, radius, space } = require('./src/theme/tokens');

module.exports = {
  content: ['./app/**/*.{js,jsx,ts,tsx}', './src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: color.surface,
          raised: color.surfaceRaised,
          sunken: color.surfaceSunken,
        },
        border: { DEFAULT: color.border, strong: color.borderStrong },
        text: { DEFAULT: color.text, secondary: color.textSecondary, muted: color.textMuted },
        accent: { DEFAULT: color.accent, text: color.accentText, fg: color.accentFg },
        success: { DEFAULT: color.success, text: color.successText },
        danger: { DEFAULT: color.danger, text: color.dangerText },
        info: { DEFAULT: color.info, text: color.infoText },
      },
      spacing: space,
      borderRadius: {
        control: `${radius.control}px`,
        surface: `${radius.surface}px`,
        pill: `${radius.pill}px`,
      },
      fontSize,
    },
  },
  plugins: [],
};
