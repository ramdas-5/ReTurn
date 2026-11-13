export default function CustomerLoading() {
  return (
    <div>
      <div className="skeleton h-3 w-24" />
      <div className="skeleton mt-3 h-9 w-72 max-w-full" />
      <div className="skeleton mt-2 h-4 w-96 max-w-full" />
      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="skeleton h-28" />
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <div className="skeleton h-72" />
        <div className="skeleton h-72" />
      </div>
    </div>
  );
}
