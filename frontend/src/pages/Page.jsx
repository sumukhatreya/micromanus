export default function Page({ title, children }) {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-gray-500">{children}</p>
    </main>
  )
}
