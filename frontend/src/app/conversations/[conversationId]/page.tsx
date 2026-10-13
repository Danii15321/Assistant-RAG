import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { ChatShell } from "@/components/chat-shell";
import { ConversationPanel } from "@/components/conversation-panel";

export const dynamic = "force-dynamic";
export default async function Page({ params }: { params: Promise<{ conversationId: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  const { conversationId } = await params;
  return <ChatShell username={session.user.name}><ConversationPanel key={conversationId} id={conversationId} /></ChatShell>;
}
