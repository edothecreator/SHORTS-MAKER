# Shorts Engine Studio — Marketing Plan

This document covers Tasks 21.3–21.9 from PRODUCTION_TASKS.txt.

---

## Task 21.3: Blog Setup Plan

### Recommendation: Next.js MDX Blog (built into the existing app)

**Why MDX over Ghost/WordPress:**
- Zero additional infrastructure cost (deploys with the app on Vercel)
- Full design control using existing CSS variables and Tailwind
- SEO-optimized with Next.js static generation (SSG)
- Type-safe, version-controlled content in the same repo
- Code examples and interactive demos can be embedded directly

**Implementation Plan:**
1. Install `@next/mdx` and `gray-matter` packages
2. Create `frontend/app/blog/` route with layout
3. Create `content/blog/` directory for `.mdx` files
4. Add frontmatter schema: title, date, description, tags, author, image
5. Build blog index page with pagination (10 posts per page)
6. Add RSS feed at `/blog/feed.xml`
7. Add sitemap generation for all blog posts
8. Add Open Graph / Twitter Card meta tags per post
9. Add related posts section at bottom of each article

**Alternative (if content team scales):** Migrate to Ghost CMS with custom theme
matching the app's dark UI. Ghost offers better editorial workflow for non-technical
writers and built-in email newsletter integration.

---


## Task 21.4: Blog Post Titles & Outlines (5 Launch Posts)

### Post 1: "How to Turn Podcasts Into Viral Shorts in Under 5 Minutes"
- **Audience:** Podcasters, interview-based creators
- **Outline:**
  1. The problem: podcasts don't get discovered on social media
  2. Why short-form clips drive podcast growth (stats)
  3. Step-by-step walkthrough using Shorts Engine
  4. Tips for picking the best moments manually vs. AI selection
  5. Results: case study showing 10x listener growth from shorts
- **CTA:** Sign up free and try with your latest episode
- **SEO keywords:** podcast to shorts, podcast clips, repurpose podcast

### Post 2: "Best Subtitle Styles for TikTok in 2026 (with Examples)"
- **Audience:** TikTok creators, Reels creators
- **Outline:**
  1. Why subtitles increase watch time by 40%+ (cite studies)
  2. Top 10 trending subtitle styles this year (screenshots)
  3. Word-by-word highlight vs. full-sentence display
  4. Color psychology: which colors get more saves
  5. How to match subtitle style to content type
  6. How Shorts Engine makes it one-click
- **CTA:** Try all 20+ styles free
- **SEO keywords:** TikTok subtitles, best subtitle styles, caption styles 2026

### Post 3: "OpusClip vs Shorts Engine: Honest Comparison (2026)"
- **Audience:** Creators comparing tools, high purchase intent
- **Outline:**
  1. What both tools do (fair overview)
  2. Pricing comparison (table)
  3. Feature comparison: AI quality, subtitle styles, platforms
  4. Where Shorts Engine wins: virality scoring, multi-language, API
  5. Where OpusClip wins: (be honest — brand recognition)
  6. Who should use which tool
- **CTA:** Try Shorts Engine free and decide for yourself
- **SEO keywords:** OpusClip alternative, OpusClip vs, best AI shorts tool

### Post 4: "How to Repurpose YouTube Videos for Instagram Reels (Complete Guide)"
- **Audience:** YouTube creators wanting to cross-post
- **Outline:**
  1. Why every YouTuber needs a Reels strategy
  2. Instagram's algorithm: what works for Reels in 2026
  3. Aspect ratio and resolution requirements
  4. Finding the right moments to clip (hook-first content)
  5. Adding subtitles (80% of Reels watched on mute)
  6. Automated workflow: YouTube URL → Shorts Engine → Reels
  7. Scheduling and optimal posting times
- **CTA:** Paste your YouTube URL and get clips in minutes
- **SEO keywords:** YouTube to Reels, repurpose YouTube, Instagram Reels from YouTube

### Post 5: "The Science Behind Our Virality Score (and How to Get 90+)"
- **Audience:** Data-driven creators, marketers
- **Outline:**
  1. Why we built a virality predictor
  2. The 5 signals: hook strength, pacing, emotion, topic, completeness
  3. How each signal is measured (technical but accessible)
  4. Tips to improve each dimension
  5. Real examples: clips that scored 95+ and their performance
  6. How the score improves over time with feedback
