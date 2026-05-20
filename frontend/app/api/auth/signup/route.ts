import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";

/**
 * POST /api/auth/signup — Create a new user account
 * Production Task 1.5: email/password signup with bcrypt hashing
 *
 * TODO: Wire to PostgreSQL when database is set up (Task 2.x)
 */
export async function POST(request: Request) {
  try {
    const { name, email, password } = await request.json();

    // Validate input
    if (!name || !email || !password) {
      return NextResponse.json(
        { error: "Name, email, and password are required." },
        { status: 400 }
      );
    }

    if (password.length < 8) {
      return NextResponse.json(
        { error: "Password must be at least 8 characters." },
        { status: 400 }
      );
    }

    // TODO: Check if email already exists in database
    // const existingUser = await db.query('SELECT id FROM users WHERE email = $1', [email]);
    // if (existingUser) return NextResponse.json({ error: "Email already registered." }, { status: 409 });

    // Hash password
    const passwordHash = await bcrypt.hash(password, 12);

    // TODO: Insert into PostgreSQL
    // await db.query(
    //   'INSERT INTO users (id, email, name, password_hash, plan, created_at) VALUES ($1, $2, $3, $4, $5, NOW())',
    //   [crypto.randomUUID(), email, name, passwordHash, 'free']
    // );

    // TODO: Send verification email
    // await sendVerificationEmail(email, verificationToken);

    return NextResponse.json(
      { message: "Account created. Please check your email to verify." },
      { status: 201 }
    );
  } catch (error) {
    console.error("Signup error:", error);
    return NextResponse.json(
      { error: "Internal server error." },
      { status: 500 }
    );
  }
}
