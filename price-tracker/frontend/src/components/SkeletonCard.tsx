export default function SkeletonCard() {
  return (
    <div className="glass animate-pulse rounded-2xl p-4">
      <div className="h-3.5 w-2/3 rounded bg-white/[0.06]" />
      <div className="mt-2 h-2.5 w-1/3 rounded bg-white/[0.04]" />
      <div className="mt-4 h-7 w-1/2 rounded bg-white/[0.06]" />
      <div className="mt-3 h-14 w-full rounded bg-white/[0.03]" />
      <div className="mt-3 h-1.5 w-full rounded-full bg-white/[0.04]" />
    </div>
  );
}
