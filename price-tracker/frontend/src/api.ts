import axios from "axios";
import type { AlertEvent, Insights, Product, ProductCreate, SaleEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const API_TOKEN = import.meta.env.VITE_API_TOKEN;

const client = axios.create({
  baseURL: API_BASE,
  headers: API_TOKEN ? { "X-API-Token": API_TOKEN } : {},
});

export const api = {
  listProducts: () => client.get<Product[]>("/api/products").then((r) => r.data),

  addProduct: (payload: ProductCreate) =>
    client.post<Product>("/api/products", payload).then((r) => r.data),

  removeProduct: (id: string) => client.delete(`/api/products/${id}`),

  checkProduct: (id: string) =>
    client.post<Product>(`/api/products/${id}/check`).then((r) => r.data),

  checkAll: () => client.post<{ mode: string }>("/api/check-all").then((r) => r.data),

  listAlerts: (limit = 50) =>
    client.get<AlertEvent[]>("/api/alerts", { params: { limit } }).then((r) => r.data),

  listSales: () => client.get<SaleEvent[]>("/api/sales").then((r) => r.data),

  addSale: (payload: Omit<SaleEvent, "id">) =>
    client.post<SaleEvent>("/api/sales", payload).then((r) => r.data),

  removeSale: (id: string) => client.delete(`/api/sales/${id}`),

  insights: (saleId?: string) =>
    client
      .get<Insights>("/api/insights", { params: saleId ? { sale_id: saleId } : {} })
      .then((r) => r.data),
};
