"use client";

import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Camera,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  FileImage,
  X,
} from "lucide-react";
import {
  useUploadReceipt,
  useReceiptPendingItems,
  useConfirmAndSeedItems,
} from "../hooks/useReceipt";
import Image from "next/image";
import { ReceiptUploadResult } from "../types";

interface ReceiptUploadProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function ReceiptUpload({
  open,
  onOpenChange,
}: ReceiptUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<ReceiptUploadResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadReceipt = useUploadReceipt();
  const { data: pendingData, refetch: refetchPending } = useReceiptPendingItems(uploadResult?.receipt_id ?? null);
  const confirmItems = useConfirmAndSeedItems();

  const handleFileSelect = (file: File) => {
    if (!file.type.startsWith("image/")) {
      alert("Please select an image file");
      return;
    }

    setSelectedFile(file);

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      const result = await uploadReceipt.mutateAsync(selectedFile);
      setUploadResult(result);
      refetchPending();

      // Clear selection
      setSelectedFile(null);
      setPreview(null);
    } catch (error) {
      console.error("Upload failed:", error);
    }
  };

  const handleConfirmAll = async () => {
    if (!pendingData?.items || pendingData.items.length === 0) return;

    const confirmData = {
      items: pendingData.items.map((item) => ({
        pending_item_id: item.id,
        action: "confirm" as const,
      })),
    };

    await confirmItems.mutateAsync(confirmData);
    setUploadResult(null);
    refetchPending();
  };

  const handleConfirmSingle = async (itemId: number) => {
    const confirmData = {
      items: [
        {
          pending_item_id: itemId,
          action: "confirm" as const,
        },
      ],
    };

    await confirmItems.mutateAsync(confirmData);
    refetchPending();
  };

  const handleSkipSingle = async (itemId: number) => {
    const confirmData = {
      items: [
        {
          pending_item_id: itemId,
          action: "skip" as const,
        },
      ],
    };

    await confirmItems.mutateAsync(confirmData);
    refetchPending();
  };

  const handleClose = () => {
    setSelectedFile(null);
    setPreview(null);
    setUploadResult(null);
    onOpenChange(false);
  };

  const hasPending = (pendingData?.count ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5 text-blue-600" />
            Scan Receipt
          </DialogTitle>
          <DialogDescription>
            Upload a receipt image and AI will automatically extract and identify
            items
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* File Upload Section */}
          {!uploadResult && (
            <>
              {!selectedFile && (
                <div className="border-2 border-dashed rounded-lg p-8 text-center space-y-4">
                  <div className="flex justify-center">
                    <FileImage className="h-12 w-12 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium mb-1">
                      Select a receipt image
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Supports JPG, PNG, HEIC formats
                    </p>
                  </div>
                  <div className="flex gap-2 justify-center">
                    <Button
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload className="mr-2 h-4 w-4" />
                      Choose File
                    </Button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleFileSelect(file);
                      }}
                    />
                  </div>
                </div>
              )}

              {selectedFile && preview && (
                <Card>
                  <CardContent className="p-4">
                    <div className="space-y-4">
                      {/* Preview */}
                      <div className="relative rounded-lg overflow-hidden bg-muted">
                        <div className="relative w-full h-64">
                          <Image
                            src={preview}
                            alt="Receipt preview"
                            fill
                            className="object-contain"
                          />
                        </div>
                        <Button
                          variant="destructive"
                          size="icon"
                          className="absolute top-2 right-2"
                          onClick={() => {
                            setSelectedFile(null);
                            setPreview(null);
                          }}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>

                      {/* File Info */}
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium">{selectedFile.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {(selectedFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                        <Button
                          onClick={handleUpload}
                          disabled={uploadReceipt.isPending}
                        >
                          {uploadReceipt.isPending ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Processing...
                            </>
                          ) : (
                            <>
                              <Camera className="mr-2 h-4 w-4" />
                              Scan Receipt
                            </>
                          )}
                        </Button>
                      </div>

                      {uploadReceipt.isPending && (
                        <Alert>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <AlertDescription>
                            AI is extracting items from your receipt. This may take
                            10-15 seconds...
                          </AlertDescription>
                        </Alert>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* Results Section */}
          {uploadResult && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-2 gap-3">
                <Card className="border-green-200 bg-green-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      <span className="text-2xl font-bold text-green-700">
                        {uploadResult.auto_added_count}
                      </span>
                    </div>
                    <p className="text-xs text-green-700">Added Automatically</p>
                  </CardContent>
                </Card>

                <Card className="border-yellow-200 bg-yellow-50/50">
                  <CardContent className="p-4 text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <span className="text-2xl font-bold text-yellow-700">
                        {uploadResult.needs_confirmation_count}
                      </span>
                    </div>
                    <p className="text-xs text-yellow-700">Need Confirmation</p>
                  </CardContent>
                </Card>
              </div>

              {uploadResult.auto_added_count > 0 && (
                <Alert className="border-green-200 bg-green-50/50">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <AlertDescription className="text-green-700">
                    {uploadResult.auto_added_count} high-confidence items were added
                    to your inventory automatically!
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {/* Pending Items Confirmation */}
          {hasPending && (
            <Card className="border-yellow-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-semibold text-sm flex items-center gap-2 text-yellow-700">
                    <AlertTriangle className="h-4 w-4" />
                    Items Needing Confirmation ({pendingData.count})
                  </h4>
                  <Button
                    size="sm"
                    onClick={handleConfirmAll}
                    disabled={confirmItems.isPending}
                  >
                    {confirmItems.isPending ? (
                      <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                    ) : (
                      <CheckCircle2 className="mr-2 h-3 w-3" />
                    )}
                    Confirm All
                  </Button>
                </div>

                <div className="space-y-3">
                  {pendingData.items.map((item) => {
                    const isLowConfidence = (item.enrichment_confidence ?? 0) < 0.5;

                    return (
                      <Card key={item.id} className={isLowConfidence ? "border-orange-200" : "border"}>
                        <CardContent className="p-3">
                          {isLowConfidence ? (
                            // Low confidence - show message, hide confirm button
                            <div className="space-y-2">
                              <div>
                                <p className="text-xs text-muted-foreground">
                                  From receipt: "{item.item_name}"
                                </p>
                                <p className="text-sm font-medium text-orange-700 mt-1">
                                  {item.canonical_name || item.item_name}
                                </p>
                                <p className="text-sm text-muted-foreground">
                                  {item.quantity} {item.unit}
                                </p>
                              </div>
                              <Alert className="border-orange-200 bg-orange-50/50">
                                <AlertDescription className="text-xs text-orange-800">
                                  We'll add this item to our database shortly. Skip for now.
                                </AlertDescription>
                              </Alert>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="w-full"
                                onClick={() => handleSkipSingle(item.id)}
                                disabled={confirmItems.isPending}
                              >
                                <X className="mr-1 h-3 w-3" />
                                Skip
                              </Button>
                            </div>
                          ) : (
                            // High confidence - show full details and confirm button
                            <>
                              <div className="flex items-start justify-between gap-3 mb-3">
                                <div className="flex-1 space-y-2">
                                  <div>
                                    <p className="text-xs text-muted-foreground">
                                      From receipt: "{item.item_name}"
                                    </p>
                                  </div>

                                  {item.canonical_name && (
                                    <div>
                                      <p className="font-medium text-sm">
                                        {item.canonical_name}
                                      </p>
                                      {item.category && (
                                        <Badge variant="outline" className="text-xs mt-1">
                                          {item.category}
                                        </Badge>
                                      )}
                                    </div>
                                  )}

                                  <p className="text-sm text-muted-foreground">
                                    {item.quantity} {item.unit}
                                  </p>

                                  {item.nutrition_data && (
                                    <div className="flex gap-3 text-xs text-muted-foreground">
                                      {item.nutrition_data.calories && (
                                        <span>{Math.round(item.nutrition_data.calories)} cal</span>
                                      )}
                                      {item.nutrition_data.protein_g && (
                                        <span>{item.nutrition_data.protein_g.toFixed(1)}g protein</span>
                                      )}
                                      {item.nutrition_data.carbs_g && (
                                        <span>{item.nutrition_data.carbs_g.toFixed(1)}g carbs</span>
                                      )}
                                    </div>
                                  )}

                                  {item.enrichment_reasoning && !item.enrichment_reasoning.includes("No matches found") && (
                                    <p className="text-xs text-muted-foreground italic">
                                      {item.enrichment_reasoning}
                                    </p>
                                  )}
                                </div>

                                {item.enrichment_confidence !== null && (
                                  <Badge
                                    variant={
                                      item.enrichment_confidence >= 0.8
                                        ? "secondary"
                                        : "outline"
                                    }
                                    className="text-xs"
                                  >
                                    {Math.round(item.enrichment_confidence * 100)}%
                                  </Badge>
                                )}
                              </div>

                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="flex-1"
                                  onClick={() => handleConfirmSingle(item.id)}
                                  disabled={confirmItems.isPending}
                                >
                                  <CheckCircle2 className="mr-1 h-3 w-3" />
                                  Confirm & Add
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleSkipSingle(item.id)}
                                  disabled={confirmItems.isPending}
                                >
                                  <X className="mr-1 h-3 w-3" />
                                  Skip
                                </Button>
                              </div>
                            </>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2 justify-end">
            {!hasPending && uploadResult && (
              <Button onClick={handleClose}>Done</Button>
            )}
            {hasPending && (
              <>
                <Button variant="outline" onClick={handleClose}>
                  Finish Later
                </Button>
                <Button onClick={handleConfirmAll} disabled={confirmItems.isPending}>
                  {confirmItems.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                  )}
                  Confirm All
                </Button>
              </>
            )}
            {!uploadResult && !selectedFile && (
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
