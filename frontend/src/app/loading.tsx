export default function Loading() {
  return (
    <main className="container-page py-10">
      <div className="skeleton h-4 w-28" />
      <div className="skeleton mt-4 h-9 w-80 max-w-full" />
      <div className="skeleton mt-2 h-4 w-2/3 max-w-lg" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="skeleton h-28" />
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="skeleton h-80" />
        <div className="skeleton h-80" />
      </div>
    </main>
  );
}
