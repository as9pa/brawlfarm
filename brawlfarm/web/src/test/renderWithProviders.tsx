/**
 * render() with the two providers every screen needs: a fresh query client per test (no
 * retries, no cache carried between cases) and a MemoryRouter so Link and useParams work
 * without a browser history.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderResult, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  options: { route?: string; client?: QueryClient } = {},
): RenderResult & { client: QueryClient } {
  const client = options.client ?? testQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[options.route ?? "/"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  // Annotated rather than inferred: render()'s generic overload leaves the query half
  // of RenderResult deferred, and an object spread drops a deferred mapped type.
  const result: RenderResult = render(ui, { wrapper });
  return { ...result, client };
}
