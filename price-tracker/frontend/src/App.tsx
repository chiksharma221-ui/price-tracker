import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { useState } from "react";
import { api } from "./api";
import AddProductModal from "./components/AddProductModal";
import AlertsPanel from "./components/AlertsPanel";
import EmptyState from "./components/EmptyState";
import Header, { type View } from "./components/Header";
import InsightsView from "./components/InsightsView";
import ProductCard from "./components/ProductCard";
import ProductDetailDrawer from "./components/ProductDetailDrawer";
import SkeletonCard from "./components/SkeletonCard";
import StatsRow from "./components/StatsRow";
import type { Product } from "./types";

const POLL_MS = 15_000;

export default function App() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [view, setView] = useState<View>("products");

  const salesQuery = useQuery({ queryKey: ["sales"], queryFn: api.listSales });

  const productsQuery = useQuery({
    queryKey: ["products"],
    queryFn: api.listProducts,
    refetchInterval: POLL_MS,
  });

  const alertsQuery = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.listAlerts(),
    refetchInterval: POLL_MS,
  });

  const addMutation = useMutation({
    mutationFn: api.addProduct,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setModalOpen(false);
      setAddError(null);
    },
    onError: (err: any) => {
      setAddError(err?.response?.data?.detail ?? "Couldn't reach the API. Is the backend running?");
    },
  });

  const removeMutation = useMutation({
    mutationFn: api.removeProduct,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });

  const checkAllMutation = useMutation({
    mutationFn: api.checkAll,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  async function handleCheckOne(id: string) {
    setCheckingId(id);
    try {
      await api.checkProduct(id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["products"] }),
        queryClient.invalidateQueries({ queryKey: ["alerts"] }),
      ]);
    } finally {
      setCheckingId(null);
    }
  }

  const products = productsQuery.data ?? [];
  const showingDemoData = products.some((p) => p.history.some((h) => h.source === "simulated"));
  const alerts = alertsQuery.data ?? [];
  const selected: Product | null = products.find((p) => p.id === selectedId) ?? null;
  const lastUpdated = productsQuery.dataUpdatedAt ? new Date(productsQuery.dataUpdatedAt) : null;

  return (
    <div className="min-h-screen pb-16">
      <Header
        view={view}
        onViewChange={setView}
        onAdd={() => setModalOpen(true)}
        onCheckAll={() => checkAllMutation.mutate()}
        checkingAll={checkAllMutation.isPending}
        lastUpdated={lastUpdated}
      />

      <main className="mx-auto max-w-6xl px-6 pt-6">
        {productsQuery.isError && (
          <div className="mb-4 rounded-xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-[13px] text-rose-300">
            Couldn't reach the API at the configured backend URL. Make sure{" "}
            <code className="rounded bg-black/30 px-1 py-0.5">uvicorn price_tracker.api:app</code> is running.
          </div>
        )}

        {showingDemoData && (
          <div className="mb-4 rounded-xl border border-amber-400/20 bg-amber-400/[0.07] px-4 py-2.5 text-[12.5px] text-amber-200/90">
            Showing simulated demo data from <code className="rounded bg-black/30 px-1">seed_demo.py</code>. These
            numbers are not real marketplace findings.
          </div>
        )}

        <div className="mb-4 flex rounded-lg border border-white/10 bg-white/[0.03] p-0.5 sm:hidden">
          {(["products", "insights"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`flex-1 rounded-md px-3 py-1.5 text-[12.5px] font-medium ${
                view === v ? "bg-white/[0.09] text-white" : "text-white/45"
              }`}
            >
              {v === "products" ? "Products" : "Sale insights"}
            </button>
          ))}
        </div>

        {view === "insights" ? (
          <InsightsView sales={salesQuery.data ?? []} />
        ) : (
        <>
        <div className="mb-6">
          {/* Stats row waits for real data so numbers don't flash from 0 */}
          {!productsQuery.isLoading && <StatsRow products={products} alerts={alerts} />}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {productsQuery.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}

            {!productsQuery.isLoading && products.length === 0 && (
              <EmptyState onAdd={() => setModalOpen(true)} />
            )}

            <AnimatePresence mode="popLayout">
              {products.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  checking={checkingId === product.id}
                  onOpen={() => setSelectedId(product.id)}
                  onCheck={() => handleCheckOne(product.id)}
                  onRemove={() => removeMutation.mutate(product.id)}
                />
              ))}
            </AnimatePresence>
          </div>

          <AlertsPanel alerts={alerts} />
        </div>
        </>
        )}
      </main>

      <AddProductModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setAddError(null);
        }}
        onSubmit={(data) => addMutation.mutate(data)}
        submitting={addMutation.isPending}
        error={addError}
      />

      <ProductDetailDrawer product={selected} sales={salesQuery.data ?? []} onClose={() => setSelectedId(null)} />
    </div>
  );
}
