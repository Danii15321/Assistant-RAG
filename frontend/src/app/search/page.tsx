import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { ChatShell } from "@/components/chat-shell";
import { SearchPanel } from "@/components/search-panel";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  return <ChatShell username={session.user.name}><div className="workspace-page"><div className="page-heading"><h1>Recherche documentaire</h1></div><SearchPanel /></div></ChatShell>;
}
