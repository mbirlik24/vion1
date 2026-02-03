"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Sparkles,
  Menu,
  LogOut,
  Coins,
  Zap,
  Brain,
  Wand2,
  Upload,
  Share2,
  MoreVertical,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/components/providers/auth-provider";
import { formatCredits, cn } from "@/lib/utils";
import type { ModelMode } from "@/app/chat/page";

interface ChatHeaderProps {
  credits: number;
  modelMode: ModelMode;
  onModelModeChange: (mode: ModelMode) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

const modeConfig = {
  auto: {
    label: "Auto",
    icon: Wand2,
    description: "Smart routing",
    color: "text-primary",
    bg: "bg-primary/10",
  },
  fast: {
    label: "Fast",
    icon: Zap,
    description: "1 credit/msg",
    color: "text-foreground",
    bg: "bg-muted",
  },
  pro: {
    label: "Pro 5.2",
    icon: Brain,
    description: "20 credits/msg",
    color: "text-foreground",
    bg: "bg-muted",
  },
};

export function ChatHeader({
  credits,
  modelMode,
  onModelModeChange,
  sidebarOpen,
  onToggleSidebar,
}: ChatHeaderProps) {
  const router = useRouter();
  const { signOut, user } = useAuth();

  const handleSignOut = async () => {
    await signOut();
    router.push("/login");
  };

  const currentMode = modeConfig[modelMode];
  const ModeIcon = currentMode.icon;

  return (
    <header className="h-14 border-b border-border/50 bg-card/30 backdrop-blur-sm flex items-center justify-between px-4">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleSidebar}
          className="shrink-0"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <span className="font-semibold text-lg">Chatow</span>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-9 w-9">
          <Upload className="h-5 w-5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-9 w-9">
          <Share2 className="h-5 w-5" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-9 w-9">
              <MoreVertical className="h-5 w-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleSignOut} className="text-destructive">
              <LogOut className="h-4 w-4 mr-2" />
              Çıkış Yap
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
