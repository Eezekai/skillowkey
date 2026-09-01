# Skillowkey

The verified library of agent skills. Searchable, sourced, license-aware.

- **5,444 skill entries** indexed from 167 source repos
- **11 organized categories** (Data & AI, Security, Finance, Coding, Legal, Marketing, Design, and more)
- Every skill links back to its **origin repo** (no dead ends — provenance at a glance)
- Every entry **SHA-256 hashed** for integrity
- Pure static site — deploy free on Cloudflare Pages / Vercel / Netlify / GitHub Pages

## Deploy

**Cloudflare Pages (recommended, free, unlimited bandwidth):**
1. Connect this repo to Cloudflare Pages
2. Framework preset: **None** (it's a static site — no build command)
3. Publish directory: `/` (root)
4. Deploy, then attach your domain under **Custom domains**

Or push to Vercel / Netlify and let them auto-detect the static site.

## Files
- `index.html` — the full site + embedded skill data (self-contained, works offline)
- `data/skills.json` — the raw library (name, description, category, origin repo, source URL)
- `robots.txt` — SEO
- `vercel.json` — static config

## Data model
Each entry: `[name, description, category, origin_repo, source_url]`

Built for makers. Verified, not scraped.