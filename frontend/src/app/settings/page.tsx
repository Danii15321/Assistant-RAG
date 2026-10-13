import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { ChatShell } from "@/components/chat-shell";
import { SettingsPanel } from "@/components/settings-panel";
export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  return <ChatShell username={session.user.name}><div className="workspace-page settings-page"><div className="page-heading"><h1>Paramètres</h1></div><SettingsPanel /></div></ChatShell>;
}
