/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"DM Sans"',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
        display: [
          '"Fraunces"',
          'Georgia',
          'Cambria',
          'serif',
        ],
      },
      colors: {
        ink: {
          DEFAULT: '#1d3029',
          muted: '#6e766e',
          subtle: '#9da39b',
        },
        forest: {
          DEFAULT: '#173c32',
          hover: '#1e4a3e',
          dark: '#0f2922',
          soft: '#e8f0ea',
        },
        paper: {
          DEFAULT: '#f7f3eb',
          deep: '#eee8dc',
          surface: '#fffdf8',
        },
        line: {
          DEFAULT: '#dedfd5',
          dark: '#c9cac0',
        },
        coral: {
          DEFAULT: '#d96552',
          hover: '#c35542',
          soft: '#f9e6df',
        },
        sage: {
          DEFAULT: '#8da78f',
          soft: '#e4eee5',
        },
        lilac: {
          DEFAULT: '#a69bc4',
          soft: '#eeeaf5',
        },
      },
      boxShadow: {
        'warm-sm': '0 2px 8px rgba(29, 48, 41, 0.05)',
        'warm-md': '0 10px 24px rgba(29, 48, 41, 0.07)',
        'warm-lg': '0 18px 36px rgba(29, 48, 41, 0.10)',
      },
    },
  },
  plugins: [],
};
