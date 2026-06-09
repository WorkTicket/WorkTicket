"use client";

import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api, setTokenGetter } from "@/lib/api";
import { useAuth } from "@clerk/nextjs";
import { FutureFeature } from "@/components/future-feature";
import {
  enrichLineItemWithComputedTotal,
  recomputeEstimate,
  validateEstimate,
  roundCurrency,
} from "@/lib/ai-validation";

type LineItemType = "labor" | "materials" | "fee";

interface EstimateLineItem {
  id?: string;
  name: string;
  item_type: LineItemType;
  quantity: number;
  rate: number;
  total: number;
  sort_order: number;
  override_reason?: string;
  ai_quantity?: number | null;
  ai_rate?: number | null;
  ai_total?: number | null;
}

interface EstimateData {
  id: string;
  title?: string;
  status: string;
  subtotal?: number;
  tax?: number;
  total?: number;
  notes?: string;
  job_id?: string;
  line_items?: EstimateLineItem[];
  confidence_score?: number;
  assumptions?: string[];
}

type LineItemAction =
  | { type: "SET_ITEMS"; items: EstimateLineItem[] }
  | { type: "CHANGE_ITEM"; idx: number; field: keyof EstimateLineItem; value: string | number }
  | { type: "ADD_ITEM" }
  | { type: "REMOVE_ITEM"; idx: number };

function lineItemsReducer(state: EstimateLineItem[], action: LineItemAction): EstimateLineItem[] {
  switch (action.type) {
    case "SET_ITEMS":
      return action.items;
    case "CHANGE_ITEM": {
      const updated = [...state];
      const item = { ...updated[action.idx] };
      (item as Record<string, unknown>)[action.field] = action.value;
      if (action.field === "quantity" || action.field === "rate") {
        item.total = roundCurrency(item.quantity * item.rate);
      }
      updated[action.idx] = item;
      return updated;
    }
    case "ADD_ITEM": {
      const newItem: EstimateLineItem = {
        name: "",
        item_type: "labor",
        quantity: 1,
        rate: 0,
        total: 0,
        sort_order: state.length,
      };
      return [...state, newItem];
    }
    case "REMOVE_ITEM": {
      return state
        .filter((_, i) => i !== action.idx)
        .map((item, i) => ({ ...item, sort_order: i }));
    }
    default:
      return state;
  }
}

