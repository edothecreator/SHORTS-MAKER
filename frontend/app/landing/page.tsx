"use client";

import Link from "next/link";
import { useState } from "react";

/* ─── Icon Components ─── */
function IconUpload() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
    </svg>
  );
}

function IconAI() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
    </svg>
  );
}

function IconDownload() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}


function IconZap() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

function IconSubtitles() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function IconGlobe() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
    </svg>
  );
}


function IconCheck() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function IconX() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

/* ─── Data ─── */
const features = [
  { icon: <IconZap />, title: "AI-Powered Analysis", desc: "Gemini AI identifies the most engaging moments from your long-form video automatically." },
  { icon: <IconSubtitles />, title: "Stunning Subtitles", desc: "20+ animated subtitle styles with word-by-word highlighting, perfect for TikTok & Reels." },
  { icon: <IconChart />, title: "Virality Scoring", desc: "Each clip gets a 0-100 virality score so you know which shorts will perform best." },
  { icon: <IconGlobe />, title: "Multi-Language", desc: "Auto-detect and translate subtitles into 10+ languages with RTL support." },
];

const steps = [
  { icon: <IconUpload />, title: "Upload", desc: "Drop your long-form video or paste a YouTube URL" },
  { icon: <IconAI />, title: "AI Analyzes", desc: "Our AI finds the best moments, adds subtitles & scores virality" },
  { icon: <IconDownload />, title: "Download Shorts", desc: "Export ready-to-post vertical clips for any platform" },
];


const pricingTiers = [
  {
    name: "Free",
    price: "$0",
    period: "/month",
    desc: "Perfect for trying things out",
    features: ["3 videos/month", "720p output", "Watermark on exports", "Standard render queue", "5 subtitle styles"],
    missing: ["Priority rendering", "4K output", "API access", "Team features"],
    cta: "Get Started Free",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$15",
    period: "/month",
    desc: "For creators who post consistently",
    features: ["30 videos/month", "1080p output", "No watermark", "Priority rendering", "All 20+ subtitle styles", "Smart reframing", "Multi-platform publish"],
    missing: ["4K output", "API access", "Team features"],
    cta: "Start 7-Day Free Trial",
    highlighted: true,
  },
  {
    name: "Business",
    price: "$39",
    period: "/month",
    desc: "For agencies and teams",
    features: ["Unlimited videos", "4K output", "No watermark", "Priority rendering", "All subtitle styles", "Smart reframing", "Multi-platform publish", "API access", "Team collaboration", "Brand kit"],
    missing: [],
    cta: "Start 7-Day Free Trial",
    highlighted: false,
  },
];


const testimonials = [
  {
    name: "Sarah Chen",
    role: "YouTube Creator, 500K subs",
    avatar: "SC",
    text: "I used to spend 4 hours editing shorts from my podcasts. Now it takes 5 minutes. The AI picks better moments than I would have chosen myself.",
  },
  {
    name: "Marcus Johnson",
    role: "Social Media Manager",
    avatar: "MJ",
    text: "We manage 12 client accounts. Shorts Engine saved us 20+ hours per week. The virality scoring actually correlates with real engagement.",
  },
  {
    name: "Priya Patel",
    role: "Course Creator",
    avatar: "PP",
    text: "The subtitle styles are incredible — my shorts get 3x more saves since switching. The multi-language feature opened up a whole new audience for me.",
  },
];

const faqs = [
  {
    q: "How long can my source video be?",
    a: "Free users can upload videos up to 60 minutes. Pro and Business users can upload up to 180 minutes (3 hours). We support most video formats including MP4, MOV, AVI, and MKV.",
  },
  {
    q: "How does the AI decide which moments to clip?",
    a: "Our AI (powered by Gemini) analyzes your video's transcript for engaging hooks, emotional peaks, complete story arcs, and optimal pacing. Each clip is scored for virality potential so you can prioritize the best content.",
  },
  {
    q: "Can I edit the clips after they're generated?",
    a: "Yes! You can adjust subtitle timing, edit transcript text, change subtitle styles, modify crop positions, and re-render with different settings. You have full control over the final output.",
  },
  {
    q: "What platforms can I publish to directly?",
    a: "You can connect TikTok, YouTube Shorts, Instagram Reels, and LinkedIn. One-click publishing and scheduling are available on Pro and Business plans.",
  },
  {
    q: "Is there a free trial for paid plans?",
    a: "Yes! Both Pro and Business plans come with a 7-day free trial — no credit card required. You'll get full access to all features during the trial period.",
  },
];


