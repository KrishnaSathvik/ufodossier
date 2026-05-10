import { getSupabase } from "@/lib/supabase";
import { redirect, notFound } from "next/navigation";
import type { Metadata } from "next";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function UUIDRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sb = getSupabase();
  const { data } = await sb.from("incidents").select("slug").eq("id", id).single();

  if (!data) notFound();

  // Redirect to slug URL if available, otherwise to the incident page with UUID
  redirect(`/incident/${data.slug || id}`);
}
