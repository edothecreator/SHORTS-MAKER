"use client";

import Link from "next/link";
import { useState } from "react";

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

const tiers = [
  { name: "Free", monthlyPrice: 0, annualPrice: 0 },
  { name: "Pro", monthlyPrice: 15, annualPrice: 12 },
  { name: "Business", monthlyPrice: 39, annualPrice: 31 },
];


interface FeatureRow {
  name: string;
  free: string | boolean;
  pro: string | boolean;
  business: string | boolean;
}

const featureMatrix: { category: string; features: FeatureRow[] }[] = [
  {
    category: "Video Processing",
    features: [
      { name: "Videos per month", free: "3", pro: "30", business: "Unlimited" },
      { name: "Max source video length", free: "60 min", pro: "180 min", business: "180 min" },
      { name: "Output resolution", free: "720p", pro: "1080p", business: "4K" },
      { name: "Render priority", free: "Standard", pro: "Priority", business: "Priority" },
      { name: "Concurrent renders", free: false, pro: true, business: true },
    ],
  },
  {
    category: "Subtitles & Styling",
    features: [
      { name: "Subtitle styles", free: "5 basic", pro: "20+ styles", business: "20+ styles" },
      { name: "Custom fonts", free: false, pro: true, business: true },
      { name: "Brand kit", free: false, pro: false, business: true },
      { name: "Watermark-free export", free: false, pro: true, business: true },
    ],
  },
  {
    category: "AI Features",
    features: [
      { name: "AI moment detection", free: true, pro: true, business: true },
      { name: "Virality scoring", free: true, pro: true, business: true },
      { name: "Smart reframing (face tracking)", free: false, pro: true, business: true },
      { name: "Multi-language subtitles", free: false, pro: true, business: true },
      { name: "Subtitle translation", free: false, pro: true, business: true },
    ],
  },
  {
    category: "Publishing & Distribution",
    features: [
      { name: "Download clips", free: true, pro: true, business: true },
      { name: "Direct publish to platforms", free: false, pro: true, business: true },
      { name: "Schedule posts", free: false, pro: true, business: true },
      { name: "Platform analytics", free: false, pro: true, business: true },
    ],
  },
  {
    category: "Collaboration & API",
    features: [
      { name: "Team members", free: "1", pro: "1", business: "Unlimited" },
      { name: "Team workspace", free: false, pro: false, business: true },
      { name: "Approval workflow", free: false, pro: false, business: true },
      { name: "REST API access", free: false, pro: false, business: true },
      { name: "Webhook notifications", free: false, pro: false, business: true },
    ],
  },
  {
    category: "Storage & Support",
    features: [
      { name: "Rendered clip storage", free: "30 days", pro: "90 days", business: "90 days" },
      { name: "Project history", free: true, pro: true, business: true },
      { name: "URL import (YouTube, etc.)", free: true, pro: true, business: true },
      { name: "Priority support", free: false, pro: true, business: true },
    ],
  },
];