/* ─── Main Component ─── */
export default function LandingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg)", color: "var(--text)" }}>
      {/* ─── Hero Section ─── */}
      <section className="relative overflow-hidden pt-20 pb-32 px-4">
        <div className="absolute inset-0 opacity-30" style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(108,99,255,0.3) 0%, transparent 70%)" }} />
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-block px-4 py-1.5 rounded-full text-sm font-medium mb-6" style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--accent)" }}>
            Trusted by 10,000+ creators
          </div>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold leading-tight mb-6">
            Turn Long Videos Into
            <span className="block" style={{ color: "var(--accent)" }}>Viral Shorts in Seconds</span>
          </h1>
          <p className="text-lg sm:text-xl max-w-2xl mx-auto mb-10" style={{ color: "var(--muted)" }}>
            Upload any video. Our AI finds the best moments, adds trending subtitles, and exports ready-to-post vertical clips for TikTok, Reels & Shorts.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Link href="/auth/signup" className="px-8 py-4 rounded-lg text-lg font-semibold text-white transition-colors" style={{ background: "var(--accent)" }}>
              Start Creating Free →
            </Link>
            <Link href="#how-it-works" className="px-8 py-4 rounded-lg text-lg font-semibold transition-colors" style={{ border: "1px solid var(--border)", color: "var(--text)" }}>
              See How It Works
            </Link>
          </div>
          {/* Demo Video Placeholder */}
          <div className="max-w-3xl mx-auto rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
            <div className="aspect-video flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: "var(--accent)", opacity: 0.9 }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="white" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                </div>
                <p style={{ color: "var(--muted)" }}>Watch 60-Second Demo</p>
              </div>
            </div>
          </div>
        </div>
      </section>


      {/* ─── Features Section ─── */}
      <section className="py-24 px-4" style={{ background: "var(--surface)" }}>
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">Why Creators Love Shorts Engine</h2>
          <p className="text-center mb-16 max-w-2xl mx-auto" style={{ color: "var(--muted)" }}>
            Everything you need to repurpose long-form content into viral short-form clips.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((f, i) => (
              <div key={i} className="p-6 rounded-xl transition-transform hover:scale-105" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div className="mb-4" style={{ color: "var(--accent)" }}>{f.icon}</div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-sm" style={{ color: "var(--muted)" }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── How It Works Section ─── */}
      <section id="how-it-works" className="py-24 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">How It Works</h2>
          <p className="text-center mb-16 max-w-xl mx-auto" style={{ color: "var(--muted)" }}>
            Three simple steps from long video to viral shorts.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((s, i) => (
              <div key={i} className="text-center p-8 rounded-xl relative" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white" style={{ background: "var(--accent)" }}>
                  {i + 1}
                </div>
                <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: "var(--bg)", color: "var(--accent)" }}>
                  {s.icon}
                </div>
                <h3 className="text-xl font-semibold mb-2">{s.title}</h3>
                <p className="text-sm" style={{ color: "var(--muted)" }}>{s.desc}</p>
                {i < 2 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 text-2xl" style={{ color: "var(--accent)" }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>


      {/* ─── Pricing Section ─── */}
      <section className="py-24 px-4" style={{ background: "var(--surface)" }}>
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">Simple, Transparent Pricing</h2>
          <p className="text-center mb-16 max-w-xl mx-auto" style={{ color: "var(--muted)" }}>
            Start free. Upgrade when you&apos;re ready to go viral.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {pricingTiers.map((tier, i) => (
              <div
                key={i}
                className="p-8 rounded-xl flex flex-col"
                style={{
                  background: "var(--bg)",
                  border: tier.highlighted ? "2px solid var(--accent)" : "1px solid var(--border)",
                  position: "relative",
                }}
              >
                {tier.highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold text-white" style={{ background: "var(--accent)" }}>
                    MOST POPULAR
                  </div>
                )}
                <h3 className="text-xl font-bold mb-1">{tier.name}</h3>
                <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>{tier.desc}</p>
                <div className="mb-6">
                  <span className="text-4xl font-bold">{tier.price}</span>
                  <span style={{ color: "var(--muted)" }}>{tier.period}</span>
                </div>
                <ul className="space-y-3 mb-8 flex-1">
                  {tier.features.map((f, fi) => (
                    <li key={fi} className="flex items-center gap-2 text-sm">
                      <span style={{ color: "var(--success)" }}><IconCheck /></span>
                      {f}
                    </li>
                  ))}
                  {tier.missing.map((m, mi) => (
                    <li key={mi} className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
                      <span><IconX /></span>
                      {m}
                    </li>
                  ))}
                </ul>
                <Link
                  href={tier.highlighted ? "/auth/signup" : "/auth/signup"}
                  className="block text-center py-3 rounded-lg font-semibold transition-colors"
                  style={{
                    background: tier.highlighted ? "var(--accent)" : "transparent",
                    border: tier.highlighted ? "none" : "1px solid var(--border)",
                    color: "white",
                  }}
                >
                  {tier.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>


      {/* ─── Testimonials Section ─── */}
      <section className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">Loved by Creators</h2>
          <p className="text-center mb-16 max-w-xl mx-auto" style={{ color: "var(--muted)" }}>
            See what our community has to say.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((t, i) => (
              <div key={i} className="p-6 rounded-xl" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                <p className="text-sm mb-6 leading-relaxed" style={{ color: "var(--muted)" }}>
                  &ldquo;{t.text}&rdquo;
                </p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold" style={{ background: "var(--accent)", color: "white" }}>
                    {t.avatar}
                  </div>
                  <div>
                    <p className="font-semibold text-sm">{t.name}</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>{t.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FAQ Section ─── */}
      <section className="py-24 px-4" style={{ background: "var(--surface)" }}>
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">Frequently Asked Questions</h2>
          <p className="text-center mb-12" style={{ color: "var(--muted)" }}>
            Got questions? We&apos;ve got answers.
          </p>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <div key={i} className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg)" }}>
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full text-left px-6 py-4 flex items-center justify-between font-medium"
                >
                  {faq.q}
                  <span className="ml-4 text-xl" style={{ color: "var(--accent)" }}>
                    {openFaq === i ? "−" : "+"}
                  </span>
                </button>
                {openFaq === i && (
                  <div className="px-6 pb-4 text-sm" style={{ color: "var(--muted)" }}>
                    {faq.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>


      {/* ─── Final CTA Section ─── */}
      <section className="py-24 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Ready to 10x Your Short-Form Content?
          </h2>
          <p className="text-lg mb-10" style={{ color: "var(--muted)" }}>
            Join thousands of creators already using Shorts Engine to grow their audience. Start free — no credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/auth/signup" className="px-8 py-4 rounded-lg text-lg font-semibold text-white transition-colors" style={{ background: "var(--accent)" }}>
              Start Creating Free →
            </Link>
            <Link href="/pricing" className="px-8 py-4 rounded-lg text-lg font-semibold transition-colors" style={{ border: "1px solid var(--border)", color: "var(--text)" }}>
              View Pricing
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="py-12 px-4" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            &copy; {new Date().getFullYear()} Shorts Engine Studio. All rights reserved.
          </p>
          <div className="flex gap-6 text-sm" style={{ color: "var(--muted)" }}>
            <Link href="/legal/terms" className="hover:underline">Terms</Link>
            <Link href="/legal/privacy" className="hover:underline">Privacy</Link>
            <Link href="/pricing" className="hover:underline">Pricing</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
