"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useAuthBootstrap, useLogin } from "@/hooks/use-auth";
import { ApiError, toUserMessage } from "@/lib/errors";
import { useAuthStore } from "@/stores/auth-store";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const { isLoading } = useAuthBootstrap();
  const mode = useAuthStore((s) => s.mode);
  const user = useAuthStore((s) => s.user);
  const login = useLogin();

  const form = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  // Nothing to sign into when the server has auth disabled, and an already-signed-in
  // user should never be shown this form.
  const shouldSkip = !isLoading && (mode?.auth_disabled || !!user);
  useEffect(() => {
    if (shouldSkip) router.replace("/dashboard");
  }, [shouldSkip, router]);

  if (isLoading || shouldSkip) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>
    );
  }

  const error = login.error;
  const rateLimited = error instanceof ApiError && error.isRateLimited;

  return (
    <div className="flex min-h-screen flex-col bg-muted/30">
      <div className="flex justify-end p-4">
        <ThemeToggle />
      </div>
      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-6 sm:items-center sm:pt-0">
        <div className="w-full max-w-sm space-y-6">
          <div className="flex flex-col items-center gap-3 text-center">
            <span className="rounded-xl bg-primary p-2.5 text-primary-foreground">
              <ShieldCheck className="h-6 w-6" aria-hidden />
            </span>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">AI Governance Console</h1>
              <p className="text-sm text-muted-foreground">
                Sign in to manage AI systems and compliance evidence.
              </p>
            </div>
          </div>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-base">Sign in</CardTitle>
              <CardDescription>Use the credentials issued by your administrator.</CardDescription>
            </CardHeader>
            <CardContent>
              {error ? (
                <Alert variant="destructive" className="mb-4">
                  <AlertDescription>
                    {rateLimited
                      ? "Too many sign-in attempts. Wait a minute and try again."
                      : toUserMessage(error)}
                  </AlertDescription>
                </Alert>
              ) : null}

              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit((values) => login.mutate(values))}
                  className="space-y-4"
                  noValidate
                >
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email</FormLabel>
                        <FormControl>
                          <Input
                            type="email"
                            autoComplete="username"
                            placeholder="you@example.com"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Password</FormLabel>
                        <FormControl>
                          <Input type="password" autoComplete="current-password" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button type="submit" className="w-full" disabled={login.isPending || rateLimited}>
                    {login.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Signing in…
                      </>
                    ) : (
                      "Sign in"
                    )}
                  </Button>
                </form>
              </Form>
            </CardContent>
          </Card>

          <div className="rounded-lg border bg-card px-4 py-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Demo credentials</p>
            <p className="mt-1 font-mono">admin@aigov.example.com · ChangeMe123!</p>
            <p className="mt-1">
              Seeded accounts also exist for <span className="font-mono">risk@</span> and{" "}
              <span className="font-mono">viewer@</span> with the same password.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
