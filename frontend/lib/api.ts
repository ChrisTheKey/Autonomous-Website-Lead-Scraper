import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

export interface Lead {
  id: number;
  company_name: string;
  website: string;
  email: string | null;
  phone: string | null;
  status: "new" | "enriched" | "qualified" | "synced" | "rejected";
  ai_summary: string | null;
  crm_id: string | null;
  crm_source: string | null;
}

export interface ScrapeRequest {
  url: string;
  use_browser?: boolean;
  depth?: number;
}

export const leadsApi = {
  list: (status?: string) =>
    api.get<Lead[]>("/api/leads/", { params: status ? { status } : {} }),
  get: (id: number) => api.get<Lead>(`/api/leads/${id}`),
  delete: (id: number) => api.delete(`/api/leads/${id}`),
};

export const scraperApi = {
  start: (payload: ScrapeRequest) => api.post("/api/scraper/", payload),
  status: (taskId: string) => api.get(`/api/scraper/${taskId}`),
};

export const mapsApi = {
  businessSearch: (query: string, location: string, radius = 5000) =>
    api.post("/api/maps/business-search", { query, location, radius_meters: radius }),
  geocode: (address: string) => api.get("/api/maps/geocode", { params: { address } }),
};

export const crmApi = {
  sync: (lead_id: number, crm: string) =>
    api.post("/api/crm/sync", { lead_id, crm }),
};

export default api;
