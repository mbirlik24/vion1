"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { User, Bot, Zap, Brain, Copy, Check, Edit2, Image as ImageIcon, ShoppingCart, AlertCircle, Share2, RotateCw, MoreVertical } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/database";
import { useState, useEffect } from "react";

interface StreamingMessage {
  id: string;
  role: "assistant";
  content: string;
  model_used: string | null;
  isStreaming: boolean;
  credits_used?: number;
}

interface ChatMessagesProps {
  messages: ChatMessage[];
  streamingMessage: StreamingMessage | null;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  onEditMessage?: (messageId: string, newContent: string) => void;
  onGenerateImage?: (prompt: string) => void;
  onRegenerate?: (messageId: string) => void;
  sessionId?: string;
  credits?: number;
}

function ModelBadge({ model }: { model: string | null }) {
  if (!model) return null;

  const isFast = model.includes("mini") || model.includes("4o-mini");
  const Icon = isFast ? Zap : Brain;
  const label = isFast ? `Fast (${model})` : `Pro (${model})`;
  const colorClass = "text-foreground bg-muted";

  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium", colorClass)}>
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7"
      onClick={handleCopy}
      title="Mesajı kopyala"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-primary" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </Button>
  );
}

function MessageContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      className="markdown-content prose prose-invert max-w-none"
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        code({ node, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          const isInline = !match;
          
          if (isInline) {
            return (
              <code className="bg-muted px-1.5 py-0.5 rounded text-sm" {...props}>
                {children}
              </code>
            );
          }

          return (
            <div className="relative group my-4">
              <div className="absolute right-2 top-2 z-10">
                <CopyButton text={String(children).replace(/\n$/, "")} />
              </div>
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                className="rounded-lg !bg-muted !my-0"
              >
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            </div>
          );
        },
        pre({ children }) {
          return <>{children}</>;
        },
        img({ node, src, alt, ...props }) {
          return (
            <div className="my-4 rounded-lg overflow-hidden border border-border/50 bg-muted/30">
              <img
                src={src}
                alt={alt || "Generated image"}
                className="w-full h-auto max-w-2xl mx-auto block"
                loading="lazy"
                {...props}
              />
              {alt && alt !== "Generated image" && (
                <div className="px-4 py-2 text-sm text-muted-foreground bg-muted/50">
                  {alt}
                </div>
              )}
            </div>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function Message({
  message,
  isStreaming = false,
  onEditMessage,
  onGenerateImage,
  onRegenerate,
  sessionId,
}: {
  message: ChatMessage | StreamingMessage;
  isStreaming?: boolean;
  onEditMessage?: (messageId: string, newContent: string) => void;
  onGenerateImage?: (prompt: string) => void;
  onRegenerate?: (messageId: string) => void;
  sessionId?: string;
}) {
  const isUser = message.role === "user";
  const creditsUsed =
    "credits_used" in message ? message.credits_used : undefined;
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  // Update editContent when message content changes
  useEffect(() => {
    setEditContent(message.content);
  }, [message.content]);

  const handleSaveEdit = () => {
    if (editContent.trim() && editContent !== message.content && onEditMessage && "id" in message) {
      onEditMessage(message.id, editContent.trim());
      setIsEditing(false);
    } else {
      setIsEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  const handleShare = async () => {
    try {
      if (navigator.share) {
        await navigator.share({
          title: "Chatow Message",
          text: message.content,
        });
      } else {
        // Fallback: copy to clipboard
        await navigator.clipboard.writeText(message.content);
        alert("Mesaj panoya kopyalandı!");
      }
    } catch (err) {
      // User cancelled or error - try clipboard fallback
      try {
        await navigator.clipboard.writeText(message.content);
        alert("Mesaj panoya kopyalandı!");
      } catch (clipboardErr) {
        console.error("Failed to share or copy:", clipboardErr);
      }
    }
  };

  const handleRegenerate = () => {
    if (onRegenerate && "id" in message && !isUser) {
      onRegenerate(message.id);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "group flex gap-3 sm:gap-4 px-3 sm:px-4 py-4 sm:py-6",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* Avatar - left side for assistant messages */}
      {!isUser && (
        <div
          className={cn(
            "shrink-0 h-8 w-8 rounded-full flex items-center justify-center",
            "bg-muted"
          )}
        >
          <Bot className="h-4 w-4 text-foreground" />
        </div>
      )}
      
      <div className={cn(
        "flex-1 min-w-0 space-y-2",
        isUser ? "flex flex-col items-end" : "flex flex-col items-start",
        isUser && "max-w-[80%] sm:max-w-[70%]"
      )}>
        <div className={cn(
          "text-sm leading-relaxed relative w-full",
          isUser && "flex flex-col items-end"
        )}>
          {isEditing && isUser && "id" in message ? (
            <div className="space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full p-2 rounded-lg bg-muted border border-border resize-none min-h-[100px]"
                autoFocus
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleSaveEdit}
                  className="h-8"
                  disabled={!editContent.trim() || editContent.trim() === message.content}
                >
                  Save
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleCancelEdit}
                  className="h-8"
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              {message.content ? (
                <div className={cn(
                  "space-y-2 w-full",
                  isUser && "flex flex-col items-end"
                )}>
                  {isUser ? (
                    <div className="flex flex-col items-end gap-2">
                      <div className="rounded-2xl px-4 py-2.5 bg-muted/60 text-foreground">
                        <MessageContent content={message.content} />
                      </div>
                      {/* Action buttons - always visible below user message */}
                      {!isStreaming && "id" in message && !isEditing && (
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setIsEditing(true)}
                            title="Düzenle"
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </Button>
                          <CopyButton text={message.content} />
                        </div>
                      )}
                    </div>
                  ) : (
                    <>
                      {/* Model badge - show which model was used */}
                      {message.model_used && (
                        <div className="mb-2">
                          <ModelBadge model={message.model_used} />
                        </div>
                      )}
                      <div className="text-foreground">
                        <MessageContent content={message.content} />
                      </div>
                      {/* Action buttons - always visible for assistant messages */}
                      {!isStreaming && (
                        <div className="flex items-center gap-1 flex-wrap">
                          <CopyButton text={message.content} />
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={handleShare}
                            title="Paylaş"
                          >
                            <Share2 className="h-3.5 w-3.5" />
                          </Button>
                          {onRegenerate && "id" in message && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={handleRegenerate}
                              title="Yeniden oluştur"
                            >
                              <RotateCw className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                title="Daha fazla"
                              >
                                <MoreVertical className="h-3.5 w-3.5" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={async () => {
                                await navigator.clipboard.writeText(message.content);
                                alert("Mesaj panoya kopyalandı!");
                              }}>
                                <Copy className="h-4 w-4 mr-2" />
                                Kopyala
                              </DropdownMenuItem>
                              {onRegenerate && "id" in message && (
                                <DropdownMenuItem onClick={handleRegenerate}>
                                  <RotateCw className="h-4 w-4 mr-2" />
                                  Yeniden oluştur
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuItem onClick={handleShare}>
                                <Share2 className="h-4 w-4 mr-2" />
                                Paylaş
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ) : isStreaming ? (
                <div className="space-y-2">
                  {/* Show model badge if available during streaming */}
                  {message.model_used && (
                    <div>
                      <ModelBadge model={message.model_used} />
                    </div>
                  )}
                  <div className="typing-indicator flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                  </div>
                </div>
              ) : null}
              
              {isStreaming && message.content && (
                <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-0.5" />
              )}
            </>
          )}
        </div>
      </div>

      {/* Avatar - right side for user messages */}
      {isUser && (
        <div
          className={cn(
            "shrink-0 h-8 w-8 rounded-full flex items-center justify-center",
            "bg-primary"
          )}
        >
          <User className="h-4 w-4 text-primary-foreground" />
        </div>
      )}
    </motion.div>
  );
}

export function ChatMessages({
  messages,
  streamingMessage,
  messagesEndRef,
  onEditMessage,
  onGenerateImage,
  onRegenerate,
  sessionId,
  credits = 0,
}: ChatMessagesProps) {
  const router = useRouter();
  const allMessages = [
    ...messages,
    ...(streamingMessage ? [streamingMessage] : []),
  ];

  const hasNoCredits = !credits || Number(credits) <= 0;

  if (allMessages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-4 sm:p-8 relative overflow-hidden">
        {/* Animated background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-primary/5 animate-pulse" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(120,119,198,0.1),transparent_50%)]" />
        
        <div className="text-center max-w-md relative z-10">
          <motion.div 
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ 
              type: "spring", 
              stiffness: 200, 
              damping: 15,
              delay: 0.1
            }}
            className="mb-8 relative"
          >
            <div className="h-24 w-24 mx-auto rounded-full bg-gradient-to-br from-primary via-primary/80 to-primary/60 flex items-center justify-center shadow-2xl shadow-primary/20 relative">
              <motion.div
                animate={{ 
                  scale: [1, 1.1, 1],
                  opacity: [0.5, 0.8, 0.5]
                }}
                transition={{ 
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
                className="absolute inset-0 rounded-full bg-primary/30 blur-xl"
              />
              <Bot className="h-12 w-12 text-primary-foreground relative z-10" />
            </div>
            {/* Floating particles */}
            {[...Array(3)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute top-0 left-0 w-full h-full"
                initial={{ opacity: 0 }}
                animate={{ 
                  opacity: [0, 1, 0],
                  x: [0, Math.random() * 100 - 50],
                  y: [0, Math.random() * 100 - 50],
                }}
                transition={{
                  duration: 3 + i,
                  repeat: Infinity,
                  delay: i * 0.5,
                  ease: "easeInOut"
                }}
              >
                <div className="w-2 h-2 rounded-full bg-primary/40 absolute top-1/2 left-1/2" />
              </motion.div>
            ))}
          </motion.div>
          
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="text-4xl sm:text-5xl font-bold mb-4 bg-gradient-to-r from-foreground via-primary to-foreground bg-clip-text text-transparent"
          >
            Welcome to Chatow
          </motion.h2>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="text-muted-foreground mb-8 text-lg leading-relaxed"
          >
            Start a conversation and I'll automatically route to the best model
            for your needs. You can edit messages, generate images, and more!
          </motion.p>
          
          {hasNoCredits ? (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ delay: 0.5, duration: 0.5 }}
              className="mb-6 p-6 rounded-xl bg-gradient-to-br from-destructive/10 via-destructive/5 to-destructive/10 border border-destructive/30 backdrop-blur-sm shadow-xl"
            >
              <motion.div 
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="flex items-center justify-center gap-2 text-destructive mb-4"
              >
                <AlertCircle className="h-6 w-6" />
                <p className="font-semibold text-lg">Krediniz yok</p>
              </motion.div>
              <p className="text-sm text-muted-foreground mb-5 text-center">
                Devam etmek için kredi satın almanız gerekiyor.
              </p>
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Button
                  onClick={() => router.push("/pricing")}
                  className="w-full bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 text-primary-foreground shadow-lg hover:shadow-xl transition-all duration-300"
                >
                  <ShoppingCart className="h-4 w-4 mr-2" />
                  Kredi Satın Al
                </Button>
              </motion.div>
            </motion.div>
          ) : (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.5 }}
              className="grid gap-4 text-sm"
            >
            <motion.div 
              whileHover={{ scale: 1.02, y: -2 }}
              transition={{ type: "spring", stiffness: 300 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-card/80 to-card/40 border border-border/50 backdrop-blur-sm shadow-lg hover:shadow-xl hover:border-primary/30 transition-all duration-300 group cursor-pointer"
            >
              <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                <Zap className="h-6 w-6 text-primary shrink-0" />
              </div>
              <div className="text-left flex-1">
                <p className="font-semibold text-base mb-1">Fast Mode</p>
                <p className="text-muted-foreground text-xs">
                  Simple questions, quick answers (1 credit)
                </p>
              </div>
            </motion.div>
            <motion.div 
              whileHover={{ scale: 1.02, y: -2 }}
              transition={{ type: "spring", stiffness: 300 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-card/80 to-card/40 border border-border/50 backdrop-blur-sm shadow-lg hover:shadow-xl hover:border-primary/30 transition-all duration-300 group cursor-pointer"
            >
              <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                <Brain className="h-6 w-6 text-primary shrink-0" />
              </div>
              <div className="text-left flex-1">
                <p className="font-semibold text-base mb-1">Pro Mode</p>
                <p className="text-muted-foreground text-xs">
                  Complex tasks, coding, analysis (20 credits)
                </p>
              </div>
            </motion.div>
            <motion.div 
              whileHover={{ scale: 1.02, y: -2 }}
              transition={{ type: "spring", stiffness: 300 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-card/80 to-card/40 border border-border/50 backdrop-blur-sm shadow-lg hover:shadow-xl hover:border-primary/30 transition-all duration-300 group cursor-pointer"
            >
              <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                <ImageIcon className="h-6 w-6 text-primary shrink-0" />
              </div>
              <div className="text-left flex-1">
                <p className="font-semibold text-base mb-1">Image Generation</p>
                <p className="text-muted-foreground text-xs">
                  Generate images with DALL-E 3 (10 credits)
                </p>
              </div>
            </motion.div>
          </motion.div>
          )}
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="max-w-3xl mx-auto">
        {allMessages.map((message, index) => (
          <Message
            key={message.id}
            message={message}
            isStreaming={
              streamingMessage?.id === message.id && streamingMessage.isStreaming
            }
            onEditMessage={onEditMessage}
            onGenerateImage={onGenerateImage}
            onRegenerate={onRegenerate}
            sessionId={sessionId}
          />
        ))}
        <div ref={messagesEndRef} className="h-4" />
      </div>
    </ScrollArea>
  );
}
