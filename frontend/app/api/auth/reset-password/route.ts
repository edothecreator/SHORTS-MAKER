import { NextResponse } from "next/server";

/**
 * POST /api/auth/reset-password — Send password reset email
 * Production Task 1.7: forgot password → email link → reset
 *
 * TODO: Wire to PostgreSQL + email service when set up (Task 2.x)
 */
export async function POST(request: Request) {
  try {
    const { email } = await request.json();

    if (!email) {
      return NextResponse.json(
        { error: "Email is required." },
        { status: 400 }
      );
    }

    // TODO: Look up user in database
    // const user = await db.query('SELECT id FROM users WHERE email = $1', [email]);

    // TODO: Generate reset token and store in DB with expiry (1 hour)
    // const token = crypto.randomUUID();
    // await db.query(
    //   'INSERT INTO password_resets (user_id, token, expires_at) VALUES ($1, $2, NOW() + INTERVAL 1 HOUR)',
    //   [user.id, token]
    // );

    // TODO: Send email with reset link
    // await sendEmail(email, {
    //   subject: 'Reset your password',
    //   body: `Click here to reset: ${process.env.NEXTAUTH_URL}/auth/reset-password/confirm?token=${token}`
    // });

    // Always return success (don't reveal whether email exists)
    return NextResponse.json(
      { message: "If that email exists, a reset link has been sent." },
      { status: 200 }
    );
  } catch (error) {
    console.error("Reset password error:", error);
    return NextResponse.json(
      { error: "Internal server error." },
      { status: 500 }
    );
  }
}
