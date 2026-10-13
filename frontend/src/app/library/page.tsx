import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { ChatShell } from "@/components/chat-shell";
import { DocumentLibrary } from "@/components/document-library";

export const dynamic = "force-dynamic";
export default async function Page({ searchParams }: { searchParams: Promise<{ document?: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  const { document } = await searchParams;
  return <ChatShell username={session.user.name}><div className="workspace-page"><div className="page-heading"><h1>Documents</h1></div><DocumentLibrary initialDocument={document} /></div></ChatShell>;
}
