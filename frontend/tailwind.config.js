/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                "primary": "#a61c2e",
                "background-light": "#f5f5f5",
                "background-dark": "#1a1a1a",
                "container-light": "#ffffff",
                "container-dark": "#2c2c2c",
            },
            fontFamily: {
                "display": ["Manrope", "sans-serif"],
            },
        },
    },
    plugins: [],
}
