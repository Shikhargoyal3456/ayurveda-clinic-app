interface LiveProjectButtonProps {
  className?: string;
}

export default function LiveProjectButton({ className = '' }: LiveProjectButtonProps) {
  return (
    <button
      className={`rounded-full border-2 border-[#D7E2EA] px-8 py-3 text-sm font-medium uppercase tracking-widest text-[#D7E2EA] transition-all duration-300 hover:bg-[#D7E2EA]/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#D7E2EA] sm:px-10 sm:py-3.5 sm:text-base ${className}`}
    >
      Live Project
    </button>
  );
}
