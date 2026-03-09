export default function Footer() {
  return (
    <footer className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-2.5 flex items-center justify-between text-xs text-gray-400">
      <span>
        &copy; {new Date().getFullYear()} Border Omni &mdash; SaaS de Qualificação de Leads
      </span>
      <span className="font-mono">v1.0.0</span>
    </footer>
  );
}
