"use client";

import { useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Check, Loader2, MapPin, Package } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Callout, Field } from "@/components/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { formatDateTime, formatWeight } from "@/lib/format";
import type { DeliveryRequest, Location, ServiceType } from "@/lib/types";

const baseSchema = z.object({
  pickup_location_id: z.string().optional(),
  pickup_address: z.string().optional(),
  pickup_area: z.string().optional(),
  pickup_lat: z.string().optional(),
  pickup_lng: z.string().optional(),
  destination_location_id: z.string().optional(),
  destination_address: z.string().optional(),
  destination_area: z.string().optional(),
  destination_lat: z.string().optional(),
  destination_lng: z.string().optional(),
  authorized_hub_name: z.string().optional(),
  return_reference: z.string().optional(),
  retailer: z.string().optional(),
  recipient_name: z.string().optional(),
  recipient_phone: z.string().optional(),
  recipient_instructions: z.string().optional(),
  parcel_description: z.string().min(3, "Describe the parcel."),
  parcel_category: z.string().optional(),
  weight_kg: z.coerce.number().min(0.05, "Minimum 0.05 kg.").max(150, "Maximum 150 kg."),
  volume_m3: z.coerce.number().min(0.001, "Minimum 0.001 m³.").max(1.5, "Maximum 1.5 m³."),
  size_class: z.enum(["small", "medium", "large"]),
  handling: z.array(z.string()).optional(),
  declared_value_inr: z.string().optional(),
  pickup_window_start: z.string().min(1, "Choose a pickup window start."),
  pickup_window_end: z.string().min(1, "Choose a pickup window end."),
  delivery_deadline: z.string().min(1, "Choose a delivery deadline."),
  notes: z.string().max(1000).optional(),
});

type Values = z.infer<typeof baseSchema>;

type Props = {
  mode: ServiceType;
  defaults: { start: string; end: string; deadline: string };
};

const STEPS = [
  { id: 1, title: "Locations", hint: "Pickup and authorised destination" },
  { id: 2, title: "Parcel & schedule", hint: "What, when, how heavy" },
  { id: 3, title: "Review", hint: "Confirm before submitting" },
];

