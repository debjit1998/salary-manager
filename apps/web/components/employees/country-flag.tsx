import type { Country } from "@/types/api";

const FLAGS: Record<Country, string> = { US: "🇺🇸", UK: "🇬🇧", IN: "🇮🇳" };

export function CountryFlag({ country }: { country: Country }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span aria-hidden>{FLAGS[country]}</span>
      <span>{country}</span>
    </span>
  );
}
