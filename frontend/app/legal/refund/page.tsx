"use client";

export default function RefundPolicyPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">Refund Policy</h1>
      <p className="text-sm text-gray-500 mb-8">
        Effective Date: [EFFECTIVE_DATE_PLACEHOLDER]
      </p>

      <p className="mb-6 text-gray-700">
        We want you to be happy with Shorts Engine Studio. If you&apos;re not
        satisfied, here&apos;s how refunds work.
      </p>

      {/* Section 1 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">1. Pro-Rated Refund (Within 7 Days)</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            If you cancel your subscription within <strong>7 days</strong> of
            subscribing or renewing, you are eligible for a pro-rated refund.
          </li>
          <li>
            The refund amount is calculated based on the number of unused days
            remaining in your billing period.
          </li>
          <li>
            For example, if you paid for a monthly plan and cancel on day 3, you
            will be refunded approximately 77% of the charge (24 unused days out
            of 31).
          </li>
          <li>
            Refunds are processed back to your original payment method (credit
            card or bank account).
          </li>
          <li>
            Please allow 5&ndash;10 business days for the refund to appear on
            your statement.
          </li>
        </ul>
      </section>

      {/* Section 2 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">2. After 7 Days</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            After the 7-day window, we do not offer refunds for the current
            billing period.
          </li>
          <li>
            However, you can cancel at any time, and your subscription will
            remain active until the end of the current billing period. You will
            not be charged again.
          </li>
        </ul>
      </section>

      {/* Section 3 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">3. How to Cancel</h2>
        <ol className="list-decimal pl-6 text-gray-700 space-y-2">
          <li>Go to your <strong>Account Settings</strong> page.</li>
          <li>Click <strong>Manage Subscription</strong> (this opens the Stripe Customer Portal).</li>
          <li>Click <strong>Cancel Subscription</strong>.</li>
          <li>Confirm the cancellation.</li>
        </ol>
        <p className="mt-3 text-gray-700">
          Alternatively, you can email{" "}
          <a href="mailto:support@shortsengine.studio" className="text-blue-600 underline">
            support@shortsengine.studio
          </a>{" "}
          and we will process the cancellation for you within 1 business day.
        </p>
      </section>

      {/* Section 4 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">4. What Happens When You Cancel</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>Your account is immediately downgraded to the free tier at the end of your current billing period.</li>
          <li>You keep access to all paid features until the period ends.</li>
          <li>
            Your projects and rendered clips remain accessible according to the
            free tier retention policy (30 days).
          </li>
          <li>
            Credits do not roll over &mdash; unused credits from a paid period
            are forfeited at cancellation.
          </li>
        </ul>
      </section>

      {/* Section 5 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">5. Annual Plan Refunds</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            Annual plans follow the same 7-day pro-rated refund policy from the
            date of purchase or renewal.
          </li>
          <li>
            After 7 days, you may cancel but no refund is provided for the
            remainder of the annual term.
          </li>
          <li>Your access continues until the annual period ends.</li>
        </ul>
      </section>

      {/* Section 6 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">6. Exceptions</h2>
        <ul className="list-disc pl-6 text-gray-700 space-y-2">
          <li>
            If we experience a major outage (more than 24 hours continuous
            downtime) affecting your ability to use the service, we will
            provide a credit or refund proportional to the downtime.
          </li>
          <li>
            If your account is terminated by us due to a policy violation, no
            refund is provided.
          </li>
          <li>
            Chargebacks filed without first contacting us may result in account
            suspension.
          </li>
        </ul>
      </section>

      {/* Section 7 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">7. How to Request a Refund</h2>
        <p className="text-gray-700">
          Email{" "}
          <a href="mailto:support@shortsengine.studio" className="text-blue-600 underline">
            support@shortsengine.studio
          </a>{" "}
          with the subject line &ldquo;Refund Request&rdquo; and include your
          account email. We will respond within 2 business days.
        </p>
      </section>

      {/* Section 8 */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3">8. Contact</h2>
        <p className="text-gray-700">
          Questions about billing or refunds? Reach us at{" "}
          <a href="mailto:support@shortsengine.studio" className="text-blue-600 underline">
            support@shortsengine.studio
          </a>
          .
        </p>
      </section>
    </main>
  );
}