function toInputValue(iso: string): string {
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function isHub(location: Location) {
  return /authorized returns hub/i.test(location.label) || /returns hub/i.test(location.label);
}

export default function RequestForm({ mode, defaults }: Props) {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [serverError, setServerError] = useState<string | null>(null);
  const [customPickup, setCustomPickup] = useState(false);
  const [customDestination, setCustomDestination] = useState(false);

  const { data: locationsData, isLoading: locationsLoading } = useQuery({
    queryKey: ["locations", "suggestions"],
    queryFn: () => apiGet<Location[]>("/locations/suggestions"),
    staleTime: 5 * 60_000,
  });
  const locations = useMemo(() => locationsData ?? [], [locationsData]);
  const hubs = useMemo(() => locations.filter(isHub), [locations]);
  const regular = useMemo(() => locations.filter((location) => !isHub(location)), [locations]);

  const schema = useMemo(
    () =>
      baseSchema.superRefine((data, ctx) => {
        const pickupFields = customPickup
          ? (["pickup_address", "pickup_area", "pickup_lat", "pickup_lng"] as const)
          : (["pickup_location_id"] as const);
        for (const key of pickupFields) {
          if (!data[key]) ctx.addIssue({ code: "custom", path: [key], message: "Required." });
        }
        const destinationFields = customDestination
          ? (["destination_address", "destination_area", "destination_lat", "destination_lng"] as const)
          : (["destination_location_id"] as const);
        for (const key of destinationFields) {
          if (!data[key]) ctx.addIssue({ code: "custom", path: [key], message: "Required." });
        }
        if (mode === "return" && !data.authorized_hub_name?.trim()) {
          ctx.addIssue({
            code: "custom",
            path: ["authorized_hub_name"],
            message: "Name the authorised return destination.",
          });
        }
        if (mode === "parcel" && !data.recipient_name?.trim()) {
          ctx.addIssue({ code: "custom", path: ["recipient_name"], message: "Add the recipient name." });
        }
        if (data.pickup_window_start && data.pickup_window_end) {
          if (new Date(data.pickup_window_end) <= new Date(data.pickup_window_start)) {
            ctx.addIssue({
              code: "custom",
              path: ["pickup_window_end"],
              message: "End must be after the start.",
            });
          }
        }
        if (data.delivery_deadline && data.pickup_window_start) {
          if (new Date(data.delivery_deadline) < new Date(data.pickup_window_start)) {
            ctx.addIssue({
              code: "custom",
              path: ["delivery_deadline"],
              message: "Deadline must be after the pickup window starts.",
            });
          }
        }
      }),
    [customPickup, customDestination, mode],
  );

  const {
    register,
    handleSubmit,
    trigger,
    watch,
    setValue,
    getValues,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      size_class: "small",
      pickup_window_start: toInputValue(defaults.start),
      pickup_window_end: toInputValue(defaults.end),
      delivery_deadline: toInputValue(defaults.deadline),
      handling: [],
    },
  });

  useEffect(() => {
    if (!locations.length) return;
    if (!getValues("pickup_location_id") && !customPickup) {
      const first = regular[0] ?? locations[0];
      if (first?.id) setValue("pickup_location_id", String(first.id));
    }
    if (!getValues("destination_location_id") && !customDestination) {
      const first = mode === "return" ? hubs[0] : regular.find((item) => String(item.id) !== getValues("pickup_location_id"));
      if (first?.id) {
        setValue("destination_location_id", String(first.id));
        if (mode === "return") setValue("authorized_hub_name", first.label);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locations.length, mode]);

  const watched = watch();
  const pickupLocation = locations.find((item) => String(item.id) === watched.pickup_location_id);
  const destinationLocation = locations.find((item) => String(item.id) === watched.destination_location_id);

  async function goNext() {
    const fields: (keyof Values)[] =
      step === 1
        ? [
            "pickup_location_id",
            "pickup_address",
            "pickup_area",
            "pickup_lat",
            "pickup_lng",
            "destination_location_id",
            "destination_address",
            "destination_area",
            "destination_lat",
            "destination_lng",
            ...(mode === "return" ? (["authorized_hub_name"] as (keyof Values)[]) : (["recipient_name"] as (keyof Values)[])),
          ]
        : [
            "parcel_description",
            "weight_kg",
            "volume_m3",
            "pickup_window_start",
            "pickup_window_end",
            "delivery_deadline",
          ];
    const valid = await trigger(fields);
    if (valid) setStep((value) => Math.min(3, value + 1));
  }

  function locationPayload(prefix: "pickup" | "destination", custom: boolean) {
    if (!custom) {
      return { location_id: Number(getValues(`${prefix}_location_id`)) };
    }
    return {
      address_line: getValues(`${prefix}_address`),
      area: getValues(`${prefix}_area`),
      city: "Kolkata",
      latitude: Number(getValues(`${prefix}_lat`)),
      longitude: Number(getValues(`${prefix}_lng`)),
      label: `${getValues(`${prefix}_area`)} — ${getValues(`${prefix}_address`)}`,
    };
  }

  async function onSubmit(values: Values) {
    setServerError(null);
    const payload = {
      type: mode,
      pickup: locationPayload("pickup", customPickup),
      destination: locationPayload("destination", customDestination),
      pickup_window_start: new Date(values.pickup_window_start).toISOString(),
      pickup_window_end: new Date(values.pickup_window_end).toISOString(),
      delivery_deadline: new Date(values.delivery_deadline).toISOString(),
      notes: values.notes || undefined,
      parcel: {
        description: values.parcel_description,
        category: values.parcel_category || "general",
        weight_kg: values.weight_kg,
        volume_m3: values.volume_m3,
        size_class: values.size_class,
        handling: values.handling ?? [],
        declared_value_inr: values.declared_value_inr ? Number(values.declared_value_inr) : undefined,
      },
      ...(mode === "return"
        ? {
            return: {
              authorized_hub_name: values.authorized_hub_name,
              return_reference: values.return_reference || undefined,
              retailer: values.retailer || undefined,
            },
          }
        : {
            recipient: {
              name: values.recipient_name,
              phone: values.recipient_phone || undefined,
              instructions: values.recipient_instructions || undefined,
            },
          }),
    };
    try {
      const created = await apiPost<DeliveryRequest>("/requests", payload);
      router.push(`/customer/requests/${created.id}`);
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError) {
        setServerError(error.message);
        const fields = error.fields ?? {};
        for (const [key, message] of Object.entries(fields)) {
          const mapped = key.includes("description")
            ? "parcel_description"
            : key.includes("weight")
              ? "weight_kg"
              : key.includes("volume")
                ? "volume_m3"
                : key.includes("window")
                  ? "pickup_window_end"
                  : key.includes("deadline")
                    ? "delivery_deadline"
                    : null;
          if (mapped) setError(mapped as keyof Values, { message });
        }
      } else {
        setServerError("The request could not be submitted. Try again.");
      }
    }
  }

  const destinationPreview =
    mode === "return"
      ? watched.authorized_hub_name || destinationLocation?.label || "Authorised return destination"
      : watched.recipient_name
        ? `${destinationLocation?.area ?? watched.destination_area ?? "Recipient"} · ${watched.recipient_name}`
        : "Recipient delivery address";

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="card card-pad">
        <ol className="mb-6 flex items-center gap-2" aria-label="Form progress">
          {STEPS.map((item) => (
            <li key={item.id} className="flex flex-1 items-center gap-2">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  step > item.id
                    ? "bg-accent text-white"
                    : step === item.id
                      ? "bg-accent-soft text-accent-strong ring-1 ring-accent"
                      : "bg-surface-muted text-muted"
                }`}
                aria-current={step === item.id ? "step" : undefined}
              >
                {step > item.id ? <Check size={14} aria-hidden /> : item.id}
              </span>
              <span className="hidden min-w-0 sm:block">
                <span className="block truncate text-[13px] font-medium">{item.title}</span>
                <span className="hidden text-[11px] text-muted lg:block">{item.hint}</span>
              </span>
            </li>
          ))}
        </ol>

        {serverError ? (
          <Callout tone="danger" title="Could not submit">
            {serverError}
          </Callout>
        ) : null}

        <form onSubmit={handleSubmit(onSubmit)} className="mt-4 space-y-6" noValidate>
          {step === 1 ? (
            <div className="space-y-6">
              <LocationBlock
                prefix="pickup"
                title="Pickup location"
                description="Where should the partner collect the parcel?"
                custom={customPickup}
                setCustom={setCustomPickup}
                locations={locationsLoading ? [] : regular}
                register={register}
                errors={errors}
                setValue={setValue}
                watch={watch}
                onSelect={(value) => setValue("pickup_location_id", value, { shouldValidate: true })}
              />

              <LocationBlock
                prefix="destination"
                title={mode === "return" ? "Authorised return destination" : "Recipient delivery address"}
                description={
                  mode === "return"
                    ? "Use the return hub authorised for this product. ReTurn never redirects a return to a shared hub."
                    : "The recipient's own address is preserved; it is never swapped for a return hub."
                }
                custom={customDestination}
                setCustom={setCustomDestination}
                locations={mode === "return" ? hubs : regular}
                register={register}
                errors={errors}
                setValue={setValue}
                watch={watch}
                onSelect={(value) => {
                  setValue("destination_location_id", value, { shouldValidate: true });
                  if (mode === "return") {
                    const hub = hubs.find((item) => String(item.id) === value);
                    if (hub) setValue("authorized_hub_name", hub.label);
                  }
                }}
              />

              {mode === "return" ? (
                <div className="field-grid">
                  <Field label="Authorised return destination name" htmlFor="hub-name" error={errors.authorized_hub_name?.message}>
                    <input id="hub-name" className="input" placeholder="e.g. ReTurn Authorized Returns Hub — Barasat" {...register("authorized_hub_name")} />
                  </Field>
                  <Field label="Return reference (optional)" htmlFor="return-ref">
                    <input id="return-ref" className="input" placeholder="RET-XXXX-00000" {...register("return_reference")} />
                  </Field>
                  <Field label="Retailer (optional)" htmlFor="retailer">
                    <input id="retailer" className="input" placeholder="Where the item was bought" {...register("retailer")} />
                  </Field>
                </div>
              ) : (
                <div className="field-grid">
                  <Field label="Recipient name" htmlFor="recipient-name" error={errors.recipient_name?.message} hint="Visible only to the assigned partner for delivery.">
                    <input id="recipient-name" className="input" {...register("recipient_name")} />
                  </Field>
                  <Field label="Recipient phone (optional)" htmlFor="recipient-phone">
                    <input id="recipient-phone" className="input" type="tel" {...register("recipient_phone")} />
                  </Field>
                  <Field label="Delivery instructions (optional)" htmlFor="recipient-instructions" className="sm:col-span-2">
                    <input id="recipient-instructions" className="input" placeholder="Gate code, handover preference…" {...register("recipient_instructions")} />
                  </Field>
                </div>
              )}
            </div>
          ) : null}

          {step === 2 ? (
            <div className="space-y-6">
              <div className="field-grid">
                <Field label="Parcel description" htmlFor="parcel-description" error={errors.parcel_description?.message} className="sm:col-span-2">
                  <input id="parcel-description" className="input" placeholder="e.g. Running shoes in original box" {...register("parcel_description")} />
                </Field>
                <Field label="Weight (kg)" htmlFor="weight" error={errors.weight_kg?.message}>
                  <input id="weight" className="input" type="number" min="0.05" max="150" step="0.05" {...register("weight_kg")} />
                </Field>
                <Field label="Volume (m³)" htmlFor="volume" error={errors.volume_m3?.message} hint="Rough size: a shoebox is about 0.014 m³.">
                  <input id="volume" className="input" type="number" min="0.001" max="1.5" step="0.001" {...register("volume_m3")} />
                </Field>
                <Field label="Size class" htmlFor="size-class">
                  <select id="size-class" className="input" {...register("size_class")}>
                    <option value="small">Small — fits a shoebox</option>
                    <option value="medium">Medium — carry-on size</option>
                    <option value="large">Large — needs van space</option>
                  </select>
                </Field>
                <Field label="Declared value (₹, optional)" htmlFor="declared">
                  <input id="declared" className="input" type="number" min="0" step="100" {...register("declared_value_inr")} />
                </Field>
              </div>

              <fieldset>
                <legend className="label">Handling requirements</legend>
                <div className="flex flex-wrap gap-4 rounded-control border bg-surface-muted px-4 py-3 text-sm">
                  {[
                    { value: "fragile", label: "Fragile" },
                    { value: "liquid", label: "Liquid" },
                    { value: "restricted", label: "Restricted (dedicated vehicle)" },
                  ].map((option) => (
                    <label key={option.value} className="flex items-center gap-2">
                      <input type="checkbox" value={option.value} className="accent-[#087c60]" {...register("handling")} />
                      {option.label}
                    </label>
                  ))}
                </div>
                <p className="help">Restricted parcels cannot share a batch; they need a dedicated vehicle.</p>
              </fieldset>

              <div className="field-grid">
                <Field label="Pickup window opens" htmlFor="window-start" error={errors.pickup_window_start?.message}>
                  <input id="window-start" type="datetime-local" className="input" {...register("pickup_window_start")} />
                </Field>
                <Field label="Pickup window closes" htmlFor="window-end" error={errors.pickup_window_end?.message}>
                  <input id="window-end" type="datetime-local" className="input" {...register("pickup_window_end")} />
                </Field>
                <Field label="Delivery deadline" htmlFor="deadline" error={errors.delivery_deadline?.message} hint="The delivery must be estimated to arrive before this time.">
                  <input id="deadline" type="datetime-local" className="input" {...register("delivery_deadline")} />
                </Field>
                <Field label="Notes for the partner (optional)" htmlFor="notes">
                  <input id="notes" className="input" placeholder="Building access, packing notes…" {...register("notes")} />
                </Field>
              </div>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <ReviewBlock title="Pickup" body={pickupLocation?.label ?? `${watched.pickup_area ?? "Custom"} — ${watched.pickup_address ?? ""}`} meta={pickupLocation?.area} />
                <ReviewBlock
                  title={mode === "return" ? "Authorised return destination" : "Recipient destination"}
                  body={destinationPreview}
                  meta={destinationLocation?.area ?? watched.destination_area}
                />
                <ReviewBlock
                  title="Parcel"
                  body={watched.parcel_description ?? "—"}
                  meta={`${formatWeight(Number(watched.weight_kg))} · ${Number(watched.volume_m3 ?? 0).toFixed(3)} m³`}
                />
                <ReviewBlock
                  title="Schedule"
                  body={formatDateTime(new Date(watched.pickup_window_start).toISOString())}
                  meta={`Window closes ${formatDateTime(new Date(watched.pickup_window_end).toISOString())} · Deadline ${formatDateTime(new Date(watched.delivery_deadline).toISOString())}`}
                />
              </div>
              <Callout tone="info" title="What happens next">
                ReTurn checks compatibility after submission. Nearby is not enough: windows, deadlines, capacity, handling,
                service area and a positive estimated saving must all pass before a shared batch is proposed. Grouping is
                not guaranteed, and the destination you entered is preserved.
              </Callout>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-5">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setStep((value) => Math.max(1, value - 1))}
              disabled={step === 1 || isSubmitting}
            >
              Back
            </button>
            {step < 3 ? (
              <button type="button" className="btn btn-primary" onClick={goNext}>
                Continue <ArrowRight size={16} aria-hidden />
              </button>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
                Submit {mode === "return" ? "return" : "parcel"} request
              </button>
            )}
          </div>
        </form>
      </div>

      <aside className="space-y-4">
        <div className="card card-pad">
          <p className="eyebrow">Request summary</p>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center gap-2">
              {mode === "return" ? <Package size={16} className="text-accent" aria-hidden /> : <MapPin size={16} className="text-[#2c6ca2]" aria-hidden />}
              <span className="font-medium">{mode === "return" ? "Product return" : "Send a parcel"}</span>
            </div>
            <SummaryRow label="Pickup" value={pickupLocation?.label ?? watched.pickup_area ?? "Choose a pickup"} />
            <SummaryRow
              label={mode === "return" ? "Authorised hub" : "Recipient"}
              value={
                mode === "return"
                  ? watched.authorized_hub_name || destinationLocation?.label || "Choose a hub"
                  : watched.recipient_name || "Add a recipient"
              }
            />
            <SummaryRow label="Parcel" value={watched.parcel_description || "Describe the parcel"} />
            <SummaryRow label="Pickup window" value={watched.pickup_window_start ? formatDateTime(new Date(watched.pickup_window_start).toISOString()) : "—"} />
          </div>
          <div className="mt-5">
            <RouteThreadMini />
          </div>
        </div>
        <Callout tone="warning" title="Destinations stay truthful">
          Return parcels always go to the authorised return destination you provide. Regular parcels always go to the
          recipient address. Grouping never merges the two.
        </Callout>
      </aside>
    </div>
  );
}

function ReviewBlock({ title, body, meta }: { title: string; body: string; meta?: string }) {
  return (
    <div className="rounded-control border bg-surface-muted p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-1 text-sm font-medium">{body}</p>
      {meta ? <p className="mt-1 text-xs text-muted">{meta}</p> : null}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 leading-5">{value}</p>
    </div>
  );
}

function RouteThreadMini() {
  return (
    <svg viewBox="0 0 280 70" className="h-[70px] w-full" aria-label="Pickup to destination route illustration">
      <path d="M20 50 C 70 50, 70 20, 130 20 S 190 50, 260 50" fill="none" stroke="#087C60" strokeWidth="2" strokeDasharray="6 5" />
      <circle cx="20" cy="50" r="8" fill="#087C60" />
      <circle cx="20" cy="50" r="3" fill="#fff" />
      <rect x="252" y="42" width="16" height="16" rx="4" fill="#2C6CA2" />
      <text x="24" y="66" fontSize="9" fill="#5E726F">Pickup</text>
      <text x="220" y="66" fontSize="9" fill="#5E726F">Destination</text>
    </svg>
  );
}

function LocationBlock({
  prefix,
  title,
  description,
  locations,
  custom,
  setCustom,
  register,
  errors,
  setValue,
  watch,
  onSelect,
}: {
  prefix: "pickup" | "destination";
  title: string;
  description: string;
  locations: Location[];
  custom: boolean;
  setCustom: (value: boolean) => void;
  register: ReturnType<typeof useForm<Values>>["register"];
  errors: ReturnType<typeof useForm<Values>>["formState"]["errors"];
  setValue: ReturnType<typeof useForm<Values>>["setValue"];
  watch: ReturnType<typeof useForm<Values>>["watch"];
  onSelect: (value: string) => void;
}) {
  const selected = watch(`${prefix}_location_id`);
  return (
    <section aria-labelledby={`${prefix}-heading`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id={`${prefix}-heading`} className="text-sm font-semibold">
            {title}
          </h3>
          <p className="text-xs leading-5 text-muted">{description}</p>
        </div>
        <button
          type="button"
          className="text-xs font-medium text-accent hover:underline"
          onClick={() => {
            const next = !custom;
            setCustom(next);
            if (next) {
              setValue(`${prefix}_location_id`, "");
            } else {
              setValue(`${prefix}_address`, "");
              setValue(`${prefix}_area`, "");
              setValue(`${prefix}_lat`, "");
              setValue(`${prefix}_lng`, "");
            }
          }}
        >
          {custom ? "Choose a sample location instead" : "Use a different address"}
        </button>
      </div>
      {!custom ? (
        <>
          <select
            className={`input ${errors[`${prefix}_location_id`] ? "input-error" : ""}`}
            aria-label={title}
            value={selected ?? ""}
            onChange={(event) => onSelect(event.target.value)}
          >
            <option value="">Select a sample location…</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.label} · {location.area}
              </option>
            ))}
          </select>
          {selected ? (
            <p className="help flex items-center gap-1">
              <MapPin size={12} aria-hidden /> Coordinates:{" "}
              {locations.find((item) => String(item.id) === selected)?.latitude.toFixed(4)},{" "}
              {locations.find((item) => String(item.id) === selected)?.longitude.toFixed(4)}
            </p>
          ) : (
            <p className="help">Sample locations are fictional demo places with approximate area coordinates.</p>
          )}
        </>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Address line" htmlFor={`${prefix}-address`} error={errors[`${prefix}_address`]?.message} className="sm:col-span-2">
            <input id={`${prefix}-address`} className="input" {...register(`${prefix}_address`)} />
          </Field>
          <Field label="Area" htmlFor={`${prefix}-area`} error={errors[`${prefix}_area`]?.message}>
            <input id={`${prefix}-area`} className="input" placeholder="e.g. Barasat" {...register(`${prefix}_area`)} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Latitude" htmlFor={`${prefix}-lat`} error={errors[`${prefix}_lat`]?.message}>
              <input id={`${prefix}-lat`} className="input" inputMode="decimal" placeholder="22.7241" {...register(`${prefix}_lat`)} />
            </Field>
            <Field label="Longitude" htmlFor={`${prefix}-lng`} error={errors[`${prefix}_lng`]?.message}>
              <input id={`${prefix}-lng`} className="input" inputMode="decimal" placeholder="88.4821" {...register(`${prefix}_lng`)} />
            </Field>
          </div>
        </div>
      )}
    </section>
  );
}
