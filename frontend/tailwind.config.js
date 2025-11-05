/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#faf8f5',
          100: '#f5f1ea',
          200: '#e8dfd0',
          300: '#d4c5aa',
          400: '#bfa87d',
          500: '#a68a5e',
          600: '#8b6f47',
          700: '#6d563a',
          800: '#4a3a28',
          900: '#2d241a',
        },
        oldmoney: {
          cream: '#faf8f5',
          beige: '#e8dfd0',
          tan: '#d4c5aa',
          gold: '#bfa87d',
          brown: '#8b6f47',
          forest: '#3d5a4c',
          burgundy: '#6b2737',
          navy: '#1e3a5f',
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
