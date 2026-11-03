/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // near-black surfaces
        ink: {
          950: '#07060d',
          900: '#0b0a14',
          850: '#100e1c',
          800: '#151327',
          700: '#1c1930',
          600: '#272443',
        },
        brand: {
          purple: '#8b5cf6',
          violet: '#a78bfa',
          indigo: '#6366f1',
          blue: '#3b82f6',
        },
        // four-accent system (purple/blue/green/orange) used across module cards + stats
        accent: {
          purple: '#8b5cf6',
          blue: '#3b82f6',
          green: '#22c55e',
          orange: '#f97316',
        },
        good: '#34d399',
        warn: '#fbbf24',
        bad: '#f87171',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(139,92,246,0.25), 0 8px 30px -10px rgba(99,102,241,0.45)',
        card: '0 10px 40px -20px rgba(0,0,0,0.8)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #3b82f6 100%)',
        'brand-soft': 'linear-gradient(135deg, rgba(139,92,246,0.18), rgba(59,130,246,0.1))',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.4s ease both',
      },
    },
  },
  plugins: [],
}