- **CTA:** Upload a video and see your scores
- **SEO keywords:** viral video score, predict viral content, AI virality

---


## Task 21.5: Analytics Setup

### Recommendation: PostHog (self-hosted or cloud)

**Why PostHog over Plausible:**
- Free tier: 1M events/month (Plausible charges from day one)
- Product analytics: funnels, session recordings, feature flags
- Privacy-friendly: EU hosting option, cookieless tracking mode
- Open source: can self-host for zero cost if needed

**Implementation Plan:**
1. Create PostHog Cloud account (free tier)
2. Install `posthog-js` in frontend: `npm install posthog-js`
3. Initialize in `frontend/app/layout.tsx` with project API key
4. Key events to track:
   - `page_view` — all pages (automatic with SPA tracking)
   - `signup_started` — clicked signup button
   - `signup_completed` — account created
   - `video_uploaded` — source video uploaded
   - `render_started` — processing triggered
   - `render_completed` — clips ready
   - `clip_downloaded` — user downloaded a clip
   - `clip_published` — published to platform
   - `upgrade_clicked` — clicked upgrade/pricing CTA
   - `subscription_started` — paid subscription activated
5. Set up funnels:
   - Landing → Signup → Upload → Render → Download (conversion funnel)
   - Free user → Upgrade click → Checkout → Paid (monetization funnel)
6. Set up dashboards:
   - Daily active users, weekly retention
   - Videos processed per day
   - Revenue metrics (MRR, churn)
7. Enable session recordings (opt-in, with consent)
8. Add feature flags for A/B testing pricing page copy

**Alternative:** Plausible Analytics for a simpler, fully privacy-compliant
dashboard. Best if only pageview-level analytics are needed. ~$9/month for
10K pageviews.

---

## Task 21.6: Email Marketing Plan

### Recommendation: Resend (transactional) + Loops (marketing automation)

**Why this combo:**
- Resend: Developer-friendly, great deliverability, free tier (100 emails/day)
- Loops: Built for SaaS, visual automation builder, generous free tier
- Alternative: Use Resend for everything with custom automation logic

**Email Sequences:**

### Welcome Sequence (triggered on signup, 3 emails over 7 days)

**Email 1 — Immediately after signup:**
- Subject: "Welcome to Shorts Engine — here's how to get your first clips"
- Content: Quick-start guide, link to upload first video, highlight the 3-step process
- CTA: "Upload Your First Video"

**Email 2 — Day 3:**
- Subject: "5 tips to get higher virality scores"
- Content: Actionable tips (use hooks, keep pacing fast, emotional moments)
- CTA: "Try these tips on your next video"

**Email 3 — Day 7:**
- Subject: "You have 3 free videos this month — here's how to make them count"
- Content: Show what Pro unlocks, social proof (testimonial), limited urgency
- CTA: "Start your free Pro trial"

### Usage Tips (triggered monthly for active users)
- Best practices for each platform
- New feature announcements
- Community highlights / creator spotlights

### Upgrade Prompts (triggered by behavior)
- When user hits 80% of monthly limit: "You're almost at your limit"
- When user hits 100%: "Upgrade to keep creating"
- After successful render: "Love your clips? Go Pro for 1080p + no watermark"

### Re-engagement (triggered after 14 days inactive)
- Subject: "We miss you — your audience is waiting"
- Content: What's new since they left, one-click link back to dashboard

---


## Task 21.7: Demo Video Script Outline

### Video: "Shorts Engine in 60 Seconds" (for landing page & social)

**Duration:** 60 seconds
**Style:** Screen recording with voiceover, fast cuts, upbeat music

**Script:**

| Time | Visual | Voiceover |
|------|--------|-----------|
| 0-5s | Logo animation → app dashboard | "Turn any long video into viral shorts — in seconds." |
| 5-12s | Drag-and-drop a podcast video onto upload zone | "Just upload your video — or paste a YouTube URL." |
| 12-18s | Progress bar, AI analyzing | "Our AI watches the whole thing and finds the best moments." |
| 18-28s | Results grid appears: 6 clips with scores, thumbnails | "You get clips ranked by virality score — highest potential first." |
| 28-38s | Click a clip, preview plays with animated subtitles | "Each clip comes with trending subtitle styles, auto-applied." |
| 38-45s | Click style picker, switch between 3 styles | "Choose from 20+ styles. Word-by-word, neon glow, bounce — you name it." |
| 45-52s | Click "Publish" → platform picker (TikTok, Reels, YouTube) | "Publish directly to TikTok, Reels, and YouTube Shorts. One click." |
| 52-58s | Dashboard showing published clips with view counts | "Track performance across all platforms in one dashboard." |
| 58-60s | CTA screen: "Start Free at shortsengine.studio" | "Start free. No credit card. Link in bio." |

