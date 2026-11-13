"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError, apiPost } from "@/lib/api";
import { homeFor } from "@/lib/roles";
import type { AuthMe, Role } from "@/lib/types";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

const registerSchema = z
  .object({
    name: z.string().min(2, "Enter your full name."),
    email: z.string().email("Enter a valid email address."),
    password: z.string().min(8, "Use at least 8 characters."),
    role: z.enum(["customer", "partner"]),
    company_name: z.string().optional(),
    vehicle_type: z.enum(["bike", "car", "van", "truck"]).optional(),
    service_area: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (data.role === "partner" && (!data.company_name || data.company_name.trim().length < 2)) {
      ctx.addIssue({
        code: "custom",
        path: ["company_name"],
        message: "Add your courier or business name.",
      });
    }
    if (data.role === "partner" && !data.vehicle_type) {
      ctx.addIssue({ code: "custom", path: ["vehicle_type"], message: "Choose a vehicle type." });
    }
  });

type RegisterValues = z.infer<typeof registerSchema>;

export default function AuthForm({ nextPath }: { nextPath?: string }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [serverError, setServerError] = useState<string | null>(null);

  return (
    <div className="card card-pad">
      <div className="mb-6 flex rounded-control bg-surface-muted p-1" role="tablist" aria-label="Account access">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "login"}
          onClick={() => {
            setMode("login");
            setServerError(null);
          }}
          className={`flex-1 rounded-[8px] px-3 py-2 text-sm font-medium transition ${
            mode === "login" ? "bg-surface text-ink shadow-sm" : "text-muted"
          }`}
        >
          Sign in
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "register"}
          onClick={() => {
            setMode("register");
            setServerError(null);
          }}
          className={`flex-1 rounded-[8px] px-3 py-2 text-sm font-medium transition ${
            mode === "register" ? "bg-surface text-ink shadow-sm" : "text-muted"
          }`}
        >
          Create account
        </button>
      </div>

      {mode === "login" ? (
        <LoginFields nextPath={nextPath} onError={setServerError} serverError={serverError} />
      ) : (
        <RegisterFields nextPath={nextPath} onError={setServerError} serverError={serverError} />
      )}
    </div>
  );
}

function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="rounded-control border border-[#f3d1cb] bg-red-soft px-3 py-2 text-[13px] text-[#8c2f2f]" role="alert">
      {message}
    </p>
  );
}

function LoginFields({
  nextPath,
  onError,
  serverError,
}: {
  nextPath?: string;
  onError: (value: string | null) => void;
  serverError: string | null;
}) {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: z.infer<typeof loginSchema>) {
    onError(null);
    try {
      const me = await apiPost<AuthMe>("/auth/login", values);
      const role = me.user.role as Role;
      const target = nextPath && nextPath.startsWith("/") ? nextPath : homeFor(role);
      router.push(target);
      router.refresh();
    } catch (error) {
      onError(error instanceof ApiError ? error.message : "Sign in failed. Try again.");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <ErrorBanner message={serverError} />
      <div>
        <label className="label" htmlFor="login-email">
          Email
        </label>
        <input
          id="login-email"
          type="email"
          autoComplete="email"
          className={`input ${errors.email ? "input-error" : ""}`}
          {...register("email")}
        />
        {errors.email ? <p className="error-text">{errors.email.message}</p> : null}
      </div>
      <div>
        <label className="label" htmlFor="login-password">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          className={`input ${errors.password ? "input-error" : ""}`}
          {...register("password")}
        />
        {errors.password ? <p className="error-text">{errors.password.message}</p> : null}
      </div>
      <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
        Sign in
      </button>
      <p className="text-center text-xs leading-5 text-muted">
        Demo accounts are listed in the repository README (development only).
      </p>
    </form>
  );
}

function RegisterFields({
  nextPath,
  onError,
  serverError,
}: {
  nextPath?: string;
  onError: (value: string | null) => void;
  serverError: string | null;
}) {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: "customer", vehicle_type: "van" },
  });
  const role = watch("role");

  async function onSubmit(values: RegisterValues) {
    onError(null);
    try {
      const me = await apiPost<AuthMe>("/auth/register", values);
      const target = nextPath && nextPath.startsWith("/") ? nextPath : homeFor(me.user.role as Role);
      router.push(target);
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fields).length) {
        onError(Object.values(error.fields).join(" "));
      } else {
        onError(error instanceof ApiError ? error.message : "Registration failed. Try again.");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <ErrorBanner message={serverError} />
      <div>
        <span className="label">I am a</span>
        <div className="grid grid-cols-2 gap-2">
          <label className="flex cursor-pointer items-center gap-2 rounded-control border bg-surface px-3 py-2.5 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
            <input type="radio" value="customer" {...register("role")} className="accent-[#087c60]" />
            Customer
          </label>
          <label className="flex cursor-pointer items-center gap-2 rounded-control border bg-surface px-3 py-2.5 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
            <input type="radio" value="partner" {...register("role")} className="accent-[#087c60]" />
            Delivery partner
          </label>
        </div>
        {role === "partner" ? (
          <p className="help">Partner accounts start pending administrator verification.</p>
        ) : null}
      </div>
      <div>
        <label className="label" htmlFor="register-name">
          Full name
        </label>
        <input id="register-name" className="input" autoComplete="name" {...register("name")} />
        {errors.name ? <p className="error-text">{errors.name.message}</p> : null}
      </div>
      <div>
        <label className="label" htmlFor="register-email">
          Email
        </label>
        <input
          id="register-email"
          type="email"
          className="input"
          autoComplete="email"
          {...register("email")}
        />
        {errors.email ? <p className="error-text">{errors.email.message}</p> : null}
      </div>
      <div>
        <label className="label" htmlFor="register-password">
          Password
        </label>
        <input
          id="register-password"
          type="password"
          className="input"
          autoComplete="new-password"
          {...register("password")}
        />
        {errors.password ? <p className="error-text">{errors.password.message}</p> : <p className="help">At least 8 characters with a letter and a number.</p>}
      </div>
      {role === "partner" ? (
        <div className="grid gap-3 rounded-control border bg-surface-muted p-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="register-company">
              Business / courier name
            </label>
            <input id="register-company" className="input" {...register("company_name")} />
            {errors.company_name ? <p className="error-text">{errors.company_name.message}</p> : null}
          </div>
          <div>
            <label className="label" htmlFor="register-vehicle">
              Vehicle type
            </label>
            <select id="register-vehicle" className="input" {...register("vehicle_type")}>
              <option value="bike">Bike</option>
              <option value="car">Car</option>
              <option value="van">Van</option>
              <option value="truck">Truck</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="register-area">
              Primary service area
            </label>
            <input id="register-area" className="input" placeholder="e.g. Barasat" {...register("service_area")} />
          </div>
        </div>
      ) : null}
      <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
        Create account
      </button>
    </form>
  );
}