function EstimateEditorContent() {
  const { id } = useParams();
  const { getToken } = useAuth();
  const queryClient = useQueryClient();

  const [lineItems, dispatch] = useReducer(lineItemsReducer, []);
  const [tax, setTax] = useState(0);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const subtotal = useMemo(
    () => roundCurrency(lineItems.reduce((sum, item) => sum + item.total, 0)),
    [lineItems],
  );
  const total = useMemo(() => roundCurrency(subtotal + tax), [subtotal, tax]);

  useEffect(() => {
    setTokenGetter(getToken);
  }, [getToken]);

  const { data: estimate, isLoading } = useQuery<EstimateData>({
    queryKey: ["estimate", id],
    queryFn: () => api.get(`/estimates/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  useEffect(() => {
    if (estimate) {
      dispatch({
        type: "SET_ITEMS",
        items: (estimate.line_items || []).map((li) =>
          enrichLineItemWithComputedTotal({
            id: li.id,
            name: li.name,
            item_type: li.item_type,
            quantity: li.quantity,
            rate: li.rate,
            total: li.total,
            sort_order: li.sort_order,
            override_reason: li.override_reason || "",
            ai_quantity: li.ai_quantity,
            ai_rate: li.ai_rate,
            ai_total: li.ai_total,
          }),
        ),
      });
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTax(estimate.tax ?? 0);
      setNotes(estimate.notes ?? "");
    }
  }, [estimate]);

  const handleItemChange = useCallback(
    (idx: number, field: keyof EstimateLineItem, value: string | number) => {
      dispatch({ type: "CHANGE_ITEM", idx, field, value });
    },
    [],
  );

  const addLineItem = useCallback(() => {
    dispatch({ type: "ADD_ITEM" });
  }, []);

  const removeLineItem = useCallback((idx: number) => {
    dispatch({ type: "REMOVE_ITEM", idx });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const raw = {
        line_items: lineItems.map((item) => ({
          name: item.name,
          item_type: item.item_type,
          quantity: item.quantity,
          rate: item.rate,
          total: roundCurrency(item.quantity * item.rate),
          sort_order: item.sort_order,
          override_reason: item.override_reason || undefined,
        })),
        tax,
        notes: notes || undefined,
      };

      const validationErrors = validateEstimate(raw);
      if (validationErrors.length > 0) {
        setError(
          `Validation failed: ${validationErrors
            .map((e) => `${e.path}: ${e.message}`)
            .join("; ")}`,
        );
        setSaving(false);
        return;
      }

      const canonical = recomputeEstimate(raw);
      await api.put(`/estimates/${id}`, canonical);
      setTax(canonical.tax ?? 0);
      setSuccessMsg("Estimate saved");
      queryClient.invalidateQueries({ queryKey: ["estimate", id] });
      queryClient.invalidateQueries({ queryKey: ["estimates"] });
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Failed to save estimate:", err);
      }
      setError("Failed to save estimate");
    } finally {
      setSaving(false);
    }
  }, [lineItems, tax, notes, id, queryClient]);

  const handleApprove = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await api.post(`/estimates/${id}/approve`);
      setSuccessMsg("Estimate approved");
      queryClient.invalidateQueries({ queryKey: ["estimate", id] });
      queryClient.invalidateQueries({ queryKey: ["estimates"] });
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Failed to approve estimate:", err);
      }
      setError("Failed to approve estimate");
    } finally {
      setSaving(false);
    }
  }, [id, queryClient]);

  const handleSend = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await api.post(`/estimates/${id}/send`);
      setSuccessMsg("Estimate sent to customer");
      queryClient.invalidateQueries({ queryKey: ["estimate", id] });
      queryClient.invalidateQueries({ queryKey: ["estimates"] });
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Failed to send estimate:", err);
      }
      setError("Failed to send estimate");
    } finally {
      setSaving(false);
    }
  }, [id, queryClient]);

  const handleReopen = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await api.post(`/estimates/${id}/reopen`);
      setSuccessMsg("Estimate reopened for editing");
      queryClient.invalidateQueries({ queryKey: ["estimate", id] });
      queryClient.invalidateQueries({ queryKey: ["estimates"] });
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("Failed to reopen estimate:", err);
      }
      setError("Failed to reopen estimate");
    } finally {
      setSaving(false);
    }
  }, [id, queryClient]);

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading estimate" className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!estimate) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-red-600 font-medium">Estimate not found</p>
        </div>
        <Link href="/estimates" className="mt-4 inline-block text-blue-600 hover:text-blue-800">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const canEdit = estimate.status === "draft" || estimate.status === "in_review";
  const canApprove = estimate.status === "in_review";
  const canSend = estimate.status === "approved";
  const canReopen = estimate.status === "sent" || estimate.status === "rejected";

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <Link href="/estimates" className="text-blue-600 hover:text-blue-800 text-sm mb-1 inline-block">
              &larr; Dashboard
            </Link>
            <h1 className="text-xl font-bold text-gray-900">{estimate.title || "Estimate"}</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              estimate.status === "approved" ? "bg-green-100 text-green-700" :
              estimate.status === "sent" ? "bg-blue-100 text-blue-700" :
              estimate.status === "in_review" ? "bg-yellow-100 text-yellow-700" :
              estimate.status === "draft" ? "bg-gray-100 text-gray-700" :
              "bg-red-100 text-red-700"
            }`}>
              {estimate.status.replace("_", " ")}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6" id="main-content">
        {error && (
          <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}
        {successMsg && (
          <div role="alert" className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
            <p className="text-green-700 text-sm">{successMsg}</p>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-1 lg:grid-cols-2 gap-6">
          <FutureFeature featureId="estimate_suggestions" />

          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4 text-gray-900">Edit Estimate</h2>
            <div className="space-y-3">
              <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 px-2">
                <div className="col-span-3">Item</div>
                <div className="col-span-1">Type</div>
                <div className="col-span-2 text-right">Qty</div>
                <div className="col-span-2 text-right">Rate</div>
                <div className="col-span-2 text-right">Total</div>
                <div className="col-span-2"></div>
              </div>
              {lineItems.map((item, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-2 items-center px-2 py-1 rounded hover:bg-gray-50">
                  <label htmlFor={`line-item-name-${idx}`} className="sr-only">Item name</label>
                  <input
                    id={`line-item-name-${idx}`}
                    className="col-span-3 border border-gray-200 rounded px-2 py-1 text-sm"
                    value={item.name}
                    onChange={(e) => handleItemChange(idx, "name", e.target.value)}
                    disabled={!canEdit}
                    placeholder="Item name"
                  />
                  <label htmlFor={`line-item-type-${idx}`} className="sr-only">Item type</label>
                  <select
                    id={`line-item-type-${idx}`}
                    className="col-span-1 border border-gray-200 rounded px-1 py-1 text-sm"
                    value={item.item_type}
                    onChange={(e) => handleItemChange(idx, "item_type", e.target.value)}
                    disabled={!canEdit}
                  >
                    <option value="labor">Labor</option>
                    <option value="materials">Mat.</option>
                    <option value="fee">Fee</option>
                  </select>
                  <label htmlFor={`line-item-qty-${idx}`} className="sr-only">Quantity</label>
                  <input
                    id={`line-item-qty-${idx}`}
                    className="col-span-2 border border-gray-200 rounded px-2 py-1 text-sm text-right"
                    type="number"
                    step="0.5"
                    value={item.quantity}
                    onChange={(e) => handleItemChange(idx, "quantity", parseFloat(e.target.value) || 0)}
                    disabled={!canEdit}
                  />
                  <label htmlFor={`line-item-rate-${idx}`} className="sr-only">Rate</label>
                  <input
                    id={`line-item-rate-${idx}`}
                    className="col-span-2 border border-gray-200 rounded px-2 py-1 text-sm text-right"
                    type="number"
                    step="1"
                    value={item.rate}
                    onChange={(e) => handleItemChange(idx, "rate", parseFloat(e.target.value) || 0)}
                    disabled={!canEdit}
                  />
                  <div className="col-span-2 text-sm text-right font-medium">
                    ${roundCurrency(item.quantity * item.rate).toFixed(2)}
                  </div>
                  <div className="col-span-2 flex justify-end gap-1">
                    {canEdit && (
                      <button
                        onClick={() => removeLineItem(idx)}
                        aria-label={`Remove ${item.name || "item"}`}
                        className="text-red-400 hover:text-red-600 text-xs"
                      >
                        ×
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {canEdit && (
                <button
                  onClick={addLineItem}
                  className="w-full border-2 border-dashed border-gray-200 rounded-lg py-2 text-sm text-gray-400 hover:text-gray-600 hover:border-gray-300"
                >
                  + Add line item
                </button>
              )}
            </div>

            <div className="mt-6 pt-4 border-t border-gray-200 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Subtotal</span>
                <span className="font-medium">${subtotal.toFixed(2)}</span>
              </div>
              {canEdit && (
                <div className="flex justify-between text-sm items-center">
                  <label htmlFor="estimate-tax" className="text-gray-500">Tax</label>
                  <input
                    id="estimate-tax"
                    className="border border-gray-200 rounded px-2 py-1 text-sm w-24 text-right"
                    type="number"
                    step="0.01"
                    value={tax}
                    onChange={(e) => {
                      setTax(parseFloat(e.target.value) || 0);
                    }}
                  />
                </div>
              )}
              {!canEdit && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Tax</span>
                  <span className="font-medium">${tax.toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between text-lg font-bold">
                <span>Total</span>
                <span className="text-blue-600">${total.toFixed(2)}</span>
              </div>
            </div>

            {canEdit && (
              <div className="mt-4">
                <label htmlFor="estimate-notes" className="block text-sm text-gray-500 mb-1">Notes</label>
                <textarea
                  id="estimate-notes"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Internal notes..."
                />
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {canEdit && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          )}
          {canApprove && (
            <button
              onClick={handleApprove}
              disabled={saving}
              className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
            >
              Approve Estimate
            </button>
          )}
          {canSend && (
            <button
              onClick={handleSend}
              disabled={saving}
              className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
            >
              Send to Customer
            </button>
          )}
          {canReopen && (
            <button
              onClick={handleReopen}
              disabled={saving}
              className="bg-yellow-500 text-white px-6 py-2 rounded-lg font-medium hover:bg-yellow-600 disabled:opacity-50"
            >
              Reopen for Editing
            </button>
          )}
          <Link href="/estimates" className="text-gray-500 hover:text-gray-700 px-4 py-2 text-sm">
            Back to Dashboard
          </Link>
        </div>
      </main>
    </div>
  );
}

export default function EstimateDetailPage() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30000, retry: 1 },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <EstimateEditorContent />
    </QueryClientProvider>
  );
}
