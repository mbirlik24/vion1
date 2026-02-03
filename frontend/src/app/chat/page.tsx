"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/components/providers/auth-provider";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { ChatMessages } from "@/components/chat/chat-messages";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatHeader } from "@/components/chat/chat-header";
import {
  supabase,
  getChatSessions,
  createChatSession,
  getSessionMessages,
} from "@/lib/supabase";
import { apiUrl } from "@/lib/api";
import type { ChatSession, ChatMessage } from "@/types/database";
import { Loader2 } from "lucide-react";

export type ModelMode = "auto" | "fast" | "pro";

interface StreamingMessage {
  id: string;
  role: "assistant";
  content: string;
  model_used: string | null;
  isStreaming: boolean;
}

export default function ChatPage() {
  const router = useRouter();
  const { user, loading, credits, refreshCredits } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  // Default to "fast" for quicker, cheaper responses.
  // Users can still switch to "auto" or "pro" from the UI when they need more power.
  const [modelMode, setModelMode] = useState<ModelMode>("fast");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  // Don't auto-redirect to pricing - let users stay on chat page
  // They can see the "Get Credits" buttons if they need credits

  // Load sessions
  useEffect(() => {
    if (user) {
      loadSessions();
    }
  }, [user]);

  // Load messages when session changes
  useEffect(() => {
    if (currentSession) {
      loadMessages(currentSession.id);
    } else {
      setMessages([]);
    }
  }, [currentSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessage]);

  const loadSessions = async () => {
    if (!user) return;
    setIsLoading(true);
    try {
      const data = await getChatSessions(user.id);
      setSessions(data);
      if (data.length > 0 && !currentSession) {
        setCurrentSession(data[0]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadMessages = async (sessionId: string) => {
    const data = await getSessionMessages(sessionId);
    setMessages(data);
  };

  const handleNewChat = async () => {
    if (!user) return;
    try {
      const newSession = await createChatSession(user.id);
      setSessions((prev) => [newSession, ...prev]);
      setCurrentSession(newSession);
      setMessages([]);
    } catch (error) {
      console.error("Error creating session:", error);
    }
  };

  const handleSelectSession = (session: ChatSession) => {
    setCurrentSession(session);
    // Close sidebar on mobile after selection
    if (window.innerWidth < 640) {
      setSidebarOpen(false);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (currentSession?.id === sessionId) {
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setCurrentSession(remaining[0] || null);
    }
  };

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!user || !content.trim() || isSending) return;

      // Create session if none exists
      let sessionId = currentSession?.id;
      if (!sessionId) {
        try {
          const newSession = await createChatSession(user.id);
          setSessions((prev) => [newSession, ...prev]);
          setCurrentSession(newSession);
          sessionId = newSession.id;
        } catch (error) {
          console.error("Error creating session:", error);
          return;
        }
      }

      // Add user message optimistically
      const userMessage: ChatMessage = {
        id: `temp-${Date.now()}`,
        session_id: sessionId,
        role: "user",
        content,
        model_used: null,
        credits_used: 0,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsSending(true);

      // Initialize streaming message
      setStreamingMessage({
        id: `stream-${Date.now()}`,
        role: "assistant",
        content: "",
        model_used: null,
        isStreaming: true,
      });

      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;

        const response = await fetch(apiUrl("api/chat"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: content,
            session_id: sessionId,
            mode: modelMode,
          }),
        });

        if (!response.ok) {
          let errorMessage = "Mesaj gönderilirken bir hata oluştu";
          try {
            const error = await response.json();
            errorMessage = error.detail || error.message || errorMessage;
          } catch {
            // If response is not JSON, try to get text
            try {
              const errorText = await response.text();
              errorMessage = errorText || errorMessage;
            } catch {
              // Fallback to status text
              if (response.status === 404) {
                errorMessage = "Endpoint bulunamadı. Lütfen sayfayı yenileyin.";
              } else if (response.status === 500) {
                errorMessage = "Sunucu hatası. Lütfen daha sonra tekrar deneyin.";
              } else {
                errorMessage = response.statusText || errorMessage;
              }
            }
          }
          throw new Error(errorMessage);
        }

        // Handle streaming response
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) throw new Error("No response body");

        let fullContent = "";
        let modelUsed: string | null = null;
        let imageUrl: string | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;

              try {
                const parsed = JSON.parse(data);
                
                // Handle different response types
                if (parsed.type === "image") {
                  // Image generation response
                  if (parsed.image_url) {
                    imageUrl = parsed.image_url;
                    fullContent = `![Generated Image](${parsed.image_url})\n\n**Prompt:** ${parsed.prompt || "Image generation"}`;
                    setStreamingMessage((prev) =>
                      prev
                        ? { ...prev, content: fullContent, model_used: parsed.model || "dall-e-3" }
                        : null
                    );
                  } else {
                    console.error("Image URL not found in response:", parsed);
                    throw new Error("Görsel URL'i alınamadı. Lütfen tekrar deneyin.");
                  }
                } else if (parsed.type === "status") {
                  // Status update (e.g., "Generating image...")
                  setStreamingMessage((prev) =>
                    prev
                      ? { ...prev, content: parsed.content, model_used: parsed.model || "dall-e-3" }
                      : null
                  );
                } else if (parsed.type === "error") {
                  // Error response
                  throw new Error(parsed.error || "Bir hata oluştu");
                } else if (parsed.content) {
                  // Normal content chunk
                  fullContent += parsed.content;
                  setStreamingMessage((prev) =>
                    prev
                      ? { ...prev, content: fullContent, model_used: parsed.model }
                      : null
                  );
                }
                
                if (parsed.model) {
                  modelUsed = parsed.model;
                }
              } catch (parseError) {
                // If it's a real error (not just incomplete JSON), throw it
                if (parseError instanceof Error) {
                  // Check if it's a meaningful error message
                  if (parseError.message.includes("hata") || 
                      parseError.message.includes("error") ||
                      parseError.message.includes("URL") ||
                      parseError.message.includes("not found")) {
                    throw parseError;
                  }
                }
                // Otherwise, ignore parse errors for incomplete chunks
              }
            }
          }
        }

        // Finalize message
        setStreamingMessage(null);

        // Wait a bit for backend to save the message, especially for images
        if (imageUrl) {
          await new Promise(resolve => setTimeout(resolve, 500));
        }

        // Reload messages to get the saved versions
        await loadMessages(sessionId);
        
        // Refresh credits
        await refreshCredits();
      } catch (error: any) {
        console.error("Error sending message:", error);
        setStreamingMessage(null);
        // Remove optimistic user message on error
        setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
        
        // Show user-friendly error message
        const errorMessage = error.message || "Mesaj gönderilirken bir hata oluştu. Lütfen tekrar deneyin.";
        if (errorMessage.includes("credits") || errorMessage.includes("kredi")) {
          alert(errorMessage + "\n\nKredi satın almak için pricing sayfasına gidebilirsiniz.");
        } else {
          alert(errorMessage);
        }
      } finally {
        setIsSending(false);
      }
    },
    [user, currentSession, isSending, modelMode, refreshCredits]
  );

  const handleEditMessage = useCallback(
    async (messageId: string, newContent: string) => {
      if (!user || !currentSession || isSending) return;

      setIsSending(true);
      setStreamingMessage({
        id: `stream-${Date.now()}`,
        role: "assistant",
        content: "",
        model_used: null,
        isStreaming: true,
      });

      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;

        const response = await fetch(apiUrl("api/chat/edit"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message_id: messageId,
            new_content: newContent,
            session_id: currentSession.id,
          }),
        });

        if (!response.ok) {
          throw new Error("Failed to edit message");
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) throw new Error("No response body");

        let fullContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;

              try {
                const parsed = JSON.parse(data);
                
                // Handle different response types
                if (parsed.type === "error") {
                  throw new Error(parsed.error || "Bir hata oluştu");
                } else if (parsed.content) {
                  fullContent += parsed.content;
                  setStreamingMessage((prev) =>
                    prev
                      ? { ...prev, content: fullContent, model_used: parsed.model }
                      : null
                  );
                }
              } catch (parseError) {
                // Ignore parse errors for incomplete chunks
                if (parseError instanceof Error && parseError.message.includes("hata")) {
                  throw parseError;
                }
              }
            }
          }
        }

        setStreamingMessage(null);
        await loadMessages(currentSession.id);
        await refreshCredits();
      } catch (error: any) {
        console.error("Error editing message:", error);
        setStreamingMessage(null);
        const errorMessage = error.message || "Mesaj düzenlenirken bir hata oluştu. Lütfen tekrar deneyin.";
        alert(errorMessage);
      } finally {
        setIsSending(false);
      }
    },
    [user, currentSession, isSending, refreshCredits]
  );

  const handleGenerateImage = useCallback(
    async (prompt: string) => {
      if (!user || !currentSession || isSending) return;

      // Create session if none exists
      let sessionId = currentSession?.id;
      if (!sessionId) {
        try {
          const newSession = await createChatSession(user.id);
          setSessions((prev) => [newSession, ...prev]);
          setCurrentSession(newSession);
          sessionId = newSession.id;
        } catch (error) {
          console.error("Error creating session:", error);
          return;
        }
      }

      setIsSending(true);

      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;

        const response = await fetch(apiUrl("api/chat/generate-image"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            prompt,
            session_id: sessionId,
            size: "1024x1024",
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "Failed to generate image");
        }

        const result = await response.json();

        // Reload messages to show the new image
        await loadMessages(sessionId);
        await refreshCredits();
      } catch (error: any) {
        console.error("Error generating image:", error);
        const errorMessage = error.message || "Görsel oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.";
        if (errorMessage.includes("credits") || errorMessage.includes("kredi")) {
          alert(errorMessage + "\n\nGörsel oluşturmak için en az 10 kredi gereklidir.");
        } else {
          alert(errorMessage);
        }
      } finally {
        setIsSending(false);
      }
    },
    [user, currentSession, isSending, refreshCredits]
  );

  const handleRegenerate = useCallback(
    async (messageId: string) => {
      if (!user || !currentSession || isSending) return;

      // Find the assistant message and the user message before it
      const messageIndex = messages.findIndex((m) => m.id === messageId);
      if (messageIndex === -1 || messageIndex === 0) return;

      const assistantMessage = messages[messageIndex];
      const userMessage = messages[messageIndex - 1];

      if (userMessage.role !== "user" || assistantMessage.role !== "assistant") return;

      // Delete the assistant message by editing the user message (this deletes all after)
      setIsSending(true);
      
      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;

        // Use edit endpoint to delete assistant message and regenerate
        const response = await fetch(apiUrl("api/chat/edit"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message_id: userMessage.id,
            new_content: userMessage.content,
            session_id: currentSession.id,
          }),
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Failed to regenerate" }));
          throw new Error(error.detail || "Failed to regenerate");
        }

        // Initialize streaming message
        setStreamingMessage({
          id: `stream-${Date.now()}`,
          role: "assistant",
          content: "",
          model_used: null,
          isStreaming: true,
        });

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) throw new Error("No response body");

        let fullContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;

              try {
                const parsed = JSON.parse(data);
                if (parsed.content) {
                  fullContent += parsed.content;
                  setStreamingMessage((prev) =>
                    prev
                      ? { ...prev, content: fullContent, model_used: parsed.model }
                      : null
                  );
                }
                if (parsed.error) {
                  throw new Error(parsed.error);
                }
              } catch (parseError) {
                // Ignore parse errors for incomplete chunks
                if (parseError instanceof Error && parseError.message.includes("error")) {
                  throw parseError;
                }
              }
            }
          }
        }

        setStreamingMessage(null);
        await loadMessages(currentSession.id);
        await refreshCredits();
      } catch (error: any) {
        console.error("Error regenerating:", error);
        setStreamingMessage(null);
        alert(error.message || "Yeniden oluşturma başarısız oldu");
      } finally {
        setIsSending(false);
      }
    },
    [user, currentSession, isSending, messages, refreshCredits]
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gradient-bg">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="h-screen flex gradient-bg overflow-hidden relative">
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 sm:hidden"
          />
        )}
      </AnimatePresence>
      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-r border-border/50 bg-card/30 backdrop-blur-sm fixed sm:relative inset-y-0 left-0 z-50 h-screen w-[280px]"
          >
            <ChatSidebar
              sessions={sessions}
              currentSession={currentSession}
              onNewChat={handleNewChat}
              onSelectSession={handleSelectSession}
              onDeleteSession={handleDeleteSession}
              isLoading={isLoading}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatHeader
          credits={credits}
          modelMode={modelMode}
          onModelModeChange={setModelMode}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <ChatMessages
          messages={messages}
          streamingMessage={streamingMessage}
          messagesEndRef={messagesEndRef}
          onEditMessage={handleEditMessage}
          onGenerateImage={handleGenerateImage}
          onRegenerate={handleRegenerate}
          sessionId={currentSession?.id}
          credits={credits}
        />

        <ChatInput
          onSend={handleSendMessage}
          disabled={isSending}
          credits={credits}
        />
        
        {/* Footer */}
        <div className="text-center py-2 text-xs text-muted-foreground">
          Chatow hata yapabilir. Önemli bilgileri kontrol edin.
        </div>
      </div>
    </div>
  );
}
