import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Tag, X } from "lucide-react";
import { useState } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: { url: string; name?: string; category?: string; target_price?: number }) => void;
  submitting: boolean;
  error: string | null;
}

export default function AddProductModal({ open, onClose, onSubmit, submitting, error }: Props) {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [category, setCategory] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit({
      url: url.trim(),
      name: name.trim() || undefined,
      category: category.trim() || undefined,
      target_price: targetPrice ? Number(targetPrice) : undefined,
    });
  }

  function handleClose() {
    setUrl("");
    setName("");
    setTargetPrice("");
    setCategory("");
    onClose();
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2"
          >
            <div className="glass rounded-2xl p-5 shadow-2xl shadow-black/50">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="btn-primary flex h-7 w-7 items-center justify-center rounded-lg">
                    <Tag className="h-3.5 w-3.5 text-white" />
                  </div>
                  <h2 className="text-[15px] font-semibold text-white">Track a new product</h2>
                </div>
                <button
                  onClick={handleClose}
                  className="focus-ring rounded-lg p-1 text-white/40 hover:bg-white/[0.06] hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/50">
                    Product URL
                  </label>
                  <input
                    autoFocus
                    required
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://www.amazon.in/dp/..."
                    className="focus-ring w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-white placeholder:text-white/25"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-white/50">
                      Name <span className="text-white/25">(optional)</span>
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Auto-detected"
                      className="focus-ring w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-white placeholder:text-white/25"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-white/50">
                      Target price <span className="text-white/25">(optional)</span>
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={targetPrice}
                      onChange={(e) => setTargetPrice(e.target.value)}
                      placeholder="1999"
                      className="focus-ring w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-white placeholder:text-white/25"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-[11px] font-medium text-white/50">
                    Category <span className="text-white/25">(used to group the sale report)</span>
                  </label>
                  <input
                    type="text"
                    list="category-suggestions"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="Electronics"
                    className="focus-ring w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-white placeholder:text-white/25"
                  />
                  <datalist id="category-suggestions">
                    {["Electronics", "Appliances", "Fashion", "Home & Kitchen", "Personal Care"].map((c) => (
                      <option key={c} value={c} />
                    ))}
                  </datalist>
                </div>

                {error && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-[12px] text-rose-300">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary focus-ring flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-fuchsia-500/10 transition hover:brightness-110 disabled:opacity-60"
                >
                  {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  {submitting ? "Fetching current price…" : "Start tracking"}
                </button>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
