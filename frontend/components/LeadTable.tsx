"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { leadsApi, crmApi, type Lead } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Trash2, RefreshCw } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-100 text-blue-800",
  enriched: "bg-yellow-100 text-yellow-800",
  qualified: "bg-green-100 text-green-800",
  synced: "bg-purple-100 text-purple-800",
  rejected: "bg-red-100 text-red-800",
};

export default function LeadTable({ statusFilter }: { statusFilter?: string }) {
  const qc = useQueryClient();

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ["leads", statusFilter],
    queryFn: () => leadsApi.list(statusFilter).then((r) => r.data),
    refetchInterval: 15_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => leadsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });

  const syncMutation = useMutation({
    mutationFn: ({ id, crm }: { id: number; crm: string }) =>
      crmApi.sync(id, crm),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });

  if (isLoading) return <p className="text-gray-500">Loading leads…</p>;
  if (!leads.length) return <p className="text-gray-400">No leads found.</p>;

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {["Company", "Website", "Email", "Phone", "Status", "CRM", "Actions"].map(
              (h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500"
                >
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {leads.map((lead: Lead) => (
            <tr key={lead.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-900">{lead.company_name}</td>
              <td className="px-4 py-3">
                <a
                  href={lead.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:underline truncate max-w-[180px] block"
                >
                  {lead.website}
                </a>
              </td>
              <td className="px-4 py-3 text-gray-600">{lead.email ?? "—"}</td>
              <td className="px-4 py-3 text-gray-600">{lead.phone ?? "—"}</td>
              <td className="px-4 py-3">
                <span
                  className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-xs font-semibold",
                    STATUS_COLORS[lead.status] ?? "bg-gray-100 text-gray-700"
                  )}
                >
                  {lead.status}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-500">{lead.crm_source ?? "—"}</td>
              <td className="px-4 py-3 flex gap-2">
                <button
                  onClick={() => syncMutation.mutate({ id: lead.id, crm: "hubspot" })}
                  title="Sync to HubSpot"
                  className="rounded p-1 text-purple-500 hover:bg-purple-50"
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(lead.id)}
                  title="Delete"
                  className="rounded p-1 text-red-400 hover:bg-red-50"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