export default function PricingPage() {
  const [annual, setAnnual] = useState(false);

  return (
    <div className="min-h-screen py-16 px-4" style={{ background: "var(--bg)", color: "var(--text)" }}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl sm:text-5xl font-bold mb-4">Choose Your Plan</h1>
          <p className="text-lg max-w-2xl mx-auto mb-8" style={{ color: "var(--muted)" }}>
            Start free. Upgrade as you grow. All paid plans include a 7-day free trial.
          </p>

          {/* Monthly / Annual Toggle */}
          <div className="flex items-center justify-center gap-4">
            <span className={`text-sm font-medium ${!annual ? "" : ""}`} style={{ color: !annual ? "var(--text)" : "var(--muted)" }}>Monthly</span>
            <button
              onClick={() => setAnnual(!annual)}
              className="relative w-14 h-7 rounded-full transition-colors"
              style={{ background: annual ? "var(--accent)" : "var(--border)" }}
              aria-label="Toggle annual billing"
            >
              <div
                className="absolute top-1 w-5 h-5 rounded-full bg-white transition-transform"
                style={{ left: annual ? "calc(100% - 1.5rem)" : "0.25rem" }}
              />
            </button>
            <span className={`text-sm font-medium`} style={{ color: annual ? "var(--text)" : "var(--muted)" }}>
              Annual <span className="ml-1 px-2 py-0.5 rounded text-xs font-bold" style={{ background: "var(--accent)", color: "white" }}>Save 20%</span>
            </span>
          </div>
        </div>


        {/* Tier Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
          {tiers.map((tier, i) => {
            const price = annual ? tier.annualPrice : tier.monthlyPrice;
            const isPopular = tier.name === "Pro";
            return (
              <div
                key={i}
                className="p-8 rounded-xl flex flex-col relative"
                style={{
                  background: "var(--surface)",
                  border: isPopular ? "2px solid var(--accent)" : "1px solid var(--border)",
                }}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold text-white" style={{ background: "var(--accent)" }}>
                    MOST POPULAR
                  </div>
                )}
                <h3 className="text-xl font-bold mb-1">{tier.name}</h3>
                <div className="mb-6 mt-2">
                  <span className="text-4xl font-bold">${price}</span>
                  <span style={{ color: "var(--muted)" }}>/month</span>
                  {annual && tier.monthlyPrice > 0 && (
                    <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                      Billed ${price * 12}/year (saves ${(tier.monthlyPrice - tier.annualPrice) * 12}/yr)
                    </p>
                  )}
                </div>
                <Link
                  href="/auth/signup"
                  className="block text-center py-3 rounded-lg font-semibold transition-colors mt-auto"
                  style={{
                    background: isPopular ? "var(--accent)" : "transparent",
                    border: isPopular ? "none" : "1px solid var(--border)",
                    color: "white",
                  }}
                >
                  {tier.monthlyPrice === 0 ? "Get Started Free" : "Start 7-Day Free Trial"}
                </Link>
              </div>
            );
          })}
        </div>


        {/* Feature Matrix */}
        <div className="mb-16">
          <h2 className="text-2xl font-bold text-center mb-8">Compare All Features</h2>
          <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid var(--border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: "var(--surface)" }}>
                  <th className="text-left p-4 font-semibold">Feature</th>
                  <th className="text-center p-4 font-semibold">Free</th>
                  <th className="text-center p-4 font-semibold" style={{ color: "var(--accent)" }}>Pro</th>
                  <th className="text-center p-4 font-semibold">Business</th>
                </tr>
              </thead>
              <tbody>
                {featureMatrix.map((section, si) => (
                  <>
                    <tr key={`cat-${si}`} style={{ background: "var(--bg)" }}>
                      <td colSpan={4} className="px-4 py-3 font-bold text-xs uppercase tracking-wider" style={{ color: "var(--accent)" }}>
                        {section.category}
                      </td>
                    </tr>
                    {section.features.map((f, fi) => (
                      <tr key={`${si}-${fi}`} style={{ borderTop: "1px solid var(--border)" }}>
                        <td className="p-4">{f.name}</td>
                        <td className="p-4 text-center">
                          {typeof f.free === "boolean" ? (
                            f.free ? <span className="inline-flex justify-center" style={{ color: "var(--success)" }}><IconCheck /></span> : <span className="inline-flex justify-center" style={{ color: "var(--muted)" }}><IconX /></span>
                          ) : (
                            <span>{f.free}</span>
                          )}
                        </td>
                        <td className="p-4 text-center">
                          {typeof f.pro === "boolean" ? (
                            f.pro ? <span className="inline-flex justify-center" style={{ color: "var(--success)" }}><IconCheck /></span> : <span className="inline-flex justify-center" style={{ color: "var(--muted)" }}><IconX /></span>
                          ) : (
                            <span>{f.pro}</span>
                          )}
                        </td>
                        <td className="p-4 text-center">
                          {typeof f.business === "boolean" ? (
                            f.business ? <span className="inline-flex justify-center" style={{ color: "var(--success)" }}><IconCheck /></span> : <span className="inline-flex justify-center" style={{ color: "var(--muted)" }}><IconX /></span>
                          ) : (
                            <span>{f.business}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>


        {/* Bottom CTA */}
        <div className="text-center p-12 rounded-xl" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-2xl font-bold mb-3">Not sure which plan is right?</h3>
          <p className="mb-6" style={{ color: "var(--muted)" }}>
            Start with Free — upgrade anytime. All paid plans include a 7-day trial, no credit card required.
          </p>
          <Link href="/auth/signup" className="inline-block px-8 py-3 rounded-lg font-semibold text-white" style={{ background: "var(--accent)" }}>
            Get Started Free →
          </Link>
        </div>
      </div>
    </div>
  );
}
