/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'hackforge-orange': '#ff7300',
        'hackforge-dark': '#0a0a0a',
      },
    },
  },
  plugins: [],
}
