import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface AsyncStateProps {
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  loadingLines?: number;
  children: React.ReactNode;
}

export function AsyncState({
  isLoading,
  error,
  onRetry,
  loadingLines = 3,
  children,
}: AsyncStateProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: loadingLines }).map((_, index) => (
          <Skeleton key={index} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between gap-3">
          <span>{error}</span>
          {onRetry && (
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  return <>{children}</>;
}
