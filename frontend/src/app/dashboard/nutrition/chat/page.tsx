"use client";

import { useState, useRef, useEffect } from "react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Bot,
  User,
  Send,
  Loader2,
  Sparkles,
  RefreshCw
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  processingTime?: number;
  cost?: number;
  timestamp: Date;
}

export default function NutritionChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hi! I'm your AI nutrition assistant powered by LangGraph! 🚀 I have access to all your nutrition data and can remember our conversation. Try:\n\n• \"How is my protein intake today?\"\n• \"What if I eat 2 samosas?\"\n• \"Suggest a high-protein lunch\"\n• \"Log 2 eggs for breakfast\"",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => {
    // Generate or retrieve session ID
    const stored = localStorage.getItem("chat_session_id");
    if (stored) return stored;
    const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("chat_session_id", newSessionId);
    return newSessionId;
  });
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const startNewChat = () => {
    const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    localStorage.setItem("chat_session_id", newSessionId);
    setSessionId(newSessionId);
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "Hi! I'm your AI nutrition assistant powered by LangGraph! 🚀 I have access to all your nutrition data and can remember our conversation. Try:\n\n• \"How is my protein intake today?\"\n• \"What if I eat 2 samosas?\"\n• \"Suggest a high-protein lunch\"\n• \"Log 2 eggs for breakfast\"",
        timestamp: new Date(),
      },
    ]);
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch("http://localhost:8000/api/nutrition/chat/v2", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query: userMessage.content,
          include_context: true,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const data = await response.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        intent: data.intent,
        processingTime: data.processing_time_ms,
        cost: data.cost_usd,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const getIntentBadgeVariant = (intent?: string) => {
    switch (intent) {
      case "stats":
        return "default";
      case "what_if":
        return "secondary";
      case "meal_suggestion":
        return "outline";
      case "meal_plan":
        return "default";
      case "inventory":
        return "secondary";
      case "conversational":
        return "outline";
      default:
        return "default";
    }
  };

  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 h-[calc(100vh-6rem)]">
        <Card className="h-full flex flex-col">
          <CardHeader className="border-b">
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="h-6 w-6 text-primary" />
                  AI Nutrition Assistant
                  <Badge variant="outline">
                    <Sparkles className="h-3 w-3 mr-1" />
                    V2 - LangGraph
                  </Badge>
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  Ask me anything about your nutrition, meals, or fitness goals
                </p>
              </div>
              <Button
                onClick={startNewChat}
                variant="outline"
                size="sm"
                className="flex-shrink-0"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                New Chat
              </Button>
            </div>
          </CardHeader>

          <CardContent className="flex-1 flex flex-col p-0">
            {/* Messages Area */}
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={cn(
                      "flex gap-3",
                      message.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    {message.role === "assistant" && (
                      <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <Bot className="h-5 w-5 text-primary" />
                      </div>
                    )}

                    <div
                      className={cn(
                        "rounded-lg px-4 py-2 max-w-[80%]",
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted"
                      )}
                    >
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                      {/* Metadata for assistant messages */}
                      {message.role === "assistant" && message.intent && (
                        <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-border/50">
                          {message.intent && (
                            <Badge variant={getIntentBadgeVariant(message.intent)} className="text-xs">
                              {message.intent}
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>

                    {message.role === "user" && (
                      <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                        <User className="h-5 w-5 text-primary-foreground" />
                      </div>
                    )}
                  </div>
                ))}

                {isLoading && (
                  <div className="flex gap-3 justify-start">
                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Bot className="h-5 w-5 text-primary" />
                    </div>
                    <div className="rounded-lg px-4 py-3 bg-muted">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm text-muted-foreground">Thinking...</span>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={scrollRef} />
              </div>
            </ScrollArea>

            {/* Input Area */}
            <div className="border-t p-4">
              <div className="flex gap-2">
                <Textarea
                  ref={inputRef}
                  placeholder="Ask me anything about your nutrition..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  className="resize-none min-h-[40px] max-h-[120px]"
                  disabled={isLoading}
                />
                <Button
                  onClick={sendMessage}
                  disabled={isLoading || !input.trim()}
                  size="icon"
                  className="h-10 w-10 flex-shrink-0"
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Press Enter to send, Shift+Enter for new line
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
