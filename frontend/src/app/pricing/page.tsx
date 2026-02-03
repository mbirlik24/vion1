"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Sparkles, Zap, Brain, Check, ArrowRight } from "lucide-react";

interface PricingPlan {
  id: string;
  name: string;
  credits: number;
  price: number;
  description: string;
  features: string[];
  popular?: boolean;
  lemonSqueezyVariantId?: string;
}

const pricingPlans: PricingPlan[] = [
  {
    id: "starter",
    name: "Starter",
    credits: 1000,
    price: 5,
    description: "Perfect for trying out Chatow",
    features: [
      "1,000 credits",
      "Fast & Pro mode access",
      "Smart model routing",
      "Email support",
    ],
    lemonSqueezyVariantId: process.env.NEXT_PUBLIC_LEMON_SQUEEZY_STARTER_VARIANT_ID || "",
  },
  {
    id: "pro",
    name: "Pro",
    credits: 5000,
    price: 20,
    description: "Best for regular users",
    features: [
      "5,000 credits",
      "Fast & Pro mode access",
      "Smart model routing",
      "Priority support",
      "Better value per credit",
    ],
    popular: true,
    lemonSqueezyVariantId: process.env.NEXT_PUBLIC_LEMON_SQUEEZY_PRO_VARIANT_ID || "",
  },
  {
    id: "unlimited",
    name: "Unlimited",
    credits: 25000,
    price: 80,
    description: "For power users",
    features: [
      "25,000 credits",
      "Fast & Pro mode access",
      "Smart model routing",
      "Priority support",
      "Best value per credit",
    ],
    lemonSqueezyVariantId: process.env.NEXT_PUBLIC_LEMON_SQUEEZY_UNLIMITED_VARIANT_ID || "",
  },
];

export default function PricingPage() {
  const router = useRouter();
  const { user, credits, loading } = useAuth();
  const { toast } = useToast();
  const [isProcessing, setIsProcessing] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  const handlePurchase = async (plan: PricingPlan) => {
    if (!user) {
      router.push("/login");
      return;
    }

    if (!plan.lemonSqueezyVariantId) {
      toast({
        title: "Configuration Error",
        description: "Payment system not configured. Please contact support.",
        variant: "destructive",
      });
      return;
    }

    setIsProcessing(true);

    try {
      // Get Lemon Squeezy store URL from environment
      const storeUrl = process.env.NEXT_PUBLIC_LEMON_SQUEEZY_STORE_URL;
      
      if (!storeUrl) {
        throw new Error("Lemon Squeezy store URL not configured");
      }

      // Redirect to Lemon Squeezy checkout
      // Include user email in custom data for webhook processing
      const checkoutUrl = `${storeUrl}/checkout/buy/${plan.lemonSqueezyVariantId}?checkout[custom][user_email]=${encodeURIComponent(user.email || "")}`;
      
      window.location.href = checkoutUrl;
    } catch (error: any) {
      console.error("Error initiating purchase:", error);
      toast({
        title: "Error",
        description: error.message || "Failed to start checkout process",
        variant: "destructive",
      });
      setIsProcessing(false);
    }
  };

  const handleSkip = () => {
    // Allow users to skip and go to chat (they'll see they need credits)
    router.push("/chat");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gradient-bg">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen gradient-bg py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <Sparkles className="h-10 w-10 text-primary" />
            <h1 className="text-4xl font-bold text-foreground">Get Started with Chatow</h1>
          </div>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Choose a credit package to start chatting with AI. Pay only for what you use.
          </p>
          {credits > 0 && (
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary">
              <span className="text-sm font-medium">Current balance: {credits.toLocaleString()} credits</span>
            </div>
          )}
        </motion.div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 mb-8">
          {pricingPlans.map((plan, index) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`relative bg-card/80 backdrop-blur-xl rounded-2xl border-2 p-8 ${
                plan.popular
                  ? "border-primary shadow-2xl scale-105"
                  : "border-border/50"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary text-primary-foreground rounded-full text-sm font-semibold">
                  Most Popular
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                <p className="text-muted-foreground text-sm mb-4">{plan.description}</p>
                <div className="mb-4">
                  <span className="text-4xl font-bold">{plan.price}$</span>
                  <span className="text-muted-foreground ml-2">one-time</span>
                </div>
                <div className="text-lg font-semibold text-primary">
                  {plan.credits.toLocaleString()} credits
                </div>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                onClick={() => handlePurchase(plan)}
                disabled={isProcessing}
                className={`w-full ${
                  plan.popular
                    ? "bg-primary hover:bg-primary/90"
                    : "bg-secondary hover:bg-secondary/80"
                }`}
              >
                {isProcessing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    Get Started <ArrowRight className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
            </motion.div>
          ))}
        </div>

        {/* Info Section */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="max-w-3xl mx-auto bg-card/50 backdrop-blur border border-border/50 rounded-xl p-6"
        >
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            How Credits Work
          </h3>
          <div className="grid md:grid-cols-2 gap-4 text-sm text-muted-foreground">
            <div>
              <p className="font-medium text-foreground mb-1">Fast Mode</p>
              <p>Simple questions use ~1 credit per message</p>
            </div>
            <div>
              <p className="font-medium text-foreground mb-1">Pro Mode</p>
              <p>Complex tasks use ~20 credits per message</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-4">
            Credits never expire. You only pay for what you use.
          </p>
        </motion.div>

        {/* Skip Button (for users who want to explore first) */}
        {credits === 0 && (
          <div className="text-center mt-8">
            <button
              onClick={handleSkip}
              className="text-sm text-muted-foreground hover:text-primary transition-colors"
            >
              Skip for now (you'll need credits to chat)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
