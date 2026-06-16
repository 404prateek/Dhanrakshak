/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0B1120',
          800: '#0F172A',
          700: '#1E293B',
        },
        primary: {
          DEFAULT: '#1d4ed8',
          hover: '#1e40af',
          light: '#eff6ff',
        },
        surface: {
          DEFAULT: '#ffffff',
          alt: '#f8fafc',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
