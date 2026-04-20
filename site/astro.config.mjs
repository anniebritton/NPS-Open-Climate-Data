// @ts-check
import { defineConfig } from "astro/config";

// GitHub Pages deploys to https://<user>.github.io/<repo>/ by default.
// Override via SITE_BASE env when deploying to a custom domain.
const base = process.env.SITE_BASE ?? "/NPS-Open-Climate-Data";
const site = process.env.SITE_URL ?? "https://anniebritton.github.io";

export default defineConfig({
  site,
  base,
  trailingSlash: "ignore",
  build: {
    assets: "_astro",
  },
});
