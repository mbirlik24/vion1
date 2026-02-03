"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Send, Loader2, AlertCircle, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  credits: number;
}

export function ChatInput({ onSend, disabled, credits }: ChatInputProps) {
  const router = useRouter();
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !disabled && credits > 0) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const insufficientCredits = !credits || Number(credits) <= 0;

  return (
    <div className="border-t border-border/50 bg-card/30 backdrop-blur-sm p-3 sm:p-4">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
        {insufficientCredits && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-3 flex items-center justify-between gap-3 p-3 rounded-lg bg-destructive/10 border border-destructive/30"
          >
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <p className="text-sm">
                Krediniz bitti. Devam etmek için kredi satın alın.
              </p>
            </div>
            <Button
              onClick={() => router.push("/pricing")}
              size="sm"
              className="bg-primary hover:bg-primary/90 text-primary-foreground shrink-0"
            >
              <ShoppingCart className="h-4 w-4 mr-2" />
              Kredi Al
            </Button>
          </motion.div>
        )}

        <div
          className={cn(
            "relative flex items-end gap-2 rounded-2xl border bg-background/50 p-2 transition-all",
            "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background",
            insufficientCredits && "opacity-50"
          )}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              insufficientCredits
                ? "Kredi satın alın..."
                : "Mesaj yazın veya görsel oluşturun (örn: 'bir kedi resmi oluştur')..."
            }
            disabled={disabled || insufficientCredits}
            rows={1}
            className={cn(
              "flex-1 resize-none bg-transparent px-3 py-2 text-sm",
              "placeholder:text-muted-foreground",
              "focus:outline-none",
              "disabled:cursor-not-allowed"
            )}
          />

          <div className="flex gap-1">
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || disabled || insufficientCredits}
              className={cn(
                "shrink-0 h-9 w-9",
                "bg-primary hover:bg-primary/90 text-primary-foreground",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {disabled ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        <p className="text-xs text-muted-foreground text-center mt-2 hidden sm:block">
          <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs">Enter</kbd> ile gönder,{" "}
          <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs">Shift + Enter</kbd> ile yeni satır. 
          Görsel oluşturmak için "resim oluştur" veya "generate image" yazın.
        </p>
      </form>
    </div>
  );
}
