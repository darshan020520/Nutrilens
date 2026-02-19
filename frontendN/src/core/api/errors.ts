export type UiError = {
  code: string;
  message: string;
  recoverable: boolean;
  retryAction?: string;
};

export function toUiError(error: unknown, fallbackMessage = "Something went wrong"): UiError {
  const anyError = error as any;
  const status = anyError?.response?.status;
  const detail = anyError?.response?.data?.detail;
  const message = typeof detail === "string" ? detail : fallbackMessage;

  if (status === 401) {
    return {
      code: "UNAUTHORIZED",
      message: "Your session expired. Please log in again.",
      recoverable: true,
      retryAction: "login",
    };
  }

  if (status >= 500) {
    return {
      code: "SERVER_ERROR",
      message,
      recoverable: true,
      retryAction: "retry",
    };
  }

  return {
    code: "REQUEST_ERROR",
    message,
    recoverable: true,
    retryAction: "retry",
  };
}
