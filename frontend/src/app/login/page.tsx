"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Sparkles, Zap, Brain } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        
        // If user is created and session is available, redirect to pricing
        if (data.user && data.session) {
          toast({
            title: "Account created!",
            description: "Redirecting to pricing to get started...",
          });
          // Small delay to show toast
          setTimeout(() => {
            router.push("/pricing");
          }, 1000);
        } else {
          toast({
            title: "Account created!",
            description: "Please check your email to verify your account.",
          });
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        
        // Check user credits and redirect accordingly
        const { data: { user: signedInUser } } = await supabase.auth.getUser();
        if (signedInUser) {
          const { data: profile } = await supabase
            .from("profiles")
            .select("credit_balance")
            .eq("id", signedInUser.id)
            .single();
          
          // Redirect to pricing if user has 0 credits
          if (profile && profile.credit_balance === 0) {
            router.push("/pricing");
          } else {
            router.push("/chat");
          }
        } else {
          router.push("/chat");
        }
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Something went wrong",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex gradient-bg lg:flex-row flex-col">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center p-12 relative overflow-hidden">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="relative z-10 text-center"
        >
          <div className="flex items-center justify-center gap-3 mb-8">
            <Sparkles className="h-12 w-12 text-primary" />
            <h1 className="text-5xl font-bold text-foreground">
              Chatow
            </h1>
          </div>
          
          <p className="text-xl text-muted-foreground mb-12 max-w-md">
            Experience intelligent AI chat with smart model routing. 
            Pay only for what you use.
          </p>

          <div className="grid gap-6 max-w-sm mx-auto">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-card/50 backdrop-blur border border-border/50"
            >
              <div className="p-2 rounded-lg bg-muted">
                <Zap className="h-6 w-6 text-foreground" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold">Fast Mode</h3>
                <p className="text-sm text-muted-foreground">Quick responses for simple tasks</p>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-card/50 backdrop-blur border border-border/50"
            >
              <div className="p-2 rounded-lg bg-muted">
                <Brain className="h-6 w-6 text-foreground" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold">Pro Mode</h3>
                <p className="text-sm text-muted-foreground">Advanced reasoning with GPT-5.2</p>
              </div>
            </motion.div>
          </div>
        </motion.div>
      </div>

      {/* Right side - Login form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-4 sm:p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-md"
        >
          <div className="bg-card/80 backdrop-blur-xl rounded-2xl border border-border/50 p-6 sm:p-8 shadow-2xl w-full">
            <div className="text-center mb-8">
              <div className="lg:hidden flex items-center justify-center gap-2 mb-4">
                <Sparkles className="h-8 w-8 text-primary" />
                <span className="text-2xl font-bold">Chatow</span>
              </div>
              <h2 className="text-2xl font-bold">
                {isSignUp ? "Create an account" : "Welcome back"}
              </h2>
              <p className="text-muted-foreground mt-2">
                {isSignUp
                  ? "Start chatting with AI today"
                  : "Sign in to continue to Chatow"}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-background/50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="bg-background/50"
                />
              </div>

              <Button
                type="submit"
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : isSignUp ? (
                  "Create Account"
                ) : (
                  "Sign In"
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => setIsSignUp(!isSignUp)}
                className="text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                {isSignUp
                  ? "Already have an account? Sign in"
                  : "Don't have an account? Sign up"}
              </button>
            </div>

            {/* Test account hint */}
            <div className="mt-6 p-4 rounded-lg bg-muted/50 border border-border/50">
              <p className="text-xs text-muted-foreground text-center">
                <strong>Test Account:</strong> admin@test.com / test123456
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
