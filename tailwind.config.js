/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./shared/templates/**/*.html",
    "./apps/doctor/templates/**/*.html",
    "./apps/patient/templates/**/*.html",
    "./apps/pharmacy/templates/**/*.html",
    "./apps/lab/templates/**/*.html",
    "./apps/delivery/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        clinic: {
          50: "#f4faf6",
          100: "#deefe3",
          200: "#b6dcc0",
          300: "#86c297",
          400: "#58a66f",
          500: "#377d51",
          600: "#245f3d",
          700: "#1b4a31",
          800: "#163a28",
          900: "#10271c",
        },
        saffron: {
          100: "#fff1d4",
          300: "#f8c96f",
          500: "#d89a1d",
          700: "#9d6510",
        },
        cream: "#f8f4ea",
        critical: "#b91c1c",
      },
      fontFamily: {
        sans: ["Inter", "Plus Jakarta Sans", "Noto Sans Devanagari", "system-ui", "sans-serif"],
        display: ["Plus Jakarta Sans", "Inter", "Noto Sans Devanagari", "sans-serif"],
      },
      boxShadow: {
        clinical: "0 20px 50px rgba(16, 39, 28, 0.10)",
        float: "0 28px 80px rgba(15, 23, 42, 0.14)",
      },
      borderRadius: {
        shell: "28px",
      },
    },
  },
  plugins: [],
};
