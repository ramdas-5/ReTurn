export default function PartnerLoading() {
  return (
    <div>
      <div className="skeleton h-3 w-28" />
      <div className="skeleton mt-3 h-9 w-64 max-w-full" />
      <div className="skeleton mt-2 h-4 w-80 max-w-full" />
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="skeleton h-28" />
        ))}
      </div>
      <div className="mt-6 skeleton h-96" />
    </div>
  );
}
