# Skillowkey

A curated, searchable library of ready-to-use agent skills. Organized by category and topic, each skill linked to its source. Standalone project - not affiliated with any other service.

- **5,438 skills** collected from **249 source repos**
- **11 categories** (Data & AI, Security, Finance, Marketing, Coding, Legal, Design, Writing, Music, Ops, General)
- **Keyword tags** on every skill for fast filtering
- Every skill links back to its **origin repo**
- Pure static single-file site - deploy free on Cloudflare Pages, Vercel, Netlify, or GitHub Pages

## Deploy

**Cloudflare Pages (free, unlimited bandwidth):**
1. Connect this repo to Cloudflare Pages
2. Framework preset: **None** (static site, no build command)
3. Publish directory: `/` (root)
4. Deploy, then attach your domain under **Custom domains**

## Files
- `index.html` - the full site + embedded skill data (self-contained, works offline)
- `data/skills.json` - the raw library: `[name, description, category, origin, source_url, tags]`
- `robots.txt` - SEO
- `vercel.json` - static config

## Data model
Each entry: `[name, description, category, origin_repo, source_url, [tags]]`

Built for makers. Curated, not scraped.