import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import GitHubProvider from "next-auth/providers/github";
import CredentialsProvider from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";

/**
 * NextAuth.js configuration — Production Task 1.1–1.4
 *
 * Providers:
 *   - Google OAuth (1.2)
 *   - GitHub OAuth (1.3)
 *   - Email/password credentials with bcrypt (1.4)
 *
 * In production, the credentials provider queries the PostgreSQL users table.
 * For now, it uses a placeholder that will be replaced when the DB is wired.
 */

// Placeholder user lookup — replace with real DB query in task 2.x
async function findUserByEmail(email: string) {
  // TODO: Replace with PostgreSQL query
  // Example: const user = await db.query('SELECT * FROM users WHERE email = $1', [email]);
  return null as {
    id: string;
    email: string;
    name: string;
    password_hash: string;
    image?: string;
    plan: string;
  } | null;
}

async function createUser(email: string, name: string, passwordHash: string) {
  // TODO: Replace with PostgreSQL INSERT
  // Returns the created user
  return {
    id: crypto.randomUUID(),
    email,
    name,
    password_hash: passwordHash,
    plan: "free",
  };
}

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID ?? "",
      clientSecret: process.env.GITHUB_CLIENT_SECRET ?? "",
    }),
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        const user = await findUserByEmail(credentials.email);
        if (!user) return null;

        const isValid = await bcrypt.compare(
          credentials.password,
          user.password_hash
        );
        if (!isValid) return null;

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.image,
        };
      },
    }),
  ],

  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },

  jwt: {
    maxAge: 30 * 24 * 60 * 60,
  },

  pages: {
    signIn: "/auth/login",
    newUser: "/auth/signup",
    error: "/auth/error",
  },

  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user && token.id) {
        (session.user as any).id = token.id;
      }
      return session;
    },
  },

  secret: process.env.NEXTAUTH_SECRET,
};
