/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'ctfWithAi-orange': '#ff7300',
        'ctfWithAi-dark': '#0a0a0a',
      },
    },
  },
  plugins: [],
}
