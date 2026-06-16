import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(dateString) {
  const options = { year: "numeric", month: "short", day: "numeric" };
  return new Date(dateString).toLocaleDateString("en-IN", options);
}

export function getRiskColor(score) {
  if (score >= 80) return "text-red-600 bg-red-50";
  if (score >= 50) return "text-amber-600 bg-amber-50";
  return "text-emerald-600 bg-emerald-50";
}
