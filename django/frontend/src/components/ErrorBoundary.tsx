import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Last-resort boundary around the routes: a render error in any surface
 * shows a short message and a reload button instead of a blank page.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div
        className="flex h-full min-h-[50vh] flex-col items-center justify-center gap-3 p-6 text-center"
        role="alert"
      >
        <p className="text-base font-semibold">Something went wrong.</p>
        <p className="max-w-md text-sm text-muted-foreground">
          {this.state.error.message || "The dashboard hit an unexpected error."}
        </p>
        <Button size="sm" onClick={() => window.location.reload()}>
          Reload page
        </Button>
      </div>
    );
  }
}
