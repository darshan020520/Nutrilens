"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { motion as motionTokens } from "@/design/motion";
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Info,
  BrainCircuit,
  ArrowRight,
} from "lucide-react";
import { useAddItems, useConfirmItem } from "../hooks/useInventory";
import type { AddItemsResult } from "../types";

interface AddItemsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type AddItemsResults = AddItemsResult["results"];
type NeedsConfirmationItem = AddItemsResults["needs_confirmation"][number];
type SuccessfulItem = AddItemsResults["successful"][number];
type FailedItem = AddItemsResults["failed"][number];

const processingPhases = [
  "Parsing natural-language quantities and units",
  "Resolving inventory item matches with fuzzy confidence",
  "Preparing confirmations for medium-confidence entries",
];

export default function AddItemsDialog({ open, onOpenChange }: AddItemsDialogProps) {
  const [textInput, setTextInput] = useState("");
  const [results, setResults] = useState<AddItemsResults | null>(null);
  const [phaseIndex, setPhaseIndex] = useState(0);

  const addItems = useAddItems();
  const confirmItem = useConfirmItem();

  useEffect(() => {
    if (!addItems.isPending) return;
    const interval = window.setInterval(() => {
      setPhaseIndex((prev) => (prev + 1) % processingPhases.length);
    }, 850);
    return () => window.clearInterval(interval);
  }, [addItems.isPending]);

  const handleSubmit = async () => {
    if (!textInput.trim()) return;

    setPhaseIndex(0);
    const result = await addItems.mutateAsync({ text_input: textInput });
    setResults(result.results);
  };

  const handleConfirm = async (item: NeedsConfirmationItem, itemId: number) => {
    await confirmItem.mutateAsync({
      original_text: item.original,
      item_id: itemId,
      quantity_grams: item.quantity_grams ?? 0,
    });

    setResults((prev) => {
      if (!prev) return prev;

      return {
        ...prev,
        needs_confirmation: prev.needs_confirmation.filter((entry) => entry.original !== item.original),
        summary: {
          ...prev.summary,
          needs_confirmation: prev.summary.needs_confirmation - 1,
          successful: prev.summary.successful + 1,
        },
      };
    });
  };

  const handleClose = () => {
    setTextInput("");
    setResults(null);
    onOpenChange(false);
  };

  const hasResults = results !== null;
  const confirmableItems =
    results?.needs_confirmation?.filter(
      (item): item is NeedsConfirmationItem & { item_id: number } => typeof item.item_id === "number"
    ) || [];
  const pendingItems = results?.needs_confirmation?.filter((item) => item.action === "add_to_pending") || [];
  const hasConfirmations = confirmableItems.length > 0;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-600" />
            Add items to inventory
          </DialogTitle>
          <DialogDescription>
            Enter items in natural language. NutriLens AI will parse, normalize, and prepare confirmations.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-xl border border-cyan-200 bg-[linear-gradient(145deg,rgba(20,184,166,0.10),rgba(14,165,233,0.08))] px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">AI Item Pipeline</p>
            <p className="text-sm text-slate-700">Paste messy grocery text and let the parser handle normalization and confidence routing.</p>
          </div>

          {!hasResults && (
            <>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <strong>Examples:</strong> &quot;2 apples, 500g chicken breast, 1L milk&quot; or &quot;bananas x3, ground beef 1kg&quot;
                </AlertDescription>
              </Alert>

              <Textarea
                placeholder="E.g., 2 apples, 500g chicken, 1L milk, 250g cheddar cheese..."
                value={textInput}
                onChange={(event) => setTextInput(event.target.value)}
                rows={6}
                className="resize-none"
              />

              <AnimatePresence>
                {addItems.isPending && (
                  <motion.div
                    className="space-y-2 rounded-xl border border-cyan-200 bg-cyan-50/70 p-3"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: motionTokens.base, ease: motionTokens.easing }}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-700 flex items-center gap-1.5">
                      <BrainCircuit className="h-3.5 w-3.5" />
                      AI parser running
                    </p>
                    <p className="text-sm text-slate-700">{processingPhases[phaseIndex]}</p>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-cyan-100">
                      <motion.div
                        className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-500"
                        initial={{ width: "18%" }}
                        animate={{ width: "100%" }}
                        transition={{ duration: 1.25, ease: "easeInOut" }}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={!textInput.trim() || addItems.isPending}
                  className="bg-gradient-to-r from-teal-600 to-cyan-600 text-white hover:from-teal-500 hover:to-cyan-500"
                >
                  {addItems.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <span className="flex items-center">
                      <Sparkles className="mr-2 h-4 w-4" />
                      Analyze and add
                    </span>
                  )}
                </Button>
              </div>
            </>
          )}

          {hasResults && results && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <Card className="border-green-200 bg-green-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="mb-1 flex items-center justify-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      <span className="text-2xl font-bold text-green-700">{results.summary.successful}</span>
                    </div>
                    <p className="text-xs text-green-700">Added</p>
                  </CardContent>
                </Card>

                <Card className="border-yellow-200 bg-yellow-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="mb-1 flex items-center justify-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <span className="text-2xl font-bold text-yellow-700">{results.summary.needs_confirmation}</span>
                    </div>
                    <p className="text-xs text-yellow-700">Needs Confirmation</p>
                  </CardContent>
                </Card>

                <Card className="border-red-200 bg-red-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="mb-1 flex items-center justify-center gap-2">
                      <XCircle className="h-4 w-4 text-red-600" />
                      <span className="text-2xl font-bold text-red-700">{results.summary.failed}</span>
                    </div>
                    <p className="text-xs text-red-700">Unresolved</p>
                  </CardContent>
                </Card>
              </div>

              {results.successful.length > 0 && (
                <Card className="border-green-200">
                  <CardContent className="p-4">
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-green-700">
                      <CheckCircle2 className="h-4 w-4" />
                      Successfully added
                    </h4>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {results.successful.map((item: SuccessfulItem, index: number) => (
                        <div key={index} className="rounded-lg border bg-white p-2.5">
                          <p className="text-sm font-medium">{item.matched}</p>
                          <div className="mt-1 flex items-center justify-between">
                            <p className="text-xs text-muted-foreground">{item.quantity}</p>
                            <Badge variant="secondary" className="text-xs">
                              {(item.confidence * 100).toFixed(0)}%
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {confirmableItems.length > 0 && (
                <Card className="border-yellow-200">
                  <CardContent className="p-4">
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-yellow-700">
                      <AlertTriangle className="h-4 w-4" />
                      Confirm medium-confidence matches
                    </h4>
                    <div className="space-y-3">
                      {confirmableItems.map((item, index: number) => (
                        <Card key={`${item.original}-${index}`} className="border">
                          <CardContent className="p-3">
                            <div className="mb-2 flex items-start justify-between gap-3">
                              <div className="flex-1">
                                <p className="mb-1 text-xs text-muted-foreground">
                                  Input: &ldquo;{item.original}&rdquo;
                                </p>
                                <p className="font-medium">Suggested match: {item.suggested || item.suggested_name}</p>
                              </div>
                              <Badge variant="outline" className="text-xs">
                                {(item.confidence * 100).toFixed(0)}% match
                              </Badge>
                            </div>

                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full justify-between border-cyan-300 bg-cyan-50/50 text-cyan-900 hover:bg-cyan-100"
                      onClick={() => handleConfirm(item, item.item_id)}
                      disabled={confirmItem.isPending}
                    >
                              <span className="flex items-center gap-2">
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                                Confirm {item.suggested || item.suggested_name}
                              </span>
                              <ArrowRight className="h-3.5 w-3.5" />
                            </Button>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {pendingItems.length > 0 && (
                <Card className="border-purple-200 bg-purple-50/35">
                  <CardContent className="p-4">
                    <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-purple-700">
                      <Sparkles className="h-4 w-4" />
                      New items queued for catalog expansion
                    </h4>
                    <p className="mb-3 text-xs text-purple-700/80">
                      These entries were captured for database review and will become searchable once validated.
                    </p>
                    <div className="space-y-2">
                      {pendingItems.map((item, index: number) => (
                        <div
                          key={`${item.original}-${index}`}
                          className="flex items-center justify-between rounded-lg border border-purple-200 bg-white p-2.5"
                        >
                          <div>
                            <p className="text-sm font-medium">{item.suggested_name}</p>
                            <p className="text-xs text-muted-foreground">from &ldquo;{item.original}&rdquo;</p>
                          </div>
                          <Badge className="bg-purple-100 text-purple-700">Pending</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {results.failed.length > 0 && (
                <Card className="border-red-200">
                  <CardContent className="p-4">
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-700">
                      <XCircle className="h-4 w-4" />
                      Could not process
                    </h4>
                    <div className="space-y-2">
                      {results.failed.map((item: FailedItem, index: number) => (
                        <div key={index} className="rounded-lg border border-red-200 bg-red-50 p-2.5">
                          <p className="text-sm">&ldquo;{item.original || item.original_text}&rdquo;</p>
                          {(item.reason || item.error) && <p className="mt-1 text-xs text-red-600">{item.reason || item.error}</p>}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="flex justify-end gap-2 pt-2">
                {!hasConfirmations ? (
                  <Button className="bg-gradient-to-r from-teal-600 to-cyan-600 text-white hover:from-teal-500 hover:to-cyan-500" onClick={handleClose}>Done</Button>
                ) : (
                  <>
                    <Button variant="outline" onClick={handleClose}>
                      Finish Later
                    </Button>
                    <Button
                      className="bg-gradient-to-r from-teal-600 to-cyan-600 text-white hover:from-teal-500 hover:to-cyan-500"
                      onClick={() => {
                        setResults((prev) => {
                          if (!prev) return prev;
                          return {
                            ...prev,
                            needs_confirmation: [],
                            summary: {
                              ...prev.summary,
                              needs_confirmation: 0,
                            },
                          };
                        });
                      }}
                    >
                      Skip Remaining
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
