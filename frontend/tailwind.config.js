/** Design tokens: a lab-bench palette. Amber is reserved for "potential anomaly",
 *  plum is reserved for DEMO / MOCK labelling, so those meanings never blur. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bench: "#EDF0F2",
        panel: "#FAFBFC",
        ink: { DEFAULT: "#14222D", soft: "#4A5B68", faint: "#7C8B97" },
        rule: "#CBD3DA",
        lens: { DEFAULT: "#0B5C7A", deep: "#083F55", wash: "#DCEBF1" },
        signal: { DEFAULT: "#B05F00", wash: "#F8E9D2" },
        demo: { DEFAULT: "#7A2A62", wash: "#F1DDEA" },
        ok: "#2F6B3F",
      },
      fontFamily: {
        display: ['"Newsreader Variable"', "Georgia", "serif"],
        sans: ['"Public Sans Variable"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
