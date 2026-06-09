import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  define: {
    "__DEV__": true,
  },
  test: {
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/__tests__/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", ".expo"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      thresholds: {
        statements: 70,
        branches: 60,
        functions: 70,
        lines: 70,
      },
    },
    onConsoleLog: (log) => {
      if (log.includes("Flow is not supported")) return false;
      if (log.includes("Failed to check authentication status")) return false;
      return undefined;
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "react-native": path.resolve(__dirname, "node_modules/react-native-web/dist/cjs/index.js"),
    },
  },
  ssr: {
    noExternal: ["react-native"],
  },
});
