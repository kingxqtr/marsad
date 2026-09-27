# Hourly update for the "المرصد" (Marsad) news site — cloud routine

You maintain a bilingual (Arabic + English) news website for one reader in Qatar. It has three tabs: Once Human (video game), Star Citizen / Squadron 42 (video game), and AI tools. Each tab shows the next 6 upcoming events and the last 3 months of news, newest first. This task runs every hour in the cloud, in a checkout of this repository. The first run of each day does full research; the other runs are quick updates from the official feeds. Every run ends by rebuilding the data and pushing to GitHub, which republishes the public site https://kingxqtr.github.io/marsad/.

Work from the repository root. Only add or edit files under data/research/daily/, data/news.json, data/first-seen.json, data/last-full-run.txt and www/data/news-data.js (the last three are written by the build script). Never edit code (www/assets, www/index.html, server/, scripts/, .github/) or the original files in data/research/*.json. Never touch www/data/live.json (the GitHub workflow owns it).

## Which kind of run is this?
Run `TZ=Asia/Qatar date +%F` for today's date (the reader is in Qatar) and read data/last-full-run.txt (it may not exist).
- Missing, or it holds a date other than today → FULL run: do A, then C, and write today's date (just YYYY-MM-DD) to data/last-full-run.txt before committing.
- It holds today's date → QUICK run: do B, then C. A quick run should take only a few minutes; don't do open-ended web searching.

## Rules (both kinds of run)
- Sources must be OFFICIAL (the developer's or company's own site, blog, newsroom, changelog, Steam page, official forum or social account, or a government page) or COMMUNITY (subreddits, community wikis/forums/Discords, Hacker News). Never cite mainstream media (IGN, PC Gamer, The Verge, TechCrunch, Reuters, Bloomberg and similar); use them only to discover stories, then cite the official or community source. Skip a story if it has no official or community source.
- Every item must be real and verified against its source, including the publication date. If a site blocks fetching, confirm through search results or another official page. Never invent facts, numbers or dates.
- No duplicates: skip anything already in data/news.json, even from a different URL.
- Quality over quantity. importance 3 = major headline, 2 = notable, 1 = minor.

## Writing
Every item has "ar" (clear Modern Standard Arabic news style; keep game, product, model and company names in Latin script) and "en" (plain English) with the same facts:
- title: at most 90 characters, no trailing period
- summary: 1–2 sentences, at most 240 characters
- details: 400–1,200 characters in 2–5 short paragraphs separated by a blank line (shorter is fine if the source is short); lines starting with "- " become bullet points
Write in your own words; never copy sentences from sources.

## Update file format
Write data/research/daily/<today>-<tab>.json (tab = once-human, star-citizen or ai), UTF-8. If today's file for that tab already exists, read it and add to it; never drop what earlier runs wrote.
{
  "topic": "<tab>",
  "generatedAt": "<today>",
  "news": [{"id", "date", "type", "importance", "sourceType", "sourceName", "url", "originalTitle", "company" and "tool" (AI tab only), "ar": {"title", "summary", "details"}, "en": {...}}],
  "upcoming": [{"id", "date", "endDate" (or null), "dateConfidence": "confirmed" or "expected", "type", "sourceType", "sourceName", "url", "company"/"tool" (AI only), "ar": {"title", "summary", "details", "location", "dateNote"}, "en": {...}}],
  "removeUpcoming": ["ids of existing upcoming items that were cancelled"],
  "removeNews": []
}
- ids are unique kebab-case. To correct an existing item, reuse its exact id with the full corrected item; it replaces the old one.
- Types. once-human: update, scenario, event, collab, platform, announcement, community. star-citizen: patch, event, ship, squadron42, development, community. ai: model, product, coding, media, business, policy, hardware. Upcoming items may also use "event" or "release".
- For an "expected" date, give a best estimate and explain it in dateNote in both languages.
- Validate each file: python3 -m json.tool <file> > /dev/null

## A. FULL run: research
1. Read data/news.json. Note `coverage.to` (the last day already covered) and, for each tab, the ids, urls and English titles of the existing news and upcoming items.
2. Optional leads: `MARSAD_TRANSLATE=0 python3 server/refresh.py --out build/leads.json` pulls the newest items from the official and community feeds. Treat them only as leads.
3. For each tab, find real news published from coverage.to (inclusive) through today:
   - Once Human: patches and hotfixes, scenarios/seasons, in-game events, collaborations, platform news. Official: oncehuman.game, the Steam news for app 2139460, official X/YouTube.
   - Star Citizen and Squadron 42: Alpha/PTU/LIVE patches, ship releases, events, Squadron 42, roadmap and development. Official: robertsspaceindustries.com Comm-Links, RSI Spectrum, official YouTube.
   - AI tools: models, assistants, coding tools, creative tools (image/video/audio), agents and browsers, major funding/acquisitions, regulation, and notable AI news from the Gulf. Official company blogs, newsrooms and changelogs.
   Open each source with WebFetch to confirm the facts and date. If WebFetch is blocked for a site by this session's network proxy, confirm the facts and date through WebSearch results that show the official page, and use www/data/live.json (official feed items, refreshed every 10 minutes by GitHub) as extra leads.
4. Review each tab's upcoming events: add newly announced events or releases dated after today, confirm or correct dates, and remove events that were cancelled. Events whose dates have passed disappear on their own.
5. Write the update files.

## B. QUICK run: new items from the feeds
1. `MARSAD_TRANSLATE=0 python3 server/refresh.py --out build/leads.json` pulls the newest items from the official and community feeds and keeps only items newer than the site's data that aren't on it yet.
   If most feeds fail (for example "403 Forbidden" / EGRESS_BLOCKED from this session's network proxy), don't stop: read www/data/live.json instead. A GitHub workflow with full internet access refreshes that file from the same official feeds every 10 minutes (`git pull` first to get the newest copy). Its items carry the feed's title, summary, url, source and publish time, so they count as the official source text.
2. Read build/leads.json (or www/data/live.json). For each item, decide whether it is news for its tab: skip customer stories, marketing, and notes that add nothing; several small same-day bug-fix notes for Once Human can become one item. If the feed text is short, open the item's URL with WebFetch to read the official post.
3. Write the new items into today's update files (see the format above). If nothing is new, go straight to C.

## C. Rebuild and publish (every run)
1. `python3 scripts/build_data.py` moves the 3-month window to today and prints the counts. Fix any warning it reports about your files.
2. Commit and push:
   ```
   git add data www/data/news-data.js
   git commit -m "Marsad update <today> <HH:MM> UTC" || true
   git fetch origin main && git rebase origin/main
   git push origin HEAD:main
   ```
   If pushing to main is refused (permissions), push the same commit to a new branch named `claude/marsad-<YYYYMMDD-HHMM>` instead; the GitHub workflow merges `claude/**` branches into main and republishes the site automatically. Commit even when only the build script changed files, so "last updated" on the site stays current.
3. The GitHub Pages site redeploys on its own within a couple of minutes; there is nothing else to publish.

## Report
Finish with a short summary in Arabic: the kind of run (كامل or سريع), how many news and upcoming items were added or changed in each tab, the most important headlines, whether the push succeeded (and to which branch), and anything you could not verify.
