"use client";

import { useState } from "react";
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
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Info,
} from "lucide-react";
import { useAddItems, useConfirmItem } from "../hooks/useInventory";

interface AddItemsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function AddItemsDialog({
  open,
  onOpenChange,
}: AddItemsDialogProps) {
  const [textInput, setTextInput] = useState("");
  const [results, setResults] = useState<any>(null);

  const addItems = useAddItems();
  const confirmItem = useConfirmItem();

  const handleSubmit = async () => {
    if (!textInput.trim()) return;

    const result = await addItems.mutateAsync({ text_input: textInput });
    setResults(result.results);
  };

  const handleConfirm = async (item: any, itemId: number) => {
    await confirmItem.mutateAsync({
      original_text: item.original,
      item_id: itemId,
      quantity_grams: item.quantity_grams,
    });

    // Remove from needs_confirmation list
    setResults((prev: any) => ({
      ...prev,
      needs_confirmation: prev.needs_confirmation.filter(
        (i: any) => i.original !== item.original
      ),
      summary: {
        ...prev.summary,
        needs_confirmation: prev.summary.needs_confirmation - 1,
        successful: prev.summary.successful + 1,
      },
    }));
  };

  const handleClose = () => {
    setTextInput("");
    setResults(null);
    onOpenChange(false);
  };

  const hasResults = results !== null;
  const confirmableItems = results?.needs_confirmation?.filter(
    (i: any) => i.item_id
  ) || [];
  const hasConfirmations = confirmableItems.length > 0;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-600" />
            Add Items to Inventory
          </DialogTitle>
          <DialogDescription>
            Enter items in natural language. AI will automatically identify and
            normalize them.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Input Section */}
          {!hasResults && (
            <>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <strong>Examples:</strong> "2 apples, 500g chicken breast, 1L milk"
                  or "bananas x3, ground beef 1kg"
                </AlertDescription>
              </Alert>

              <Textarea
                placeholder="E.g., 2 apples, 500g chicken, 1L milk, 250g cheddar cheese..."
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                rows={6}
                className="resize-none"
              />

              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={!textInput.trim() || addItems.isPending}
                >
                  {addItems.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Processing with AI...
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-4 w-4" />
                      Add Items
                    </>
                  )}
                </Button>
              </div>
            </>
          )}

          {/* Results Section */}
          {hasResults && (
            <div className="space-y-4">
              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-3">
                <Card className="border-green-200 bg-green-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      <span className="text-2xl font-bold text-green-700">
                        {results.summary.successful}
                      </span>
                    </div>
                    <p className="text-xs text-green-700">Added Successfully</p>
                  </CardContent>
                </Card>

                <Card className="border-yellow-200 bg-yellow-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <span className="text-2xl font-bold text-yellow-700">
                        {results.summary.needs_confirmation}
                      </span>
                    </div>
                    <p className="text-xs text-yellow-700">Needs Confirmation</p>
                  </CardContent>
                </Card>

                <Card className="border-red-200 bg-red-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <XCircle className="h-4 w-4 text-red-600" />
                      <span className="text-2xl font-bold text-red-700">
                        {results.summary.failed}
                      </span>
                    </div>
                    <p className="text-xs text-red-700">Could Not Process</p>
                  </CardContent>
                </Card>
              </div>

              {/* Successfully Added Items */}
              {results.successful && results.successful.length > 0 && (
                <Card className="border-green-200">
                  <CardContent className="p-4">
                    <h4 className="font-semibold text-sm mb-3 flex items-center gap-2 text-green-700">
                      <CheckCircle2 className="h-4 w-4" />
                      Successfully Added
                    </h4>
                    <div className="space-y-2">
                      {results.successful.map((item: any, index: number) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-2 bg-white rounded border"
                        >
                          <div className="flex-1">
                            <p className="font-medium text-sm">{item.matched}</p>
                            <p className="text-xs text-muted-foreground">
                              {item.quantity}
                            </p>
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {(item.confidence * 100).toFixed(0)}%
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Items Needing Confirmation */}
              {results.needs_confirmation?.filter((i: any) => i.item_id).length > 0 && (
                <Card className="border-yellow-200">
                  <CardContent className="p-4">
                    <h4 className="font-semibold text-sm mb-3 flex items-center gap-2 text-yellow-700">
                      <AlertTriangle className="h-4 w-4" />
                      Please Confirm These Items
                    </h4>
                    <div className="space-y-3">
                      {results.needs_confirmation
                        .filter((item: any) => item.item_id)
                        .map((item: any, index: number) => (
                        <Card key={index} className="border">
                          <CardContent className="p-3">
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <div className="flex-1">
                                <p className="text-xs text-muted-foreground mb-1">
                                  You entered: &ldquo;{item.original}&rdquo;
                                </p>
                                <p className="font-medium">
                                  AI detected: {item.suggested || item.suggested_name}
                                </p>
                              </div>
                              <Badge variant="outline" className="text-xs">
                                {(item.confidence * 100).toFixed(0)}% match
                              </Badge>
                            </div>

                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full justify-start"
                              onClick={() => handleConfirm(item, item.item_id)}
                              disabled={confirmItem.isPending}
                            >
                              <CheckCircle2 className="mr-2 h-3.5 w-3.5 text-green-600" />
                              <span className="flex-1 text-left">
                                Yes, add as {item.suggested || item.suggested_name}
                              </span>
                            </Button>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* New Items Discovered */}
              {results.needs_confirmation?.filter((i: any) => i.action === 'add_to_pending').length > 0 && (
                <Card className="border-purple-200 bg-purple-50/30">
                  <CardContent className="p-4">
                    <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-purple-700">
                      <Sparkles className="h-4 w-4" />
                      New Items Discovered
                    </h4>
                    <p className="text-xs text-purple-600 mb-3">
                      Thanks for helping us expand our database! These items have been noted and will be added soon.
                    </p>
                    <div className="space-y-2">
                      {results.needs_confirmation
                        .filter((item: any) => item.action === 'add_to_pending')
                        .map((item: any, index: number) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-2 bg-white rounded border border-purple-200"
                        >
                          <div className="flex-1">
                            <p className="font-medium text-sm">{item.suggested_name}</p>
                            <p className="text-xs text-muted-foreground">
                              from &ldquo;{item.original}&rdquo;
                              {item.category && <> &middot; {item.category}</>}
                            </p>
                          </div>
                          <Badge className="bg-purple-100 text-purple-700 text-xs">
                            Pending
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Failed Items */}
              {results.failed && results.failed.length > 0 && (
                <Card className="border-red-200">
                  <CardContent className="p-4">
                    <h4 className="font-semibold text-sm mb-3 flex items-center gap-2 text-red-700">
                      <XCircle className="h-4 w-4" />
                      Could Not Process
                    </h4>
                    <div className="space-y-2">
                      {results.failed.map((item: any, index: number) => (
                        <div
                          key={index}
                          className="p-2 bg-red-50 rounded border border-red-200"
                        >
                          <p className="text-sm">&ldquo;{item.original || item.original_text}&rdquo;</p>
                          {(item.reason || item.error) && (
                            <p className="text-xs text-red-600 mt-1">
                              {item.reason || item.error}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2 justify-end pt-2">
                {!hasConfirmations && (
                  <Button onClick={handleClose}>Done</Button>
                )}
                {hasConfirmations && (
                  <>
                    <Button variant="outline" onClick={handleClose}>
                      Finish Later
                    </Button>
                    <Button
                      onClick={() => {
                        // Skip all remaining confirmations
                        setResults((prev: any) => ({
                          ...prev,
                          needs_confirmation: [],
                          summary: {
                            ...prev.summary,
                            needs_confirmation: 0,
                          },
                        }));
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
