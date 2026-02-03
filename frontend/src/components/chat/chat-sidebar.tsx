"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Plus, MessageSquare, Trash2, Loader2, Search, FileText, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { deleteChatSession } from "@/lib/supabase";
import { formatDate } from "@/lib/utils";
import type { ChatSession } from "@/types/database";
import { cn } from "@/lib/utils";

interface ChatSidebarProps {
  sessions: ChatSession[];
  currentSession: ChatSession | null;
  onNewChat: () => void;
  onSelectSession: (session: ChatSession) => void;
  onDeleteSession: (sessionId: string) => void;
  isLoading: boolean;
}

export function ChatSidebar({
  sessions,
  currentSession,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  isLoading,
}: ChatSidebarProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeletingId(sessionId);
    try {
      await deleteChatSession(sessionId);
      onDeleteSession(sessionId);
    } catch (error) {
      console.error("Error deleting session:", error);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="h-full flex flex-col bg-card/50 border-r border-border/50">
      {/* Logo and title */}
      <div className="p-3 border-b border-border/50">
        <div className="flex items-center gap-2 mb-4">
          <div className="h-6 w-6 rounded bg-primary flex items-center justify-center">
            <MessageSquare className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="font-semibold">Chatow</span>
          <ChevronDown className="h-4 w-4 ml-auto text-muted-foreground" />
        </div>
        <Button
          onClick={onNewChat}
          className="w-full justify-start gap-2 h-9"
          variant="ghost"
        >
          <Plus className="h-4 w-4" />
          Yeni sohbet
        </Button>
      </div>
      
      {/* Quick actions */}
      <div className="p-2 border-b border-border/50">
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-muted-foreground"
        >
          <Search className="h-4 w-4" />
          Geçmiş
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-muted-foreground"
        >
          <FileText className="h-4 w-4" />
          Keşfet
        </Button>
      </div>

      {/* Sessions list */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Henüz sohbet yok
            </div>
          ) : (
            sessions.map((session, index) => (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <div
                  onClick={() => onSelectSession(session)}
                  className={cn(
                    "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors group cursor-pointer",
                    currentSession?.id === session.id
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"
                  )}
                >
                  <MessageSquare className="h-4 w-4 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="truncate">{session.title}</p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-destructive/20 rounded transition-all"
                    disabled={deletingId === session.id}
                  >
                    {deletingId === session.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    )}
                  </button>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </ScrollArea>
      
      {/* User avatar at bottom */}
      <div className="p-3 border-t border-border/50 flex items-center gap-2">
        <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-semibold text-sm">
          U
        </div>
      </div>
    </div>
  );
}
