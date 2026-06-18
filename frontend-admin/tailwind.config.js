/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fef7ec',
          100: '#fdecd3',
          200: '#fad5a5',
          300: '#f7b86d',
          400: '#f39333',
          500: '#f07316',
          600: '#e1580c',
          700: '#bb400c',
          800: '#963312',
          900: '#792c12',
        },
        dark: {
          50: '#f6f6f7',
          100: '#e2e3e5',
          200: '#c5c6ca',
          300: '#a0a2a8',
          400: '#7b7d85',
          500: '#60636a',
          600: '#4c4e54',
          700: '#3f4145',
          800: '#35373a',
          900: '#1a1b1e',
          950: '#0d0e10',
        }
      }
    },
  },
  plugins: [],
}
