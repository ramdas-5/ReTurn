import { Search, Users } from "lucide-react";
import Link from "next/link";

import { CustomerAccountAction } from "@/components/admin/AdminActions";
import { Callout, Card, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { formatDateTime, initials } from "@/lib/format";
import { requireUser, serverFetchList } from "@/lib/server";
import type { ApiUser } from "@/lib/types";

export const metadata = { title: "Customers" };

type CustomerRow = ApiUser & { request_count: number };

export default async function AdminCustomersPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  await requireUser("admin");
  const params = await searchParams;
  const query = params.q ? `?q=${encodeURIComponent(params.q)}` : "";
  const { data: customers } = await serverFetchList<CustomerRow>(`/customers${query}`);

  return (
    <div>
      <PageHeader
        eyebrow="Account management"
        title="Customers"
        description="Inspect customer accounts and safely disable access when necessary. Disabling preserves requests, batches and tracking history."
        actions={
          <Link href="/admin/requests" className="btn btn-secondary">
            Request queue
          </Link>
        }
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Customers" value={customers.length} hint="Accounts in this view" icon={<Users size={17} aria-hidden />} tone="accent" />
        <StatCard label="Active accounts" value={customers.filter((customer) => !customer.disabled).length} hint="Can sign in" />
        <StatCard label="Disabled" value={customers.filter((customer) => customer.disabled).length} hint="Sessions revoked" tone={customers.some((customer) => customer.disabled) ? "red" : "default"} />
      </div>

      <form className="card card-pad mb-5 flex flex-col gap-3 sm:flex-row sm:items-end" method="get">
        <div className="flex-1">
          <label className="label" htmlFor="customer-search">Search customers</label>
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
            <input id="customer-search" name="q" defaultValue={params.q ?? ""} className="input pl-9" placeholder="Name or email" />
          </div>
        </div>
        <button type="submit" className="btn btn-primary">Search</button>
        <Link href="/admin/customers" className="btn btn-ghost">Clear</Link>
      </form>

      {customers.length === 0 ? (
        <EmptyState icon={<Users size={20} aria-hidden />} title="No customers found" description="No account matches this search." />
      ) : (
        <Card className="overflow-hidden">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Customer</th>
                  <th scope="col">Contact</th>
                  <th scope="col">Requests</th>
                  <th scope="col">Joined</th>
                  <th scope="col">Account</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-[11px] font-bold text-accent-strong">
                          {initials(customer.name)}
                        </span>
                        <div>
                          <p className="text-[13px] font-medium">{customer.name}</p>
                          <p className="mono text-[10px] text-muted">RTN-USR-{1000 + customer.id}</p>
                        </div>
                      </div>
                    </td>
                    <td>
                      <p className="text-[12px]">{customer.email}</p>
                      <p className="text-[11px] text-muted">{customer.phone ?? "No phone"}</p>
                    </td>
                    <td className="mono">{customer.request_count}</td>
                    <td className="text-[12px] text-muted">{formatDateTime(customer.created_at)}</td>
                    <td>
                      <span className={`chip ${customer.disabled ? "chip-red" : "chip-green"}`}>
                        {customer.disabled ? "Disabled" : "Active"}
                      </span>
                    </td>
                    <td>
                      <CustomerAccountAction customer={customer} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="mt-5">
        <Callout tone="info" title="Privacy-scoped administration">
          Customer contact details are shown here for operational support only. They are never part of a public page and are
          not exposed to partners before acceptance. Disabling an account is audited.
        </Callout>
      </div>
    </div>
  );
}
