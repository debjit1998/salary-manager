/**
 * Smoke tests for the login page view.
 *
 * The actual auth call goes through TanStack Query → axios → /auth/login;
 * we mock useLogin so the test exercises the component's interaction
 * surface (form fields wire up, button state reflects pending, error
 * toast fires on rejection) without touching the network.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LoginView } from "../view";

// vi.mock() factories are hoisted above the imports they need, so any
// shared spies have to be hoisted alongside via vi.hoisted().
const mocks = vi.hoisted(() => ({
  loginMutate: vi.fn(),
  isPending: false,
  toastError: vi.fn(),
}));

vi.mock("@/lib/hooks/use-auth", () => ({
  useLogin: () => ({ mutate: mocks.loginMutate, isPending: mocks.isPending }),
}));

vi.mock("sonner", () => ({
  toast: { error: mocks.toastError },
}));

describe("LoginView", () => {
  beforeEach(() => {
    mocks.loginMutate.mockReset();
    mocks.toastError.mockReset();
    mocks.isPending = false;
  });

  it("renders the email/password form", () => {
    render(<LoginView />);
    expect(screen.getByText(/Salary Manager/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign in/i })).toBeEnabled();
  });

  it("submits the typed credentials to useLogin", async () => {
    render(<LoginView />);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "hr@acme.org" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "super-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => expect(mocks.loginMutate).toHaveBeenCalledTimes(1));
    const [credentials] = mocks.loginMutate.mock.calls[0];
    expect(credentials).toEqual({
      email: "hr@acme.org",
      password: "super-secret",
    });
  });

  it("disables the submit button while the login mutation is pending", () => {
    mocks.isPending = true;
    render(<LoginView />);
    expect(screen.getByRole("button", { name: /Signing in/i })).toBeDisabled();
  });

  it("surfaces the server's detail message on error via toast", async () => {
    render(<LoginView />);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "hr@acme.org" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "nope" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => expect(mocks.loginMutate).toHaveBeenCalled());

    // The component registers an onError callback that maps the axios
    // error's `response.data.detail` to a toast. Invoke it directly to
    // exercise that path without faking a rejected mutation.
    const [, opts] = mocks.loginMutate.mock.calls[0];
    opts.onError({
      response: { data: { detail: "invalid email or password" } },
    });

    expect(mocks.toastError).toHaveBeenCalledWith("invalid email or password");
  });
});
