/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          light: '#FFFFFF',
          DEFAULT: '#FBF9F5',
          warm: '#F5F2EB',
          border: '#E7E2D8',
          subtle: '#EFECE6',
        },
        ink: {
          DEFAULT: '#141413',
          muted: '#57534E',
          faint: '#A8A29E',
        },
        signal: {
          50: '#FFF7ED',
          100: '#FFEDD5',
          200: '#FED7AA',
          500: '#F97316',
          DEFAULT: '#EA580C',
          dark: '#C2410C',
        },
        stone: {
          charcoal: '#292524',
          slate: '#44403C',
          muted: '#78716C',
        }
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        serif: ['"Newsreader"', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(28, 25, 23, 0.05), 0 1px 2px -1px rgba(28, 25, 23, 0.05)',
        elevated: '0 4px 6px -1px rgba(28, 25, 23, 0.08), 0 2px 4px -2px rgba(28, 25, 23, 0.08)',
      }
    },
  },
  plugins: [],
}
