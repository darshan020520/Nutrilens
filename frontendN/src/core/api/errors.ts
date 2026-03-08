export type UiError = {
  code: string;
  message: string;
  recoverable: boolean;
  retryAction?: string;
};

type ApiErrorLike = {
  response?: {
    status?: number;
    data?: {
      detail?: string;
    };
  };
};

export function toUiError(error: unknown, fallbackMessage = "Something went wrong"): UiError {
  const apiError = error as ApiErrorLike;
  const status = apiError?.response?.status;
  const detail = apiError?.response?.data?.detail;
  const message = typeof detail === "string" ? detail : fallbackMessage;

  if (status === 401) {
    return {
      code: "UNAUTHORIZED",
      message: "Your session expired. Please log in again.",
      recoverable: true,
      retryAction: "login",
    };
  }

  if (typeof status === "number" && status >= 500) {
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