**Production Notes:**
- Record at 1440p, export at 1080p for sharpness
- Use real app with sample podcast video (get permission)
- Add subtle zoom animations on key UI elements
- Background music: upbeat lo-fi (royalty-free)
- Add captions to the demo video itself (meta!)

---

## Task 21.8: Social Media Accounts to Create

| Platform | Handle | Purpose |
|----------|--------|---------|
| Twitter/X | @ShortsEngine | Product updates, creator tips, engagement |
| TikTok | @shortsengine | Demo clips, before/after comparisons, tutorials |
| YouTube | Shorts Engine Studio | Long-form tutorials, weekly tips, case studies |
| Instagram | @shortsengine | Reels demos, carousel tips, stories |
| LinkedIn | Shorts Engine Studio | B2B content, agency case studies, hiring |
| Product Hunt | Shorts Engine Studio | Launch page, upcoming product |
| Discord | Shorts Engine Community | User community, support, feature requests |

**Content Strategy by Platform:**
- **Twitter/X:** 2-3 posts/day — tips, polls, creator spotlights, product updates
- **TikTok:** 1 video/day — "watch me turn this podcast into 6 viral clips" format
- **YouTube:** 2 videos/week — tutorials, comparisons, creator interviews
- **Instagram:** 1 Reel/day + 3 Stories/day — demos, carousel tips, UGC reposts
- **LinkedIn:** 2 posts/week — industry insights, case studies, team updates

---


## Task 21.9: Product Hunt Launch Checklist

### Pre-Launch (2-4 weeks before)

- [ ] Create Product Hunt maker profile with complete bio
- [ ] Build "Upcoming" page with email signup
- [ ] Collect 200+ email subscribers before launch day
- [ ] Prepare all visual assets:
  - [ ] Logo (240x240px)
  - [ ] Gallery images (5-8 screenshots, 1270x760px)
  - [ ] Product demo GIF (15-30 seconds)
  - [ ] Thumbnail/hero image
- [ ] Write product tagline (max 60 chars): "Turn any video into viral shorts with AI"
- [ ] Write product description (clear, benefit-focused, 300 words max)
- [ ] Prepare "first comment" from maker (story behind the product)
- [ ] Line up 5+ hunter candidates (ask if they'll hunt the product)
- [ ] Schedule launch date (Tuesday-Thursday, avoid holidays)
- [ ] Prepare team to be online 12:01 AM PT on launch day
- [ ] Draft social media posts for launch day
- [ ] Prepare email blast to subscriber list for launch morning

### Launch Day

- [ ] Product goes live at 12:01 AM PT
- [ ] Post maker's "first comment" immediately
- [ ] Send email to subscriber list: "We're live on Product Hunt!"
- [ ] Post on Twitter/X with Product Hunt link
- [ ] Post in relevant communities (Reddit, Discord, Slack groups)
- [ ] Respond to every comment within 30 minutes
- [ ] Share personal story on LinkedIn
- [ ] Update landing page with "Featured on Product Hunt" badge
- [ ] Monitor analytics for traffic spike
- [ ] Thank supporters throughout the day
- [ ] Post afternoon update with early stats/milestone

### Post-Launch (1 week after)

- [ ] Write "lessons learned" blog post
- [ ] Follow up with everyone who commented
- [ ] Add "Product Hunt" badge to landing page
- [ ] Analyze traffic sources and conversion rates
- [ ] Reach out to press/blogs that covered similar launches
- [ ] Plan next milestone announcement (1,000 users, etc.)
- [ ] Convert Product Hunt visitors: retargeting + email nurture

### Success Metrics
- **Top 5** in daily rankings (target: #1-3)
- **500+** upvotes on launch day
- **1,000+** new signups from PH traffic
- **50+** comments with engagement
- Conversion rate from PH visitors: target 15-20% signup rate

---

*Document created as part of Production Task 21. All marketing activities
should begin 2-4 weeks before the planned public launch date.*
