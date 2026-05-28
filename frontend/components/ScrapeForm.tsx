"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { scraperApi } from "@/lib/api";

export default function ScrapeForm() {
  const qc = useQueryClient();
  const [url, setUrl] = useState("");
  const [useBrowser, setUseBrowser] = useState(false);
  const [lastTask, setLastTask] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => scraperApi.start({ url, use_browser: useBrowser }),
    onSuccess: (res) => {
      setLastTask(res.data.task_id);
      setUrl("");
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-gray-800">Scrape a new website</h2>
      <div className="flex flex-col gap-3">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={useBrowser}
            onChange={(e) => setUseBrowser(e.target.checked)}
            className="accent-blue-600"
          />
          Use Playwright browser (for JS-heavy sites)
        </label>
        <button
          onClick={() => mutation.mutate()}
          disabled={!url || mutation.isPending}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? "Queuing…" : "Start Scrape"}
        </button>
        {lastTask && (
          <p className="text-xs text-green-600">
            Job queued — Task ID: <code>{lastTask}</code>
          </p>
        )}
        {mutation.isError && (
          <p className="text-xs text-red-500">
            Error: {String((mutation.error as Error).message)}
          </p>
        )}
      </div>
    </div>
  );
}
