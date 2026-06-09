"use client";

import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useOnboardingStore } from "@/stores/onboarding-store";

interface Customer {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  address?: string;
}

function CustomersContent() {
  const queryClient = useQueryClient();
  const completeStep = useOnboardingStore((s) => s.completeStep);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; phone?: string }>({});
  const [creating, setCreating] = useState(false);

  const { data, isLoading, error } = useQuery<{ customers: Customer[] }>({
    queryKey: ["customers"],
    queryFn: () => api.get("/jobs/customers").then((r) => r.data),
  });

  const handleCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: { email?: string; phone?: string } = {};
    if (email && !/\S+@\S+\.\S+/.test(email)) {
      errors.email = "Invalid email format";
    }
    if (phone && !/^[\d\s\-+()]+$/.test(phone)) {
      errors.phone = "Phone may contain only digits, spaces, dashes, parentheses, and +";
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    if (!name.trim() || creating) return;
    setCreating(true);
    try {
      await api.post("/jobs/customers", { name, email, phone, address });
      setName("");
      setEmail("");
      setPhone("");
      setAddress("");
      setShowForm(false);
      completeStep("customer");
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Failed to create customer:", err);
      }
      setFormError("Failed to create customer");
    } finally {
      setCreating(false);
    }
  }, [name, email, phone, address, creating, queryClient, completeStep]);

  const handleDelete = useCallback(async (customerId: string) => {
    if (!confirm("Delete this customer?")) return;
    try {
      setFormError(null);
      await api.delete(`/jobs/customers/${customerId}`);
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Failed to delete customer:", err);
      }
      setFormError("Failed to delete customer");
    }
  }, [queryClient]);

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Customer directory with contact info and job history."
        actions={
          <Button onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "+ Add Customer"}
          </Button>
        }
      />

      {formError && (
        <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {formError}
          <button type="button" onClick={() => setFormError(null)} className="ml-4 font-medium">
            Dismiss
          </button>
        </div>
      )}

      <div>
        {showForm && (
          <form onSubmit={handleCreate} className="bg-white rounded-xl shadow-sm p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">New Customer</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="customer-name" className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  id="customer-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2"
                  required
                />
              </div>
              <div>
                <label htmlFor="customer-email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  id="customer-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={`w-full border rounded-lg px-3 py-2 ${fieldErrors.email ? "border-red-300 bg-red-50" : "border-gray-300"}`}
                />
                {fieldErrors.email && (
                  <p className="text-red-500 text-xs mt-1">{fieldErrors.email}</p>
                )}
              </div>
              <div>
                <label htmlFor="customer-phone" className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  id="customer-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className={`w-full border rounded-lg px-3 py-2 ${fieldErrors.phone ? "border-red-300 bg-red-50" : "border-gray-300"}`}
                />
                {fieldErrors.phone && (
                  <p className="text-red-500 text-xs mt-1">{fieldErrors.phone}</p>
                )}
              </div>
              <div>
                <label htmlFor="customer-address" className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                <input
                  id="customer-address"
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={creating}
              className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create Customer"}
            </button>
          </form>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <p className="text-red-600 font-medium">Failed to load customers</p>
            <p className="text-red-400 text-sm mt-1">Check your connection and try again</p>
          </div>
        ) : !data?.customers?.length ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <p className="text-gray-400 text-lg mb-2">No customers yet</p>
            <p className="text-gray-400 text-sm">Add your first customer to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {data.customers.map((customer) => (
              <div
                key={customer.id}
                className="bg-white rounded-xl shadow-sm p-4 flex items-center justify-between"
              >
                <div>
                  <p className="font-medium">{customer.name}</p>
                  <div className="flex gap-4 text-sm text-gray-500 mt-1">
                    {customer.email && <span>{customer.email}</span>}
                    {customer.phone && <span>{customer.phone}</span>}
                    {customer.address && <span>{customer.address}</span>}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(customer.id)}
                  aria-label={`Delete customer ${customer.name}`}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CustomersPage() {
  return (
    <PermissionGate permission="customers:view">
      <CustomersContent />
    </PermissionGate>
  );
}
