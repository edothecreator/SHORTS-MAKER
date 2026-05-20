"use client";

export default function TermsOfServicePage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">Terms of Service</h1>
      <p className="text-sm text-gray-500 mb-8">
        Effective Date: [EFFECTIVE_DATE_PLACEHOLDER]
      </p>

      <p className="mb-6 text-gray-700">
        Welcome to Shorts Engine Studio. By using our service, you agree to
        these terms. Please read them carefully. If you do not agree, do not use
        the service.
      </p>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">1. What This Service Does</h2>
        <p className="text-gray-700">
          Shorts Engine Studio is a web application that helps you turn long-form
          video content into short-form clips suitable for social media platforms.
          We provide video analysis, automatic clipping, subtitle generation,
          smart reframing, and optional publishing to connected platforms.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">2. Who Can Use This Service</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>You must be at least 18 years old, or the age of majority in your jurisdiction.</li>
          <li>You must provide accurate information when creating an account.</li>
          <li>You are responsible for keeping your login credentials secure.</li>
          <li>One person or entity per account &mdash; sharing accounts is not allowed.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">3. Content Ownership</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            <strong>Your content stays yours.</strong> You retain full ownership
            of any videos you upload and any clips we generate from them.
          </li>
          <li>
            You grant us a limited license to process, store temporarily, and
            render your content solely to provide the service.
          </li>
          <li>
            We do not claim any intellectual property rights over your content.
          </li>
          <li>
            You are responsible for ensuring you have the right to upload and
            process any content you submit (e.g., you own it, or you have a
            license to use it).
          </li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">4. Usage Rights and Restrictions</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>You may use the service for personal or commercial purposes in accordance with your plan.</li>
          <li>You may not upload content that is illegal, infringing, hateful, or pornographic.</li>
          <li>You may not use the service to harass, abuse, or harm others.</li>
          <li>You may not attempt to reverse-engineer, scrape, or overload our systems.</li>
          <li>You may not resell access to the service without written permission.</li>
          <li>We reserve the right to remove content that violates these terms without notice.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">5. Subscription Plans and Payment</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>Free accounts have limited usage (see our pricing page for current limits).</li>
          <li>Paid plans are billed monthly or annually, charged in advance.</li>
          <li>Prices may change with 30 days&apos; notice. Existing subscriptions are honored until renewal.</li>
          <li>You can cancel anytime. Your access continues until the end of the current billing period.</li>
          <li>Failed payments will result in a 3-day grace period, after which your account will be downgraded to free.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">6. Refunds</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>We offer pro-rated refunds if you cancel within 7 days of subscribing or renewing.</li>
          <li>Refunds are calculated based on unused days in your billing period.</li>
          <li>After 7 days, no refund is provided but you keep access until period end.</li>
          <li>Refunds are processed back to the original payment method within 5-10 business days.</li>
          <li>See our <a href="/legal/refund" className="text-blue-600 underline">Refund Policy</a> for full details.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">7. Service Availability</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>We aim for high uptime but do not guarantee uninterrupted service.</li>
          <li>We may perform maintenance with reasonable notice when possible.</li>
          <li>We are not liable for losses caused by downtime, slow performance, or service interruptions.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">8. Limitation of Liability</h2>
        <p className="text-gray-700 mb-3">
          To the maximum extent permitted by law:
        </p>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            The service is provided &ldquo;as is&rdquo; without warranties of
            any kind, whether express or implied.
          </li>
          <li>
            We are not responsible for any indirect, incidental, or
            consequential damages arising from your use of the service.
          </li>
          <li>
            Our total liability to you for any claim related to the service is
            limited to the amount you paid us in the 12 months preceding the
            claim.
          </li>
          <li>
            We are not responsible for content you publish to third-party
            platforms using our service.
          </li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">9. Account Termination</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            <strong>By you:</strong> You can delete your account at any time from
            your profile settings. We will permanently delete all your data
            within 30 days.
          </li>
          <li>
            <strong>By us:</strong> We may suspend or terminate your account if
            you violate these terms, engage in abusive behavior, or fail to pay
            for a paid plan.
          </li>
          <li>
            Upon termination, your right to use the service stops immediately.
            Stored content may be deleted.
          </li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">10. Privacy</h2>
        <p className="text-gray-700">
          Your privacy matters. Please read our{" "}
          <a href="/legal/privacy" className="text-blue-600 underline">
            Privacy Policy
          </a>{" "}
          to understand what data we collect and how we use it.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">11. Changes to These Terms</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>We may update these terms from time to time.</li>
          <li>We will notify you via email or in-app notice at least 14 days before changes take effect.</li>
          <li>Continued use of the service after changes means you accept the new terms.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">12. Governing Law</h2>
        <p className="text-gray-700">
          These terms are governed by the laws of the State of Delaware, United
          States, without regard to conflict of law principles. Any disputes will
          be resolved in the courts of Delaware, unless we agree to arbitration.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">13. Contact Us</h2>
        <p className="text-gray-700">
          If you have questions about these terms, please contact us at{" "}
          <a href="mailto:legal@shortsengine.studio" className="text-blue-600 underline">
            legal@shortsengine.studio
          </a>
          .
        </p>
      </section>
    </main>
  );
}
