import { adminConfigured, isAdmin } from "@/lib/admin/auth";
import { AdminLogin } from "@/components/admin/AdminLogin";
import { ReviewQueue } from "@/components/admin/ReviewQueue";

export default async function AdminPage() {
  if (!adminConfigured()) {
    return (
      <main className="mx-auto max-w-md p-6">
        <h1 className="font-serif text-2xl font-semibold">Review</h1>
        <p className="mt-3 text-ink-2">
          The review area is closed. Add an <code>ADMIN_PASSWORD</code> environment variable in Vercel and redeploy.
        </p>
      </main>
    );
  }
  return (await isAdmin()) ? <ReviewQueue /> : <AdminLogin />;
}
