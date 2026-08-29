/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#05101F',
          900: '#0B1D3A',
          800: '#112347',
          700: '#1A3360',
          600: '#1E3A6E',
        },
        gold: {
          300: '#E8CC6A',
          400: '#D4B53A',
          500: '#C5A028',
          600: '#A88420',
        },
        ksp: {
          red: '#C0392B',
          green: '#0F7A5A',
          amber: '#E67E22',
        }
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', '"Courier New"', 'monospace'],
      },
      animation: {
        'pulse-gold': 'pulseGold 2s ease-in-out infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'bounce-dot': 'bounceDot 1.4s ease-in-out infinite',
      },
      keyframes: {
        pulseGold: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(197,160,40,0.4)' },
          '50%': { boxShadow: '0 0 0 10px rgba(197,160,40,0)' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        bounceDot: {
          '0%,80%,100%': { transform: 'scale(0)' },
          '40%': { transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
}
