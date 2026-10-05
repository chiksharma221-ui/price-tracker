import { motion } from "framer-motion";
import { PackagePlus } from "lucide-react";

interface Props {
  onAdd: () => void;
}

export default function EmptyState({ onAdd }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass col-span-full flex flex-col items-center justify-center gap-3 rounded-2xl border-dashed py-16 text-center"
    >
      <div className="rounded-2xl bg-white/[0.04] p-3">
        <PackagePlus className="h-6 w-6 text-white/40" />
      </div>
      <div>
        <p className="text-[14px] font-semibold text-white/80">Nothing tracked yet</p>
        <p className="mt-1 text-[12.5px] text-white/35">
          Paste a product URL to start watching its price.
        </p>
      </div>
      <button
        onClick={onAdd}
        className="btn-primary focus-ring mt-1 rounded-lg px-4 py-2 text-[13px] font-semibold text-white shadow-lg shadow-fuchsia-500/10 hover:brightness-110"
      >
        Track your first product
      </button>
    </motion.div>
  );
}
