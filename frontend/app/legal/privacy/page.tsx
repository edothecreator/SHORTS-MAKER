"use client";

export default function PrivacyPolicyPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-sm text-gray-500 mb-8">
        Effective Date: [EFFECTIVE_DATE_PLACEHOLDER]
      </p>

      <p className="mb-6 text-gray-700">
        At Shorts Engine Studio, we take your privacy seriously. This policy
        explains what information we collect, how we use it, how long we keep it,
        and what rights you have over it.
      </p>

      {/* Section 1 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">1. Information We Collect</h2>

        <h3 className="text-lg font-medium mt-4 mb-2">Account Information</h3>
        <ul className="list-disc pl-6 text-gray-700 space-y-1">
          <li>Name and email address (when you sign up)</li>
          <li>Profile picture (if you sign in with Google or GitHub)</li>
          <li>Password hash (if you use email/password login)</li>
        </ul>

        <h3 className="text-lg font-medium mt-4 mb-2">Payment Information</h3>
        <ul className="list-disc pl-6 text-gray-700 space-y-1">
          <li>Billing name and address</li>
          <li>Payment method details are handled by Stripe &mdash; we never store your full card number</li>
          <li>Transaction history and subscription status</li>
        </ul>

        <h3 className="text-lg font-medium mt-4 mb-2">Content You Upload</h3>
        <ul className="list-disc pl-6 text-gray-700 space-y-1">
          <li>Video files you upload for processing</li>
          <li>Generated clips, subtitles, and project configurations</li>
          <li>Transcript text generated from your videos</li>
        </ul>

        <h3 className="text-lg font-medium mt-4 mb-2">Usage Data</h3>
        <ul className="list-disc pl-6 text-gray-700 space-y-1">
          <li>Pages you visit and features you use</li>
          <li>Device type, browser, and operating system</li>
          <li>IP address and approximate location (country/region level)</li>
          <li>Processing history (which videos processed, settings used)</li>
        </ul>
      </section>

      {/* Section 2 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">2. How We Use Your Information</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li><strong>To provide the service:</strong> Process your videos, generate clips, render subtitles.</li>
          <li><strong>To manage your account:</strong> Authentication, billing, subscription management.</li>
          <li><strong>To improve the service:</strong> Analyze usage patterns to improve features and performance.</li>
          <li><strong>To communicate with you:</strong> Send account notifications, billing receipts, and service updates.</li>
          <li><strong>To ensure security:</strong> Detect and prevent fraud, abuse, and unauthorized access.</li>
          <li><strong>To comply with law:</strong> Respond to legal requests and enforce our terms.</li>
        </ul>
        <p className="mt-3 text-gray-700">
          We do <strong>not</strong> sell your personal information to anyone. Ever.
        </p>
      </section>

      {/* Section 3 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">3. Cookies and Tracking</h2>

        <h3 className="text-lg font-medium mt-4 mb-2">Necessary Cookies</h3>
        <p className="text-gray-700 mb-2">
          These are required for the service to function. They handle authentication
          sessions and security tokens. You cannot opt out of these.
        </p>

        <h3 className="text-lg font-medium mt-4 mb-2">Analytics Cookies</h3>
        <p className="text-gray-700 mb-2">
          We use privacy-friendly analytics (such as PostHog or Plausible) to
          understand how people use our service. These cookies track page views,
          feature usage, and performance metrics. You can opt out of these.
        </p>

        <h3 className="text-lg font-medium mt-4 mb-2">Marketing Cookies</h3>
        <p className="text-gray-700 mb-2">
          If enabled, these help us understand which marketing channels bring
          users to us. They are disabled by default and require your explicit
          consent.
        </p>

        <p className="text-gray-700 mt-3">
          You can manage your cookie preferences at any time through our cookie
          settings panel accessible from the footer of every page.
        </p>
      </section>

      {/* Section 4 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">4. Data Retention</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li><strong>Account data:</strong> Kept for as long as your account is active, plus 30 days after deletion request.</li>
          <li><strong>Uploaded source videos:</strong> Automatically deleted within 24 hours after processing.</li>
          <li><strong>Rendered clips:</strong> Kept for 30 days (free tier) or 90 days (paid tier) after creation, then automatically deleted.</li>
          <li><strong>Usage logs:</strong> Retained for 12 months for analytics, then anonymized or deleted.</li>
          <li><strong>Payment records:</strong> Retained for 7 years as required by tax law.</li>
        </ul>
      </section>

      {/* Section 5 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">5. Third-Party Services</h2>
        <p className="text-gray-700 mb-3">
          We use the following third-party services that may process your data:
        </p>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li><strong>Stripe</strong> &mdash; Payment processing. See <a href="https://stripe.com/privacy" className="text-blue-600 underline" target="_blank" rel="noopener noreferrer">Stripe&apos;s Privacy Policy</a>.</li>
          <li><strong>Google Cloud / AWS</strong> &mdash; Cloud infrastructure and content moderation. Data processed in the US and EU.</li>
          <li><strong>Cloudflare</strong> &mdash; CDN and DDoS protection. See <a href="https://www.cloudflare.com/privacypolicy/" className="text-blue-600 underline" target="_blank" rel="noopener noreferrer">Cloudflare&apos;s Privacy Policy</a>.</li>
          <li><strong>PostHog / Plausible</strong> &mdash; Privacy-friendly analytics.</li>
          <li><strong>Resend / Loops</strong> &mdash; Transactional emails (receipts, password resets).</li>
          <li><strong>Sentry</strong> &mdash; Error tracking (may include anonymized usage context).</li>
          <li><strong>Social platforms (TikTok, YouTube, Instagram, LinkedIn)</strong> &mdash; Only when you explicitly connect your accounts for publishing.</li>
        </ul>
        <p className="mt-3 text-gray-700">
          We have Data Processing Agreements (DPAs) with all critical third-party
          processors as required by GDPR.
        </p>
      </section>

      {/* Section 6 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">6. Your Rights (GDPR)</h2>
        <p className="text-gray-700 mb-3">
          If you are in the European Economic Area (EEA), United Kingdom, or a
          jurisdiction with similar laws, you have the following rights:
        </p>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li><strong>Access:</strong> Request a copy of all personal data we hold about you.</li>
          <li><strong>Rectification:</strong> Correct inaccurate data we hold about you.</li>
          <li><strong>Erasure:</strong> Request deletion of all your personal data (&ldquo;right to be forgotten&rdquo;).</li>
          <li><strong>Portability:</strong> Receive your data in a machine-readable format (JSON export).</li>
          <li><strong>Restriction:</strong> Request we stop processing your data in certain circumstances.</li>
          <li><strong>Objection:</strong> Object to processing based on legitimate interests.</li>
          <li><strong>Withdraw consent:</strong> Withdraw consent for optional data processing at any time.</li>
        </ul>
        <p className="mt-3 text-gray-700">
          To exercise these rights, visit your account settings or email{" "}
          <a href="mailto:privacy@shortsengine.studio" className="text-blue-600 underline">
            privacy@shortsengine.studio
          </a>
          . We will respond within 30 days.
        </p>
      </section>

      {/* Section 7 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">7. Your Rights (CCPA &mdash; California Residents)</h2>
        <p className="text-gray-700 mb-3">
          If you are a California resident, the California Consumer Privacy Act
          (CCPA) gives you additional rights:
        </p>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li><strong>Right to know:</strong> What personal information we collect and how we use it.</li>
          <li><strong>Right to delete:</strong> Request deletion of your personal information.</li>
          <li><strong>Right to opt out:</strong> Opt out of the &ldquo;sale&rdquo; of personal information. Note: We do not sell your data, but you can submit an opt-out request for the record.</li>
          <li><strong>Right to non-discrimination:</strong> We will not treat you differently for exercising your rights.</li>
        </ul>
        <p className="mt-3 text-gray-700">
          To exercise your CCPA rights, email{" "}
          <a href="mailto:privacy@shortsengine.studio" className="text-blue-600 underline">
            privacy@shortsengine.studio
          </a>{" "}
          or use the opt-out controls in your account settings.
        </p>
      </section>

      {/* Section 8 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">8. Data Security</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>All data transmitted between your browser and our servers is encrypted with TLS (HTTPS).</li>
          <li>Passwords are hashed with bcrypt (never stored in plain text).</li>
          <li>Access to production systems is limited to authorized personnel with multi-factor authentication.</li>
          <li>We perform regular security audits and vulnerability assessments.</li>
          <li>In the event of a data breach, we will notify affected users within 72 hours as required by GDPR.</li>
        </ul>
      </section>

      {/* Section 9 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">9. International Data Transfers</h2>
        <p className="text-gray-700">
          Our servers are primarily located in the United States. If you are
          accessing the service from outside the US, your data will be
          transferred to and processed in the US. We rely on Standard Contractual
          Clauses (SCCs) and adequacy decisions where applicable to ensure your
          data is protected during international transfers.
        </p>
      </section>

      {/* Section 10 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">10. Children&apos;s Privacy</h2>
        <p className="text-gray-700">
          Our service is not intended for children under 18. We do not knowingly
          collect information from children. If you believe a child has provided
          us with personal information, please contact us and we will delete it.
        </p>
      </section>

      {/* Section 11 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">11. Changes to This Policy</h2>
        <p className="text-gray-700">
          We may update this privacy policy periodically. We will notify you of
          material changes via email or an in-app banner at least 14 days before
          the changes take effect. Your continued use of the service after
          changes means you accept the updated policy.
        </p>
      </section>

      {/* Section 12 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">12. Contact Us</h2>
        <p className="text-gray-700">
          For privacy-related questions or to exercise your data rights:
        </p>
        <ul className="list-none pl-0 mt-3 text-gray-700 space-y-1">
          <li>Email: <a href="mailto:privacy@shortsengine.studio" className="text-blue-600 underline">privacy@shortsengine.studio</a></li>
          <li>Data Protection Officer: <a href="mailto:dpo@shortsengine.studio" className="text-blue-600 underline">dpo@shortsengine.studio</a></li>
        </ul>
      </section>
    </main>
  );
}
